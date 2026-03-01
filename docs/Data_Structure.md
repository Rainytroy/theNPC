# theNPC - 数据结构定义文档

> **版本**: 1.0  
> **用途**: 定义服务端存储的 JSON 数据结构，以及前后端交互的数据对象。

## 1. 世界设定 (World Bible)

存储于 `data/worlds/{world_id}/bible.json`。

```json
{
  "world_id": "uuid",
  "created_at": "timestamp",
  "background": {
    "era": "Cyberpunk 2077 style",
    "rules": ["High tech, low life", "Neon lights everywhere"],
    "society": "Corporation dominated"
  },
  "scene": {
    "name": "Midnight Ramen Stand",
    "description": "A small, steamy ramen stand located in the lower district...",
    "key_objects": ["Ramen Counter", "Vending Machine", "Old TV"]
  },
  "time_config": {
    "start_date": "2077-01-01",
    "day_length_real_sec": 3600 // 1 Game Day = 3600 Real Seconds
  }
}
```

## 2. NPC 档案 (NPC Profile)

存储于 `data/worlds/{world_id}/npcs/{npc_id}.json`。

### 2.1 完整结构
```json
{
  "id": "npc_001",
  "meta": {
    "name": "Kenji",
    "age": 45,
    "gender": "Male",
    "race": "Human (Cyborg)",
    "avatar_url": "/assets/avatars/kenji.png"
  },
  "personality": {
    "traits": ["Stoic", "Hardworking", "Secretly caring"],
    "speaking_style": "Short sentences, uses old slang",
    "values": ["Loyalty to customers", "Quality of food above all"]
  },
  "status": {
    "location": "Behind the counter",
    "mood": "Focused",
    "current_action": "Cooking noodles",
    "energy": 80
  },
  "capabilities": {
    "cooking": { "level": 9, "desc": "Master of Ramen" },
    "fighting": { "level": 2, "desc": "Can use a knife if needed" }
  },
  "goals": [
    {
      "id": "goal_main_1",
      "type": "main",
      "description": "Keep the ramen stand open despite debt",
      "status": "in_progress",
      "priority": 10
    },
    {
      "id": "goal_sub_1",
      "type": "sub",
      "description": "Serve the customer who just sat down",
      "status": "pending",
      "trigger_condition": "customer_order",
      "created_at": "timestamp"
    }
  ],
  "relationships": {
    "player": {
      "know_name": false,
      "affinity": 10, // 0-100
      "impressions": ["Just another hungry soul"]
    },
    "npc_002": {
      "know_name": true,
      "affinity": 60,
      "impressions": ["Old friend, owes me money"]
    }
  },
  "memory_archive": [
    {
      "date": "2077-01-01",
      "summary": "Served a strange customer today. It rained heavily.",
      "key_events": ["Player asked about the corporation"]
    }
  ]
}
```

## 3. 运行时消息对象 (Runtime Messages)

这些对象不一定持久化存储，但在 Event Bus 和 WebSocket 中流转。

### 3.1 玩家输入 (PlayerAction)
```typescript
interface PlayerAction {
  source_id: "player";
  target_id: string; // "npc_id" or "all"
  action_type: "speak" | "gesture" | "move";
  content: string; // "Hello" or "Waved hand"
  timestamp: number;
}
```

### 3.2 NPC 响应 (NPCResponse)
```typescript
interface NPCResponse {
  source_id: string; // npc_id
  target_id: string; // "player" or other npc_id
  action_text: string; // "Nods slowly"
  dialogue_text: string; // "Welcome back." (Nullable)
  emotion_tag: string; // "neutral"
  timestamp: number;
}
```

### 3.3 系统事件 (SystemEvent)
```typescript
interface SystemEvent {
  type: "weather" | "news" | "gm_intervention";
  description: string;
  effect_scope: string[]; // Affected NPC IDs
}
