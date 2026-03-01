# Runtime UI Rendering Rules (RuntimeView)

本文档记录了 `RuntimeView.vue` 中世界时间线（World Events）及 NPC 列表的渲染逻辑与视觉规范。

## 1. 事件解析规则 (Event Parsing)

前端会解析后端传来的 `event.content` 文本，用于区分 **对话 (Dialogue)** 和 **动作 (Action)**。

- **前缀处理**：如果内容包含冒号 `:`（例如 `NpcName: Hello`），系统会自动截取冒号之后的内容进行解析。
- **动作识别**：使用正则 `(\*[^*]+\*)` 匹配被星号包裹的文本（如 `*smiles*`）。
  - **动作 (Action)**：被 `*` 包裹的部分，渲染为灰色斜体或弱化文本。
  - **对话 (Dialogue)**：其余部分，渲染为对应分类的主题色。

### 核心代码 (TypeScript)
```typescript
interface ParsedContent {
  type: 'action' | 'dialogue';
  text: string;
}

const parseContent = (content: string): ParsedContent[] => {
  // 1. 去除冒号前缀 (例如 "NPC: Hello" -> " Hello")
  const textToParse = content.includes(':') 
    ? content.substring(content.indexOf(':') + 1) 
    : content;

  // 2. 正则分割
  const parts = textToParse.split(/(\*[^*]+\*)/g);
  
  return parts
    .map(part => {
      const isAction = part.startsWith('*') && part.endsWith('*');
      const cleanText = isAction ? part.slice(1, -1).trim() : part.trim();
      return {
        text: cleanText,
        type: isAction ? 'action' : 'dialogue'
      } as ParsedContent;
    })
    .filter(p => p.text.length > 0); // 过滤空字符串
};
```

## 2. 事件分类与样式 (Event Categories)

根据 `event.category` 字段，系统采用不同的颜色和布局策略。

### A. 玩家交互 (player_interaction)
*   **适用场景**：NPC 与玩家之间的对话或互动。
*   **主题色**：`#d946ef` (Magenta/紫红色)
*   **头部信息**：
    *   显示：`Source Name -> Target Name`
    *   图标：`ArrowRight`
    *   附加：如果 `metadata.location` 存在，显示 `MapPin` 图标 + 地点名称（灰色）。
*   **内容渲染**：
    *   调用 `parseContent` 解析。
    *   对话文本：**紫红色** (`text-[#d946ef]`)。
    *   动作文本：**灰色** (`text-zinc-400`)。

### B. 社交互动 (social)
*   **适用场景**：NPC 之间的对话或互动。
*   **主题色**：`text-amber-400` (Amber/琥珀黄)
*   **头部信息**：
    *   显示：`Source Name -> Target Name`
    *   图标：`ArrowRight`
    *   附加：如果 `metadata.location` 存在，显示 `MapPin` 图标 + 地点名称。
*   **内容渲染**：
    *   调用 `parseContent` 解析。
    *   对话文本：**琥珀黄** (`text-amber-400`)。
    *   动作文本：**灰色** (`text-zinc-400`)。

### C. 单人行为 (action)
*   **适用场景**：NPC 的个人行动、移动或状态变更。
*   **主题色**：`text-emerald-400` (Emerald/翠绿色)
*   **头部信息**：
    *   显示：`Source Name`
    *   附加：如果 `metadata.location` 存在，显示 `MapPin` 图标 + 地点名称。
*   **内容渲染**：
    *   **不解析**动作/对话标记。
    *   直接显示完整 `content` 文本。
    *   颜色：**翠绿色** (`text-emerald-400`)。

### D. 系统消息 (system / default)
*   **适用场景**：世界旁白、目标更新、系统提示。
*   **特殊类型**：
    *   如果 `metadata.type === 'objective'`：
        *   样式：`text-[#ccff00]` (Lime/荧光绿)，**加粗**，字间距加宽。
        *   用于显示任务目标更新。
*   **默认样式**：
    *   颜色：`text-zinc-500` (深灰色)。

### 渲染示例 (Vue Template)
```html
<!-- 示例：Player Interaction -->
<div v-if="event.category === 'player_interaction'" class="text-sm">
  <!-- Header -->
  <div class="flex items-center gap-2 mb-1 text-sm font-bold text-[#d946ef] uppercase tracking-wide">
    <span>{{ getNpcName(event.source) }}</span>
    <ArrowRight class="w-4 h-4 text-zinc-700" />
    <span>{{ getNpcName(event.target) }}</span>
    
    <!-- Location (Optional) -->
    <template v-if="event.metadata?.location">
      <MapPin class="w-3 h-3 ml-2 text-zinc-700" />
      <span class="text-zinc-500 text-xs font-normal">{{ event.metadata.location }}</span>
    </template>
  </div>
  
  <!-- Content Body -->
  <div class="space-y-1">
    <div v-for="(part, idx) in parseContent(event.content)" :key="idx">
      <!-- 动作: 灰色 -->
      <p v-if="part.type === 'action'" class="text-zinc-400 block mb-1">{{ part.text }}</p>
      <!-- 对话: 主题色 -->
      <p v-else class="text-[#d946ef]">{{ part.text }}</p>
    </div>
  </div>
</div>
```

## 3. NPC 列表渲染 (NPC List)

左侧侧边栏显示当前世界的所有 NPC 状态。

*   **卡片样式**：
    *   默认：深色背景 (`bg-zinc-950`)，灰色边框。
    *   选中：紫红色背景淡化 (`bg-[#d946ef]/10`)，紫红色边框。
*   **状态指示**：
    *   **地点 (Location)**：显示 `MapPin` 图标 + `dynamic.current_location`。
    *   **当前行为 (Current Action)**：
        *   显示 `dynamic.current_action`。
        *   如果存在行为，标题旁会显示绿色的 `Activity` 图标并带有呼吸动画 (`animate-pulse`)。

## 4. 时间与状态栏 (Top Bar)

*   **时间显示**：
    *   格式：`周X, X月X日, HH:mm` (中文本地化)。
    *   未就绪时显示 "初始化中..."。
*   **状态标签**：
    *   **Running (LIVE)**：`#d946ef` (紫红色) + 背景高亮。
    *   **Paused (PAUSED)**：红色 + 背景高亮。
    *   **Waiting**：灰色。
    *   **Loading**：琥珀色 + 旋转 Loading 图标。

## 5. 图标系统 (Icons)

使用了 `lucide-vue-next` 图标库：
- `ArrowRight`: 交互指向 (->)
- `MapPin`: 地点指示
- `Activity`: 正在进行的活动
- `Clock`: 时间
- `History`: 历史记录/加载更多
- `User`: NPC/居民
- `Play/Pause`: 时间控制
