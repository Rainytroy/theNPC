# Genesis JSON Commands Reference

## 📋 概述

本文档定义了Genesis创世阶段中**Sower Agent**与系统交互的所有JSON命令格式。这些命令嵌入在LLM的响应中，用于触发特定的系统行为和UI交互。

### 命令格式规范

所有JSON命令必须包含在markdown代码块中：

```json
{
  "command_name": value,
  ...
}
```

系统会自动提取并解析这些JSON块，执行相应的操作。

---

## 1. 阶段转换命令

### 1.1 World → NPC (世界设定完成)

**触发时机**：当用户与Agent完成世界设定对话，准备进入NPC生成阶段

**JSON格式**：
```json
{
  "ready": true,
  "world_setting": {
    "title": "世界标题",
    "background": {
      "era": "时代背景描述",
      "rules": ["法则1", "法则2", "法则3"],
      "society": "社会形态描述"
    },
    "scene": {
      "name": "场景名称",
      "description": "场景描述",
      "atmosphere": "氛围描述"
    },
    "player_objective": "玩家目标"
  }
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ready` | `boolean` | ✅ | 必须为 `true`，表示世界设定已完成 |
| `world_setting` | `object` | ✅ | 完整的世界设定对象，参考 `WorldBible` schema |
| `world_setting.title` | `string` | ✅ | 世界标题 |
| `world_setting.background` | `object` | ✅ | 背景设定 |
| `world_setting.scene` | `object` | ✅ | 核心场景 |
| `world_setting.player_objective` | `string` | ✅ | 玩家目标 |

**前端响应**：
```typescript
GenesisChatResponse {
  is_ready_to_generate: true,
  suggested_world_setting: { ... }
}
```

**后端处理**：
- 位置：`genesis_service.py` 第189-201行
- 触发 `finalize_world_phase()`
- 生成世界摘要并保存到 `status.json`
- 更新阶段为 `npc`

---

### 1.2 NPC → Quest (居民名册完成)

**触发时机**：当用户确认NPC名册已完成，准备进入任务蓝图阶段

**JSON格式**：
```json
{
  "confirm_roster": true
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `confirm_roster` | `boolean` | ✅ | 必须为 `true`，表示居民名册已完成 |

**前端响应**：
```typescript
GenesisChatResponse {
  pending_actions: [
    {
      type: "enter_quest_phase",
      label: "生成任务 (Generate Quests)",
      style: "primary"
    },
    {
      type: "cancel_enter_quest",
      label: "调整居民 (Modify NPCs)",
      style: "secondary"
    }
  ]
}
```

**后端处理**：
- 位置：`genesis_service.py` 第245-255行
- 当用户点击按钮后，调用 `handle_roster_confirm()`
- 生成居民摘要并保存到 `status.json`
- 更新阶段为 `quest`

---

### 1.3 Quest → Launch (任务蓝图完成)

**触发时机**：当用户确认任务蓝图已完成，准备启动世界

**JSON格式**：
```json
{
  "confirm_quests": true
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `confirm_quests` | `boolean` | ✅ | 必须为 `true`，表示任务蓝图已完成 |

**前端响应**：
- 生成"启动世界"按钮
- 更新阶段为 `launch`

---

## 2. NPC管理命令

### 2.1 生成NPC请求

**触发时机**：用户首次请求生成NPC时

**JSON格式**：
```json
{
  "ready_for_npc": true,
  "npc_requirements": "需求描述（例如：需要3位居民，包括一位武者、一位商人和一位医师）",
  "count": 3
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ready_for_npc` | `boolean` | ✅ | 必须为 `true` |
| `npc_requirements` | `string` | ❌ | NPC需求的自然语言描述 |
| `count` | `number` | ❌ | NPC数量，默认3 |

**前端响应**：
```typescript
GenesisChatResponse {
  is_ready_for_npc: true,
  npc_requirements: "需求描述",
  npc_count: 3
}
```

**后端处理**：
- 位置：`genesis_service.py` 第203-213行
- 前端调用 `generateNPCs()` API
- 分两阶段生成：roster → details

---

### 2.2 增加NPC

**触发时机**：用户要求在现有基础上增加更多NPC

**JSON格式**：
```json
{
  "add_npc": {
    "count": 2,
    "requirements": "增加两位江湖侠客，一位擅长暗器，一位精通轻功"
  }
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `add_npc` | `object` | ✅ | 增加NPC指令对象 |
| `add_npc.count` | `number` | ✅ | 要增加的NPC数量 |
| `add_npc.requirements` | `string` | ❌ | 新NPC的需求描述 |

**前端响应**：
```typescript
GenesisChatResponse {
  pending_actions: [
    {
      type: "add_npc",
      data: { world_id, count, requirements },
      label: "增加 2 位居民",
      style: "primary"
    },
    {
      type: "cancel",
      label: "取消",
      style: "secondary"
    }
  ]
}
```

**后端处理**：
- 位置：`genesis_service.py` 第215-227行
- 用户点击确认后调用 `execute_add_npc()`

---

### 2.3 重新生成NPC

**触发时机**：用户对某个NPC不满意，要求重新生成或修改

**JSON格式**：
```json
{
  "regenerate_npc": {
    "target_name": "张三",
    "instruction": "让这个角色更年轻一些，增加一些幽默感"
  }
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `regenerate_npc` | `object` | ✅ | 重新生成指令对象 |
| `regenerate_npc.target_name` | `string` | ✅ | 目标NPC的名字 |
| `regenerate_npc.instruction` | `string` | ✅ | 修改指令的自然语言描述 |

**前端响应**：
```typescript
GenesisChatResponse {
  pending_actions: [
    {
      type: "regenerate_npc",
      data: { world_id, target_name, instruction },
      label: "修改居民: 张三",
      style: "primary"
    },
    {
      type: "cancel",
      label: "取消",
      style: "secondary"
    }
  ]
}
```

**后端处理**：
- 位置：`genesis_service.py` 第229-243行
- 用户点击确认后调用 `execute_npc_regenerate()`

---

### 2.4 更新NPC（遗留）

**⚠️ 注意**：这是旧版命令，仅用于更新头像描述，建议使用 `regenerate_npc`

**JSON格式**：
```json
{
  "update_npc": {
    "target_name": "张三",
    "new_avatar_desc": "新的外貌描述"
  }
}
```

**后端处理**：
- 位置：`genesis_service.py` 第257-263行
- 自动执行，不需要用户确认

---

## 3. 图片管理命令

### 3.1 批量生成立绘

**触发时机**：用户要求为所有NPC生成立绘

**JSON格式**：
```json
{
  "manage_images": {
    "action": "generate_all"
  }
}
```

**前端响应**：
```typescript
GenesisChatResponse {
  pending_actions: [
    {
      type: "manage_images",
      data: { world_id, action: "generate_all" },
      label: "生成立绘 (Generate Images)",
      style: "primary"
    },
    {
      type: "cancel",
      label: "取消",
      style: "secondary"
    }
  ]
}
```

---

### 3.2 单个生成立绘

**触发时机**：用户要求为指定NPC生成立绘

**JSON格式**：
```json
{
  "manage_images": {
    "action": "generate_one",
    "target_name": "张三"
  }
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `manage_images.action` | `string` | ✅ | 固定值：`"generate_one"` |
| `manage_images.target_name` | `string` | ✅ | 目标NPC的名字 |

---

### 3.3 开启图文模式

**JSON格式**：
```json
{
  "manage_images": {
    "action": "enable"
  }
}
```

---

### 3.4 关闭图文模式

**JSON格式**：
```json
{
  "manage_images": {
    "action": "disable"
  }
}
```

---

## 4. 前端响应字段映射

### GenesisChatResponse Schema

```typescript
interface GenesisChatResponse {
  response: string;                    // LLM的文本响应（已移除JSON块）
  is_ready_to_generate: boolean;       // 世界设定是否完成
  suggested_world_setting?: object;    // 建议的世界设定
  is_ready_for_npc: boolean;          // 是否准备生成NPC
  npc_requirements?: string;           // NPC需求描述
  npc_count: number;                   // NPC数量
  pending_actions: PendingAction[];    // 待处理的操作按钮
}

interface PendingAction {
  type: string;      // 操作类型
  data: object;      // 操作数据
  label: string;     // 按钮文本
  style: string;     // 按钮样式（primary/secondary）
}
```

### 字段对应关系

| JSON命令 | 前端字段 |
|---------|---------|
| `{"ready": true, "world_setting": {...}}` | `is_ready_to_generate = true` |
| `{"ready_for_npc": true}` | `is_ready_for_npc = true` |
| `{"confirm_roster": true}` | `pending_actions` 包含按钮 |
| `{"add_npc": {...}}` | `pending_actions` 包含按钮 |
| `{"regenerate_npc": {...}}` | `pending_actions` 包含按钮 |
| `{"manage_images": {...}}` | `pending_actions` 包含按钮 |

---

## 5. 完整示例

### 示例1：完成世界设定

**Agent响应**：
```
太好了！您描述的这个明末武侠世界充满了冲突与机遇。让我为您整理一下：

【世界设定已完成】
- 时代：明朝末年崇祯年间
- 法则：江湖以武为尊，正邪两道对立
- 场景：云透城·醉仙楼

现在我们可以进入下一阶段，为这个世界创造居民了！

```json
{
  "ready": true,
  "world_setting": {
    "title": "江湖风云录",
    "background": {
      "era": "明朝末年崇祯年间，关外清军压境，内有流寇作乱",
      "rules": ["江湖以武为尊", "正邪两道势不两立", "恩怨当面了"],
      "society": "江湖分为正道五大门派与邪道三大势力"
    },
    "scene": {
      "name": "云透城·醉仙楼",
      "description": "边境重镇的著名客栈",
      "atmosphere": "江湖人士汇聚之地"
    },
    "player_objective": "在江湖中闯出名号，查明师门灭门真相"
  }
}
```
```

**前端处理**：
1. 解析JSON，提取 `world_setting`
2. 设置 `is_ready_to_generate = true`
3. 显示"确认世界之书定稿"按钮
4. 用户点击后调用 `confirmWorld()` API

---

### 示例2：修改NPC

**用户**："张三这个角色太严肃了，能让他更活泼一些吗？"

**Agent响应**：
```
好的，我来帮您调整张三的性格，让他更加活泼开朗。

```json
{
  "regenerate_npc": {
    "target_name": "张三",
    "instruction": "调整性格为更加活泼开朗，增加幽默感和亲和力"
  }
}
```
```

**前端处理**：
1. 解析JSON，生成两个按钮：
   - "修改居民: 张三"（主按钮）
   - "取消"（次按钮）
2. 用户点击主按钮后调用 `executeAction()` API
3. 后端重新生成张三的详细信息

---

## 6. 调试建议

### 6.1 检查JSON是否被正确提取

在 `genesis_service.py` 的 `chat()` 方法中，添加调试日志：

```python
data = parse_json_from_llm(response_text)
if data:
    print(f"DEBUG: Extracted JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")
```

### 6.2 检查前端是否收到正确响应

在前端 `genesis.ts` 中：

```typescript
const response = await genesisApi.chat(...)
console.log('Chat Response:', response)
console.log('Pending Actions:', response.pending_actions)
```

### 6.3 常见问题

**Q: JSON没有被识别？**
- 检查JSON是否在markdown代码块中
- 检查JSON格式是否正确（逗号、引号等）
- 检查 `parse_json_from_llm()` 是否工作正常

**Q: 按钮没有出现？**
- 检查 `pending_actions` 是否为空数组
- 检查前端是否正确渲染 `choices`
- 检查 `world_id` 是否正确传递

**Q: 命令执行后没有效果？**
- 检查后端日志，确认API被调用
- 检查 `status.json` 是否更新
- 检查 `npcs.json` 是否被修改

---

## 7. 相关代码位置

### 后端

| 文件 | 行号 | 功能 |
|------|------|------|
| `genesis_service.py` | 189-281 | JSON命令解析和处理 |
| `genesis_service.py` | 372-403 | `finalize_world_phase()` |
| `genesis_service.py` | 405-462 | `handle_roster_confirm()` |
| `core/utils.py` | - | `parse_json_from_llm()` |

### 前端

| 文件 | 功能 |
|------|------|
| `stores/genesis.ts` | Genesis状态管理 |
| `api/genesis.ts` | API调用封装 |
| `components/GenesisChat.vue` | 对话界面和按钮渲染 |

---

## 8. 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2025-12-15 | 1.0.0 | 初始版本，包含所有核心命令 |

---

## 9. 下一步计划

- [ ] 添加 Quest 阶段的 JSON 命令
- [ ] 添加错误处理和重试机制
- [ ] 优化JSON解析的健壮性
- [ ] 添加命令执行的状态反馈
