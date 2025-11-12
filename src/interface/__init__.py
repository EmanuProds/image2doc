"""
Modern GTK4/Libadwaita interface for Image2DOC application.
Provides a clean, responsive, and accessible user interface.
"""

from .main import MainWindow
from .home import HomePage
from .settings import SettingsPage
from .logs import LogsPage
from .about import AboutDialog
from .correction import CorrectionDialog

__all__ = [
    'MainWindow',
    'HomePage',
    'SettingsPage',
    'LogsPage',
    'AboutDialog',
    'CorrectionDialog',
]
