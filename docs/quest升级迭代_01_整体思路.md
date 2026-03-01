# Quest 升级迭代 01：整体思路与架构设计

> **版本**: 1.0
> **状态**: 待审阅
> **目标**: 将任务系统从“线性对话列表”升级为“涌现式游戏化任务网络”

## 1. 核心理念 (Core Philosophy)

### 1.1 现状诊断
当前的 Quest 系统是一个**被动式、线性的对话检查器**。
*   **交互单一**: 仅能通过 `speak` 推进。
*   **结构僵化**: 必须按 `Node 1 -> Node 2` 顺序执行。
*   **缺乏深度**: 无法感知物品、时间、地点或 NPC 状态的变化。

### 1.2 升级愿景
我们将构建一个 **条件驱动 (Condition-Driven)** 的任务网络。
*   **从清单到网络**: 任务推进不再依赖单一的 index，而是依赖“条件满足”。
*   **多维交互**: 引入“物品交互”、“地点探索”、“时间等待”等玩法。
*   **模板化生成**: 采用“人工设计模板 + AI 填充内容”的模式，确保逻辑闭环。

---

## 2. 架构变更 (Architecture Changes)

### 2.1 数据层 (Schema)
*   **QuestNode 扩展**: 不再只是 `description + target`。
    *   新增 `type`: 用于区分对话、收集、探索等。
    *   新增 `conditions`: 一个灵活的条件列表（与/或关系）。
*   **QuestCondition 定义**: 结构化的条件描述对象。
    *   `type`: `affinity` | `item` | `location` | `time` | `state`
    *   `params`: 具体的参数字典 (如 `{item_id: "key_01", count: 1}`)。

### 2.2 逻辑层 (Engine)
*   **从轮询 (Polling) 到 事件驱动 (Event-Driven)**:
    *   **旧逻辑**: 玩家对话 -> 检查当前任务 -> 检查好感度 -> 推进。
    *   **新逻辑**: 
        *   PlayerEngine 产生事件 (如 `ItemAcquired`, `LocationChanged`)。
        *   QuestEngine 监听事件总线。
        *   当事件触发时，只检查相关的任务节点条件。
        *   条件满足 -> 自动推进任务状态。

### 2.3 交互层 (Interaction)
*   **解析增强**: PlayerEngine 需要识别非对话指令。
    *   `*给予 [物品]*`
    *   `*调查 [对象]*`
*   **前端配合**: 初期通过文本指令模拟，后期增加 UI 按钮辅助。

---

## 3. 任务类型体系 (Quest Types)

我们定义 5 种核心任务原型：

1.  **对话 (Dialogue)**: 传统的“谈话即完成”，可附加“关键词”条件。
2.  **收集 (Collection)**: 获取特定物品 (Item System 依赖)。
3.  **调查 (Investigation)**: 到达特定地点或检查特定物体。
4.  **等待 (Wait)**: 在特定时间窗口内，或等待 NPC 进入特定状态。
5.  **抉择 (Choice)**: 产生分支，玩家的选择将改变任务走向 (Phase 3 实现)。

---

## 4. 实施路线图 (Roadmap)

*   **Phase 1: 数据基石 (Data Foundation)**
    *   扩展 Schema (QuestNode, QuestCondition)。
    *   实现基础物品系统 (Items)。
    *   改造 PlayerEngine 识别动作指令。

*   **Phase 2: 逻辑引擎 (Logic Engine)**
    *   实现 QuestCondition 校验逻辑。
    *   引入模板库 (QuestTemplates)。
    *   实现简单的事件监听。

*   **Phase 3: 复杂性与工具 (Complexity & Tools)**
    *   分支任务与多结局。
    *   前端任务调试面板/编辑器。
