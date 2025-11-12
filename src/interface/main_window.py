"""
Modern main window with navigation and responsive design.
Uses Adw.NavigationView for clean tab-based navigation.
"""
import logging
from typing import Optional, Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from .home_page import HomePage
from .settings_page import SettingsPage
from .logs_page import LogsPage
from .about_dialog import AboutDialog

logger = logging.getLogger(__name__)


class MainWindow(Adw.ApplicationWindow):
    """
    Modern main application window with navigation view.

    Features:
    - Clean navigation with Adw.NavigationView
    - Responsive design with Adw.Clamp
    - Toast notifications for user feedback
    - Proper window state management
    """

    def __init__(self, application: Adw.Application):
        super().__init__(application=application)

        self.set_title("Image2PDF")
        self.set_default_size(900, 700)

        # Initialize state
        self._is_processing = False
        self.toast_overlay = Adw.ToastOverlay.new()

        # Setup UI
        self._setup_ui()
        self._setup_actions()
        self._setup_style()

        # Set content
        self.set_content(self.toast_overlay)

    def _setup_ui(self) -> None:
        """Setup the main UI structure."""
        # Create main box with header and content
        main_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        # Create stack for pages first
        self.stack = Gtk.Stack.new()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # Create pages
        self.home_page = HomePage()
        self.settings_page = SettingsPage()
        self.logs_page = LogsPage()

        # Connect page signals
        self.home_page.connect("processing-started", self._on_processing_started)
        self.home_page.connect("processing-finished", self._on_processing_finished)
        self.home_page.connect("show-toast", self._on_show_toast)

        # Add pages to stack
        self.stack.add_titled(self.home_page, "home", "Home")
        self.stack.add_titled(self.settings_page, "settings", "Settings")
        self.stack.add_titled(self.logs_page, "logs", "Logs")

        # Create header bar after stack is created
        self.header_bar = Adw.HeaderBar.new()
        self._setup_header_bar()
        main_box.append(self.header_bar)

        main_box.append(self.stack)

        # Add main box to toast overlay
        self.toast_overlay.set_child(main_box)

    def _setup_header_bar(self) -> None:
        """Setup the header bar with navigation and actions."""
        # Create stack switcher for navigation
        self.stack_switcher = Gtk.StackSwitcher.new()
        self.stack_switcher.set_stack(self.stack)
        self.header_bar.set_title_widget(self.stack_switcher)

        # Add about button
        about_button = Gtk.Button.new_from_icon_name("help-about-symbolic")
        about_button.set_tooltip_text("About Image2PDF")
        about_button.connect("clicked", self._on_about_clicked)
        self.header_bar.pack_end(about_button)

    def _setup_actions(self) -> None:
        """Setup window actions."""
        # Keyboard shortcuts
        self.add_action_entries([
            ("show-about", self._on_about_clicked, None),
            ("show-settings", lambda *_: self._navigate_to_page("settings"), None),
            ("show-logs", lambda *_: self._navigate_to_page("logs"), None),
            ("go-home", lambda *_: self._navigate_to_page("home"), None),
        ])

        # Setup accelerators
        app = self.get_application()
        app.set_accels_for_action("win.show-about", ["F1"])
        app.set_accels_for_action("win.show-settings", ["<Ctrl>s"])
        app.set_accels_for_action("win.show-logs", ["<Ctrl>l"])
        app.set_accels_for_action("win.go-home", ["<Ctrl>h"])

    def _setup_style(self) -> None:
        """Setup custom CSS styling."""
        css_provider = Gtk.CssProvider.new()
        css_data = """
        .processing-active {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
        }

        .status-success {
            color: #33d17a;
        }

        .status-error {
            color: #e01b24;
        }

        .status-warning {
            color: #ff7800;
        }
        """
        css_provider.load_from_data(css_data.encode('utf-8'))

        display = self.get_display()
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _navigate_to_page(self, tag: str) -> None:
        """Navigate to a specific page by tag."""
        self.stack.set_visible_child_name(tag)

    def _on_about_clicked(self, *args) -> None:
        """Show about dialog."""
        AboutDialog.show(transient_for=self)

    def _on_processing_started(self, page) -> None:
        """Handle processing start event."""
        self._is_processing = True
        self._update_processing_state()

    def _on_processing_finished(self, page) -> None:
        """Handle processing finish event."""
        self._is_processing = False
        self._update_processing_state()

    def _on_show_toast(self, page, message: str, timeout: int = 3) -> None:
        """Show a toast notification."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)

    def _update_processing_state(self) -> None:
        """Update UI state based on processing status."""
        # Update window title
        if self._is_processing:
            self.set_title("Image2PDF - Processing...")
        else:
            self.set_title("Image2PDF")

        # Update header bar sensitivity
        self.header_bar.set_sensitive(not self._is_processing)

        # Notify pages of state change
        self.home_page.set_processing_state(self._is_processing)
        self.settings_page.set_processing_state(self._is_processing)

    def do_close_request(self) -> bool:
        """Handle window close request."""
        if self._is_processing:
            # Show confirmation dialog
            dialog = Adw.MessageDialog.new(
                self,
                "Processing in Progress",
                "Document processing is currently running. Closing the window will stop the process.\n\nDo you want to close anyway?"
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("close", "Close Anyway")
            dialog.set_response_appearance("close", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_response(dialog, response):
                if response == "close":
                    self.destroy()
                dialog.destroy()

            dialog.connect("response", on_response)
            dialog.present()
            return True  # Don't close yet

        return False  # Allow closing

    # Public API for external access
    def get_home_page(self) -> HomePage:
        """Get the home page instance."""
        return self.home_page

    def get_settings_page(self) -> SettingsPage:
        """Get the settings page instance."""
        return self.settings_page

    def get_logs_page(self) -> LogsPage:
        """Get the logs page instance."""
        return self.logs_page

    def show_error_toast(self, message: str) -> None:
        """Show an error toast notification."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(5)
        toast.add_css_class("status-error")
        self.toast_overlay.add_toast(toast)

    def show_success_toast(self, message: str) -> None:
        """Show a success toast notification."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        toast.add_css_class("status-success")
        self.toast_overlay.add_toast(toast)
