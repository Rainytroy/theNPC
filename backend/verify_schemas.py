from app.schemas.item import Item
from app.schemas.quest import Quest, QuestNode, QuestCondition
import json
import os

def test_schemas():
    print("Testing Item Schema...")
    try:
        item = Item(
            id="test_item",
            name="Test Item",
            description="Desc",
            type="key",
            obtain_methods=[{"method": "find", "source": "Here"}]
        )
        print("  - Item Schema OK")
    except Exception as e:
        print(f"  - Item Schema FAILED: {e}")

    print("Testing Quest Schema...")
    try:
        # Test new condition
        cond = QuestCondition(type="item", params={"item_id": "test_item", "count": 1})
        
        # Test Node with condition
        node = QuestNode(
            id="n1",
            type="collect",
            description="Get the item",
            conditions=[cond],
            status="locked"
        )
        
        # Test Quest
        quest = Quest(
            id="q1",
            title="Test Quest",
            description="Desc",
            nodes=[node]
        )
        print("  - Quest Schema OK")
    except Exception as e:
        print(f"  - Quest Schema FAILED: {e}")

def check_generated_items():
    print("Checking items.json...")
    world_id = "af6c21d8-926f-46a0-97f4-4d1cf73041dc"
    path = f"theNPC/backend/data/worlds/{world_id}/items.json"
    
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data.get("items", [])
            print(f"  - Found {len(items)} items.")
            for i in items:
                try:
                    Item(**i)
                except Exception as e:
                    print(f"  - Item {i.get('name')} validation failed: {e}")
            print("  - All items validated against Schema.")
    else:
        print("  - items.json NOT FOUND")

if __name__ == "__main__":
    test_schemas()
    check_generated_items()
