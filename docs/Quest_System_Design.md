# Quest System Design & Generation Logic

## Overview
The Quest System transforms the open world into a narrative-driven experience. Instead of just existing, NPCs now actively participate in stories that the Player must uncover. This system is tightly integrated with the **NPC Affinity System**, meaning progress often requires building relationships, not just solving puzzles.

## Core Concepts

### 1. Quest (The Story Arc)
A linear or branching sequence of events that tells a specific story.
- **Main Quest**: Generated based on the "Player Objective" defined in the World Bible.
- **Side Quests**: Generated based on NPC backstories and local lore.

### 2. QuestNode (The Step)
A single step in a Quest.
- **Description**: What needs to happen (e.g., "Find the Key").
- **Target NPC**: Who holds the key to progress.
- **Affinity Gate**: The relationship level required with the Target NPC to unlock this step.
- **Status**: `pending` -> `active` -> `completed`.

### 3. Affinity (The Relationship)
A value (-5 to +5) representing the relationship between the Player and an NPC.
- **-5 (Hostile)**: Will attack or flee.
- **0 (Neutral)**: Polite but guarded.
- **+1 (Acquaintance)**: Willing to share rumors.
- **+3 (Friend)**: Willing to share secrets/items.
- **+5 (Confidant)**: Will risk safety for the player.

---

## Data Structures

### Quest Schema
```python
class QuestNode(BaseModel):
    id: str             # e.g., "q1_n1_ask_info"
    description: str    # e.g., "Ask the Bartender about the rumors"
    target_npc_id: str  # The NPC to interact with
    required_affinity: int = 0  # Min affinity needed (e.g., 1)
    status: str = "pending" # pending, active, completed

class Quest(BaseModel):
    id: str
    title: str
    type: str # "main" or "side"
    nodes: List[QuestNode]
    current_node_index: int = 0
```

### NPC Schema Updates
*   **`player_affinity`**: Integer (-5 to 5), stored in `NPC.relationships["player"]`.

---

## Quest Generation Process (Genesis Phase 3)

The Quest Generation runs *after* the World Bible and NPC Roster are generated.

### Input
1.  **World Bible**:
    *   `player_objective`: The ultimate goal (e.g., "Find the Lost Videotape").
    *   `world_theme`: The narrative tone (e.g., "Cyberpunk Mystery").
2.  **NPC Roster**: List of all generated NPCs (Name, Occupation, Personality).

### Process (LLM Prompt)
The `QuestGenerator` (AI Writer) performs the following steps:

1.  **Deconstruction**: Breaks down the `player_objective` into 3-5 logical steps (Nodes).
2.  **Casting**: Assigns existing NPCs to each node.
    *   *Example*: "Node 1 is gathering info. Who is the gossip? -> Bartender."
    *   *Example*: "Node 2 is getting an item. Who hides things? -> The suspicious Antique Dealer."
3.  **Gating**: Assigns difficulty (Affinity Requirement) based on the narrative tension.
    *   Early steps: Low affinity (0-1).
    *   Climax steps: High affinity (3-5).
4.  **Side Quest Generation**: Creates 2-3 extra quests based on unused NPC backstories to flesh out the world.

### Output
A `quests.json` file containing the structured Quest list.

---

## Runtime Integration

### Interaction Flow
1.  **Player talks to NPC A**.
2.  **PlayerEngine Check**:
    *   Is there an **Active Quest Node** where `target_npc_id == NPC A`?
    *   Is `NPC A.affinity >= node.required_affinity`?
3.  **Prompt Injection**:
    *   *If Yes*: "Player is asking about [Quest Topic]. Affinity is sufficient. REVEAL THE CLUE: [Node Description]. Trigger Quest Advance."
    *   *If No*: "Player is asking about [Quest Topic]. Affinity is too low. REFUSE politeley. Hint that you need to trust them more."
4.  **State Update**:
    *   LLM Output includes `update_quest` (advance node) or `update_affinity` (change score).
    *   System updates `quests.json` and `npcs.json`.

---

## Future Expansion
*   **Item System**: Nodes that require possessing specific items.
*   **Time Limits**: Nodes that must be completed before a certain schedule time.
