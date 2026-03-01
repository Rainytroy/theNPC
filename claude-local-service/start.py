#!/usr/bin/env python3
"""
Claude Local Service 启动脚本
"""

import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """检查依赖是否已安装"""
    try:
        import fastapi
        import uvicorn
        import requests
        import pydantic
        import anthropic
        print("✅ 所有依赖已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def check_config():
    """检查配置文件"""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ 未找到 .env 配置文件")
        print("请复制 .env.template 为 .env 并填入你的 API Key")
        print("命令: cp .env.template .env")
        return False
    
    # 读取 .env 文件检查 API Key
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "your_claude_api_key_here" in content:
        print("⚠️  检测到默认的 API Key，请在 .env 文件中填入真实的 Claude API Key")
        return False
    
    if not any(line.startswith("CLAUDE_API_KEY=") and len(line.split("=", 1)[1].strip()) > 10 
              for line in content.split('\n')):
        print("⚠️  未找到有效的 CLAUDE_API_KEY 配置")
        return False
    
    print("✅ 配置文件检查通过")
    return True

def main():
    """主函数"""
    print("=== Claude Local Service 启动器 ===\n")
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    # 检查配置
    if not check_config():
        return 1
    
    print("\n🚀 启动 Claude Local Service...")
    print("服务地址: http://localhost:8000")
    print("API 文档: http://localhost:8000/docs")
    print("按 Ctrl+C 停止服务\n")
    
    try:
        # 启动服务
        result = subprocess.run([
            sys.executable, "server.py"
        ], cwd=os.path.dirname(os.path.abspath(__file__)))
        
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
        return 0
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
