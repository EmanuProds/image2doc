import gi
from typing import Optional

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio

# Importa as configurações (Presume-se que o módulo config existe no diretório pai)
from .. import config 

class PrefPage(Gtk.Box): # Alterado de Adw.StatusPage para Gtk.Box
    """
    Página dedicada às configurações de processamento (Máximo de Folhas, Processos).
    """
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12) # Inicializa Gtk.Box
        
        # Removidas as chamadas set_title/set_description/set_icon_name

        # Contêiner para centralizar a lista
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
        vbox.set_margin_top(24)
        vbox.set_margin_bottom(24)
        vbox.set_margin_start(24)
        vbox.set_margin_end(24)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.START)

        # Título da Página (Adicionado manualmente para manter a estética)
        title_label = Gtk.Label.new("Configurações de Processamento")
        title_label.add_css_class("title-1")
        vbox.prepend(title_label)

        # Descrição da Página (Adicionado manualmente)
        desc_label = Gtk.Label.new("Ajuste os parâmetros para otimizar a conversão.")
        desc_label.add_css_class("body")
        desc_label.set_margin_bottom(12)
        vbox.prepend(desc_label)

        # Icone (Adicionado manualmente)
        icon_image = Gtk.Image.new_from_icon_name("document-properties-symbolic")
        icon_image.set_icon_size(Gtk.IconSize.LARGE)
        icon_image.set_margin_bottom(12)
        vbox.prepend(icon_image)

        # Configurações iniciais
        initial_max = config.MAX_FOLHAS_DEFAULT
        initial_proc = config.NUM_PROCESSES_DEFAULT

        # Cria a lista de controles
        list_box = Gtk.ListBox.new()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")
        
        # --- Campo Max Folhas ---
        row_max_folhas = Adw.ActionRow.new()
        row_max_folhas.set_title("Máximo de Folhas")
        row_max_folhas.set_subtitle("Define o limite máximo de páginas para processar.")
        
        self.max_folhas_entry = Gtk.Entry.new()
        self.max_folhas_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        self.max_folhas_entry.set_text(str(initial_max))
        # Adiciona o Entry como sufixo da ActionRow
        row_max_folhas.add_suffix(self.max_folhas_entry)
        row_max_folhas.set_activatable_widget(self.max_folhas_entry)

        list_box.append(row_max_folhas)

        # --- Campo Número de Processos ---
        row_num_processes = Adw.ActionRow.new()
        row_num_processes.set_title("Número de Processos Paralelos")
        row_num_processes.set_subtitle("Processamento multi-core. (0 = Automático)")
        
        self.num_processes_entry = Gtk.Entry.new()
        self.num_processes_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        self.num_processes_entry.set_text(str(initial_proc))
        # Adiciona o Entry como sufixo da ActionRow
        row_num_processes.add_suffix(self.num_processes_entry)
        row_num_processes.set_activatable_widget(self.num_processes_entry)

        list_box.append(row_num_processes)
        
        vbox.append(list_box)
        
        # Adiciona a Gtk.Box principal ao Gtk.Box da PrefPage (self)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.append(vbox)


    @property
    def max_folhas(self) -> Optional[int]:
        """Retorna o valor de Máximo de Folhas (ou None se inválido/vazio)."""
        try:
            val = self.max_folhas_entry.get_text().strip()
            if not val:
                return config.MAX_FOLHAS_DEFAULT
            return int(val)
        except ValueError:
            return None # Tratamento de erro de input inválido no home.py

    @property
    def num_processes(self) -> Optional[int]:
        """Retorna o valor de Número de Processos (ou None se inválido/vazio)."""
        try:
            val = self.num_processes_entry.get_text().strip()
            if not val:
                return config.NUM_PROCESSES_DEFAULT
            return int(val)
        except ValueError:
            return None # Tratamento de erro de input inválido no home.py
