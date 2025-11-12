# 📄 Image2DOC

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![GTK](https://img.shields.io/badge/GTK-4.0-orange.svg)](https://gtk.org/)
[![Tesseract](https://img.shields.io/badge/Tesseract-OCR-green.svg)](https://github.com/tesseract-ocr/tesseract)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A GTK4 application that converts document images to organized PDFs using OCR technology. It automatically detects page numbers, organizes documents, and allows manual corrections when OCR fails.

## ✨ Features

- **⚡ Parallel OCR Processing**: Uses multiple CPU cores for faster image processing
- **🔍 Automatic Page Detection**: Extracts page numbers using Tesseract OCR
- **✏️ Manual Correction**: Interactive dialog for correcting OCR failures
- **📚 Smart Organization**: Automatically organizes PDFs by page numbers (FL. 001, FL. 002, etc.)
- **💾 Cache System**: Skips already processed images to avoid reprocessing
- **🎨 Modern UI**: Built with GTK4 and Libadwaita for a native Linux experience
- **📊 Real-time Logs**: Live monitoring of processing status and errors
- **⚙️ Configurable Settings**: Adjustable maximum pages and processing threads

## Prerequisites

### System Requirements
- Linux operating system
- Python 3.8 or higher
- GTK4 development libraries
- Tesseract OCR engine

### Installing System Dependencies

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

## Installation

1. Clone the repository:
```bash
git clone https://github.com/EmanuProds/ncx-book-organizer.git
cd img2doc
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install pytesseract pillow pygobject
```

## Usage

1. Activate the virtual environment (if created):
```bash
source venv/bin/activate
```

2. Run the application:
```bash
python main.py
```

### How to Use

1. **Select Input Directory**: Choose the folder containing your document images (JPG/JPEG)
2. **Select Output Directory**: Choose where the organized PDFs will be saved
3. **Configure Settings** (optional):
   - Maximum pages: Set the total number of pages in your document
   - Number of processes: Adjust parallel processing (0 = auto-detect)
4. **Start Processing**: Click "Start Processing" and monitor progress in the Logs tab
5. **Manual Corrections**: If OCR fails, the app will prompt for manual page number input

### Output Structure

The application creates organized PDFs with the following naming convention:
- `FL. 001.pdf`, `FL. 002.pdf`, etc. - Regular pages
- `FL. 001-verso.pdf` - Back sides of pages
- `TERMO DE ABERTURA.pdf` - Opening terms
- `TERMO DE ENCERRAMENTO.pdf` - Closing terms
- `ERRO_OCR_filename.pdf` - Files that couldn't be processed

## Configuration

### OCR Settings
- **Language**: Portuguese (por)
- **PSM Mode**: 6 (Uniform block of text)
- **ROI**: Configurable region of interest for page number detection

### Processing Settings
- **Maximum Pages**: Default 300 pages
- **Parallel Processes**: Default 4 workers
- **Cache System**: Automatically detects and skips already processed files

## Architecture

```
src/
├── core.py          # Main processing logic and parallel OCR
├── ocr.py           # OCR functions and image processing
├── config.py        # Application configuration constants
└── interface/
    ├── entrypoint.py    # GTK application initialization
    ├── gui.py           # Main window and navigation
    ├── home.py          # Processing interface
    ├── pref.py          # Preferences/settings page
    ├── logs.py          # Logging interface
    └── about.py         # About dialog
```

## Development

### Project Structure
- `main.py`: Application entry point
- `src/`: Main source code
- `old/`: Legacy code (deprecated)

### Key Technologies
- **GTK4**: Modern GUI framework
- **Libadwaita**: Adaptive UI components
- **Tesseract**: OCR engine
- **Pillow**: Image processing
- **Concurrent.futures**: Parallel processing

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Troubleshooting

### Common Issues

**Tesseract not found**
```
Error: Tesseract not found
```
- Install Tesseract: `sudo apt install tesseract-ocr`
- Ensure it's in PATH: `which tesseract`

**GTK4 not available**
```
ImportError: GTK4 libraries not found
```
- Install GTK4 development packages
- Ensure PyGObject is properly installed

**OCR accuracy issues**
- Ensure images are clear and well-lit
- Check that page numbers are in the expected region
- Use manual correction when automatic detection fails

### Performance Tips
- Use SSD storage for faster I/O
- Increase parallel processes for multi-core systems
- Process images in batches for better cache utilization

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

Developed by Emanuel Pereira

## Acknowledgments

- Tesseract OCR project
- GTK and GNOME communities
- Python Pillow library contributors
