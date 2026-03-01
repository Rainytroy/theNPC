#!/bin/bash

# Claude Local Service 停止脚本

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=================================="
echo "停止 Claude Local Service"
echo "=================================="
echo ""

PORT=25999

# 检查端口是否有进程运行
if ! lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "ℹ️  端口 $PORT 上没有运行的服务"
    exit 0
fi

# 获取进程信息
PID=$(lsof -ti:$PORT)
PROCESS_INFO=$(ps -p $PID -o comm= 2>/dev/null)

echo "发现运行中的服务:"
echo "  - 端口: $PORT"
echo "  - PID: $PID"
echo "  - 进程: $PROCESS_INFO"
echo ""

read -p "是否停止该服务? (y/n): " confirm

if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    echo ""
    echo "正在停止服务..."
    
    # 尝试优雅停止
    kill $PID 2>/dev/null
    sleep 2
    
    # 检查是否已停止
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "优雅停止失败，强制停止..."
        kill -9 $PID 2>/dev/null
        sleep 1
    fi
    
    # 最终检查
    if ! lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "✓ 服务已停止"
    else
        echo "❌ 停止失败，请手动停止"
        exit 1
    fi
else
    echo "已取消"
    exit 0
fi
