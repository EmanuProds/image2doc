# Definição de todas as constantes e variáveis de configuração utilizadas no backend e na API.

# --- Parâmetros de Processamento (Compatíveis com a GUI) ---

# Máximo padrão de folhas do livro para o Termo de Encerramento.
MAX_FOLHAS_DEFAULT = 300

# Número padrão de processos/workers a serem usados no ProcessPoolExecutor.
NUM_PROCESSES_DEFAULT = 4 

# --- Configurações da Aplicação ---
APP_ID = "com.jtp.image2pdf"
APP_VERSION = "1.0.0"

# --- CONFIGURAÇÃO DE OCR ---
# REGIÃO DE INTERESSE (ROI) para OCR: (X_min, Y_min, X_max, Y_max) em escala de 0 a 1000
OCR_ROI = (450, 50, 950, 250)
# Define a área de interesse para procurar o número da folha (em escala 0-1000).

LIMIAR_CARACTERES_VERSO = 250
# Número mínimo de caracteres para uma página ser considerada 'Frente'. Abaixo disso, é tratada como 'Verso' se o OCR falhar.

PSM_CONFIG = r'--oem 3 -l por --psm 6'
# Configuração do Tesseract: Engine Mode (OEM 3) + Language (Português) + Page Segmentation Mode (PSM 6: Bloco único uniforme).

CORRECOES_MANUAIS = {}
# Dicionário para armazenar correções manuais durante a execução (chave: nome base do arquivo, valor: número da folha).
