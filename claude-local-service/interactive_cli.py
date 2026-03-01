#!/usr/bin/env python3
"""
Claude Interactive CLI - 交互式命令行工具
支持对话和模型切换
"""

import requests
import sys
import os
from typing import List, Dict, Optional

# ANSI 颜色代码
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'

class ClaudeInteractiveCLI:
    """Claude 交互式命令行客户端"""
    
    def __init__(self, base_url="http://localhost:25999"):
        self.base_url = base_url
        self.conversation_history: List[Dict[str, str]] = []
        self.current_model = None
        self.system_prompt = None
        
    def check_connection(self) -> bool:
        """检查服务连接"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get("claude_configured"):
                    # 获取当前配置
                    config = requests.get(f"{self.base_url}/config").json()
                    self.current_model = config.get("model")
                    return True
            return False
        except:
            return False
    
    def get_available_models(self) -> List[str]:
        """获取可用模型列表（从.env注释中解析）"""
        models = [
            "claude-sonnet-4-5-20250929",
            "claude-sonnet-4-5-20250929:1m",
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-20250514",
            "claude-sonnet-4-20250514:1m",
            "claude-opus-4-5-20251101",
            "claude-opus-4-1-20250805",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]
        return models
    
    def chat(self, message: str, model: Optional[str] = None) -> Optional[str]:
        """发送聊天消息"""
        try:
            # 构建消息历史
            messages = self.conversation_history + [
                {"role": "user", "content": message}
            ]
            
            data = {
                "messages": messages,
                "model": model or self.current_model
            }
            
            if self.system_prompt:
                data["system"] = self.system_prompt
            
            # 添加CLI标识，让服务器知道这是CLI调用
            headers = {
                "Content-Type": "application/json",
                "X-Client-Type": "CLI"
            }
            
            response = requests.post(
                f"{self.base_url}/chat",
                json=data,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    assistant_message = result["data"]["content"][0]["text"]
                    
                    # 添加到历史记录
                    self.conversation_history.append({"role": "user", "content": message})
                    self.conversation_history.append({"role": "assistant", "content": assistant_message})
                    
                    return assistant_message
                else:
                    return f"错误: {result.get('error')}"
            else:
                return f"HTTP错误 {response.status_code}"
                
        except requests.exceptions.Timeout:
            return "请求超时（60秒）"
        except Exception as e:
            return f"异常: {str(e)}"
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
        print(f"{Colors.YELLOW}✓ 已清空对话历史{Colors.RESET}")
    
    def show_history(self):
        """显示对话历史"""
        if not self.conversation_history:
            print(f"{Colors.GRAY}暂无对话历史{Colors.RESET}")
            return
        
        print(f"\n{Colors.CYAN}=== 对话历史 ==={Colors.RESET}")
        for i, msg in enumerate(self.conversation_history, 1):
            role = "You" if msg["role"] == "user" else "Claude"
            color = Colors.GREEN if msg["role"] == "user" else Colors.BLUE
            content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            print(f"{color}{i}. {role}: {content}{Colors.RESET}")
        print()
    
    def show_config(self):
        """显示当前配置"""
        try:
            response = requests.get(f"{self.base_url}/config")
            if response.status_code == 200:
                config = response.json()
                print(f"\n{Colors.CYAN}=== 当前配置 ==={Colors.RESET}")
                print(f"模型: {Colors.YELLOW}{config.get('model')}{Colors.RESET}")
                print(f"Max Tokens: {config.get('max_tokens')}")
                print(f"Temperature: {config.get('temperature')}")
                print(f"API URL: {config.get('api_url')}")
                print()
        except Exception as e:
            print(f"{Colors.RED}无法获取配置: {e}{Colors.RESET}")
    
    def show_models(self):
        """显示可用模型列表"""
        models = self.get_available_models()
        print(f"\n{Colors.CYAN}=== 可用模型 ==={Colors.RESET}")
        for model in models:
            indicator = " ⭐" if model == self.current_model else ""
            if ":1m" in model:
                print(f"{Colors.YELLOW}{model}{Colors.RESET} (1M context) 🔥{indicator}")
            else:
                print(f"{model}{indicator}")
        print()
    
    def switch_model(self, model: str):
        """切换模型"""
        available = self.get_available_models()
        if model in available:
            self.current_model = model
            print(f"{Colors.GREEN}✓ 已切换到: {model}{Colors.RESET}")
        else:
            print(f"{Colors.RED}✗ 未知模型: {model}{Colors.RESET}")
            print(f"{Colors.GRAY}使用 /models 查看可用模型{Colors.RESET}")
    
    def show_help(self):
        """显示帮助信息"""
        print(f"\n{Colors.CYAN}=== 可用命令 ==={Colors.RESET}")
        print(f"{Colors.YELLOW}/model <模型名>{Colors.RESET}  - 切换模型")
        print(f"{Colors.YELLOW}/models{Colors.RESET}          - 查看所有可用模型")
        print(f"{Colors.YELLOW}/clear{Colors.RESET}           - 清空对话历史")
        print(f"{Colors.YELLOW}/history{Colors.RESET}         - 查看对话历史")
        print(f"{Colors.YELLOW}/config{Colors.RESET}          - 查看当前配置")
        print(f"{Colors.YELLOW}/help{Colors.RESET}            - 显示此帮助信息")
        print(f"{Colors.YELLOW}/exit{Colors.RESET}            - 退出程序")
        print()
    
    def handle_command(self, command: str) -> bool:
        """处理命令，返回True表示继续，False表示退出"""
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        
        if cmd == "/exit" or cmd == "/quit":
            return False
        elif cmd == "/clear":
            self.clear_history()
        elif cmd == "/history":
            self.show_history()
        elif cmd == "/config":
            self.show_config()
        elif cmd == "/models":
            self.show_models()
        elif cmd == "/help":
            self.show_help()
        elif cmd == "/model":
            if len(parts) > 1:
                self.switch_model(parts[1])
            else:
                print(f"{Colors.RED}用法: /model <模型名>{Colors.RESET}")
        else:
            print(f"{Colors.RED}未知命令: {cmd}{Colors.RESET}")
            print(f"{Colors.GRAY}输入 /help 查看可用命令{Colors.RESET}")
        
        return True
    
    def run(self):
        """运行交互式CLI"""
        # 打印欢迎信息
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*50}")
        print(f"Claude Interactive CLI")
        print(f"{'='*50}{Colors.RESET}\n")
        
        # 检查连接
        print(f"{Colors.GRAY}正在连接服务...{Colors.RESET}")
        if not self.check_connection():
            print(f"{Colors.RED}✗ 无法连接到服务: {self.base_url}{Colors.RESET}")
            print(f"{Colors.YELLOW}请确保服务已启动: python3 server.py{Colors.RESET}")
            sys.exit(1)
        
        print(f"{Colors.GREEN}✓ 已连接到服务{Colors.RESET}")
        print(f"{Colors.GRAY}当前模型: {Colors.YELLOW}{self.current_model}{Colors.RESET}")
        print(f"\n{Colors.GRAY}输入 '/help' 查看命令，输入 '/exit' 退出{Colors.RESET}\n")
        
        # 主循环
        try:
            while True:
                try:
                    # 读取用户输入
                    user_input = input(f"{Colors.GREEN}You:{Colors.RESET} ").strip()
                    
                    if not user_input:
                        continue
                    
                    # 处理命令
                    if user_input.startswith('/'):
                        if not self.handle_command(user_input):
                            break
                        continue
                    
                    # 发送聊天消息
                    print(f"{Colors.BLUE}Claude:{Colors.RESET} ", end='', flush=True)
                    response = self.chat(user_input)
                    
                    if response:
                        print(response)
                    print()  # 空行
                    
                except KeyboardInterrupt:
                    print(f"\n{Colors.YELLOW}使用 /exit 退出{Colors.RESET}")
                    continue
                except EOFError:
                    break
                    
        except Exception as e:
            print(f"\n{Colors.RED}程序错误: {e}{Colors.RESET}")
        
        print(f"\n{Colors.CYAN}再见！{Colors.RESET}\n")

def main():
    """主函数"""
    # 可以通过环境变量或命令行参数指定服务地址
    base_url = os.getenv("CLAUDE_SERVICE_URL", "http://localhost:25999")
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    cli = ClaudeInteractiveCLI(base_url)
    cli.run()

if __name__ == "__main__":
    main()
