from PIL import Image
import os
import re
import pytesseract
from typing import Optional, Dict

# --- CONFIGURAÇÃO ---
# Mude este caminho para o DIRETÓRIO (pasta) que contém suas imagens
# EX: './livros/23'
INPUT_DIR = './livros/26'
# Novo diretório onde as imagens processadas serão salvas (será criado se não existir)
OUTPUT_DIR = './livros/26_editados'
# Número máximo de folhas no livro para determinar o "Termo de Encerramento"
MAX_FOLHAS = 300

# REGIÃO DE INTERESSE (ROI) para OCR: (X_min, Y_min, X_max, Y_max) em escala de 0 a 1000
# Esta área é OTIMIZADA para encontrar o número da folha (geralmente no cabeçalho).
OCR_ROI = (450, 50, 950, 250)

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
    # Se a imagem IMG_20251015_135831 for o Termo de Abertura, adicione aqui (retorna 0)
    # Exemplo: "IMG_20251015_135831": 0,
    # Se a imagem for o Termo de Encerramento (FL. 301), adicione aqui (retorna 301)
    # Exemplo: "ERRO_OCR_IMG_20251015_120736": MAX_FOLHAS + 1,
}

# ----------------------------------------------------


def extrair_numero_folha_ocr(image: Image.Image) -> Optional[int]:
    """
    Tenta identificar Termos Especiais (Abertura/Encerramento) usando OCR na imagem
    completa. Se não for um Termo Especial, recorta a imagem para o ROI
    e executa o OCR para o número da folha.
    
    Retorna o número da folha (int):
      - 0 para Termo de Abertura
      - MAX_FOLHAS + 1 para Termo de Encerramento
      - Número da folha para páginas normais
      - None se não for encontrado
    """
    global PSM_CONFIG, OCR_ROI

    # --- 1. Tentar identificar Termos Especiais usando OCR na IMAGEM COMPLETA ---
    try:
        # Usar uma configuração de PSM para página completa (PSM 3)
        full_text = pytesseract.image_to_string(image, config=r'--oem 3 -l por --psm 3')
        upper_text = full_text.upper()

        # 1a. Verifica Termo de Abertura
        if "TERMO DE ABERTURA" in upper_text or "TERMO DE INSTALAÇÃO" in upper_text:
            print("  > OCR ENCONTRADO (Página Completa): Termo de Abertura.")
            return 0
        
        # 1b. Verifica Termo de Encerramento
        if "TERMO DE ENCERRAMENTO" in upper_text:
            print("  > OCR ENCONTRADO (Página Completa): Termo de Encerramento.")
            return MAX_FOLHAS + 1 
            
    except pytesseract.TesseractNotFoundError:
        print("  > ERRO CRÍTICO DE OCR: O Tesseract OCR não foi encontrado. Verifique o caminho.")
        return None
    except Exception as e:
        print(f"  > ERRO durante a tentativa de OCR na página completa: {e}")
        # Continua para a próxima etapa (OCR por ROI) em caso de erro não crítico

    # --- 2. Tentar identificar Número de Folha usando OCR na REGIÃO DE INTERESSE (ROI) ---
    # 2a. Definir o box de corte em PIXELS
    img_width, img_height = image.size
    
    # Converte as coordenadas (0-1000) para pixels
    x_min = int(img_width * OCR_ROI[0] / 1000)
    y_min = int(img_height * OCR_ROI[1] / 1000)
    x_max = int(img_width * OCR_ROI[2] / 1000)
    y_max = int(img_height * OCR_ROI[3] / 1000)
    
    crop_box = (x_min, y_min, x_max, y_max)
    
    try:
        # 2b. Recortar a imagem
        cropped_image = image.crop(crop_box)
        
        # 2c. Executar o OCR apenas na área recortada (usando PSM 6 otimizado)
        text_roi = pytesseract.image_to_string(cropped_image, config=PSM_CONFIG)
        upper_text_roi = text_roi.upper()

        # 2d. Procura por padrões de número de folha (ex: FOLHA: 42, FL. 42)
        match = re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', upper_text_roi)

        if match:
            # Captura o grupo 2 da regex, que é o número da folha
            folha_numero = int(match.group(2))
            print(f"  > OCR SUCESSO (ROI): Folha nº {folha_numero}")
            return folha_numero
        
        print(f"  > OCR FALHA: Não encontrou um número de folha claro no ROI: '{upper_text_roi.strip().replace('\n', ' ')}'")
        return None

    except Exception as e:
        print(f"  > ERRO durante o processamento OCR no ROI: {e}")
        return None


def processar_imagens_no_diretorio(input_dir, output_dir):
    """
    Percorre o diretório de entrada, processa arquivos .jpg/.jpeg, aplica OCR com ROI,
    aplica correções manuais (fallback) e salva como .pdf no diretório de saída.
    """
    print(f"Iniciando processamento no diretório: {input_dir}")

    # 1. Verifica e cria o diretório de saída
    if not os.path.isdir(input_dir):
        print(f"ERRO: O caminho '{input_dir}' não é um diretório válido. Por favor, configure a variável INPUT_DIR corretamente.")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Diretório de saída criado: {output_dir}")

    # 2. Itera sobre todos os itens dentro do diretório de entrada
    for filename in os.listdir(input_dir):
        input_path = os.path.join(input_dir, filename)

        # Remove a extensão para usar na verificação de correções
        base_filename = os.path.splitext(filename)[0]

        # 3. Filtra: verifica se é um ARQUIVO e se possui a extensão .jpg ou .jpeg
        if os.path.isfile(input_path) and filename.lower().endswith(('.jpg', '.jpeg')):

            print(f"\nProcessando arquivo: {filename}...")

            try:
                img = Image.open(input_path)

                # --- ROTAÇÃO ---
                if img.width > img.height:
                    print("  > Orientação: Paisagem. Rotacionando -90 graus...")
                    img = img.rotate(-90, expand=True)
                else:
                    print("  > Orientação: Retrato ou Quadrada. Sem rotação.")
                
                # --- OCR e Extração de Número da Folha ---
                folha_num_ocr = extrair_numero_folha_ocr(img)
                folha_num = folha_num_ocr
                
                # --- CORREÇÃO MANUAL / OVERRIDE ---
                # Verifica se o arquivo tem uma correção manual definida.
                if base_filename in CORRECOES_MANUAIS:
                    folha_num_corrigido = CORRECOES_MANUAIS[base_filename]
                    print(f"  > CORREÇÃO MANUAL APLICADA: '{base_filename}' forçado para Folha nº {folha_num_corrigido}.")
                    folha_num = folha_num_corrigido # Sobrescreve o resultado do OCR
                
                # --- 5. Definição do Nome do Arquivo ---
                if folha_num is not None:
                    
                    if folha_num == 0:
                        # Termo de Abertura: FL. 000
                        novo_filename = "TERMO DE ABERTURA.pdf"
                        print(f"  > NOME DEFINIDO: Termo de Abertura -> '{novo_filename}'.")
                    elif folha_num == MAX_FOLHAS + 1:
                        # Termo de Encerramento: FL. 301 (ou MAX_FOLHAS + 1)
                        novo_filename = f"TERMO DE ENCERRAMENTO.pdf"
                        print(f"  > NOME DEFINIDO: Termo de Encerramento -> '{novo_filename}'.")
                    else:
                        # Folha normal: FL. 042. O :03d garante 3 dígitos.
                        novo_filename = f"FL. {folha_num:03d}.pdf"
                        print(f"  > NOME DEFINIDO: Folha {folha_num:03d} -> '{novo_filename}'.")
                
                else:
                    # Se o OCR falhar e NÃO houver correção manual, usa o nome de erro
                    novo_filename = f"ERRO_OCR_{base_filename}.pdf"
                    print(f"  > AVISO: OCR falhou e sem correção manual. Salvando com nome de erro: '{novo_filename}'.")
                
                output_path = os.path.join(output_dir, novo_filename)

                # --- 6. Conversão e Salvamento para PDF ---
                img.save(output_path, "PDF", resolution=100.0)
                
                print(f"  > SUCESSO: Salva e convertida para PDF em '{output_path}'.")

            except Exception as e:
                print(f"  > ERRO FATAL ao processar '{filename}': {e}")
                print("  > Este arquivo foi ignorado.")

        elif os.path.isdir(input_path):
             print(f"Ignorando item: {filename} (É um subdiretório).")
        else:
             print(f"Ignorando item: {filename} (Não é um arquivo .jpg/.jpeg).")

    print("\nProcessamento de todas as imagens no diretório concluído.")


# --- Execução do Script ---
if __name__ == "__main__":
    processar_imagens_no_diretorio(INPUT_DIR, OUTPUT_DIR)
