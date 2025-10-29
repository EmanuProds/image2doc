# Contém as classes da GUI (OCR_AppGTK, CorrectionDialog e OCR_Application).
import os
import queue
import threading
import sys 
from typing import Optional, Dict, Callable

# Dependências GTK/Libadwaita
try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    
    # Importação explícita de todos os módulos necessários
    from gi.repository import Gtk, Adw, GLib, Gio
    
except ImportError:
    # Este erro deve ser tratado no ponto de entrada
    raise ImportError(
        "As bibliotecas GTK4/Libadwaita (pygobject) não estão instaladas."
    )

# Importa as configurações e o backend (Usando importação relativa para módulos dentro de 'src')
from . import config
from . import core

# BLOCO DE FUNÇÕES DA INTERFACE E DIÁLOGOS
# --- CLASSE DE DIÁLOGO DE CORREÇÃO (Mantida) ---
class CorrectionDialog(Adw.MessageDialog):
    """
    Diálogo Modal GTK para Intervenção Manual.
    Permite que o usuário digite o número da folha correto quando o OCR falha.
    """
    def __init__(
      self, parent: Gtk.Window, filename: str, last_folha: int, max_folhas: int
    ):
        body_text = (
            f"Arquivo: <b>{filename}</b>\nÚltima Folha Processada: FL. {last_folha}"
        )
        super().__init__(
            parent=parent,
            modal=True,
            heading="Correção Manual de Número de Folha",
            body=body_text,
            default_show_close_button=False,
            close_response="cancel",
        )
        
        self.folha_num_entry = Gtk.Entry()
        self.folha_num_entry.set_placeholder_text("Ex: 154")
        self.folha_num_entry.set_input_hints(Gtk.InputHints.DIGITS)
        
        clamp = Adw.Clamp.new()
        clamp.set_child(self.folha_num_entry)

        self.add_response("cancel", "Cancelar")
        self.add_response("apply", "Aplicar Correção")
        self.set_response_enabled("apply", False)

        self.set_response_response("cancel", Gtk.ResponseType.CANCEL)
        self.set_response_response("apply", Gtk.ResponseType.APPLY)
        
        self.set_default_response("apply")
        
        self.folha_num_entry.connect("changed", self._on_entry_changed, max_folhas)

        self.set_extra_child(clamp)

        self.folha_corrigida: Optional[int] = None
        self.connect("response", self._on_response)

    def _on_entry_changed(self, entry: Gtk.Entry, max_folhas: int):
        text = entry.get_text().strip()
        is_valid = False
        
        if text.isdigit():
            num = int(text)
            # Permite 0 (zero) e até max_folhas + 1 como número válido
            if 0 <= num <= max_folhas + 1:
                is_valid = True
        
        self.set_response_enabled("apply", is_valid)

    def _on_response(self, dialog, response_id: str):
        if response_id == "apply":
            try:
                text = self.folha_num_entry.get_text().strip()
                self.folha_corrigida = int(text)
            except ValueError:
                self.folha_corrigida = None
        elif response_id == "cancel":
            self.folha_corrigida = None
            
        self.close()


# --- CLASSE PRINCIPAL DA INTERFACE (Atualizada) ---
class OCR_AppGTK(Adw.ApplicationWindow):
    """
    Classe da janela principal (Adw.ApplicationWindow) usando Adw.NavigationSplitView.
    """

    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        
        # Estado e dados da aplicação
        self.input_dir: Optional[str] = None
        self.output_dir: Optional[str] = None
        self.max_folhas: int = config.DEFAULT_MAX_FOLHAS
        self.num_processes: int = config.DEFAULT_PROCESSES
        self.ultima_folha_processada: Optional[int] = None
        self.is_processing: bool = False
        self.correcoes_manuais: Dict[str, int] = {} 
        self.processing_thread: Optional[threading.Thread] = None

        # Configuração da janela principal
        self.set_default_size(800, 650)
        self.set_icon_name("x-office-document") 
        self.set_title("Image2PDF") 

        # 1. Header Bar (Barra de Título)
        self.header_bar = Adw.HeaderBar.new()
        
        # Botão de Cancelar
        self.cancel_button = Gtk.Button.new_with_label("Cancelar")
        self.cancel_button.set_icon_name("media-playback-stop-symbolic")
        self.cancel_button.add_css_class("destructive-action")
        self.cancel_button.set_visible(False)
        self.cancel_button.connect("clicked", self._on_cancel_clicked)
        self.header_bar.pack_end(self.cancel_button)

        # 2. Toast Overlay (Para notificações)
        self.toast_overlay = Adw.ToastOverlay.new()
        self.set_content(self.toast_overlay)

        # 3. Gtk.Box vertical principal
        main_vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.toast_overlay.set_child(main_vbox)

        # Adiciona a HeaderBar ao box
        main_vbox.append(self.header_bar)

        # 4. Navigation Split View (Layout principal)
        self.main_view = Adw.NavigationSplitView.new()
        self.main_view.set_min_sidebar_width(250)
        self.main_view.set_sidebar_width_fraction(0.2)
        self.main_view.set_vexpand(True) 
        main_vbox.append(self.main_view) 

        # 5. Sidebar (Menu Lateral)
        self.sidebar_list_box = Gtk.ListBox.new()
        self.sidebar_list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar_list_box.add_css_class("navigation-sidebar")
        
        sidebar_page = Adw.NavigationPage.new(self.sidebar_list_box, "Visualizações")
        self.main_view.set_sidebar(sidebar_page)

        # 6. Content Stack (Conteúdo Principal)
        self.content_stack = Gtk.Stack.new()
        content_page = Adw.NavigationPage.new(self.content_stack, "Conteúdo")
        self.main_view.set_content(content_page)
        self.sidebar_list_box.connect("row-selected", self._on_sidebar_row_selected)

        # 7. Criação das Páginas
        self._create_home_page()
        self._create_parameters_page()
        self._create_log_page()

        # 8. Adiciona Páginas ao Sidebar e Stack
        self._add_navigation_page("home", "Processar", "media-playback-start-symbolic", self.home_page_box)
        self._add_navigation_page("params", "Configurações", "org.gnome.Settings-symbolic", self.parameters_page)
        self._add_navigation_page("log", "Histórico", "document-open-recent-symbolic", self.log_page_scrolled)

        # Seleciona a primeira página (Home)
        self.sidebar_list_box.select_row(self.sidebar_list_box.get_row_at_index(0))


    def _add_navigation_page(self, name: str, title: str, icon: str, content_widget: Gtk.Widget):
        """Adiciona uma página ao Stack e uma linha correspondente ao Sidebar."""
        self.content_stack.add_titled(content_widget, name, title)
        
        row = Adw.ActionRow.new()
        row.set_title(title)
        row.set_icon_name(icon) 
        row.set_activatable(True)
        row.set_name(name) 
        self.sidebar_list_box.append(row)

    def _on_sidebar_row_selected(self, list_box: Gtk.ListBox, row: Optional[Gtk.ListBoxRow]):
        """Callback para mudar a página de conteúdo quando o menu lateral é clicado."""
        if row is None:
            return
            
        # Se o processamento estiver ativo, ignora a troca de página 
        if self.is_processing:
            return
            
        page_name = row.get_name()
        self.content_stack.set_visible_child_name(page_name)
        
        stack_page = self.content_stack.get_visible_child().get_parent()
        
        if stack_page and isinstance(stack_page, Gtk.StackPage):
            self.set_title(stack_page.get_title())
        else:
            self.set_title("Image2PDF")


    # --- Métodos de Criação de Página ---

    def _create_home_page(self):
        """Cria a página 'Home' (Processar) com o botão de iniciar."""
        
        status_page = Adw.StatusPage.new()
        status_page.set_icon_name("x-office-document") 
        status_page.set_title("Image2PDF")
        status_page.set_description("Defina os diretórios e parâmetros na aba 'Parâmetros' e inicie o processo.")
        
        # Botão de Iniciar (com ícone de Play)
        self.start_button = Gtk.Button.new_with_label("Iniciar Processamento")
        self.start_button.set_icon_name("media-playback-start-symbolic")
        self.start_button.add_css_class("suggested-action")
        self.start_button.set_halign(Gtk.Align.CENTER)
        self.start_button.connect("clicked", self._on_start_clicked)
        
        status_page.set_child(self.start_button)
        
        self.home_page_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 20)
        self.home_page_box.set_valign(Gtk.Align.CENTER)
        self.home_page_box.set_halign(Gtk.Align.CENTER)
        self.home_page_box.set_margin_top(24)
        self.home_page_box.set_margin_bottom(24)
        
        self.home_page_box.append(status_page)
        
        # Label de Status
        self.status_label = Gtk.Label.new("Não iniciado.")
        self.status_label.add_css_class("title-4")
        self.status_label.set_halign(Gtk.Align.CENTER)
        
        status_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        status_box.set_halign(Gtk.Align.CENTER)
        status_box.append(Gtk.Label.new("Última Folha Processada:"))
        status_box.append(self.status_label)
        
        self.home_page_box.append(status_box)
        
    def _create_parameters_page(self):
        """Cria a página 'Parâmetros'."""
        
        self.parameters_page = Adw.PreferencesPage.new()
        self.parameters_page.set_title("Parâmetros") 
        
        # --- Grupo de Diretórios ---
        settings_group_dirs = Adw.PreferencesGroup.new()
        settings_group_dirs.set_title("Diretórios")
        self.parameters_page.add(settings_group_dirs)
        
        # Input Directory
        self.input_row = Adw.ActionRow.new()
        self.input_row.set_title("Diretório de Entrada (Imagens p/ OCR)")
        self.input_row.set_subtitle("Nenhum diretório selecionado")
        self.input_row.set_icon_name("folder-open-symbolic")
        self.input_row.set_activatable(True)
        self.input_row.connect("activated", self._on_select_input_dir)
        settings_group_dirs.add(self.input_row)

        # Output Directory
        self.output_row = Adw.ActionRow.new()
        self.output_row.set_title("Diretório de Saída (PDFs Renomeados)")
        self.output_row.set_subtitle("Nenhum diretório selecionado")
        self.output_row.set_icon_name("folder-new-symbolic")
        self.output_row.set_activatable(True)
        self.output_row.connect("activated", self._on_select_output_dir)
        settings_group_dirs.add(self.output_row)
        
        # --- Grupo de Parâmetros ---
        settings_group_params = Adw.PreferencesGroup.new()
        settings_group_params.set_title("Parâmetros do Livro e Processamento")
        self.parameters_page.add(settings_group_params)
        
        # Máximo de Folhas
        self.max_folhas_row = Adw.ActionRow.new()
        self.max_folhas_row.set_title("Máximo de Folhas do Livro")
        self.max_folhas_row.set_subtitle(f"Define o número FL. Máximo (padrão: {config.DEFAULT_MAX_FOLHAS})")
        self.max_folhas_spin = Gtk.SpinButton.new_with_range(1, 1000, 1)
        self.max_folhas_spin.set_value(config.DEFAULT_MAX_FOLHAS)
        self.max_folhas_spin.connect("value-changed", self._on_max_folhas_changed)
        self.max_folhas_row.add_suffix(self.max_folhas_spin)
        self.max_folhas_row.set_activatable_widget(self.max_folhas_spin)
        settings_group_params.add(self.max_folhas_row)
        
        # Número de Processos
        self.num_processes_row = Adw.ActionRow.new()
        self.num_processes_row.set_title("Número de Workers de OCR")
        self.num_processes_row.set_subtitle(f"Processos paralelos para OCR (padrão: {config.DEFAULT_PROCESSES})")
        self.num_processes_spin = Gtk.SpinButton.new_with_range(1, 16, 1)
        self.num_processes_spin.set_value(config.DEFAULT_PROCESSES)
        self.num_processes_spin.connect("value-changed", self._on_num_processes_changed)
        self.num_processes_row.add_suffix(self.num_processes_spin)
        self.num_processes_row.set_activatable_widget(self.num_processes_spin)
        settings_group_params.add(self.num_processes_row)

    def _create_log_page(self):
        """Cria a página de 'Log'."""
        self.log_buffer = Gtk.TextBuffer.new()
        self.log_view = Gtk.TextView.new_with_buffer(self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        
        self.log_page_scrolled = Gtk.ScrolledWindow.new()
        self.log_page_scrolled.set_child(self.log_view)
        self.log_page_scrolled.set_vexpand(True)
        self.log_page_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        

    # --- Funções de Lógica e Callbacks ---
    
    # LOG e Status (chamados do thread principal via GLib.idle_add)
    def log(self, message: str, is_error: bool = False):
        """Adiciona uma mensagem de log thread-safe e imprime imediatamente no console."""
        
        # 1. DEBUG CRÍTICO: Imprime imediatamente no console.
        print(f"[UI LOG {'ERROR' if is_error else 'INFO'}]: {message}", 
              file=sys.stderr if is_error else sys.stdout, flush=True)

        def _add_log():
            buffer = self.log_buffer
            end_iter = buffer.get_end_iter()
            
            if is_error:
                # Cria ou obtém a tag de erro
                tag = buffer.get_tag_table().lookup("error")
                if tag is None:
                     tag = buffer.create_tag("error", foreground="#e01b24", weight=700)
                buffer.insert_with_tags_by_name(end_iter, message + "\n", "error")
            else:
                buffer.insert(end_iter, message + "\n")
            
            end_iter = buffer.get_end_iter()
            self.log_view.scroll_to_iter(end_iter, 0.0, False, 0.0, 0.0)
            return GLib.SOURCE_REMOVE
            
        GLib.idle_add(_add_log)
        
    def update_status_label(self, folha_num: Optional[int] = None):
        """Atualiza a label de status da última folha processada thread-safe."""
        if folha_num is not None:
            self.ultima_folha_processada = folha_num
            
        text = "Não iniciado."
        if self.is_processing:
            text = "Em processamento..."
        
        if self.ultima_folha_processada is not None:
            text = f"FL. {self.ultima_folha_processada:03d}"
            
        def _update_label():
            self.status_label.set_text(text)
            return GLib.SOURCE_REMOVE
            
        GLib.idle_add(_update_label)

    # ESTADO DA INTERFACE
    def set_controls_state(self, state: bool):
        """Define o estado (ativo/inativo) dos controles durante o processamento (True = Ativo, False = Inativo)."""
        # Define o estado de processamento
        self.is_processing = not state
        
        # Menu Lateral
        self.sidebar_list_box.set_sensitive(state)
        
        # Página de Parâmetros (desabilita tudo nela)
        self.parameters_page.set_sensitive(state)
        
        # Botões
        self.start_button.set_sensitive(state)
        # O botão de Cancelar só deve aparecer quando o processamento está ativo
        self.cancel_button.set_visible(not state) 
        if state:
             self.cancel_button.set_sensitive(True)

        self.update_status_label()

    # FUNÇÕES DE INTERAÇÃO COM DIRETÓRIOS
    
    def _update_dir_and_row(self, row: Adw.ActionRow, attr_name: str, directory: Optional[str]):
        """Executa a atualização da UI de forma atômica e reponsável."""
        if directory:
            setattr(self, attr_name, directory)
            row.set_subtitle(directory)
        elif not getattr(self, attr_name):
            # Se o usuário cancelar e o diretório ainda não estiver definido
            row.set_subtitle("Nenhum diretório selecionado")
    
    def _on_select_input_dir(self, row: Adw.ActionRow):
        """Abre o diálogo para selecionar o diretório de entrada."""
        self._select_directory(
            title="Selecionar Diretório de Imagens de Entrada",
            callback=lambda d: self._update_dir_and_row(row, 'input_dir', d)
        )

    def _on_select_output_dir(self, row: Adw.ActionRow):
        """Abre o diálogo para selecionar o diretório de saída."""
        self._select_directory(
            title="Selecionar Diretório de Saída (PDFs)",
            callback=lambda d: self._update_dir_and_row(row, 'output_dir', d)
        )

    def _select_directory(self, title: str, callback: Callable[[Optional[str]], None]):
        """
        Função auxiliar para abrir o seletor de diretório.
        Usa Gtk.FileDialog e seu método assíncrono para garantir que não haja bloqueio
        do thread principal (UI).
        """
        self.log("DEBUG A: Chamando Gtk.FileDialog.select_folder(). UI viva.")
        
        dialog = Gtk.FileDialog.new()
        dialog.set_title(title)

        # Passamos o callback de atualização da UI como user_data
        dialog.select_folder(self, None, self._on_folder_selected_cb, callback)

    # CORREÇÃO CRÍTICA: Deferir a atualização da UI com timeout
    def _on_folder_selected_cb(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, callback: Callable[[Optional[str]], None]):
        """Callback assíncrono chamado após a seleção do diretório."""
        
        # LOG DE DEBUG 1: Início do callback
        self.log("DEBUG 1: Início do callback de seleção de pasta (select_folder_finish prestes a ser chamado).")
        
        folder_path = None
        try:
            # Tenta obter o resultado da operação assíncrona
            file = dialog.select_folder_finish(result)
            
            # LOG DE DEBUG 2: Sucesso na chamada finish
            self.log("DEBUG 2: select_folder_finish concluído com sucesso.")
            
            if file:
                # Gtk.File (file) é retornado se a seleção for bem-sucedida
                folder_path = file.get_path()
                self.log(f"DEBUG 2.1: Caminho obtido: {folder_path}")

        except GLib.Error as e:
            # Captura exceções de cancelamento ou erro
            if "canceled" not in str(e).lower():
                self.log(f"Erro ao selecionar diretório: {e}", is_error=True)
            
            # LOG DE DEBUG 3: Cancelamento ou erro tratado
            self.log("DEBUG 3: Seleção cancelada ou erro tratado.")
            folder_path = None
        
        
        # --- MUDANÇA CRÍTICA: Deferir o callback final da UI com um pequeno timeout ---
        # Usamos GLib.timeout_add com 10ms (10) para garantir que o loop de eventos
        # principal do GTK tenha tempo de fechar e liberar o estado do FileDialog
        # antes de redesenhar a janela principal.
        def _deferred_update():
            # A lógica de callback/atualização da UI (set_subtitle)
            callback(folder_path)
            self.log("DEBUG 4: Fim do callback de seleção de pasta. UI liberada após a atualização deferida (via timeout).") 
            return GLib.SOURCE_REMOVE # Remove o timeout
            
        # Agenda a execução em 10 milissegundos (muito curto, mas suficiente para liberar o modal)
        GLib.timeout_add(10, _deferred_update)


    # EVENTOS DE MUDANÇA DE PARÂMETROS
    
    def _on_max_folhas_changed(self, spin_button: Gtk.SpinButton):
        """Atualiza o valor de max_folhas quando o spin button muda."""
        self.max_folhas = spin_button.get_value_as_int()
        self.max_folhas_row.set_subtitle(f"Define o número FL. Máximo (valor: {self.max_folhas})")

    def _on_num_processes_changed(self, spin_button: Gtk.SpinButton):
        """Atualiza o valor de num_processes quando o spin button muda."""
        self.num_processes = spin_button.get_value_as_int()
        self.num_processes_row.set_subtitle(f"Processos paralelos para OCR (valor: {self.num_processes})")

    # FUNÇÕES DE EXECUÇÃO
    
    def _on_start_clicked(self, button: Gtk.Button):
        """Lógica para iniciar o processamento em uma thread separada."""
        if self.is_processing:
            self.log("Já existe um processamento em andamento.", is_error=True)
            self.toast_overlay.add_toast(Adw.Toast.new("Processamento já em andamento!"))
            return
            
        if not self.input_dir or not self.output_dir:
            self.log("Selecione os diretórios de Entrada e Saída antes de iniciar.", is_error=True)
            self.toast_overlay.add_toast(Adw.Toast.new("Selecione os diretórios de Entrada e Saída"))
            return

        # Limpa o log e o estado anterior
        self.log_buffer.set_text("")
        self.log("--- INICIANDO PROCESSAMENTO ---")
        self.ultima_folha_processada = None
        self.correcoes_manuais = {}
        
        self.set_controls_state(False)

        # Muda para a aba de Log automaticamente
        self.content_stack.set_visible_child_name("log")
        log_row = self.sidebar_list_box.get_row_at_index(2)
        if log_row:
             self.sidebar_list_box.select_row(log_row)
        
        self.processing_thread = threading.Thread(target=self._run_backend_logic, daemon=True)
        self.processing_thread.start()
        
    def _on_cancel_clicked(self, button: Gtk.Button):
        """Define a flag de is_processing para False para sinalizar o cancelamento."""
        if not self.is_processing:
            self.log("Nenhum processamento em andamento para cancelar.", is_error=True)
            return

        self.is_processing = False 
        self.log("\n--- SINAL DE CANCELAMENTO ENVIADO. Aguardando a conclusão da tarefa atual... ---", is_error=True)
        self.cancel_button.set_sensitive(False)


    # CALLBACK PARA INTERVENÇÃO MANUAL 
    def ask_manual_correction(self, filename: str, last_folha: int) -> Optional[int]:
        """Abre um diálogo modal para intervenção manual e armazena a correção."""
        self.log(f"--- INTERVENÇÃO MANUAL REQUERIDA para '{filename}'. ---", is_error=True)
        
        result_queue = queue.Queue()
        
        # Função executada na thread principal (UI)
        def _run_and_present(): 
            dialog = CorrectionDialog(
                parent=self.get_root(),
                filename=filename, 
                last_folha=last_folha, 
                max_folhas=self.max_folhas
            )
            
            # Conecta o sinal 'response' do diálogo para enviar o resultado para a fila
            def on_dialog_response(dialog_obj, response_id):
                result_queue.put(dialog_obj.folha_corrigida)
                
            dialog.connect("response", on_dialog_response)
            dialog.present() 
            return GLib.SOURCE_REMOVE

        # Agenda a apresentação do diálogo na thread principal
        GLib.idle_add(_run_and_present)
        
        # Bloqueia a thread de processamento até que a thread principal retorne um valor
        folha_num_corrigida = result_queue.get()
        
        if folha_num_corrigida is not None:
            filename_base = os.path.basename(filename)
            self.correcoes_manuais[filename_base] = folha_num_corrigida
            self.log(f"Correção aplicada: '{filename}' -> FL. {folha_num_corrigida:03d}")
        else:
            self.log(f"Correção cancelada para '{filename}'. Processo interrompido.", is_error=True)
            self.is_processing = False
            
        return folha_num_corrigida

    # LÓGICA DE EXECUÇÃO DE BACKEND
    def _run_backend_logic(self):
        """Executa a lógica principal do backend em uma thread de trabalho."""

        def get_is_processing_state_wrapper() -> bool:
            return self.is_processing
            
        def set_is_processing_state_wrapper(state: bool):
            self.is_processing = state
            GLib.idle_add(self.set_controls_state, state)

        try:
            final_ultima_folha = core.run_processing_logic(
                input_dir=self.input_dir,
                output_dir=self.output_dir,
                max_folhas=self.max_folhas,
                num_processes=self.num_processes,
                ultima_folha_processada=self.ultima_folha_processada,
                correcoes_manuais=self.correcoes_manuais,
                log_callback=self.log,
                ask_manual_correction_callback=self.ask_manual_correction,
                set_is_processing_state=set_is_processing_state_wrapper,
                get_is_processing_state=get_is_processing_state_wrapper,
            )

            if final_ultima_folha is not None:
                self.ultima_folha_processada = final_ultima_folha
                GLib.idle_add(self.update_status_label, self.ultima_folha_processada)
                
            self.log("--- PROCESSAMENTO CONCLUÍDO ---")
        
        except Exception as e:
            self.log(f"\n--- ERRO CRÍTICO NO BACKEND: {e} ---", is_error=True)
            import traceback
            self.log(traceback.format_exc(), is_error=True)
        
        finally:
            # Garante que os controles sejam reativados (True) no thread principal,
            # independentemente do resultado (sucesso, erro ou cancelamento).
            GLib.idle_add(self.set_controls_state, True)


# --- CLASSE DE APLICAÇÃO (Sem alterações) ---
class OCR_Application(Adw.Application):
    """Classe principal da aplicação GTK4/Libadwaita (Ponto de entrada GTK)."""

    def __init__(self):
        super().__init__(application_id="com.jtp.organizadorlivros")
        self.connect("activate", self.on_activate)
        
    def on_activate(self, app):
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)

        self.main_window = OCR_AppGTK(self)
        self.main_window.present()
