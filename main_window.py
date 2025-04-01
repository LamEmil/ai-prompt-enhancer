# main_window.py
import sys
import os
import time
import json  # Make sure json is imported for api_client potentially
import traceback  # For more detailed error printing
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtGui import QIcon, QPixmap  # For icons (if needed)

# Try importing qtawesome for icons if available with qt-material
try:
    import qtawesome as qta
    QTA_INSTALLED = True
except ImportError:
    QTA_INSTALLED = False
    print("Optional dependency 'qtawesome' not found. Icons will be basic text/emoji.")

# Import backend modules
import api_client
import config_manager
import prompt_manager
import utils

SAVED_PROMPTS_DIR = "saved_prompts"  # Keep directory name for saved files

# --- Worker Thread Classes (WorkerSignals, ApiWorker - unchanged) ---
class WorkerSignals(QtCore.QObject):
    """Defines signals available from a running worker thread."""
    finished = QtCore.Signal()
    error = QtCore.Signal(str)
    models_fetched = QtCore.Signal(list)
    generation_complete = QtCore.Signal(dict)

class ApiWorker(QtCore.QRunnable):
    """Worker thread for executing API functions."""
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.worker_name = fn.__name__ if hasattr(fn, '__name__') else 'unknown_worker'

    @QtCore.Slot()
    def run(self):
        """Execute the work function."""
        print(f"--- Worker '{self.worker_name}' started ---")
        try:
            result = self.fn(*self.args, **self.kwargs)
            print(f"--- Worker '{self.worker_name}' function executed ---")
            if self.fn == api_client.fetch_installed_models:
                print(f"--- Worker '{self.worker_name}' emitting models_fetched ---")
                self.signals.models_fetched.emit(result)
            elif self.fn == api_client.generate_text:
                print(f"--- Worker '{self.worker_name}' emitting generation_complete ---")
                self.signals.generation_complete.emit(result)
        except Exception as e:
            print(f"--- Worker '{self.worker_name}' encountered error: {e} ---")
            traceback.print_exc()
            self.signals.error.emit(str(e))
        finally:
            print(f"--- Worker '{self.worker_name}' finished ---")
            self.signals.finished.emit()

# --- Main Application Window ---
class MainWindow(QtWidgets.QMainWindow):
    # Define constants for view indices for clarity
    GENERATOR_VIEW_INDEX = 0
    PROMPT_EDITOR_VIEW_INDEX = 1  # Renamed from SAVED_PROMPTS_VIEW_INDEX
    SYSTEM_PROMPTS_VIEW_INDEX = 2
    SETTINGS_VIEW_INDEX = 3

    def __init__(self):
        super().__init__()
        self.config = config_manager.load_config()
        # --- Load initial config values ---
        self.api_endpoint = self.config.get("api_endpoint")
        self.api_type = self.config.get("api_type", "Ollama")
        self.api_key = self.config.get("api_key", "")
        self.active_system_prompt_file = self.config.get("active_system_prompt", "default.txt")
        # --- Initialize other attributes ---
        self.current_system_prompt_content = ""
        self.example_prompts_content = ""
        self.save_target_file = None  # File path for saving GENERATED prompts
        self.system_prompt_editor_dirty = False
        self.prompt_editor_dirty = False  # State for Prompt Editor page
        self.current_prompt_editor_file = None  # File loaded in Prompt Editor page

        self.threadpool = QtCore.QThreadPool()
        print(f"Multithreading with maximum {self.threadpool.maxThreadCount()} threads")

        if not os.path.exists(SAVED_PROMPTS_DIR):
            try:
                os.makedirs(SAVED_PROMPTS_DIR)
            except OSError as e:
                QtCore.QTimer.singleShot(100, lambda: self.show_error_message("Directory Error", f"Could not create directory '{SAVED_PROMPTS_DIR}': {e}"))

        self._setup_ui()
        self._connect_signals()
        QtCore.QTimer.singleShot(100, self._load_initial_data)

    # --- UI Setup ---
    def _setup_ui(self):
        """Sets up the main UI elements using a Discord-like layout."""
        self.setWindowTitle("AI Text Prompt Enhancer")
        self.setGeometry(100, 100, 1150, 850)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Left Navigation Sidebar ---
        self.nav_list = QtWidgets.QListWidget()
        self.nav_list.setObjectName("NavList")
        self.nav_list.setFixedWidth(200)
        self.nav_list.setSpacing(3)

        # Add items with text (including emoji)
        self.nav_generator_item = QtWidgets.QListWidgetItem("🚀 Prompt Generator")
        self.nav_prompt_editor_item = QtWidgets.QListWidgetItem("📝 Prompt Editor")  # Renamed item text
        self.nav_system_item = QtWidgets.QListWidgetItem("⚙️ System Prompts")
        self.nav_settings_item = QtWidgets.QListWidgetItem("🔧 Configuration")

        self.nav_list.addItem(self.nav_generator_item)
        self.nav_list.addItem(self.nav_prompt_editor_item)
        self.nav_list.addItem(self.nav_system_item)
        self.nav_list.addItem(self.nav_settings_item)

        self.nav_list.setCurrentRow(self.GENERATOR_VIEW_INDEX)
        self.nav_list.setStyleSheet("""
            QListWidget#NavList { border: none; padding-top: 10px; outline: 0; }
            QListWidget#NavList::item { padding: 12px 15px; }
        """)
        main_layout.addWidget(self.nav_list)

        # --- Right Content Area (Stacked Widget) ---
        self.stacked_widget = QtWidgets.QStackedWidget()
        self.stacked_widget.setObjectName("ContentStack")

        # Create pages
        self.generator_page = self._create_generator_page()
        self.prompt_editor_page = self._create_prompt_editor_page()
        self.system_prompts_page = self._create_system_prompts_page()
        self.settings_page = self._create_settings_page()

        # Add pages in the order corresponding to view indices constants
        self.stacked_widget.addWidget(self.generator_page)      # Index 0
        self.stacked_widget.addWidget(self.prompt_editor_page)   # Index 1
        self.stacked_widget.addWidget(self.system_prompts_page)  # Index 2
        self.stacked_widget.addWidget(self.settings_page)      # Index 3

        main_layout.addWidget(self.stacked_widget, stretch=1)

        # --- Status Bar ---
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready.")

    # --- Page Creation Methods ---
    def _create_generator_page(self):
        """Creates the content widget for the Generator Page."""
        page = QtWidgets.QWidget()
        page.setObjectName("GeneratorPage")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)

        # Model Selection
        model_group = QtWidgets.QGroupBox("AI Model")
        model_group_layout = QtWidgets.QHBoxLayout(model_group)
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.setToolTip("Select the AI model to use for generation.")
        self.model_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        model_group_layout.addWidget(self.model_combo)
        self.refresh_models_button = QtWidgets.QPushButton("Refresh")
        self.refresh_models_button.setToolTip("Refresh the list of available AI models from the API.")
        model_group_layout.addWidget(self.refresh_models_button)
        layout.addWidget(model_group)

        # Load Example Prompts
        example_group = QtWidgets.QGroupBox("Example Prompts")
        example_group_layout = QtWidgets.QHBoxLayout(example_group)
        self.load_examples_button = QtWidgets.QPushButton("Browse...")
        self.load_examples_button.setToolTip("Load a .txt file containing example prompts.")
        example_group_layout.addWidget(self.load_examples_button)
        self.example_file_label = QtWidgets.QLabel("No file loaded")
        self.example_file_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.example_file_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        example_group_layout.addWidget(self.example_file_label)
        layout.addWidget(example_group)

        # User Input
        user_input_group = QtWidgets.QGroupBox("Topic/Goal for New Prompt")
        user_input_layout = QtWidgets.QVBoxLayout(user_input_group)
        self.user_prompt_input = QtWidgets.QTextEdit()
        self.user_prompt_input.setPlaceholderText("Enter the core idea or keywords for the prompt you want to generate...")
        self.user_prompt_input.setToolTip("Describe what the generated prompt should be about.")
        self.user_prompt_input.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.user_prompt_input.setFixedHeight(120)
        user_input_layout.addWidget(self.user_prompt_input)
        layout.addWidget(user_input_group)

        # Generate Button
        self.generate_button = QtWidgets.QPushButton("✨ Generate Enhanced Prompt")
        self.generate_button.setStyleSheet("padding: 10px; font-weight: bold;")
        self.generate_button.setToolTip("Generate a new prompt based on the examples and your topic/goal.")
        layout.addWidget(self.generate_button)

        # Response Display
        response_group = QtWidgets.QGroupBox("Generated Prompt")
        response_layout = QtWidgets.QVBoxLayout(response_group)
        self.response_display = QtWidgets.QTextEdit()
        self.response_display.setReadOnly(True)
        self.response_display.setToolTip("The generated prompt will appear here.")
        self.response_display.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        response_layout.addWidget(self.response_display)
        layout.addWidget(response_group, stretch=1)

        # Save Generated Prompt Button
        self.save_gen_button = QtWidgets.QPushButton("💾 Save Generated Prompt")
        self.save_gen_button.setEnabled(False)
        self.save_gen_button.setToolTip("Save the generated prompt to the currently set target file (see Prompt Editor tab).")
        layout.addWidget(self.save_gen_button)
        return page

    def _create_prompt_editor_page(self):
        """Creates the content widget for the Prompt Editor Page."""
        page = QtWidgets.QWidget()
        page.setObjectName("PromptEditorPage")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        # --- Top Control Bar ---
        control_layout = QtWidgets.QHBoxLayout()
        control_layout.setSpacing(10)
        self.pe_open_button = QtWidgets.QPushButton("Open File...")
        self.pe_open_button.setToolTip("Open a text file to view/edit saved prompts.\nThis also sets the target file for the 'Save Generated Prompt' button.")
        control_layout.addWidget(self.pe_open_button)
        self.pe_save_button = QtWidgets.QPushButton("Save Changes")
        self.pe_save_button.setToolTip("Save modifications made in the editor TO THE CURRENTLY OPEN file.")
        self.pe_save_button.setEnabled(False)
        control_layout.addWidget(self.pe_save_button)
        self.pe_close_button = QtWidgets.QPushButton("Close File")
        self.pe_close_button.setToolTip("Close the current file, clearing the editor.\nThis also clears the target file for the 'Save Generated Prompt' button.")
        self.pe_close_button.setEnabled(False)
        control_layout.addWidget(self.pe_close_button)
        control_layout.addStretch(1)
        layout.addLayout(control_layout)

        # --- Filename Display ---
        filename_container = QtWidgets.QWidget()
        filename_layout = QtWidgets.QHBoxLayout(filename_container)
        filename_layout.setContentsMargins(0, 5, 0, 5)
        self.pe_filename_label = QtWidgets.QLabel("No file open.")
        self.pe_filename_label.setToolTip("Path of the currently open saved prompts file.")
        self.pe_filename_label.setStyleSheet("font-style: italic; color: gray;")
        filename_layout.addWidget(self.pe_filename_label)
        filename_layout.addStretch(1)
        layout.addWidget(filename_container)

        # --- Text Editor ---
        self.pe_editor = QtWidgets.QTextEdit()
        self.pe_editor.setObjectName("PromptEditor")
        self.pe_editor.setPlaceholderText("Open a file to view or edit saved prompts...")
        self.pe_editor.setToolTip("Contents of the opened saved prompts file.")
        self.pe_editor.setReadOnly(True)
        self.pe_editor.setEnabled(False)
        layout.addWidget(self.pe_editor, stretch=1)

        return page

    def _create_system_prompts_page(self):
        """Creates the content widget for the System Prompts Page."""
        page = QtWidgets.QWidget()
        page.setObjectName("SystemPromptsPage")
        main_layout = QtWidgets.QHBoxLayout(page)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(15)
        # Left Pane
        left_pane_widget = QtWidgets.QGroupBox("Presets Management")
        left_layout = QtWidgets.QVBoxLayout(left_pane_widget)
        left_layout.setSpacing(8)
        self.prompt_list_widget = QtWidgets.QListWidget()
        self.prompt_list_widget.setToolTip("List of saved system prompt presets.")
        left_layout.addWidget(self.prompt_list_widget, stretch=1)
        list_button_layout = QtWidgets.QHBoxLayout()
        self.load_preset_button = QtWidgets.QPushButton("Load")
        self.load_preset_button.setToolTip("Load the selected preset into the editor.")
        self.delete_preset_button = QtWidgets.QPushButton("Delete")
        self.delete_preset_button.setToolTip("Delete the selected preset (cannot delete default).")
        list_button_layout.addWidget(self.load_preset_button)
        list_button_layout.addWidget(self.delete_preset_button)
        left_layout.addLayout(list_button_layout)
        self.set_active_button = QtWidgets.QPushButton("Set as Active")
        self.set_active_button.setToolTip("Use the selected preset as the system prompt for generation.")
        left_layout.addWidget(self.set_active_button)
        left_layout.addStretch(0)
        # Right Pane
        right_pane_widget = QtWidgets.QWidget()
        right_pane_layout = QtWidgets.QVBoxLayout(right_pane_widget)
        right_pane_layout.setContentsMargins(0, 0, 0, 0)
        right_pane_layout.setSpacing(8)
        editor_group = QtWidgets.QGroupBox("System Prompt Editor")
        editor_layout = QtWidgets.QVBoxLayout(editor_group)
        editor_layout.setSpacing(8)
        self.system_prompt_editor = QtWidgets.QTextEdit()
        self.system_prompt_editor.setPlaceholderText("Select a preset to load or start typing a new one...")
        self.system_prompt_editor.setToolTip("Edit the content of the selected system prompt here.\nRemember to use {example_text} and {user_prompt} placeholders.")
        self.system_prompt_editor.setEnabled(False)
        editor_layout.addWidget(self.system_prompt_editor, stretch=1)
        editor_button_layout = QtWidgets.QHBoxLayout()
        self.save_as_button = QtWidgets.QPushButton("Save As New...")
        self.save_as_button.setToolTip("Save the current editor content as a new preset file.")
        self.save_button = QtWidgets.QPushButton("Save Changes")
        self.save_button.setToolTip("Save changes to the currently selected preset file.")
        self.save_button.setEnabled(False)
        editor_button_layout.addWidget(self.save_as_button)
        editor_button_layout.addWidget(self.save_button)
        editor_layout.addLayout(editor_button_layout)
        right_pane_layout.addWidget(editor_group, stretch=1)
        # Active Prompt Display
        active_prompt_frame = QtWidgets.QFrame()
        active_prompt_frame.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        active_prompt_layout = QtWidgets.QHBoxLayout(active_prompt_frame)
        active_prompt_layout.setContentsMargins(0, 10, 0, 0)
        active_prompt_label = QtWidgets.QLabel("Active System Prompt:")
        self.active_prompt_display_label = QtWidgets.QLabel(f"<b>{self.active_system_prompt_file}</b>")
        self.active_prompt_display_label.setToolTip("The system prompt currently being used for generation.")
        self.active_prompt_display_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        active_prompt_layout.addWidget(active_prompt_label)
        active_prompt_layout.addWidget(self.active_prompt_display_label)
        active_prompt_layout.addStretch(1)
        right_pane_layout.addWidget(active_prompt_frame)
        # Add panes
        main_layout.addWidget(left_pane_widget, stretch=1)
        main_layout.addWidget(right_pane_widget, stretch=3)
        return page

    def _create_settings_page(self):
        """Creates the content widget for the Settings Page."""
        page = QtWidgets.QWidget()
        page.setObjectName("SettingsPage")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        api_type_group = QtWidgets.QGroupBox("API Type")
        api_type_layout = QtWidgets.QVBoxLayout(api_type_group)
        api_type_layout.setSpacing(8)
        self.radio_ollama = QtWidgets.QRadioButton("Ollama API")
        self.radio_ollama.setToolTip("Use Ollama's native /api/generate endpoint.")
        self.radio_openai = QtWidgets.QRadioButton("OpenAI-Compatible API (LM Studio, etc.)")
        self.radio_openai.setToolTip("Use OpenAI's /v1/chat/completions format.")
        self.api_type_button_group = QtWidgets.QButtonGroup(page)
        self.api_type_button_group.addButton(self.radio_ollama)
        self.api_type_button_group.addButton(self.radio_openai)
        api_type_layout.addWidget(self.radio_ollama)
        api_type_layout.addWidget(self.radio_openai)
        layout.addWidget(api_type_group)
        api_config_group = QtWidgets.QGroupBox("API Configuration")
        api_config_layout = QtWidgets.QFormLayout(api_config_group)
        api_config_layout.setSpacing(10)
        api_config_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.endpoint_input = QtWidgets.QLineEdit()
        self.endpoint_input.setPlaceholderText("e.g., http://localhost:11434 or http://127.0.0.1:1234")
        self.endpoint_input.setToolTip("The base URL of your AI API server.")
        api_config_layout.addRow("API Endpoint URL:", self.endpoint_input)
        self.apikey_input = QtWidgets.QLineEdit()
        self.apikey_input.setPlaceholderText("Optional - Leave blank if not needed (e.g., local LM Studio)")
        self.apikey_input.setToolTip("API Key, if required by the endpoint (e.g., OpenAI).")
        self.apikey_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        api_config_layout.addRow("API Key (Optional):", self.apikey_input)
        layout.addWidget(api_config_group)
        self.save_settings_button = QtWidgets.QPushButton("Save Settings")
        self.save_settings_button.setToolTip("Save the API configuration.")
        self.save_settings_button.setStyleSheet("padding: 8px;")
        layout.addWidget(self.save_settings_button, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    # --- Signal Connections ---
    def _connect_signals(self):
        """Connect widget signals to appropriate slots."""
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        # Generator Page Widgets
        self.refresh_models_button.clicked.connect(self._update_model_list)
        self.load_examples_button.clicked.connect(self._load_example_prompts_file)
        self.generate_button.clicked.connect(self._trigger_generation)
        self.save_gen_button.clicked.connect(self._save_generated_prompt)
        # Prompt Editor Page Widgets
        self.pe_open_button.clicked.connect(self._pe_open_file)
        self.pe_save_button.clicked.connect(self._pe_save_file)
        self.pe_close_button.clicked.connect(self._pe_close_file)
        self.pe_editor.textChanged.connect(self._pe_mark_dirty)
        # System Prompt Page Widgets
        self.prompt_list_widget.currentItemChanged.connect(self._on_preset_select)
        self.load_preset_button.clicked.connect(self._load_selected_preset_from_button)
        self.delete_preset_button.clicked.connect(self._delete_selected_preset)
        self.set_active_button.clicked.connect(self._set_active_preset)
        self.system_prompt_editor.textChanged.connect(self._mark_dirty)
        self.save_button.clicked.connect(self._save_preset)
        self.save_as_button.clicked.connect(self._save_preset_as)
        # Settings Page Widgets
        self.save_settings_button.clicked.connect(self._save_settings)

    # --- Navigation Slot ---
    def _on_nav_changed(self, current_row):
        """Switches the view in the QStackedWidget based on nav list selection."""
        print(f">>> _on_nav_changed called. Row: {current_row}")
        previous_index = self.stacked_widget.currentIndex()
        print(f"   Previous view index: {previous_index}")
        can_switch = True
        # Check System Prompts
        if previous_index == self.SYSTEM_PROMPTS_VIEW_INDEX and self.system_prompt_editor_dirty:
            print("   Switching away from dirty System Prompts view. Asking confirmation.")
            can_switch = self.confirm_action("Unsaved Changes", "Discard unsaved changes in the system prompt editor?")
            if can_switch:
                self._clear_dirty_flag()
        # Check Prompt Editor
        elif previous_index == self.PROMPT_EDITOR_VIEW_INDEX and self.prompt_editor_dirty:
            print("   Switching away from dirty Prompt Editor view. Asking confirmation.")
            can_switch = self.confirm_action("Unsaved Changes", "Discard unsaved changes to the saved prompts file?")
            if can_switch:
                self._pe_clear_dirty_flag()
        # Perform switch or revert
        if can_switch:
            print(f"   Switching stacked widget to index: {current_row}")
            self.stacked_widget.setCurrentIndex(current_row)
            # Update Prompt Editor view if switching TO it
            if current_row == self.PROMPT_EDITOR_VIEW_INDEX:
                print("   Switched TO Prompt Editor view. Checking sync.")
                if self.save_target_file and self.save_target_file != self.current_prompt_editor_file:
                    print(f"   Main save target differs. Loading.")
                    self._load_file_into_pe_editor(self.save_target_file)
                elif not self.save_target_file and self.current_prompt_editor_file:
                    print("   Main save target None, editor has file. Closing editor.")
                    self._pe_close_file(force=True)
                elif not self.save_target_file and not self.current_prompt_editor_file:
                    print("   No save target, no file in editor. Sync ok (empty).")
                    if hasattr(self, 'pe_editor'):
                        self.pe_editor.clear()
                        self.pe_editor.setEnabled(False)
                        self.pe_editor.setReadOnly(True)
                        self.pe_save_button.setEnabled(False)
                        self.pe_close_button.setEnabled(False)
                        self.pe_filename_label.setText("No file open.")
                        self.pe_filename_label.setStyleSheet("font-style: italic; color: gray;")
        else:
            print("   User cancelled switch. Reverting selection.")
            self.nav_list.blockSignals(True)
            self.nav_list.setCurrentRow(previous_index)
            self.nav_list.blockSignals(False)
        print(f"<<< _on_nav_changed finished. Current view index: {self.stacked_widget.currentIndex()}")

    # --- Settings Slot ---
    def _save_settings(self):
        """Saves the current settings from the UI to config and updates state."""
        print(">>> _save_settings called")
        selected_api_type = "Ollama"
        if self.radio_openai.isChecked():
            selected_api_type = "OpenAI"
        print(f"   Selected API Type: {selected_api_type}")
        endpoint = self.endpoint_input.text().strip().rstrip('/')
        api_key = self.apikey_input.text()
        if not endpoint:
            self.show_error_message("Settings Error", "API Endpoint URL cannot be empty.")
            return
        if not (endpoint.startswith("http://") or endpoint.startswith("https://")):
            self.show_error_message("Settings Error", "API Endpoint URL must start with http:// or https://")
            return
        print(f"   Endpoint: {endpoint}")
        self.api_type = selected_api_type
        self.api_endpoint = endpoint
        self.api_key = api_key
        self._save_config()
        self.show_info_message("Settings Saved", "API settings saved.\nModel list will refresh.")
        self.status_bar.showMessage("Settings saved. Refreshing models...")
        print("   Triggering model list refresh.")
        self._update_model_list()

    # --- Initial Data Loading ---
    def _load_initial_data(self):
        """Loads models, presets, active prompt, and settings on startup."""
        print("--- Starting initial data load ---")
        self.status_bar.showMessage("Initializing...")
        print(f"   Loading settings: Type='{self.api_type}', Endpoint='{self.api_endpoint}', Key set={'Yes' if self.api_key else 'No'}")
        if hasattr(self, 'endpoint_input'):
            self.endpoint_input.setText(self.api_endpoint)
            self.apikey_input.setText(self.api_key)
            if self.api_type == "OpenAI":
                self.radio_openai.setChecked(True)
            else:
                self.radio_ollama.setChecked(True)
        else:
            print("   Warning: Settings UI elements not found during initial load.")
        self._update_model_list()
        self._update_preset_list()
        print(f"   Configured active prompt: {self.active_system_prompt_file}")
        needs_config_save = False
        list_items = [self.prompt_list_widget.item(i).text() for i in range(self.prompt_list_widget.count())]
        print(f"   Available presets: {list_items}")
        if self.active_system_prompt_file not in list_items:
            print(f"   WARNING: Active prompt '{self.active_system_prompt_file}' not found.")
            self.active_system_prompt_file = prompt_manager.DEFAULT_PROMPT_NAME
            needs_config_save = True
            print(f"   Forcing active prompt to default: {self.active_system_prompt_file}")
        else:
            print(f"   Configured active prompt '{self.active_system_prompt_file}' found.")
        self._load_active_system_prompt_content()
        if self.current_system_prompt_content.startswith("Error loading"):
            print(f"   ERROR: Failed loading active prompt '{self.active_system_prompt_file}'. Attempting default.")
            if self.active_system_prompt_file != prompt_manager.DEFAULT_PROMPT_NAME:
                self.active_system_prompt_file = prompt_manager.DEFAULT_PROMPT_NAME
                self._load_active_system_prompt_content()
                needs_config_save = True
            if self.current_system_prompt_content.startswith("Error loading"):
                QtCore.QTimer.singleShot(100, lambda: self.show_error_message("Init Error", f"Failed to load default system prompt '{prompt_manager.DEFAULT_PROMPT_NAME}'. Check file."))
        if needs_config_save:
            self._save_config()
        self._update_active_prompt_display()
        print(f"   Attempting to select '{self.active_system_prompt_file}' in list.")
        final_active_items = self.prompt_list_widget.findItems(self.active_system_prompt_file, QtCore.Qt.MatchFlag.MatchExactly)
        if final_active_items:
            self.prompt_list_widget.setCurrentItem(final_active_items[0])
            print(f"   Selected '{self.active_system_prompt_file}'.")
            self._load_selected_preset()
        elif self.prompt_list_widget.count() > 0:
            print("   ERROR: Active prompt not found. Selecting first.")
            self.prompt_list_widget.setCurrentRow(0)
            self._load_selected_preset()
        else:
            print("   ERROR: No system presets found.")
            QtCore.QTimer.singleShot(100, lambda: self.show_error_message("Init Error", "No system presets found."))
            self.system_prompt_editor.setEnabled(False)
        self.nav_list.setCurrentRow(self.GENERATOR_VIEW_INDEX)
        self.stacked_widget.setCurrentIndex(self.GENERATOR_VIEW_INDEX)
        self.status_bar.showMessage("Ready.")
        print("--- Initial data load finished ---")

    # --- Load Active Prompt Content ---
    def _load_active_system_prompt_content(self):
        """Loads the text content of the active prompt file into self.current_system_prompt_content."""
        filename_to_load = self.active_system_prompt_file
        print(f"--- Loading active system prompt: {filename_to_load} ---")
        content = prompt_manager.load_prompt_text(filename_to_load)
        if content is None:
            print(f"   ERROR loading {filename_to_load}")
            self.current_system_prompt_content = f"Error loading {filename_to_load}"
        elif content == "" and filename_to_load != prompt_manager.DEFAULT_PROMPT_NAME:
            print(f"   Loaded empty non-default: {filename_to_load}")
            self.current_system_prompt_content = ""
        else:
            print(f"   Successfully loaded content: {filename_to_load}")
            self.current_system_prompt_content = content

    # --- Helper Methods ---
    def show_error_message(self, title, message):
        """Displays a critical error message box."""
        print(f"!! ERROR: {title} - {message}")
        try:
            msg_str = str(message) if message is not None else "An unknown error occurred."
            QtWidgets.QMessageBox.critical(self, title, msg_str)
        except RuntimeError as e:
            print(f"!! Could not display error message box: {e}")
        except Exception as e:
            print(f"!! Unexpected error displaying error message box: {e}")

    def show_warning_message(self, title, message):
        """Displays a warning message box."""
        print(f"?? WARNING: {title} - {message}")
        try:
            msg_str = str(message) if message is not None else "Unknown warning."
            QtWidgets.QMessageBox.warning(self, title, msg_str)
        except RuntimeError as e:
            print(f"!! Could not display warning message box: {e}")
        except Exception as e:
            print(f"!! Unexpected error displaying warning message box: {e}")

    def show_info_message(self, title, message):
        """Displays an information message box."""
        print(f".. INFO: {title} - {message}")
        try:
            msg_str = str(message) if message is not None else "Information."
            QtWidgets.QMessageBox.information(self, title, msg_str)
        except RuntimeError as e:
            print(f"!! Could not display info message box: {e}")
        except Exception as e:
            print(f"!! Unexpected error displaying info message box: {e}")

    def confirm_action(self, title, message):
        """Displays a confirmation (Yes/No) message box."""
        print(f"?? CONFIRM: {title} - {message}")
        try:
            msg_str = str(message) if message is not None else "Confirm action?"
            reply = QtWidgets.QMessageBox.question(self, title, msg_str,
                                                   QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                                                   QtWidgets.QMessageBox.StandardButton.No)  # Default to No
            confirmed = reply == QtWidgets.QMessageBox.StandardButton.Yes
            print(f"   User confirmation: {confirmed}")
            return confirmed
        except RuntimeError as e:
            print(f"!! Could not display confirmation box: {e}")
            return False
        except Exception as e:
            print(f"!! Unexpected error displaying confirmation box: {e}")
            return False

    def _set_busy_state(self, busy):
        """Enable/disable relevant controls and set cursor."""
        if busy:
            print(">>> Setting busy: TRUE")
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        else:
            print("<<< Setting busy: FALSE")
            if QtWidgets.QApplication.overrideCursor() is not None:
                QtWidgets.QApplication.restoreOverrideCursor()
            else:
                print("    (Skipped restore cursor)")
        is_enabled = not busy
        if hasattr(self, 'generate_button'):
            self.generate_button.setEnabled(is_enabled)
        if hasattr(self, 'refresh_models_button'):
            self.refresh_models_button.setEnabled(is_enabled)
        if hasattr(self, 'load_examples_button'):
            self.load_examples_button.setEnabled(is_enabled)
        if hasattr(self, 'model_combo'):
            self.model_combo.setEnabled(is_enabled)
        if hasattr(self, 'user_prompt_input'):
            self.user_prompt_input.setEnabled(is_enabled)
        if hasattr(self, 'save_settings_button'):
            self.save_settings_button.setEnabled(is_enabled)
        if hasattr(self, 'endpoint_input'):
            self.endpoint_input.setEnabled(is_enabled)
        if hasattr(self, 'apikey_input'):
            self.apikey_input.setEnabled(is_enabled)
        if hasattr(self, 'radio_ollama'):
            self.radio_ollama.setEnabled(is_enabled)
        if hasattr(self, 'radio_openai'):
            self.radio_openai.setEnabled(is_enabled)
        if hasattr(self, 'nav_list'):
            self.nav_list.setEnabled(is_enabled)

    def _save_config(self):
        """Saves the current configuration state."""
        print("--- Saving configuration ---")
        self.config["api_type"] = self.api_type
        self.config["api_endpoint"] = self.api_endpoint
        self.config["api_key"] = self.api_key
        self.config["active_system_prompt"] = self.active_system_prompt_file
        config_manager.save_config(self.config)
        print(f"   Config saved: Type='{self.api_type}', Endpoint='{self.api_endpoint}', Key set={'Yes' if self.api_key else 'No'}, ActivePrompt='{self.active_system_prompt_file}'")

    def _update_active_prompt_display(self):
        """Updates the label showing the active system prompt filename."""
        print(f"--- Updating active prompt display to: {self.active_system_prompt_file} ---")
        if hasattr(self, 'active_prompt_display_label'):
            self.active_prompt_display_label.setText(f"<b>{self.active_system_prompt_file}</b>")

    # --- Model List Handling ---
    def _update_model_list(self):
        """Fetches models using the worker thread based on current settings."""
        print(">>> _update_model_list called")
        current_api_type = self.api_type
        current_api_endpoint = self.api_endpoint
        current_api_key = self.api_key
        self.status_bar.showMessage(f"Fetching models ({current_api_type})...")
        self._set_busy_state(True)
        worker = ApiWorker(api_client.fetch_installed_models, current_api_endpoint, current_api_type, current_api_key)
        worker.signals.models_fetched.connect(self._on_models_fetched)
        worker.signals.error.connect(self._on_worker_error)
        self.threadpool.start(worker)
        print(f"--- Model fetch worker started (Type: {current_api_type}) ---")

    def _on_models_fetched(self, models):
        """Updates the model combobox."""
        print(">>> _on_models_fetched called")
        current_selection = self.model_combo.currentText()
        self.model_combo.clear()
        if models:
            self.model_combo.addItems(models)
            if current_selection in models:
                self.model_combo.setCurrentText(current_selection)
            elif self.model_combo.count() > 0:
                self.model_combo.setCurrentIndex(0)
            self.status_bar.showMessage(f"{len(models)} models loaded ({self.api_type}).")
            print(f"   Loaded models: {models}")
        else:
            self.model_combo.addItem(f"No models found ({self.api_type})")
            self.status_bar.showMessage(f"No models found ({self.api_type}). Check API.")
            print("   No models found.")
        self._set_busy_state(False)
        print("<<< _on_models_fetched finished")

    def _on_worker_error(self, error_message):
        """Handles errors reported by ANY worker thread."""
        print(f">>> _on_worker_error: {error_message}")
        self._set_busy_state(False)
        self.show_error_message("API Error", error_message)
        self.status_bar.showMessage("API fail.")
        print("<<< _on_worker_error finished")

    # --- Generator Tab Slot Methods ---
    def _load_example_prompts_file(self):
        """Opens file dialog to load example prompts."""
        print(">>> _load_example_prompts_file")
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Example File", "", "Text Files (*.txt);;All (*.*)")
        if file_path:
            print(f"   Selected: {file_path}")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.example_prompts_content = content
                base_name = os.path.basename(file_path)
                self.example_file_label.setText(base_name)
                self.example_file_label.setToolTip(file_path)
                self.status_bar.showMessage(f"Loaded: {base_name}")
                print("   Load OK.")
            except Exception as e:
                print(f"   ERROR reading: {e}")
                self.show_error_message("File Error", f"Failed: {e}")
                self.example_prompts_content = ""
                self.example_file_label.setText("Error load")
                self.example_file_label.setToolTip("")
                self.status_bar.showMessage("Error load.")
        else:
            print("   Load cancelled.")

    def _trigger_generation(self):
        """Validates input and starts the generation worker thread."""
        print(">>> _trigger_generation")
        selected_model = self.model_combo.currentText()
        user_input = self.user_prompt_input.toPlainText().strip()
        example_text = self.example_prompts_content
        system_prompt_template = self.current_system_prompt_content
        print("   Validating...")
        if not selected_model or "model" in selected_model.lower() or "No models" in selected_model:
            self.show_warning_message("Input Error", "Select valid model.")
            print("   Fail: No model.")
            return
        if not user_input:
            self.show_warning_message("Input Error", "Describe topic/goal.")
            print("   Fail: No input.")
            return
        if not self.example_prompts_content:
            self.show_warning_message("Input Error", "Load examples file.")
            print("   Fail: No examples.")
            return
        if not system_prompt_template or system_prompt_template.startswith("Error loading"):
            self.show_warning_message("System Prompt Error", "Active system prompt invalid/missing.")
            print(f"   Fail: Invalid sys prompt: '{system_prompt_template[:50]}...'")
            return
        print("   Validation OK.")
        self.status_bar.showMessage(f"Sending ({self.api_type})...")
        self.response_display.setPlainText("Generating...")
        self.response_display.setReadOnly(True)
        self.save_gen_button.setEnabled(False)
        self._set_busy_state(True)
        worker = ApiWorker(api_client.generate_text, self.api_endpoint, self.api_type, selected_model, system_prompt_template, user_input, example_text, self.api_key)
        worker.signals.generation_complete.connect(self._on_generation_complete)
        worker.signals.error.connect(self._on_worker_error)
        self.threadpool.start(worker)
        print(f"--- Gen worker started (Type: {self.api_type}) ---")

    def _on_generation_complete(self, result):
        """Handles the result from the generation worker."""
        print(">>> _on_generation_complete")
        success = False
        if "response" in result:
            cleaned_response = utils.process_response(result["response"])
            if cleaned_response:
                print("   Gen successful.")
                self.response_display.setPlainText(cleaned_response)
                self.status_bar.showMessage("Gen OK.")
                success = True
            else:
                print("   Gen empty response.")
                self.response_display.setPlainText("Received empty response.")
                self.status_bar.showMessage("Empty response.")
        elif "error" in result:
            error_msg = f"Error: {result['error']}"
            print(f"   Gen failed: {error_msg}")
            self.response_display.setPlainText(error_msg)
            self.status_bar.showMessage("Gen fail.")
        else:
            print("   Gen fail: Unknown response.")
            self.response_display.setPlainText("Error: Unknown response.")
            self.status_bar.showMessage("Gen fail: Unknown.")
        self.response_display.setReadOnly(not success)
        self.save_gen_button.setEnabled(success)
        self._set_busy_state(False)
        print("<<< _on_generation_complete finished")

    def _ask_save_target_file(self):
        """Asks the user to select/create a file for saving GENERATED prompts."""
        print(">>> _ask_save_target_file (from Gen Page save)")
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Set Save File", SAVED_PROMPTS_DIR, "Text (*.txt);;All (*.*)")
        if filepath:
            print(f"   User selected: {filepath}")
            self.save_target_file = filepath
            if hasattr(self, 'pe_editor'):
                print("   Updating Prompt Editor view.")
                if self.prompt_editor_dirty:
                    current_fn = os.path.basename(self.current_prompt_editor_file) if self.current_prompt_editor_file else "prev file"
                    new_fn = os.path.basename(filepath)
                    if self.confirm_action("Unsaved Changes", f"Set new save file ('{new_fn}'). Discard unsaved changes in Editor for '{current_fn}'?"):
                        self._load_file_into_pe_editor(filepath)
                    else:
                        print("   User kept editor changes (out of sync).")
                        self.pe_filename_label.setText(f"{os.path.basename(self.current_prompt_editor_file)}* (Out of sync)")
                        self.pe_filename_label.setStyleSheet("font-style: italic; color: orange;")
                else:
                    self._load_file_into_pe_editor(filepath)
            return True
        else:
            print("   User cancelled save target.")
            self.save_target_file = None
            return False

    def _save_generated_prompt(self):
        """Saves the content of the response display to the target file AND refreshes editor."""
        print(">>> _save_generated_prompt")
        generated_text = self.response_display.toPlainText().strip()
        if not generated_text or "Generating..." in generated_text or "Error:" in generated_text:
            self.show_warning_message("Save Error", "No valid prompt to save.")
            print("   Save cancel: No valid text.")
            return
        if self.save_target_file is None:
            print("   Save target None, asking...")
            if not self._ask_save_target_file():
                print("   Save cancel: No file path.")
                return
        print(f"   Saving to: {self.save_target_file}")
        try:
            add_sep = os.path.exists(self.save_target_file) and os.path.getsize(self.save_target_file) > 0
            mode = "a"
            print(f"   Mode: {mode}, Sep: {add_sep}")
            with open(self.save_target_file, mode, encoding="utf-8") as f:
                if add_sep:
                    f.write("\n\n" + "=" * 20 + "\n\n")
                f.write(generated_text)
            base_name = os.path.basename(self.save_target_file)
            self.status_bar.showMessage(f"Appended to {base_name}")
            print(f"   Appended OK: {base_name}")
            # Refresh Prompt Editor if this file is open
            if hasattr(self, 'pe_editor') and self.save_target_file == self.current_prompt_editor_file:
                print("   Appending matched open editor file. Reloading.")
                if self.prompt_editor_dirty:
                    if self.confirm_action("File Updated", "File updated externally. Discard editor changes to see update?"):
                        print("    Reloading (discarding editor changes).")
                        self._load_file_into_pe_editor(self.save_target_file)
                    else:
                        print("    User kept editor changes (won't see append).")
                        self.pe_filename_label.setText(f"{os.path.basename(self.current_prompt_editor_file)}* (External change)")
                        self.pe_filename_label.setStyleSheet("font-style: italic; color: orange;")
                else:
                    print("    Editor clean, reloading automatically.")
                    self._load_file_into_pe_editor(self.save_target_file)
        except IOError as e:
            print(f"   ERROR IOError: {e}")
            self.show_error_message("Save Error", f"IOError writing:\n{self.save_target_file}\n\n{e}")
        except Exception as e:
            print(f"   ERROR Exception: {e}")
            self.show_error_message("Save Error", f"Unexpected save error:\n{e}")

    # --- Prompt Editor Slots ---
    def _pe_open_file(self):
        """Opens a file dialog to select a save target file and loads it."""
        print(">>> _pe_open_file")
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Saved File", SAVED_PROMPTS_DIR, "Text (*.txt);;All (*.*)")
        if filepath:
            print(f"   User selected: {filepath}")
            if self.prompt_editor_dirty and not self.confirm_action("Unsaved", "Discard editor changes?"):
                print("   Open cancel: Unsaved.")
                return
            self._load_file_into_pe_editor(filepath)
        else:
            print("   Open cancelled.")

    def _load_file_into_pe_editor(self, filepath):
        """Loads the content of the given filepath into the Prompt Editor."""
        print(f"--- Loading '{filepath}' into PE ---")
        try:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Not found: {filepath}")
            with open(filepath, "r", encoding='utf-8') as f:
                content = f.read()
            self.save_target_file = filepath
            self.current_prompt_editor_file = filepath
            self.pe_editor.setPlainText(content)
            base_name = os.path.basename(filepath)
            self.pe_filename_label.setText(base_name)
            self.pe_filename_label.setToolTip(filepath)
            self.pe_filename_label.setStyleSheet("")
            self.pe_editor.setEnabled(True)
            self.pe_editor.setReadOnly(False)
            self.pe_close_button.setEnabled(True)
            self._pe_clear_dirty_flag()
            self.status_bar.showMessage(f"Opened: {base_name}")
            print("   PE Load OK.")
        except Exception as e:
            print(f"   ERROR reading file '{filepath}': {e}")
            self.show_error_message("File Error", f"Read fail:\n{filepath}\n\n{e}")
            self._pe_close_file(force=True)

    def _pe_save_file(self):
        """Saves the current content of the Prompt Editor to its file."""
        print(">>> _pe_save_file")
        if not self.current_prompt_editor_file:
            self.show_warning_message("Save Error", "No file open.")
            print("   Save fail: No file open.")
            return
        if not self.prompt_editor_dirty:
            print("   Save skip: No changes.")
            return
        content_to_save = self.pe_editor.toPlainText()
        print(f"   Saving to: {self.current_prompt_editor_file}")
        try:
            with open(self.current_prompt_editor_file, "w", encoding='utf-8') as f:
                f.write(content_to_save)
            print("   Save OK.")
            self.status_bar.showMessage(f"Saved: {os.path.basename(self.current_prompt_editor_file)}")
            self._pe_clear_dirty_flag()
        except Exception as e:
            print(f"   ERROR save: {e}")
            self.show_error_message("Save Error", f"Save fail:\n{self.current_prompt_editor_file}\n\n{e}")

    def _pe_close_file(self, force=False):
        """Closes the currently open file in the Prompt Editor."""
        print(">>> _pe_close_file")
        if not self.current_prompt_editor_file:
            print("   No file open.")
            return
        if not force and self.prompt_editor_dirty:
            print("   Dirty, confirm close.")
            if not self.confirm_action("Unsaved", "Discard editor changes?"):
                print("   Close cancel.")
                return
        print(f"   Closing: {self.current_prompt_editor_file}")
        self.pe_editor.clear()
        self.pe_editor.setEnabled(False)
        self.pe_editor.setReadOnly(True)
        self.pe_filename_label.setText("No file open.")
        self.pe_filename_label.setToolTip("")
        self.pe_filename_label.setStyleSheet("font-style: italic; color: gray;")
        if self.current_prompt_editor_file == self.save_target_file:
            print("   Clearing main save target.")
            self.save_target_file = None
            if hasattr(self, 'save_gen_button'):
                self.save_gen_button.setEnabled(False)
        self.current_prompt_editor_file = None
        self._pe_clear_dirty_flag()
        self.pe_save_button.setEnabled(False)
        self.pe_close_button.setEnabled(False)
        self.status_bar.showMessage("Prompt file closed.")

    def _pe_mark_dirty(self):
        """Marks the Prompt Editor as dirty."""
        if self.pe_editor.isEnabled() and not self.pe_editor.isReadOnly():
            if not self.prompt_editor_dirty:
                print("--- PE dirty ---")
            self.prompt_editor_dirty = True
            self.pe_save_button.setEnabled(self.current_prompt_editor_file is not None)

    def _pe_clear_dirty_flag(self):
        """Marks the Prompt Editor as clean."""
        if self.prompt_editor_dirty:
            print("--- PE dirty flag cleared ---")
        self.prompt_editor_dirty = False
        if hasattr(self, 'pe_save_button'):
            self.pe_save_button.setEnabled(False)

    # --- System Prompt Tab Slot Methods ---
    def _get_selected_preset_item(self):
        selected_items = self.prompt_list_widget.selectedItems()
        return selected_items[0] if selected_items else None

    def _on_preset_select(self, current_item, previous_item):
        current_text = current_item.text() if current_item else "None"
        previous_text = previous_item.text() if previous_item else "None"
        print(f">>> _on_preset_select: C={current_text}, P={previous_text}")
        if self.system_prompt_editor_dirty:
            print("   Sys dirty, confirm.")
            if self.confirm_action("Unsaved", "Discard sys prompt changes?"):
                print("   Discard OK.")
                self._load_selected_preset()
            else:
                print("   Discard cancel, revert.")
                self.prompt_list_widget.blockSignals(True)
                if previous_item:
                    self.prompt_list_widget.setCurrentItem(previous_item)
                self.prompt_list_widget.blockSignals(False)
                print("<<< _on_preset_select (reverted).")
                return
        else:
            print("   Sys clean, load.")
            self._load_selected_preset()
        print("<<< _on_preset_select finished.")

    def _load_selected_preset_from_button(self):
        print(">>> _load_preset_btn")
        self._load_selected_preset()
        print("<<< _load_preset_btn finished")

    def _load_selected_preset(self):
        print(">>> _load_selected_preset")
        selected_item = self.prompt_list_widget.currentItem()
        if selected_item:
            filename = selected_item.text()
            print(f"   Loading: {filename}")
            content = prompt_manager.load_prompt_text(filename)
            self.system_prompt_editor.setEnabled(True)
            if content is not None:
                print("   Load OK.")
                self.system_prompt_editor.setPlainText(content)
                self.status_bar.showMessage(f"Loaded: {filename}")
            else:
                print(f"   ERROR load: {filename}.")
                self.system_prompt_editor.setPlainText(f"# Error: {filename}")
                self.system_prompt_editor.setEnabled(False)
            self._clear_dirty_flag()
            print("   Sys editor updated, dirty clear.")
        else:
            print("   No selection, clear.")
            self.system_prompt_editor.clear()
            self.system_prompt_editor.setEnabled(False)
            self.status_bar.showMessage("Select preset.")
            self._clear_dirty_flag()
        print("<<< _load_selected_preset finished")

    def _save_preset(self):
        print(">>> _save_preset")
        selected_item = self.prompt_list_widget.currentItem()
        if not selected_item:
            self.show_warning_message("Save Error", "No preset selected.")
            print("   Save fail: No selection.")
            return
        filename = selected_item.text()
        content = self.system_prompt_editor.toPlainText().strip()
        print(f"   Saving: {filename}")
        if prompt_manager.save_prompt_text(filename, content):
            print("   Save OK.")
            self.status_bar.showMessage(f"Saved: {filename}")
            self._clear_dirty_flag()
            if filename == self.active_system_prompt_file:
                print("   Saved active, update cache.")
                self.current_system_prompt_content = content
        else:
            print("   Save fail.")
            self.status_bar.showMessage(f"Save fail: {filename}'.")
        print("<<< _save_preset finished")

    def _save_preset_as(self):
        print(">>> _save_preset_as")
        content = self.system_prompt_editor.toPlainText().strip()
        filename_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Sys Preset As", prompt_manager.PROMPT_DIR, "Text (*.txt);;All (*.*)")
        if filename_path:
            base_filename = os.path.basename(filename_path)
            print(f"   Save As: {base_filename}")
            if base_filename.lower() == prompt_manager.DEFAULT_PROMPT_NAME.lower():
                self.show_warning_message("Save Prevented", f"Cannot overwrite default '{prompt_manager.DEFAULT_PROMPT_NAME}'.")
                print("   Save prevent: Overwrite default.")
                return
            if prompt_manager.save_prompt_text(base_filename, content):
                print("   Save As OK.")
                self.status_bar.showMessage(f"Saved new: {base_filename}'.")
                self._update_preset_list()
                items = self.prompt_list_widget.findItems(base_filename, QtCore.Qt.MatchFlag.MatchExactly)
                if items:
                    print(f"   Selecting new: {base_filename}'.")
                    self.prompt_list_widget.setCurrentItem(items[0])
            else:
                print("   Save As fail.")
                self.status_bar.showMessage(f"Save As fail: {base_filename}'.")
        else:
            print("   Save As cancel.")
        print("<<< _save_preset_as finished")

    def _delete_selected_preset(self):
        print(">>> _delete_selected_preset")
        selected_item = self.prompt_list_widget.currentItem()
        if not selected_item:
            self.show_warning_message("Delete Error", "No preset selected.")
            print("   Delete fail: No selection.")
            return
        filename = selected_item.text()
        print(f"   Attempt delete: {filename}")
        if filename.lower() == prompt_manager.DEFAULT_PROMPT_NAME.lower():
            self.show_warning_message("Delete Prevented", f"Cannot delete default '{prompt_manager.DEFAULT_PROMPT_NAME}'.")
            print("   Delete prevent: default.")
            return
        if prompt_manager.delete_prompt_preset(filename):
            print(f"   Delete OK: {filename}.")
            self.status_bar.showMessage(f"Deleted: {filename}'.")
            if filename == self.active_system_prompt_file:
                print("   Deleted active. Reset default.")
                self.show_info_message("Active Deleted", f"Active '{filename}' deleted. Reset default.")
                self.active_system_prompt_file = prompt_manager.DEFAULT_PROMPT_NAME
                self._load_active_system_prompt_content()
                self._save_config()
                self._update_active_prompt_display()
            current_row = self.prompt_list_widget.currentRow()
            print(f"   Updating list after delete. Row was: {current_row}")
            self._update_preset_list()
            new_row = -1
            if self.prompt_list_widget.count() > 0:
                new_row = min(current_row, self.prompt_list_widget.count() - 1)
                if new_row >= 0:
                    self.prompt_list_widget.setCurrentRow(new_row)
                    print(f"   Set row: {new_row}")
                else:
                    print("   Could not get new row.")
                    self._load_selected_preset()
            else:
                print("   List empty.")
                self._load_selected_preset()
        else:
            print(f"   Delete cancel/fail: {filename}.")
            self.status_bar.showMessage(f"Delete fail: {filename}'.")
        print("<<< _delete_selected_preset finished")

    def _set_active_preset(self):
        print(">>> _set_active_preset")
        selected_item = self.prompt_list_widget.currentItem()
        if not selected_item:
            self.show_warning_message("Set Active Error", "No preset selected.")
            print("   Set active fail: No selection.")
            return
        filename = selected_item.text()
        print(f"   Setting active: {filename}")
        self.active_system_prompt_file = filename
        self._load_active_system_prompt_content()
        self._save_config()
        self._update_active_prompt_display()
        self.status_bar.showMessage(f"'{filename}' is now active.")
        print("<<< _set_active_preset finished")

    def _update_preset_list(self):
        print("--- Updating preset list ---")
        selected_text = self.prompt_list_widget.currentItem().text() if self.prompt_list_widget.currentItem() else None
        print(f"   Prev select: {selected_text}")
        self.prompt_list_widget.blockSignals(True)
        self.prompt_list_widget.clear()
        presets = prompt_manager.get_prompt_presets()
        print(f"   Found: {presets}")
        self.prompt_list_widget.addItems(presets)
        self.prompt_list_widget.blockSignals(False)
        new_selection_restored = False
        if selected_text:
            items = self.prompt_list_widget.findItems(selected_text, QtCore.Qt.MatchFlag.MatchExactly)
            if items:
                self.prompt_list_widget.blockSignals(True)
                self.prompt_list_widget.setCurrentItem(items[0])
                self.prompt_list_widget.blockSignals(False)
                new_selection_restored = True
                print(f"   Restored select: {selected_text}")
            else:
                print(f"   Cannot restore select: {selected_text}")
        if not new_selection_restored:
            if self.prompt_list_widget.count() > 0:
                self.prompt_list_widget.blockSignals(True)
                self.prompt_list_widget.setCurrentRow(0)
                self.prompt_list_widget.blockSignals(False)
                print("   Manual load first item.")
                self._load_selected_preset()
                print("   Selected first item.")
            else:
                self._load_selected_preset()
                print("   List empty after update.")
        print("--- Preset list updated ---")

    # --- Editor Dirty Flag Management ---
    def _mark_dirty(self):
        """Handles textChanged for the System Prompt editor."""
        if self.system_prompt_editor.isEnabled() and not self.system_prompt_editor.signalsBlocked():
            if not self.system_prompt_editor_dirty:
                print("--- Sys prompt dirty ---")
            self.system_prompt_editor_dirty = True
            self.save_button.setEnabled(self.prompt_list_widget.currentItem() is not None)

    def _clear_dirty_flag(self):
        """Clears dirty flag for the System Prompt editor."""
        if self.system_prompt_editor_dirty:
            print("--- Sys prompt dirty clear ---")
        self.system_prompt_editor_dirty = False
        self.save_button.setEnabled(False)

    def _pe_mark_dirty(self):
        """Handles textChanged for the Prompt Editor (Saved Prompts)."""
        if self.pe_editor.isEnabled() and not self.pe_editor.isReadOnly():
            if not self.prompt_editor_dirty:
                print("--- PE dirty ---")
            self.prompt_editor_dirty = True
            self.pe_save_button.setEnabled(self.current_prompt_editor_file is not None)

    def _pe_clear_dirty_flag(self):
        """Clears dirty flag for the Prompt Editor (Saved Prompts)."""
        if self.prompt_editor_dirty:
            print("--- PE dirty flag cleared ---")
        self.prompt_editor_dirty = False
        if hasattr(self, 'pe_save_button'):
            self.pe_save_button.setEnabled(False)

    # --- Application Closing ---
    def closeEvent(self, event):
        """Handles the close event, checks for unsaved changes."""
        print(">>> closeEvent called")
        can_close = True
        dirty_view_index = -1
        # Check system prompt editor
        if self.system_prompt_editor_dirty:
            print("   Sys prompt dirty, confirm.")
            can_close = self.confirm_action("Exit", "Discard sys prompt changes?")
            if not can_close:
                dirty_view_index = self.SYSTEM_PROMPTS_VIEW_INDEX
        # Check prompt editor
        if can_close and self.prompt_editor_dirty:
            print("   Prompt editor dirty, confirm.")
            can_close = self.confirm_action("Exit", "Discard saved prompt file changes?")
            if not can_close:
                dirty_view_index = self.PROMPT_EDITOR_VIEW_INDEX
        # Final Action
        if can_close:
            print("   Closing OK.")
            event.accept()
        else:
            print("   Close cancelled.")
            event.ignore()
            if dirty_view_index != -1 and self.stacked_widget.currentIndex() != dirty_view_index:
                print(f"   Switch view to {dirty_view_index}.")
                if hasattr(self, 'nav_list'):
                    self.nav_list.setCurrentRow(dirty_view_index)
