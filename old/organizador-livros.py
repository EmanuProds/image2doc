# -*- coding: utf-8 -*-
#
# ORGANIZADOR DE LIVROS COM INTERFACE GTK4/LIBADWAITA
# Reescrita do organizador-livros.py para usar gi.repository (GTK/Libadwaita)
#
import os
import re
import pytesseract
import sys
import io
import queue 
import threading 
import concurrent.futures 
from typing import Optional, Dict, Tuple, Any, List, Set

# --- Dependências GTK/Libadwaita ---
try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw, GLib
except ImportError:
    print("ERRO: As bibliotecas GTK4/Libadwaita (gi.repository) não estão instaladas. Tente 'pip install pygobject'.")
    sys.exit(1)

# --- Dependências de Backend ---
from PIL import Image
# Não podemos usar filedialog/messagebox do tkinter, usaremos Gtk.FileDialog/Gtk.MessageDialog

# --- CONFIGURAÇÃO E VARIÁVEIS GLOBAIS (Mantidas) ---
DEFAULT_MAX_FOLHAS = 300
DEFAULT_PROCESSES = 4 
# REGIÃO DE INTERESSE (ROI) para OCR: (X_min, Y_min, X_max, X_max) em escala de 0 a 1000
OCR_ROI = (450, 50, 950, 250)
LIMIAR_CARACTERES_VERSO = 250
PSM_CONFIG = r'--oem 3 -l por --psm 6'
CORRECOES_MANUAIS: Dict[str, int] = {}
# pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'


# --- FUNÇÕES WORKER PARALELA (Mantidas) ---

def _run_ocr_worker(input_path: str, max_folhas: int) -> Tuple[str, Optional[int], str, bytes]:
    """
    Função de worker que executa o OCR, a rotação e a extração de dados
    para UMA ÚNICA imagem. Roda em um processo separado.
    """
    try:
        filename = os.path.basename(input_path)
        img = Image.open(input_path)

        # 1. ROTAÇÃO INTELIGENTE
        # Tenta rotacionar -90, se o OCR de ROI for melhor, mantém. Senão, tenta rotacionar +90.
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
        img.save(img_byte_arr, format='PNG') 
        img_bytes = img_byte_arr.getvalue()
        
        # 4. Retorna todos os dados para o thread principal
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

def extract_folha_num(text: str) -> Optional[int]:
    """Extrai o número da folha de um texto usando regex."""
    match = re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', text.upper())
    if match:
        try:
            return int(match.group(2))
        except ValueError:
            return None
    return None

def extrair_numero_folha_ocr_worker(image: Image.Image, max_folhas: int) -> Tuple[Optional[int], str]:
    """Extrai Termos Especiais e Números de Folha (Usado pelo worker)."""
    full_text = ""
    try:
        # Tenta OCR com psm 3 (página inteira) para Termos Especiais
        full_text = pytesseract.image_to_string(image, config=r'--oem 3 -l por --psm 3')
        upper_text = full_text.upper()

        if "TERMO DE ABERTURA" in upper_text or "TERMO DE INSTALAÇÃO" in upper_text:
            # Retorna 0 para Termo de Abertura
            return 0, full_text
        if "TERMO DE ENCERRAMENTO" in upper_text:
            # Retorna (max_folhas + 1) para Termo de Encerramento
            return max_folhas + 1, full_text
            
    except Exception:
        pass

    try:
        # Tenta OCR com psm 6 (ROI) para número da folha
        img_width, img_height = image.size
        x_min = int(img_width * OCR_ROI[0] / 1000)
        y_min = int(img_height * OCR_ROI[1] / 1000)
        y_max = int(img_height * OCR_ROI[3] / 1000)
        x_max = int(img_width * OCR_ROI[2] / 1000)
        crop_box = (x_min, y_min, x_max, y_max)
        
        cropped_image = image.crop(crop_box)
        text_roi = pytesseract.image_to_string(cropped_image, config=PSM_CONFIG)
        
        folha_numero = extract_folha_num(text_roi)
        
        return folha_numero, full_text

    except Exception:
        return None, full_text


def load_processed_sheets(output_dir: str, max_folhas: int) -> Set[int]:
    """
    Carrega os números de folha (FL. XXX) dos PDFs já processados na pasta de saída.
    """
    processed_sheets = set()
    if not os.path.isdir(output_dir):
        return processed_sheets
        
    for filename in os.listdir(output_dir):
        if filename.lower().endswith('.pdf'):
            # Padrão para FL. XXX
            match_fl = re.search(r'FL\. (\d{3})(?:-verso)?\.pdf', filename.upper())
            if match_fl:
                try:
                    folha_num = int(match_fl.group(1))
                    # Adiciona a folha (ex: 1, 2, 3...)
                    processed_sheets.add(folha_num) 
                except ValueError:
                    pass
            
            # Padrão para Termo de Abertura/Encerramento
            if 'TERMO DE ABERTURA' in filename.upper():
                processed_sheets.add(0) # 0 representa Abertura
            if 'TERMO DE ENCERRAMENTO' in filename.upper():
                processed_sheets.add(max_folhas + 1) # max_folhas + 1 representa Encerramento
                
    return processed_sheets

# --- DIÁLOGO MODAL GTK PARA CORREÇÃO MANUAL ---
class CorrectionDialog(Adw.MessageDialog):
    def __init__(self, parent: Gtk.Window, filename: str, last_folha: int, max_folhas: int):
        super().__init__(
            modal=True,
            heading="!!! INTERVENÇÃO NECESSÁRIA !!!",
            body=f"Arquivo: <b>{filename}</b>\nÚltima Folha Processada: FL. {last_folha:03d}\n\nDigite o número CORRETO da folha (0=Abertura, {max_folhas + 1}=Encerramento):",
            use_markup=True,
            width_request=400
        )
        self.set_transient_for(parent)
        
        # O Gtk.MessageDialog só permite botões de confirmação/cancelamento simples.
        # Para input, precisamos adicionar um widget de conteúdo personalizado.
        
        self.result = None
        self.max_folhas = max_folhas
        
        # Campo de entrada
        self.entry = Gtk.Entry.new()
        # Sugere a próxima folha normal
        suggested_num = str(last_folha + 1 if last_folha >= 0 else 1)
        self.entry.set_text(suggested_num)
        self.entry.set_width_chars(10)
        self.entry.set_halign(Gtk.Align.CENTER)
        
        # Botões de ação
        self.add_response("confirmar", "Confirmar")
        self.add_response("ignorar", "Ignorar (Salvar como ERRO_OCR)")
        self.set_default_response("confirmar")
        
        # Conecta o sinal de resposta e o evento de Enter
        self.connect("response", self._on_response)
        self.entry.connect("activate", lambda *a: self._on_submit_via_enter())

        # Adicionar o campo de entrada ao conteúdo do diálogo
        content_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
        content_box.set_margin_top(12)
        content_box.append(self.entry)
        
        # Adiciona o content_box ao corpo do diálogo
        self.set_content(content_box)
        
        # Foco e Seleção
        self.entry.grab_focus()
        self.entry.select_region(0, -1)


    def _on_submit_via_enter(self):
        """Simula um clique no botão de confirmação ao pressionar Enter."""
        # Se Enter for pressionado, aciona a resposta 'confirmar'
        self.response("confirmar")

    def _on_response(self, dialog, response_id: str):
        if response_id == "confirmar":
            try:
                num = int(self.entry.get_text())
                if 0 <= num <= self.max_folhas + 1:
                    self.result = num
                else:
                    # Mensagem de erro (não bloqueia o main loop)
                    error_msg = f"O número da folha deve ser entre 0 (Abertura) e {self.max_folhas + 1} (Encerramento)."
                    self._show_error(error_msg)
                    return # Não fecha o diálogo
            except ValueError:
                self.result = None
                self._show_error("Por favor, insira um número inteiro válido.")
                return # Não fecha o diálogo
        
        elif response_id == "ignorar":
            self.result = None
            
        self.close()

    def _show_error(self, message: str):
        """Exibe uma mensagem de erro de forma não-bloqueante."""
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            modal=True,
            heading="Erro de Validação",
            body=message,
        )
        dialog.add_response("ok", "OK")
        dialog.set_response_enabled("ok", True)
        dialog.connect("response", lambda d, r: d.close())
        dialog.present()


# --- CLASSE DA APLicação GTK4/LIBADWAITA ---
class OCR_AppGTK(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.set_default_size(800, 600)
        
        # 1. CRIAR HEADERBAR EXPLÍCITO (Força a exibição dos botões de controle de janela)
        header_bar = Adw.HeaderBar.new()
        # Define o título no Widget de Título do HeaderBar
        # CORREÇÃO: Mudar 'None' para uma string vazia ("") para evitar TypeError
        header_bar.set_title_widget(Adw.WindowTitle.new("Organizador de Livros com OCR", ""))
        
        # 2. DEFINIR O HEADERBAR
        self.set_titlebar(header_bar) 
        
        # --- VARIÁVEIS DE CONTROLE DO GTK ---
        self.input_dir = ""
        self.output_dir = ""
        self.max_folhas = DEFAULT_MAX_FOLHAS
        self.num_processes = DEFAULT_PROCESSES
        
        # --- VARIÁVEIS DE CONTROLE DE THREADS E ESTADO (Fila para thread-safe) ---
        self.log_queue = queue.Queue() 
        self.modal_request_queue = queue.Queue() # (filename)
        self.modal_result_queue = queue.Queue()  # (result: Optional[int])
        self.processing_thread = None 
        self.executor = None 
        self.is_processing = False
        self.ultima_folha_processada = 0
        self.correcoes_manuais = CORRECOES_MANUAIS.copy()

        self.create_widgets()
        
        # Chamadas periódicas seguras para o thread principal
        GLib.timeout_add(100, self.check_log_queue)
        GLib.timeout_add(100, self.check_modal_requests)
        
        # Conecta o sinal 'close-request' para garantir o encerramento seguro dos workers
        self.connect("close-request", self._on_close_request)
        
    def _on_close_request(self, *args) -> bool:
        """
        Garante que o processamento paralelo seja interrompido ao fechar a janela (clicar no 'X').
        Retorna False para permitir que a janela feche e o Adw.Application encerre a app.
        """
        if self.is_processing:
            self.log("Tentativa de fechar: Solicitando interrupção dos workers...")
            # Chama a função de parada, que desliga o executor
            self.stop_processing()
            
            # Não forçamos o encerramento aqui, apenas tentamos parar o backend de forma limpa.
            # O fechamento da janela continua.
            
        return False # Permite que a janela feche

    def log(self, message: str):
        """Método que adiciona mensagens à fila de log (thread-safe)."""
        self.log_queue.put(message)

    def check_log_queue(self, *args) -> bool: # Adiciona *args para evitar warnings se o GLib passar argumentos
        """Verifica a fila de log e atualiza o widget na thread principal (GUI)."""
        while not self.log_queue.empty():
            message = self.log_queue.get()
            buffer = self.log_widget.get_buffer()
            # Adiciona o texto no final
            end_iter = buffer.get_end_iter()
            buffer.insert(end_iter, message + "\n")
            # Scroll para o final
            end_iter = buffer.get_end_iter()
            self.log_widget.scroll_to_iter(end_iter, 0.0, False, 0.0, 0.0)
        return True # Retorna True para continuar a chamada periódica

    def create_widgets(self):
        # Layout principal: Gtk.Box horizontal para Sidebar e Conteúdo
        main_content_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        self.set_content(main_content_box) 

        # --- Gtk.Stack (Onde o conteúdo de cada página fica) ---
        self.view_stack = Gtk.Stack.new()
        self.view_stack.set_vexpand(True)
        self.view_stack.set_hexpand(True)

        # --- Gtk.StackSidebar (O menu lateral no estilo da imagem) ---
        sidebar = Gtk.StackSidebar.new()
        sidebar.set_stack(self.view_stack)
        # CORREÇÃO: Usar set_size_request(-1 para altura) em vez de set_width_request()
        sidebar.set_size_request(200, -1) 
        sidebar.add_css_class("sidebar") # Aplica o estilo de barra lateral (dark mode)
        
        main_content_box.append(sidebar)
        main_content_box.append(self.view_stack)

        # --- PÁGINAS DO APP ---
        
        # 1. PÁGINA DE CONFIGURAÇÕES E INÍCIO
        config_page = self._create_config_page()
        # CORREÇÃO GTK4: Usar add_titled e set_icon_name separadamente
        self.view_stack.add_titled(
            config_page, "config_page", "Configurações"
        )
        page = self.view_stack.get_page(config_page)
        page.set_icon_name("settings-symbolic")

        # 2. PÁGINA DE LOG DE STATUS
        log_page = self._create_log_page()
        # CORREÇÃO GTK4: Usar add_titled e set_icon_name separadamente
        self.view_stack.add_titled(
            log_page, "log_page", "Log de Status"
        )
        page = self.view_stack.get_page(log_page)
        page.set_icon_name("document-symbolic")

    def _create_config_page(self) -> Gtk.Widget:
        """Cria e retorna o Gtk.ScrolledWindow contendo a página de configurações."""
        
        # Usamos Adw.Clamp para centralizar o conteúdo de forma responsiva
        clamp = Adw.Clamp.new()
        clamp.set_maximum_size(800) 
        
        scroll = Gtk.ScrolledWindow.new()
        scroll.set_child(clamp)
        scroll.set_margin_top(1) # Pequeno ajuste visual

        config_page_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 10)
        config_page_box.set_margin_start(30)
        config_page_box.set_margin_end(30)
        config_page_box.set_margin_top(20)
        config_page_box.set_margin_bottom(20)
        clamp.set_child(config_page_box)
        
        # -- 1. GRUPO DE CONFIGURAÇÕES DE DIRETÓRIO --
        dir_group = Adw.PreferencesGroup.new()
        dir_group.set_title("Diretórios")
        config_page_box.append(dir_group)
        
        # Pasta de Entrada
        self.input_entry = Gtk.Entry.new()
        self.input_entry.set_placeholder_text("Selecione a pasta com os arquivos JPG/JPEG")
        self.input_row = Adw.ActionRow.new()
        self.input_row.set_title("Pasta de Entrada (JPGs)")
        self.input_row.add_suffix(self.input_entry)
        
        input_btn = Gtk.Button.new_with_label("Procurar")
        input_btn.set_icon_name("folder-open-symbolic")
        input_btn.connect("clicked", self.select_input_dir)
        self.input_row.add_suffix(input_btn)
        dir_group.add(self.input_row)

        # Pasta de Saída
        self.output_entry = Gtk.Entry.new()
        self.output_entry.set_placeholder_text("Selecione onde salvar os PDFs")
        self.output_row = Adw.ActionRow.new()
        self.output_row.set_title("Pasta de Saída (PDFs)")
        self.output_row.add_suffix(self.output_entry)
        
        output_btn = Gtk.Button.new_with_label("Procurar")
        output_btn.set_icon_name("folder-download-symbolic")
        output_btn.connect("clicked", self.select_output_dir)
        self.output_row.add_suffix(output_btn)
        dir_group.add(self.output_row)

        # -- 2. GRUPO DE CONFIGURAÇÕES DE PROCESSAMENTO --
        config_group = Adw.PreferencesGroup.new()
        config_group.set_title("Configurações do OCR")
        config_page_box.append(config_group)

        # Máximo de Folhas
        self.max_folhas_spin = Gtk.SpinButton.new_with_range(1, 1000, 1)
        self.max_folhas_spin.set_value(DEFAULT_MAX_FOLHAS)
        self.max_folhas_spin.connect("value-changed", self._on_config_changed)
        max_folhas_row = Adw.ActionRow.new()
        max_folhas_row.set_title("Máximo de Folhas do Livro")
        max_folhas_row.add_suffix(self.max_folhas_spin)
        config_group.add(max_folhas_row)
        
        # Processos Paralelos
        self.num_processes_spin = Gtk.SpinButton.new_with_range(1, 16, 1)
        self.num_processes_spin.set_value(DEFAULT_PROCESSES)
        self.num_processes_spin.connect("value-changed", self._on_config_changed)
        num_processes_row = Adw.ActionRow.new()
        num_processes_row.set_title("Processos Paralelos (Workers)")
        num_processes_row.add_suffix(self.num_processes_spin)
        config_group.add(num_processes_row)
        
        # -- 3. BOTÕES DE AÇÃO --
        action_group = Adw.PreferencesGroup.new()
        config_page_box.append(action_group)
        
        # Box para os botões (para que fiquem alinhados)
        button_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 10)
        button_box.set_margin_top(10)
        action_group.add(button_box)
        
        self.start_button = Gtk.Button.new_with_label("INICIAR PROCESSAMENTO")
        self.start_button.add_css_class("suggested-action") 
        self.start_button.set_halign(Gtk.Align.CENTER)
        self.start_button.connect("clicked", self.start_processing_thread)
        button_box.append(self.start_button)
        
        self.stop_button = Gtk.Button.new_with_label("ENCERRAR")
        self.stop_button.add_css_class("destructive-action") 
        self.stop_button.set_sensitive(False)
        self.stop_button.set_halign(Gtk.Align.CENTER)
        self.stop_button.connect("clicked", self.stop_processing)
        button_box.append(self.stop_button)
        
        return scroll

    def _create_log_page(self) -> Gtk.Widget:
        """Cria e retorna o Gtk.ScrolledWindow contendo o Log de Status."""
        
        self.log_widget = Gtk.TextView.new()
        self.log_widget.set_editable(False)
        self.log_widget.set_wrap_mode(Gtk.WrapMode.WORD)
        self.log_widget.get_buffer().set_text("Pronto para iniciar. Selecione a pasta de entrada e clique em 'INICIAR PROCESSAMENTO'.\n")
        
        scrolled_window = Gtk.ScrolledWindow.new()
        scrolled_window.set_vexpand(True)
        scrolled_window.set_child(self.log_widget)
        
        return scrolled_window
        
    def _on_config_changed(self, spin_button):
        """Atualiza variáveis de configuração ao mudar o SpinButton."""
        try:
            self.max_folhas = int(self.max_folhas_spin.get_value())
            self.num_processes = int(self.num_processes_spin.get_value())
        except Exception:
            self.log("ERRO: Configurações devem ser números inteiros.")

    def select_input_dir(self, button):
        """Abre o diálogo de seleção de diretório de entrada (Gtk.FileDialog)."""
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_title("Selecione a Pasta de Entrada")
        self.log("Aguardando seleção da pasta de entrada...")
        self.set_sensitive(False) # Desativa a janela principal enquanto o diálogo está aberto
        self.set_modal(True)
        file_dialog.select_folder(self, None, self._input_dir_selected)

    def _input_dir_selected(self, file_dialog, result):
        """Callback após a seleção do diretório de entrada."""
        self.set_modal(False)
        self.set_sensitive(True) # Reativa a janela principal
        try:
            folder = file_dialog.select_folder_finish(result)
            if folder:
                self.input_dir = folder.get_path()
                self.input_entry.set_text(self.input_dir)
                
                # Sugere o diretório de saída
                if not self.output_entry.get_text():
                    output_default = os.path.join(self.input_dir, os.path.basename(self.input_dir) + "_editados")
                    self.output_dir = output_default
                    self.output_entry.set_text(self.output_dir)
                    
                self.log(f"Pasta de entrada selecionada: {self.input_dir}")
        except GLib.Error as e:
            # Captura a exceção de cancelamento ou outro erro de seleção
            if 'cancelled' not in str(e): 
                 self.log(f"Erro ao selecionar pasta de entrada: {e.message}")
            else:
                 self.log("Seleção de pasta de entrada cancelada.")


    def select_output_dir(self, button):
        """Abre o diálogo de seleção de diretório de saída (Gtk.FileDialog)."""
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_title("Selecione a Pasta de Saída")
        self.log("Aguardando seleção da pasta de saída...")
        self.set_sensitive(False) # Desativa a janela principal enquanto o diálogo está aberto
        self.set_modal(True)
        file_dialog.select_folder(self, None, self._output_dir_selected)

    def _output_dir_selected(self, file_dialog, result):
        """Callback após a seleção do diretório de saída."""
        self.set_modal(False)
        self.set_sensitive(True) # Reativa a janela principal
        try:
            folder = file_dialog.select_folder_finish(result)
            if folder:
                self.output_dir = folder.get_path()
                self.output_entry.set_text(self.output_dir)
                self.log(f"Pasta de saída selecionada: {self.output_dir}")
        except GLib.Error as e:
            if 'cancelled' not in str(e):
                 self.log(f"Erro ao selecionar pasta de saída: {e.message}")
            else:
                 self.log("Seleção de pasta de saída cancelada.")


    def set_controls_state(self, is_running: bool):
        """Alterna o estado dos botões e campos de entrada de forma thread-safe."""
        self.start_button.set_sensitive(not is_running)
        self.stop_button.set_sensitive(is_running)
        self.input_entry.set_sensitive(not is_running)
        self.output_entry.set_sensitive(not is_running)
        self.max_folhas_spin.set_sensitive(not is_running)
        self.num_processes_spin.set_sensitive(not is_running)
        
    def check_modal_requests(self, *args) -> bool: # Adiciona *args para evitar warnings se o GLib passar argumentos
        """Verifica a fila de requisições de modal (chamada periodicamente no thread principal)."""
        if not self.modal_request_queue.empty():
            filename = self.modal_request_queue.get()
            self._show_manual_correction_dialog(filename)
        return True

    def _show_manual_correction_dialog(self, filename: str):
        """Cria e exibe o diálogo de correção manual (chamado apenas no thread principal)."""
        
        # Obtém os valores de configuração atuais
        max_folhas = int(self.max_folhas_spin.get_value())
        
        dialog = CorrectionDialog(
            parent=self, 
            filename=filename, 
            last_folha=self.ultima_folha_processada, 
            max_folhas=max_folhas
        )
        
        # Quando o diálogo fecha, a callback _on_dialog_closed é chamada
        dialog.connect("response", self._on_dialog_closed)
        dialog.present()

    def _on_dialog_closed(self, dialog: CorrectionDialog, response_id: str):
        """Callback quando o Gtk.Dialog fecha (chamado no thread principal)."""
        # Coloca o resultado na fila para desbloquear o thread de processamento
        self.modal_result_queue.put(dialog.result)
        dialog.destroy()
        
    def ask_manual_correction(self, filename: str) -> Optional[int]:
        """Envia a requisição de modal para o thread principal e bloqueia o thread atual até obter o resultado."""
        # 1. Envia a requisição para o thread principal
        self.modal_request_queue.put(filename)
        
        # 2. BLOQUEIA O THREAD DE PROCESSAMENTO esperando pelo resultado
        # O método .get() do queue é bloqueante até que um item seja colocado
        result = self.modal_result_queue.get() 
        return result

    def start_processing_thread(self, button):
        """Inicia a lógica principal em um novo thread para não bloquear a GUI."""
        # Obtém valores atuais dos widgets
        self.input_dir = self.input_entry.get_text()
        self.output_dir = self.output_entry.get_text()
        
        if self.is_processing:
            self.log("Já existe um processo em execução.")
            return

        # 1. Validação inicial
        if not self.input_dir or not os.path.isdir(self.input_dir):
            self.log("ERRO: Por favor, selecione um diretório de entrada válido.")
            return
            
        self.log_widget.get_buffer().set_text("")
        # Muda para a página de log ao iniciar
        self.view_stack.set_visible_child_name("log_page")
        
        self.log("="*60)
        self.log("INICIANDO ORGANIZADOR DE LIVROS (CACHE ATIVO)...")
        self.log("="*60)

        # 2. Inicia o Thread e atualiza a GUI
        self.is_processing = True
        GLib.idle_add(self.set_controls_state, True)
        self.processing_thread = threading.Thread(target=self.processar_imagens_logic, daemon=True) 
        self.processing_thread.start()

    def stop_processing(self, button=None):
        """Define a flag para interromper o loop de processamento e tenta cancelar workers."""
        if self.is_processing:
            self.is_processing = False 
            self.log("\n!!! INTERRUPÇÃO SOLICITADA PELO USUÁRIO. Tentando encerrar processos workers... !!!")
            
            if self.executor:
                # Tenta cancelar futures e desliga o executor
                self.executor.shutdown(wait=False, cancel_futures=True) 
                self.log("Tentativa de cancelamento de processos paralelos enviada.")

    def _cleanup_processing(self, is_interrupted=False):
        """Finaliza e limpa o estado de processamento (chamado pelo thread worker no fim) de forma thread-safe."""
        
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
        GLib.idle_add(self.set_controls_state, False) # Atualiza a GUI no thread principal

    def processar_imagens_logic(self):
        """
        Lógica principal (Mantida no thread de processamento): 
        Pré-carrega cache, submete OCR em paralelo e processa sequencialmente.
        """
        # Obtém os valores de configuração
        input_dir = self.input_dir
        output_dir = self.output_dir
        max_folhas = self.max_folhas
        num_processes = self.num_processes
            
        self.ultima_folha_processada = 0

        # Validação/Criação do diretório de saída
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                self.log(f"Diretório de saída criado: {output_dir}")
            except Exception as e:
                self.log(f"ERRO: Não foi possível criar o diretório de saída: {e}")
                self._cleanup_processing()
                return
        
        # --- 1.1 PRÉ-VERIFICAÇÃO (CACHE) ---
        processed_sheets = load_processed_sheets(output_dir, max_folhas)
        self.log(f"Cache de PDFs existente carregado: {len(processed_sheets)} folhas já convertidas.")
        
        # --- 2. LISTAGEM E ORDENAÇÃO ---
        arquivos_encontrados = [
            f for f in os.listdir(input_dir)
            if os.path.isfile(os.path.join(input_dir, f)) and f.lower().endswith(('.jpg', '.jpeg'))
        ]
        arquivos_ordenados = sorted(arquivos_encontrados)
        
        if not arquivos_ordenados:
            self.log("Nenhuma imagem JPG/JPEG encontrada no diretório de entrada.")
            self._cleanup_processing()
            return

        self.log(f"Encontradas {len(arquivos_ordenados)} imagens. OCR paralelo usando {num_processes} processos.")
        self.log("-" * 60)
        
        file_to_future = {} 
        
        # --- 2. ETAPA DE OCR PARALELO (SUBMISSÃO) ---
        try:
            # Armazena o executor para cancelamento
            with concurrent.futures.ProcessPoolExecutor(max_workers=num_processes) as self.executor:
                
                # Submete todas as tarefas
                for filename in arquivos_ordenados:
                    input_path = os.path.join(input_dir, filename)
                    future = self.executor.submit(_run_ocr_worker, input_path, max_folhas)
                    file_to_future[filename] = future
                
                self.log(f"{len(file_to_future)} tarefas submetidas. Iniciando processamento sequencial e condicional...")
                self.log("\n" + "="*60)
                
                # --- 2.1 ETAPA SEQUENCIAL: Resgate OCR, Cache Check e Processamento ---
                for filename in arquivos_ordenados:
                    
                    if not self.is_processing:
                        break 
                        
                    future = file_to_future[filename]
                    
                    try:
                        # BLOQUEIA ATÉ QUE O RESULTADO OCR DESTA IMAGEM ESTEJA PRONTO
                        filename_returned, folha_num_ocr, full_ocr_text, img_bytes = future.result() 
                        
                        self.log(f"--- OCR CONCLUÍDO para: {filename} ---")
                        
                        base_filename = os.path.splitext(filename)[0]
                        folha_num = folha_num_ocr
                        sufixo = ""

                        # 1. Verifica Erro de Worker
                        if full_ocr_text.startswith("ERRO INTERNO NO WORKER:"):
                            self.log(f"  > ERRO NO WORKER: {full_ocr_text}. Requer correção manual.")
                            folha_num = None 

                        # 2. Aplica Correção Manual Prévia
                        if base_filename in self.correcoes_manuais:
                            folha_num = self.correcoes_manuais[base_filename]
                            self.log(f"  > CORREÇÃO MANUAL ANTERIOR APLICADA: Folha nº {folha_num}.")
                        
                        # 3. VERIFICAÇÃO DE CACHE (Pulamos se já existe)
                        if folha_num is not None and folha_num in processed_sheets:
                            # Se for uma folha normal, atualiza a última folha processada
                            if folha_num > 0 and folha_num <= max_folhas:
                                self.ultima_folha_processada = folha_num
                            
                            self.log(f"  > *** ARQUIVO PULADO (CACHE) ***: Folha {folha_num:03d} já existe como PDF. Avançando.")
                            continue # Pula para a próxima iteração do loop

                        # --- Processamento (Se não foi Pulado pelo Cache) ---
                        
                        # 4. Abertura da Imagem (Rotacionada pelo Worker)
                        try:
                            img = Image.open(io.BytesIO(img_bytes)) 
                        except Exception:
                            self.log(f"  > ERRO: Falha ao reconstruir imagem para {filename}. Ignorando.")
                            continue

                        # 5. Tratamento de Erro e Lógica de Verso/Correção Manual
                        is_termo = (folha_num == 0 or folha_num == max_folhas + 1)
                        
                        if folha_num is None:
                            texto_limpo = re.sub(r'\s+', '', full_ocr_text)
                            
                            if len(texto_limpo) < LIMIAR_CARACTERES_VERSO and self.ultima_folha_processada > 0 and not is_termo:
                                folha_num = self.ultima_folha_processada
                                sufixo = "-verso"
                                self.log(f"  > AVISO: OCR falhou. Aplicando regra de VERSO: Folha nº {folha_num}{sufixo}.")
                            else:
                                self.log("!!! ERRO DE OCR DETECTADO - ABRINDO CORREÇÃO MANUAL !!!")
                                # Chamada BLOQUEANTE (via fila) para obter o input da GUI
                                manual_num = self.ask_manual_correction(filename)
                                
                                if manual_num is not None:
                                    folha_num = manual_num
                                    self.correcoes_manuais[base_filename] = folha_num
                                    self.log(f"  > MANUAL: Folha nº {folha_num} definida pelo usuário.")
                                else:
                                    folha_num = None 
                                    self.log(f"  > IGNORADO: O arquivo será salvo com nome de erro.")

                        if folha_num is not None and folha_num > 0 and folha_num <= max_folhas:
                            # Atualiza a última folha processada para uso na próxima iteração ou Verso
                            self.ultima_folha_processada = folha_num
                            
                        # 6. Definição do Nome do Arquivo
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

                        # 7. Conversão e Salvamento para PDF (IMEDIATO)
                        try:
                            img.save(output_path, "PDF", resolution=100.0)
                            # Adiciona ao cache interno para evitar que seja processado novamente se a correção for feita
                            if folha_num is not None:
                                processed_sheets.add(folha_num) 
                            self.log(f"  > SUCESSO: Salva em '{output_path}'.")
                        except Exception as e:
                            self.log(f"  > ERRO FATAL ao salvar PDF para '{filename}': {e}")
                            
                    except concurrent.futures.CancelledError:
                        self.log(f"\n--- Processamento de {filename} cancelado. ---")
                        break
                    except Exception as exc:
                        self.log(f"\n--- ERRO CRÍTICO ao obter resultado para {filename}: {exc} ---")
                        self.is_processing = False
                        break
                        
                # Garante que o executor será desligado
                if not self.is_processing:
                    self.executor.shutdown(wait=False, cancel_futures=True)
            
            self.executor = None 

        except Exception as e:
            self.log(f"ERRO CRÍTICO NA EXECUÇÃO PARALELA: {e}")
            self._cleanup_processing()
            return
            
        self._cleanup_processing(is_interrupted=not self.is_processing)


class OCR_Application(Adw.Application):
    """Classe principal da aplicação GTK4/Libadwaita."""
    def __init__(self):
        # AQUI NÃO PRECISAMOS DE FLAGS, mas se precisarmos de FLAGS_NONE, é 0.
        super().__init__(application_id="com.jtp.organizadorlivros") 
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        self.win = OCR_AppGTK(application=app)
        self.win.present()

if __name__ == "__main__":
    # 1. Verifica a disponibilidade do Tesseract
    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        print("\n" + "="*70)
        print("ERRO CRÍTICO: Tesseract não encontrado. Certifique-se de que está instalado e configurado.")
        print("="*70)
        sys.exit(1)
    
    # 2. Inicia o loop principal do GTK
    app = OCR_Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)
