# Runtime Engine Refactoring Architecture

## Overview
The `RuntimeEngine` (originally in `runtime.py`) has grown to handle too many responsibilities, including time management, NPC scheduling, social interactions, player handling, and system events. 

To improve maintainability and scalability, we are splitting the monolithic `runtime.py` into specialized engines/modules.

## New Directory Structure
```
backend/app/
├── core/
│   ├── runtime.py          # Facade & State Holder (Slimmed down)
│   ├── clock.py            # Time Management
│   └── global_state.py     # Global singleton for FastAPI access
├── engines/
│   ├── social_engine.py    # NPC-NPC Interactions
│   ├── player_engine.py    # Player-NPC Interactions
│   ├── director_engine.py  # System/Global Events
│   └── reflection_engine.py # Daily Reflections & Long-term Memory
```

## Module Responsibilities

### 1. `core/clock.py` (WorldClock)
- Manages the game loop (asyncio task).
- Handles time scaling (real seconds to game minutes).
- Provides a subscription mechanism for other engines to react to "ticks".

### 2. `core/runtime.py` (RuntimeEngine)
- **Coordinator**: Initializes and holds instances of all sub-engines.
- **State Holder**: Manages the canonical state of NPCs, World Bible, and Schedules.
- **Persistence**: Handles loading/saving of data (`state.json`, `schedules.json`, `events.jsonl`).
- **Communication**: Manages WebSocket connections and broadcasting.

### 3. `engines/social_engine.py` (SocialEngine)
- **Trigger**: Checks for colocated NPCs on every tick.
- **Logic**: Decides if a conversation should happen (cooldowns, probability).
- **Execution**: Calls LLM to generate dialogue and updates memory/relationships.

### 4. `engines/player_engine.py` (PlayerEngine)
- **Trigger**: Activated by incoming WebSocket messages (Player Actions).
- **Logic**: Determines which NPC is targeted and constructs the reaction context.
- **Execution**: Calls LLM to generate NPC response/action and updates NPC state.

### 5. `engines/director_engine.py` (DirectorEngine)
- **Trigger**: Runs periodically (e.g., every 4 game hours).
- **Logic**: Evaluates global state to see if a plot twist or environmental event is needed.
- **Execution**: Generates system events that affect all NPCs.

### 6. `engines/reflection_engine.py` (ReflectionEngine)
- **Trigger**: Runs daily (e.g., at 22:00).
- **Logic**: Summarizes the day's events for each NPC.
- **Execution**: Updates NPC long-term memory, mood, and goals.

## Data Flow
1. **Clock Tick** -> `RuntimeEngine.on_tick`
2. `RuntimeEngine` delegates to:
   - `SocialEngine.check_interactions(current_time)`
   - `DirectorEngine.check_event(current_time)` (if interval met)
   - `ReflectionEngine.check_schedule(current_time)`
3. **Player Input** -> `RuntimeEngine.handle_player_action` -> `PlayerEngine.handle_action`
