"""
Image2PDF - Document Processing Application

A modern GTK4 application for converting document images to organized PDFs
using OCR technology with intelligent page detection and manual correction support.
"""

from . import config
from . import models
from . import exceptions
from . import core

# Public API
__version__ = config.APP_VERSION
__all__ = [
    'config',
    'models',
    'exceptions',
    'core',
]
