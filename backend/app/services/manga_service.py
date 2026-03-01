import asyncio
import json
import os
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime
from ..core.config import settings
from ..core.llm import llm_client
from .image_service import image_service
# from ..prompts.manga import MANGA_DIRECTOR_PROMPT

MANGA_DIRECTOR_PROMPT_V2 = """
You are a Manga Director and Storyboard Artist.
Your task is to adapt a sequence of world events into a single, high-quality manga page description.

### Input
1. **World Events**: A chronological list of events that happened in the world.
2. **Characters**: A list of key characters involved in these events (Names and basic descriptions).

### Output Format
You must output a JSON object with the following structure:
{{
    "plot_description": "A detailed string describing the manga page...",
    "characters_in_frame": ["Name1", "Name2"]
}}

### Requirements for 'plot_description'
1.  **Language**: The description MUST be in **Simplified Chinese (简体中文)**.
2.  **Structure**:
    *   Start with: "日式漫画页，绝对黑白，水墨风格。竖向构图，比例2:3。"
    *   Describe the **Layout**: "页面布局使用带有白色间隙的分镜，包含斜向/不规则切割。"
    *   **Panels (分镜)**: Break the events into 3-5 distinct panels. Number them (e.g., 分镜1, 分镜2...).
        *   Specify size/shape (e.g., 顶部宽幅, 中部不规则, 底部大幅).
        *   Describe the action, character expressions, and dialogue (in speech bubbles).
        *   **Crucial**: You MUST explicitly map the characters to their position or role if they appear (e.g., "左=小阮", "中=陈师傅"). However, since we are generating from events, you might not know the exact "Left/Middle/Right" of the *reference image* unless I provide it. 
        *   **Constraint**: The reference image provided to the drawing AI contains specific characters. You must assign roles to them based on the events. 
        *   If the events involve characters NOT in the reference image, try to focus on the ones who ARE, or describe the others generically.
3.  **Style**: Emphasize dramatic angles, speed lines, and emotional reactions.

### Reference Characters (The Image AI will use these faces)
The reference image contains specific characters in fixed positions (e.g., Left, Middle, Right). 
(Note: The actual mapping will be handled by the caller, but you should describe characters clearly so the image generator knows who is doing what).

### Events to Adapt
{events_text}

### Character Profiles
{npc_profiles}

Now, create the manga page description.
"""

# Configure Debug Logging
logger = logging.getLogger("manga_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("manga_debug.log", encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

class MangaService:
    def __init__(self):
        self._running_tasks: Dict[str, bool] = {} # world_id -> is_running
        self._background_tasks: Dict[str, asyncio.Task] = {}

    def is_running(self, world_id: str) -> bool:
        return self._running_tasks.get(world_id, False)

    async def start_generation(self, world_id: str):
        logger.info(f"Request to start generation for {world_id}")
        # 1. Check Config (is_illustrated)
        bible = self._load_world_bible(world_id)
        config = bible.get("config", {})
        if not config.get("is_illustrated", False):
            logger.info(f"Manga Generation Skipped for World {world_id}: 'is_illustrated' is disabled.")
            return

        if self.is_running(world_id):
            logger.info(f"Manga generation already running for {world_id}")
            return
        
        logger.info(f"Starting Manga Generation for World {world_id}")
        self._running_tasks[world_id] = True
        
        # Start background task
        task = asyncio.create_task(self._generation_loop(world_id))
        self._background_tasks[world_id] = task

    async def stop_generation(self, world_id: str):
        logger.info(f"Request to stop generation for {world_id}")
        if not self.is_running(world_id):
            return
            
        logger.info(f"Stopping Manga Generation for World {world_id}")
        self._running_tasks[world_id] = False
        # Task will exit on next loop check

    async def get_pages(self, world_id: str) -> List[dict]:
        manga_file = self._get_manga_file_path(world_id)
        if not os.path.exists(manga_file):
            return []
        
        try:
            with open(manga_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("pages", [])
        except Exception as e:
            print(f"Error reading manga pages: {e}")
            return []

    async def _generation_loop(self, world_id: str):
        logger.info(f"Manga Generation Loop Started for {world_id}")
        
        while self.is_running(world_id):
            try:
                # 1. Check for new events
                has_new, events_batch = await self._get_unprocessed_events(world_id)
                
                if has_new:
                    logger.info(f"Found {len(events_batch)} new events for manga page...")
                    
                    # 2. Generate Page
                    page_data = await self._generate_single_page(world_id, events_batch)
                    
                    if page_data:
                        # 3. Save Page and Update Cursor
                        await self._save_page(world_id, page_data, events_batch[-1]["timestamp"])
                        logger.info(f"Manga Page Generated: {page_data['id']}")
                    else:
                        logger.error("Failed to generate manga page")
                        
                    # Wait a bit after generation
                    await asyncio.sleep(5) 
                else:
                    # No new events, wait longer
                    # logger.info("No new events, waiting...") 
                    await asyncio.sleep(10)
                    
            except Exception as e:
                logger.error(f"Error in Manga Loop: {e}", exc_info=True)
                await asyncio.sleep(10) # Error backoff

        logger.info(f"Manga Generation Loop Stopped for {world_id}")

    async def _get_unprocessed_events(self, world_id: str) -> (bool, List[dict]):
        """
        Check events.jsonl and return next batch after cursor.
        """
        manga_data = self._load_manga_data(world_id)
        last_ts = manga_data.get("last_processed_timestamp", 0)
        
        # Load config for dynamic batch size
        bible = self._load_world_bible(world_id)
        config = bible.get("config", {})
        target_size = config.get("manga_page_size", 10)
        
        events_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "events.jsonl")
        if not os.path.exists(events_path):
            return False, []
            
        new_events = []
        
        try:
            with open(events_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        evt = json.loads(line)
                        if evt.get("timestamp", 0) > last_ts:
                            new_events.append(evt)
                    except:
                        continue
        except Exception as e:
            print(f"Error reading events: {e}")
            return False, []
            
        # Strategy:
        # Wait until we have enough events based on config
        if len(new_events) >= target_size:
            return True, new_events[:target_size]
            
        return False, []

    async def _generate_single_page(self, world_id: str, events: List[dict]) -> Optional[dict]:
        logger.info("Starting _generate_single_page")
        # 1. Prepare Context
        npcs = self._load_npcs(world_id)
        
        npc_profiles = "\n".join([
            f"- Name: {n['profile']['name']}, Desc: {n['profile']['avatar_desc']}, Role: {n['profile']['occupation']}" 
            for n in npcs
        ])
        
        events_text = "\n".join([
            f"[{datetime.fromtimestamp(e['timestamp']/1000).strftime('%H:%M')}] {e['content']}" 
            for e in events
        ])
        
        # 2. Director (LLM) - Plan the page
        logger.info(f"Using Fixed Prompt Template V2. Length: {len(MANGA_DIRECTOR_PROMPT_V2)}")
        prompt = MANGA_DIRECTOR_PROMPT_V2.format(
            events_text=events_text,
            npc_profiles=npc_profiles
        )
        
        try:
            logger.info("Calling LLM for director prompt...")
            response = await llm_client.generate_json(prompt)
            if not response or "plot_description" not in response:
                logger.error(f"LLM failed to generate plot description. Response: {response}")
                return None
            
            plot_description = response["plot_description"]
            characters_in_frame = response.get("characters_in_frame", [])
            logger.info(f"Manga Plot Generated: {plot_description[:50]}...")
            
            # 3. Illustrator (Image Service) - Stitch References
            # Collect avatar URLs for characters in frame
            target_npc_urls = []
            for char_name in characters_in_frame:
                # Find NPC by name (fuzzy match or contains)
                npc = next((n for n in npcs if n['profile']['name'] in char_name), None)
                if npc and npc['profile'].get('avatar_url'):
                    target_npc_urls.append(npc['profile']['avatar_url'])
            
            logger.info(f"Identified characters: {characters_in_frame}, URLs found: {len(target_npc_urls)}")

            # Fallback: if list is empty, use the first NPC in the world list as a placeholder (or skipping reference).
            if not target_npc_urls and npcs:
                 logger.info("No character match found, using first NPC as fallback reference.")
                 target_npc_urls.append(npcs[0]['profile']['avatar_url'])

            # Stitch images (with caching)
            logger.info("Combining reference images...")
            ref_image_url = await image_service.combine_reference_images(world_id, target_npc_urls)
            
            if not ref_image_url:
                logger.error("Failed to prepare reference image")
                return None
            
            logger.info(f"Reference image ready: {ref_image_url}")

            # 4. Construct Final Prompt
            final_prompt = (
                f"{plot_description}, "
                "vertical composition, aspect ratio 2:3, "
                "multi-panel layout, dynamic panel composition, varying panel sizes, irregular panel borders, diagonal cuts, white gutters between panels, "
                "character breaking the panel borders, intense speed lines, focus lines, dramatic shading, "
                "absolute black and white, monochrome, ink drawing, screentones, manga style, speech bubbles, japanese sound effects text, "
                "high contrast, detailed line art, masterpiece, high quality"
            )
            
            # 5. Generate
            logger.info("Calling Image Service to generate manga page...")
            image_url = await image_service.generate_manga_page(final_prompt, ref_image_url, world_id)
            
            if image_url:
                logger.info(f"Manga page generated successfully: {image_url}")
                return {
                    "id": f"page_{int(time.time())}",
                    "timestamp": int(time.time() * 1000),
                    "image_url": image_url,
                    "plot": plot_description,
                    "events_range": {
                        "start": events[0]["timestamp"],
                        "end": events[-1]["timestamp"]
                    }
                }
            logger.error("Image Service returned None for image_url")
            return None
            
        except Exception as e:
            logger.error(f"Error generating single page: {e}", exc_info=True)
            return None

    def _load_manga_data(self, world_id: str) -> dict:
        path = self._get_manga_file_path(world_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"last_processed_timestamp": 0, "pages": []}

    async def get_progress(self, world_id: str) -> dict:
        # Count total events
        total_events = 0
        events_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "events.jsonl")
        if os.path.exists(events_path):
            try:
                with open(events_path, "r", encoding="utf-8") as f:
                    for _ in f: total_events += 1
            except: pass
                
        # Count processed
        manga_data = self._load_manga_data(world_id)
        last_ts = manga_data.get("last_processed_timestamp", 0)
        
        processed_events = 0
        if os.path.exists(events_path):
            try:
                with open(events_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            if json.loads(line).get("timestamp", 0) <= last_ts:
                                processed_events += 1
                        except: pass
            except: pass

        return {
            "total_events": total_events,
            "processed_events": processed_events,
            "queue_size": max(0, total_events - processed_events),
            "pages_generated": len(manga_data.get("pages", [])),
            "is_running": self.is_running(world_id)
        }

    async def regenerate_page(self, world_id: str, page_id: str) -> Optional[dict]:
        manga_data = self._load_manga_data(world_id)
        pages = manga_data.get("pages", [])
        
        target_page = next((p for p in pages if p["id"] == page_id), None)
        if not target_page:
            return None
            
        # Get events
        start_ts = target_page["events_range"]["start"]
        end_ts = target_page["events_range"]["end"]
        
        events = []
        events_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "events.jsonl")
        if os.path.exists(events_path):
            try:
                with open(events_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            evt = json.loads(line)
                            ts = evt.get("timestamp", 0)
                            if start_ts <= ts <= end_ts:
                                events.append(evt)
                        except: pass
            except: pass
        
        if not events:
            return None
            
        # Generate
        logger.info(f"Regenerating page {page_id} with {len(events)} events")
        new_page = await self._generate_single_page(world_id, events)
        if new_page:
            new_page["id"] = page_id # Keep ID
            # Update in list
            for i, p in enumerate(pages):
                if p["id"] == page_id:
                    pages[i] = new_page
                    break
            manga_data["pages"] = pages
            
            # Save
            path = self._get_manga_file_path(world_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(manga_data, f, ensure_ascii=False, indent=2)
                
            return new_page
        return None

    async def _save_page(self, world_id: str, page_data: dict, last_ts: int):
        path = self._get_manga_file_path(world_id)
        data = self._load_manga_data(world_id)
        
        data["pages"].append(page_data)
        data["last_processed_timestamp"] = last_ts
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_npcs(self, world_id: str) -> List[dict]:
        path = os.path.join(settings.DATA_DIR, "worlds", world_id, "npcs.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def _load_world_bible(self, world_id: str) -> dict:
        path = os.path.join(settings.DATA_DIR, "worlds", world_id, "bible.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _get_manga_file_path(self, world_id: str) -> str:
        return os.path.join(settings.DATA_DIR, "worlds", world_id, "manga.json")

manga_service = MangaService()
