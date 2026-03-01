# theNPC 开发进度清单

> **状态标记说明**:
> - [ ] 未开始
> - [x] 已完成
> - [-] 已废弃/挂起

---

## Phase 0: 基础设施搭建 (Infrastructure)

### 0.1 后端环境 (Python FastAPI)
- [x] 创建后端项目目录 `backend/`
- [x] 配置 `requirements.txt` (FastAPI, Uvicorn, Pydantic, httpx)
- [x] 搭建 FastAPI 基础骨架 (Main entry, Router structure)
- [x] 实现 `LLMClient` 类，连接本地 Claude/Gemini 服务
- [x] 验证 LLM 连接 (Ping test)

### 0.2 前端环境 (Vue 3)
- [x] 创建前端项目目录 `frontend/` (Vite + Vue 3 + TypeScript)
- [x] 安装 TailwindCSS
- [x] 配置 Axios 和 WebSocket Client
- [x] 实现基础布局 (Layout: 左侧信息栏, 右侧对话框)

### 0.3 数据层
- [x] 设计 JSON 文件存储结构
- [x] 实现 `WorldManager` (创世与存档管理)
- [x] 实现 `MemoryService` (向量数据库集成 ChromaDB)

---

## Phase 1: 创世引擎 (The Genesis Engine)

### 1.1 播种者 (The Sower) - 后端
- [x] 定义 `WorldConfig` Pydantic 模型
- [x] 编写 Sower 的 System Prompt (引导用户、补全设定)
- [x] 实现 `/api/genesis/chat` 接口 (流式对话)
- [x] 实现 `/api/genesis/confirm_world` 接口 (生成 JSON)

### 1.2 塑造者 (The Shaper) - 后端
- [x] 定义 `NPCProfile` Pydantic 模型
- [x] 编写 Shaper 的 System Prompt (基于 World Bible 生成 NPC)
- [x] 实现 `/api/genesis/generate_npcs` 接口 (批量生成)
- [x] 实现自洽性校验逻辑

### 1.3 创世 UI - 前端
- [x] 实现创世引导对话界面 (Chat UI)
- [x] 实现世界设定展示卡片 (World Bible View)
- [x] 实现 NPC 列表确认界面 (NPC Roster View)

---

## Phase 2: 运行时内核 (Runtime Core)

### 2.1 时间与调度
- [x] 实现 `RuntimeEngine` (游戏时间维护 1:60)
- [x] 实现 Ticker (心跳机制)
- [x] 实现 NPC 日程生成器 (Scheduler Agent)
- [x] WebSocket 推送 `world_tick` 事件

### 2.2 事件总线 (Event Bus)
- [x] 实现 WebSocket 广播机制
- [x] 定义事件类型 (`event`, `npc_update`, `time_update`)

### 2.3 运行时 UI
- [x] 实现世界状态面板 (显示时间)
- [x] 实现实时日志流 (Log View)
- [x] 实现 NPC 状态列表 (Location, Action)

---

## Phase 3: NPC 智能模型 (Interaction & Emergence)

### 3.1 基础行为
- [x] 实现 NPC 基础响应 (`_npc_react`)
- [x] 实现状态机 (`is_busy`, `busy_until`)
- [x] 实现动态行为队列 (`dynamic_queue`)

### 3.2 社交系统
- [x] 实现社交检测 (同一地点 NPC 聚合)
- [x] 实现多轮对话生成 (`SOCIAL_SYSTEM_PROMPT`)
- [x] 实现社交冷却机制

### 3.3 记忆与反思
- [x] 集成 ChromaDB 存储长期记忆
- [x] 实现记忆检索 (基于上下文检索相关记忆)
- [x] 实现每日反思 (`REFLECTION_SYSTEM_PROMPT`)

---

## Phase 4: 交互与完善 (Interaction & Polish)

### 4.1 玩家交互
- [x] 实现 @ 机制 (指定 NPC 私聊)
- [x] 前端实现 NPC 选择交互
- [x] 实现上下文感知 (`Context Buffer`)

### 4.2 上帝导演 (The Director)
- [x] 编写 Director System Prompt
- [x] 实现随机事件生成与广播
- [x] 实现 NPC 对系统事件的群体反应

---

## Phase 5: 智能代理深化 (Deep Agentic Behavior)

### 5.1 动态规划
- [x] 实现日程中断机制 (Schedule Interruption)
- [x] 实现即时任务插入 (Dynamic Planning)
- [x] 实现自主目标生成 (Goal Emergence)

---

## Phase 6: 优化与扩展 (Optimization & Extension)

### 6.1 长期记忆增强
- [ ] 实现基于语义的更精准记忆检索
- [ ] 引入记忆遗忘机制 (Memory Decay)

### 6.2 UI/UX 改进
- [ ] 增加“观察者模式”地图视图
- [ ] 优化移动端适配
- [ ] 美化聊天气泡与事件展示

### 6.3 性能与并发
- [ ] 优化多世界并发运行性能
- [ ] 探索小模型 (SLM) 微调以降低成本
