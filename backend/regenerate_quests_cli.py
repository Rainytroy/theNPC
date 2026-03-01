import asyncio
import json
import os
from app.services.components.quest_generator import QuestGenerator
from app.services.components.world_status_manager import WorldStatusManager
from app.core.config import settings

async def main():
    world_id = "af6c21d8-926f-46a0-97f4-4d1cf73041dc"
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    
    print(f"Regenerating quests for {world_id}...")
    
    # Load Bible & NPCs
    with open(os.path.join(world_dir, "bible.json"), "r", encoding="utf-8") as f:
        bible = json.load(f)
    
    with open(os.path.join(world_dir, "npcs.json"), "r", encoding="utf-8") as f:
        npcs = json.load(f)
        
    status_manager = WorldStatusManager()
    generator = QuestGenerator(status_manager)
    
    # Generate
    quests = await generator.generate_quests(bible, npcs)
    
    # Save
    quest_path = os.path.join(world_dir, "quests.json")
    with open(quest_path, "w", encoding="utf-8") as f:
        json.dump(quests, f, indent=2, ensure_ascii=False)
        
    print(f"Success! Generated {len(quests)} quests. Saved to {quest_path}")

if __name__ == "__main__":
    asyncio.run(main())
