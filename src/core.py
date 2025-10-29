# Contém a lógica sequencial de processamento, cache e coordenação do ProcessPoolExecutor.
import os
import re
import io
import concurrent.futures 
from typing import Set, List, Dict, Callable, Optional

from PIL import Image

# Importa as configurações e as funções worker
from . import config
from .ocr import _run_ocr_worker


# BLOCO DE FUNÇÕES DE MANIPULAÇÃO DE ARQUIVOS
def load_processed_sheets(output_dir: str, max_folhas: int) -> Set[int]:
    """
    Carrega os números de folha (FL. XXX) dos PDFs já processados na pasta de saída (Cache).
    
    Args:
        output_dir (str): Caminho para o diretório de saída.
        max_folhas (int): O número máximo de folhas do livro.
        
    Returns:
        Set[int]: Um conjunto de números de folha que já foram processados (0=Abertura, max_folhas+1=Encerramento).
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
                    processed_sheets.add(folha_num) 
                except ValueError:
                    pass
            
            # Padrão para Termo de Abertura/Encerramento
            if 'TERMO DE ABERTURA' in filename.upper():
                processed_sheets.add(0)
            if 'TERMO DE ENCERRAMENTO' in filename.upper():
                processed_sheets.add(max_folhas + 1)
                
    return processed_sheets


# Bloco principal de processamento
def run_processing_logic(
    input_dir: str, 
    output_dir: str, 
    max_folhas: int, 
    num_processes: int,
    ultima_folha_processada: int,
    correcoes_manuais: Dict[str, int],
    log_callback: Callable[[str], None],
    ask_manual_correction_callback: Callable[[str], Optional[int]],
    set_is_processing_state: Callable[[bool], None],
    get_is_processing_state: Callable[[], bool]
):
    """
    Lógica principal de processamento que orquestra o OCR paralelo e a conversão sequencial para PDF.
    
    Args:
        input_dir (str): Pasta de entrada com JPGs.
        output_dir (str): Pasta de saída para PDFs.
        max_folhas (int): Máximo de folhas.
        num_processes (int): Número de workers.
        ultima_folha_processada (int): Última folha processada antes desta execução.
        correcoes_manuais (Dict[str, int]): Dicionário de correções manuais permanentes.
        log_callback (Callable[[str], None]): Função para logar mensagens na GUI (thread-safe).
        ask_manual_correction_callback (Callable[[str], Optional[int]]): Função para solicitar intervenção manual da GUI (bloqueante).
        set_is_processing_state (Callable[[bool], None]): Função para definir o estado de processamento.
        get_is_processing_state (Callable[[], bool]): Função para obter o estado de processamento (para verificar interrupção).
    """
    
    # Função auxiliar de limpeza/finalização
    def _cleanup_processing(is_interrupted=False):
        """Finaliza e limpa o estado de processamento (chamado pelo thread worker no fim) de forma thread-safe."""
        
        log_callback("\n" + "="*60)
        if is_interrupted:
            log_callback("PROCESSAMENTO ENCERRADO POR SOLICITAÇÃO DO USUÁRIO!")
        elif get_is_processing_state():
            log_callback("PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        else:
             log_callback("PROCESSAMENTO ENCERRADO DEVIDO A UM ERRO INTERNO!")
            
        log_callback("Verifique a pasta de saída.")
        log_callback("="*60)
        
        set_is_processing_state(False)


    # Validação/Criação do diretório de saída
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            log_callback(f"Diretório de saída criado: {output_dir}")
        except Exception as e:
            log_callback(f"ERRO: Não foi possível criar o diretório de saída: {e}")
            _cleanup_processing()
            return

    # Pré-verificação (CACHE)
    processed_sheets = load_processed_sheets(output_dir, max_folhas)
    log_callback(f"Cache de PDFs existente carregado: {len(processed_sheets)} folhas já convertidas.")
    
    # Listagem e ordenação
    arquivos_encontrados = [
        f for f in os.listdir(input_dir)
        if os.path.isfile(os.path.join(input_dir, f)) and f.lower().endswith(('.jpg', '.jpeg'))
    ]
    arquivos_ordenados = sorted(arquivos_encontrados)
    
    if not arquivos_ordenados:
        log_callback("Nenhuma imagem JPG/JPEG encontrada no diretório de entrada.")
        _cleanup_processing()
        return

    log_callback(f"Encontradas {len(arquivos_ordenados)} imagens. OCR paralelo usando {num_processes} processos.")
    log_callback("-" * 60)
    
    file_to_future: Dict[str, concurrent.futures.Future] = {} 
    
    # Etapa do OCR paralelo (SUBMISSÃO)
    # Usamos ThreadPoolExecutor para o gerenciamento de futures, mas ele usa ProcessPoolExecutor internamente
    # O executor em si será criado e armazenado na classe GTK, mas aqui trabalhamos com ele localmente.
    executor_ref = None # Referência para o executor (será definida na classe GTK)
    
    try:
        # Cria o executor de processos
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_processes) as executor:
            executor_ref = executor
            
            # Submete todas as tarefas
            for filename in arquivos_ordenados:
                input_path = os.path.join(input_dir, filename)
                # Passa a função worker importada
                future = executor.submit(_run_ocr_worker, input_path, max_folhas) 
                file_to_future[filename] = future
            
            log_callback(f"{len(file_to_future)} tarefas submetidas. Iniciando processamento sequencial e condicional...")
            log_callback("\n" + "="*60)
            
            # Etapa Sequencial: Resgate OCR, checagem do Cache e Processamento
            for filename in arquivos_ordenados:
                
                # Verifica a flag de interrupção
                if not get_is_processing_state():
                    break 
                    
                future = file_to_future[filename]
                
                try:
                    # Bloqueia até que o resultado do OCR da imagem selecionada esteja pronto
                    filename_returned, folha_num_ocr, full_ocr_text, img_bytes = future.result() 
                    
                    log_callback(f"--- OCR CONCLUÍDO para: {filename} ---")
                    
                    base_filename = os.path.splitext(filename)[0]
                    folha_num = folha_num_ocr
                    sufixo = ""

                    # Verifica Erro de Worker
                    if full_ocr_text.startswith("ERRO INTERNO NO WORKER:"):
                        log_callback(f"  > ERRO NO WORKER: {full_ocr_text}. Requer correção manual.")
                        folha_num = None 

                    # Aplica Correção Manual Prévia (se houver)
                    if base_filename in correcoes_manuais:
                        folha_num = correcoes_manuais[base_filename]
                        log_callback(f"  > CORREÇÃO MANUAL ANTERIOR APLICADA: Folha nº {folha_num}.")
                    
                    # Verificação de cache (é pulada se já existe)
                    if folha_num is not None and folha_num in processed_sheets:
                        if folha_num > 0 and folha_num <= max_folhas:
                            ultima_folha_processada = folha_num # Atualiza a última folha
                        
                        log_callback(f"  > *** ARQUIVO PULADO ***: Folha {folha_num:03d} já existe como PDF. Avançando.")
                        continue

                    # Processamento (Se não foi Pulado pelo cache)
                    
                    # Abertura da Imagem (Rotacionada pelo worker)
                    try:
                        # Reconstroi a imagem a partir dos bytes retornados pelo worker
                        img = Image.open(io.BytesIO(img_bytes)) 
                    except Exception:
                        log_callback(f"  > ERRO: Falha ao reconstruir imagem para {filename}. Ignorando.")
                        continue

                    # Tratamento de Erro, Lógica de verso e Correção Manual
                    is_termo = (folha_num == 0 or folha_num == max_folhas + 1)
                    
                    if folha_num is None:
                        # Se o OCR falhou
                        texto_limpo = re.sub(r'\s+', '', full_ocr_text)
                        
                        # Verifica se é uma página em branco (ou quase) para considerar como verso
                        if len(texto_limpo) < config.LIMIAR_CARACTERES_VERSO and ultima_folha_processada > 0 and not is_termo:
                            folha_num = ultima_folha_processada
                            sufixo = "-verso"
                            log_callback(f"  > AVISO: OCR falhou. Aplicando regra de VERSO: Folha nº {folha_num}{sufixo}.")
                        else:
                            # Requer intervenção manual
                            log_callback("!!! ERRO DE OCR DETECTADO - ABRINDO CORREÇÃO MANUAL !!!")
                            # Chamada BLOQUEANTE para obter o input da GUI (via fila)
                            manual_num = ask_manual_correction_callback(filename)
                            
                            if manual_num is not None:
                                folha_num = manual_num
                                # Adiciona a correção ao dicionário
                                correcoes_manuais[base_filename] = folha_num 
                                log_callback(f"  > MANUAL: Folha nº {folha_num} definida pelo usuário.")
                            else:
                                folha_num = None 
                                log_callback(f"  > IGNORADO: O arquivo será salvo com nome de erro.")

                    # Atualiza o estado da última folha processada (retorna para a GUI)
                    if folha_num is not None and folha_num > 0 and folha_num <= max_folhas:
                        ultima_folha_processada = folha_num 
                        
                    # Definição do Nome do Arquivo
                    if folha_num is not None:
                        if folha_num == 0:
                            novo_filename = "TERMO DE ABERTURA.pdf"
                        elif folha_num == max_folhas + 1:
                            novo_filename = f"TERMO DE ENCERRAMENTO.pdf" 
                        else:
                            novo_filename = f"FL. {folha_num:03d}{sufixo}.pdf"
                        log_callback(f"  > NOME DEFINIDO: '{novo_filename}'.")
                    else:
                        novo_filename = f"ERRO_OCR_{base_filename}.pdf"
                        log_callback(f"  > SALVANDO ERRO: Nome de erro aplicado: '{novo_filename}'.")
                    
                    output_path = os.path.join(output_dir, novo_filename)

                    # Conversão e Salvamento para PDF
                    try:
                        # Salva a imagem (já rotacionada pelo worker) como PDF
                        img.save(output_path, "PDF", resolution=100.0) 
                        if folha_num is not None:
                            processed_sheets.add(folha_num) # Adiciona ao cache
                        log_callback(f"  > SUCESSO: Salva em '{output_path}'.")
                    except Exception as e:
                        log_callback(f"  > ERRO FATAL ao salvar PDF para '{filename}': {e}")
                        
                except concurrent.futures.CancelledError:
                    log_callback(f"\n--- Processamento de {filename} cancelado. ---")
                    # Sai do loop sequencial
                    break 
                except Exception as exc:
                    log_callback(f"\n--- ERRO CRÍTICO ao obter resultado para {filename}: {exc} ---")
                    # Define a flag para garantir a limpeza
                    set_is_processing_state(False)
                    break
                    
            # Se a interrupção foi manual, o executor precisa ser desligado
            if not get_is_processing_state() and executor_ref:
                executor_ref.shutdown(wait=False, cancel_futures=True)
                
    except Exception as e:
        log_callback(f"ERRO CRÍTICO NA EXECUÇÃO PARALELA: {e}")
        # Garante que a limpeza seja feita após o erro
        _cleanup_processing()
        return
        
    # Limpeza final
    _cleanup_processing(is_interrupted=not get_is_processing_state())
    
    # Retorna o último valor processado para a GUI
    return ultima_folha_processada
