# theNPC - Generative Agent Sandbox

An AI-driven NPC (Non-Player Character) simulation system that creates living, breathing game worlds with autonomous characters. NPCs have their own schedules, relationships, quests, and memories — all powered by large language models.

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

**Services Overview:**

| Service | Port | Role |
|---------|------|------|
| Frontend | 26001 | Vue 3 + TypeScript UI |
| Backend API | 26000 | Core game logic, world management, quest/NPC engines |
| Claude Service | 25999 | LLM proxy — forwards requests to Claude API |
| Gemini Service | 25998 | LLM proxy — forwards requests to Gemini API |

## Prerequisites

- **Python 3.13+**
- **Node.js 18+** & npm
- API keys for at least one LLM provider (Claude or Gemini)
- *(Optional)* Aliyun OSS account for NPC avatar storage
- *(Optional)* Image generation service URL for avatar/manga generation

## Quick Start

### 1. Clone & Enter Project

```bash
git clone <repo-url>
cd theNPC
```

### 2. Configure Environment Variables

Each service requires its own `.env` file. Copy the templates and fill in your values:

```bash
# Backend
cp backend/.env.template backend/.env

# Claude Service
cp claude-local-service/.env.template claude-local-service/.env

# Gemini Service (optional)
cp gemini-service/.env.template gemini-service/.env
```

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

**Manual (any OS):**

Open 4 terminal windows and run each:

```bash
# Terminal 1: Claude Service
cd claude-local-service
python server.py

# Terminal 2: Gemini Service (optional)
cd gemini-service
python server.py

# Terminal 3: Backend API
cd backend
python main.py

# Terminal 4: Frontend
cd frontend
npm run dev
```

Then open **http://localhost:26001** in your browser.

---

## Service Configuration Details

### Claude Service (`claude-local-service/`)

This service acts as a local proxy for the Claude API. The backend communicates with this service instead of calling Claude directly.

**`claude-local-service/.env`:**
```env
# Claude API Key and Endpoint
CLAUDE_API_KEY=your_claude_api_key_here
CLAUDE_API_URL=https://api.anthropic.com

# You can also use Azure-hosted Claude:
# AZURE_CLAUDE_API_KEY=your_azure_key
# AZURE_CLAUDE_API_URL=https://your-resource.services.ai.azure.com/anthropic

# Model Selection
CLAUDE_MODEL=claude-sonnet-4-5-20250929

# Server
HOST=127.0.0.1
PORT=25999

# Generation Settings
MAX_TOKENS=4096
TEMPERATURE=0.7
```

**How to get a Claude API key:**
1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an API key
3. Paste it as `CLAUDE_API_KEY`

**Azure-hosted Claude:**
If using Azure, set `AZURE_CLAUDE_API_KEY` and `AZURE_CLAUDE_API_URL` in your `.env`. The service will use Azure configuration by default.

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service status |
| `/health` | GET | Health check |
| `/chat` | POST | Full chat (messages array, system prompt, model selection) |
| `/simple-chat` | POST | Simple chat (single message string) |
| `/config` | GET | Current config (no secrets exposed) |
| `/config/switch` | POST | Switch model at runtime |

---

### Gemini Service (`gemini-service/`)

Alternative LLM provider using Google's Gemini API. This service can be used alongside or instead of Claude.

**`gemini-service/.env`:**
```env
# Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Model
GEMINI_MODEL=gemini-3-pro-preview

# Server
HOST=127.0.0.1
PORT=25998
```

**How to get a Gemini API key:**
1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Click "Get API key"
3. Paste it as `GEMINI_API_KEY`

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/chat` | POST | Chat with messages array, system prompt, temperature |

---

### Backend API (`backend/`)

The core game engine. Manages worlds, NPCs, quests, schedules, dialogue, and social systems.

**`backend/.env`:**
```env
# LLM - uses the API key as image service token
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-pro
HOST=127.0.0.1
PORT=26000

# Image Generation Service (for NPC avatars & manga)
IMAGE_SERVICE_URL=https://your-image-service-url/api/image/text2image
IMAGE_EDIT_URL=https://your-image-service-url/api/image/edit

# Aliyun OSS (for storing generated images)
ALIYUN_ACCESS_KEY_ID=your_aliyun_access_key_id
ALIYUN_ACCESS_KEY_SECRET=your_aliyun_access_key_secret
OSS_BUCKET_NAME=your_bucket_name
OSS_ENDPOINT=https://oss-cn-shanghai.aliyuncs.com
```

> **Note:** Image generation and OSS are optional features. The core NPC simulation works without them — you just won't get generated avatars or manga pages.

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
| `services/oss_service.py` | Aliyun OSS file storage |
| `services/memory_service.py` | Vector DB (ChromaDB) for NPC memory |

---

### Frontend (`frontend/`)

Vue 3 + TypeScript + Tailwind CSS application.

```bash
cd frontend
npm install
npm run dev      # Development server at :26001
npm run build    # Production build
```

No additional configuration needed — the frontend connects to the backend at `http://localhost:26000` by default.

---

## Project Structure

```
theNPC/
├── backend/                  # Python FastAPI backend
│   ├── app/
│   │   ├── core/             # Config, clock, LLM client, runtime
│   │   ├── engines/          # Game logic engines
│   │   ├── prompts/          # LLM prompt templates
│   │   ├── routers/          # API route handlers
│   │   ├── schemas/          # Pydantic data models
│   │   └── services/         # Business logic services
│   ├── .env.template
│   ├── main.py
│   └── requirements.txt
├── claude-local-service/     # Claude LLM proxy service
├── gemini-service/           # Gemini LLM proxy service
├── frontend/                 # Vue 3 frontend
│   └── src/
│       ├── components/       # UI components
│       ├── views/            # Page views
│       ├── stores/           # Pinia state management
│       └── api/              # API client layer
├── docs/                     # Design documents & specs
├── start_system.bat          # Windows one-click launcher
└── README.md
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3, TypeScript, Tailwind CSS, Pinia, Vite |
| Backend | Python 3.13, FastAPI, Pydantic |
| LLM | Claude (Anthropic) / Gemini (Google) |
| Vector DB | ChromaDB (NPC memory) |
| Storage | Aliyun OSS (optional, for images) |
| Image Gen | External API service (optional) |

## License

MIT
