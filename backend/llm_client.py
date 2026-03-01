import httpx
import logging
from typing import List, Dict, Optional, Any
from config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.base_url = settings.LLM_SERVICE_URL
        self.headers = {"Content-Type": "application/json"}
    
    async def check_health(self) -> bool:
        """Check if LLM service is reachable"""
        try:
            # trust_env=False to avoid system proxy issues on localhost
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.get(f"{self.base_url}/health", timeout=5.0)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"LLM Service health check failed: {e}")
            return False

    async def simple_chat(self, message: str, system: Optional[str] = None) -> str:
        """Send a simple message to LLM"""
        url = f"{self.base_url}/simple-chat"
        payload = {
            "message": message,
            "system": system
        }
        
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.post(url, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                if data.get("success"):
                    return data.get("message", "")
                else:
                    error_msg = data.get("error", "Unknown error")
                    raise Exception(f"LLM API Error: {error_msg}")
        except Exception as e:
            logger.error(f"LLM Chat Error: {e}")
            raise

    async def chat_completion(self, messages: List[Dict[str, str]], system: Optional[str] = None) -> str:
        """Send full chat history to LLM"""
        url = f"{self.base_url}/chat"
        payload = {
            "messages": messages,
            "system": system
        }
        
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.post(url, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                if data.get("success"):
                    return data["data"]["content"][0]["text"]
                else:
                    error_msg = data.get("error", "Unknown error")
                    raise Exception(f"LLM API Error: {error_msg}")
        except Exception as e:
            logger.error(f"LLM Chat Completion Error: {e}")
            raise

llm_client = LLMClient()
