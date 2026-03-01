# Social Engine (SocialEngine)

## Path: `backend/app/engines/social_engine.py`

## Logic
Responsible for detecting when NPCs should interact and generating the conversation content using LLMs.

### Updated Design (Renovation 2025-02-09)
The engine has been redesigned to prioritize "Interpersonal History" and "Information Propagation" over simple "Location Context".

#### Key Principles
1.  **Shared History > Location History**: What A and B talked about before (anywhere) is more important than what C and D said here 5 minutes ago.
2.  **5-Layer Behavior Priority**:
    *   **Layer 1: Routine & Persona** (Highest): Adhere to daily schedule and basic personality.
    *   **Layer 2: Urgent Goals**: Only deviate from routine if a goal is strictly urgent and relevant to the partner.
    *   **Layer 3: Quest Stance**: Helper vs Blocker logic towards the Player.
    *   **Layer 4: Info Propagation**: Check memory for secrets/gossip to pass on.
    *   **Layer 5: Hidden Depth**: Only reveal deep thoughts if affinity is high.

#### Context Injection Strategy
*   **Global**: Time, Location, Player Objective.
*   **Participant**:
    *   **Routine**: Current activity (e.g., "Patrolling", "Resting").
    *   **Memory 1 (Shared History)**: `query="Interaction with {PartnerName}"` (5-10 results).
    *   **Memory 2 (Quest/Secrets)**: `query="Player" OR "Quest" OR "{PartnerName}"` (Find gossip/secrets).

## Key Implementation

```python
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from ..schemas.npc import NPC
from ..core.llm import llm_client
from ..prompts.social import SOCIAL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
SOCIAL_COOLDOWN = timedelta(minutes=60)

class SocialEngine:
    # ... (See implementation in actual file)
    pass
```
