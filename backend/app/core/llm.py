import httpx
import logging
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from .config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.providers = {
            "claude": settings.LLM_SERVICE_URL,
            "gemini": settings.GEMINI_SERVICE_URL
        }
        self.default_provider = "claude"
        self.headers = {"Content-Type": "application/json"}
    
    def get_base_url(self, provider: Optional[str] = None) -> str:
        provider = provider or self.default_provider
        return self.providers.get(provider, self.providers[self.default_provider])

    async def check_health(self) -> bool:
        """Check if LLM services are reachable"""
        results = {}
        async with httpx.AsyncClient(trust_env=False) as client:
            for name, url in self.providers.items():
                try:
                    response = await client.get(f"{url}/health", timeout=5.0)
                    results[name] = response.status_code == 200
                except Exception:
                    results[name] = False
        return any(results.values())

    async def simple_chat(self, message: str, system: Optional[str] = None, provider: Optional[str] = None) -> str:
        """Send a simple message to LLM"""
        return await self.chat_completion([{"role": "user", "content": message}], system, provider)

    async def chat_completion(self, messages: List[Dict[str, str]], system: Optional[str] = None, provider: Optional[str] = None, timeout: float = 180.0) -> str:
        """Send full chat history to LLM"""
        base_url = self.get_base_url(provider)
        url = f"{base_url}/chat"
        
        payload = {
            "messages": messages,
            "system": system
        }

        # Debug Log Request
        try:
            # Use settings.BASE_DIR if available, else relative to this file
            log_dir = getattr(settings, "BASE_DIR", os.getcwd())
            debug_log_path = os.path.join(log_dir, "llm_debug.log")
            
            with open(debug_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n{'='*50}\n[{datetime.now().isoformat()}] REQUEST ({provider or self.default_provider})\n{'='*50}\n")
                if system:
                    f.write(f"SYSTEM PROMPT:\n{system}\n\n")
                f.write(f"MESSAGES:\n{json.dumps(messages, indent=2, ensure_ascii=False)}\n")
        except Exception as e:
            logger.error(f"Failed to write debug log (Request): {e}")
        
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.post(url, json=payload, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                
                content = ""
                if data.get("success"):
                    # Different services might return structure slightly differently,
                    # but our wrapper services (server.py) standardized it to:
                    # {"success": True, "data": {"content": [{"text": "..."}]}}
                    content = data["data"]["content"][0]["text"]
                else:
                    error_msg = data.get("error", "Unknown error")
                    raise Exception(f"LLM API Error ({provider or self.default_provider}): {error_msg}")
                
                # Debug Log Response
                try:
                    with open(debug_log_path, "a", encoding="utf-8") as f:
                        f.write(f"\n[{datetime.now().isoformat()}] RESPONSE:\n{content}\n{'='*50}\n")
                except Exception as e:
                    logger.error(f"Failed to write debug log (Response): {e}")

                return content
                
        except Exception as e:
            logger.error(f"LLM Chat Completion Error: {e}")
            raise

    async def generate_json(self, prompt: str, system: Optional[str] = None, provider: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Generate and parse JSON response"""
        import json
        
        # Ensure we ask for JSON
        prompt += "\n\nIMPORTANT: Output ONLY valid JSON."
        
        try:
            response_text = await self.simple_chat(prompt, system, provider)
            
            # Clean up markdown code blocks if present
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            return json.loads(cleaned_text.strip())
        except Exception as e:
            logger.error(f"JSON Generation Error: {e}")
            return None

llm_client = LLMClient()
