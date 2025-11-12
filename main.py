"""
Image2DOC - Modern Document Processing Application

Main entry point for the GTK4 application that converts document images
to organized PDFs using OCR technology.
"""
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check if all required dependencies are available."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        logger.info("Tesseract OCR found")
    except ImportError:
        logger.error("pytesseract not installed. Run: pip install pytesseract")
        return False
    except pytesseract.TesseractNotFoundError:
        logger.error(
            "Tesseract not found. Install from: https://github.com/tesseract-ocr/tesseract"
        )
        return False

    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk, Adw, Gio
        logger.info("GTK4 and Libadwaita found")
    except (ImportError, ValueError) as e:
        logger.error(f"GTK4/Libadwaita not available: {e}")
        return False

    return True


def main():
    """Main application entry point."""
    logger.info("Starting Image2DOC application")

    # Check dependencies
    if not check_dependencies():
        logger.error("Dependency check failed. Exiting.")
        sys.exit(1)

    # Import and run application
    try:
        from gi.repository import Adw, Gio
        from src.interface.main import MainWindow

        app = Adw.Application.new(
            application_id="com.jtp.image2doc",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

        def on_activate(app):
            """Create and show the main window."""
            window = MainWindow(app)
            window.present()

        app.connect("activate", on_activate)

        # Run the application
        exit_code = app.run(sys.argv)
        logger.info("Application exited with code: %d", exit_code)
        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
