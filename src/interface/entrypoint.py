# Ponto de entrada modularizado para a aplicação Image2PDF.
import gi
import sys

# Assume que os módulos gi, Gtk, Adw, config e core estão disponíveis.
try:
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    # Adicionando Gtk e Gdk para lidar com CSS
    from gi.repository import Adw, Gtk, Gdk 
except ImportError:
    print("Erro: Bibliotecas GTK4/Libadwaita (pygobject) não encontradas. Certifique-se de que estão instaladas.")
    sys.exit(1)

# Importa a janela principal e o app (modularização)
# O gui.py agora contém a classe Image2PDFWindow que orquestra as páginas
from .gui import Image2PDFWindow

class Image2PDFApp(Adw.Application):
    """Classe principal da aplicação GTK4/Libadwaita."""

    def __init__(self):
        super().__init__(application_id="com.jtp.image2pdf")
        self.connect("activate", self.on_activate)
        self.load_custom_css() # Garante que o CSS seja carregado na inicialização

    def load_custom_css(self):
        # GTK4 usa Gtk.CssProvider para aplicar estilos.
        css_provider = Gtk.CssProvider.new()
        css_data = """
        /* Fundo escurecido para o diálogo 'Sobre' (Scrim) */
        .about-scrim {
            /* CORREÇÃO: Define o fundo semi-transparente para o scrim */
            background-color: rgba(0, 0, 0, 0.4); 
            padding: 0px; 
            margin: 0px;
        }

        /* Estilo do container do diálogo central */
        .about-dialog-content {
            background-color: @card_bg_color;
            border-radius: 12px;
            padding: 0px; /* Padding será controlado pelos filhos */
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }

        /* Estilo do indicador de versão (como na imagem) */
        .version-pill {
            background-color: @accent_bg_color;
            color: @accent_color;
            font-weight: bold;
        }
        """
        
        # Adiciona o CSS ao provider
        css_provider.load_from_data(css_data.encode('utf-8'))
        
        # Aplica o CSS a todas as janelas do aplicativo
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def on_activate(self, app):
        # Preferência de esquema de cores do sistema
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)

        # A Image2PDFWindow agora é o container que carrega Home, Prefs e Logs
        self.main_window = Image2PDFWindow(self)
        self.main_window.present()

if __name__ == "__main__":
    app = Image2PDFApp()
    sys.exit(app.run(sys.argv))
