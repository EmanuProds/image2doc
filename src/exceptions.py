"""
Custom exceptions for the Image2PDF application.
Provides specific error types for better error handling and debugging.
"""


class Image2PDFError(Exception):
    """Base exception for Image2PDF application errors."""
    pass


class ConfigurationError(Image2PDFError):
    """Raised when there's a configuration-related error."""
    pass


class FileOperationError(Image2PDFError):
    """Raised when file operations fail."""
    pass


class OCRError(Image2PDFError):
    """Raised when OCR processing fails."""
    pass


class ProcessingError(Image2PDFError):
    """Raised when document processing fails."""
    pass


class ValidationError(Image2PDFError):
    """Raised when input validation fails."""
    pass


class ThreadingError(Image2PDFError):
    """Raised when threading operations fail."""
    pass
