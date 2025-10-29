# Contém as funções de OCR e manipulação de imagem que rodam em processos separados (ProcessPoolExecutor).
import os
import re
import io
import pytesseract
from typing import Optional, Tuple

from PIL import Image

# Importa as configurações do módulo local
from . import config

# Bloco de funções auxiliares da API

def verificar_sucesso_ocr_roi(image: Image.Image, ocr_roi: tuple, psm_config: str) -> bool:
    """
    Verifica se um padrão de número de folha válido pode ser encontrado na Região de Interesse (ROI).
    Esta função é usada pelos workers para determinar a orientação correta da imagem.
    
    Args:
        image (Image.Image): A imagem PIL a ser analisada.
        ocr_roi (tuple): A ROI (X_min, Y_min, X_max, Y_max) em escala de 0 a 1000.
        psm_config (str): Configuração do Tesseract para o OCR.
        
    Returns:
        bool: True se um número de folha for encontrado na ROI, False caso contrário.
    """
    img_width, img_height = image.size
    # Calcula a caixa de corte da ROI em coordenadas de pixel
    x_min = int(img_width * ocr_roi[0] / 1000)
    y_min = int(img_height * ocr_roi[1] / 1000)
    x_max = int(img_width * ocr_roi[2] / 1000)
    y_max = int(img_height * ocr_roi[3] / 1000)
    crop_box = (x_min, y_min, x_max, y_max)
    
    try:
        cropped_image = image.crop(crop_box)
        text_roi = pytesseract.image_to_string(cropped_image, config=psm_config)
        # Procura por "FOLHA" ou "FL" seguido por um número
        match = re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', text_roi.upper())
        return match is not None
    except Exception:
        # Se qualquer erro ocorrer (ex: imagem inválida, falha no Tesseract), retorna False
        return False

def extract_folha_num(text: str) -> Optional[int]:
    """
    Extrai o número da folha de um texto usando regex.
    
    Args:
        text (str): O texto de saída do OCR.
        
    Returns:
        Optional[int]: O número da folha encontrado ou None.
    """
    # Procura por "FOLHA" ou "FL" seguido por um número
    match = re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', text.upper())
    if match:
        try:
            # Retorna o segundo grupo que contém o número da folha
            return int(match.group(2))
        except ValueError:
            return None
    return None

def extrair_numero_folha_ocr_worker(image: Image.Image, max_folhas: int) -> Tuple[Optional[int], str]:
    """
    Executa o OCR para extrair Termos Especiais (Abertura/Encerramento) ou o Número da Folha.
    
    Args:
        image (Image.Image): Imagem PIL rotacionada.
        max_folhas (int): O número máximo de folhas do livro.
        
    Returns:
        Tuple[Optional[int], str]: O número da folha (ou 0, max_folhas+1 para Termos) e o texto completo do OCR.
    """
    full_text = ""
    
    # Tenta OCR para Termos Especiais (página inteira, PSM 3)
    try:
        full_text = pytesseract.image_to_string(image, config=r'--oem 3 -l por --psm 3')
        upper_text = full_text.upper()

        if "TERMO DE ABERTURA" in upper_text or "TERMO DE INSTALAÇÃO" in upper_text:
            return 0, full_text # 0 para Termo de Abertura
        if "TERMO DE ENCERRAMENTO" in upper_text:
            return max_folhas + 1, full_text # max_folhas + 1 para Termo de Encerramento
            
    except Exception:
        pass # Ignora erros de OCR de página inteira e tenta o OCR da ROI

    # Tenta OCR para Número da Folha (Região de Interesse, PSM 6)
    try:
        img_width, img_height = image.size
        # Calcula a caixa de corte da ROI
        x_min = int(img_width * config.OCR_ROI[0] / 1000)
        y_min = int(img_height * config.OCR_ROI[1] / 1000)
        y_max = int(img_height * config.OCR_ROI[3] / 1000)
        x_max = int(img_width * config.OCR_ROI[2] / 1000)
        crop_box = (x_min, y_min, x_max, y_max)
        
        cropped_image = image.crop(crop_box)
        text_roi = pytesseract.image_to_string(cropped_image, config=config.PSM_CONFIG)
        
        folha_numero = extract_folha_num(text_roi)
        
        return folha_numero, full_text

    except Exception:
        # Se falhar, retorna None para o número da folha e o texto completo (mesmo que vazio)
        return None, full_text


# Bloco principal do worker

def _run_ocr_worker(input_path: str, max_folhas: int) -> Tuple[str, Optional[int], str, bytes]:
    """
    Função de worker que executa o OCR, a rotação e a extração de dados para UMA ÚNICA imagem.
    É a função que o ProcessPoolExecutor chama em cada processo.
    
    Args:
        input_path (str): Caminho completo para o arquivo de imagem JPG/JPEG.
        max_folhas (int): O número máximo de folhas do livro.
        
    Returns:
        Tuple[str, Optional[int], str, bytes]: Nome do arquivo, número da folha encontrado, texto OCR completo, bytes da imagem (possivelmente rotacionada).
    """
    try:
        filename = os.path.basename(input_path)
        img = Image.open(input_path)

        # ROTAÇÃO INTELIGENTE
        # Tenta rotacionar -90 se a imagem for horizontal
        if img.width > img.height:
            img_neg90 = img.rotate(-90, expand=True)
            # Verifica se o OCR de ROI funciona melhor após a rotação
            if verificar_sucesso_ocr_roi(img_neg90, config.OCR_ROI, config.PSM_CONFIG):
                img = img_neg90
            else:
                # Se não, tenta rotacionar +90 como fallback para vertical
                img = img.rotate(90, expand=True)

        # OCR, Extração e Texto Completo (usando a imagem final/rotacionada)
        folha_num_ocr, full_ocr_text = extrair_numero_folha_ocr_worker(img, max_folhas)

        # Converter imagem (possivelmente rotacionada) para bytes para transferir ao processo principal
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG') 
        img_bytes = img_byte_arr.getvalue()
        
        # Retorna os resultados
        return (filename, folha_num_ocr, full_ocr_text, img_bytes)

    except Exception as e:
        # Em caso de erro, retorna uma mensagem de erro para o thread principal tratar
        return (os.path.basename(input_path), None, f"ERRO INTERNO NO WORKER: {e}", b'')
