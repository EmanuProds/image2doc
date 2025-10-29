import gi
from typing import Callable

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, Gdk

# Importa o módulo de configuração (mantido)
try:
    from .. import config
    APP_VERSION = config.APP_VERSION
except ImportError:
    # Fallback
    class MockConfig:
        APP_VERSION = "0.0.0"
    config = MockConfig()
    APP_VERSION = config.APP_VERSION


class AboutDialog(Gtk.Box):
    """
    Widget 'Sobre' customizado, desenhado para ser usado dentro de um Adw.Overlay.
    Ele renderiza um "scrim" (fundo escurecido) e um diálogo centralizado.
    """
    
    def __init__(self, close_callback: Callable):
        """
        Inicializa o widget 'Sobre'.
        
        Args:
            close_callback: Função a ser chamada quando o diálogo deve ser fechado 
                            (ex: clique no 'X' ou no fundo).
        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.close_callback = close_callback
        
        # --- 1. Scrim (Fundo Escurecido) ---
        # O próprio Gtk.Box atuará como o scrim
        self.add_css_class("about-scrim")
        self.set_hexpand(True)
        self.set_vexpand(True)
        
        # Conecta o clique no scrim para fechar
        scrim_click = Gtk.GestureClick.new()
        # Permite que os filhos capturem o clique antes de fechar o scrim
        scrim_click.set_propagation_phase(Gtk.PropagationPhase.BUBBLE) 
        scrim_click.connect("pressed", self._on_scrim_clicked)
        self.add_controller(scrim_click)

        # --- 2. Conteúdo do Diálogo (Box Central) ---
        # Este é o container que se parece com o diálogo da imagem
        dialog_content_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 15)
        # CORREÇÃO: Adicionando a classe 'card' para garantir que ele tenha um fundo sólido
        dialog_content_box.add_css_class("card") 
        dialog_content_box.add_css_class("about-dialog-content")
        dialog_content_box.set_size_request(380, -1) # Largura fixa
        dialog_content_box.set_valign(Gtk.Align.CENTER)
        dialog_content_box.set_halign(Gtk.Align.CENTER)
        
        # *** CORREÇÃO: Bloquear a propagação de cliques no conteúdo do diálogo ***
        dialog_click = Gtk.GestureClick.new()
        # CAPTURE garante que este evento seja processado antes do scrim (fundo)
        dialog_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        # O handler retorna Gdk.EVENT_STOP (que é True) para parar o evento aqui
        dialog_click.connect("pressed", lambda gesture, n_press, x, y: Gdk.EVENT_STOP) 
        dialog_content_box.add_controller(dialog_click)
        
        # Adiciona o diálogo centrado ao scrim (self)
        self.append(dialog_content_box)
        
        # --- 3. Botão de Fechar (Estilo da Imagem) ---
        close_button = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close_button.add_css_class("circular")
        close_button.add_css_class("flat")
        close_button.set_halign(Gtk.Align.END)
        close_button.set_valign(Gtk.Align.START)
        close_button.set_margin_top(8)
        close_button.set_margin_end(8)
        close_button.connect("clicked", lambda *args: self.close_callback())
        
        # Adiciona o botão em uma Gtk.Box para alinhamento (canto superior direito)
        close_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        close_box.append(close_button)
        dialog_content_box.append(close_box) # Adiciona ao dialog_content_box

        # --- 4. Conteúdo Original (Header, Versão, Lista) ---
        
        # --- Área do Header (Ícone, Título e Subtítulo/Autor) ---
        header_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
        header_box.set_halign(Gtk.Align.CENTER)
        header_box.set_margin_top(0) # Padding é controlado pelo CSS

        icon_image = Gtk.Image.new_from_icon_name("x-office-document")
        icon_image.set_pixel_size(96)
        icon_image.set_margin_bottom(10)
        
        title_label = Gtk.Label.new("Image2PDF")
        title_label.add_css_class("title-1")

        author_label = Gtk.Label.new("Desenvolvido por Emanuel Pereira")
        author_label.add_css_class("body")
        
        header_box.append(icon_image)
        header_box.append(title_label)
        header_box.append(author_label)

        # --- Tag de Versão (Estilo Pílula - Estilo da Imagem) ---
        version_tag_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        version_tag_box.set_halign(Gtk.Align.CENTER)
        
        version_button = Gtk.Button.new_with_label(f"v{APP_VERSION}")
        version_button.add_css_class("pill")
        version_button.add_css_class("version-pill")
        version_button.set_sensitive(False) # Mantém como não clicável
        
        version_tag_box.append(version_button)

        dialog_content_box.append(header_box)
        dialog_content_box.append(version_tag_box)
        
        # --- Lista de Ações (Links e Info) ---
        list_box = Gtk.ListBox.new()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add_css_class("boxed-list")
        
        # Adiciona margens para não colar nas bordas
        list_box.set_margin_top(15)
        list_box.set_margin_bottom(20)
        list_box.set_margin_start(20)
        list_box.set_margin_end(20)

        # Função auxiliar (Já está correta para o estilo da imagem)
        def create_about_row(title, subtitle=None, link_uri=None):
            row = Adw.ActionRow.new()
            row.set_title(title)
            if subtitle: row.set_subtitle(subtitle)
            
            if link_uri:
                # Estilo da imagem: ícone de link externo
                row.add_suffix(Gtk.Image.new_from_icon_name("adw-external-link-symbolic")) 
                row.set_activatable(True)
                row.connect("activated", lambda *args: Gio.AppInfo.launch_default_for_uri(link_uri, None))
            else:
                # Fallback para itens internos
                row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
                row.set_activatable(True)
                
            list_box.append(row)
            return row

        # Ação Única: GitHub (Mantido)
        create_about_row("GitHub", link_uri="https://github.com/EmanuProds/ncx-book-organizer") 

        dialog_content_box.append(list_box)
        
        # Conecta a tecla ESC para fechar o diálogo
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-released", self._on_key_release)
        self.add_controller(key_controller) # Adiciona o controller ao widget (self)

    def _on_scrim_clicked(self, *args):
        """Chamado quando o fundo (scrim) é clicado. Deve fechar."""
        self.close_callback()
        return Gdk.EVENT_STOP # Impede que o clique vá adiante

    def _on_key_release(self, controller, keyval, keycode, state):
        """Chamado quando uma tecla é liberada."""
        # Verifica se a tecla liberada é ESC (Gdk.KEY_Escape)
        if keyval == Gdk.KEY_Escape:
            self.close_callback()
            return Gdk.EVENT_STOP # Evento tratado
        return Gdk.EVENT_PROPAGATE # Evento não tratado
