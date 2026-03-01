#!/bin/bash

# Claude Interactive CLI 启动脚本

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=================================="
echo "Claude Interactive CLI"
echo "=================================="
echo ""

# 检查服务是否运行
PORT=25999
if ! lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  警告: 服务未在端口 $PORT 运行"
    echo ""
    echo "请先启动服务:"
    echo "  ./start_service.sh"
    echo ""
    read -p "是否现在启动服务? (y/n): " start_service
    
    if [ "$start_service" = "y" ] || [ "$start_service" = "Y" ]; then
        echo ""
        echo "正在启动服务..."
        ./start_service.sh &
        sleep 3
    else
        echo "已取消"
        exit 0
    fi
fi

# 检查依赖
if ! python3 -c "import requests" 2>/dev/null; then
    echo "❌ 错误: 未安装依赖"
    echo "请先运行: pip3 install -r requirements.txt"
    exit 1
fi

echo "✓ 连接到服务: http://127.0.0.1:$PORT"
echo ""
echo "=================================="
echo ""

# 启动交互式CLI
python3 interactive_cli.py
