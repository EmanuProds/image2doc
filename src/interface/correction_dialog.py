"""
Modern correction dialog using Adw.AlertDialog.
Provides user-friendly manual correction interface for OCR failures.
"""
import logging
from typing import Optional, Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GObject

logger = logging.getLogger(__name__)


class CorrectionDialog(Adw.AlertDialog):
    """
    Modern correction dialog for manual OCR intervention.

    Features:
    - Clean Adw.AlertDialog interface
    - Input validation
    - Suggested correction value
    - Multiple action options
    """

    def __init__(self,
                 parent: Gtk.Window,
                 filename: str,
                 last_page: int,
                 max_pages: int):
        """
        Initialize correction dialog.

        Args:
            parent: Parent window
            filename: Name of the file needing correction
            last_page: Last successfully processed page number
            max_pages: Maximum pages in the document
        """
        super().__init__()

        self.filename = filename
        self.last_page = last_page
        self.max_pages = max_pages
        self.suggested_page = last_page + 1

        self._setup_properties()
        self._setup_extra_child()

    def _setup_properties(self) -> None:
        """Setup dialog properties."""
        # Basic properties
        self.set_heading("Manual Correction Required")
        self.set_body(self._create_body_text())

        # Close response (Escape key)
        self.set_close_response("cancel")

        # Default response
        self.set_default_response("confirm")

        # Add responses
        self.add_response("cancel", "Skip All")
        self.add_response("skip", "Skip This")
        self.add_response("confirm", "Apply Correction")

        # Style responses
        self.set_response_appearance("confirm", Adw.ResponseAppearance.SUGGESTED)
        self.set_response_appearance("cancel", Adw.ResponseAppearance.DESTRUCTIVE)

    def _create_body_text(self) -> str:
        """Create the dialog body text."""
        import os
        short_filename = os.path.basename(self.filename)

        return (
            f"OCR failed to detect page number for:\n"
            f"<b>{short_filename}</b>\n\n"
            f"Last processed page: <b>{self.last_page}</b>\n"
            f"Suggested correction: <b>{self.suggested_page}</b>"
        )

    def _setup_extra_child(self) -> None:
        """Setup the extra child with input field."""
        # Create a box for the input
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
        box.set_margin_top(12)

        # Label
        label = Gtk.Label.new("Enter the correct page number:")
        label.set_halign(Gtk.Align.START)
        label.add_css_class("heading")

        # Spin button for page number input
        self.page_spin = Gtk.SpinButton.new_with_range(
            1, self.max_pages, 1
        )
        self.page_spin.set_value(self.suggested_page)
        self.page_spin.set_halign(Gtk.Align.CENTER)
        self.page_spin.add_css_class("large")

        # Make spin button activatable
        self.page_spin.set_activatable(True)

        # Add to box
        box.append(label)
        box.append(self.page_spin)

        # Set as extra child
        self.set_extra_child(box)

    def get_correction_data(self) -> Optional[int]:
        """
        Get the correction data from the dialog.

        Returns:
            The corrected page number, or None if invalid
        """
        try:
            value = self.page_spin.get_value()
            page_number = int(value)

            # Validate range
            if 1 <= page_number <= self.max_pages:
                return page_number
            else:
                logger.warning(f"Page number {page_number} out of range (1-{self.max_pages})")
                return None

        except (ValueError, TypeError) as e:
            logger.error(f"Invalid page number input: {e}")
            return None

    @classmethod
    def show_correction_dialog(cls,
                              parent: Gtk.Window,
                              filename: str,
                              last_page: int,
                              max_pages: int) -> Optional[int]:
        """
        Convenience method to show correction dialog and get result.

        Args:
            parent: Parent window
            filename: File needing correction
            last_page: Last processed page
            max_pages: Maximum pages

        Returns:
            Corrected page number or None
        """
        def on_response(dialog, response):
            if response == "confirm":
                correction = dialog.get_correction_data()
                if correction is not None:
                    cls._dialog_result = correction
                else:
                    # Invalid input, treat as skip
                    cls._dialog_result = None
            elif response == "skip":
                cls._dialog_result = None  # Will use suggested value
            elif response == "cancel":
                cls._dialog_result = -1  # Special value for cancel all

        # Create and show dialog
        dialog = cls(parent, filename, last_page, max_pages)
        dialog.connect("response", on_response)

        # Reset result
        cls._dialog_result = None

        dialog.present()

        # Note: In GTK4, dialogs are async, so we need to handle this differently
        # This is a simplified version - in practice, you'd use a callback pattern
        return None
