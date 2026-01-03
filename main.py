import sys
import uuid
import os
import shutil
import tempfile
import zipfile
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QLabel, QMessageBox, QComboBox, 
                             QFileDialog, QScrollArea, QFrame, QListWidget, QListWidgetItem,
                             QSplitter, QMenu, QInputDialog, QStyle, QCheckBox, QTextEdit, 
                             QGroupBox, QDialog, QSpacerItem, QSizePolicy, QDoubleSpinBox) 
from PyQt6.QtCore import Qt, QSize

from app_config import HISTORY_FILE, CONFIG_FILE, LIGHT_THEME, DARK_THEME, load_json, save_json
from widgets import MessageBubble, AutoResizingTextEdit
from worker import GeminiWorker

# Default System Instruction
DEFAULT_SYSTEM_INSTRUCTION = (
    "ROLE: You are a Principal and expert Python Software Engineer. Your goal is to generate production-grade, highly optimized, and secure Python code. You value precision, readability, and maintainability over brevity..\n"
    "CORE CODING STANDARDS: 1. Modern Syntax: Use Python 3.10+ syntax features, 2. Type Safety: Use strict type hinting, 3. Documentation: Include Google-style docstrings, 4. Style Guide: Strictly follow PEP 8, 5. Path Handling: Use pathlib.Path, 6. Error Handling: Never use bare except clauses.\n"
    "RESPONSE STRUCTURE: 1. Reasoning (Brief), 2. The Code, 3. Explanation.\n"
    "LIBRARIES & DEPENDENCIES: Prioritize standard libraries, use pandas/polars, httpx/requests, pydantic.\n"
    "CRITICAL INSTRUCTIONS: No Hallucinations. Secure coding practices. Do not add unrelated code."
)

class SettingsDialog(QDialog):
    """
    Modal dialog for application settings.
    """
    def __init__(self, parent, config):
        super().__init__(parent)
        self.main_window = parent
        self.config = config
        self.setWindowTitle("Settings")
        self.setFixedWidth(500)
        self.initUI()
        self.apply_theme_to_dialog()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Model Selection
        layout.addWidget(QLabel("Gemini Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gemini-2.0-flash", "gemini-2.0-pro-exp-02-05", "gemini-1.5-pro"])
        self.model_combo.setCurrentText(self.config.get("model", "gemini-2.0-flash"))
        self.model_combo.currentTextChanged.connect(self.save_general_settings)
        layout.addWidget(self.model_combo)

        # 2. API Key
        layout.addWidget(QLabel("API Key:"))
        self.api_input = QLineEdit(self.config.get("api_key", ""))
        self.api_input.setPlaceholderText("Paste Gemini API Key")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.textChanged.connect(self.save_general_settings)
        layout.addWidget(self.api_input)

        # 3. Grounding
        self.chk_grounding = QCheckBox("Enable Google Search Grounding")
        self.chk_grounding.setChecked(self.config.get("use_search", False))
        self.chk_grounding.toggled.connect(self.save_general_settings)
        layout.addWidget(self.chk_grounding)

        # --- Generation Parameters (Temperature & Top P) ---
        param_group = QGroupBox("Generation Parameters")
        param_layout = QVBoxLayout()
        
        hbox_params = QHBoxLayout()
        
        # Temperature
        temp_layout = QVBoxLayout()
        temp_layout.addWidget(QLabel("Temperature (Creativity):"))
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 2.0)
        self.spin_temp.setSingleStep(0.1)
        self.spin_temp.setValue(self.config.get("temperature", 0.8))
        self.spin_temp.setToolTip("Lower = More logical/precise. Higher = More creative/random.")
        temp_layout.addWidget(self.spin_temp)
        hbox_params.addLayout(temp_layout)

        # Top P
        top_p_layout = QVBoxLayout()
        top_p_layout.addWidget(QLabel("Top P (Nucleus Sampling):"))
        self.spin_top_p = QDoubleSpinBox()
        self.spin_top_p.setRange(0.0, 1.0)
        self.spin_top_p.setSingleStep(0.05)
        self.spin_top_p.setValue(self.config.get("top_p", 0.95))
        self.spin_top_p.setToolTip("Controls diversity. Lower = Factual/focused. Higher = Diverse vocabulary.")
        top_p_layout.addWidget(self.spin_top_p)
        hbox_params.addLayout(top_p_layout)

        param_layout.addLayout(hbox_params)

        # Dedicated Save Button for Parameters
        self.btn_save_params = QPushButton("Save Parameters")
        self.btn_save_params.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_params.setStyleSheet("background-color: #2D2E30; border: 1px solid #555; border-radius: 4px; padding: 5px;")
        self.btn_save_params.clicked.connect(self.save_generation_params)
        param_layout.addWidget(self.btn_save_params)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)
        # --------------------------------------------------

        # 4. System Instruction + Save Button
        layout.addWidget(QLabel("System Instructions:"))
        self.txt_system_instruction = QTextEdit()
        self.txt_system_instruction.setPlaceholderText("Enter system instructions (overrides default persona)...")
        self.txt_system_instruction.setFixedHeight(120)
        current_instr = self.config.get("system_instruction", "")
        self.txt_system_instruction.setText(current_instr)
        layout.addWidget(self.txt_system_instruction)

        self.btn_save_sys = QPushButton("Save System Instruction")
        self.btn_save_sys.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_sys.setStyleSheet("background-color: #0B57D0; color: white; border-radius: 4px; padding: 6px;")
        self.btn_save_sys.clicked.connect(self.save_system_instruction)
        layout.addWidget(self.btn_save_sys)

        # 5. Theme Toggle
        self.btn_theme = QPushButton("Toggle Dark/Light Mode")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        layout.addWidget(self.btn_theme)

        # Close Button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def save_general_settings(self):
        """Auto-saves generic settings like API Key, Model, and Search."""
        self.config["api_key"] = self.api_input.text().strip()
        self.config["model"] = self.model_combo.currentText()
        self.config["use_search"] = self.chk_grounding.isChecked()
        save_json(CONFIG_FILE, self.config)

    def save_generation_params(self):
        """Explicitly saves Temperature and Top P settings, with rounding."""
        self.config["temperature"] = round(self.spin_temp.value(), 2)
        self.config["top_p"] = round(self.spin_top_p.value(), 2)
        save_json(CONFIG_FILE, self.config)
        QMessageBox.information(self, "Saved", "Generation parameters have been saved successfully.")

    def save_system_instruction(self):
        """Explicitly saves System Instructions."""
        text = self.txt_system_instruction.toPlainText().strip()
        self.config["system_instruction"] = text
        save_json(CONFIG_FILE, self.config)
        QMessageBox.information(self, "Saved", "System instructions have been saved successfully.")

    def toggle_theme(self):
        self.main_window.toggle_theme()
        self.apply_theme_to_dialog()

    def apply_theme_to_dialog(self):
        if self.config.get("theme") == "Dark":
            self.setStyleSheet("""
                QDialog { background-color: #1E1F20; color: #E3E3E3; } 
                QLabel { color: #E3E3E3; } 
                QCheckBox { color: #E3E3E3; }
                QGroupBox { border: 1px solid #444; border-radius: 5px; margin-top: 10px; padding-top: 10px; color: #E3E3E3; font-weight: bold; }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }
                QTextEdit, QLineEdit, QComboBox, QDoubleSpinBox { background-color: #282A2C; color: #E3E3E3; border: 1px solid #444; }
            """)
        else:
            self.setStyleSheet("""
                QDialog { background-color: #FFFFFF; color: #000000; } 
                QLabel { color: #000000; } 
                QCheckBox { color: #000000; }
                QGroupBox { border: 1px solid #CCC; border-radius: 5px; margin-top: 10px; padding-top: 10px; color: #000000; font-weight: bold; }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }
                QTextEdit, QLineEdit, QComboBox, QDoubleSpinBox { background-color: #F0F0F0; color: #000000; border: 1px solid #CCC; }
            """)


class GeminiBrowser(QMainWindow):
    """
    Main Application Window for the Gemini GUI.
    """
    def __init__(self):
        super().__init__()
        self.data = load_json(HISTORY_FILE, {})
        # Initialize Config with Defaults
        self.config = load_json(CONFIG_FILE, {
            "api_key": "", 
            "model": "gemini-2.0-flash", 
            "theme": "Dark", 
            "use_search": False,
            "system_instruction": DEFAULT_SYSTEM_INSTRUCTION,
            "temperature": 0.8,
            "top_p": 0.95
        })
        
        if "system_instruction" not in self.config:
            self.config["system_instruction"] = DEFAULT_SYSTEM_INSTRUCTION

        self.current_session_id: Optional[str] = None
        
        # --- File Handling Properties ---
        self.attached_files: List[str] = []
        self.temp_dirs: List[str] = [] # Track temp dirs for cleanup

        if not self.config.get("api_key"):
            QMessageBox.warning(self, "Missing API Key", "Please enter your Gemini API key in the settings (Top Right).")

        self.initUI()
        self.update_sidebar()
        self.create_new_session()

    def initUI(self):
        self.setWindowTitle("Gemini GUI")
        app_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(app_icon)
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar ---
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setFixedWidth(260)
        self.sidebar_frame.setObjectName("Sidebar")

        sidebar_layout = QVBoxLayout(self.sidebar_frame)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(10)

        self.btn_new_chat = QPushButton(" +  New chat")
        self.btn_new_chat.setObjectName("BtnNewChat")
        self.btn_new_chat.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_chat.clicked.connect(self.create_new_session)
        sidebar_layout.addWidget(self.btn_new_chat)

        sidebar_layout.addSpacing(10)

        lbl_hist = QLabel("Recent")
        lbl_hist.setObjectName("SidebarLabel")
        sidebar_layout.addWidget(lbl_hist)

        self.chat_list = QListWidget()
        self.chat_list.itemClicked.connect(self.load_session_from_list)
        self.chat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self.show_context_menu)
        sidebar_layout.addWidget(self.chat_list)
        
        # --- Chat Area ---
        self.chat_area = QWidget()
        self.chat_area.setObjectName("ChatArea")
        chat_layout = QVBoxLayout(self.chat_area)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 10, 20, 0)
        
        header_layout.addWidget(QLabel("Gemini Assistant"))
        header_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        self.btn_settings = QPushButton("⚙️ Settings")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setFixedWidth(100)
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_settings.setStyleSheet("""
            QPushButton { 
                background-color: transparent; 
                border: 1px solid #555; 
                border-radius: 4px; 
                color: #888; 
            }
            QPushButton:hover { background-color: #333; color: #EEE; }
        """)
        header_layout.addWidget(self.btn_settings)
        
        chat_layout.addWidget(header_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("ScrollArea")

        self.messages_container = QWidget()
        self.messages_container.setObjectName("MessagesContainer")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(20)
        self.messages_layout.setContentsMargins(50, 20, 50, 20)

        self.scroll_area.setWidget(self.messages_container)
        chat_layout.addWidget(self.scroll_area, 1)

        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(20, 10, 20, 30)

        self.file_label = QLabel("")
        self.file_label.setStyleSheet("color: #0B57D0; font-size: 12px; margin-left: 10px; margin-bottom: 5px;")
        bottom_layout.addWidget(self.file_label)

        self.input_frame = QFrame()
        self.input_frame.setObjectName("InputFrame")
        
        pill_layout = QHBoxLayout(self.input_frame)
        pill_layout.setContentsMargins(10, 5, 10, 5)
        pill_layout.setSpacing(10)
        pill_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter) 

        # Attachment Button with Menu
        self.btn_file = QPushButton("+")
        self.btn_file.setToolTip("Attach Files or Folders")
        self.btn_file.setFixedSize(36, 36)
        self.btn_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_file.setStyleSheet("""
            QPushButton { background: #D3E3FD; color: #041E49; border-radius: 18px; font-size: 20px; border: none; }
            QPushButton:hover { background: #C2E7FF; }
        """)
        self.btn_file.clicked.connect(self.show_attach_menu)

        self.input_field = AutoResizingTextEdit(self) 

        btn_send = QPushButton("➤")
        btn_send.setFixedSize(36, 36)
        btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_send.setObjectName("BtnSend")
        btn_send.setStyleSheet("""
            QPushButton { background: transparent; color: #0B57D0; border-radius: 18px; font-size: 18px; }
            QPushButton:hover { background: #D3E3FD; }
        """)
        btn_send.clicked.connect(self.send_message)

        pill_layout.addWidget(self.btn_file)
        pill_layout.addWidget(self.input_field)
        pill_layout.addWidget(btn_send)

        bottom_layout.addWidget(self.input_frame)
        chat_layout.addWidget(bottom_container, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar_frame)
        splitter.addWidget(self.chat_area)
        splitter.setStretchFactor(1, 4)
        splitter.setHandleWidth(1)

        main_layout.addWidget(splitter)
        self.apply_theme()

    # --- New File Handling Methods ---
    def show_attach_menu(self):
        """Displays menu for attaching files or folders."""
        menu = QMenu(self)
        action_files = menu.addAction("Attach Files (Text, Image, PDF, Audio, Zip...)")
        action_folder = menu.addAction("Attach Folder (Recursive)")
        
        action_files.triggered.connect(self.attach_files)
        action_folder.triggered.connect(self.attach_folder)
        
        # Position menu above the button
        menu.exec(self.btn_file.mapToGlobal(self.btn_file.rect().topLeft()))

    def attach_files(self):
        """Handles selecting one or more files."""
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*)")
        if files:
            self._process_new_attachments(files)

    def attach_folder(self):
        """Handles selecting a directory and recursively adding files."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            collected_files = []
            for root, dirs, files in os.walk(folder):
                # Skip hidden directories like .git, .idea
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for file in files:
                    if not file.startswith('.'):
                        collected_files.append(os.path.join(root, file))
            
            if collected_files:
                self._process_new_attachments(collected_files)
            else:
                QMessageBox.information(self, "Info", "No valid files found in selected folder.")

    def _process_new_attachments(self, file_paths: List[str]):
        """Processes list of files, expanding archives if needed."""
        for path in file_paths:
            p = Path(path)
            # Check for compressed formats
            if p.suffix.lower() in ['.zip', '.tar', '.gz', '.tgz']:
                self._extract_and_attach_archive(p)
            else:
                self.attached_files.append(str(p))
        
        self._update_file_label()

    def _extract_and_attach_archive(self, archive_path: Path):
        """Extracts zip/tar to a temporary folder and adds contents."""
        try:
            temp_dir = tempfile.mkdtemp(prefix="gemini_gui_extract_")
            self.temp_dirs.append(temp_dir) # Track for cleanup
            
            extracted_files = []
            
            # Extract based on type
            if zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            elif tarfile.is_tarfile(archive_path):
                with tarfile.open(archive_path, 'r') as tar_ref:
                    tar_ref.extractall(temp_dir)
            
            # Recursively walk the extracted temp directory
            for root, dirs, files in os.walk(temp_dir):
                # Filter out hidden/system dirs (e.g., __MACOSX)
                dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
                for file in files:
                    if not file.startswith('.'):
                        extracted_files.append(os.path.join(root, file))
            
            self.attached_files.extend(extracted_files)
            
        except Exception as e:
            QMessageBox.warning(self, "Extraction Error", f"Failed to extract {archive_path.name}: {e}")

    def _update_file_label(self):
        count = len(self.attached_files)
        if count == 0:
            self.file_label.setText("")
        else:
            names = [Path(f).name for f in self.attached_files[-3:]] # Show last 3
            display_text = ", ".join(names)
            if count > 3:
                display_text += f" (+{count - 3} more)"
            self.file_label.setText(f"📎 Attached ({count}): {display_text}")

    def _cleanup_temp_resources(self):
        """Clean up attached list and temporary directories."""
        self.attached_files.clear()
        self.file_label.setText("")
        
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    print(f"Warning: Could not remove temp dir {temp_dir}: {e}")
        self.temp_dirs.clear()

    # --- Existing Functionality ---

    def get_current_theme(self) -> str:
        return self.config.get("theme", "Dark")

    def apply_theme(self):
        theme = self.get_current_theme()
        if theme == "Dark":
            self.setStyleSheet(DARK_THEME)
        else:
            self.setStyleSheet(LIGHT_THEME)
        
        if self.current_session_id:
            self.load_session_from_list(self.chat_list.currentItem())

    def toggle_theme(self):
        current = self.get_current_theme()
        new_theme = "Dark" if current == "Light" else "Light"
        self.config["theme"] = new_theme
        self.save_config()
        self.apply_theme()

    def create_new_session(self):
        self.current_session_id = str(uuid.uuid4())
        self.data[self.current_session_id] = {"title": "New Chat", "timestamp": datetime.now().isoformat(), "history": []}
        self.clear_chat_ui()
        self._cleanup_temp_resources()
        self.input_field.setFocus()
        self.chat_list.clearSelection()

    def update_sidebar(self):
        self.chat_list.clear()
        sorted_sessions = sorted(self.data.items(), key=lambda x: x[1].get('timestamp', ''), reverse=True)
        for sess_id, sess_data in sorted_sessions:
            item = QListWidgetItem(sess_data.get("title", "Untitled"))
            item.setData(Qt.ItemDataRole.UserRole, sess_id)
            self.chat_list.addItem(item)
            if sess_id == self.current_session_id: 
                item.setSelected(True)
                self.chat_list.setCurrentItem(item)

    def load_session_from_list(self, item):
        if not item: return
        self.current_session_id = item.data(Qt.ItemDataRole.UserRole)
        self.clear_chat_ui()
        history = self.data.get(self.current_session_id, {}).get("history", [])
        for msg in history:
            self.messages_layout.addWidget(
                MessageBubble(msg['text'], is_user=(msg['role'] == 'user'), theme_mode=self.get_current_theme())
            )
        self.scroll_to_bottom()

    def clear_chat_ui(self):
        while self.messages_layout.count():
            child = self.messages_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

    def show_context_menu(self, pos):
        item = self.chat_list.itemAt(pos)
        if not item: return
        menu = QMenu()
        menu.addAction("Delete Chat").triggered.connect(lambda: self.delete_session(item))
        menu.addAction("Rename").triggered.connect(lambda: self.rename_session(item))
        menu.exec(self.chat_list.mapToGlobal(pos))

    def delete_session(self, item):
        sess_id = item.data(Qt.ItemDataRole.UserRole)
        if sess_id in self.data:
            del self.data[sess_id]
            save_json(HISTORY_FILE, self.data)
            self.update_sidebar()
            if sess_id == self.current_session_id: self.create_new_session()

    def rename_session(self, item):
        sess_id = item.data(Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(self, "Rename", "Chat Title:", text=item.text())
        if ok and new_name:
            if sess_id in self.data:
                self.data[sess_id]["title"] = new_name
                save_json(HISTORY_FILE, self.data)
                self.update_sidebar()

    def save_config(self):
        save_json(CONFIG_FILE, self.config)

    def open_settings(self):
        dlg = SettingsDialog(self, self.config)
        dlg.exec()

    def send_message(self):
        prompt = self.input_field.toPlainText().strip()
        api_key = self.config.get("api_key", "")
        if not api_key: 
            QMessageBox.warning(self, "Missing Key", "Please enter Gemini API Key in Settings.")
            return
        if not prompt and not self.attached_files: return

        # User Bubble (Display simplified text for attached files)
        file_msg = f" [Attached {len(self.attached_files)} files]" if self.attached_files else ""
        display_text = (prompt + file_msg) if prompt else file_msg
        
        self.messages_layout.addWidget(
            MessageBubble(display_text, is_user=True, theme_mode=self.get_current_theme())
        )
        self.scroll_to_bottom()
        
        self.input_field.clear()
        self.input_field.adjust_height()

        loading_lbl = QLabel("Gemini is processing...")
        loading_lbl.setStyleSheet("color: #888; margin-left: 20px; font-style: italic;")
        self.messages_layout.addWidget(loading_lbl)

        session = self.data[self.current_session_id]
        if not session["history"]:
            session["title"] = (prompt[:25] + "...") if len(prompt) > 25 else (prompt or "Analysis")
            self.update_sidebar()

        # Add text history only (files are ephemeral for the API call in this implementation)
        session["history"].append({"role": "user", "text": prompt if prompt else "[Sent Files]"})

        # --- LOAD SETTINGS ---
        use_search = self.config.get("use_search", False)
        sys_instr = self.config.get("system_instruction", "")
        model_name = self.config.get("model", "gemini-2.0-flash")
        temperature = self.config.get("temperature", 0.8)
        top_p = self.config.get("top_p", 0.95)

        # Pass a copy of attached files list to worker
        files_to_send = list(self.attached_files)

        self.worker = GeminiWorker(
            api_key, 
            prompt, 
            model_name, 
            files_to_send, 
            session["history"][:-1],
            use_grounding=use_search,
            system_instruction=sys_instr,
            temperature=temperature,
            top_p=top_p
        )
        self.worker.finished.connect(lambda res: self.on_response_success(res, loading_lbl))
        self.worker.error.connect(lambda err: self.on_response_error(err, loading_lbl))
        self.worker.start()

    def on_response_success(self, text, loading_lbl):
        loading_lbl.deleteLater()
        self.messages_layout.addWidget(
            MessageBubble(text, is_user=False, theme_mode=self.get_current_theme())
        )
        self.scroll_to_bottom()
        self.data[self.current_session_id]["history"].append({"role": "model", "text": text})
        self.data[self.current_session_id]["timestamp"] = datetime.now().isoformat()
        save_json(HISTORY_FILE, self.data)
        
        # Cleanup files after successful send
        self._cleanup_temp_resources()

    def on_response_error(self, err, loading_lbl):
        loading_lbl.deleteLater()
        lbl = QLabel(f"Error: {err}")
        lbl.setStyleSheet("color: #D32F2F;")
        self.messages_layout.addWidget(lbl)
        
        # Don't cleanup on error immediately so user can retry, 
        # but user can also click 'Clear Chat' or 'New Chat'.

    def scroll_to_bottom(self):
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = GeminiBrowser()
    window.show()
    sys.exit(app.exec())