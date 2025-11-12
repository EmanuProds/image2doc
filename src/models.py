"""
Data models and domain entities for the Image2PDF application.
Uses modern Python features like dataclasses and enums for clean, type-safe code.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, List
from PIL import Image


class ProcessingStatus(Enum):
    """Status of document processing operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PageType(Enum):
    """Types of document pages."""
    REGULAR = "regular"
    OPENING_TERM = "opening_term"
    CLOSING_TERM = "closing_term"
    BACK_PAGE = "back_page"
    ERROR = "error"


@dataclass
class OCRConfig:
    """Configuration for OCR processing."""
    roi: tuple[int, int, int, int] = (450, 50, 950, 250)
    language: str = "por"
    psm_mode: int = 6
    oem_mode: int = 3
    min_chars_for_front_page: int = 250

    @property
    def psm_config(self) -> str:
        """Get Tesseract PSM configuration string."""
        return f"--oem {self.oem_mode} -l {self.language} --psm {self.psm_mode}"


@dataclass
class ProcessingConfig:
    """Configuration for document processing."""
    max_pages: int = 300
    num_processes: int = 4
    input_dir: Optional[Path] = None
    output_dir: Optional[Path] = None


@dataclass
class PageInfo:
    """Information about a document page."""
    filename: str
    page_number: Optional[int]
    page_type: PageType
    ocr_text: str
    confidence_score: float = 0.0
    is_processed: bool = False
    correction_applied: bool = False

    @property
    def base_filename(self) -> str:
        """Get filename without extension."""
        return Path(self.filename).stem

    def get_output_filename(self) -> str:
        """Generate output filename based on page type and number."""
        if self.page_type == PageType.OPENING_TERM:
            return "TERMO DE ABERTURA.pdf"
        elif self.page_type == PageType.CLOSING_TERM:
            return "TERMO DE ENCERRAMENTO.pdf"
        elif self.page_number is not None:
            suffix = "-verso" if self.page_type == PageType.BACK_PAGE else ""
            return f"FL. {self.page_number:03d}{suffix}.pdf"
        else:
            return f"ERRO_OCR_{self.base_filename}.pdf"


@dataclass
class ProcessingResult:
    """Result of a document processing operation."""
    status: ProcessingStatus
    processed_pages: List[PageInfo] = field(default_factory=list)
    total_pages: int = 0
    last_processed_page: Optional[int] = None
    errors: List[str] = field(default_factory=list)
    manual_corrections: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate of processing."""
        if not self.processed_pages:
            return 0.0
        successful = sum(1 for page in self.processed_pages if page.is_processed)
        return successful / len(self.processed_pages)


@dataclass
class OCRResult:
    """Result of OCR processing for a single image."""
    filename: str
    page_number: Optional[int]
    full_text: str
    processed_image_bytes: bytes
    confidence_score: float = 0.0
    error_message: Optional[str] = None

    @property
    def has_error(self) -> bool:
        """Check if OCR processing failed."""
        return self.error_message is not None or "ERRO INTERNO" in self.full_text


@dataclass
class ManualCorrection:
    """Manual correction data for OCR failures."""
    filename: str
    suggested_page: int
    user_correction: Optional[int] = None
    action: str = "pending"  # "confirm", "skip", "stop", "pending"

    def apply_correction(self) -> Optional[int]:
        """Apply the manual correction."""
        if self.action == "confirm" and self.user_correction is not None:
            return self.user_correction
        elif self.action == "skip":
            return self.suggested_page
        return None
