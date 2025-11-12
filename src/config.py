"""
Application configuration using modern data structures.
Centralized configuration management for the Image2DOC application.
"""
from .models import OCRConfig, ProcessingConfig

# Application metadata
APP_ID = "com.jtp.image2doc"
APP_VERSION = "1.0.0"

# Default configurations
DEFAULT_OCR_CONFIG = OCRConfig(
    roi=(450, 50, 950, 250),  # Region of interest for page number detection
    language="por",            # Portuguese language for OCR
    psm_mode=6,               # Page segmentation mode for uniform text blocks
    oem_mode=3,               # OCR Engine Mode
    min_chars_for_front_page=250  # Minimum characters to consider as front page
)

DEFAULT_PROCESSING_CONFIG = ProcessingConfig(
    max_pages=300,            # Default maximum pages for closing term detection
    num_processes=4           # Default number of parallel processes
)

# Legacy constants for backward compatibility (will be removed)
MAX_FOLHAS_DEFAULT = DEFAULT_PROCESSING_CONFIG.max_pages
NUM_PROCESSES_DEFAULT = DEFAULT_PROCESSING_CONFIG.num_processes
OCR_ROI = DEFAULT_OCR_CONFIG.roi
LIMIAR_CARACTERES_VERSO = DEFAULT_OCR_CONFIG.min_chars_for_front_page
PSM_CONFIG = DEFAULT_OCR_CONFIG.psm_config
CORRECOES_MANUAIS = {}
