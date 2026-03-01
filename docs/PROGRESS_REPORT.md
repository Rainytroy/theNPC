# 📊 开发进度报告 (Development Progress Report)

**日期**: 2025-12-03
**状态**: Phase 5 (智能代理深化) 完成，进入 Phase 6 (长期运行测试与优化)。

---

## ✅ 已完成功能 (Completed)

### Phase 1: 创世引擎 (The Genesis Engine)
1.  **播种者 (The Sower)**:
    *   对话式引导，根据用户输入生成结构化的《世界设定书》(World Bible)。
    *   支持自动补全和设定确认。
2.  **塑造者 (The Shaper)**:
    *   基于世界设定，批量生成 3-5 个自洽的 NPC。
    *   生成内容包括：性格、职业、技能、主线目标、次要目标。
3.  **存档系统 (The Archivist)**:
    *   **持久化**: 所有数据保存于 `data/worlds/{world_id}/`。
    *   **管理**: 支持查看历史存档、加载、删除、新建世界。
4.  **多模型支持 (Multi-Model)**:
    *   **架构**: 独立的 `claude-local-service` 和 `gemini-service` 微服务。
    *   **切换**: 前端导航栏实时切换模型 (Claude 4.5 Sonnet / Gemini 3 Pro)。
    *   **路由**: 后端 `LLMClient` 根据请求头动态路由。

### Phase 2: 运行阶段 (The Runtime)
1.  **核心循环 (Core Loop)**:
    *   `RuntimeEngine` 维护游戏内时间 (1秒现实=60秒游戏，即 1分钟现实=1小时游戏)。
    *   支持 WebSocket 连接，实时广播时间更新。
2.  **NPC 调度器 (Scheduler)**:
    *   系统启动时，调用 LLM 为每个 NPC 生成当天的 24 小时日程表。
    *   每分钟 (Tick) 检查日程，触发对应行动。
3.  **事件系统 (Event Bus)**:
    *   NPC 的行动会作为事件 (`type: event`) 广播给前端。
    *   前端 `RuntimeView` 实时显示滚动日志。
4.  **交互界面 (Runtime View)**:
    *   显示当前世界时间。
    *   显示 NPC 列表及状态。
    *   提供 暂停/继续 控制。
    *   **玩家干预**: 提供聊天输入框，允许玩家直接发送消息给 NPC。
5.  **玩家互动 (Player Intervention)**:
    *   后端监听 `player_action` 消息。
    *   调用 `Reaction Agent` 决定 NPC 如何回应玩家的话。

### Phase 3: 互动与涌现 (Interaction & Emergence)
1.  **NPC 社交 (Socializing)**:
    *   **社交检测**: 运行时自动检测同一地点的 NPC 群组。
    *   **对话生成**: 调用 LLM (基于 `SOCIAL_SYSTEM_PROMPT`) 生成自然对话。
    *   **冷却机制**: 同一地点的社交事件有 60 分钟(游戏时间)冷却。
    *   **广播与展示**: 前端实时显示 NPC 位置变化和对话内容。
2.  **记忆系统 (Memory)**:
    *   **向量存储**: 引入 ChromaDB 作为长期记忆存储 (`data/worlds/{world_id}/memory_db`)。
    *   **记忆写入**: 社交互动的 Outcome 会自动存入向量库，包含时间戳和重要性。
    *   **记忆检索**: 在生成社交对话前，系统会根据上下文 (地点、参与者) 检索相关记忆，增强对话连贯性。
3.  **反思机制 (Reflection)**:
    *   **每日触发**: 每天 22:00，系统会自动触发每个 NPC 的反思进程。
    *   **记忆整合**: 检索当天的所有记忆片段，调用 LLM (基于 `REFLECTION_SYSTEM_PROMPT`) 生成每日摘要 (Daily Summary)。
    *   **自我演化**: 反思过程会产出 NPC 的情绪变化 (Mood Shift) 和新的次要目标 (New Goals)，并实时更新到 NPC 状态中。
    *   **长期记忆**: 每日摘要会被存入 ChromaDB，作为高权重的长期记忆。

### Phase 4: 交互与完善 (Interaction & Polish)
1.  **上帝导演 (The Director)**:
    *   **宏观调控**: Director Agent 每隔 4 个游戏小时审视一次世界。
    *   **随机事件**: 基于 `DIRECTOR_SYSTEM_PROMPT`，决定是否触发天气变化、突发新闻等事件 (熵增)。
    *   **全员反应**: 系统事件会广播给所有 NPC，触发他们的即时反应 (`reaction` 机制)，打破既定日程。
2.  **玩家交互深度化 (Player Interaction)**:
    *   **定向沟通**: 前端新增了 NPC 选择功能，玩家现在可以点击 NPC 卡片，指定对象进行私聊 (`target_npc_id`)。
    *   **动态行为**: NPC 的 `_npc_react` 机制升级，现在不仅能说话，还能根据玩家输入或环境事件改变当前行动 (`current_action`)。
    *   **上下文感知**: 引入了 `Context Buffer`，NPC 现在能"记住"当前场景内最近的 10 条对话，从而进行连贯的插话或回应。
    *   **区域广播**: 消息广播机制升级，确保只有与目标 NPC 处于同一场景的其他 NPC 才会感知到玩家的发言（作为旁观者），从而决定是否插嘴。
3.  **目标系统深化 (Goal Enhancement)**:
    *   **即时目标**: 在 `REACTION_SYSTEM_PROMPT` 中增加了 `new_goal` 输出。NPC 在应对突发状况（如玩家指令、导演事件）时，可以实时生成新的短期目标。
    *   **地点标准化**: 调度器现在强制使用 World Bible 中定义的 `locations` 列表中选择地点，确保 NPC 能够物理上相遇。同时做了向后兼容，旧存档自动适配默认地点。
4.  **调试工具优化**:
    *   **时间控制**: 前端增加了丰富的时间控制选项 (24h, 4h, 2h, 1h, 24m, 48s / Day)。支持慢放以便观察微观互动，也支持快进以测试宏观演化。
5.  **系统稳定性增强**:
    *   **Schema 修复**: 修正了 NPC 动态属性缺失导致的崩溃问题。
    *   **JSON 鲁棒性**: 增强了后端对 LLM 输出 JSON 的解析能力，能自动处理格式微瑕疵。
    *   **UI 体验**: 优化了聊天窗口的自动滚动逻辑。

### Phase 5: 智能代理深化 (Deep Agentic Behavior)
1.  **日程中断 (Schedule Interruption)**:
    *   **状态追踪**: 在 `RuntimeEngine` 中引入了 `npc_states` 来追踪每个 NPC 的 `is_busy` 状态和 `busy_until` 时间。
    *   **动态优先**: 当 NPC 处于对话或执行突发任务时，系统会自动暂停其静态日程表的执行，防止"聊着天突然跑路"的违和感。
    *   **自动恢复**: 忙碌状态结束后（如对话结束 15 分钟后），NPC 会自动回归原定日程。
2.  **动态规划 (Dynamic Planning)**:
    *   **任务队列**: 实现了 `dynamic_queue` 机制，允许插入临时的高优先级任务。
    *   **即时反应**: NPC 的 `_npc_react` 现在会直接修改当前行动并设定忙碌时间，实现了对突发事件的即时响应。
    *   **目标衍生**: NPC 在对话中可以自主生成新的 `NPCGoal`，并将其加入目标列表。

---

## 🏗️ 进行中 / 计划 (Work in Progress / Planned)

### Phase 6: 优化与扩展 (Optimization & Extension)
1.  **任务融合系统 (Quest Integration System) [已实现]**:
    *   **创世**: 在 Sower 阶段询问用户的“玩家目标”(Player Objective)。
    *   **塑造**: Shaper 会为每个 NPC 分配暗线角色 (Guide/Blocker/Neutral) 和线索 (Clue)。
    *   **响应**: 运行时引入任务上下文，NPC 会根据玩家是否触及目标关键词来决定是提供线索还是进行阻碍。
2.  **长期记忆增强**:
    *   实现基于语义的更精准记忆检索。
    *   引入记忆遗忘机制，防止向量库无限膨胀。
2.  **UI/UX 改进**:
    *   增加“观察者模式”，允许点击地图上的地点查看该地点的所有活动。
    *   优化移动端适配。
3.  **多世界并发**:
    *   测试并优化同时运行多个世界实例的性能。
4.  **模型微调 (Optional)**:
    *   探索使用收集到的交互数据微调小模型 (如 Llama 3) 以降低运行成本。

---

## 🛠️ 技术架构 (Architecture)

*   **Backend**: FastAPI (Port 26000)
    *   `app.core.runtime`: 单例 RuntimeEngine，处理时间与事件。
    *   `app.services.genesis`: 处理 LLM 交互与数据生成。
*   **Frontend**: Vue 3 + Vite + TailwindCSS (Port 26001)
    *   `GenesisView`: 创世与存档管理。
    *   `RuntimeView`: 游戏运行主界面。
*   **LLM Services**:
    *   Claude Service (Port 25999)
    *   Gemini Service (Port 25998)

## 🚀 启动方式
运行根目录下的 `theNPC\start_system.bat` 即可一键启动所有服务。

## 📝 备注
*   关键 Bug 修复记录请参考 `docs/BEST_PRACTICES.md`。
*   数据存储路径已修正为 `d:/VibeCoding/theNPC/data`。
