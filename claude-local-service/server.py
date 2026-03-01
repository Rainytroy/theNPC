import sys
import os

# Fix Windows console encoding (GBK can't handle emoji/unicode)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import logging
import json
from config import get_settings
from claude_service import ClaudeService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 简洁日志输出
def print_clean_log(client: str, endpoint: str, user_input: str, model: str, response_text: str):
    """以简洁格式打印请求和响应"""
    separator = "-" * 60
    try:
        print(f"\n{separator}")
        print(f"[REQUEST] {client} -> {endpoint}")
        print(user_input)
        print(f"\n[RESPONSE] {model}")
        print(response_text)
        print(f"{separator}\n")
    except Exception:
        print(f"[LOG] {client} -> {endpoint} (output encoding error, skipped)")

# 创建 FastAPI 应用
app = FastAPI(
    title="Claude Local Service",
    description="本地 Claude API 服务",
    version="1.0.0"
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取配置
settings = get_settings()

# 初始化 Claude 服务
claude_service = None

def init_claude_service():
    global claude_service
    
    api_key = settings.azure_claude_api_key
    api_url = settings.azure_claude_api_url
    logger.info("Initializing Claude Service with Azure Config")
        
    if not api_key:
        logger.error(f"Claude API Key ({settings.active_config}) 未配置")
        return False
    
    claude_service = ClaudeService(
        api_key=api_key,
        api_url=api_url
    )
    logger.info(f"Claude 服务已初始化 (Config: {settings.active_config})")
    return True

# 请求模型
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    system: Optional[str] = None

class SimpleChatRequest(BaseModel):
    message: str
    system: Optional[str] = None

class ConfigSwitchRequest(BaseModel):
    config: str  # "azure"
    model: str   # e.g. "claude-sonnet-4-5"

# API 路由
@app.get("/")
async def root():
    """服务状态检查"""
    return {
        "status": "running",
        "service": "Claude Local Service",
        "version": "1.0.0",
        "claude_configured": claude_service is not None,
        "active_config": settings.active_config,
        "active_model": settings.active_model
    }

@app.get("/health")
async def health():
    """健康检查"""
    if claude_service is None:
        raise HTTPException(status_code=503, detail="Claude 服务未初始化")
    
    return {"status": "healthy", "claude_service": "ready", "config": settings.active_config, "model": settings.active_model}

@app.post("/chat")
async def chat(request: ChatRequest, req: Request):
    """完整的聊天接口"""
    if claude_service is None:
        raise HTTPException(status_code=503, detail="Claude 服务未初始化，请检查 API Key 配置")
    
    try:
        # 转换消息格式
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # 使用请求参数或默认配置
        # 优先使用 active_model
        model = request.model or settings.active_model
        
        max_tokens = request.max_tokens or settings.max_tokens
        temperature = request.temperature or settings.temperature
        
        # 获取最后一条用户消息用于日志
        last_user_message = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_message = msg["content"]
                break
        
        # 调用 Claude 服务
        response = claude_service.chat(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=request.system
        )
        
        # 打印简洁日志（仅在非CLI调用时）
        if response.get("success"):
            # 检查是否是CLI调用
            is_cli = req.headers.get("X-Client-Type") == "CLI"
            if not is_cli:
                response_text = response["data"]["content"][0]["text"]
                client_ip = req.client.host if req.client else "unknown"
                print_clean_log(client_ip, "POST /chat", last_user_message, model, response_text)
        
        return response
        
    except Exception as e:
        logger.error(f"聊天请求处理错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@app.post("/simple-chat")
async def simple_chat(request: SimpleChatRequest, req: Request):
    """简单的聊天接口"""
    if claude_service is None:
        raise HTTPException(status_code=503, detail="Claude 服务未初始化，请检查 API Key 配置")
    
    try:
        response = claude_service.simple_chat(
            user_message=request.message,
            system=request.system,
            model=settings.active_model
        )
        
        # 提取文本内容
        if response.get("success"):
            text_content = claude_service.get_response_text(response)
            
            # 打印简洁日志（仅在非CLI调用时）
            is_cli = req.headers.get("X-Client-Type") == "CLI"
            if not is_cli:
                client_ip = req.client.host if req.client else "unknown"
                print_clean_log(client_ip, "POST /simple-chat", request.message, settings.active_model, text_content)
            
            return {
                "success": True,
                "message": text_content,
                "raw_response": response
            }
        else:
            return response
            
    except Exception as e:
        logger.error(f"简单聊天请求处理错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

@app.get("/config")
async def get_config():
    """获取当前配置信息（不包含敏感信息）"""
    return {
        "active_config": settings.active_config,
        "model": settings.active_model,
        "max_tokens": settings.max_tokens,
        "temperature": settings.temperature,
        "server_host": settings.host,
        "server_port": settings.port,
        "api_key_configured": bool(settings.azure_claude_api_key)
    }

@app.post("/config/switch")
async def switch_config(request: ConfigSwitchRequest):
    """切换 API 模型配置"""
    if request.config not in ["azure"]:
        raise HTTPException(status_code=400, detail="Invalid config type. Must be 'azure'")
    
    settings.active_config = request.config
    settings.active_model = request.model
    
    # Re-initialize service with new config
    if init_claude_service():
        msg = f"Switched to {settings.active_config} configuration with model {settings.active_model}"
        logger.info(msg)
        print(f"\n[CONFIG SWITCH] {msg}\n")
        return {
            "success": True, 
            "active_config": settings.active_config,
            "active_model": settings.active_model,
            "message": msg
        }
    else:
        msg = f"Switched to {settings.active_config} but failed to initialize service (missing key?)"
        logger.error(msg)
        return {
            "success": False, 
            "active_config": settings.active_config,
            "message": msg
        }

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("Claude Local Service 正在启动...")
    if not init_claude_service():
        logger.warning("Claude 服务初始化失败，请检查配置")

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info"
    )
