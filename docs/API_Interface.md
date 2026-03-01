# theNPC - 前后端接口规范文档

> **版本**: 1.0  
> **后端地址**: `http://localhost:26000`  
> **WS地址**: `ws://localhost:26000/ws`

## 1. 概述
本系统采用 REST API 负责“控制流”（如创世、配置、启停），采用 WebSocket 负责“数据流”（如实时对话、状态更新）。

---

## 2. REST API 接口定义

### 2.1 创世阶段 (Genesis)

#### 初始化创世会话
*   **URL**: `/api/genesis/start`
*   **Method**: `POST`
*   **Response**:
    ```json
    {
      "session_id": "uuid",
      "message": "我是播种者Agent，请告诉我你想创造什么样的世界？"
    }
    ```

#### 与播种者对话
*   **URL**: `/api/genesis/chat`
*   **Method**: `POST`
*   **Body**:
    ```json
    {
      "session_id": "uuid",
      "content": "我想要一个赛博朋克风格的拉面摊"
    }
    ```
*   **Response**:
    ```json
    {
      "response": "好的，这个拉面摊位于新东京的下层区吗？...",
      "is_ready_to_generate": false
    }
    ```

#### 确认世界设定
*   **URL**: `/api/genesis/confirm_world`
*   **Method**: `POST`
*   **Body**: `{"session_id": "...", "world_setting": {...}}` (可选，若为空则使用最后一次对话生成的设定)
*   **Response**: `{"status": "success", "world_bible": {...}}`

#### 生成/重新生成 NPC
*   **URL**: `/api/genesis/generate_npcs`
*   **Method**: `POST`
*   **Body**: `{"session_id": "...", "count": 3}`
*   **Response**:
    ```json
    {
      "npcs": [
        {"id": "npc_1", "name": "...", "role": "..."},
        ...
      ]
    }
    ```

### 2.2 世界控制 (World Control)

#### 启动/加载游戏
*   **URL**: `/api/world/launch`
*   **Method**: `POST`
*   **Body**: `{"world_id": "world_001"}`
*   **Response**: `{"status": "running"}`

#### 暂停游戏
*   **URL**: `/api/world/pause`
*   **Method**: `POST`

#### 获取当前全量状态 (用于前端初始化/重连)
*   **URL**: `/api/world/state`
*   **Method**: `GET`
*   **Response**:
    ```json
    {
      "world_time": "Day 1 10:00",
      "npcs": [...],
      "logs": [...] // 最近N条日志
    }
    ```

---

## 3. WebSocket 通信协议

前端连接至 `ws://localhost:26000/ws/{client_id}`。

### 3.1 客户端发送 (C2S)

#### 玩家输入 (动作/对话)
```json
{
  "type": "player_input",
  "payload": {
    "target_npc_id": "npc_001", // 或 "all"
    "action": "smile",         // 表情/动作
    "content": "老板，来碗面"     // 对话内容
  }
}
```

### 3.2 服务端推送 (S2C)

#### 1. 时间流逝 (Tick)
```json
{
  "type": "world_tick",
  "payload": {
    "game_time": "2077-01-01 10:05",
    "day_phase": "morning"
  }
}
```

#### 2. NPC 响应 (Response)
这是最核心的消息，展示NPC的思考与行动。
```json
{
  "type": "npc_response",
  "payload": {
    "npc_id": "npc_001",
    "npc_name": "老张",
    "action": "擦了擦桌子",    // 动作描述
    "dialogue": "好勒，马上好！", // 对话内容 (可为空)
    "target": "player"
  }
}
```

#### 3. 世界旁白/系统日志 (System Log)
```json
{
  "type": "system_log",
  "payload": {
    "level": "info", // info, warning, event
    "content": "外面开始下起了酸雨..."
  }
}
```

#### 4. NPC 状态变更 (State Update)
当NPC属性发生变化时推送（如好感度变化、位置移动）。
```json
{
  "type": "npc_update",
  "payload": {
    "npc_id": "npc_001",
    "changes": {
      "location": "kitchen",
      "mood": "busy"
    }
  }
}
