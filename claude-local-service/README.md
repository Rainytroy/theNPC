# Claude Local Service

一个本地的 Claude API 服务，提供交互式CLI和HTTP API两种使用方式。

## ✨ 功能特性

- 🚀 **HTTP API 服务** - 简单易用的 REST API 接口
- 💬 **交互式 CLI** - 支持实时对话和模型切换
- 🔧 **灵活配置** - 支持13+个Claude模型（包括Claude 4系列）
- 📝 **完整功能** - 支持多轮对话、系统提示等
- 🔒 **安全管理** - 环境变量管理 API Key
- 📊 **简洁日志** - 外部调用时显示清晰的请求/响应

## 🎯 两种使用方式

### 方式1: 交互式CLI（推荐用于测试和对话）

```bash
# 终端1: 启动服务
cd theNPC/claude-local-service
python3 server.py

# 终端2: 启动交互式CLI
python3 interactive_cli.py
```

**交互式CLI功能**:
```
You: 你好
Claude: 你好！有什么可以帮助你的？

You: /model claude-sonnet-4-5-20250929
✓ 已切换到: claude-sonnet-4-5-20250929

You: /models     # 查看所有可用模型
You: /clear      # 清空对话历史
You: /history    # 查看对话历史
You: /config     # 查看当前配置
You: /help       # 显示帮助信息
You: /exit       # 退出
```

### 方式2: HTTP API（用于应用集成）

启动服务后，其他应用可以调用API：

```bash
curl -X POST "http://localhost:8000/simple-chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "你好"}'
```

**外部调用时的服务器日志**（简洁格式）:
```
────────────────────────────────────────
[REQUEST] 127.0.0.1 → POST /simple-chat
帮我写一个Python函数计算斐波那契数列

[RESPONSE] claude-sonnet-4-20250514
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
────────────────────────────────────────
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd theNPC/claude-local-service
pip3 install -r requirements.txt
```

### 2. 配置 API Key

复制配置模板并填入你的信息：

```bash
cp .env.template .env
nano .env  # 或使用其他编辑器
```

编辑 `.env` 文件：

```bash
CLAUDE_API_KEY=your_api_key_here
CLAUDE_API_URL=your_api_url_here
CLAUDE_MODEL=claude-sonnet-4-20250514  # 见下方可用模型列表
```

### 3. 启动服务

```bash
python3 server.py
```

服务将在 `http://localhost:8000` 启动。

## 📋 可用模型列表

所有模型已在 `.env` 文件中详细注释，包括：

### Claude 4 系列（最新）
- `claude-sonnet-4-5-20250929` - Sonnet 4.5 最新版 (200K)
- `claude-sonnet-4-5-20250929:1m` - Sonnet 4.5 1M版本 🔥
- `claude-haiku-4-5-20251001` - Haiku 4.5 最快速度
- `claude-sonnet-4-20250514` - Sonnet 4 标准版 ⭐
- `claude-sonnet-4-20250514:1m` - Sonnet 4 1M版本 🔥
- `claude-opus-4-5-20251101` - Opus 4.5 最强性能
- `claude-opus-4-1-20250805` - Opus 4.1

### Claude 3.5 系列
- `claude-3-5-sonnet-20241022` - Sonnet 3.5
- `claude-3-5-haiku-20241022` - Haiku 3.5

### Claude 3 系列
- `claude-3-opus-20240229` - Opus 3 最强
- `claude-3-sonnet-20240229` - Sonnet 3 平衡
- `claude-3-haiku-20240307` - Haiku 3 快速

**选择建议**:
- 日常使用: `claude-haiku-4-5-20251001` (最快)
- 平衡性能: `claude-sonnet-4-5-20250929` (推荐)
- 最强性能: `claude-opus-4-5-20251101` (最强)
- 超长文档: `claude-sonnet-4-5-20250929:1m` (1M context)

## 📡 API 接口

### 1. 服务状态检查

```bash
GET http://localhost:8000/
```

### 2. 简单聊天（推荐）

```bash
POST http://localhost:8000/simple-chat
Content-Type: application/json

{
    "message": "你好，Claude！",
    "system": "你是一个有用的助手"
}
```

### 3. 完整聊天（支持多轮对话）

```bash
POST http://localhost:8000/chat
Content-Type: application/json

{
    "messages": [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
        {"role": "user", "content": "请继续"}
    ],
    "model": "claude-sonnet-4-5-20250929",
    "max_tokens": 4096,
    "temperature": 0.7
}
```

### 4. 获取配置信息

```bash
GET http://localhost:8000/config
```

## 💻 使用示例

### Python 客户端

```python
import requests

def chat(message):
    response = requests.post(
        "http://localhost:8000/simple-chat",
        json={"message": message}
    )
    return response.json()["message"]

# 使用
print(chat("你好，Claude！"))
```

完整示例见 `client_example.py`

### curl 示例

```bash
# 简单对话
curl -X POST "http://localhost:8000/simple-chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "你好"}'

# 切换模型（在请求中指定）
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "messages": [{"role": "user", "content": "你好"}],
       "model": "claude-opus-4-5-20251101"
     }'
```

## ⚙️ 配置选项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `CLAUDE_API_KEY` | - | Claude API Key（必填） |
| `CLAUDE_API_URL` | - | Claude API 地址（必填） |
| `CLAUDE_MODEL` | claude-sonnet-4-20250514 | 默认模型 |
| `HOST` | 127.0.0.1 | 服务器地址 |
| `PORT` | 8000 | 服务器端口 |
| `MAX_TOKENS` | 4096 | 最大token数 |
| `TEMPERATURE` | 0.7 | 温度参数 |

## 🔧 故障排除

### 交互式CLI无法连接
```bash
# 确保服务已启动
ps aux | grep "python3 server.py"

# 检查端口
lsof -ti:8000
```

### 服务端口被占用
```bash
# 杀死占用端口的进程
lsof -ti:8000 | xargs kill -9
```

### API Key错误
- 检查 `.env` 文件是否正确配置
- 确认API Key有效且有权限

## 📝 开发说明

### 项目结构
```
claude-local-service/
├── server.py              # HTTP服务器（带简洁日志）
├── interactive_cli.py     # 交互式CLI工具
├── claude_service.py      # Claude API 封装
├── config.py             # 配置管理
├── client_example.py     # 客户端示例
├── .env                  # 配置文件（不要提交）
├── .env.template         # 配置模板
└── README.md            # 本文档
```

### 扩展开发

如需添加新功能，可以修改：
- `server.py` - 添加新的API端点
- `claude_service.py` - 扩展Claude API调用
- `interactive_cli.py` - 添加新的CLI命令

## 📄 许可证

MIT License
