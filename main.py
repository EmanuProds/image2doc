# Inicializa a aplicação e trata as dependências de ambiente.
import sys
import os

# Tenta importar as classes e dependências principais
try:
    import pytesseract
    from src.interface import OCR_Application
except ImportError as e:
    print(f"ERRO: Não foi possível importar as dependências necessárias: {e}")
    sys.exit(1)


def main():
    # Função principal que verifica o ambiente e inicia o loop da aplicação GTK.
    # Verifica a disponibilidade do Tesseract
    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        print("\n" + "=" * 70)
        print(
            "ERRO CRÍTICO: Tesseract não encontrado. Certifique-se de que está instalado e configurado."
        )
        print("Instruções: https://github.com/tesseract-ocr/tesseract")
        print("=" * 70)
        sys.exit(1)

    # Inicia o loop principal do GTK
    app = OCR_Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
