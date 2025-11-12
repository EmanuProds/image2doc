"""
Modern logs page with syntax highlighting and filtering.
Uses Gtk.TextView with proper styling and search capabilities.
"""
import logging
from typing import Optional
from datetime import datetime

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Pango, GLib, GObject

logger = logging.getLogger(__name__)


class LogsPage(Adw.PreferencesPage):
    """
    Modern logs page with advanced features.

    Features:
    - Syntax highlighting for different log levels
    - Search and filter capabilities
    - Auto-scroll to bottom
    - Export functionality
    - Performance optimized for large logs
    """

    def __init__(self):
        super().__init__()

        self.set_title("Processing Logs")
        self.set_icon_name("text-x-log-symbolic")

        # Initialize state
        self._auto_scroll = True
        self._log_buffer: list[str] = []
        self._max_lines = 10000  # Limit to prevent memory issues

        # Setup UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the logs UI."""
        # Main group
        logs_group = Adw.PreferencesGroup.new()
        logs_group.set_title("Processing Logs")
        logs_group.set_description("Real-time processing status and error messages")

        # Toolbar
        toolbar_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        toolbar_box.set_margin_bottom(12)

        # Auto-scroll toggle
        self.auto_scroll_button = Gtk.ToggleButton.new()
        self.auto_scroll_button.set_label("Auto-scroll")
        self.auto_scroll_button.set_active(True)
        self.auto_scroll_button.set_tooltip_text("Automatically scroll to latest logs")
        self.auto_scroll_button.connect("toggled", self._on_auto_scroll_toggled)

        # Clear button
        clear_button = Gtk.Button.new_from_icon_name("edit-clear-all-symbolic")
        clear_button.set_tooltip_text("Clear all logs")
        clear_button.connect("clicked", self._on_clear_clicked)

        # Export button
        export_button = Gtk.Button.new_from_icon_name("document-save-symbolic")
        export_button.set_tooltip_text("Export logs to file")
        export_button.connect("clicked", self._on_export_clicked)

        # Search entry
        self.search_entry = Gtk.SearchEntry.new()
        self.search_entry.set_placeholder_text("Search logs...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.set_hexpand(True)

        toolbar_box.append(self.auto_scroll_button)
        toolbar_box.append(clear_button)
        toolbar_box.append(export_button)
        toolbar_box.append(self.search_entry)

        # Scrolled window for logs
        self.scrolled_window = Gtk.ScrolledWindow.new()
        self.scrolled_window.set_vexpand(True)
        self.scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Text view setup
        self._setup_text_view()

        self.scrolled_window.set_child(self.text_view)

        # Status bar
        self.status_label = Gtk.Label.new("Ready")
        self.status_label.add_css_class("caption")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_margin_top(6)

        # Main container
        main_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        main_box.append(toolbar_box)
        main_box.append(self.scrolled_window)
        main_box.append(self.status_label)

        logs_group.set_header_suffix(main_box)
        self.add(logs_group)

    def _setup_text_view(self) -> None:
        """Setup the text view with proper styling."""
        # Create text buffer with tags for syntax highlighting
        self.text_buffer = Gtk.TextBuffer.new()

        # Create text tags for different log levels
        self._create_text_tags()

        # Create text view
        self.text_view = Gtk.TextView.new_with_buffer(self.text_buffer)
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_monospace(True)

        # Connect scroll events
        vadjustment = self.scrolled_window.get_vadjustment()
        vadjustment.connect("value-changed", self._on_scroll_changed)

    def _create_text_tags(self) -> None:
        """Create text tags for syntax highlighting."""
        # Info tag (default)
        self.text_buffer.create_tag("info", foreground="foreground")

        # Error tag
        self.text_buffer.create_tag("error", foreground="#e01b24", weight=Pango.Weight.BOLD)

        # Warning tag
        self.text_buffer.create_tag("warning", foreground="#ff7800", weight=Pango.Weight.BOLD)

        # Success tag
        self.text_buffer.create_tag("success", foreground="#33d17a", weight=Pango.Weight.BOLD)

        # Timestamp tag
        self.text_buffer.create_tag("timestamp", foreground="gray", scale=0.9)

        # Search highlight tag
        self.text_buffer.create_tag("search-highlight",
                                   background="#3584e4",
                                   foreground="white")

    def _on_auto_scroll_toggled(self, button: Gtk.ToggleButton) -> None:
        """Handle auto-scroll toggle."""
        self._auto_scroll = button.get_active()
        if self._auto_scroll:
            self._scroll_to_bottom()

    def _on_clear_clicked(self, button: Gtk.Button) -> None:
        """Handle clear logs button."""
        def on_response(dialog, response):
            if response == "clear":
                self.clear_logs()
            dialog.destroy()

        # Confirmation dialog
        dialog = Adw.MessageDialog.new(
            self.get_root(),
            "Clear Logs",
            "Are you sure you want to clear all logs? This action cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear Logs")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        dialog.connect("response", on_response)
        dialog.present()

    def _on_export_clicked(self, button: Gtk.Button) -> None:
        """Handle export logs button."""
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Export Logs")
        dialog.set_initial_name(f"image2doc_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

        def on_save(dialog, result):
            try:
                file = dialog.save_finish(result)
                self._export_logs_to_file(file.get_path())
            except Exception as e:
                logger.error(f"Failed to export logs: {e}")

        dialog.save(self.get_root(), None, on_save)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text change."""
        search_text = entry.get_text().lower()
        if search_text:
            self._highlight_search_results(search_text)
        else:
            self._clear_search_highlights()

    def _on_scroll_changed(self, adjustment) -> None:
        """Handle scroll position changes."""
        # Check if user scrolled to bottom
        if self._auto_scroll:
            upper = adjustment.get_upper()
            page_size = adjustment.get_page_size()
            value = adjustment.get_value()

            # If user scrolled up, disable auto-scroll
            if upper - page_size - value > 10:  # Small threshold
                self.auto_scroll_button.set_active(False)

    def _highlight_search_results(self, search_text: str) -> None:
        """Highlight search results in the text buffer."""
        self._clear_search_highlights()

        # Get text content
        start_iter = self.text_buffer.get_start_iter()
        end_iter = self.text_buffer.get_end_iter()
        text = self.text_buffer.get_text(start_iter, end_iter, False)

        # Find all occurrences
        search_start = 0
        while True:
            pos = text.lower().find(search_text, search_start)
            if pos == -1:
                break

            # Create iters for the match
            match_start = self.text_buffer.get_iter_at_offset(pos)
            match_end = self.text_buffer.get_iter_at_offset(pos + len(search_text))

            # Apply highlight tag
            self.text_buffer.apply_tag_by_name("search-highlight", match_start, match_end)

            search_start = pos + len(search_text)

    def _clear_search_highlights(self) -> None:
        """Clear all search highlights."""
        start_iter = self.text_buffer.get_start_iter()
        end_iter = self.text_buffer.get_end_iter()
        self.text_buffer.remove_tag_by_name("search-highlight", start_iter, end_iter)

    def _export_logs_to_file(self, file_path: str) -> None:
        """Export logs to a file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for line in self._log_buffer:
                    f.write(line + '\n')

            # Show success toast
            toast = Adw.Toast.new(f"Logs exported to {file_path}")
            toast.set_timeout(3)

            # Find toast overlay in parent
            root = self.get_root()
            if hasattr(root, 'toast_overlay'):
                root.toast_overlay.add_toast(toast)

        except Exception as e:
            logger.error(f"Failed to export logs: {e}")
            # Show error toast
            toast = Adw.Toast.new("Failed to export logs")
            toast.set_timeout(3)
            toast.add_css_class("error")

            root = self.get_root()
            if hasattr(root, 'toast_overlay'):
                root.toast_overlay.add_toast(toast)

    def _scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the text view."""
        def scroll():
            vadjustment = self.scrolled_window.get_vadjustment()
            vadjustment.set_value(vadjustment.get_upper() - vadjustment.get_page_size())
            return False

        GLib.idle_add(scroll)

    def log(self, message: str, is_error: bool = False) -> None:
        """
        Add a log message to the buffer.

        Args:
            message: The message to log
            is_error: Whether this is an error message
        """
        # Add to buffer
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        full_message = f"{timestamp} {message}"

        self._log_buffer.append(full_message)

        # Limit buffer size
        if len(self._log_buffer) > self._max_lines:
            self._log_buffer = self._log_buffer[-self._max_lines:]

        # Update UI in main thread
        GLib.idle_add(self._append_log_to_ui, full_message, is_error)

    def _append_log_to_ui(self, message: str, is_error: bool) -> None:
        """Append log message to UI (called in main thread)."""
        # Determine tag based on content
        tag_name = "error" if is_error else "info"

        # Special highlighting for different message types
        lower_message = message.lower()
        if "error" in lower_message or "failed" in lower_message:
            tag_name = "error"
        elif "warning" in lower_message or "aviso" in lower_message:
            tag_name = "warning"
        elif "success" in lower_message or "completed" in lower_message:
            tag_name = "success"

        # Insert text
        end_iter = self.text_buffer.get_end_iter()
        self.text_buffer.insert(end_iter, message + "\n")

        # Apply tag to the inserted text
        start_iter = self.text_buffer.get_iter_at_offset(end_iter.get_offset() - len(message) - 1)
        self.text_buffer.apply_tag_by_name(tag_name, start_iter, end_iter)

        # Update status
        self._update_status()

        # Auto-scroll if enabled
        if self._auto_scroll:
            self._scroll_to_bottom()

    def _update_status(self) -> None:
        """Update the status label."""
        total_lines = len(self._log_buffer)
        error_count = sum(1 for line in self._log_buffer if "[error]" in line.lower() or "error" in line.lower())

        if error_count > 0:
            self.status_label.set_text(f"{total_lines} lines ({error_count} errors)")
            self.status_label.add_css_class("error")
            self.status_label.remove_css_class("success")
        else:
            self.status_label.set_text(f"{total_lines} lines")
            self.status_label.add_css_class("success")
            self.status_label.remove_css_class("error")

    def clear_logs(self) -> None:
        """Clear all logs."""
        self._log_buffer.clear()
        self.text_buffer.set_text("")
        self._update_status()
        logger.info("Logs cleared")

    def get_log_content(self) -> str:
        """Get all log content as a string."""
        return "\n".join(self._log_buffer)

    def search_logs(self, query: str) -> list[tuple[int, str]]:
        """
        Search logs for a query.

        Returns:
            List of (line_number, line_content) tuples
        """
        results = []
        for i, line in enumerate(self._log_buffer):
            if query.lower() in line.lower():
                results.append((i + 1, line))
        return results
