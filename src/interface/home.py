import os
import queue
import threading
import sys
from typing import Optional, Dict, Callable

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, Pango

# Importa o backend (core) e o diálogo About
from .. import core
from .about import AboutDialog 

# --- CLASSE DE DIÁLOGO DE CORREÇÃO --
class CorrectionDialog(Adw.MessageDialog):
    """Diálogo Modal GTK para Intervenção Manual (OCR)."""
    def __init__(self, parent: Gtk.Window, filename: str, last_folha: int, max_folhas: int):
        # Usamos apenas o nome base do arquivo para uma UI mais limpa
        self.filename = filename
        body_text = f"Arquivo: <b>{os.path.basename(filename)}</b>\nÚltima Folha Processada: FL. {last_folha}"
        
        super().__init__(
            parent=parent, 
            modal=True,
            heading="Correção Manual Necessária",
            body=body_text,
            default_show_close_button=False # Apenas as ações definidas abaixo
        )
        
        # Adiciona a ActionRow com o campo de input
        row = Adw.ActionRow.new()
        row.set_title("Próxima Folha (FL.)")
        row.set_subtitle(f"Valor sugerido: {last_folha + 1}")

        self.input_entry = Gtk.Entry.new()
        self.input_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        self.input_entry.set_text(str(last_folha + 1))
        
        # Adiciona o entry ao fim da ActionRow
        row.add_suffix(self.input_entry)
        row.set_activatable_widget(self.input_entry)

        # Adiciona a ActionRow ao conteúdo do diálogo
        self.set_extra_child(row)

        # Botões de Ação
        self.add_response("confirm", "Aplicar Correção e Continuar")
        self.add_response("skip", "Pular Correção (Usar Sugestão)")
        self.add_response("stop", "Parar Processamento")

        # Conecta o evento de fechar (Enter/Escape)
        self.set_response_enabled("confirm", True)
        self.set_default_response("confirm")

    def get_correction_data(self) -> Optional[int]:
        """Retorna o valor corrigido inserido pelo usuário."""
        try:
            return int(self.input_entry.get_text().strip())
        except ValueError:
            return None

# --- CLASSE DA PÁGINA INICIAL ---
class HomePage(Gtk.Box): # Alterado de Adw.StatusPage para Gtk.Box
    """
    Página principal da aplicação, contendo os seletores de I/O, 
    botões de controle e toda a lógica de interação com o backend.
    """
    def __init__(self, parent_window: Gtk.Window, log_callback: Callable, get_prefs_data: Callable):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=24) # Inicializa Gtk.Box
        self.parent_window = parent_window
        self.log_callback = log_callback
        self.get_prefs_data = get_prefs_data # Callback para buscar dados de pref.py
        
        # Removidas as chamadas set_title/set_description/set_icon_name
        
        # --- Variáveis de Estado ---
        self.input_dir: Optional[str] = None
        self.output_dir: Optional[str] = None
        self.processing_thread: Optional[threading.Thread] = None
        self._is_processing = False
        self.correcoes_manuais: Dict[str, int] = {} # {filename: folha_corrigida}
        self.ultima_folha_processada: Optional[int] = None

        # --- Interface (Gtk.Box como conteúdo principal) ---
        main_vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 24)
        main_vbox.set_margin_top(24)
        main_vbox.set_margin_bottom(24)
        main_vbox.set_margin_start(24)
        main_vbox.set_margin_end(24)
        main_vbox.set_halign(Gtk.Align.CENTER)
        
        # Lista de Ações (Seletores de Pasta)
        list_box = Gtk.ListBox.new()
        list_box.add_css_class("boxed-list")
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        # 1. Seletor de Pasta de Entrada
        self.input_row = self._create_dir_selector_row(
            title="Pasta de Entrada", 
            subtitle="Selecione o diretório com as imagens a serem processadas.",
            callback=lambda widget: self._on_select_folder_clicked("input")
        )
        list_box.append(self.input_row)

        # 2. Seletor de Pasta de Saída
        self.output_row = self._create_dir_selector_row(
            title="Pasta de Saída", 
            subtitle="Diretório onde os PDFs e relatórios serão salvos.",
            callback=lambda widget: self._on_select_folder_clicked("output")
        )
        list_box.append(self.output_row)
        
        main_vbox.append(list_box)
        
        # --- Controles de Status e Ação ---
        
        # Título da Página (Adicionado manualmente para manter a estética)
        title_label = Gtk.Label.new("Image2PDF Converter")
        title_label.add_css_class("title-1")
        title_label.set_margin_bottom(12)
        main_vbox.prepend(title_label)

        # Descrição da Página (Adicionado manualmente)
        desc_label = Gtk.Label.new("Converta imagens de documentos para PDFs organizados com correção OCR.")
        desc_label.add_css_class("body")
        desc_label.set_wrap(True)
        main_vbox.prepend(desc_label)

        # Icone (Adicionado manualmente)
        icon_image = Gtk.Image.new_from_icon_name("folder-documents-symbolic")
        icon_image.set_icon_size(Gtk.IconSize.LARGE)
        icon_image.set_margin_bottom(12)
        main_vbox.prepend(icon_image)

        # Label de Status (para feedback rápido)
        self.status_label = Gtk.Label.new("Aguardando seleção de diretórios...")
        self.status_label.set_wrap(True)
        self.status_label.add_css_class("heading")
        main_vbox.append(self.status_label)

        # Botão Iniciar/Parar
        self.start_button = Gtk.Button.new_with_label("Iniciar Processamento")
        self.start_button.add_css_class("suggested-action")
        self.start_button.connect("clicked", self._on_start_stop_clicked)
        main_vbox.append(self.start_button)
        
        # Adiciona a Gtk.Box principal ao Gtk.Box da HomePage (self)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.append(main_vbox)

        # Inicializa o estado dos controles
        self.set_controls_state(False)


    # --- Métodos de Criação de UI (Helper) ---

    def _create_dir_selector_row(self, title: str, subtitle: str, callback: Callable) -> Adw.ActionRow:
        """Cria uma ActionRow com um botão de seleção de pasta."""
        row = Adw.ActionRow.new()
        row.set_title(title)
        row.set_subtitle(subtitle)
        
        button = Gtk.Button.new_from_icon_name("folder-open-symbolic")
        button.connect("clicked", callback)
        
        row.add_suffix(button)
        row.set_activatable_widget(button)
        return row

    # --- Lógica de Callbacks da UI (Botões) ---

    def _on_select_folder_clicked(self, type: str):
        """Abre o diálogo de seleção de pasta para Input ou Output."""
        dialog = Gtk.FileDialog.new()
        dialog.set_modal(True)
        dialog.set_title(f"Selecione a Pasta de {'Entrada' if type == 'input' else 'Saída'}")
        
        # Configura o tipo de seleção como pasta
        if hasattr(Gtk.FileDialog, 'set_select_folder'): # GTK 4.10+
            dialog.set_select_folder(True)
        else: # Fallback para versões mais antigas
             print("Aviso: Versão do GTK inferior à 4.10. Usando fallback.")

        def on_select(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
                path = folder.get_path()
                
                if type == "input":
                    self.input_dir = path
                    self.input_row.set_subtitle(f"Entrada: {path}")
                    self.log_callback(f"Pasta de Entrada Selecionada: {path}")
                elif type == "output":
                    self.output_dir = path
                    self.output_row.set_subtitle(f"Saída: {path}")
                    self.log_callback(f"Pasta de Saída Selecionada: {path}")
                    
                self.set_controls_state(self._is_processing)
            
            except Exception as e:
                # Ocorre quando o usuário cancela o diálogo
                if "Gio.IOErrorEnum.CANCELLED" not in str(e):
                    self.log_callback(f"Erro ao selecionar pasta: {e}", is_error=True)

        dialog.select_folder(self.parent_window, None, on_select)

    def _on_start_stop_clicked(self, widget: Gtk.Button):
        """Lida com o clique no botão Iniciar/Parar."""
        if self._is_processing:
            # Lógica de Parada
            self._is_processing = False
            self.set_controls_state(False)
            self.log_callback("Pedido de parada enviado ao backend...", is_error=True)
            # O backend (no thread) deve respeitar o estado _is_processing
        else:
            # Lógica de Início
            if not self.input_dir or not self.output_dir:
                self.log_callback("ERRO: Selecione as pastas de Entrada e Saída.", is_error=True)
                return

            self._is_processing = True
            self.set_controls_state(True)
            self.log_callback("--- INICIANDO PROCESSAMENTO ---")
            
            # Obtém as preferências da página de configurações
            prefs = self.get_prefs_data() 
            self.max_folhas = prefs.get('max_folhas')
            self.num_processes = prefs.get('num_processes')

            # Validação de Preferências
            if self.max_folhas is None or self.num_processes is None:
                 self.log_callback("ERRO: Configurações de Max Folhas ou Processos Inválidas (devem ser números inteiros).", is_error=True)
                 self._is_processing = False
                 self.set_controls_state(False)
                 return

            # Inicia o processamento em um novo thread
            self.processing_thread = threading.Thread(target=self._run_processing_thread)
            self.processing_thread.start()

    # --- Callbacks para o Backend (Thread Principal) ---

    def log(self, message: str, is_error: bool = False):
        """Callback que o backend usará para logar mensagens na UI."""
        self.log_callback(message, is_error)

    def ask_manual_correction(self, filename: str, last_folha: int, max_folhas: int) -> Dict[str, int]:
        """
        Callback que o backend usa para solicitar intervenção manual.
        
        Retorna um dicionário com a correção ou o comando de parada.
        O diálogo é exibido na thread principal via GLib.idle_add/GLib.timeout_add.
        """
        response_queue = queue.Queue()

        def show_dialog_and_wait():
            dialog = CorrectionDialog(
                parent=self.parent_window, 
                filename=filename, 
                last_folha=last_folha, 
                max_folhas=max_folhas
            )
            response = dialog.run()
            
            # Mapeia a resposta do diálogo para o resultado do backend
            result = {}
            if response == "confirm":
                corrigido = dialog.get_correction_data()
                if corrigido is not None:
                    # Registra a correção para o arquivo
                    self.correcoes_manuais[filename] = corrigido
                    result = {"action": "continue", "folha": corrigido}
                else:
                    self.log_callback("Valor de correção inválido. Parando processamento.", is_error=True)
                    result = {"action": "stop"}
            elif response == "skip":
                # Pula a correção, usa o valor sugerido (last_folha + 1)
                self.correcoes_manuais[filename] = last_folha + 1
                result = {"action": "continue", "folha": last_folha + 1}
            elif response == "stop":
                self._is_processing = False # Seta o estado para parar
                result = {"action": "stop"}
            
            dialog.destroy()
            response_queue.put(result)
            return GLib.SOURCE_REMOVE

        # Executa o diálogo na thread principal e espera o resultado
        GLib.idle_add(show_dialog_and_wait)
        
        # Bloqueia a thread do backend até que a resposta seja recebida
        return response_queue.get()

    def update_status_label(self, final_ultima_folha: int):
        """Atualiza a label de status ao final do processamento (thread-safe)."""
        if final_ultima_folha > 0:
            self.status_label.set_label(f"Processamento Concluído! Última folha processada: FL. {final_ultima_folha}")
        else:
            self.status_label.set_label("Processamento Concluído! Nenhuma folha processada.")
        self.set_controls_state(False)

    # --- Lógica de Controle da UI ---

    def set_controls_state(self, is_running: bool):
        """
        Habilita/Desabilita controles e altera o botão de Iniciar/Parar.
        Isto deve ser chamado APENAS na thread principal (via GLib.idle_add).
        """
        self._is_processing = is_running
        
        self.input_row.set_sensitive(not is_running)
        self.output_row.set_sensitive(not is_running)
        # O botão About também deve ser desativado, mas está na janela principal

        if is_running:
            self.start_button.set_label("Parar Processamento (Aguarde...)")
            self.start_button.remove_css_class("suggested-action")
            self.start_button.add_css_class("destructive-action")
            self.status_label.set_label("Processando, aguarde intervenção manual se necessário...")
        else:
            self.start_button.set_label("Iniciar Processamento")
            self.start_button.remove_css_class("destructive-action")
            self.start_button.add_css_class("suggested-action")
            if not self.input_dir or not self.output_dir:
                self.status_label.set_label("Aguardando seleção de diretórios...")
            
    # --- Lógica de Threading (Chama o Backend) ---

    def _run_processing_thread(self):
        """
        Função executada em um thread separado para chamar o backend (core.py).
        TODA a interação com a UI deve ser feita via callbacks/GLib.idle_add.
        """
        self.log_callback("Iniciando thread de processamento...")
        
        def get_is_processing_state() -> bool:
            """Permite que o backend verifique o estado de parada."""
            return self._is_processing

        def set_is_processing_state_wrapper(is_running: bool):
            """
            Permite que o backend chame uma parada de processamento (is_running=False)
            de forma thread-safe (via GLib.idle_add).
            """
            GLib.idle_add(self.set_controls_state, not is_running)

        try:
            # CHAMADA CRÍTICA AO BACKEND (FUNCIONALIDADE MANTIDA)
            final_ultima_folha = core.run_processing_logic(
                input_dir=self.input_dir,
                output_dir=self.output_dir,
                max_folhas=self.max_folhas,
                num_processes=self.num_processes,
                log_callback=self.log,
                ask_manual_correction_callback=self.ask_manual_correction,
                ultima_folha_processada=self.ultima_folha_processada or 0, 
                correcoes_manuais=self.correcoes_manuais,
                get_is_processing_state=get_is_processing_state,
                set_is_processing_state=set_is_processing_state_wrapper, 
            )

            if final_ultima_folha is not None:
                GLib.idle_add(self.update_status_label, final_ultima_folha)
                
            self.log("--- PROCESSAMENTO CONCLUÍDO ---\n")
        
        except Exception as e:
            self.log(f"\n--- ERRO CRÍTICO NO BACKEND: {e} ---", is_error=True)
            import traceback
            self.log(f"Detalhes do Erro:\n{traceback.format_exc()}", is_error=True)
        finally:
             # Garante que os controles voltem ao estado de repouso
            GLib.idle_add(self.set_controls_state, False)
