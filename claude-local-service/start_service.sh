#!/bin/bash

# Claude Local Service 启动脚本
# 端口: 25999
# 模型: claude-sonnet-4-5-20250929

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=================================="
echo "Claude Local Service"
echo "=================================="
echo ""

# 检查端口是否被占用
PORT=25999
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  端口 $PORT 已被占用"
    echo ""
    echo "选择操作:"
    echo "1) 停止占用端口的进程并重新启动"
    echo "2) 取消启动"
    read -p "请选择 (1/2): " choice
    
    if [ "$choice" = "1" ]; then
        echo "正在停止占用端口的进程..."
        lsof -ti:$PORT | xargs kill -9 2>/dev/null
        sleep 1
        echo "✓ 已停止"
    else
        echo "已取消启动"
        exit 0
    fi
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "❌ 错误: .env 文件不存在"
    echo "请先配置 .env 文件"
    exit 1
fi

# 检查依赖
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "❌ 错误: 未安装依赖"
    echo "请先运行: pip3 install -r requirements.txt"
    exit 1
fi

echo "✓ 配置检查完成"
echo ""
echo "启动信息:"
echo "  - 端口: $PORT"
echo "  - 地址: http://127.0.0.1:$PORT"
echo "  - 模型: claude-sonnet-4-5-20250929"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""
echo "=================================="
echo ""

# 启动服务
python3 server.py
