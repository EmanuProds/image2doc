from PIL import Image
import os
import re
import pytesseract
from typing import Optional

# --- CONFIGURAÇÃO ---
# Mude este caminho para o DIRETÓRIO (pasta) que contém suas imagens
# EX: './livros/23'
INPUT_DIR = './livros/23'
# Novo diretório onde as imagens processadas serão salvas (será criado se não existir)
OUTPUT_DIR = './livros/23_editados'
# Número máximo de folhas no livro para determinar o "Termo de Encerramento"
# Exemplo: Livro com folhas de 001 a 300, o encerramento é 301.
MAX_FOLHAS = 300
# Caminho para o executável do Tesseract (ajuste se necessário, especialmente no Windows)
# Exemplo Windows: r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Em Linux/macOS geralmente não é necessário, pois está no PATH
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' # Descomente e ajuste se necessário
# --------------------


def extrair_numero_folha_ocr(image: Image.Image) -> Optional[int]:
    """
    Extrai o texto de uma imagem usando OCR e tenta encontrar o número da folha.
    Retorna o número da folha (int) ou None se não for encontrado.
    """
    try:
        # Usa OCR para extrair texto da imagem
        text = pytesseract.image_to_string(image, lang='por')
        
        # Converte o texto para maiúsculas para facilitar a busca
        upper_text = text.upper()
        
        # 1. Verifica TERMO DE ABERTURA
        if "TERMO DE ABERTURA" in upper_text or "TERMO DE INSTALAÇÃO" in upper_text:
            return 0  # Convenção: Abertura é a folha 000 (anterior a 001)

        # 2. Verifica TERMO DE ENCERRAMENTO
        # Para ser mais robusto, também verifica se o documento é muito grande,
        # assumindo que é a folha após a última folha numerada (MAX_FOLHAS + 1)
        if "TERMO DE ENCERRAMENTO" in upper_text:
            return MAX_FOLHAS + 1  # Convenção: Encerramento é a folha após a última numerada

        # 3. Procura por padrões de número de folha (ex: FOLHA: 42, LIVRO: 23, FOLHA 42)
        # Regex para capturar números após "FOLHA" ou "FL"
        match = re.search(r'(FOLHA|FL)\s*[:\s]*(\d+)', upper_text)

        if match:
            # Captura o grupo 2 da regex, que é o número da folha
            folha_numero = int(match.group(2))
            print(f"  > OCR ENCONTRADO: Folha nº {folha_numero}")
            return folha_numero

        print("  > OCR NÃO ENCONTROU um número de folha claro, Abertura ou Encerramento.")
        return None

    except pytesseract.TesseractNotFoundError:
        print("  > ERRO CRÍTICO DE OCR: O Tesseract OCR não foi encontrado.")
        print("  > Certifique-se de que o Tesseract está instalado e que o caminho (pytesseract.pytesseract.tesseract_cmd) está correto na CONFIGURAÇÃO.")
        return None
    except Exception as e:
        print(f"  > ERRO durante o processamento OCR: {e}")
        return None


def processar_imagens_no_diretorio(input_dir, output_dir):
    """
    Percorre o diretório de entrada, processa apenas arquivos .jpg, aplica OCR,
    renomeia e salva como .pdf no diretório de saída.
    """
    print(f"Iniciando processamento no diretório: {input_dir}")

    # 1. Verifica se o caminho de entrada é um diretório
    if not os.path.isdir(input_dir):
        print(f"ERRO: O caminho '{input_dir}' não é um diretório válido. Por favor, configure a variável INPUT_DIR corretamente.")
        return

    # 2. Cria o diretório de saída se ele não existir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Diretório de saída criado: {output_dir}")

    # 3. Itera sobre todos os itens dentro do diretório de entrada
    for filename in os.listdir(input_dir):
        # Constrói o caminho completo para o arquivo de entrada
        input_path = os.path.join(input_dir, filename)

        # 4. Filtra: verifica se é um ARQUIVO e se possui a extensão .jpg ou .jpeg
        if os.path.isfile(input_path) and filename.lower().endswith(('.jpg', '.jpeg')):

            print(f"\nProcessando arquivo: {filename}...")

            try:
                img = Image.open(input_path)

                # --- 5. ROTAÇÃO (Lógica existente) ---
                if img.width > img.height:
                    print("  > Orientação: Paisagem. Rotacionando 90 graus...")
                    img = img.rotate(-90, expand=True) # Alterado para -90 (anti-horário) para evitar virar a página de cabeça para baixo
                else:
                    print("  > Orientação: Retrato ou Quadrada. Sem rotação.")
                
                # --- 6. OCR e Extração de Número da Folha ---
                folha_num = extrair_numero_folha_ocr(img)

                if folha_num is not None:
                    # 7. Formatação do Nome do Arquivo
                    if folha_num == 0:
                        # Termo de Abertura: FL. 000
                        novo_filename = "FL. 000.pdf"
                        print(f"  > IDENTIFICADO: Termo de Abertura. Renomeando para '{novo_filename}'.")
                    elif folha_num == MAX_FOLHAS + 1:
                        # Termo de Encerramento: FL. 301 (ou MAX_FOLHAS + 1)
                        novo_filename = f"FL. {folha_num:03d}.pdf"
                        print(f"  > IDENTIFICADO: Termo de Encerramento. Renomeando para '{novo_filename}'.")
                    else:
                        # Folha normal: FL. 042
                        novo_filename = f"FL. {folha_num:03d}.pdf"
                        print(f"  > NOME DEFINIDO: Folha {folha_num}. Renomeando para '{novo_filename}'.")
                else:
                    # Se o OCR falhar, usa o nome original com um prefixo de erro
                    novo_filename = f"ERRO_OCR_{filename.split('.')[0]}.pdf"
                    print(f"  > AVISO: OCR falhou. Salvando com nome de erro: '{novo_filename}'.")
                
                output_path = os.path.join(output_dir, novo_filename)

                # --- 8. Conversão e Salvamento para PDF ---
                # Salva a imagem processada como PDF
                # A conversão de JPG para PDF é feita de forma nativa pela PIL
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
