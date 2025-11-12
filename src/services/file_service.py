"""
File operations service using modern Python patterns.
Handles file discovery, validation, and output operations.
"""
import logging
from pathlib import Path
from typing import List, Set, Optional
import re

from ..models import PageInfo, PageType, ProcessingConfig
from ..exceptions import FileOperationError, ValidationError

logger = logging.getLogger(__name__)


class FileService:
    """Service for handling file operations in the Image2PDF application."""

    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg'}

    def __init__(self, config: ProcessingConfig):
        """Initialize file service with configuration."""
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if not self.config.input_dir:
            raise ValidationError("Input directory not specified")
        if not self.config.output_dir:
            raise ValidationError("Output directory not specified")

        if not self.config.input_dir.exists():
            raise FileOperationError(f"Input directory does not exist: {self.config.input_dir}")
        if not self.config.input_dir.is_dir():
            raise FileOperationError(f"Input path is not a directory: {self.config.input_dir}")

    def discover_image_files(self) -> List[Path]:
        """Discover all supported image files in the input directory."""
        try:
            image_files = [
                f for f in self.config.input_dir.iterdir()
                if f.is_file() and f.suffix.lower() in self.SUPPORTED_EXTENSIONS
            ]
            # Sort for consistent processing order
            image_files.sort()
            logger.info(f"Found {len(image_files)} image files")
            return image_files
        except OSError as e:
            raise FileOperationError(f"Failed to read input directory: {e}") from e

    def ensure_output_directory(self) -> None:
        """Ensure output directory exists."""
        try:
            self.config.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Output directory ready: {self.config.output_dir}")
        except OSError as e:
            raise FileOperationError(f"Failed to create output directory: {e}") from e

    def load_processed_pages_cache(self) -> Set[int]:
        """Load cache of already processed page numbers."""
        processed_pages = set()

        if not self.config.output_dir.exists():
            return processed_pages

        try:
            for pdf_file in self.config.output_dir.glob("*.pdf"):
                page_number = self._extract_page_number_from_filename(pdf_file.name)
                if page_number is not None:
                    processed_pages.add(page_number)
                elif self._is_special_term_file(pdf_file.name):
                    # Handle special term files
                    if "ABERTURA" in pdf_file.name.upper():
                        processed_pages.add(0)
                    elif "ENCERRAMENTO" in pdf_file.name.upper():
                        processed_pages.add(self.config.max_pages + 1)

            logger.info(f"Loaded cache with {len(processed_pages)} processed pages")
            return processed_pages

        except OSError as e:
            logger.warning(f"Failed to read cache directory: {e}")
            return processed_pages

    def _extract_page_number_from_filename(self, filename: str) -> Optional[int]:
        """Extract page number from PDF filename."""
        # Pattern for FL. XXX or FL. XXX-verso
        match = re.search(r'FL\.\s*(\d{3})(?:-verso)?\.pdf', filename.upper())
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    def _is_special_term_file(self, filename: str) -> bool:
        """Check if filename is a special term file."""
        upper_name = filename.upper()
        return "TERMO DE ABERTURA" in upper_name or "TERMO DE ENCERRAMENTO" in upper_name

    def save_page_as_pdf(self, page_info: PageInfo, image_bytes: bytes) -> Path:
        """Save a page as PDF file."""
        try:
            from PIL import Image
            import io

            # Reconstruct image from bytes
            image = Image.open(io.BytesIO(image_bytes))

            # Generate output filename
            output_filename = page_info.get_output_filename()
            output_path = self.config.output_dir / output_filename

            # Save as PDF
            image.save(output_path, "PDF", resolution=100.0)

            logger.info(f"Saved page: {output_path}")
            return output_path

        except Exception as e:
            error_msg = f"Failed to save page {page_info.filename}: {e}"
            logger.error(error_msg)
            raise FileOperationError(error_msg) from e

    def is_page_already_processed(self, page_info: PageInfo, processed_cache: Set[int]) -> bool:
        """Check if a page has already been processed."""
        if page_info.page_number is None:
            return False

        # Check if page number is in cache
        if page_info.page_number in processed_cache:
            logger.info(f"Page {page_info.page_number} already processed, skipping")
            return True

        # Check if output file exists
        output_filename = page_info.get_output_filename()
        output_path = self.config.output_dir / output_filename

        if output_path.exists():
            logger.warning(f"Output file already exists: {output_path}")
            return True

        return False
