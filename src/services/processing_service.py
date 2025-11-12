"""
Main document processing service.
Coordinates OCR, file operations, and page processing workflow.
"""
import logging
from pathlib import Path
from typing import Dict, List, Callable, Optional
from concurrent.futures import ProcessPoolExecutor, Future

from ..models import (
    ProcessingConfig, OCRConfig, ProcessingResult, ProcessingStatus,
    PageInfo, PageType, OCRResult, ManualCorrection
)
from ..exceptions import ProcessingError, ValidationError
from .file_service import FileService
from .ocr_service import OCRService

logger = logging.getLogger(__name__)


class ProcessingService:
    """Main service for coordinating document processing operations."""

    def __init__(self,
                 processing_config: ProcessingConfig,
                 ocr_config: OCRConfig,
                 log_callback: Callable[[str], None]):
        """
        Initialize processing service.

        Args:
            processing_config: Configuration for processing
            ocr_config: Configuration for OCR
            log_callback: Callback for logging messages
        """
        self.processing_config = processing_config
        self.ocr_config = ocr_config
        self.log_callback = log_callback

        # Initialize services
        self.file_service = FileService(processing_config)
        self.ocr_service = OCRService(ocr_config)

        # Processing state
        self._is_processing = False
        self.manual_corrections: Dict[str, int] = {}

    def process_documents(self,
                         get_processing_state: Callable[[], bool],
                         set_processing_state: Callable[[bool], None],
                         ask_manual_correction: Callable[[str, int, int], Optional[Dict]]) -> ProcessingResult:
        """
        Main document processing workflow.

        Args:
            get_processing_state: Callback to check if processing should continue
            set_processing_state: Callback to update processing state
            ask_manual_correction: Callback for manual correction requests

        Returns:
            ProcessingResult with operation results
        """
        result = ProcessingResult(status=ProcessingStatus.PENDING)

        try:
            # Setup phase
            self._setup_processing()
            result.status = ProcessingStatus.PROCESSING

            # Discover and validate input files
            image_files = self.file_service.discover_image_files()
            if not image_files:
                raise ProcessingError("No image files found in input directory")

            # Load processing cache
            processed_cache = self.file_service.load_processed_pages_cache()

            # Process files
            result = self._process_files_parallel(
                image_files, processed_cache, get_processing_state,
                set_processing_state, ask_manual_correction
            )

            result.status = ProcessingStatus.COMPLETED
            self.log_callback("Document processing completed successfully")

        except Exception as e:
            error_msg = f"Processing failed: {e}"
            logger.error(error_msg)
            result.status = ProcessingStatus.FAILED
            result.errors.append(error_msg)
            self.log_callback(f"CRITICAL ERROR: {error_msg}")

        finally:
            set_processing_state(False)

        return result

    def _setup_processing(self) -> None:
        """Setup processing environment."""
        self.log_callback("Setting up processing environment...")

        # Ensure output directory exists
        self.file_service.ensure_output_directory()

        # Validate configurations
        self._validate_processing_config()

        self.log_callback("Processing environment ready")

    def _validate_processing_config(self) -> None:
        """Validate processing configuration."""
        if self.processing_config.max_pages <= 0:
            raise ValidationError("Maximum pages must be positive")
        if self.processing_config.num_processes <= 0:
            raise ValidationError("Number of processes must be positive")

    def _process_files_parallel(self,
                               image_files: List[Path],
                               processed_cache: set,
                               get_processing_state: Callable[[], bool],
                               set_processing_state: Callable[[bool], None],
                               ask_manual_correction: Callable[[str, int, int], Optional[Dict]]) -> ProcessingResult:
        """Process files in parallel using ProcessPoolExecutor."""

        result = ProcessingResult(status=ProcessingStatus.PROCESSING)
        result.total_pages = len(image_files)

        self.log_callback(f"Starting parallel OCR processing with {self.processing_config.num_processes} workers")
        self.log_callback(f"Found {len(image_files)} images to process")

        # Submit OCR tasks
        with ProcessPoolExecutor(max_workers=self.processing_config.num_processes) as executor:
            future_to_file = {}

            for image_file in image_files:
                if not get_processing_state():
                    self.log_callback("Processing cancelled by user")
                    result.status = ProcessingStatus.CANCELLED
                    break

                future = executor.submit(self._process_single_image_ocr, image_file)
                future_to_file[future] = image_file

            # Process results sequentially
            for future in future_to_file:
                if not get_processing_state():
                    break

                try:
                    image_file = future_to_file[future]
                    ocr_result = future.result()

                    # Process the OCR result
                    page_info = self._process_ocr_result(
                        ocr_result, result.last_processed_page or 0,
                        ask_manual_correction
                    )

                    if page_info:
                        result.processed_pages.append(page_info)

                        # Save page if not already processed
                        if not self.file_service.is_page_already_processed(page_info, processed_cache):
                            try:
                                output_path = self.file_service.save_page_as_pdf(
                                    page_info, ocr_result.processed_image_bytes
                                )
                                page_info.is_processed = True

                                # Update cache and result tracking
                                if page_info.page_number is not None:
                                    processed_cache.add(page_info.page_number)
                                    result.last_processed_page = max(
                                        result.last_processed_page or 0,
                                        page_info.page_number
                                    )

                            except Exception as e:
                                error_msg = f"Failed to save {page_info.filename}: {e}"
                                result.errors.append(error_msg)
                                self.log_callback(f"ERROR: {error_msg}")

                except Exception as e:
                    error_msg = f"Failed to process future result: {e}"
                    result.errors.append(error_msg)
                    logger.error(error_msg)

        return result

    def _process_single_image_ocr(self, image_file: Path) -> OCRResult:
        """Process a single image through OCR (for parallel execution)."""
        return self.ocr_service.process_image(image_file)

    def _process_ocr_result(self,
                           ocr_result: OCRResult,
                           last_page_number: int,
                           ask_manual_correction: Callable[[str, int, int], Optional[Dict]]) -> Optional[PageInfo]:
        """Process OCR result and create PageInfo."""

        # Determine page type
        page_type = self.ocr_service.determine_page_type(
            ocr_result, last_page_number, self.processing_config.max_pages
        )

        # Handle page number assignment
        page_number = ocr_result.page_number

        # Handle special cases
        if page_type == PageType.CLOSING_TERM:
            page_number = self.processing_config.max_pages + 1
        elif page_type == PageType.BACK_PAGE:
            page_number = last_page_number
        elif page_type == PageType.ERROR and not ocr_result.has_error:
            # Try manual correction for OCR failures
            correction = self._request_manual_correction(
                ocr_result, last_page_number, ask_manual_correction
            )
            if correction and correction.page_number is not None:
                page_number = correction.page_number
                page_type = PageType.REGULAR

        # Create page info
        page_info = PageInfo(
            filename=ocr_result.filename,
            page_number=page_number,
            page_type=page_type,
            ocr_text=ocr_result.full_text,
            confidence_score=ocr_result.confidence_score
        )

        # Log processing result
        self._log_page_processing(page_info)

        return page_info

    def _request_manual_correction(self,
                                  ocr_result: OCRResult,
                                  last_page_number: int,
                                  ask_manual_correction: Callable[[str, int, int], Optional[Dict]]) -> Optional[ManualCorrection]:
        """Request manual correction for failed OCR."""

        self.log_callback(f"OCR failed for {ocr_result.filename} - requesting manual correction")

        try:
            correction_data = ask_manual_correction(
                ocr_result.filename,
                last_page_number,
                self.processing_config.max_pages
            )

            if correction_data and correction_data.get("action") == "continue":
                page_number = correction_data.get("folha")
                if page_number is not None:
                    # Store correction for future use
                    self.manual_corrections[ocr_result.filename] = page_number

                    correction = ManualCorrection(
                        filename=ocr_result.filename,
                        suggested_page=last_page_number + 1,
                        user_correction=page_number,
                        action="confirm"
                    )

                    self.log_callback(f"Manual correction applied: page {page_number}")
                    return correction

        except Exception as e:
            self.log_callback(f"Manual correction failed: {e}")

        return None

    def _log_page_processing(self, page_info: PageInfo) -> None:
        """Log page processing results."""
        if page_info.page_type == PageType.ERROR:
            self.log_callback(f"ERROR: Failed to process {page_info.filename}")
        elif page_info.page_number is not None:
            type_str = "regular"
            if page_info.page_type == PageType.OPENING_TERM:
                type_str = "opening term"
            elif page_info.page_type == PageType.CLOSING_TERM:
                type_str = "closing term"
            elif page_info.page_type == PageType.BACK_PAGE:
                type_str = "back page"

            self.log_callback(f"Processed {page_info.filename} -> {type_str} page {page_info.page_number}")
        else:
            self.log_callback(f"Skipped {page_info.filename} (no page number detected)")
