import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from PIL import Image
import os
import re
import pytesseract
import sys
import io
from typing import Optional, Dict, Tuple, Any, List
import concurrent.futures 
import threading # NOVO: Para não bloquear a GUI
import queue # NOVO: Para comunicação thread-safe

# --- CONFIGURAÇÃO E VARIÁVEIS GLOBAIS ---
DEFAULT_MAX_FOLHAS = 300
DEFAULT_PROCESSES = 4 
OCR_ROI = (450, 50, 950, 250)
LIMIAR_CARACTERES_VERSO = 250
PSM_CONFIG = r'--oem 3 -l por --psm 6'
CORRECOES_MANUAIS: Dict[str, int] = {}
# Exemplo de configuração do Tesseract para Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'


# --- FUNÇÃO WORKER PARALELA (Roda em um PROCESSO separado) ---

def _run_ocr_worker(input_path: str, max_folhas: int) -> Tuple[str, Optional[int], str, bytes]:
    """
    Função de worker que executa o OCR, a rotação e a extração de dados
    para UMA ÚNICA imagem. Roda em um processo separado.
    """
    try:
        filename = os.path.basename(input_path)
        img = Image.open(input_path)

        # 1. ROTAÇÃO INTELIGENTE
        if img.width > img.height:
            img_neg90 = img.rotate(-90, expand=True)
            if verificar_sucesso_ocr_roi(img_neg90, OCR_ROI, PSM_CONFIG):
                img = img_neg90
            else:
                img = img.rotate(90, expand=True)

        # 2. OCR, Extração e Texto Completo
        folha_num_ocr, full_ocr_text = extrair_numero_folha_ocr_worker(img, max_folhas)

        # 3. Converter imagem (possivelmente rotacionada) para bytes
        img_byte_arr = io.BytesIO()
        # Salva como PNG para evitar perda de qualidade na transmissão
        img.save(img_byte_arr, format='PNG') 
        img_bytes = img_byte_arr.getvalue()
        
        # 4. Retorna todos os dados
        return (filename, folha_num_ocr, full_ocr_text, img_bytes)

    except Exception as e:
        # Retorna erro para ser tratado no processo principal
        return (os.path.basename(input_path), None, f"ERRO INTERNO NO WORKER: {e}", b'')

def verificar_sucesso_ocr_roi(image: Image.Image, ocr_roi: tuple, psm_config: str) -> bool:
    """Verifica se um padrão de número de folha válido pode ser encontrado na ROI (Usado pelo worker)."""
    img_width, img_height = image.size
    x_min = int(img_width * ocr_roi[0] / 1000)
    y_min = int(img_height * ocr_roi[1] / 1000)
    x_max = int(img_width * ocr_roi[2] / 1000)
    y_max = int(img_height * ocr_roi[3] / 1000)
    crop_box = (x_min, y_min, x_max, y_max)
    
    try:
        cropped_image = image.crop(crop_box)
        text_roi = pytesseract.image_to_string(cropped_image, config=psm_config)
        match = re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', text_roi.upper())
        return match is not None
    except Exception:
        return False

def extrair_numero_folha_ocr_worker(image: Image.Image, max_folhas: int) -> Tuple[Optional[int], str]:
    """Extrai Termos Especiais e Números de Folha (Usado pelo worker)."""
    full_text = ""
    try:
        # Tenta OCR com psm 3 (página inteira) para Termos Especiais
        full_text = pytesseract.image_to_string(image, config=r'--oem 3 -l por --psm 3')
        upper_text = full_text.upper()

        if "TERMO DE ABERTURA" in upper_text or "TERMO DE INSTALAÇÃO" in upper_text:
            return 0, full_text
        if "TERMO DE ENCERRAMENTO" in upper_text:
            return max_folhas + 1, full_text
            
    except Exception:
        pass

    try:
        # Tenta OCR com psm 6 (ROI) para número da folha
        img_width, img_height = image.size
        x_min = int(img_width * OCR_ROI[0] / 1000)
        y_min = int(img_height * OCR_ROI[1] / 1000)
        x_max = int(img_width * OCR_ROI[2] / 1000)
        y_max = int(img_height * OCR_ROI[3] / 1000)
        crop_box = (x_min, y_min, x_max, y_max)
        
        cropped_image = image.crop(crop_box)
        text_roi = pytesseract.image_to_string(cropped_image, config=PSM_CONFIG)
        upper_text_roi = text_roi.upper()

        match = re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', upper_text_roi)
        if match:
            folha_numero = int(match.group(2))
            return folha_numero, full_text
        
        return None, full_text

    except Exception:
        return None, full_text


class OCR_App:
    def __init__(self, master):
        self.master = master
        master.title("Organizador de Livros (Acelerado e Responsivo)")
        
        # --- VARIÁVEIS DE CONTROLE DO TKINTER ---
        self.input_dir_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.max_folhas_var = tk.IntVar(value=DEFAULT_MAX_FOLHAS)
        self.num_processes_var = tk.IntVar(value=DEFAULT_PROCESSES)
        
        # --- VARIÁVEIS DE CONTROLE DE THREADS E ESTADO ---
        self.log_queue = queue.Queue() # Fila para comunicação thread-safe
        self.processing_thread = None 
        self.executor = None # Para armazenar o ProcessPoolExecutor para cancelamento
        self.is_processing = False
        self.ultima_folha_processada = 0
        self.correcoes_manuais = CORRECOES_MANUAIS.copy()
        
        self.create_widgets()
        # Inicia a verificação periódica da fila de log para atualizar a GUI
        self.master.after(100, self.check_log_queue) 
        
    def log(self, message):
        """Método que adiciona mensagens à fila de log (thread-safe)."""
        self.log_queue.put(message)

    def check_log_queue(self):
        """Verifica a fila de log e atualiza o widget na thread principal (GUI)."""
        while not self.log_queue.empty():
            message = self.log_queue.get()
            self.enable_log_edit(True)
            self.log_widget.insert(tk.END, message + "\n")
            self.log_widget.see(tk.END)
            self.enable_log_edit(False)
        # Agenda a próxima verificação
        self.master.after(100, self.check_log_queue)

    def create_widgets(self):
        main_frame = tk.Frame(self.master, padx=10, pady=10)
        main_frame.pack(fill='both', expand=True)

        # 1. Diretório de Entrada
        tk.Label(main_frame, text="1. Pasta de Entrada (JPGs):", anchor="w").grid(row=0, column=0, sticky="w", pady=5, columnspan=2)
        tk.Entry(main_frame, textvariable=self.input_dir_var, width=60).grid(row=1, column=0, sticky="ew", padx=(0, 5))
        tk.Button(main_frame, text="Selecionar", command=self.select_input_dir).grid(row=1, column=1, sticky="e")

        # 2. Diretório de Saída
        tk.Label(main_frame, text="2. Pasta de Saída (PDFs):", anchor="w").grid(row=2, column=0, sticky="w", pady=5, columnspan=2)
        tk.Entry(main_frame, textvariable=self.output_dir_var, width=60).grid(row=3, column=0, sticky="ew", padx=(0, 5))
        tk.Button(main_frame, text="Selecionar", command=self.select_output_dir).grid(row=3, column=1, sticky="e")

        # 3. Máximo de Folhas e Processos Paralelos
        config_frame = tk.Frame(main_frame)
        config_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)
        
        tk.Label(config_frame, text="3. Máximo de Folhas:").pack(side=tk.LEFT, padx=(0, 5))
        tk.Entry(config_frame, textvariable=self.max_folhas_var, width=5).pack(side=tk.LEFT, padx=(0, 20))
        
        tk.Label(config_frame, text="4. Processos Paralelos:").pack(side=tk.LEFT, padx=(0, 5))
        tk.Entry(config_frame, textvariable=self.num_processes_var, width=5).pack(side=tk.LEFT)

        # 5. Botões de Ação
        action_frame = tk.Frame(main_frame)
        action_frame.grid(row=6, column=0, columnspan=2, pady=20, sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=1)

        # MUDANÇA: Chama o método que inicia o thread
        self.start_button = tk.Button(action_frame, text="INICIAR", bg="#4CAF50", fg="white", font=("Helvetica", 12, "bold"),
                                      command=self.start_processing_thread) 
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        # O botão Encerrar AGORA funcionará porque a GUI não está bloqueada
        self.stop_button = tk.Button(action_frame, text="ENCERRAR", bg="#f44336", fg="white", font=("Helvetica", 12, "bold"),
                                     command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, sticky="ew")

        # 6. Log de Status
        tk.Label(main_frame, text="Log de Status:", anchor="w").grid(row=7, column=0, sticky="w", pady=5, columnspan=2)
        self.log_widget = scrolledtext.ScrolledText(main_frame, height=15, state='disabled', wrap=tk.WORD, font=("Consolas", 9))
        self.log_widget.grid(row=8, column=0, columnspan=2, sticky="nsew")

        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(8, weight=1)

    def select_input_dir(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.input_dir_var.set(folder_selected)
            if not self.output_dir_var.get():
                output_default = os.path.join(folder_selected, os.path.basename(folder_selected) + "_editados")
                self.output_dir_var.set(output_default)
            self.log(f"Pasta de entrada selecionada: {folder_selected}")

    def select_output_dir(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.output_dir_var.set(folder_selected)
            self.log(f"Pasta de saída selecionada: {folder_selected}")

    def enable_log_edit(self, enable=True):
        """Habilita/Desabilita a edição do widget de log para inserção de texto."""
        self.log_widget.config(state='normal' if enable else 'disabled')
        
    def set_controls_state(self, is_running: bool):
        """Alterna o estado dos botões e campos de entrada."""
        # Atrasado para a thread principal (via after(0)) para segurança
        state = tk.DISABLED if is_running else tk.NORMAL
        self.start_button.config(state=tk.DISABLED if is_running else tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL if is_running else tk.DISABLED)
        
    def ask_manual_correction(self, filename: str) -> Optional[int]:
        """Abre uma nova janela (modal) para correção manual."""
        # Mantido o mesmo código do modal, pois ele é bloqueante APENAS para o thread worker.
        modal = tk.Toplevel(self.master)
        modal.title("Correção Manual de Folha")
        modal.transient(self.master)
        modal.grab_set()
        modal.geometry("400x180")
        
        result = None
        
        def on_submit():
            nonlocal result
            try:
                num = int(entry.get())
                if num >= 0:
                    result = num
                    modal.destroy()
                else:
                    messagebox.showerror("Erro", "O número da folha deve ser zero ou positivo.", parent=modal)
            except ValueError:
                messagebox.showerror("Erro", "Por favor, insira um número inteiro válido.", parent=modal)

        tk.Label(modal, text="!!! INTERVENÇÃO NECESSÁRIA !!!", font=("Helvetica", 10, "bold")).pack(pady=5)
        tk.Label(modal, text=f"Arquivo: {filename}").pack()
        tk.Label(modal, text=f"Última Folha Processada: FL. {self.ultima_folha_processada:03d}").pack()
        tk.Label(modal, text="Digite o número CORRETO da folha (0 para Termo de Abertura):").pack(pady=5)
        
        entry = tk.Entry(modal, width=10)
        entry.insert(0, str(self.ultima_folha_processada + 1))
        entry.pack()
        entry.bind("<Return>", lambda event: on_submit())
        entry.focus_set()

        def on_ignore():
            nonlocal result
            result = None
            modal.destroy()

        button_frame = tk.Frame(modal)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Confirmar", command=on_submit, bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Ignorar (Salvar como ERRO_OCR)", command=on_ignore, bg="#f44336", fg="white").pack(side=tk.LEFT, padx=10)

        # BLOQUEIA O THREAD DE PROCESSAMENTO (não a GUI principal)
        self.master.wait_window(modal)
        
        return result

    def start_processing_thread(self):
        """Inicia a lógica principal em um novo thread para não bloquear a GUI."""
        if self.is_processing:
            self.log("Já existe um processo em execução.")
            return

        # 1. Validação inicial na thread principal
        input_dir = self.input_dir_var.get()
        if not input_dir or not os.path.isdir(input_dir):
            messagebox.showerror("Erro de Configuração", "Por favor, selecione um diretório de entrada válido.")
            return
            
        self.log_widget.delete('1.0', tk.END)
        self.log("="*60)
        self.log("INICIANDO ORGANIZADOR DE LIVROS EM THREAD SEPARADA...")
        self.log("="*60)

        # 2. Inicia o Thread
        self.is_processing = True
        self.set_controls_state(True)
        # Usa daemon=True para que o thread seja encerrado quando o programa principal fechar
        self.processing_thread = threading.Thread(target=self.processar_imagens_logic, daemon=True) 
        self.processing_thread.start()

    def stop_processing(self):
        """Define a flag para interromper o loop de processamento e tenta cancelar workers."""
        if self.is_processing:
            # 1. Define a flag de interrupção (que será checada no thread worker)
            self.is_processing = False 
            self.log("\n!!! INTERRUPÇÃO SOLICITADA PELO USUÁRIO. Tentando encerrar processos workers... !!!")
            
            # 2. Tenta desligar o ProcessPoolExecutor imediatamente se ele estiver ativo
            if self.executor:
                # wait=False e cancel_futures=True cancela futures pendentes e tenta encerrar processos workers.
                self.executor.shutdown(wait=False, cancel_futures=True) 
                self.log("Tentativa de cancelamento de processos paralelos enviada.")
            
            # O thread de processamento terminará assim que o ProcessPoolExecutor fechar.

    def _cleanup_processing(self, is_interrupted=False):
        """Finaliza e limpa o estado de processamento (chamado pelo thread worker no fim)."""
        
        self.log("\n" + "="*60)
        if is_interrupted:
            self.log("PROCESSAMENTO ENCERRADO POR SOLICITAÇÃO DO USUÁRIO!")
        elif self.is_processing:
            self.log("PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        else:
             self.log("PROCESSAMENTO ENCERRADO DEVIDO A UM ERRO INTERNO!")
            
        self.log("Verifique a pasta de saída.")
        self.log("="*60)
        
        self.is_processing = False
        self.executor = None
        # Atualiza o estado dos controles na thread principal de forma segura
        self.master.after(0, lambda: self.set_controls_state(False))

    def processar_imagens_logic(self):
        """
        Lógica principal de processamento (incluindo paralelismo), executada em um thread separado.
        """
        input_dir = self.input_dir_var.get()
        output_dir = self.output_dir_var.get()
        
        try:
            max_folhas = self.max_folhas_var.get()
            num_processes = self.num_processes_var.get()
        except tk.TclError:
            self.log("ERRO: Máximo de Folhas e Processos Paralelos devem ser números inteiros.")
            self._cleanup_processing()
            return
            
        self.ultima_folha_processada = 0

        # Validação do diretório de saída
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                self.log(f"Diretório de saída criado: {output_dir}")
            except Exception as e:
                self.log(f"ERRO: Não foi possível criar o diretório de saída: {e}")
                self._cleanup_processing()
                return
        
        # --- 2. LISTAGEM E FILTRAGEM ---
        arquivos_encontrados = [
            f for f in os.listdir(input_dir)
            if os.path.isfile(os.path.join(input_dir, f)) and f.lower().endswith(('.jpg', '.jpeg'))
        ]
        arquivos_ordenados = sorted(arquivos_encontrados)
        input_paths = [os.path.join(input_dir, f) for f in arquivos_ordenados]
        
        if not arquivos_ordenados:
            self.log("Nenhuma imagem JPG/JPEG encontrada no diretório de entrada.")
            self._cleanup_processing()
            return

        self.log(f"Encontradas {len(arquivos_ordenados)} imagens. OCR paralelo usando {num_processes} processos.")
        self.log("-" * 60)
        
        ocr_results: List[Tuple[str, Optional[int], str, bytes]] = []
        
        # --- 3. ETAPA DE OCR PARALELO ---
        self.log("Executando OCR em paralelo... Aguarde.")
        
        try:
            # Armazena o executor em uma variável de instância para que stop_processing possa acessá-lo
            with concurrent.futures.ProcessPoolExecutor(max_workers=num_processes) as self.executor:
                
                future_to_file = {
                    self.executor.submit(_run_ocr_worker, path, max_folhas): os.path.basename(path) 
                    for path in input_paths
                }

                all_results_unordered: List[Tuple[str, Optional[int], str, bytes]] = []
                for future in concurrent.futures.as_completed(future_to_file):
                    if not self.is_processing:
                        # Se a INTERRUPÇÃO foi solicitada, cancela o resto
                        self.log("INTERRUPÇÃO DETECTADA no thread worker. Fechando o executor...")
                        # Isto garante o cancelamento de futures pendentes
                        self.executor.shutdown(wait=False, cancel_futures=True) 
                        break
                        
                    try:
                        result = future.result()
                        all_results_unordered.append(result)
                        self.log(f"  > Worker Concluído: {future_to_file[future]} (Resultado OCR bruto recebido).")
                    except concurrent.futures.CancelledError:
                        self.log(f"  > Worker Cancelado: {future_to_file[future]} foi cancelado.")
                    except Exception as exc:
                        self.log(f"  > Worker ERROR: {future_to_file[future]} gerou uma exceção: {exc}")
                        
                # Ordena os resultados com base na lista de arquivos original
                filename_to_result = {res[0]: res for res in all_results_unordered}
                for filename in arquivos_ordenados:
                    if filename in filename_to_result:
                        ocr_results.append(filename_to_result[filename])
                    elif filename not in filename_to_result and self.is_processing:
                         # Arquivo não foi processado (pode ter falhado ou não ter sido submetido/cancelado)
                         # Se o processo não foi cancelado, assume um erro.
                         ocr_results.append((filename, None, "ERRO: Worker falhou ou foi cancelado.", b''))
            
            # Limpa o executor após o bloco `with`
            self.executor = None 

        except Exception as e:
            self.log(f"ERRO CRÍTICO NA EXECUÇÃO PARALELA: {e}")
            self._cleanup_processing()
            return
            
        self.log("\n" + "="*60)
        self.log("ETAPA DE OCR PARALELO CONCLUÍDA. Iniciando Renomeação Sequencial...")
        self.log("="*60)
        
        # Se houve interrupção no meio do OCR, não faz a renomeação sequencial
        if not self.is_processing:
            self.log("Processamento interrompido. Nenhuma renomeação ou salvamento sequencial iniciado.")
            self._cleanup_processing(is_interrupted=True)
            return

        # --- 4. ETAPA SEQUENCIAL: Lógica de Renomeação, Verso e Salvamento ---
        
        for filename, folha_num_ocr, full_ocr_text, img_bytes in ocr_results:
            
            if not self.is_processing:
                break # Interrompe a lógica sequencial
                
            self.log(f"\n--- Processando Sequencialmente: {filename} ---")
            
            # Reconstroi a imagem a partir dos bytes (já rotacionada e pronta)
            try:
                # Usa PNG aqui, que foi o formato usado para salvar os bytes no worker
                img = Image.open(io.BytesIO(img_bytes)) 
            except Exception:
                self.log(f"  > ERRO: Falha ao reconstruir imagem para {filename}. Ignorando.")
                continue

            base_filename = os.path.splitext(filename)[0]
            folha_num = folha_num_ocr
            sufixo = ""

            if full_ocr_text.startswith("ERRO INTERNO NO WORKER:"):
                 self.log(f"  > ERRO NO WORKER: {full_ocr_text}. Requer correção manual.")
                 folha_num = None 

            if base_filename in self.correcoes_manuais:
                folha_num = self.correcoes_manuais[base_filename]
                self.log(f"  > CORREÇÃO MANUAL APLICADA: Forçado para Folha nº {folha_num}.")
            
            is_termo = (folha_num == 0 or folha_num == max_folhas + 1)
            
            if folha_num is None:
                texto_limpo = re.sub(r'\s+', '', full_ocr_text)
                
                if len(texto_limpo) < LIMIAR_CARACTERES_VERSO and self.ultima_folha_processada > 0 and not is_termo:
                    folha_num = self.ultima_folha_processada
                    sufixo = "-verso"
                    self.log(f"  > AVISO: OCR falhou. Aplicando regra de VERSO: Folha nº {folha_num}{sufixo}.")
                else:
                    self.log("!!! ERRO DE OCR DETECTADO - ABRINDO CORREÇÃO MANUAL !!!")
                    
                    manual_num = self.ask_manual_correction(filename)
                    
                    if manual_num is not None:
                        folha_num = manual_num
                        self.correcoes_manuais[base_filename] = folha_num
                        self.log(f"  > MANUAL: Folha nº {folha_num} definida pelo usuário.")
                    else:
                        folha_num = None 
                        self.log(f"  > IGNORADO: O arquivo será salvo com nome de erro.")

            if folha_num is not None and folha_num > 0 and folha_num <= max_folhas:
                self.ultima_folha_processada = folha_num
                
            # --- 5. Definição do Nome do Arquivo ---
            if folha_num is not None:
                
                if folha_num == 0:
                    novo_filename = "TERMO DE ABERTURA.pdf"
                elif folha_num == max_folhas + 1:
                    novo_filename = f"TERMO DE ENCERRAMENTO.pdf" 
                else:
                    novo_filename = f"FL. {folha_num:03d}{sufixo}.pdf"

                self.log(f"  > NOME DEFINIDO: '{novo_filename}'.")
            
            else:
                novo_filename = f"ERRO_OCR_{base_filename}.pdf"
                self.log(f"  > SALVANDO ERRO: Nome de erro aplicado: '{novo_filename}'.")
            
            output_path = os.path.join(output_dir, novo_filename)

            # --- 6. Conversão e Salvamento para PDF ---
            try:
                img.save(output_path, "PDF", resolution=100.0)
                self.log(f"  > SUCESSO: Salva em '{output_path}'.")
            except Exception as e:
                self.log(f"  > ERRO FATAL ao salvar PDF para '{filename}': {e}")
        
        # --- FIM DO PROCESSAMENTO ---
        # Chama a limpeza, indicando se houve interrupção ou não
        self._cleanup_processing(is_interrupted=not self.is_processing)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = OCR_App(root)
        root.mainloop()
    except tk.TclError as e:
        print("\n" + "="*70)
        print("ERRO CRÍTICO DO TKINTER: Falha ao inicializar a interface gráfica.")
        print(f"Detalhe do erro: {e}")
        print("Possível solução: Tente rodar o script em um ambiente com ambiente gráfico (X server).")
        print("="*70)
        sys.exit(1)
