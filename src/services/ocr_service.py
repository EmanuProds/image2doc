"""
OCR processing service using Tesseract.
Handles image rotation, text extraction, and page number detection.
"""
import logging
from pathlib import Path
from typing import Optional, Tuple
import io
import re

import pytesseract
from PIL import Image

from ..models import OCRConfig, OCRResult, PageType
from ..exceptions import OCRError

logger = logging.getLogger(__name__)


class OCRService:
    """Service for OCR processing operations."""

    def __init__(self, config: OCRConfig):
        """Initialize OCR service with configuration."""
        self.config = config

    def process_image(self, image_path: Path) -> OCRResult:
        """
        Process a single image through OCR pipeline.

        Args:
            image_path: Path to the image file

        Returns:
            OCRResult with processing results

        Raises:
            OCRError: If OCR processing fails
        """
        try:
            # Load and potentially rotate image
            image = self._load_and_rotate_image(image_path)

            # Extract page number and full text
            page_number, full_text = self._extract_page_info(image)

            # Convert processed image to bytes for saving
            image_bytes = self._image_to_bytes(image)

            confidence_score = self._calculate_confidence_score(full_text)

            return OCRResult(
                filename=image_path.name,
                page_number=page_number,
                full_text=full_text,
                processed_image_bytes=image_bytes,
                confidence_score=confidence_score
            )

        except Exception as e:
            error_msg = f"OCR processing failed for {image_path.name}: {e}"
            logger.error(error_msg)
            return OCRResult(
                filename=image_path.name,
                page_number=None,
                full_text="",
                processed_image_bytes=b"",
                error_message=error_msg
            )

    def _load_and_rotate_image(self, image_path: Path) -> Image.Image:
        """Load image and apply intelligent rotation if needed."""
        try:
            image = Image.open(image_path)

            # If image is wider than tall, try rotating
            if image.width > image.height:
                rotated_image = image.rotate(-90, expand=True)

                # Check if rotation improves OCR success
                if self._check_ocr_success(rotated_image):
                    logger.info(f"Rotated image -90°: {image_path.name}")
                    return rotated_image
                else:
                    # Try +90° as fallback
                    rotated_image = image.rotate(90, expand=True)
                    logger.info(f"Rotated image +90°: {image_path.name}")
                    return rotated_image

            return image

        except Exception as e:
            raise OCRError(f"Failed to load/rotate image {image_path.name}: {e}") from e

    def _check_ocr_success(self, image: Image.Image) -> bool:
        """Check if OCR can successfully extract page number from image."""
        try:
            # Crop to ROI
            cropped = self._crop_to_roi(image)

            # Try OCR on cropped region
            text = pytesseract.image_to_string(cropped, config=self.config.psm_config)

            # Check for page number pattern
            return bool(re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', text.upper()))

        except Exception:
            return False

    def _crop_to_roi(self, image: Image.Image) -> Image.Image:
        """Crop image to the configured ROI."""
        img_width, img_height = image.size

        # Convert percentage ROI to pixel coordinates
        x_min = int(img_width * self.config.roi[0] / 1000)
        y_min = int(img_height * self.config.roi[1] / 1000)
        x_max = int(img_width * self.config.roi[2] / 1000)
        y_max = int(img_height * self.config.roi[3] / 1000)

        # Ensure valid crop bounds
        x_min, x_max = max(0, x_min), min(img_width, x_max)
        y_min, y_max = max(0, y_min), min(img_height, y_max)

        if x_max <= x_min or y_max <= y_min:
            raise OCRError("Invalid ROI coordinates")

        return image.crop((x_min, y_min, x_max, y_max))

    def _extract_page_info(self, image: Image.Image) -> Tuple[Optional[int], str]:
        """Extract page number and full text from image."""
        # First, try to detect special terms (opening/closing)
        full_text = self._ocr_full_page(image)
        page_number = self._detect_special_terms(full_text)

        if page_number is not None:
            return page_number, full_text

        # If not a special term, try ROI-based page number extraction
        page_number = self._extract_page_number_from_roi(image)

        return page_number, full_text

    def _ocr_full_page(self, image: Image.Image) -> str:
        """Perform OCR on the full page."""
        try:
            return pytesseract.image_to_string(
                image,
                config=f"--oem {self.config.oem_mode} -l {self.config.language} --psm 3"
            )
        except Exception as e:
            logger.warning(f"Full page OCR failed: {e}")
            return ""

    def _detect_special_terms(self, text: str) -> Optional[int]:
        """Detect special term pages (opening/closing terms)."""
        upper_text = text.upper()

        if "TERMO DE ABERTURA" in upper_text or "TERMO DE INSTALAÇÃO" in upper_text:
            return 0  # Opening term
        elif "TERMO DE ENCERRAMENTO" in upper_text:
            return -1  # Closing term (will be converted to max_pages + 1 later)

        return None

    def _extract_page_number_from_roi(self, image: Image.Image) -> Optional[int]:
        """Extract page number from ROI."""
        try:
            cropped = self._crop_to_roi(image)
            roi_text = pytesseract.image_to_string(cropped, config=self.config.psm_config)
            return self._parse_page_number(roi_text)
        except Exception as e:
            logger.warning(f"ROI OCR failed: {e}")
            return None

    def _parse_page_number(self, text: str) -> Optional[int]:
        """Parse page number from OCR text."""
        # Look for patterns like "FOLHA 123" or "FL 123" or "FL. 123"
        match = re.search(r'(FOLHA|FL)\s*[:.\s]*(\d+)', text.upper())
        if match:
            try:
                return int(match.group(2))
            except ValueError:
                pass
        return None

    def _image_to_bytes(self, image: Image.Image) -> bytes:
        """Convert PIL image to bytes."""
        try:
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            return buffer.getvalue()
        except Exception as e:
            raise OCRError(f"Failed to convert image to bytes: {e}") from e

    def _calculate_confidence_score(self, text: str) -> float:
        """Calculate a simple confidence score based on text length and content."""
        if not text.strip():
            return 0.0

        # Basic heuristics for confidence
        score = min(len(text.strip()) / 100.0, 1.0)  # Length-based score

        # Bonus for having numbers (likely page numbers)
        if re.search(r'\d+', text):
            score += 0.2

        # Bonus for structured text
        if re.search(r'(FOLHA|FL)', text.upper()):
            score += 0.3

        return min(score, 1.0)

    def determine_page_type(self, ocr_result: OCRResult, last_page_number: int,
                           max_pages: int) -> PageType:
        """Determine the type of page based on OCR results."""
        if ocr_result.page_number == 0:
            return PageType.OPENING_TERM
        elif ocr_result.page_number == -1:
            return PageType.CLOSING_TERM
        elif ocr_result.page_number is None:
            # Check if it might be a back page
            clean_text = re.sub(r'\s+', '', ocr_result.full_text)
            if (len(clean_text) < self.config.min_chars_for_front_page and
                last_page_number > 0):
                return PageType.BACK_PAGE
            else:
                return PageType.ERROR
        else:
            return PageType.REGULAR
