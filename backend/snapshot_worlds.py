import os
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "worlds")

def snapshot_worlds():
    if not os.path.exists(DATA_DIR):
        logger.error(f"Data directory not found: {DATA_DIR}")
        return

    logger.info(f"Scanning worlds in {DATA_DIR}...")
    
    count = 0
    for world_id in os.listdir(DATA_DIR):
        world_path = os.path.join(DATA_DIR, world_id)
        if not os.path.isdir(world_path):
            continue
            
        logger.info(f"Checking world: {world_id}")
        
        # 1. Snapshot NPCs
        npc_path = os.path.join(world_path, "npcs.json")
        npc_orig_path = os.path.join(world_path, "npcs.original.json")
        
        if os.path.exists(npc_path) and not os.path.exists(npc_orig_path):
            shutil.copy2(npc_path, npc_orig_path)
            logger.info(f"  -> Created npcs.original.json")
            count += 1
        elif os.path.exists(npc_orig_path):
            logger.info(f"  -> npcs.original.json already exists")

        # 2. Snapshot Bible
        bible_path = os.path.join(world_path, "bible.json")
        bible_orig_path = os.path.join(world_path, "bible.original.json")
        
        if os.path.exists(bible_path) and not os.path.exists(bible_orig_path):
            shutil.copy2(bible_path, bible_orig_path)
            logger.info(f"  -> Created bible.original.json")
            count += 1
        elif os.path.exists(bible_orig_path):
            logger.info(f"  -> bible.original.json already exists")

    logger.info(f"Snapshot complete. Processed {count} files.")

if __name__ == "__main__":
    snapshot_worlds()
