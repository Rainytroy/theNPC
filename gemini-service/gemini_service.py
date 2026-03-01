import google.generativeai as genai
from config import settings
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL
        self.model = genai.GenerativeModel(self.model_name)

    def chat(self, 
             messages: List[Dict[str, str]], 
             temperature: float = 0.7,
             system: Optional[str] = None) -> Dict[str, Any]:
        """
        Send chat request to Gemini API
        Args:
            messages: [{"role": "user"|"assistant", "content": "..."}]
            system: System instruction
        """
        try:
            # Gemini SDK handles system instructions differently (usually at model init),
            # but for per-request, we can prepend it or use specific API if available.
            # In 1.5 Pro, system instruction is supported at model creation or generate_content.
            
            # Re-init model if system instruction provided (or pass to count_tokens etc, but generate_content takes contents)
            # Actually, `GenerativeModel` takes `system_instruction` in constructor.
            # For dynamic system prompt per request, we might need to instantiate here.
            
            current_model = self.model
            if system:
                current_model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=system
                )

            # Convert OpenAI/Claude style messages to Gemini history
            # Gemini uses: role="user"|"model"
            gemini_history = []
            last_user_message = ""
            
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                content = msg["content"]
                
                # Gemini generate_content expects the *next* message as argument, history as context.
                # But here we probably receive the full history including the last user message.
                # We need to split.
                
                if msg == messages[-1] and msg["role"] == "user":
                    last_user_message = content
                else:
                    gemini_history.append({"role": role, "parts": [content]})

            # Start chat
            chat = current_model.start_chat(history=gemini_history)
            
            # Config
            generation_config = genai.types.GenerationConfig(
                temperature=temperature
            )

            # Send message
            response = chat.send_message(last_user_message, generation_config=generation_config)
            
            return {
                "success": True,
                "data": {
                    "content": [
                        {"text": response.text}
                    ]
                }
            }

        except Exception as e:
            logger.error(f"Gemini API Error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

gemini_service = GeminiService()
