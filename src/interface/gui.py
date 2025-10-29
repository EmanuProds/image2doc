# Contém a classe da janela principal (Image2PDFWindow)
import gi
from typing import Optional

# Dependências GTK/Libadwaita
try:
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw, GLib, Gio
    
except ImportError:
    # Este erro deve ser tratado no ponto de entrada
    raise ImportError("As bibliotecas GTK4/Libadwaita (pygobject) não estão instaladas.")

# Importa os módulos modularizados
from .about import AboutDialog # Mantido
from .home import HomePage      # Lógica de Processamento
from .pref import PrefPage      # Configurações
from .logs import LogsPage      # Visualização de Logs

# --- CLASSE DA JANELA PRINCIPAL ---
class Image2PDFWindow(Adw.ApplicationWindow):
    """
    Janela Principal da Aplicação Image2PDF.
    Atua como um container que gerencia a navegação entre as páginas (Home, Prefs, Logs)
    e exibe o diálogo 'Sobre' em um overlay.
    """

    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title("Image2PDF")
        self.set_default_size(800, 600)

        # Inicializa as páginas
        self.logs_page = LogsPage()
        self.pref_page = PrefPage()
        
        # Função helper para obter dados de preferência para a Home Page
        def get_prefs_data():
            """Busca os valores de max_folhas e num_processes da página de prefs."""
            return {
                'max_folhas': self.pref_page.max_folhas,
                'num_processes': self.pref_page.num_processes
            }

        # A Home Page recebe o callback de log e a função para buscar preferências
        self.home_page = HomePage(
            parent_window=self, 
            log_callback=self.logs_page.log, 
            get_prefs_data=get_prefs_data
        )

        # --- Estrutura de Navegação (Adw.ViewStack / Gtk.Stack) ---
        
        # Gtk.Stack para gerenciar as páginas
        self.view_stack = Gtk.Stack.new()
        
        # Adiciona as páginas ao stack
        self.view_stack.add_titled(self.home_page, "home", "Início")
        self.view_stack.add_titled(self.pref_page, "prefs", "Configurações")
        self.view_stack.add_titled(self.logs_page, "logs", "Logs")

        # Gtk.StackSwitcher para controle de navegação (botões/abas)
        stack_switcher = Gtk.StackSwitcher.new()
        stack_switcher.set_stack(self.view_stack)

        # --- Header Bar ---
        # Salva a header_bar como uma variável de instância para acesso posterior
        self.header_bar = Adw.HeaderBar.new()
        self.header_bar.set_title_widget(stack_switcher)

        # Botão Sobre
        about_button = Gtk.Button.new_from_icon_name("help-about-symbolic")
        about_button.connect("clicked", self._on_about_clicked)
        self.header_bar.pack_start(about_button) # Usa self.header_bar

        # --- Layout Principal (MODIFICADO COM Adw.Overlay) ---
        
        # 1. Conteúdo principal (Header + Stack)
        main_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        main_box.append(self.header_bar) # Usa self.header_bar
        main_box.append(self.view_stack)
        
        # 2. Widget 'Sobre' (inicialmente invisível)
        self.about_widget = AboutDialog(close_callback=self._close_about)
        self.about_widget.set_visible(False)
        self.about_widget.set_vexpand(True)
        self.about_widget.set_hexpand(True)
        
        # 3. Overlay (Contém o main_box e o about_widget por cima)
        # *** CORREÇÃO: Alterado de Adw.Overlay para Gtk.Overlay ***
        self.overlay = Gtk.Overlay.new()
        self.overlay.set_child(main_box)
        self.overlay.add_overlay(self.about_widget)
        
        # Define o overlay como o conteúdo da janela
        self.set_content(self.overlay)
    
    def _on_about_clicked(self, widget: Gtk.Widget):
        """Exibe o diálogo 'Sobre' (dentro do overlay)."""
        self.about_widget.set_visible(True)
        
    def _close_about(self, *args):
        """Esconde o diálogo 'Sobre'."""
        self.about_widget.set_visible(False)
        
    def set_controls_state(self, is_running: bool):
        """
        Método chamado pela HomePage para controlar o estado da janela principal.
        Desativa controles (botão 'Sobre', navegação) durante o processamento.
        """
        
        # (Adicionado) Esconde o 'Sobre' se estiver aberto ao iniciar o processo
        if is_running and self.about_widget.get_visible():
            self.about_widget.set_visible(False)
            
        # Usa self.header_bar (que agora é uma variável de instância)
        if isinstance(self.header_bar, Adw.HeaderBar):
            # Desativa o botão About
            about_button = self.header_bar.get_start_child()
            if about_button:
                about_button.set_sensitive(not is_running)

            # Desativa a navegação (StackSwitcher)
            if self.header_bar.get_title_widget():
                self.header_bar.get_title_widget().set_sensitive(not is_running)
                
        # Chama a atualização dos controles na Home Page
        self.home_page.set_controls_state(is_running)

    def do_close_request(self):
        """
        Sobrescreve o comportamento de fechar para verificar se está processando.
        """
        if self.home_page._is_processing:
            self.home_page.log("Aguarde a conclusão ou pare o processamento antes de fechar.", is_error=True)
            return True # Cancela o fechamento
            
        return super().do_close_request()

