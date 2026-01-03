import os
import time
import mimetypes
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QThread, pyqtSignal
from google import genai
from google.genai import types

from utils import RateLimiter

class GeminiWorker(QThread):
    """
    Worker thread to handle Gemini API requests asynchronously.
    Supports robust file handling including Images, Audio, PDF, and Text.
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
        history_context: list[dict[str, str]],
        use_grounding: bool = False,
        system_instruction: Optional[str] = None,
        temperature: float = 0.8,
        top_p: float = 0.95
    ):
        super().__init__()
        self.api_key = api_key
        self.prompt = prompt
        self.model = model
        self.file_paths = file_paths
        self.history_context = history_context
        self.use_grounding = use_grounding
        self.system_instruction = system_instruction
        self.temperature = temperature
        self.top_p = top_p
        
        # Initialize mimetypes
        mimetypes.init()

    def run(self) -> None:
        try:
            # 1. Check Rate Limit
            if not GeminiWorker.RATE_LIMITER.acquire(blocking=True, timeout=30):
                self.error.emit("Rate limit exceeded: Could not acquire token after waiting.")
                return

            client = genai.Client(api_key=self.api_key)
            gemini_contents = []

            # 2. Build Chat History
            for item in self.history_context:
                parts = [types.Part.from_text(text=item['text'])]
                gemini_contents.append(types.Content(role=item['role'], parts=parts))

            # 3. Construct Prompt Parts
            current_parts = []
            
            # --- Enhanced File Processing ---
            # Separate plain text files from binary media (Image/Audio/PDF)
            # Binary files are uploaded via File API for "unlimited" feel and better handling.
            
            for path_str in self.file_paths:
                path = Path(path_str)
                if not path.exists():
                    continue

                mime_type, _ = mimetypes.guess_type(path)
                if not mime_type:
                    mime_type = "text/plain" # Default fallback

                # Determine strategy based on MIME type
                is_media_or_pdf = (
                    mime_type.startswith("image/") or 
                    mime_type.startswith("audio/") or 
                    mime_type == "application/pdf"
                )

                if is_media_or_pdf:
                    # >>> STRATEGY A: Upload via File API (Professional/Large File Support) <<<
                    try:
                        # Upload file
                        uploaded_file = client.files.upload(path=path)
                        
                        # Wait for processing (Crucial for Audio/Video)
                        while uploaded_file.state.name == "PROCESSING":
                            time.sleep(1)
                            uploaded_file = client.files.get(name=uploaded_file.name)
                            
                        if uploaded_file.state.name == "FAILED":
                            raise ValueError(f"File {path.name} failed processing on server.")

                        # Create Part from URI
                        current_parts.append(types.Part.from_uri(
                            file_uri=uploaded_file.uri,
                            mime_type=uploaded_file.mime_type
                        ))
                    except Exception as e:
                        # If upload fails, try to continue with other files but warn logic could be added here
                        print(f"Failed to upload media {path.name}: {e}")
                
                else:
                    # >>> STRATEGY B: Read Text Content (Low Latency for Code/Text) <<<
                    try:
                        # Try utf-8 first, fallback to latin-1 if needed
                        try:
                            content = path.read_text(encoding="utf-8")
                        except UnicodeDecodeError:
                            content = path.read_text(encoding="latin-1")
                            
                        # Format as a labeled text block
                        text_block = f"\n[FILE: {path.name}]\n{content}\n"
                        current_parts.append(types.Part.from_text(text=text_block))
                    except Exception as e:
                        print(f"Failed to read text file {path.name}: {e}")

            # Add the user prompt text
            if self.prompt:
                current_parts.append(types.Part.from_text(text=self.prompt))

            if not current_parts:
                self.error.emit("No content to send (Prompt is empty and no valid files).")
                return

            gemini_contents.append(types.Content(role="user", parts=current_parts))

            # 4. Safety Config
            safety = [
                types.SafetySetting(category=c, threshold="BLOCK_NONE")
                for c in [
                    "HARM_CATEGORY_HARASSMENT", 
                    "HARM_CATEGORY_HATE_SPEECH",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT", 
                    "HARM_CATEGORY_DANGEROUS_CONTENT"
                ]
            ]

            # 5. Configure Tools (Grounding)
            tools = []
            if self.use_grounding:
                tools = [types.Tool(google_search=types.GoogleSearch())]

            # 6. API Call
            api_system_instruction = self.system_instruction if (self.system_instruction and self.system_instruction.strip()) else None

            response = client.models.generate_content(
                model=self.model,
                contents=gemini_contents,
                config=types.GenerateContentConfig(
                    safety_settings=safety, 
                    temperature=self.temperature,
                    top_p=self.top_p,
                    tools=tools,
                    system_instruction=api_system_instruction
                )
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