from PIL import Image
import os
import re
import pytesseract
from typing import Optional, Dict

# --- CONFIGURAÇÃO ---
# Mude este caminho para o DIRETÓRIO (pasta) que contém suas imagens
# EX: './livros/23'
INPUT_DIR = './livros/23'
# Novo diretório onde as imagens processadas serão salvas (será criado se não existir)
OUTPUT_DIR = './livros/23_editados'
# Número máximo de folhas no livro para determinar o "Termo de Encerramento"
MAX_FOLHAS = 300

# REGIÃO DE INTERESSE (ROI) para OCR: (X_min, Y_min, X_max, Y_max) em escala de 0 a 1000
# Esta área é OTIMIZADA para encontrar o número da folha (geralmente no cabeçalho).
OCR_ROI = (450, 50, 950, 250)

# LIMIAR DE CARACTERES para detecção de "verso"
# Se o OCR da imagem completa retornar menos do que este número de caracteres,
# a página é considerada "em branco" ou "quase em branco" (verso).
LIMIAR_CARACTERES_VERSO = 250 

# Caminho para o executável do Tesseract (ajuste se necessário, especialmente no Windows)
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' # Descomente e ajuste se necessário

# Configuração de OCR (PSM - Page Segmentation Mode):
# 6: Assume um bloco uniforme de texto (bom para a área recortada).
# -l por: Define o idioma português.
PSM_CONFIG = r'--oem 3 -l por --psm 6'

# --- CORREÇÕES MANUAIS (FALLBACK CRÍTICO) ---
# Dicionário para corrigir erros de OCR conhecidos e persistentes em imagens específicas.
# Chave: Nome base do arquivo JPG (sem extensão).
# Valor: Número da folha correto (int).
CORRECOES_MANUAIS: Dict[str, int] = {
    # ERRO_OCR_IMG_20251015_113139 deveria ser Folha 70
    "IMG_20251015_113139": 70,
    # ERRO_OCR_IMG_20251015_113525 deveria ser Folha 100
    "IMG_20251015_113525": 100,
    # FL. 002 (IMG_20251015_115652) deveria ser Folha 218
    "IMG_20251015_115652": 218,
    # FL. 004 (IMG_20251015_112749) deveria ser Folha 43,
    "IMG_20251015_112749": 43,
    # Exemplo: Se "IMG_20251015_135831" for Termo de Abertura (0)
    # Exemplo: "IMG_20251015_135831": 0,
}

# ----------------------------------------------------


def verificar_sucesso_ocr_roi(image: Image.Image, ocr_roi: tuple, psm_config: str) -> bool:
    """
    Verifica se um padrão de número de folha válido pode ser encontrado
    na Região de Interesse (ROI) da imagem.
    Retorna True se o padrão for encontrado, False caso contrário.
    """
    img_width, img_height = image.size
    
    # Converte as coordenadas (0-1000) para pixels
    x_min = int(img_width * ocr_roi[0] / 1000)
    y_min = int(img_height * ocr_roi[1] / 1000)
    x_max = int(img_width * ocr_roi[2] / 1000)
    y_max = int(img_height * ocr_roi[3] / 1000)
    
    crop_box = (x_min, y_min, x_max, y_max)
    
    try:
        cropped_image = image.crop(crop_box)
        text_roi = pytesseract.image_to_string(cropped_image, config=psm_config)
        
        # O OCR só é considerado bem-sucedido se encontrar o padrão FOLHA/FL
        match = re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', text_roi.upper())
        return match is not None
    except Exception:
        return False


def extrair_numero_folha_ocr(image: Image.Image) -> tuple[Optional[int], str]:
    """
    Tenta identificar Termos Especiais e Números de Folha.
    Retorna uma tupla: (Número da folha (int ou None), Texto completo do OCR).
    """
    global PSM_CONFIG, OCR_ROI

    full_text = ""
    try:
        # Tentar OCR na imagem completa para capturar Termos Especiais e texto para o limite de verso
        # Usar uma configuração de PSM para página completa (PSM 3)
        full_text = pytesseract.image_to_string(image, config=r'--oem 3 -l por --psm 3')
        upper_text = full_text.upper()

        # 1a. Verifica Termo de Abertura
        if "TERMO DE ABERTURA" in upper_text or "TERMO DE INSTALAÇÃO" in upper_text:
            print("  > OCR ENCONTRADO (Página Completa): Termo de Abertura.")
            return 0, full_text
        
        # 1b. Verifica Termo de Encerramento
        if "TERMO DE ENCERRAMENTO" in upper_text:
            print("  > OCR ENCONTRADO (Página Completa): Termo de Encerramento.")
            return MAX_FOLHAS + 1, full_text
            
    except pytesseract.TesseractNotFoundError:
        print("  > ERRO CRÍTICO DE OCR: O Tesseract OCR não foi encontrado. Verifique o caminho.")
        return None, full_text
    except Exception as e:
        print(f"  > ERRO durante a tentativa de OCR na página completa: {e}")
        # Continua para a próxima etapa (OCR por ROI) em caso de erro não crítico

    # --- 2. Tentar identificar Número de Folha usando OCR na REGIÃO DE INTERESSE (ROI) ---
    img_width, img_height = image.size
    x_min = int(img_width * OCR_ROI[0] / 1000)
    y_min = int(img_height * OCR_ROI[1] / 1000)
    x_max = int(img_width * OCR_ROI[2] / 1000)
    y_max = int(img_height * OCR_ROI[3] / 1000)
    crop_box = (x_min, y_min, x_max, y_max)
    
    try:
        cropped_image = image.crop(crop_box)
        text_roi = pytesseract.image_to_string(cropped_image, config=PSM_CONFIG)
        upper_text_roi = text_roi.upper()

        # 2d. Procura por padrões de número de folha (ex: FOLHA: 42, FL. 42)
        match = re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', upper_text_roi)

        if match:
            folha_numero = int(match.group(2))
            print(f"  > OCR SUCESSO (ROI): Folha nº {folha_numero}")
            return folha_numero, full_text
        
        # OCR falhou no ROI.
        return None, full_text

    except Exception as e:
        print(f"  > ERRO durante o processamento OCR no ROI: {e}")
        return None, full_text


def processar_imagens_no_diretorio(input_dir, output_dir):
    """
    Percorre o diretório de entrada, processa arquivos .jpg/.jpeg, aplica rotação
    inteligente, OCR, correções manuais (fallback), lógica de "-verso"
    e salva como .pdf, seguindo a ordem alfabética/numérica do nome do arquivo.
    """
    global OCR_ROI, PSM_CONFIG, LIMIAR_CARACTERES_VERSO
    print(f"Iniciando processamento no diretório: {input_dir}")

    if not os.path.isdir(input_dir):
        print(f"ERRO: O caminho '{input_dir}' não é um diretório válido.")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Diretório de saída criado: {output_dir}")

    # Variável de estado para rastrear o último número de folha (para a regra de "verso")
    ultima_folha_processada = 0 
    
    arquivos_encontrados = [
        f for f in os.listdir(input_dir)
        if os.path.isfile(os.path.join(input_dir, f)) and f.lower().endswith(('.jpg', '.jpeg'))
    ]
    arquivos_ordenados = sorted(arquivos_encontrados)
    print(f"Foram encontrados {len(arquivos_ordenados)} imagens para processamento (ordenadas por nome).")

    for filename in arquivos_ordenados:
        input_path = os.path.join(input_dir, filename)
        base_filename = os.path.splitext(filename)[0]

        print(f"\nProcessando arquivo: {filename}...")

        try:
            img = Image.open(input_path)

            # --- ROTAÇÃO INTELIGENTE ---
            if img.width > img.height:
                img_neg90 = img.rotate(-90, expand=True)
                
                # Prioriza a rotação que resulta em um OCR bem-sucedido no ROI
                if verificar_sucesso_ocr_roi(img_neg90, OCR_ROI, PSM_CONFIG):
                    img = img_neg90
                    print("  > Orientação: Paisagem. Rotacionado em -90 graus (Para a esquerda) via OCR.")
                else:
                    img_pos90 = img.rotate(90, expand=True)
                    if verificar_sucesso_ocr_roi(img_pos90, OCR_ROI, PSM_CONFIG):
                        img = img_pos90
                        print("  > Orientação: Paisagem. Rotacionado em +90 graus (Para a direita) via OCR.")
                    else:
                        img = img_neg90
                        print("  > Orientação: Paisagem. OCR de rotação falhou. Fallback para -90 graus.")
            else:
                print("  > Orientação: Retrato ou Quadrada. Sem rotação.")
            
            # --- OCR, Extração e Texto Completo ---
            folha_num_ocr, full_ocr_text = extrair_numero_folha_ocr(img)
            folha_num = folha_num_ocr
            
            sufixo = ""

            # --- CORREÇÃO MANUAL / OVERRIDE ---
            if base_filename in CORRECOES_MANUAIS:
                folha_num = CORRECOES_MANUAIS[base_filename]
                print(f"  > CORREÇÃO MANUAL APLICADA: '{base_filename}' forçado para Folha nº {folha_num}.")
            
            # --- LÓGICA DE 'VERSO' (Se o OCR falhou E não é Termo) ---
            if folha_num is None:
                # Se o OCR falhou e não é um Termo (Termos já são tratados no extrair_numero_folha_ocr)
                
                # Remove espaços e quebras de linha para contar apenas o texto útil
                texto_limpo = re.sub(r'\s+', '', full_ocr_text)
                
                if len(texto_limpo) < LIMIAR_CARACTERES_VERSO and ultima_folha_processada > 0:
                    # Se o texto for muito pequeno, assume que é o verso da última folha
                    folha_num = ultima_folha_processada
                    sufixo = "-verso"
                    print(f"  > AVISO: OCR falhou e pouco texto ({len(texto_limpo)} chars). Aplicando regra de VERSO: Folha nº {folha_num}{sufixo}.")
                else:
                    # Não foi possível identificar o número E não é considerada uma página de verso
                    folha_num = None
                    print(f"  > AVISO: OCR falhou e texto extenso ({len(texto_limpo)} chars). Não é verso. Marcando como ERRO.")

            # --- ATUALIZAÇÃO DO RASTREADOR DE FOLHA ---
            # Atualiza o rastreador APENAS se um número de folha frontal foi encontrado (excluindo 0 e MAX_FOLHAS+1)
            if folha_num is not None and folha_num > 0 and folha_num <= MAX_FOLHAS:
                # Se a página tiver o número da folha, este é a folha frontal.
                ultima_folha_processada = folha_num
                
            # --- 5. Definição do Nome do Arquivo ---
            if folha_num is not None:
                
                if folha_num == 0:
                    # Termo de Abertura: FL. 000
                    novo_filename = "FL. 000 - TERMO DE ABERTURA.pdf"
                    print(f"  > NOME DEFINIDO: Termo de Abertura -> '{novo_filename}'.")
                elif folha_num == MAX_FOLHAS + 1:
                    # Termo de Encerramento: FL. 301 (ou MAX_FOLHAS + 1)
                    novo_filename = f"FL. {folha_num:03d} - TERMO DE ENCERRAMENTO.pdf"
                    print(f"  > NOME DEFINIDO: Termo de Encerramento -> '{novo_filename}'.")
                else:
                    # Folha normal ou Verso: FL. 042.pdf ou FL. 042-verso.pdf
                    novo_filename = f"FL. {folha_num:03d}{sufixo}.pdf"
                    print(f"  > NOME DEFINIDO: Folha {folha_num:03d}{sufixo} -> '{novo_filename}'.")
            
            else:
                # Fallback final se for None (OCR falhou e não se enquadrou como verso/termo)
                novo_filename = f"ERRO_OCR_{base_filename}.pdf"
                print(f"  > AVISO: OCR falhou e sem correção/verso. Salvando com nome de erro: '{novo_filename}'.")
            
            output_path = os.path.join(output_dir, novo_filename)

            # --- 6. Conversão e Salvamento para PDF ---
            img.save(output_path, "PDF", resolution=100.0)
            
            print(f"  > SUCESSO: Salva e convertida para PDF em '{output_path}'.")

        except Exception as e:
            print(f"  > ERRO FATAL ao processar '{filename}': {e}")
            print("  > Este arquivo foi ignorado.")

    print("\nProcessamento de todas as imagens no diretório concluído.")


# --- Execução do Script ---
if __name__ == "__main__":
    processar_imagens_no_diretorio(INPUT_DIR, OUTPUT_DIR)
