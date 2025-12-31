import json
import logging
from pathlib import Path
from typing import Any

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Paths
BASE_DIR = Path(__file__).resolve().parent
HISTORY_FILE = BASE_DIR / "history.json"
CONFIG_FILE = BASE_DIR / "settings.json"

def load_json(filepath: Path, default: Any = None) -> Any:
    """
    Loads JSON data from a file with error handling.

    Args:
        filepath (Path): The path to the JSON file.
        default (Any): The default return value if loading fails.

    Returns:
        Any: The loaded data or the default value.
    """
    if not filepath.exists():
        return default if default is not None else {}
    try:
        with filepath.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.error(f"Failed to load {filepath}: {e}")
        return default if default is not None else {}

def save_json(filepath: Path, data: Any) -> None:
    """
    Saves data to a JSON file.

    Args:
        filepath (Path): The destination path.
        data (Any): The data to serialize.
    """
    try:
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except OSError as e:
        logging.error(f"Failed to save {filepath}: {e}")

# --- THEMES & STYLES ---

# Syntax Highlighting Colors (Hex codes)
SYNTAX_COLORS = {
    "Dark": {
        "keyword": "#ff79c6",  # Pink
        "string": "#f1fa8c",   # Yellow/Green
        "comment": "#6272a4",  # Gray/Blue
        "function": "#50fa7b", # Green
        "class": "#8be9fd",    # Cyan
        "number": "#bd93f9",   # Purple
        "background": "#1e1e1e",
        "text": "#f8f8f2"
    },
    "Light": {
        "keyword": "#d73a49",  # Red
        "string": "#032f62",   # Dark Blue
        "comment": "#6a737d",  # Gray
        "function": "#6f42c1", # Purple
        "class": "#005cc5",    # Blue
        "number": "#005cc5",   # Blue
        "background": "#f6f8fa",
        "text": "#24292e"
    }
}

LIGHT_THEME = """
QMainWindow, QWidget { background-color: #FFFFFF; color: #1F1F1F; }
QTextEdit, QLineEdit { background-color: #F0F4F9; border: none; border-radius: 12px; padding: 10px; color: #1F1F1F; }
QListWidget { background-color: #F0F4F9; border: none; }
QListWidget::item:selected { background-color: #D3E3FD; color: #041E49; border-radius: 20px; }
QLabel { color: #1F1F1F; }
QPushButton#BtnNewChat { background-color: #D3E3FD; color: #041E49; border-radius: 15px; font-weight: bold; padding: 12px; text-align: left; padding-left: 20px; border: none; }
QPushButton#BtnNewChat:hover { background-color: #C2E7FF; }
QFrame#Sidebar { background-color: #F0F4F9; border-right: none; }

/* User Bubble: Gemini Light Gray/Blue (#F0F4F9) */
QFrame#UserBubble { background-color: #F0F4F9; border-radius: 20px; color: #1F1F1F; }
QFrame#UserBubble QLabel { color: #1F1F1F; }

/* AI Bubble: Transparent (Clean text look) */
QFrame#AIBubble { background-color: transparent; border: none; }
QFrame#AIBubble QLabel { color: #1F1F1F; }

/* Fonts: Roboto/Segoe UI to mimic Google Sans */
QLabel#BubbleText { font-family: 'Roboto', 'Segoe UI', sans-serif; font-size: 16px; line-height: 1.6; }
QScrollArea { border: none; background: transparent; }
"""

DARK_THEME = """
QMainWindow, QWidget { background-color: #131314; color: #E3E3E3; }
QTextEdit, QLineEdit { background-color: #282A2C; border: none; border-radius: 12px; padding: 10px; color: #E3E3E3; }
QListWidget { background-color: #1E1F20; border: none; }
QListWidget::item:selected { background-color: #004A77; color: #C2E7FF; border-radius: 20px; }
QLabel { color: #E3E3E3; }
QPushButton#BtnNewChat { background-color: #1E1F20; color: #E3E3E3; border-radius: 15px; font-weight: bold; padding: 12px; text-align: left; padding-left: 20px; border: none; }
QPushButton#BtnNewChat:hover { background-color: #2D2E30; }
QFrame#Sidebar { background-color: #1E1F20; border-right: none; }

/* User Bubble: Gemini Dark Gray (#3C4043) */
QFrame#UserBubble { background-color: #3C4043; border-radius: 20px; color: #E3E3E3; }
QFrame#UserBubble QLabel { color: #E3E3E3; }

/* AI Bubble: Transparent */
QFrame#AIBubble { background-color: transparent; border: none; }
QFrame#AIBubble QLabel { color: #E3E3E3; }

/* Fonts */
QLabel#BubbleText { font-family: 'Roboto', 'Segoe UI', sans-serif; font-size: 16px; line-height: 1.6; }
QScrollArea { border: none; background: transparent; }
"""