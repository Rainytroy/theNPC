import os
import json
import re
import uuid
from typing import List, Dict
from app.schemas.item import Item

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "worlds")

def extract_items_from_bible(world_id: str):
    world_dir = os.path.join(DATA_DIR, world_id)
    bible_path = os.path.join(world_dir, "bible.json")
    items_path = os.path.join(world_dir, "items.json")

    if not os.path.exists(bible_path):
        print(f"Skipping {world_id}: bible.json not found.")
        return

    try:
        with open(bible_path, "r", encoding="utf-8") as f:
            bible = json.load(f)
    except Exception as e:
        print(f"Error reading bible for {world_id}: {e}")
        return

    # Extract Key Objects
    scene_data = bible.get("scene", {})
    key_objects = scene_data.get("key_objects", [])
    
    if not key_objects:
        print(f"No key_objects found in {world_id}.")
        return

    generated_items = []
    
    print(f"Found {len(key_objects)} objects in {world_id}...")

    for obj_str in key_objects:
        # Parse "Name(Description)" format
        match = re.match(r"^(.*?)[（\(](.*?)[）\)]$", obj_str)
        if match:
            name = match.group(1).strip()
            desc = match.group(2).strip()
        else:
            name = obj_str
            desc = "从世界设定中发现的关键物品。"

        # Generate ID
        # Simple ID generation: item_{hash}
        import hashlib
        short_hash = hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
        item_id = f"item_{short_hash}"

        item = Item(
            id=item_id,
            name=name,
            description=desc,
            type="key", # Default to key item
            rarity="rare",
            obtain_methods=[
                {"method": "find", "source": "World Scene"} 
            ]
        )
        generated_items.append(item.model_dump())
        print(f"  - Generated: {name} ({item_id})")

    # Save to items.json
    try:
        # Check if items.json exists to avoid overwriting manually added items?
        # For this task, we overwrite or merge. Let's overwrite for initialization.
        with open(items_path, "w", encoding="utf-8") as f:
            json.dump({"items": generated_items}, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(generated_items)} items to {items_path}")
    except Exception as e:
        print(f"Error saving items for {world_id}: {e}")

def main():
    if not os.path.exists(DATA_DIR):
        print(f"Data directory not found: {DATA_DIR}")
        return

    worlds = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]
    
    print(f"Found {len(worlds)} worlds. Starting extraction...")
    
    for world_id in worlds:
        extract_items_from_bible(world_id)

if __name__ == "__main__":
    main()
