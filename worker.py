import os
from pathlib import Path
# FIX: Removed 'list' and 'dict' from typing imports. Using built-ins directly.
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal
from google import genai
from google.genai import types

from utils import RateLimiter

class GeminiWorker(QThread):
    """
    Worker thread to handle Gemini API requests asynchronously.
    """
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    # Shared rate limiter across all worker instances
    RATE_LIMITER = RateLimiter(max_requests=20, period=60, auto_refill=True)

    def __init__(
        self, 
        api_key: str, 
        prompt: str, 
        model: str, 
        file_paths: list[str], 
        history_context: list[dict[str, str]]
    ):
        super().__init__()
        self.api_key = api_key
        self.prompt = prompt
        self.model = model
        self.file_paths = file_paths
        self.history_context = history_context

    def run(self) -> None:
        try:
            # 1. Check Rate Limit
            if not GeminiWorker.RATE_LIMITER.acquire(blocking=True, timeout=30):
                self.error.emit("Rate limit exceeded: Could not acquire token after waiting.")
                return

            client = genai.Client(api_key=self.api_key)
            gemini_contents = []

            # 2. Build History
            for item in self.history_context:
                parts = [types.Part.from_text(text=item['text'])]
                gemini_contents.append(types.Content(role=item['role'], parts=parts))

            # 3. Construct System/User Prompt
            current_prompt_text = (
                "ROLE: You are a Principal and expert Python Software Engineer. Your goal is to generate production-grade, highly optimized, and secure Python code. You value precision, readability, and maintainability over brevity.."
                "CORE CODING STANDARDS: 1. Modern Syntax: Use Python 3.10+ syntax features (e.g., match/case statements, union types X | Y instead of Union[X, Y]), 2.  Type Safety: You must use strict type hinting for all function arguments and return values. Use the typing module or standard collections (e.g., list[str], dict[str, Any]), 3.  Documentation: Include Google-style docstrings for all functions and classes. Describe args, returns, and raises, 4.  Style Guide: Strictly follow PEP 8 standards. Use snake case for variables functions and PascalCase for classes, 5.  Path Handling: Always use pathlib.Path instead of os.path strings, 6.  Error Handling: Never use bare except: clauses. Catch specific exceptions. Use the logging module instead of print statements for production code."
                "RESPONSE STRUCTURE: 1.  Reasoning (Brief): Before writing code, briefly outline your logic or algorithm if the task is complex, 2.  The Code: Provide the complete, runnable code block. Do not use placeholders (like  ... code here) unless explicitly requested to be brief, 3.  Explanation: After the code, explain key decisions (e.g., 'I used a generator here to save memory')"
                "LIBRARIES & DEPENDENCIES: 1. Prioritize standard libraries where possible, 2. For data manipulation, use pandas or polars, 3. For API interaction, use httpx or requests, 4. For data validation, use pydantic."
                "CRITICAL INSTRUCTIONS: 1. No Hallucinations: If a library or method does not exist, do not invent it. If you are unsure, state your limitations, 2. Security: Avoid hardcoding API keys or credentials. Suggest using os.getenv() or python-dotenv, 3. Do not change any codes, functions, logic, features that is not related, 4. Do not add additional codes, functions, logic, features without my request.\n"
                f"REQUEST: {self.prompt}"
            )
            
            current_parts = [types.Part.from_text(text=current_prompt_text)]

            # 4. Attach Files
            for path_str in self.file_paths:
                path = Path(path_str)
                if path.exists():
                    try:
                        with path.open("r", encoding="utf-8", errors="ignore") as f:
                            file_content = f.read()
                            current_parts.append(types.Part.from_text(text=f"\n[FILE: {path.name}]\n{file_content}\n"))
                    except OSError as e:
                        self.error.emit(f"Failed to read file {path.name}: {e}")
                        return

            gemini_contents.append(types.Content(role="user", parts=current_parts))

            # 5. Safety Config
            safety = [
                types.SafetySetting(category=c, threshold="BLOCK_NONE")
                for c in [
                    "HARM_CATEGORY_HARASSMENT", 
                    "HARM_CATEGORY_HATE_SPEECH",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT", 
                    "HARM_CATEGORY_DANGEROUS_CONTENT"
                ]
            ]

            # 6. API Call
            response = client.models.generate_content(
                model=self.model,
                contents=gemini_contents,
                config=types.GenerateContentConfig(safety_settings=safety, temperature=0.8)
            )

            if response.text: 
                self.finished.emit(response.text)
            else: 
                self.error.emit("Blocked by Safety Filters (Empty Response)")

        except Exception as e:
            error_str = str(e)
            if "ResourceExhausted" in error_str or "429" in error_str:
                self.error.emit(f"Rate limit exceeded. Please wait. Details: {e}")
            elif "GoogleAuthError" in error_str or "401" in error_str or "Unauthenticated" in error_str:
                self.error.emit(f"Authentication error. Check API key. Details: {e}")
            else:
                self.error.emit(f"An unexpected error occurred: {e}")
        finally:
            GeminiWorker.RATE_LIMITER.release()