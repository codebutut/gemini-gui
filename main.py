import sys
import uuid
from datetime import datetime
from pathlib import Path
# FIX: Removed 'list' from imports. 'Optional' is still valid.
from typing import Optional

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QLabel, QMessageBox, QComboBox, 
                             QFileDialog, QScrollArea, QFrame, QListWidget, QListWidgetItem,
                             QSplitter, QMenu, QInputDialog, QStyle)
from PyQt6.QtCore import Qt, QSize

from app_config import HISTORY_FILE, CONFIG_FILE, LIGHT_THEME, DARK_THEME, load_json, save_json
from widgets import MessageBubble, AutoResizingTextEdit
from worker import GeminiWorker

class GeminiBrowser(QMainWindow):
    """
    Main Application Window for the Gemini GUI.
    """
    def __init__(self):
        super().__init__()
        self.data = load_json(HISTORY_FILE, {})
        self.config = load_json(CONFIG_FILE, {"api_key": "", "model": "gemini-2.0-flash", "theme": "Dark"})
        self.current_session_id: Optional[str] = None
        self.attached_files: list[str] = []

        if not self.config.get("api_key"):
            QMessageBox.warning(self, "Missing API Key", "Please enter your Gemini API key in the settings.")

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
        self.sidebar_frame.setFixedWidth(280)
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

        sidebar_layout.addSpacing(10)
        lbl_settings = QLabel("Settings")
        lbl_settings.setObjectName("SidebarLabel")
        sidebar_layout.addWidget(lbl_settings)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["gemini-2.0-flash", "gemini-2.0-pro-exp-02-05", "gemini-1.5-pro"])
        self.model_combo.setCurrentText(self.config.get("model", "gemini-2.0-flash"))
        self.model_combo.currentTextChanged.connect(self.save_config)
        sidebar_layout.addWidget(self.model_combo)
        
        self.api_input = QLineEdit(self.config.get("api_key", ""))
        self.api_input.setPlaceholderText("API Key")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.textChanged.connect(self.save_config)
        sidebar_layout.addWidget(self.api_input)

        self.btn_theme = QPushButton("Toggle Dark/Light Mode")
        self.btn_theme.setObjectName("BtnToggleTheme")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        sidebar_layout.addWidget(self.btn_theme)

        # --- Chat Area ---
        self.chat_area = QWidget()
        self.chat_area.setObjectName("ChatArea")
        chat_layout = QVBoxLayout(self.chat_area)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

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

        btn_file = QPushButton("+")
        btn_file.setToolTip("Attach Files")
        btn_file.setFixedSize(36, 36)
        btn_file.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_file.setStyleSheet("""
            QPushButton { background: #D3E3FD; color: #041E49; border-radius: 18px; font-size: 20px; border: none; }
            QPushButton:hover { background: #C2E7FF; }
        """)
        btn_file.clicked.connect(self.attach_files)

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

        pill_layout.addWidget(btn_file)
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

    def get_current_theme(self) -> str:
        return self.config.get("theme", "Dark")

    def apply_theme(self):
        theme = self.get_current_theme()
        if theme == "Dark":
            self.setStyleSheet(DARK_THEME)
        else:
            self.setStyleSheet(LIGHT_THEME)
        
        # Reload chat to apply theme-specific highlighter
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
        self.attached_files = []
        self.file_label.setText("")
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
        self.config["api_key"] = self.api_input.text().strip()
        self.config["model"] = self.model_combo.currentText()
        save_json(CONFIG_FILE, self.config)

    def attach_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            self.attached_files.extend(files)
            file_names = [Path(f).name for f in self.attached_files]
            display_text = ", ".join(file_names)
            self.file_label.setText(f"📎 Attached ({len(self.attached_files)}): {display_text}")

    def send_message(self):
        prompt = self.input_field.toPlainText().strip()
        api_key = self.api_input.text().strip()
        if not api_key: return QMessageBox.warning(self, "Missing Key", "Please enter Gemini API Key.")
        if not prompt and not self.attached_files: return

        # User Bubble
        self.messages_layout.addWidget(
            MessageBubble(prompt if prompt else "[Files]", is_user=True, theme_mode=self.get_current_theme())
        )
        self.scroll_to_bottom()
        
        self.input_field.clear()
        self.input_field.adjust_height()

        loading_lbl = QLabel("Gemini is thinking...")
        loading_lbl.setStyleSheet("color: #888; margin-left: 20px; font-style: italic;")
        self.messages_layout.addWidget(loading_lbl)

        session = self.data[self.current_session_id]
        if not session["history"]:
            session["title"] = (prompt[:25] + "...") if len(prompt) > 25 else (prompt or "Analysis")
            self.update_sidebar()

        session["history"].append({"role": "user", "text": prompt})

        self.worker = GeminiWorker(api_key, prompt, self.model_combo.currentText(), list(self.attached_files), session["history"][:-1])
        self.worker.finished.connect(lambda res: self.on_response_success(res, loading_lbl))
        self.worker.error.connect(lambda err: self.on_response_error(err, loading_lbl))
        self.worker.start()

        self.attached_files = []
        self.file_label.setText("")

    def on_response_success(self, text, loading_lbl):
        loading_lbl.deleteLater()
        self.messages_layout.addWidget(
            MessageBubble(text, is_user=False, theme_mode=self.get_current_theme())
        )
        self.scroll_to_bottom()
        self.data[self.current_session_id]["history"].append({"role": "model", "text": text})
        self.data[self.current_session_id]["timestamp"] = datetime.now().isoformat()
        save_json(HISTORY_FILE, self.data)

    def on_response_error(self, err, loading_lbl):
        loading_lbl.deleteLater()
        lbl = QLabel(f"Error: {err}")
        lbl.setStyleSheet("color: #D32F2F;")
        self.messages_layout.addWidget(lbl)

    def scroll_to_bottom(self):
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = GeminiBrowser()
    window.show()
    sys.exit(app.exec())