"""
Modern GTK4/Libadwaita interface for Image2PDF application.
Provides a clean, responsive, and accessible user interface.
"""

from .main_window import MainWindow
from .home_page import HomePage
from .settings_page import SettingsPage
from .logs_page import LogsPage
from .about_dialog import AboutDialog
from .correction_dialog import CorrectionDialog

__all__ = [
    'MainWindow',
    'HomePage',
    'SettingsPage',
    'LogsPage',
    'AboutDialog',
    'CorrectionDialog',
]
