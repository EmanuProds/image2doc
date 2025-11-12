"""
Modern settings page using Adw.PreferencesWindow.
Provides clean configuration interface with proper validation.
"""
import logging
from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GObject

from ..models import OCRConfig, ProcessingConfig

logger = logging.getLogger(__name__)


class SettingsPage(Adw.PreferencesPage):
    """
    Modern settings page for application configuration.

    Features:
    - Clean preferences groups
    - Input validation
    - Real-time feedback
    - Proper state management
    """

    def __init__(self):
        super().__init__()

        self.set_title("Settings")
        self.set_icon_name("preferences-system-symbolic")

        # Initialize configurations
        self.processing_config = ProcessingConfig()
        self.ocr_config = OCRConfig()

        # Setup UI
        self._setup_ui()

        # Load current values
        self._load_current_values()

    def _setup_ui(self) -> None:
        """Setup the preferences UI."""
        # Processing settings group
        processing_group = Adw.PreferencesGroup.new()
        processing_group.set_title("Processing")
        processing_group.set_description("Configure document processing parameters")

        # Max pages row
        self.max_pages_row = Adw.SpinRow.new_with_range(1, 10000, 10)
        self.max_pages_row.set_title("Maximum Pages")
        self.max_pages_row.set_subtitle("Maximum number of pages to process")
        self.max_pages_row.connect("changed", self._on_max_pages_changed)

        # Num processes row
        self.num_processes_row = Adw.SpinRow.new_with_range(1, 32, 1)
        self.num_processes_row.set_title("Parallel Processes")
        self.num_processes_row.set_subtitle("Number of CPU cores to use (0 = auto-detect)")
        self.num_processes_row.connect("changed", self._on_num_processes_changed)

        processing_group.add(self.max_pages_row)
        processing_group.add(self.num_processes_row)

        # OCR settings group
        ocr_group = Adw.PreferencesGroup.new()
        ocr_group.set_title("OCR Configuration")
        ocr_group.set_description("Configure optical character recognition settings")

        # Language row
        self.language_row = Adw.ComboRow.new()
        self.language_row.set_title("OCR Language")
        self.language_row.set_subtitle("Language for text recognition")

        # Setup language model
        language_model = Gtk.StringList.new()
        languages = ["por", "eng", "spa", "fra", "deu"]
        for lang in languages:
            language_model.append(lang)

        self.language_row.set_model(language_model)
        self.language_row.connect("notify::selected", self._on_language_changed)

        # PSM mode row
        self.psm_row = Adw.SpinRow.new_with_range(0, 13, 1)
        self.psm_row.set_title("PSM Mode")
        self.psm_row.set_subtitle("Page segmentation mode for OCR")
        self.psm_row.connect("changed", self._on_psm_changed)

        # Min chars row
        self.min_chars_row = Adw.SpinRow.new_with_range(0, 1000, 10)
        self.min_chars_row.set_title("Minimum Characters")
        self.min_chars_row.set_subtitle("Minimum characters to consider as front page")
        self.min_chars_row.connect("changed", self._on_min_chars_changed)

        ocr_group.add(self.language_row)
        ocr_group.add(self.psm_row)
        ocr_group.add(self.min_chars_row)

        # Advanced settings group
        advanced_group = Adw.PreferencesGroup.new()
        advanced_group.set_title("Advanced")
        advanced_group.set_description("Advanced configuration options")

        # ROI configuration (expandable)
        self.roi_expander = Adw.ExpanderRow.new()
        self.roi_expander.set_title("OCR Region of Interest")
        self.roi_expander.set_subtitle("Configure the area where page numbers are detected")

        # ROI spin rows
        self.roi_x_min = Adw.SpinRow.new_with_range(0, 1000, 10)
        self.roi_x_min.set_title("X Minimum")
        self.roi_x_min.connect("changed", self._on_roi_changed)

        self.roi_y_min = Adw.SpinRow.new_with_range(0, 1000, 10)
        self.roi_y_min.set_title("Y Minimum")
        self.roi_y_min.connect("changed", self._on_roi_changed)

        self.roi_x_max = Adw.SpinRow.new_with_range(0, 1000, 10)
        self.roi_x_max.set_title("X Maximum")
        self.roi_x_max.connect("changed", self._on_roi_changed)

        self.roi_y_max = Adw.SpinRow.new_with_range(0, 1000, 10)
        self.roi_y_max.set_title("Y Maximum")
        self.roi_y_max.connect("changed", self._on_roi_changed)

        self.roi_expander.add_row(self.roi_x_min)
        self.roi_expander.add_row(self.roi_y_min)
        self.roi_expander.add_row(self.roi_x_max)
        self.roi_expander.add_row(self.roi_y_max)

        advanced_group.add(self.roi_expander)

        # Reset button
        reset_row = Adw.ActionRow.new()
        reset_row.set_title("Reset to Defaults")
        reset_row.set_subtitle("Restore all settings to their default values")

        reset_button = Gtk.Button.new_with_label("Reset")
        reset_button.add_css_class("destructive-action")
        reset_button.connect("clicked", self._on_reset_clicked)
        reset_row.add_suffix(reset_button)

        advanced_group.add(reset_row)

        # Add groups to page
        self.add(processing_group)
        self.add(ocr_group)
        self.add(advanced_group)

    def _load_current_values(self) -> None:
        """Load current configuration values into UI."""
        # Processing config
        self.max_pages_row.set_value(self.processing_config.max_pages)
        self.num_processes_row.set_value(self.processing_config.num_processes)

        # OCR config
        # Set language selection
        language_model = self.language_row.get_model()
        for i in range(language_model.get_n_items()):
            if language_model.get_string(i) == self.ocr_config.language:
                self.language_row.set_selected(i)
                break

        self.psm_row.set_value(self.ocr_config.psm_mode)
        self.min_chars_row.set_value(self.ocr_config.min_chars_for_front_page)

        # ROI values
        self.roi_x_min.set_value(self.ocr_config.roi[0])
        self.roi_y_min.set_value(self.ocr_config.roi[1])
        self.roi_x_max.set_value(self.ocr_config.roi[2])
        self.roi_y_max.set_value(self.ocr_config.roi[3])

    def _on_max_pages_changed(self, spin_row: Adw.SpinRow) -> None:
        """Handle max pages change."""
        self.processing_config.max_pages = int(spin_row.get_value())
        logger.debug(f"Max pages changed to: {self.processing_config.max_pages}")

    def _on_num_processes_changed(self, spin_row: Adw.SpinRow) -> None:
        """Handle num processes change."""
        self.processing_config.num_processes = int(spin_row.get_value())
        logger.debug(f"Num processes changed to: {self.processing_config.num_processes}")

    def _on_language_changed(self, combo_row: Adw.ComboRow, pspec) -> None:
        """Handle language change."""
        selected = combo_row.get_selected()
        if selected >= 0:
            model = combo_row.get_model()
            self.ocr_config.language = model.get_string(selected)
            logger.debug(f"OCR language changed to: {self.ocr_config.language}")

    def _on_psm_changed(self, spin_row: Adw.SpinRow) -> None:
        """Handle PSM mode change."""
        self.ocr_config.psm_mode = int(spin_row.get_value())
        logger.debug(f"PSM mode changed to: {self.ocr_config.psm_mode}")

    def _on_min_chars_changed(self, spin_row: Adw.SpinRow) -> None:
        """Handle min chars change."""
        self.ocr_config.min_chars_for_front_page = int(spin_row.get_value())
        logger.debug(f"Min chars changed to: {self.ocr_config.min_chars_for_front_page}")

    def _on_roi_changed(self, spin_row: Adw.SpinRow) -> None:
        """Handle ROI change."""
        roi = (
            int(self.roi_x_min.get_value()),
            int(self.roi_y_min.get_value()),
            int(self.roi_x_max.get_value()),
            int(self.roi_y_max.get_value())
        )
        self.ocr_config.roi = roi
        logger.debug(f"ROI changed to: {roi}")

    def _on_reset_clicked(self, button: Gtk.Button) -> None:
        """Handle reset to defaults."""
        def on_response(dialog, response):
            if response == "reset":
                # Reset to default configurations
                self.processing_config = ProcessingConfig()
                self.ocr_config = OCRConfig()

                # Reload UI values
                self._load_current_values()

                logger.info("Settings reset to defaults")

            dialog.destroy()

        # Confirmation dialog
        dialog = Adw.MessageDialog.new(
            self.get_root(),
            "Reset Settings",
            "Are you sure you want to reset all settings to their default values?"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("reset", "Reset")
        dialog.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        dialog.connect("response", on_response)
        dialog.present()

    def get_processing_config(self) -> ProcessingConfig:
        """Get current processing configuration."""
        return self.processing_config

    def get_ocr_config(self) -> OCRConfig:
        """Get current OCR configuration."""
        return self.ocr_config

    def set_processing_state(self, is_processing: bool) -> None:
        """Set processing state (disable/enable controls during processing)."""
        # Disable configuration changes during processing
        sensitivity = not is_processing
        self.max_pages_row.set_sensitive(sensitivity)
        self.num_processes_row.set_sensitive(sensitivity)
        self.language_row.set_sensitive(sensitivity)
        self.psm_row.set_sensitive(sensitivity)
        self.min_chars_row.set_sensitive(sensitivity)
        self.roi_expander.set_sensitive(sensitivity)

        # Update descriptions based on state
        if is_processing:
            self.set_description("⚠️ Settings cannot be changed during processing")
        else:
            self.set_description("Configure application settings")

    def validate_settings(self) -> list[str]:
        """Validate current settings and return list of errors."""
        errors = []

        # Validate processing config
        if self.processing_config.max_pages < 1:
            errors.append("Maximum pages must be at least 1")

        if self.processing_config.num_processes < 1:
            errors.append("Number of processes must be at least 1")

        # Validate OCR config
        roi = self.ocr_config.roi
        if roi[0] >= roi[2] or roi[1] >= roi[3]:
            errors.append("Invalid ROI: minimum values must be less than maximum values")

        if not self.ocr_config.language:
            errors.append("OCR language must be specified")

        return errors
