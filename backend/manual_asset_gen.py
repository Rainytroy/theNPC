import os
import json
import re
import hashlib

# Configuration
WORLD_ID = "952d8435-aa2a-45b9-a692-504dadcade43"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "worlds")

def generate_id(prefix: str, content: str) -> str:
    hash_object = hashlib.md5(content.encode("utf-8"))
    return f"{prefix}_{hash_object.hexdigest()[:8]}"

def extract_assets_from_bible(world_id: str):
    world_dir = os.path.join(DATA_DIR, world_id)
    bible_path = os.path.join(world_dir, "bible.json")
    
    print(f"Target World Dir: {world_dir}")
    
    if not os.path.exists(bible_path):
        print(f"Skipping {world_id}: bible.json not found.")
        return

    try:
        with open(bible_path, "r", encoding="utf-8") as f:
            bible = json.load(f)
    except Exception as e:
        print(f"Error reading bible for {world_id}: {e}")
        return

    scene_data = bible.get("scene", {})
    
    # --- 1. Extract Items ---
    key_objects = scene_data.get("key_objects", [])
    generated_items = []
    
    print(f"Found {len(key_objects)} key objects.")
    
    for obj_str in key_objects:
        # Parse "Name(Description)" format
        match = re.match(r"^(.*?)[（\(](.*?)[）\)]$", obj_str)
        if match:
            name = match.group(1).strip()
            desc = match.group(2).strip()
        else:
            name = obj_str
            desc = "从世界设定中发现的关键物品。"

        item_id = generate_id("item", name)
        item = {
            "id": item_id,
            "name": name,
            "description": desc,
            "type": "key",
            "obtain_methods": [{"method": "find", "source": "World Scene"}]
        }
        generated_items.append(item)

    items_path = os.path.join(world_dir, "items.json")
    try:
        with open(items_path, "w", encoding="utf-8") as f:
            json.dump({"items": generated_items}, f, indent=2, ensure_ascii=False)
        print(f"[{world_id}] Saved {len(generated_items)} items to {items_path}")
    except Exception as e:
        print(f"Error saving items: {e}")

    # --- 2. Extract Locations ---
    locations_list = scene_data.get("locations", [])
    generated_locations = []
    
    print(f"Found {len(locations_list)} locations.")
    
    for loc_str in locations_list:
        # Parse "Name(Description)" format
        match = re.match(r"^(.*?)[（\(](.*?)[）\)]$", loc_str)
        if match:
            name = match.group(1).strip()
            desc = match.group(2).strip()
        else:
            name = loc_str
            desc = "世界设定中的地点。"

        loc_id = generate_id("loc", name)
        # Simple type inference
        loc_type = "building" if "客栈" in name or "镖局" in name or "楼" in name or "铺" in name else "area"

        location = {
            "id": loc_id,
            "name": name,
            "description": desc,
            "type": loc_type
        }
        generated_locations.append(location)

    locations_path = os.path.join(world_dir, "locations.json")
    try:
        with open(locations_path, "w", encoding="utf-8") as f:
            json.dump({"locations": generated_locations}, f, indent=2, ensure_ascii=False)
        print(f"[{world_id}] Saved {len(generated_locations)} locations to {locations_path}")
    except Exception as e:
        print(f"Error saving locations: {e}")

    # --- 3. Extract Time ---
    bible_time = bible.get("time_config", {})
    if bible_time:
        start_datetime = bible_time.get("start_datetime", "2024-01-01 08:00")
        display_year = bible_time.get("display_year", "")
        
        time_config = {
            "start_datetime": start_datetime,
            "display_year": display_year,
            "chronology": {
                "display_rule": display_year.replace("十年", "{year}年") if "十年" in display_year else display_year,
                "current_year": 1
            }
        }
        
        time_path = os.path.join(world_dir, "time.json")
        try:
            with open(time_path, "w", encoding="utf-8") as f:
                json.dump(time_config, f, indent=2, ensure_ascii=False)
            print(f"[{world_id}] Saved time config to {time_path}")
        except Exception as e:
            print(f"Error saving time: {e}")

if __name__ == "__main__":
    extract_assets_from_bible(WORLD_ID)
