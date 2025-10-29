import gi
from typing import Optional, Callable

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Pango

class LogsPage(Gtk.Box): # Alterado de Adw.StatusPage para Gtk.Box
    """
    Página dedicada à visualização em tempo real dos logs de processamento.
    """
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        
        # O Gtk.Box principal da página
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)

        # Título
        title_label = Gtk.Label.new("Logs de Processamento")
        title_label.add_css_class("title-1")
        title_label.set_halign(Gtk.Align.START)
        self.append(title_label)

        # Descrição
        desc_label = Gtk.Label.new("Acompanhe o status e as mensagens de erro do backend.")
        desc_label.add_css_class("body")
        desc_label.set_halign(Gtk.Align.START)
        desc_label.set_margin_bottom(12)
        self.append(desc_label)

        # --- Área de Visualização de Logs ---
        
        # Buffer de texto
        self.text_buffer = Gtk.TextBuffer.new()
        
        # Cria uma tag para mensagens de erro
        self.error_tag = self.text_buffer.create_tag("error", foreground="red", weight=Pango.Weight.BOLD)
        
        # TextView dentro de um ScrolledWindow
        scrolled_window = Gtk.ScrolledWindow.new()
        scrolled_window.set_vexpand(True) # Expande para preencher o espaço vertical

        self.text_view = Gtk.TextView.new_with_buffer(self.text_buffer)
        self.text_view.set_editable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.add_css_class("monospace")
        
        scrolled_window.set_child(self.text_view)
        self.append(scrolled_window)

        # Botão para Limpar Logs
        clear_button = Gtk.Button.new_with_label("Limpar Logs")
        clear_button.set_halign(Gtk.Align.END)
        clear_button.connect("clicked", self._on_clear_logs_clicked)
        self.append(clear_button)

    def _on_clear_logs_clicked(self, button: Gtk.Button):
        """Limpa todo o conteúdo do buffer de texto."""
        self.text_buffer.set_text("")

    def log(self, message: str, is_error: bool = False):
        """
        Adiciona uma nova linha ao log de forma thread-safe.
        (Antigo append_log)
        Este método deve ser chamado pelo `GLib.idle_add` ou diretamente se na thread principal.
        """
        # Adicionar à fila de idle (garantir execução na thread principal)
        GLib.idle_add(self._append_log_in_main_thread, message, is_error)
        
    def _append_log_in_main_thread(self, message: str, is_error: bool):
        """Lógica real de adição de log, executada APENAS na thread principal."""
        end_iter = self.text_buffer.get_end_iter()
        
        # Formata a mensagem com quebra de linha
        log_entry = f"[{GLib.DateTime.new_now_local().format('%H:%M:%S')}] {message}\n"
        
        # Insere o texto e aplica a tag se for um erro
        if is_error:
            self.text_buffer.insert_with_tags(end_iter, log_entry, self.error_tag)
        else:
            self.text_buffer.insert(end_iter, log_entry)

        # Rola automaticamente para a última linha
        end_iter = self.text_buffer.get_end_iter()
        self.text_view.scroll_to_iter(end_iter, 0.0, False, 0.0, 0.0)
        
        return GLib.SOURCE_REMOVE # Retorna False para não ser executado novamente
