# theNPC - 技术架构设计文档

> **版本**: 1.0  
> **架构名称**: The Theatre Architecture (剧场架构)  
> **核心理念**: 平衡“Agent自主性”与“系统可控性”，将世界视为一个精密运转的即兴舞台。

## 1. 核心架构模式 (The Theatre Model)

我们将系统划分为两个主要部分，模拟剧场的运作：
*   **后台 (Backstage / Server)**: 处理所有的逻辑、推理、状态变更、记忆检索。这是AI大脑所在的地方。
*   **前台 (Stage / Client)**: 仅作为即时渲染层，负责展示对话、动作、状态变化日志。它是无状态的观察窗口。

---

## 2. 系统模块设计

### 2.1 创世引擎 (The Genesis Engine)
*对应 PRD “创世阶段”*

此模块是一组协同工作的Agent，负责生成世界的静态数据。

*   **播种者 (The Sower)**
    *   **职责**: 交互式Prompt工程。
    *   **功能**: 与用户多轮对话 -> 填充 `World_Config_Schema` -> 生成《世界设定书》(World Bible)。
    *   **机制**: 内置检查表 (Checklist)，自动检测设定完备性，必要时调用Creative Base补充细节。

*   **塑造者 (The Shaper)**
    *   **职责**: 批量角色生成。
    *   **功能**: 读取 World Bible -> 批量生成 `NPC_Profile_Schema` -> 一致性校验 (Self-Consistency Check)。
    *   **输出**: 3-5个NPC的完整JSON档案。

### 2.2 运行时内核 (Runtime Core)
*对应 PRD “运行阶段”*

基于 **事件驱动架构 (Event-Driven Architecture)** 构建的服务端核心。

*   **时间调度器 (Chronos Scheduler)**
    *   **Tick机制**: 系统心跳。
    *   **映射**: 物理时间 1 小时 -> 游戏时间 1 天。
    *   **CronJob**: 管理NPC的定时日程 (Schedule)。

*   **事件总线 (The Stage Bus)**
    *   所有交互被抽象为消息 (Message)：`Player_Speak`, `NPC_Action`, `Time_Pass`, `System_Event`。
    *   **Pub/Sub模式**: NPC订阅总线，通过过滤器 (Filter) 决定是否处理某条消息（基于@机制、位置、公共/私有属性）。

*   **上帝Agent (The Director)**
    *   **环境叙事**: 每日播报（天气、节日）。
    *   **熵减与熵增**:
        *   当剧情停滞时，抛入随机事件（熵增）。
        *   当NPC行为逻辑崩坏时，进行修正或阻止（熵减）。

---

## 3. NPC Agent 设计：OODA 循环

每个NPC都是一个独立的Agent，遵循 **Observe-Orient-Decide-Act** 循环。

### 3.1 数据结构 (JSON Profile)
我们采用纯JSON文件存储，动态加载到内存。

```json
{
  "id": "npc_001",
  "static_profile": { "name": "...", "role": "..." }, 
  "dynamic_state": { 
    "mood": "happy", 
    "location": "coffee_shop", 
    "skills": ["latte_art", "listening"] 
  },
  "goals": [ 
    { "id": "g1", "type": "main", "desc": "...", "status": "active" },
    { "id": "g2", "type": "sub", "desc": "...", "status": "pending", "trigger_time": "10:00" }
  ],
  "relationships": { 
    "npc_002": { "know_name": true, "affinity": 50, "memory_summary": "..." } 
  },
  "memory_archive": ["day1_summary", "day2_summary"]
}
```

### 3.2 运行流程
1.  **感知 (Observe)**: 监听事件总线，捕获相关信息。
2.  **定位与检索 (Orient)**: 
    *   检索短期记忆 (Context Window)。
    *   检索长期记忆 (JSON Archive)。
    *   检查当前目标状态。
3.  **决策 (Decide)**: 
    *   调用 LLM (Claude 4.5 Sonnet)。
    *   System Prompt + Current State + Event -> **Tool Calls**。
4.  **行动 (Act)**: 执行工具调用，广播结果。

### 3.3 关键工具箱 (Toolbox)
NPC通过调用以下工具与世界交互：
*   `speak(content, emotion)`: 说话。
*   `action(description)`: 执行动作。
*   `update_goal(goal_id, status)`: 修改任务清单。
*   `update_self(attribute, value)`: 修改自身属性（性格、能力）。
*   `update_relationship(target_npc, affinity_change)`: 更新社交关系。

### 3.4 记忆与反思 (Memory & Reflection)
*   **短期记忆**: 维护最近 N 轮对话在 Context 中。
*   **每日反思**: 游戏日结束时，触发 Reflection 任务，将当日经历压缩为摘要，写入 `memory_archive`，清空短期 Context。

---

## 4. 技术栈与部署架构

### 4.1 技术选型
*   **前端 (Frontend)**: 
    *   **Vue 3** (Composition API)
    *   **Vite** (构建工具)
    *   **WebSocket** (原生或 Socket.io-client) 用于实时通信
*   **后端 (Backend)**: 
    *   **Python FastAPI** (异步高性能 Web 框架)
    *   **Uvicorn** (ASGI 服务器)
*   **LLM 服务**: 
    *   独立运行的 `claude-local-service` (Claude 4.5 Sonnet)
*   **数据存储**: 
    *   本地 JSON 文件系统 (无需传统数据库)

### 4.2 网络端口规划 (固定)
为了避免端口冲突，所有服务端口固定在 26000 段：
*   **后端 API 服务**: `http://localhost:26000`
*   **前端 Web 服务**: `http://localhost:26001`
*   **LLM 服务**: `http://localhost:25999` (保持原服务默认配置，后端通过配置连接)

### 4.3 前后端交互模型
*   **初始化/控制流 (REST API)**:
    *   Vue -> FastAPI: 提交创世设定、暂停/恢复游戏、手动触发事件。
*   **实时数据流 (WebSocket)**:
    *   FastAPI -> Vue: 推送时间流逝 (Tick)、NPC 移动、对话气泡、系统日志。
    *   连接地址: `ws://localhost:26000/ws`

---

## 5. 接口设计原则
*   所有的 Agent 思考过程对用户（开发者）透明，在 Log 中可见。
*   所有的 State Change 必须通过 Tool Call 显式发生。
