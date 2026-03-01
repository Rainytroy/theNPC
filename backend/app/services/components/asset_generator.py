import os
import json
import re
import hashlib
from typing import Dict, Any, Optional
from ...core.config import settings
from ...core.llm import llm_client
from ...core.utils import parse_json_from_llm
from ...prompts.asset_enricher import ASSET_ENRICHER_PROMPT, QUEST_ENRICHER_PROMPT
from ...schemas.item import Item
from ...schemas.location import Location
from ...schemas.time_config import TimeConfig, TimeChronology

class AssetGenerator:
    def __init__(self):
        pass

    def generate_id(self, prefix: str, index: int) -> str:
        return f"{prefix}_{index:03d}"

    def extract_assets_from_bible(self, world_id: str, bible_data: Dict[str, Any]):
        """
        Extract items, locations, and time config from world bible 
        and save them to respective JSON files.
        """
        print(f"DEBUG: Extracting assets for world {world_id}")
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        
        if not os.path.exists(world_dir):
            print(f"Error: World directory not found for {world_id}")
            return

        # 🔧 FIX: 修正typo - 应该从 bible_data 获取 scene
        scene_data = bible_data.get("scene", {})
        
        print(f"DEBUG: scene_data keys: {scene_data.keys() if scene_data else 'None'}")
        print(f"DEBUG: bible_data keys: {bible_data.keys() if isinstance(bible_data, dict) else type(bible_data)}")
        
        # --- 1. Extract Items ---
        key_objects = scene_data.get("key_objects", [])
        generated_items = []
        
        for idx, obj_str in enumerate(key_objects, 1):
            # Parse "Name(Description)" format
            match = re.match(r"^(.*?)[（\(](.*?)[）\)]$", obj_str)
            if match:
                name = match.group(1).strip()
                desc = match.group(2).strip()
            else:
                name = obj_str
                desc = "从世界设定中发现的关键物品。"

            item_id = self.generate_id("item", idx)
            # Create basic item schema
            item = {
                "id": item_id,
                "name": name,
                "description": desc,
                "type": "key",
                "obtain_methods": [{"method": "find", "source": "World Bible"}]
            }
            generated_items.append(item)

        items_path = os.path.join(world_dir, "items.json")
        try:
            with open(items_path, "w", encoding="utf-8") as f:
                json.dump({"items": generated_items}, f, indent=2, ensure_ascii=False)
            print(f"[{world_id}] Saved {len(generated_items)} items.")
        except Exception as e:
            print(f"Error saving items: {e}")

        # --- 2. Extract Locations ---
        locations_list = scene_data.get("locations", [])
        generated_locations = []
        
        for idx, loc_str in enumerate(locations_list, 1):
            # Parse "Name(Description)" format
            match = re.match(r"^(.*?)[（\(](.*?)[）\)]$", loc_str)
            if match:
                name = match.group(1).strip()
                desc = match.group(2).strip()
            else:
                name = loc_str
                desc = "世界设定中的地点。"

            loc_id = self.generate_id("loc", idx)
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
            print(f"[{world_id}] Saved {len(generated_locations)} locations.")
        except Exception as e:
            print(f"Error saving locations: {e}")

        # --- 3. Extract Time ---
        bible_time = bible_data.get("time_config", {})
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
                print(f"[{world_id}] Saved time config.")
            except Exception as e:
                print(f"Error saving time: {e}")

    async def enrich_assets_with_llm(self, world_id: str, bible_data: Dict[str, Any], provider: Optional[str] = None):
        """
        使用LLM优化items和locations的描述，使其更符合世界观设定。
        
        这个方法会：
        1. 读取当前的items.json和locations.json
        2. 调用LLM根据world bible生成更好的描述
        3. 更新描述并保存回文件
        """
        print(f"DEBUG: 开始使用LLM优化assets描述 for world {world_id}")
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        
        if not os.path.exists(world_dir):
            print(f"Error: World directory not found for {world_id}")
            return
        
        items_path = os.path.join(world_dir, "items.json")
        locations_path = os.path.join(world_dir, "locations.json")
        
        # 1. 读取当前的items和locations
        current_items = []
        current_locations = []
        
        try:
            if os.path.exists(items_path):
                with open(items_path, "r", encoding="utf-8") as f:
                    items_data = json.load(f)
                    current_items = items_data.get("items", [])
            
            if os.path.exists(locations_path):
                with open(locations_path, "r", encoding="utf-8") as f:
                    locations_data = json.load(f)
                    current_locations = locations_data.get("locations", [])
            
            print(f"DEBUG: 读取到 {len(current_items)} items 和 {len(current_locations)} locations")
            
        except Exception as e:
            print(f"Error reading assets: {e}")
            return
        
        # 如果没有assets，则跳过
        if not current_items and not current_locations:
            print(f"DEBUG: 没有需要优化的assets，跳过LLM优化步骤")
            return
        
        # 2. 准备输入数据给LLM
        bible_json = json.dumps(bible_data, ensure_ascii=False, indent=2)
        
        # 简化items和locations数据（只保留需要优化的字段）
        simplified_items = []
        for item in current_items:
            simplified_items.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description"),
                "type": item.get("type", "key")
            })
        
        simplified_locations = []
        for loc in current_locations:
            simplified_locations.append({
                "id": loc.get("id"),
                "name": loc.get("name"),
                "description": loc.get("description"),
                "type": loc.get("type", "area")
            })
        
        items_json = json.dumps(simplified_items, ensure_ascii=False, indent=2)
        locations_json = json.dumps(simplified_locations, ensure_ascii=False, indent=2)
        
        user_prompt = f"""
**World Bible**:
{bible_json}

**Current Items** (需要优化描述):
{items_json}

**Current Locations** (需要优化描述):
{locations_json}
"""
        
        # 3. 调用LLM
        try:
            print(f"DEBUG: 调用LLM优化描述...")
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": user_prompt}],
                system=ASSET_ENRICHER_PROMPT,
                provider=provider,
                timeout=120.0
            )
            
            # 4. 解析LLM返回的结果
            enriched_data = parse_json_from_llm(response)
            
            if not enriched_data:
                print(f"Warning: LLM未返回有效的JSON，跳过优化")
                return
            
            enriched_items = enriched_data.get("items", [])
            enriched_locations = enriched_data.get("locations", [])
            
            print(f"DEBUG: LLM返回 {len(enriched_items)} items 和 {len(enriched_locations)} locations")
            
            # 5. 更新描述（保持原有的其他字段）
            if enriched_items:
                # 创建ID到优化描述的映射
                item_desc_map = {item.get("id"): item.get("description") for item in enriched_items if item.get("id")}
                
                # 更新current_items的描述
                for item in current_items:
                    item_id = item.get("id")
                    if item_id in item_desc_map and item_desc_map[item_id]:
                        item["description"] = item_desc_map[item_id]
                        print(f"  ✓ 更新 item: {item.get('name')}")
                
                # 保存items.json
                with open(items_path, "w", encoding="utf-8") as f:
                    json.dump({"items": current_items}, f, indent=2, ensure_ascii=False)
                print(f"[{world_id}] ✓ Items描述已优化并保存")
            
            if enriched_locations:
                # 创建ID到优化描述的映射
                loc_desc_map = {loc.get("id"): loc.get("description") for loc in enriched_locations if loc.get("id")}
                
                # 更新current_locations的描述
                for loc in current_locations:
                    loc_id = loc.get("id")
                    if loc_id in loc_desc_map and loc_desc_map[loc_id]:
                        loc["description"] = loc_desc_map[loc_id]
                        print(f"  ✓ 更新 location: {loc.get('name')}")
                
                # 保存locations.json
                with open(locations_path, "w", encoding="utf-8") as f:
                    json.dump({"locations": current_locations}, f, indent=2, ensure_ascii=False)
                print(f"[{world_id}] ✓ Locations描述已优化并保存")
            
        except Exception as e:
            print(f"Error during LLM enrichment: {e}")
            print(f"继续执行任务生成流程...")

    async def enrich_quests_with_llm(self, world_id: str, bible_data: Dict[str, Any], provider: Optional[str] = None):
        """
        使用LLM为Quest Nodes生成剧情资产（对话脚本、调查描述）。
        
        新策略（类似Schedule生成）：
        1. 逐个Quest处理，避免node ID冲突
        2. 每次LLM调用注入全局Quest上下文，保持剧情连贯性
        3. 每个Quest的enrichment保存到单独文件
        4. 最后合并所有enrichments到quests.json
        """
        print(f"DEBUG: 开始为World {world_id} 填充Quest剧情资产...")
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        quests_path = os.path.join(world_dir, "quests.json")
        skeleton_path = os.path.join(world_dir, "quests_skeleton.json")
        enrichments_dir = os.path.join(world_dir, "quest_enrichments")
        old_enrichments_file = os.path.join(world_dir, "quest_enrichments.json")

        if not os.path.exists(quests_path) and not os.path.exists(skeleton_path):
            print(f"Warning: No quests data found for world {world_id}")
            return
        
        # 🔧 清理上一次的生成数据（重新生成前清除旧数据）
        import shutil
        
        if os.path.exists(enrichments_dir):
            print(f"DEBUG: Cleaning previous quest enrichments directory...")
            shutil.rmtree(enrichments_dir)
        
        if os.path.exists(old_enrichments_file):
            print(f"DEBUG: Removing old quest enrichments file...")
            os.remove(old_enrichments_file)

        try:
            # 1. Load Skeleton
            if os.path.exists(skeleton_path):
                print("DEBUG: Loading from Skeleton (quests_skeleton.json)...")
                with open(skeleton_path, "r", encoding="utf-8") as f:
                    raw_skeleton = json.load(f)
                
                # 兼容 list 和 dict 两种格式
                if isinstance(raw_skeleton, list):
                    print("DEBUG: Converting skeleton from list to dict format...")
                    skeleton_data = {"quests": raw_skeleton}
                    with open(skeleton_path, "w", encoding="utf-8") as f:
                        json.dump(skeleton_data, f, indent=2, ensure_ascii=False)
                elif isinstance(raw_skeleton, dict):
                    skeleton_data = raw_skeleton
                else:
                    print(f"ERROR: Invalid skeleton format: {type(raw_skeleton)}")
                    return
            else:
                print("DEBUG: Creating Skeleton from current quests...")
                with open(quests_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                
                if isinstance(raw_data, list):
                    skeleton_data = {"quests": raw_data}
                else:
                    skeleton_data = raw_data
                    
                with open(skeleton_path, "w", encoding="utf-8") as f:
                    json.dump(skeleton_data, f, indent=2, ensure_ascii=False)
            
            quests_list = skeleton_data.get("quests", [])

            if not quests_list:
                print("DEBUG: No quests to enrich.")
                return

            # 2. 准备全局上下文（所有Quest的概览）
            quest_summaries = []
            for quest in quests_list:
                quest_summaries.append({
                    "id": quest.get("id"),
                    "title": quest.get("title"),
                    "type": quest.get("type"),
                    "description": quest.get("description"),
                    "node_count": len(quest.get("nodes", []))
                })
            
            global_context = f"""
[全局Quest概览 - 供参考，了解整体剧情结构]
{json.dumps(quest_summaries, ensure_ascii=False, indent=2)}

[World Bible]
{json.dumps(bible_data, ensure_ascii=False, indent=2)}
"""
            
            # 3. 创建enrichments目录
            os.makedirs(enrichments_dir, exist_ok=True)
            
            # 4. 逐个Quest处理（类似Schedule生成）
            from .world_status_manager import WorldStatusManager
            status_mgr = WorldStatusManager()
            
            total_quests = len(quests_list)
            
            for idx, quest in enumerate(quests_list, 1):
                quest_id = quest.get("id")
                quest_nodes = quest.get("nodes", [])
                
                if not quest_nodes:
                    print(f"DEBUG: Quest {quest_id} has no nodes, skipping...")
                    continue
                
                print(f"DEBUG: [{idx}/{total_quests}] Enriching Quest: {quest_id} ({len(quest_nodes)} nodes)")
                
                # 更新进度
                quest_title = quest.get("title", quest_id)
                status_mgr.update_status_progress(world_id, "quest_enrich", {
                    "status": "processing",
                    "current": idx,
                    "total": total_quests,
                    "message": f"Enriching storyline for \"{quest_title}\" ({idx}/{total_quests})..."
                })
                
                # 准备当前Quest的nodes数据
                simplified_nodes = []
                for node in quest_nodes:
                    simplified_nodes.append({
                        "id": node.get("id"),
                        "type": node.get("type"),
                        "description": node.get("description"),
                        "target": node.get("target"),
                        "next_step": node.get("next_step")
                    })
                
                # 构造提示词（全局上下文 + 当前Quest）
                user_prompt = f"""
{global_context}

════════════════════════════════════════
[当前处理的Quest]
Quest ID: {quest_id}
Quest Title: {quest.get("title")}
Quest Type: {quest.get("type")}

[待生成剧情的Nodes]
{json.dumps(simplified_nodes, ensure_ascii=False, indent=2)}
════════════════════════════════════════

请为当前Quest的每个node生成剧情内容。注意：每个Quest内部node ID（如n1,n2）是独立命名空间，无需担心与其他Quest冲突。
"""
                
                # 调用LLM
                try:
                    response = await llm_client.chat_completion(
                        messages=[{"role": "user", "content": user_prompt}],
                        system=QUEST_ENRICHER_PROMPT,
                        provider=provider,
                        timeout=180.0
                    )
                    
                    # 解析结果
                    enrichment_data = parse_json_from_llm(response)
                    
                    if not enrichment_data:
                        print(f"Warning: LLM returned invalid JSON for {quest_id}")
                        continue
                    
                    # 保存到单独文件
                    enrichment_file = os.path.join(enrichments_dir, f"{quest_id}.json")
                    with open(enrichment_file, "w", encoding="utf-8") as f:
                        json.dump(enrichment_data, f, indent=2, ensure_ascii=False)
                    
                    print(f"DEBUG: ✓ Saved enrichment for {quest_id} ({len(enrichment_data)} nodes)")
                    
                except Exception as e:
                    print(f"Error enriching {quest_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # 5. 合并所有enrichments到quests.json
            print(f"DEBUG: Merging all enrichments into quests.json...")
            
            total_updated = 0
            for quest in quests_list:
                quest_id = quest.get("id")
                enrichment_file = os.path.join(enrichments_dir, f"{quest_id}.json")
                
                if os.path.exists(enrichment_file):
                    with open(enrichment_file, "r", encoding="utf-8") as f:
                        enrichment_data = json.load(f)
                    
                    # 更新quest的nodes
                    for node in quest.get("nodes", []):
                        node_id = node.get("id")
                        if node_id and node_id in enrichment_data:
                            content = enrichment_data[node_id]
                            if "investigation_desc" in content:
                                node["investigation_desc"] = content["investigation_desc"]
                            if "dialogue_script" in content:
                                node["dialogue_script"] = content["dialogue_script"]
                            total_updated += 1
            
            # 保存最终quests.json
            if total_updated > 0:
                with open(quests_path, "w", encoding="utf-8") as f:
                    json.dump({"quests": quests_list}, f, indent=2, ensure_ascii=False)
                print(f"[{world_id}] ✓ 成功填充了 {total_updated} 个任务节点的剧情资产")
            
            # 更新最终状态
            status_mgr.update_status_progress(world_id, "quest_enrich", {
                "status": "completed",
                "current": total_quests,
                "total": total_quests,
                "message": f"All {total_quests} quests enriched successfully."
            })

        except Exception as e:
            print(f"Error enriching quests: {e}")
            import traceback
            traceback.print_exc()

    async def generate_intro(self, world_id: str, bible_data: Dict[str, Any], provider: Optional[str] = None) -> str:
        """
        Generate the opening crawl/intro text for the game.
        """
        print(f"DEBUG: Generating intro for world {world_id}...")
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        
        # Try to load existing intro first
        intro_path = os.path.join(world_dir, "intro.txt")
        if os.path.exists(intro_path):
             with open(intro_path, "r", encoding="utf-8") as f:
                 return f.read()

        bible_json = json.dumps(bible_data, ensure_ascii=False, indent=2)
        
        prompt = f"""
You are the narrator of a game. Based on the World Bible below, write a captivating opening introduction for the player.
- Language: Simplified Chinese (简体中文).
- Format: Start with a bolded title (e.g. **序章：觉醒**).
- Style: Star Wars opening crawl / RPG Intro.
- Content: Set the scene, the atmosphere, and the current tension. 
- Hint: Give a vague hint about what the player might do first. **IMPORTANT: You MUST wrap the specific location name or destination in markdown bold syntax (e.g. **酒馆** or **中央广场**) to highlight where the player should go.**
- Length: 100-200 words.

**World Bible**:
{bible_json}

Output ONLY the text of the introduction.
"""
        try:
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system="You are a game narrator.",
                provider=provider,
                timeout=60.0
            )
            
            intro_text = response.strip()
            
            # Save to disk
            with open(intro_path, "w", encoding="utf-8") as f:
                f.write(intro_text)
                
            print(f"[{world_id}] ✓ Intro generated.")
            return intro_text
            
        except Exception as e:
            print(f"Error generating intro: {e}")
            return "Welcome to the world. Your journey begins now."
