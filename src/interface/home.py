"""
Modern home page with responsive design and clean UI.
Uses Adw.StatusPage, Adw.Clamp, and proper state management.
"""
import logging
from pathlib import Path
from typing import Optional, Callable, Dict

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, GObject

from ..models import ProcessingConfig, OCRConfig
from ..services.processing_service import ProcessingService

logger = logging.getLogger(__name__)


class HomePage(Gtk.Box):
    """
    Modern home page for document processing.

    Features:
    - Clean status page design
    - Responsive layout with Adw.Clamp
    - Visual feedback for all states
    - Proper signal emission for state changes
    """

    __gsignals__ = {
        'processing-started': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'processing-finished': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'show-toast': (GObject.SignalFlags.RUN_FIRST, None, (str, int)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        # Initialize state
        self.input_dir: Optional[Path] = None
        self.output_dir: Optional[Path] = None
        self.processing_service: Optional[ProcessingService] = None
        self._is_processing = False

        # Setup UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the main UI structure."""
        # Main clamp for responsive design
        clamp = Adw.Clamp.new()
        clamp.set_maximum_size(600)
        clamp.set_tightening_threshold(500)

        # Main box
        main_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_valign(Gtk.Align.CENTER)

        # Status page for initial state
        self.status_page = Adw.StatusPage.new()
        self.status_page.set_title("Image2DOC Converter")
        self.status_page.set_description("Convert document images to organized PDFs with OCR")
        self.status_page.set_icon_name("document-open-symbolic")
        self.status_page.set_vexpand(True)

        # Setup button
        setup_button = Gtk.Button.new_with_label("Get Started")
        setup_button.add_css_class("suggested-action")
        setup_button.add_css_class("pill")
        setup_button.connect("clicked", self._on_setup_clicked)
        self.status_page.set_child(setup_button)

        # Processing view (hidden initially)
        self.processing_box = self._create_processing_view()
        self.processing_box.set_visible(False)

        # Add views to main box
        main_box.append(self.status_page)
        main_box.append(self.processing_box)

        clamp.set_child(main_box)
        self.append(clamp)

    def _create_processing_view(self) -> Gtk.Box:
        """Create the processing interface view."""
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 24)

        # Directory selection section
        dir_section = self._create_directory_section()
        box.append(dir_section)

        # Progress section
        progress_section = self._create_progress_section()
        box.append(progress_section)

        # Action buttons
        buttons_section = self._create_buttons_section()
        box.append(buttons_section)

        return box

    def _create_directory_section(self) -> Adw.PreferencesGroup:
        """Create directory selection section."""
        group = Adw.PreferencesGroup.new()
        group.set_title("Document Directories")
        group.set_description("Select input and output directories for processing")

        # Input directory row
        self.input_row = Adw.ActionRow.new()
        self.input_row.set_title("Input Directory")
        self.input_row.set_subtitle("Select folder containing images")
        self.input_row.set_activatable(True)

        input_button = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        input_button.set_valign(Gtk.Align.CENTER)
        input_button.connect("clicked", self._on_select_input_dir)
        self.input_row.add_suffix(input_button)
        self.input_row.set_activatable_widget(input_button)

        # Output directory row
        self.output_row = Adw.ActionRow.new()
        self.output_row.set_title("Output Directory")
        self.output_row.set_subtitle("Select folder for PDF output")
        self.output_row.set_activatable(True)

        output_button = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        output_button.set_valign(Gtk.Align.CENTER)
        output_button.connect("clicked", self._on_select_output_dir)
        self.output_row.add_suffix(output_button)
        self.output_row.set_activatable_widget(output_button)

        group.add(self.input_row)
        group.add(self.output_row)

        return group

    def _create_progress_section(self) -> Adw.PreferencesGroup:
        """Create progress display section."""
        group = Adw.PreferencesGroup.new()
        group.set_title("Processing Status")

        # Progress bar
        self.progress_bar = Gtk.ProgressBar.new()
        self.progress_bar.set_show_text(True)
        self.progress_bar.set_text("Ready")
        self.progress_bar.set_fraction(0.0)

        # Status label
        self.status_label = Gtk.Label.new("Select directories to begin")
        self.status_label.add_css_class("body")
        self.status_label.set_wrap(True)
        self.status_label.set_halign(Gtk.Align.START)

        # Progress box
        progress_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
        progress_box.append(self.progress_bar)
        progress_box.append(self.status_label)

        group.set_header_suffix(progress_box)
        return group

    def _create_buttons_section(self) -> Gtk.Box:
        """Create action buttons section."""
        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 12)
        box.set_halign(Gtk.Align.CENTER)

        # Start/Stop button
        self.action_button = Gtk.Button.new_with_label("Start Processing")
        self.action_button.add_css_class("suggested-action")
        self.action_button.add_css_class("pill")
        self.action_button.connect("clicked", self._on_action_clicked)

        # Settings button
        settings_button = Gtk.Button.new_with_label("Settings")
        settings_button.add_css_class("flat")
        settings_button.connect("clicked", self._on_settings_clicked)

        box.append(settings_button)
        box.append(self.action_button)

        return box

    def _on_setup_clicked(self, button: Gtk.Button) -> None:
        """Handle setup button click."""
        self.status_page.set_visible(False)
        self.processing_box.set_visible(True)

    def _on_select_input_dir(self, button: Gtk.Button) -> None:
        """Handle input directory selection."""
        self._select_directory("input")

    def _on_select_output_dir(self, button: Gtk.Button) -> None:
        """Handle output directory selection."""
        self._select_directory("output")

    def _select_directory(self, dir_type: str) -> None:
        """Select a directory using file dialog."""
        dialog = Gtk.FileDialog.new()
        dialog.set_title(f"Select {dir_type.title()} Directory")
        dialog.set_modal(True)

        def on_select(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
                path = Path(folder.get_path())

                if dir_type == "input":
                    self.input_dir = path
                    self.input_row.set_subtitle(f"📁 {path.name}")
                    self.emit("show-toast", f"Input directory selected: {path.name}", 2)
                else:
                    self.output_dir = path
                    self.output_row.set_subtitle(f"📁 {path.name}")
                    self.emit("show-toast", f"Output directory selected: {path.name}", 2)

                self._update_action_button_state()

            except Exception as e:
                logger.warning(f"Directory selection cancelled: {e}")

        dialog.select_folder(self.get_root(), None, on_select)

    def _on_action_clicked(self, button: Gtk.Button) -> None:
        """Handle start/stop action button."""
        if self._is_processing:
            self._stop_processing()
        else:
            self._start_processing()

    def _on_settings_clicked(self, button: Gtk.Button) -> None:
        """Handle settings button click."""
        # This will be handled by the parent window navigation
        pass

    def _start_processing(self) -> None:
        """Start document processing."""
        if not self._can_start_processing():
            return

        try:
            # Create configuration
            processing_config = ProcessingConfig(
                max_pages=300,  # TODO: Get from settings
                num_processes=4,  # TODO: Get from settings
                input_dir=self.input_dir,
                output_dir=self.output_dir
            )

            ocr_config = OCRConfig()  # TODO: Get from settings

            # Create processing service
            self.processing_service = ProcessingService(
                processing_config, ocr_config, self._log_message
            )

            # Update UI state
            self._is_processing = True
            self.emit("processing-started")

            self.action_button.set_label("Stop Processing")
            self.action_button.remove_css_class("suggested-action")
            self.action_button.add_css_class("destructive-action")

            self.progress_bar.set_text("Initializing...")
            self.status_label.set_text("Starting document processing...")

            # Disable directory selection
            self.input_row.set_sensitive(False)
            self.output_row.set_sensitive(False)

            # Start processing in thread
            GLib.Thread.new("processing", self._run_processing_thread)

        except Exception as e:
            logger.error(f"Failed to start processing: {e}")
            self.emit("show-toast", f"Failed to start processing: {str(e)}", 5)

    def _stop_processing(self) -> None:
        """Stop document processing."""
        self._is_processing = False
        self.status_label.set_text("Stopping processing...")
        self.emit("show-toast", "Stopping processing...", 2)

    def _run_processing_thread(self) -> None:
        """Run processing in a separate thread."""
        def get_processing_state():
            return self._is_processing

        def set_processing_state(is_processing):
            self._is_processing = is_processing

        def ask_correction(filename, last_page, max_pages):
            # TODO: Implement manual correction dialog
            return {"action": "skip", "folha": last_page + 1}

        try:
            result = self.processing_service.process_documents(
                get_processing_state=get_processing_state,
                set_processing_state=set_processing_state,
                ask_manual_correction=ask_correction
            )

            GLib.idle_add(self._on_processing_complete, result)

        except Exception as e:
            GLib.idle_add(self._on_processing_error, str(e))

    def _on_processing_complete(self, result) -> None:
        """Handle processing completion."""
        self._is_processing = False
        self.emit("processing-finished")

        # Update UI
        self.action_button.set_label("Start Processing")
        self.action_button.remove_css_class("destructive-action")
        self.action_button.add_css_class("suggested-action")

        self.progress_bar.set_fraction(1.0)
        self.progress_bar.set_text("Complete")

        self.status_label.set_text(
            f"Processing complete! Processed {result.total_pages} pages."
        )

        # Re-enable directory selection
        self.input_row.set_sensitive(True)
        self.output_row.set_sensitive(True)

        self.emit("show-toast", "Processing completed successfully!", 3)

    def _on_processing_error(self, error: str) -> None:
        """Handle processing error."""
        self._is_processing = False
        self.emit("processing-finished")

        # Update UI
        self.action_button.set_label("Start Processing")
        self.action_button.remove_css_class("destructive-action")
        self.action_button.add_css_class("suggested-action")

        self.progress_bar.set_text("Error")
        self.status_label.set_text(f"Processing failed: {error}")

        # Re-enable directory selection
        self.input_row.set_sensitive(True)
        self.output_row.set_sensitive(True)

        self.emit("show-toast", f"Processing failed: {error}", 5)

    def _can_start_processing(self) -> bool:
        """Check if processing can be started."""
        if not self.input_dir:
            self.emit("show-toast", "Please select an input directory", 3)
            return False

        if not self.output_dir:
            self.emit("show-toast", "Please select an output directory", 3)
            return False

        if self.input_dir == self.output_dir:
            self.emit("show-toast", "Input and output directories must be different", 3)
            return False

        return True

    def _update_action_button_state(self) -> None:
        """Update action button state based on current configuration."""
        can_start = self._can_start_processing()
        self.action_button.set_sensitive(can_start and not self._is_processing)

    def _log_message(self, message: str, is_error: bool = False) -> None:
        """Log a message (callback for processing service)."""
        # Update status label with latest message
        if not is_error:
            GLib.idle_add(self.status_label.set_text, message)

    def set_processing_state(self, is_processing: bool) -> None:
        """Set processing state (called by parent window)."""
        self._is_processing = is_processing
        self._update_action_button_state()

        if is_processing:
            self.action_button.set_label("Stop Processing")
            self.action_button.remove_css_class("suggested-action")
            self.action_button.add_css_class("destructive-action")
        else:
            self.action_button.set_label("Start Processing")
            self.action_button.remove_css_class("destructive-action")
            self.action_button.add_css_class("suggested-action")
