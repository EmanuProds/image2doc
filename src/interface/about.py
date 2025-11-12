"""
Modern about dialog using Adw.AboutWindow.
Provides comprehensive application information with proper styling.
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from .. import config


class AboutDialog:
    """
    Modern about dialog with comprehensive application information.

    Features:
    - Application metadata
    - Developer information
    - Links and resources
    - Proper GNOME HIG compliance
    """

    @staticmethod
    def show(transient_for: Gtk.Window = None) -> None:
        """
        Show the about dialog.

        Args:
            transient_for: Parent window for the dialog
        """
        dialog = Adw.AboutWindow.new()

        if transient_for:
            dialog.set_transient_for(transient_for)

        # Application information
        dialog.set_application_name("Image2DOC")
        dialog.set_application_icon("image2doc")  # Will fallback to generic icon
        dialog.set_version(config.APP_VERSION)
        dialog.set_comments("Convert document images to organized PDFs with OCR technology")

        # Developer information
        dialog.set_developer_name("Emanuel Pereira")
        dialog.set_developers(["Emanuel Pereira"])

        # Copyright and license
        dialog.set_copyright("© 2024 Emanuel Pereira")
        dialog.set_license_type(Gtk.License.MIT_X11)

        # Website and issue tracker
        dialog.set_website("https://github.com/EmanuProds/ncx-book-organizer")
        dialog.set_issue_url("https://github.com/EmanuProds/ncx-book-organizer/issues")

        # Release notes (optional)
        dialog.set_release_notes("""
<b>Version 1.0.0</b>

🚀 Major Refactoring
• Complete architecture modernization
• Service-oriented design pattern
• Modern Python type hints and dataclasses
• Enhanced error handling and logging

✨ New Features
• Responsive GTK4/Libadwaita interface
• Advanced settings with validation
• Real-time log viewer with search
• Toast notifications and status feedback

🐛 Improvements
• Better OCR accuracy and performance
• Improved parallel processing
• Enhanced user experience
• Comprehensive documentation
        """)

        # Credits
        dialog.add_credit_section(
            "Technologies",
            [
                "Python",
                "GTK4",
                "Libadwaita",
                "Tesseract OCR",
                "Pillow (PIL)"
            ]
        )

        dialog.add_credit_section(
            "Resources",
            [
                "GNOME Human Interface Guidelines",
                "GTK Documentation",
                "Tesseract OCR Project"
            ]
        )

        dialog.present()
