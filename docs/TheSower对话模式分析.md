# The Sower (播种者) 对话模式分析报告

## 📋 概述

**The Sower** 是 theNPC 项目中的核心 AI Agent，负责引导用户通过对话式交互创建游戏世界。本文档详细分析其对话模式、架构设计和数据流转机制。

---

## 🎯 核心定位

The Sower 扮演**世界创造引导者**的角色，通过多轮对话：
1. **收集信息**：理解用户意图，提取关键设定
2. **提供建议**：基于上下文给出创意提案
3. **确认决策**：让用户明确确认后才执行生成操作
4. **协调 Agent**：调度后端的 Shaper、Asset Enricher、Quest Writer 等专业 Agent

---

## 🔄 三阶段对话流程

### **Phase 1: World Bible (世界圣经)**
**目标**：确定世界背景、场景、时间规则

**对话策略**：
- 开放式提问，鼓励用户描述梦想中的世界
- 识别关键词（时代、风格、氛围）
- 当信息足够时，输出 `suggested_world_setting`（草稿）
- 用户确认后，标记 `is_ready_to_generate=true`

**Prompt 关键点**（来自 `sower.py`）：
```python
PHASE_1_CONTEXT = """
你的目标是通过对话帮助用户构建完整的世界设定...
当你认为信息充足时，将 is_ready_to_generate 设置为 true
```

---

### **Phase 2: NPC Roster (角色名册)**
**目标**：生成核心 NPC 并完善角色关系

**对话策略**：
- 询问用户对 NPC 的需求（数量、类型、特殊要求）
- 收集到足够信息后，输出 `is_ready_for_npc=true`
- 可选：用户通过 `pending_actions` 确认生成操作

**两阶段生成机制**：
1. **Roster 生成**（`generate_roster`）：快速创建骨架（Skeleton）
   - 包含基本信息：name, gender, age, occupation
   - 前端立即显示，提升响应速度
   
2. **Details 生成**（`generate_npc_details`）：并行填充详细信息
   - Profile (外貌、背景故事)
   - Personality (性格特质)
   - Goals & Secrets (目标、秘密)

**Prompt 关键点**：
```python
PHASE_2_CONTEXT = """
分析用户对 NPC 的需求...
记录 npc_requirements 字段（这是关键！）
当准备好时设置 is_ready_for_npc=true
```

---

### **Phase 3: Quest Blueprint (任务蓝图）**
**目标**：生成主线任务 + 支线任务

**对话策略**：
- 询问用户对任务的期望（剧情走向、难度、主题）
- **关键**：收集 `quest_requirements`（任务需求）
- 确认后输出 `is_ready_for_quest=true`

**三步走生成流程**：
1. **Reset & Enrich Assets**：
   - 从 World Bible 提取关键物品/地点
   - 通过 Asset Enricher 优化描述和属性

2. **Generate Main Quest**：
   - 基于 `quest_requirements` 生成主线任务
   - 使用 Quest Writer Agent（参考 `quest_writer.py`）

3. **Generate Side Quests**：
   - 为每个 NPC 生成专属支线任务
   - 并行执行，增量更新

**Prompt 关键点**：
```python
PHASE_3_CONTEXT = """
引导用户描述任务期望...
🚨 关键字段：quest_requirements（用户的任务需求描述）
```

---

## 🧩 数据流转架构

```
用户输入
   ↓
[前端] GenesisChat.vue
   ↓ (POST /api/genesis/chat)
[路由] genesis.py::chat_genesis()
   ↓
[Service] genesis_service.chat()
   ↓
[Sower] prompts/sower.py (构造 Prompt)
   ↓
[LLM] llm_client.chat_completion()
   ↓
[返回] GenesisChatResponse {
   response: "播种者回复",
   is_ready_for_quest: true,
   quest_requirements: "用户的任务需求"  ← 关键！
}
   ↓
[前端] 显示确认按钮
   ↓ (用户点击确认)
[前端] 调用 /api/genesis/generate_main_quest
   ↓
[路由] genesis.py::generate_main_quest()
   ↓ ❌ 问题在这里！
[Service] genesis_service.generate_main_quest(
   world_bible,
   npcs,
   provider
   ❌ 缺少 requirements=request.requirements
)
   ↓
[Generator] quest_generator.py::generate_main_quest()
   ↓
6. **User Requirements (CRITICAL)**:
{requirements if requirements else "Please design a compelling..."}
   ↑ 
   如果 requirements 是 None，就会使用英文默认值！
```

---

## 🐛 当前 BUG 分析

### **问题现象**
用户在 Phase 3 对话中明确表达任务需求（例如：希望主线任务围绕"拯救被囚禁的公主"），但生成的任务却是通用的默认任务。

### **根本原因**
在 **路由层** (`genesis.py::generate_main_quest`) 调用服务时，**没有传递 `requirements` 参数**：

```python
# ❌ 当前代码（错误）
quests = await genesis_service.generate_main_quest(
    request.world_bible, 
    request.npcs, 
    provider=x_model_provider
    # 缺少 requirements=request.requirements
)
```

**修复方案**：
```python
# ✅ 修复后代码
quests = await genesis_service.generate_main_quest(
    request.world_bible, 
    request.npcs, 
    provider=x_model_provider,
    requirements=request.requirements  # 添加这一行
)
```

### **影响链路**
1. **Schema 层**：`GenerateMainQuestRequest` 已包含 `requirements` 字段 ✅
2. **路由层**：**未传递参数** ❌
3. **Service 层**：`genesis_service.generate_main_quest()` 接收参数 ✅
4. **Generator 层**：`quest_generator.py` 正确注入到 Prompt ✅

**结论**：只需在路由层添加一行代码即可修复。

---

## 💡 设计亮点

### 1. **渐进式信息收集**
The Sower 不会一次性要求用户提供所有信息，而是通过多轮对话逐步深入，降低用户认知负担。

### 2. **Context-Aware Prompting**
每个阶段的 System Prompt 都基于当前 World Bible 和 NPC Roster 动态构造，确保 AI 回复与项目上下文高度相关。

### 3. **Pending Actions 机制**
通过返回 `pending_actions` 数组，前端可渲染确认按钮，让用户对 AI 提案有明确的控制权：
```typescript
{
  type: "add_npc",
  label: "生成 3 个 NPC",
  style: "primary",
  data: { count: 3, requirements: "..." }
}
```

### 4. **增量生成 + 实时反馈**
- NPC 分阶段生成（Skeleton → Details）
- Quest 分离生成（Main Quest → Side Quests）
- 前端通过 SSE/Polling 实时显示进度

---

## 📊 关键数据结构

### **GenesisChatResponse**
```typescript
{
  response: string,                    // 播种者回复
  is_ready_to_generate: boolean,       // Phase 1: World Bible 是否就绪
  suggested_world_setting?: Object,    // Phase 1: 世界设定草稿
  is_ready_for_npc: boolean,           // Phase 2: NPC 是否就绪
  npc_requirements?: string,           // Phase 2: NPC 需求描述
  npc_count?: number,                  // Phase 2: NPC 数量
  is_ready_for_quest: boolean,         // Phase 3: Quest 是否就绪
  quest_requirements?: string,         // Phase 3: 任务需求描述 ← 核心
  pending_actions?: PendingAction[]    // 待确认操作
}
```

### **PendingAction**
```typescript
{
  type: "add_npc" | "regenerate_npc" | "confirm_roster",
  label: string,     // 按钮文本
  style: "primary" | "secondary" | "danger",
  data: Object       // 操作参数
}
```

---

## 🔧 优化建议

### 1. **中文 Fallback**
当 `requirements` 为空时，默认提示应改为中文：
```python
{requirements if requirements else "请设计一个符合世界设定的精彩主线任务。"}
```

### 2. **需求摘要持久化**
将用户需求保存到 `status.json` 的 `phase_summaries` 中：
```json
{
  "phase_summaries": {
    "quest_summary": "用户希望主线任务围绕拯救公主展开，难度适中..."
  }
}
```

### 3. **需求校验**
在生成任务前，验证 `requirements` 是否有效：
```python
if not requirements or len(requirements.strip()) < 10:
    raise ValueError("Quest requirements too short or missing")
```

### 4. **多轮迭代支持**
允许用户在看到任务草稿后，继续与 Sower 对话进行调整：
```
用户："主线任务太简单了，能加一个背叛者支线吗？"
Sower："好的，我会在现有任务基础上添加一个背叛者角色..."
```

---

## 📖 代码文件索引

| 文件路径 | 功能说明 |
|---------|---------|
| `backend/app/prompts/sower.py` | Sower 的 System Prompt 定义（三阶段） |
| `backend/app/services/genesis_service.py` | Genesis 服务协调层，调度各 Agent |
| `backend/app/routers/genesis.py` | API 路由定义 |
| `backend/app/schemas/genesis.py` | 数据模型（Request/Response） |
| `backend/app/prompts/quest_writer.py` | Quest Writer Agent Prompt |
| `backend/app/services/components/quest_generator.py` | Quest 生成逻辑 |
| `frontend/src/components/GenesisChat.vue` | 前端对话界面 |
| `frontend/src/stores/genesis/quest.ts` | Quest Store（状态管理） |

---

## ✅ 总结

**The Sower 的对话模式核心特点**：
1. **分阶段引导**：World → NPC → Quest
2. **上下文感知**：基于当前项目状态动态构造 Prompt
3. **用户确认机制**：通过 `pending_actions` 让用户控制生成流程
4. **需求传递**：通过 `*_requirements` 字段将用户意图传递给专业 Agent

**当前 Bug**：
- **根因**：路由层未传递 `quest_requirements` 参数
- **修复**：在 `genesis.py::generate_main_quest()` 中添加 `requirements=request.requirements`

**建议改进**：
- 增加中文默认提示
- 持久化用户需求到 `status.json`
- 支持任务草稿的多轮迭代优化

---

**分析完成日期**：2026-01-17  
**分析者**：Cline (AI Assistant)
