from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import uvicorn
import logging
from config import settings
from gemini_service import gemini_service

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gemini Local Service")

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    system: Optional[str] = None

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "gemini-local"}

@app.post("/chat")
async def chat(request: ChatRequest):
    logger.info(f"Received chat request: {len(request.messages)} messages")
    result = gemini_service.chat(
        messages=request.messages,
        temperature=request.temperature,
        system=request.system
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return {"success": True, "data": result["data"]}

if __name__ == "__main__":
    logger.info(f"Starting Gemini Service on {settings.HOST}:{settings.PORT}")
    uvicorn.run("server:app", host=settings.HOST, port=settings.PORT, reload=True)
