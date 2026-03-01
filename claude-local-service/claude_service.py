import requests
import json
from typing import Dict, Any, Optional, List
from config import get_settings
import logging

logger = logging.getLogger(__name__)

class ClaudeService:
    def __init__(self, api_key: str, api_url: str = "https://api.anthropic.com"):
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    
    def chat(self, 
             messages: List[Dict[str, str]], 
             model: str = "claude-3-sonnet-20240229",
             max_tokens: int = 4096,
             temperature: float = 0.7,
             system: Optional[str] = None) -> Dict[str, Any]:
        """
        发送聊天请求到 Claude API
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "消息内容"}]
            model: 使用的模型名称
            max_tokens: 最大令牌数
            temperature: 温度参数
            system: 系统消息（可选）
        
        Returns:
            Claude API 的响应
        """
        try:
            # 构建请求数据
            data = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }
            
            if system:
                data["system"] = system
            
            # 发送请求
            response = requests.post(
                f"{self.api_url}/v1/messages",
                headers=self.headers,
                json=data,
                timeout=180
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                logger.error(f"Claude API 错误: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API 错误: {response.status_code}",
                    "details": response.text
                }
                
        except requests.exceptions.Timeout:
            logger.error("Claude API 请求超时")
            return {
                "success": False,
                "error": "请求超时",
                "details": "API 请求超过 180 秒未响应"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Claude API 请求异常: {str(e)}")
            return {
                "success": False,
                "error": "请求异常",
                "details": str(e)
            }
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            return {
                "success": False,
                "error": "未知错误",
                "details": str(e)
            }
    
    def simple_chat(self, user_message: str, system: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """
        简单的聊天接口，只需要提供用户消息
        
        Args:
            user_message: 用户消息
            system: 系统消息（可选）
            model: 模型名称（可选）
        
        Returns:
            Claude 的响应
        """
        messages = [{"role": "user", "content": user_message}]
        if model:
            return self.chat(messages, model=model, system=system)
        else:
            return self.chat(messages, system=system)
    
    def get_response_text(self, response: Dict[str, Any]) -> str:
        """
        从响应中提取文本内容
        
        Args:
            response: Claude API 响应
        
        Returns:
            提取的文本内容
        """
        if not response.get("success", False):
            return f"错误: {response.get('error', '未知错误')}"
        
        try:
            data = response.get("data", {})
            content = data.get("content", [])
            
            if content and len(content) > 0:
                return content[0].get("text", "")
            
            return "无响应内容"
            
        except Exception as e:
            return f"解析响应错误: {str(e)}"
