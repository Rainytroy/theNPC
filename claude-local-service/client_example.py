#!/usr/bin/env python3
"""
Claude Local Service 客户端示例
"""

import requests
import json

class ClaudeClient:
    """Claude 本地服务客户端"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def check_status(self):
        """检查服务状态"""
        try:
            response = requests.get(f"{self.base_url}/")
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def chat(self, message, system=None):
        """简单聊天"""
        try:
            data = {"message": message}
            if system:
                data["system"] = system
                
            response = requests.post(
                f"{self.base_url}/simple-chat",
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return result.get("message")
                else:
                    return f"错误: {result.get('error')}"
            else:
                return f"HTTP 错误: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"请求异常: {str(e)}"
    
    def advanced_chat(self, messages, model=None, max_tokens=None, temperature=None, system=None):
        """高级聊天接口"""
        try:
            data = {"messages": messages}
            
            if model:
                data["model"] = model
            if max_tokens:
                data["max_tokens"] = max_tokens
            if temperature:
                data["temperature"] = temperature
            if system:
                data["system"] = system
                
            response = requests.post(
                f"{self.base_url}/chat",
                json=data
            )
            
            return response.json()
            
        except Exception as e:
            return {"error": str(e)}

def main():
    """主函数 - 演示如何使用 Claude 客户端"""
    
    print("=== Claude Local Service 客户端示例 ===\n")
    
    # 初始化客户端
    client = ClaudeClient()
    
    # 1. 检查服务状态
    print("1. 检查服务状态...")
    status = client.check_status()
    print(f"状态: {json.dumps(status, indent=2, ensure_ascii=False)}\n")
    
    if not status.get("claude_configured"):
        print("⚠️  Claude 服务未配置，请检查 .env 文件中的 API Key")
        return
    
    # 2. 简单聊天示例
    print("2. 简单聊天示例...")
    response = client.chat("你好，请简单介绍一下你自己")
    print(f"Claude: {response}\n")
    
    # 3. 带系统提示的聊天
    print("3. 带系统提示的聊天...")
    response = client.chat(
        "请帮我写一个 Python 函数来计算两个数字的最大公约数",
        system="你是一个专业的 Python 程序员，请提供简洁清晰的代码"
    )
    print(f"Claude: {response}\n")
    
    # 4. 多轮对话示例
    print("4. 多轮对话示例...")
    messages = [
        {"role": "user", "content": "我想学习 Python，你有什么建议吗？"},
        {"role": "assistant", "content": "学习 Python 是一个很好的选择！我建议你从基础语法开始..."},
        {"role": "user", "content": "那我应该从哪些基础知识开始呢？"}
    ]
    
    response = client.advanced_chat(messages)
    if response.get("success"):
        content = response["data"]["content"][0]["text"]
        print(f"Claude: {content}\n")
    else:
        print(f"错误: {response.get('error')}\n")
    
    print("=== 示例完成 ===")

if __name__ == "__main__":
    main()
