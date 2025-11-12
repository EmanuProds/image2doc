# 📄 Image2DOC

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![GTK](https://img.shields.io/badge/GTK-4.0-orange.svg)](https://gtk.org/)
[![Tesseract](https://img.shields.io/badge/Tesseract-OCR-green.svg)](https://github.com/tesseract-ocr/tesseract)
[![Licença: MIT](https://img.shields.io/badge/Licença-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Uma aplicação GTK4 que converte imagens de documentos para PDFs organizados usando tecnologia OCR. Detecta automaticamente números de página, organiza documentos e permite correções manuais quando o OCR falha.

## ✨ Funcionalidades

- **⚡ Processamento OCR Paralelo**: Usa múltiplos núcleos de CPU para processamento mais rápido de imagens
- **🔍 Detecção Automática de Páginas**: Extrai números de página usando OCR Tesseract
- **✏️ Correção Manual**: Diálogo interativo para corrigir falhas do OCR
- **📚 Organização Inteligente**: Organiza automaticamente PDFs por números de página (FL. 001, FL. 002, etc.)
- **💾 Sistema de Cache**: Pula imagens já processadas para evitar reprocessamento
- **🎨 Interface Moderna**: Construída com GTK4 e Libadwaita para uma experiência nativa no Linux
- **📊 Logs em Tempo Real**: Monitoramento ao vivo do status de processamento e erros
- **⚙️ Configurações Ajustáveis**: Páginas máximas e threads de processamento configuráveis

## Pré-requisitos

### Requisitos do Sistema
- Sistema operacional Linux
- Python 3.8 ou superior
- Bibliotecas de desenvolvimento GTK4
- Motor OCR Tesseract

### Instalando Dependências do Sistema

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3 python3-pip tesseract-ocr tesseract-ocr-por libgtk-4-dev libadwaita-1-dev
```

#### Fedora
```bash
sudo dnf install python3 python3-pip tesseract tesseract-langpack-por gtk4-devel libadwaita-devel
```

#### Arch Linux
```bash
sudo pacman -S python python-pip tesseract tesseract-data-por gtk4 libadwaita
```

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/EmanuProds/ncx-book-organizer.git
cd img2doc
```

2. Crie um ambiente virtual (recomendado):
```bash
python3 -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

3. Instale as dependências Python:
```bash
pip install pytesseract pillow pygobject
```

## Uso

1. Ative o ambiente virtual (se criado):
```bash
source venv/bin/activate
```

2. Execute a aplicação:
```bash
python main.py
```

### Como Usar

1. **Selecionar Diretório de Entrada**: Escolha a pasta contendo suas imagens de documento (JPG/JPEG)
2. **Selecionar Diretório de Saída**: Escolha onde os PDFs organizados serão salvos
3. **Configurar Preferências** (opcional):
   - Páginas máximas: Defina o número total de páginas do seu documento
   - Número de processos: Ajuste o processamento paralelo (0 = detecção automática)
4. **Iniciar Processamento**: Clique em "Iniciar Processamento" e monitore o progresso na aba Logs
5. **Correções Manuais**: Se o OCR falhar, o app solicitará entrada manual do número da página

### Estrutura de Saída

A aplicação cria PDFs organizados com a seguinte convenção de nomenclatura:
- `FL. 001.pdf`, `FL. 002.pdf`, etc. - Páginas regulares
- `FL. 001-verso.pdf` - Verso das páginas
- `TERMO DE ABERTURA.pdf` - Termos de abertura
- `TERMO DE ENCERRAMENTO.pdf` - Termos de encerramento
- `ERRO_OCR_filename.pdf` - Arquivos que não puderam ser processados

## Configuração

### Configurações OCR
- **Idioma**: Português (por)
- **Modo PSM**: 6 (Bloco uniforme de texto)
- **ROI**: Região de interesse configurável para detecção de números de página

### Configurações de Processamento
- **Páginas Máximas**: Padrão 300 páginas
- **Processos Paralelos**: Padrão 4 workers
- **Sistema de Cache**: Detecta e pula automaticamente arquivos já processados

## Arquitetura

```
src/
├── core.py          # Lógica principal de processamento e OCR paralelo
├── ocr.py           # Funções OCR e processamento de imagem
├── config.py        # Constantes de configuração da aplicação
└── interface/
    ├── entrypoint.py    # Inicialização da aplicação GTK
    ├── gui.py           # Janela principal e navegação
    ├── home.py          # Interface de processamento
    ├── pref.py          # Página de preferências/configurações
    ├── logs.py          # Interface de logging
    └── about.py         # Diálogo Sobre
```

## Desenvolvimento

### Estrutura do Projeto
- `main.py`: Ponto de entrada da aplicação
- `src/`: Código fonte principal
- `old/`: Código legado (descontinuado)

### Tecnologias Principais
- **GTK4**: Framework GUI moderno
- **Libadwaita**: Componentes UI adaptativos
- **Tesseract**: Motor OCR
- **Pillow**: Processamento de imagem
- **Concurrent.futures**: Processamento paralelo

### Contribuição
1. Faça fork do repositório
2. Crie uma branch de funcionalidade
3. Faça suas alterações
4. Teste exaustivamente
5. Envie um pull request

## Solução de Problemas

### Problemas Comuns

**Tesseract não encontrado**
```
Erro: Tesseract não encontrado
```
- Instale o Tesseract: `sudo apt install tesseract-ocr`
- Certifique-se de que está no PATH: `which tesseract`

**GTK4 não disponível**
```
ImportError: Bibliotecas GTK4 não encontradas
```
- Instale pacotes de desenvolvimento GTK4
- Certifique-se de que PyGObject está instalado corretamente

**Problemas de precisão do OCR**
- Certifique-se de que as imagens estão claras e bem iluminadas
- Verifique se os números de página estão na região esperada
- Use correção manual quando a detecção automática falhar

### Dicas de Performance
- Use armazenamento SSD para I/O mais rápido
- Aumente processos paralelos para sistemas multi-core
- Processe imagens em lotes para melhor utilização do cache

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo LICENSE para detalhes.

## Autor

Desenvolvido por Emanuel Pereira

## Agradecimentos

- Projeto Tesseract OCR
- Comunidades GTK e GNOME
- Contribuidores da biblioteca Python Pillow
