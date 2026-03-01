# Event Data Schema Documentation

This document defines the unified data structure for all events within "theNPC" runtime environment. These events are broadcast to the frontend via WebSocket and persisted in `events.json`.

## Base Schema

Every event object follows this JSON structure:

```json
{
  "id": "UUID String (Unique Identifier)",
  "type": "event",
  "category": "action | social | player_interaction | system",
  "content": "String (The main text to display)",
  "source": "ID String (npc_id, 'player', 'system')",
  "target": "ID String (npc_id, 'player', 'all')",
  "game_time": "HH:MM (In-game time)",
  "real_time": "ISO 8601 Timestamp (Real-world time)",
  "metadata": {
    // Optional additional data depending on category
  }
}
```

## Categories

### 1. Action (NPC Autonomous Behavior)
*   **Description**: An NPC performs a scheduled action or a dynamic behavior.
*   **Source**: `npc_id`
*   **Target**: `all` (or specific location if we filter)
*   **Content Format**: `"{NPC Name}: {Action Description} (@{Location})"`
*   **Metadata**: `{"location": "..."}`

### 2. Social (NPC-NPC Interaction)
*   **Description**: Two or more NPCs talking to each other.
*   **Source**: `npc_id` (Speaker)
*   **Target**: `all` (or `npc_id` of listener)
*   **Content Format**: `"{NPC Name}: {Dialogue}"` or `"{NPC Name}: *{Action}* {Dialogue}"`
*   **Metadata**: `{"location": "...", "topic": "..."}`

### 3. Player Interaction (Player-NPC)
*   **Description**: Conversation between Player and NPC.
*   **Source**: `player` OR `npc_id`
*   **Target**: `npc_id` OR `player`
*   **Content Format**:
    *   Player: `"我 (对 {NPC}): {Message}"`
    *   NPC: `"{NPC}: {Response}"`

### 4. System (Notifications)
*   **Description**: Meta-events or narrator messages.
*   **Source**: `system`
*   **Target**: `player`
*   **Content Format**: Free text (e.g., "🏃 {NPC} left...", "🌟 Objective Updated").

## Persistence

*   **File**: `data/worlds/{world_id}/events.json`
*   **Format**: A JSON List `[...]`. New events are appended.
*   **Loading**: Upon WebSocket connection, the full history is sent as a `history` type message containing this list.
