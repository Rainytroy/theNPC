# Quest 升级迭代 02：第一步实现计划 (Phase 1)

> **版本**: 1.0
> **状态**: 待审阅
> **周期**: 预计 2 天
> **核心任务**: 数据结构扩展 (Schema) 与 物品系统原型 (Items)

## 1. 任务清单 (Tasks)

### 1.1 新增数据模型 (Schema)
我们首先需要定义新的数据结构，为条件判断打好基础。

*   [ ] **创建 `backend/app/schemas/item.py`**
    *   定义 `Item` 模型：包含 `id`, `name`, `description`, `type` (key/consumable/tool), `icon`。
*   [ ] **更新 `backend/app/schemas/quest.py`**
    *   新增 `QuestCondition` 模型：支持 `type` 和 `params`。
    *   更新 `QuestNode` 模型：
        *   添加 `type` (Literal: dialogue, collect, investigate, wait)。
        *   添加 `conditions` (List[QuestCondition])。
        *   保留 `target_npc_id` (作为 Dialogue 类型的必填项，其他类型可选)。

### 1.2 创建 Mock 数据
为了测试物品系统，我们需要一份预设的物品清单。

*   [ ] **创建 `backend/data/items.json`**
    *   填入 5-10 个基础物品（如：旧钥匙、神秘信件、苹果、金币）。

### 1.3 改造 PlayerEngine
让玩家不仅能“说话”，还能“做动作”。

*   [ ] **修改 `backend/app/engines/player_engine.py`**
    *   在 `process_message` 中增加指令解析逻辑。
    *   **识别规则**: 以 `*` 开头的内容被视为动作 (Action)。
        *   `*给予 <物品名>*` -> 触发 `give_item` 逻辑。
        *   `*调查 <对象>*` -> 触发 `investigate` 逻辑。
    *   **临时处理**: Phase 1 阶段，解析成功后仅需在 Log 中打印 "Action Detected: [Type] [Target]"，并模拟返回一个系统提示。

### 1.4 兼容性测试
确保新的 Schema 不会破坏现有的存档读取。

*   [ ] **测试 QuestEngine 加载**
    *   使用旧的 `quests.json` 测试加载，确保向后兼容（字段设为 Optional）。
    *   创建一个包含新字段的 `quests_v2_test.json` 测试加载。

---

## 2. 验收标准 (Acceptance Criteria)

1.  **Schema 验证**: 能够成功通过 Pydantic 校验并实例化一个包含 `conditions` 的 `QuestNode`。
2.  **动作解析**: 在前端对话框输入 `*给予 苹果*`，后端日志中能清晰看到解析出的 `action_type="give"` 和 `target="苹果"`。
3.  **无回归**: 现有的纯对话任务依然能正常运行，不会报错。

---

## 3. 代码预览 (Code Preview)

### 3.1 Item Schema
```python
class Item(BaseModel):
    id: str
    name: str
    description: str
    type: Literal["key", "consumable", "tool", "clue"]
```

### 3.2 QuestCondition Schema
```python
class QuestCondition(BaseModel):
    type: Literal["affinity", "item", "location", "time", "state"]
    # 使用 Dict 存储不同条件所需的参数
    # 例: {"item_id": "key_01", "count": 1}
    params: Dict[str, Any] = {} 
```
