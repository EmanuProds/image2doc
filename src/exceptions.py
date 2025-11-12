"""
Custom exceptions for the Image2DOC application.
Provides specific error types for better error handling and debugging.
"""


class Image2DOCError(Exception):
    """Base exception for Image2DOC application errors."""
    pass


class ConfigurationError(Image2DOCError):
    """Raised when there's a configuration-related error."""
    pass


class FileOperationError(Image2DOCError):
    """Raised when file operations fail."""
    pass


class OCRError(Image2DOCError):
    """Raised when OCR processing fails."""
    pass


class ProcessingError(Image2DOCError):
    """Raised when document processing fails."""
    pass


class ValidationError(Image2DOCError):
    """Raised when input validation fails."""
    pass


class ThreadingError(Image2DOCError):
    """Raised when threading operations fail."""
    pass
