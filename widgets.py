import re
import markdown
from markdown_it import MarkdownIt  # FIX: Added for robust parsing
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QTextEdit, QApplication, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import (
    QDesktopServices, QFontDatabase, QFont, QSyntaxHighlighter, 
    QTextCharFormat, QColor, QTextDocument
)

# Pygments imports for Syntax Highlighting
from pygments import lex
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.token import Token

from app_config import SYNTAX_COLORS

class GeminiHighlighter(QSyntaxHighlighter):
    """
    A Qt Syntax Highlighter that uses Pygments to tokenize code.
    """
    def __init__(self, document, language: str, theme_mode: str = "Dark"):
        super().__init__(document)
        self.theme_mode = theme_mode
        self.styles = SYNTAX_COLORS.get(theme_mode, SYNTAX_COLORS["Dark"])

        # Determine Lexer
        try:
            self.lexer = get_lexer_by_name(language)
        except Exception:
            self.lexer = TextLexer()

        # Create Formatting Rules based on Pygments Tokens
        self.formats = self._create_formats()

    def _create_formats(self) -> dict:
        """Maps Pygments tokens to QTextCharFormat based on current theme."""
        formats = {}
        
        # Helper to create format
        def _fmt(color_key):
            color = self.styles.get(color_key, "#dcdcdc")
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            return f

        formats[Token.Keyword] = _fmt("keyword")
        formats[Token.Name.Function] = _fmt("function")
        formats[Token.Name.Class] = _fmt("class")
        formats[Token.String] = _fmt("string")
        formats[Token.Comment] = _fmt("comment")
        formats[Token.Number] = _fmt("number")
        formats[Token.Operator] = _fmt("operator")
        formats[Token.Name] = _fmt("variable") # Default for names
        
        return formats

    def highlightBlock(self, text: str):
        """Applied to every block of text in the document."""
        original_text = text
        # Lex the text using Pygments
        tokens = lex(original_text, self.lexer)
        
        index = 0
        for token_type, value in tokens:
            length = len(value)
            # Find the best matching format
            fmt = self.formats.get(token_type)
            if not fmt:
                # Try parent token types if direct match fails
                if token_type in Token.Keyword: fmt = self.formats.get(Token.Keyword)
                elif token_type in Token.Name: fmt = self.formats.get(Token.Name)
                elif token_type in Token.String: fmt = self.formats.get(Token.String)
                elif token_type in Token.Comment: fmt = self.formats.get(Token.Comment)
                
            if fmt:
                self.setFormat(index, length, fmt)
            
            index += length

class CodeBlock(QFrame):
    """
    A widget to display code with a header, Copy button, and auto-sizing.
    """
    def __init__(self, code: str, language: str = "text", theme_mode: str = "Dark"):
        super().__init__()
        self.code = code
        self.language = language if language else "text"
        self.theme_mode = theme_mode
        self.initUI()

    def initUI(self):
        self.setObjectName("CodeBlock")
        bg_color = "#1e1e1e" if self.theme_mode == "Dark" else "#f6f8fa"
        border_color = "#333" if self.theme_mode == "Dark" else "#d0d7de"
        
        self.setStyleSheet(f"""
            QFrame#CodeBlock {{ 
                background-color: {bg_color}; 
                border-radius: 6px; 
                border: 1px solid {border_color}; 
                margin-top: 8px; 
                margin-bottom: 8px; 
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Header ---
        header = QFrame()
        header.setObjectName("CodeHeader")
        header_bg = "#2d2d2d" if self.theme_mode == "Dark" else "#eaeef2"
        header.setStyleSheet(f"""
            QFrame#CodeHeader {{ 
                background-color: {header_bg}; 
                border-top-left-radius: 6px; 
                border-top-right-radius: 6px;
                border-bottom: 1px solid {border_color};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)

        lang_lbl = QLabel(self.language.upper())
        lang_lbl.setStyleSheet(f"color: {'#aaa' if self.theme_mode == 'Dark' else '#57606a'}; font-weight: bold; font-size: 11px; font-family: 'Segoe UI', sans-serif;")
        
        copy_btn = QPushButton("Copy")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; 
                color: {'#aaa' if self.theme_mode == 'Dark' else '#57606a'}; 
                border: none; 
                font-size: 11px;
            }}
            QPushButton:hover {{ color: {'#fff' if self.theme_mode == 'Dark' else '#0969da'}; }}
        """)
        copy_btn.clicked.connect(self.copy_code)

        header_layout.addWidget(lang_lbl)
        header_layout.addStretch()
        header_layout.addWidget(copy_btn)

        layout.addWidget(header)

        # --- Code Editor (Read Only) ---
        self.editor = QTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setPlainText(self.code)
        
        # Font settings for code
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(10)
        self.editor.setFont(font)

        # Styling
        text_color = "#e3e3e3" if self.theme_mode == "Dark" else "#1f2328"
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                color: {text_color};
                border: none;
                padding: 5px;
            }}
        """)
        
        # Hide scrollbars, we will resize widget instead
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Apply Syntax Highlighting
        self.highlighter = GeminiHighlighter(self.editor.document(), self.language, self.theme_mode)

        layout.addWidget(self.editor)
        
        # Adjust Height
        self.adjust_height()

    def adjust_height(self):
        """Auto-resize based on content line count."""
        lines = self.code.count('\n') + 1
        
        # FIX: Use QFontMetrics to get accurate line height for the current font.
        # This prevents clipping if the system font is larger than expected.
        fm = self.editor.fontMetrics()
        line_height = fm.lineSpacing() 
        
        # Header (35) + Content + Padding (10)
        height = 35 + (lines * line_height) + 10
        self.setFixedHeight(min(height, 600)) # Cap at 600px

    def copy_code(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.code)
        
        # Feedback
        btn = self.findChild(QPushButton)
        if btn:
            original = btn.text()
            btn.setText("Copied!")
            QTimer.singleShot(1500, lambda: btn.setText(original))


class MessageBubble(QFrame):
    """
    A bubble for rendering Markdown text and Code Blocks nicely.
    """
    def __init__(self, text: str, is_user: bool = False, theme_mode: str = "Dark"):
        super().__init__()
        self.raw_text = text  # Store original text
        self.is_user = is_user
        self.theme_mode = theme_mode
        self.initUI()

    def initUI(self):
        self.setObjectName("AIBubble")
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # --- FIX: Use markdown-it-py for robust parsing ---
        # This handles nested backticks and complex structures correctly.
        md = MarkdownIt()
        tokens = md.parse(self.raw_text)
        
        # We need the raw lines to extract text chunks accurately
        lines = self.raw_text.splitlines(keepends=True)
        last_line_idx = 0

        for token in tokens:
            if token.type == 'fence': # 'fence' indicates a code block
                start_line, end_line = token.map
                
                # 1. Render Markdown Text occurring BEFORE this code block
                if start_line > last_line_idx:
                    text_chunk = "".join(lines[last_line_idx:start_line])
                    if text_chunk.strip():
                        self._add_markdown_text(text_chunk, layout)
                
                # 2. Render the Code Block
                # token.content holds the code, token.info holds the language
                self._add_code_block(token.content, token.info, layout)
                
                last_line_idx = end_line

        # 3. Render any remaining text after the last code block
        if last_line_idx < len(lines):
            text_chunk = "".join(lines[last_line_idx:])
            if text_chunk.strip():
                self._add_markdown_text(text_chunk, layout)

        # Add Toolbar (Copy / Regenerate) if it's the model
        if not self.is_user:
            self._add_toolbar(layout)

    def _add_markdown_text(self, text: str, layout: QVBoxLayout):
        """Renders markdown text using QLabel with rich text."""
        # Process simple markdown to HTML
        html_content = self._markdown_to_html(text)
        
        lbl = QLabel(html_content)
        lbl.setObjectName("BubbleText")
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setOpenExternalLinks(True)
        
        # Text Color based on theme
        text_color = "#E3E3E3" if self.theme_mode == "Dark" else "#1F1F1F"
        lbl.setStyleSheet(f"color: {text_color}; border: none;")
        
        layout.addWidget(lbl)

    def _add_code_block(self, code_content: str, language: str, layout: QVBoxLayout):
        """Creates a CodeBlock widget."""
        # token.content usually includes a trailing newline, trim it for display
        if code_content.endswith('\n'):
            code = code_content[:-1]
        else:
            code = code_content

        # Fallback if language is empty
        if not language:
            language = "text"

        block = CodeBlock(code, language.strip(), self.theme_mode)
        layout.addWidget(block)

    def _add_toolbar(self, layout: QVBoxLayout):
        """Adds a Copy button footer."""
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        
        copy_btn = QPushButton("Copy Text")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #888;
                font-size: 11px;
                padding: 4px 8px;
            }
            QPushButton:hover { color: #4da6ff; background-color: rgba(255,255,255,0.05); border-radius: 4px; }
        """)
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(clean=True, btn=copy_btn))
        
        toolbar.addWidget(copy_btn)
        layout.addLayout(toolbar)

    def _markdown_to_html(self, text: str) -> str:
        """Converts Markdown to basic HTML for QLabel."""
        # Use Python-Markdown for robust conversion
        try:
            # FIX: Added 'tables' extension to support Markdown table rendering
            html = markdown.markdown(text, extensions=['tables'])
            
            # Style adjustments for Qt
            link_color = "#4da6ff" if self.theme_mode == "Dark" else "#0969da"
            html = html.replace('<a href=', f'<a style="color: {link_color}; text-decoration: none;" href=')
            
            # FIX: Add HTML attributes to tables because QLabel doesn't default to showing borders
            if "<table>" in html:
                html = html.replace("<table>", '<table border="1" cellspacing="0" cellpadding="5" width="100%">')

            return html
        except Exception:
            # Fallback for simple formatting if lib fails
            return text

    def copy_to_clipboard(self, clean: bool = True, btn: QPushButton = None):
        """
        Copies the content to clipboard.
        FIX: Converts Markdown to plain text via QTextDocument to strip syntax.
        """
        clipboard = QApplication.clipboard()
        
        if clean:
            # 1. Convert Raw Markdown to HTML
            try:
                # FIX: Also use 'tables' here so copying "Clean Text" preserves table data structure if possible
                html_content = markdown.markdown(self.raw_text, extensions=['tables'])
                
                # 2. Use QTextDocument to convert HTML -> Plain Text
                doc = QTextDocument()
                doc.setHtml(html_content)
                clean_text = doc.toPlainText()
                
                clipboard.setText(clean_text.strip())
            except Exception:
                clipboard.setText(self.raw_text)
        else:
            clipboard.setText(self.raw_text)
        
        if btn:
            original_text = btn.text()
            btn.setText("Copied!")
            QTimer.singleShot(1500, lambda: btn.setText(original_text))


class AutoResizingTextEdit(QTextEdit):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setObjectName("InputBox") 
        self.setPlaceholderText("Enter a prompt here (Shift+Enter for new line)...")
        self.setFixedHeight(50) 
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.textChanged.connect(self.adjust_height)

    def adjust_height(self):
        doc_height = self.document().size().height()
        # Cap max height at 150px
        new_height = min(max(50, int(doc_height + 10)), 150)
        self.setFixedHeight(new_height)

    def keyPressEvent(self, event):
        # Allow Shift+Enter for new line, regular Enter sends message
        if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.parent_window.send_message()
        else:
            super().keyPressEvent(event)