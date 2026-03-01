# theNPC - Generative Agent Sandbox

An AI-driven NPC (Non-Player Character) simulation system that creates living, breathing game worlds with autonomous characters. NPCs have their own schedules, relationships, quests, and memories — all powered by large language models.

> **Important:** This project requires you to **bring your own LLM API keys** (Claude or Gemini). Image generation and manga features require an external image service — these are optional and the core system works without them. See [Configuration](#2-configure-environment-variables) for details.

[中文文档](#中文文档)

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Frontend (Vue 3)                   │
│                  http://localhost:26001               │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│                 Backend API (FastAPI)                 │
│                  http://localhost:26000               │
│  Engines: Dialogue / Director / Quest / Social / ... │
└────────┬─────────────────────────────┬───────────────┘
         │                             │
┌────────▼──────────┐     ┌────────────▼───────────────┐
│  Claude Service   │     │      Gemini Service        │
│  :25999           │     │      :25998                │
│  (NPC intelligence│     │  (NPC intelligence         │
│   & dialogue)     │     │   alternative provider)    │
└───────────────────┘     └────────────────────────────┘
```

| Service | Port | Role |
|---------|------|------|
| Frontend | 26001 | Vue 3 + TypeScript UI |
| Backend API | 26000 | Core game logic, world management, quest/NPC engines |
| Claude Service | 25999 | LLM proxy — forwards requests to Claude API |
| Gemini Service | 25998 | LLM proxy — forwards requests to Gemini API |

## Prerequisites

- **Python 3.13+**
- **Node.js 18+** & npm
- **API key** for at least one LLM provider:
  - [Anthropic Claude](https://console.anthropic.com/) — or Azure-hosted Claude
  - [Google Gemini](https://aistudio.google.com/) (alternative)
- *(Optional)* External image generation API for NPC avatars & manga pages
- *(Optional)* Aliyun OSS account for image storage

## Quick Start

### 1. Clone & Enter Project

```bash
git clone https://github.com/Rainytroy/theNPC.git
cd theNPC
```

### 2. Configure Environment Variables

Each service requires its own `.env` file. **You must provide your own API keys.**

```bash
# Backend
cp backend/.env.template backend/.env

# Claude Service (required — primary LLM)
cp claude-local-service/.env.template claude-local-service/.env

# Gemini Service (optional — alternative LLM)
cp gemini-service/.env.template gemini-service/.env
```

Then edit each `.env` file and fill in your values. See [Service Configuration](#service-configuration) below for details on each field.

### 3. Install Dependencies

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
pip install -r requirements.txt

# Claude Service
cd ../claude-local-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Gemini Service (optional)
cd ../gemini-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 4. Start All Services

**Windows (one-click):**
```bash
start_system.bat
```

**Manual (any OS) — open 4 terminals:**

```bash
# Terminal 1: Claude Service
cd claude-local-service && python server.py

# Terminal 2: Gemini Service (optional)
cd gemini-service && python server.py

# Terminal 3: Backend API
cd backend && python main.py

# Terminal 4: Frontend
cd frontend && npm run dev
```

Open **http://localhost:26001** in your browser.

---

## Service Configuration

### Claude Service (`claude-local-service/`)

Local proxy for the Claude API. **You need your own API key.**

```env
# Option A: Anthropic direct
CLAUDE_API_KEY=your_claude_api_key_here
CLAUDE_API_URL=https://api.anthropic.com

# Option B: Azure-hosted Claude
AZURE_CLAUDE_API_KEY=your_azure_key
AZURE_CLAUDE_API_URL=https://your-resource.services.ai.azure.com/anthropic
AZURE_CLAUDE_MODEL=claude-sonnet-4-5

# Model (for direct Anthropic)
CLAUDE_MODEL=claude-sonnet-4-5-20250929

# Server
HOST=127.0.0.1
PORT=25999
MAX_TOKENS=4096
TEMPERATURE=0.7
```

**How to get a key:** [Anthropic Console](https://console.anthropic.com/) → Create API key

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service status |
| `/health` | GET | Health check |
| `/chat` | POST | Full chat (messages, system prompt, model) |
| `/simple-chat` | POST | Simple single-message chat |
| `/config` | GET | Current config (no secrets) |
| `/config/switch` | POST | Switch model at runtime |

---

### Gemini Service (`gemini-service/`)

Alternative LLM provider. **Optional — only needed if you want to use Gemini instead of or alongside Claude.**

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3-pro-preview
HOST=127.0.0.1
PORT=25998
```

**How to get a key:** [Google AI Studio](https://aistudio.google.com/) → Get API key

---

### Backend API (`backend/`)

Core game engine. Manages worlds, NPCs, quests, schedules, dialogue, and social systems.

```env
# Token for image generation service (reuses Gemini key format)
GEMINI_API_KEY=your_api_key_here
HOST=127.0.0.1
PORT=26000

# Image Generation (OPTIONAL — provide your own service)
# These URLs must point to an image generation API you control.
# Without these, the system works fine but won't generate NPC avatars or manga pages.
IMAGE_SERVICE_URL=https://your-image-service/api/image/text2image
IMAGE_EDIT_URL=https://your-image-service/api/image/edit

# Aliyun OSS (OPTIONAL — for storing generated images)
ALIYUN_ACCESS_KEY_ID=your_aliyun_access_key_id
ALIYUN_ACCESS_KEY_SECRET=your_aliyun_access_key_secret
OSS_BUCKET_NAME=your_bucket_name
OSS_ENDPOINT=https://oss-cn-shanghai.aliyuncs.com
```

> **Note on Image/Manga generation:** This project's image features (NPC avatars, manga pages) rely on an external image generation API that you must provide yourself. The expected API interface accepts a JSON payload with `prompt`, `aspectRatio`, `imageSize` fields and returns `{"httpCode": 200, "result": {"imageUrl": "..."}}`. If you don't have such a service, simply leave `IMAGE_SERVICE_URL` and `IMAGE_EDIT_URL` empty — the core NPC simulation (world creation, dialogue, quests, social dynamics) works fully without images.

**Key Modules:**

| Module | Description |
|--------|-------------|
| `engines/dialogue_flow_engine.py` | NPC conversation management |
| `engines/director_engine.py` | World event orchestration |
| `engines/quest_engine.py` | Quest generation & progression |
| `engines/social_engine.py` | NPC relationship dynamics |
| `engines/reflection_engine.py` | NPC memory & self-reflection |
| `engines/player_engine.py` | Player interaction handling |
| `services/genesis_service.py` | World creation ("Genesis" flow) |
| `services/manga_service.py` | Manga/comic page generation |
| `services/image_service.py` | Avatar & image generation |
| `services/memory_service.py` | Vector DB (ChromaDB) for NPC memory |

---

### Frontend (`frontend/`)

```bash
cd frontend
npm install
npm run dev      # Dev server at :26001
npm run build    # Production build
```

No additional configuration needed — connects to backend at `http://localhost:26000` via Vite proxy.

---

## Project Structure

```
theNPC/
├── backend/                  # Python FastAPI backend
│   ├── app/
│   │   ├── core/             # Config, clock, LLM client, runtime
│   │   ├── engines/          # Game logic engines (6 engines)
│   │   ├── prompts/          # LLM prompt templates
│   │   ├── routers/          # API route handlers
│   │   ├── schemas/          # Pydantic data models
│   │   └── services/         # Business logic & generators
│   ├── .env.template
│   ├── main.py
│   └── requirements.txt
├── claude-local-service/     # Claude LLM proxy service
├── gemini-service/           # Gemini LLM proxy service
├── frontend/                 # Vue 3 + TypeScript + Tailwind CSS
│   └── src/
│       ├── components/       # 15 Vue components
│       ├── views/            # Genesis, Runtime, Settings
│       ├── stores/           # Pinia state management
│       └── api/              # Backend API client
├── docs/                     # Design docs & specifications
├── start_system.bat          # Windows one-click launcher
└── README.md
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3, TypeScript, Tailwind CSS, Pinia, Vite |
| Backend | Python 3.13, FastAPI, Pydantic |
| LLM | Claude (Anthropic) / Gemini (Google) — **BYO API key** |
| Vector DB | ChromaDB (NPC memory) |
| Storage | Aliyun OSS (optional) |
| Image Gen | External API (optional, BYO service) |

## License

MIT

---

---

# 中文文档

# theNPC - 生成式智能体沙盒

一个 AI 驱动的 NPC（非玩家角色）模拟系统，能够创造鲜活的游戏世界。NPC 拥有自己的日程、人际关系、任务和记忆——全部由大语言模型驱动。

> **重要提示：** 本项目需要你**自行提供 LLM API 密钥**（Claude 或 Gemini）。图片生成和漫画功能需要外部图片服务——这些是可选的，核心系统无需图片服务即可正常运行。详见[配置说明](#2-配置环境变量)。

---

## 系统架构

```
┌──────────────────────────────────────────────────────┐
│                   前端 (Vue 3)                        │
│                http://localhost:26001                 │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│                后端 API (FastAPI)                      │
│                http://localhost:26000                 │
│   引擎: 对话 / 导演 / 任务 / 社交 / 反思 / 玩家       │
└────────┬─────────────────────────────┬───────────────┘
         │                             │
┌────────▼──────────┐     ┌────────────▼───────────────┐
│  Claude 服务       │     │     Gemini 服务             │
│  :25999            │     │     :25998                  │
│  (NPC 智能与对话)  │     │  (备选 LLM 提供商)          │
└───────────────────┘     └────────────────────────────┘
```

| 服务 | 端口 | 功能 |
|------|------|------|
| 前端 | 26001 | Vue 3 + TypeScript 用户界面 |
| 后端 API | 26000 | 核心游戏逻辑、世界管理、任务/NPC 引擎 |
| Claude 服务 | 25999 | LLM 代理——转发请求到 Claude API |
| Gemini 服务 | 25998 | LLM 代理——转发请求到 Gemini API |

## 环境要求

- **Python 3.13+**
- **Node.js 18+** & npm
- **至少一个 LLM 提供商的 API 密钥**（必须自行获取）：
  - [Anthropic Claude](https://console.anthropic.com/) — 或 Azure 托管的 Claude
  - [Google Gemini](https://aistudio.google.com/)（备选）
- *（可选）* 外部图片生成 API，用于 NPC 立绘和漫画页面
- *（可选）* 阿里云 OSS 账号，用于图片存储

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Rainytroy/theNPC.git
cd theNPC
```

### 2. 配置环境变量

每个服务需要独立的 `.env` 文件。**你必须提供自己的 API 密钥。**

```bash
# 后端
cp backend/.env.template backend/.env

# Claude 服务（必需——主要 LLM）
cp claude-local-service/.env.template claude-local-service/.env

# Gemini 服务（可选——备选 LLM）
cp gemini-service/.env.template gemini-service/.env
```

编辑每个 `.env` 文件，填入你的配置值。

### 3. 安装依赖

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
pip install -r requirements.txt

# Claude 服务
cd ../claude-local-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Gemini 服务（可选）
cd ../gemini-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 前端
cd ../frontend
npm install
```

### 4. 启动服务

**Windows 一键启动：**
```bash
start_system.bat
```

**手动启动（任何系统）— 打开 4 个终端：**

```bash
# 终端 1: Claude 服务
cd claude-local-service && python server.py

# 终端 2: Gemini 服务（可选）
cd gemini-service && python server.py

# 终端 3: 后端 API
cd backend && python main.py

# 终端 4: 前端
cd frontend && npm run dev
```

浏览器打开 **http://localhost:26001**

---

## 服务配置详情

### Claude 服务 (`claude-local-service/`)

Claude API 本地代理。**需要自行获取 API 密钥。**

```env
# 方式 A：Anthropic 直连
CLAUDE_API_KEY=你的_claude_api_key
CLAUDE_API_URL=https://api.anthropic.com

# 方式 B：Azure 托管的 Claude
AZURE_CLAUDE_API_KEY=你的_azure_key
AZURE_CLAUDE_API_URL=https://你的资源.services.ai.azure.com/anthropic
AZURE_CLAUDE_MODEL=claude-sonnet-4-5

# 模型选择
CLAUDE_MODEL=claude-sonnet-4-5-20250929

# 服务器
HOST=127.0.0.1
PORT=25999
MAX_TOKENS=4096
TEMPERATURE=0.7
```

**获取密钥：** [Anthropic 控制台](https://console.anthropic.com/) → 创建 API 密钥

---

### Gemini 服务 (`gemini-service/`)

备选 LLM。**可选——仅在需要使用 Gemini 时配置。**

```env
GEMINI_API_KEY=你的_gemini_api_key
GEMINI_MODEL=gemini-3-pro-preview
HOST=127.0.0.1
PORT=25998
```

**获取密钥：** [Google AI Studio](https://aistudio.google.com/) → 获取 API 密钥

---

### 后端 API (`backend/`)

核心游戏引擎。

```env
GEMINI_API_KEY=你的_api_key
HOST=127.0.0.1
PORT=26000

# 图片生成（可选——需自行提供图片生成服务）
# 留空则跳过立绘和漫画功能，核心 NPC 模拟不受影响
IMAGE_SERVICE_URL=https://你的图片服务/api/image/text2image
IMAGE_EDIT_URL=https://你的图片服务/api/image/edit

# 阿里云 OSS（可选——用于存储生成的图片）
ALIYUN_ACCESS_KEY_ID=你的_aliyun_access_key_id
ALIYUN_ACCESS_KEY_SECRET=你的_aliyun_access_key_secret
OSS_BUCKET_NAME=你的_bucket_name
OSS_ENDPOINT=https://oss-cn-shanghai.aliyuncs.com
```

> **关于图片/漫画生成：** 本项目的图片功能（NPC 立绘、漫画页面）依赖外部图片生成 API，需要你自行提供。API 接口需接受包含 `prompt`、`aspectRatio`、`imageSize` 字段的 JSON，返回格式为 `{"httpCode": 200, "result": {"imageUrl": "..."}}`。如果没有此服务，留空 `IMAGE_SERVICE_URL` 和 `IMAGE_EDIT_URL` 即可——核心 NPC 模拟（世界创建、对话、任务、社交）完全不受影响。

**核心模块：**

| 模块 | 功能 |
|------|------|
| `engines/dialogue_flow_engine.py` | NPC 对话管理 |
| `engines/director_engine.py` | 世界事件编排 |
| `engines/quest_engine.py` | 任务生成与推进 |
| `engines/social_engine.py` | NPC 人际关系 |
| `engines/reflection_engine.py` | NPC 记忆与自省 |
| `engines/player_engine.py` | 玩家交互处理 |
| `services/genesis_service.py` | 世界创建（"创世"流程） |
| `services/manga_service.py` | 漫画页面生成 |
| `services/image_service.py` | 立绘与图片生成 |
| `services/memory_service.py` | 向量数据库（ChromaDB）NPC 记忆 |

---

## 项目结构

```
theNPC/
├── backend/                  # Python FastAPI 后端
│   ├── app/
│   │   ├── core/             # 配置、时钟、LLM 客户端、运行时
│   │   ├── engines/          # 游戏逻辑引擎（6 个引擎）
│   │   ├── prompts/          # LLM 提示词模板
│   │   ├── routers/          # API 路由
│   │   ├── schemas/          # Pydantic 数据模型
│   │   └── services/         # 业务逻辑与生成器
│   ├── .env.template
│   ├── main.py
│   └── requirements.txt
├── claude-local-service/     # Claude LLM 代理服务
├── gemini-service/           # Gemini LLM 代理服务
├── frontend/                 # Vue 3 + TypeScript + Tailwind CSS
│   └── src/
│       ├── components/       # 15 个 Vue 组件
│       ├── views/            # 创世、运行时、设置
│       ├── stores/           # Pinia 状态管理
│       └── api/              # 后端 API 客户端
├── docs/                     # 设计文档与规格说明
├── start_system.bat          # Windows 一键启动脚本
└── README.md
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3, TypeScript, Tailwind CSS, Pinia, Vite |
| 后端 | Python 3.13, FastAPI, Pydantic |
| LLM | Claude (Anthropic) / Gemini (Google) — **需自备 API 密钥** |
| 向量数据库 | ChromaDB（NPC 记忆） |
| 存储 | 阿里云 OSS（可选） |
| 图片生成 | 外部 API（可选，需自备服务） |

## 许可证

MIT
