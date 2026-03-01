from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
import json
import os
import uuid
from typing import Optional
from ..schemas.genesis import (
    GenesisChatRequest, GenesisChatResponse, 
    GenerateWorldRequest, GenerateWorldResponse, 
    WorldBible, WorldBackground, GameScene, TimeConfig,
    GenerateQuestsRequest, GenerateQuestsResponse,
    GenerateMainQuestRequest, GenerateSideQuestRequest,
    WorldCreationStatus, EnrichAssetsRequest, EnrichAssetsResponse
)
from ..schemas.npc import GenerateNPCsRequest, GenerateNPCsResponse, NPC
from ..services.genesis_service import genesis_service
from ..services.image_service import image_service
from ..services.oss_service import oss_service
from ..core.config import settings

router = APIRouter(prefix="/api/genesis", tags=["genesis"])

@router.post("/start")
async def start_genesis():
    """Start a new world creation session"""
    session_id = genesis_service.create_session()
    return {
        "session_id": session_id,
        "message": "你好！欢迎使用透悉全宇宙 theNPC 服务，你想创造一个什么样的世界？"
    }

@router.post("/check_status", response_model=WorldCreationStatus)
async def check_status(request: dict):
    """Check the current status of world creation"""
    # Request body: { "world_id": "..." }
    world_id = request.get("world_id")
    if not world_id:
        raise HTTPException(status_code=400, detail="Missing world_id")
        
    try:
        return await genesis_service.check_world_status(world_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")

@router.post("/save_chat")
async def save_chat_history(request: dict):
    """Save chat history to file"""
    # Request: { "world_id": "...", "messages": [...] }
    world_id = request.get("world_id")
    messages = request.get("messages")
    
    if not world_id or messages is None:
        raise HTTPException(status_code=400, detail="Missing world_id or messages")
        
    try:
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        if not os.path.exists(world_dir):
            raise HTTPException(status_code=404, detail="World not found")
            
        chat_path = os.path.join(world_dir, "chat.json")
        with open(chat_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
            
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save chat: {str(e)}")

@router.post("/chat", response_model=GenesisChatResponse)
async def chat_genesis(
    request: GenesisChatRequest,
    x_model_provider: Optional[str] = Header(None)
):
    """Chat with The Sower to build the world"""
    try:
        response = await genesis_service.chat(
            request.session_id, 
            request.content, 
            provider=x_model_provider,
            current_bible=request.current_bible,
            phase=request.phase or "world"  # ✅ Pass phase parameter
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/confirm_world", response_model=GenerateWorldResponse)
async def confirm_world(request: GenerateWorldRequest):
    """Confirm world settings and save to file"""
    if not request.world_setting:
        raise HTTPException(status_code=400, detail="Missing world_setting data")
    
    try:
        # Check if updating existing world (Draft ID reuse)
        existing_id = request.world_setting.get("world_id")
        if existing_id and os.path.exists(os.path.join(settings.DATA_DIR, "worlds", existing_id)):
            world_id = existing_id
            print(f"DEBUG: Updating existing world {world_id}")
        else:
            world_id = str(uuid.uuid4())
            print(f"DEBUG: Creating new world {world_id}")
        
        # Safe parsing
        title = request.world_setting.get("title")
        bg_data = request.world_setting.get("background", {})
        scene_data = request.world_setting.get("scene", {})
        player_objective = request.world_setting.get("player_objective")
        time_config_data = request.world_setting.get("time_config", {})
        
        world_bible = WorldBible(
            world_id=world_id,
            title=title,
            player_objective=player_objective,
            background=WorldBackground(**bg_data),
            scene=GameScene(**scene_data),
            time_config=TimeConfig(**time_config_data) if time_config_data else TimeConfig()
        )
        
        # Save to file
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        os.makedirs(world_dir, exist_ok=True)
        
        bible_path = os.path.join(world_dir, "bible.json")
        with open(bible_path, "w", encoding="utf-8") as f:
            f.write(world_bible.model_dump_json(indent=2))
            
        # Save Chat History if provided
        if request.chat_history:
            chat_path = os.path.join(world_dir, "chat.json")
            with open(chat_path, "w", encoding="utf-8") as f:
                json.dump(request.chat_history, f, indent=2, ensure_ascii=False)

        # Finalize Phase & Inject Summary/Transition
        # This updates status.json and appends transition messages to chat.json
        await genesis_service.finalize_world_phase(world_id, world_bible)

        return GenerateWorldResponse(
            status="success",
            world_bible=world_bible,
            is_locked=False
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create world: {str(e)}")

@router.post("/generate_npcs", response_model=GenerateNPCsResponse)
async def generate_npcs(
    request: GenerateNPCsRequest,
    x_model_provider: Optional[str] = Header(None)
):
    """Generate NPCs based on the World Bible"""
    print(f"DEBUG: Received generate_npcs request. Count: {request.count}, Provider: {x_model_provider}")
    
    # CHECK WORLD LOCK
    world_id = request.world_bible.get("world_id")
    if world_id:
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        if os.path.exists(world_dir):
            # Lock Conditions: schedules.json OR events.jsonl OR archives/
            is_locked = False
            if os.path.exists(os.path.join(world_dir, "schedules.json")): is_locked = True
            if os.path.exists(os.path.join(world_dir, "events.jsonl")): is_locked = True
            
            archives_dir = os.path.join(world_dir, "archives")
            if os.path.exists(archives_dir) and os.listdir(archives_dir): is_locked = True
            
            if is_locked:
                raise HTTPException(status_code=400, detail="World is initialized and locked. Cannot regenerate NPCs.")

    try:
        npcs = await genesis_service.generate_npcs(
            request.world_bible, 
            request.count, 
            provider=x_model_provider,
            requirements=request.requirements
        )
        
        # Save to file if world_id exists in the bible
        if world_id:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            if os.path.exists(world_dir):
                # Save NPCs
                npc_path = os.path.join(world_dir, "npcs.json")
                with open(npc_path, "w", encoding="utf-8") as f:
                    # Convert list of Pydantic models to list of dicts
                    f.write(json.dumps([npc.model_dump() for npc in npcs], indent=2, ensure_ascii=False))
                
                # ✅ NEW: Save updated world_bible (with merged locations from Shaper)
                bible_path = os.path.join(world_dir, "bible.json")
                with open(bible_path, "w", encoding="utf-8") as f:
                    json.dump(request.world_bible, f, indent=2, ensure_ascii=False)
                print(f"DEBUG: Saved updated bible.json with {len(request.world_bible.get('scene', {}).get('locations', []))} locations")
        
        return GenerateNPCsResponse(npcs=npcs)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate NPCs: {str(e)}")

@router.post("/generate_roster")
async def generate_roster(
    request: GenerateNPCsRequest,
    x_model_provider: Optional[str] = Header(None)
):
    """Phase 1: Generate NPC Roster and World Map"""
    try:
        result = await genesis_service.generate_roster(
            request.world_bible, 
            request.count, 
            provider=x_model_provider,
            requirements=request.requirements
        )
        
        # Save Skeletons to file (Incremental Save)
        world_id = request.world_bible.get("world_id")
        if world_id and result.get("skeletons"):
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            if os.path.exists(world_dir):
                npc_path = os.path.join(world_dir, "npcs.json")
                # Convert dicts to NPC models to ensure valid schema before saving
                # Note: Skeletons might miss some fields, but NPC model has defaults.
                # If validation fails, we might need to handle it, but Shaper should be consistent.
                from ..schemas.npc import NPC
                npc_models = []
                for sk in result["skeletons"]:
                    try:
                        # Ensure dynamic exists
                        if "dynamic" not in sk and "dynamic_core" in sk:
                             sk["dynamic"] = sk["dynamic_core"]
                        npc_models.append(NPC(**sk).model_dump())
                    except Exception as e:
                        print(f"Warning: Skeleton validation failed: {e}")
                        npc_models.append(sk) # Fallback to raw dict

                with open(npc_path, "w", encoding="utf-8") as f:
                    json.dump(npc_models, f, indent=2, ensure_ascii=False)
                
                # Update Status Count
                genesis_service.update_status_progress(
                    world_id=world_id,
                    section="npc_roster",
                    updates={"count": len(npc_models), "status": "drafting"}
                )

                # Update Bible Locations (Persist new locations)
                bible_path = os.path.join(world_dir, "bible.json")
                if os.path.exists(bible_path):
                    try:
                        with open(bible_path, "r", encoding="utf-8") as f:
                            bible_data = json.load(f)
                        
                        current_locs = bible_data.get("scene", {}).get("locations", [])
                        new_locs = result.get("new_locations", [])
                        
                        updated = False
                        for loc in new_locs:
                            if loc not in current_locs:
                                current_locs.append(loc)
                                updated = True
                        
                        if updated:
                            bible_data["scene"]["locations"] = current_locs
                            with open(bible_path, "w", encoding="utf-8") as f:
                                json.dump(bible_data, f, indent=2, ensure_ascii=False)
                            print(f"DEBUG: Updated bible locations with {len(new_locs)} new locations.")
                            
                    except Exception as e:
                        print(f"Error updating bible locations: {e}")

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate roster: {str(e)}")

@router.post("/generate_npc_details")
async def generate_npc_details(
    request: dict,
    x_model_provider: Optional[str] = Header(None)
):
    """Phase 2: Generate details for a specific NPC"""
    # Request body: { skeleton: {}, world_bible: {}, roster_names: "", requirements: "" }
    try:
        npc_data = await genesis_service.generate_npc_details(
            request["skeleton"], 
            request["world_bible"], 
            request["roster_names"], 
            provider=x_model_provider,
            requirements=request.get("requirements")
        )
        
        # Update NPC in file (Incremental Save)
        world_bible = request.get("world_bible", {})
        world_id = world_bible.get("world_id")
        npc_id = npc_data.get("id")
        
        if world_id and npc_id:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            npc_path = os.path.join(world_dir, "npcs.json")
            if os.path.exists(npc_path):
                try:
                    with open(npc_path, "r", encoding="utf-8") as f:
                        current_npcs = json.load(f)
                    
                    # Find and update
                    updated = False
                    for i, n in enumerate(current_npcs):
                        if n.get("id") == npc_id:
                            current_npcs[i] = npc_data
                            updated = True
                            break
                    
                    # If not found (shouldn't happen if roster ran first), append
                    if not updated:
                        current_npcs.append(npc_data)
                        
                    with open(npc_path, "w", encoding="utf-8") as f:
                        json.dump(current_npcs, f, indent=2, ensure_ascii=False)
                    
                    # Update Status Count
                    genesis_service.update_status_progress(
                        world_id=world_id,
                        section="npc_roster",
                        updates={"count": len(current_npcs)}
                    )
                except Exception as e:
                    print(f"Error updating NPC file: {e}")

        return npc_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate NPC details: {str(e)}")

@router.post("/regenerate_npc/{npc_id}")
async def regenerate_npc(
    npc_id: str,
    request: dict,
    x_model_provider: Optional[str] = Header(None)
):
    """Regenerate a failed/incomplete NPC"""
    # Request body: { world_id: "", requirements: "" }
    try:
        world_id = request.get("world_id")
        if not world_id:
            raise HTTPException(status_code=400, detail="world_id is required")
        
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        
        # Load world bible
        bible_path = os.path.join(world_dir, "bible.json")
        if not os.path.exists(bible_path):
            raise HTTPException(status_code=404, detail="World not found")
        
        with open(bible_path, "r", encoding="utf-8") as f:
            world_bible = json.load(f)
        
        # Load existing NPCs to find the skeleton
        npc_path = os.path.join(world_dir, "npcs.json")
        if not os.path.exists(npc_path):
            raise HTTPException(status_code=404, detail="NPCs file not found")
        
        with open(npc_path, "r", encoding="utf-8") as f:
            npcs = json.load(f)
        
        # Find target NPC
        skeleton = None
        for npc in npcs:
            if npc.get("id") == npc_id:
                skeleton = npc
                break
        
        if not skeleton:
            raise HTTPException(status_code=404, detail=f"NPC {npc_id} not found")
        
        # Prepare roster names
        roster_names = ", ".join([n.get("profile", {}).get("name", "Unknown") for n in npcs])
        
        # Regenerate with retry
        new_npc_data = await genesis_service.generate_npc_details_with_retry(
            skeleton=skeleton,
            world_bible=world_bible,
            roster_names=roster_names,
            provider=x_model_provider,
            requirements=request.get("requirements")
        )
        
        # Update file
        for i, npc in enumerate(npcs):
            if npc.get("id") == npc_id:
                npcs[i] = new_npc_data
                break
        
        with open(npc_path, "w", encoding="utf-8") as f:
            json.dump(npcs, f, indent=2, ensure_ascii=False)
        
        return {"status": "success", "npc": new_npc_data}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to regenerate NPC: {str(e)}")

@router.post("/generate_npc_image", response_model=NPC)
async def generate_npc_image(request: dict):
    """Generate and upload avatar image for an NPC"""
    # Request: { "world_id": "...", "npc_id": "...", "style_prompt": "..." }
    world_id = request.get("world_id")
    npc_id = request.get("npc_id")
    style_prompt = request.get("style_prompt")
    
    if not world_id or not npc_id:
        raise HTTPException(status_code=400, detail="Missing world_id or npc_id")
        
    try:
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        bible_path = os.path.join(world_dir, "bible.json")
        npc_path = os.path.join(world_dir, "npcs.json")
        
        if not os.path.exists(bible_path) or not os.path.exists(npc_path):
            raise HTTPException(status_code=404, detail="World data not found")
            
        # 1. Load Data for Prompt Construction (Read-Only phase)
        with open(bible_path, "r", encoding="utf-8") as f:
            world_bible = json.load(f)
        
        with open(npc_path, "r", encoding="utf-8") as f:
            initial_npcs = json.load(f)
            
        # Find NPC for prompt
        target_npc_data = None
        for npc in initial_npcs:
            if npc.get("id") == npc_id:
                target_npc_data = npc
                break
        
        if not target_npc_data:
            raise HTTPException(status_code=404, detail="NPC not found")
            
        # Construct Prompt
        profile = target_npc_data.get("profile", {})
        # name = profile.get("name", "Unknown") # User requested to remove name
        gender = profile.get("gender", "Unknown")
        age = profile.get("age", "Unknown")
        occupation = profile.get("occupation", "Unknown")
        avatar_desc = profile.get("avatar_desc", "")
        
        bg = world_bible.get("background", {})
        era = bg.get("era", "")
        style = bg.get("society", "") # Use society as style/vibe
        
        # Add Style Prompt (Japanese Manga/Anime Style)
        # Use provided style_prompt or fallback to default
        if style_prompt is not None:
            style_instruction = style_prompt
        else:
            style_instruction = "Japanese manga style, anime art style, vibrant colors, detailed character design, high quality illustration."
        
        # Modified Prompt: Gender, Age, Occupation, Appearance. No Name.
        prompt = f"{style_instruction} Character portrait of a {age} years old {gender} {occupation}. Appearance: {avatar_desc}. Setting: {era}, {style}. Full body, 9:16 aspect ratio."
        
        # 2. Call Image Service (Slow Operation - file might change during this)
        image_url = await image_service.generate_avatar(prompt, world_id, npc_id)
        
        if not image_url:
            raise HTTPException(status_code=500, detail="Failed to generate image")
            
        # 3. Critical Section: Re-Load, Update, Save
        # Re-read file to get latest state (avoid overwriting parallel changes)
        with open(npc_path, "r", encoding="utf-8") as f:
            npcs = json.load(f)
            
        target_npc = None
        target_index = -1
        for i, npc in enumerate(npcs):
            if npc.get("id") == npc_id:
                target_npc = npc
                target_index = i
                break
        
        if target_npc:
            # Update URL
            target_npc["profile"]["avatar_url"] = image_url
            npcs[target_index] = target_npc
            
            # Save to file
            with open(npc_path, "w", encoding="utf-8") as f:
                json.dump(npcs, f, indent=2, ensure_ascii=False)
                
            # Also update RuntimeEngine if active (Double safety)
            from ..core.runtime import RuntimeEngine
            if world_id in RuntimeEngine._instances:
                engine = RuntimeEngine.get_instance(world_id)
                for engine_npc in engine.npcs:
                    if engine_npc.id == npc_id:
                        engine_npc.profile.avatar_url = image_url
                        break

            return target_npc
        else:
             raise HTTPException(status_code=404, detail="NPC not found during save")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating NPC image: {str(e)}")

@router.post("/update_npc_profile", response_model=NPC)
async def update_npc_profile(request: dict):
    """Update NPC profile (e.g. avatar_desc)"""
    # Request: { "world_id": "...", "npc_id": "...", "avatar_desc": "..." }
    world_id = request.get("world_id")
    npc_id = request.get("npc_id")
    avatar_desc = request.get("avatar_desc")
    
    if not world_id or not npc_id:
        raise HTTPException(status_code=400, detail="Missing world_id or npc_id")
        
    try:
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        npc_path = os.path.join(world_dir, "npcs.json")
        
        if not os.path.exists(npc_path):
            raise HTTPException(status_code=404, detail="World data not found")
            
        # Critical Section: Re-Load, Update, Save
        with open(npc_path, "r", encoding="utf-8") as f:
            npcs = json.load(f)
            
        target_npc = None
        target_index = -1
        for i, npc in enumerate(npcs):
            if npc.get("id") == npc_id:
                target_npc = npc
                target_index = i
                break
        
        if target_npc:
            # Update Description
            if avatar_desc is not None:
                target_npc["profile"]["avatar_desc"] = avatar_desc
            
            npcs[target_index] = target_npc
            
            # Save to file
            with open(npc_path, "w", encoding="utf-8") as f:
                json.dump(npcs, f, indent=2, ensure_ascii=False)

            return target_npc
        else:
             raise HTTPException(status_code=404, detail="NPC not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating NPC profile: {str(e)}")

@router.post("/enrich_assets", response_model=EnrichAssetsResponse)
async def enrich_assets(
    request: EnrichAssetsRequest,
    x_model_provider: Optional[str] = Header(None)
):
    """Step 1 & 2: Reset and Enrich Assets"""
    try:
        world_id = request.world_bible.get("world_id")
        if not world_id:
             raise HTTPException(status_code=400, detail="Missing world_id")
             
        items, locations = await genesis_service.enrich_world_assets(
            world_id, request.world_bible, x_model_provider
        )
        return EnrichAssetsResponse(items=items, locations=locations)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enrich assets: {str(e)}")

@router.post("/generate_main_quest", response_model=GenerateQuestsResponse)
async def generate_main_quest(
    request: GenerateMainQuestRequest,
    x_model_provider: Optional[str] = Header(None)
):
    """Phase 3: Generate Main Quest (Optionally skip enrichment)"""
    try:
        # Auto-confirm roster if needed
        world_id = request.world_bible.get("world_id")
        if world_id:
             await genesis_service.handle_roster_confirm(world_id)

        # ✅ STEP 1 & 2: Reset & Enrich Assets (If NOT skipped)
        if world_id and not request.skip_enrichment:
            await genesis_service.enrich_world_assets(
                world_id, request.world_bible, x_model_provider
            )
            
        print(f"DEBUG: [Step 3/3] 开始生成主线任务...")

        # ✅ STEP 3: Generate ONLY Main Quest (for incremental UI update)
        quests = await genesis_service.generate_main_quest(
            request.world_bible, 
            request.npcs, 
            provider=x_model_provider,
            requirements=request.requirements
        )
        
        # Save main quest to file (frontend will call side quest endpoints separately)
        if world_id:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            if os.path.exists(world_dir):
                quest_path = os.path.join(world_dir, "quests.json")
                existing_quests = []
                if os.path.exists(quest_path):
                    with open(quest_path, "r", encoding="utf-8") as f:
                        existing_quests = json.load(f)
                
                # Remove existing main quests and add new one
                existing_quests = [q for q in existing_quests if q.get("type") != "main"]
                existing_quests.extend(quests)
                
                with open(quest_path, "w", encoding="utf-8") as f:
                    json.dump(existing_quests, f, indent=2, ensure_ascii=False)
        
        # ✅ NEW: Read optimized assets after LLM enrichment to return to frontend
        optimized_items = []
        optimized_locations = []
        
        if world_id:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            items_path = os.path.join(world_dir, "items.json")
            locations_path = os.path.join(world_dir, "locations.json")
            
            if os.path.exists(items_path):
                with open(items_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    optimized_items = data.get("items", []) if isinstance(data, dict) else data
            
            if os.path.exists(locations_path):
                with open(locations_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    optimized_locations = data.get("locations", []) if isinstance(data, dict) else data
            
            print(f"DEBUG: Returning {len(optimized_items)} items and {len(optimized_locations)} locations to frontend")

        return {
            "quests": quests,
            "items": optimized_items,
            "locations": optimized_locations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate main quest: {str(e)}")

@router.post("/generate_side_quest", response_model=GenerateQuestsResponse)
async def generate_side_quest(
    request: GenerateSideQuestRequest,
    x_model_provider: Optional[str] = Header(None)
):
    """Phase 3: Generate Side Quest for specific NPC (Granular)"""
    try:
        quests = await genesis_service.generate_side_quest(
            request.target_npc,
            request.world_bible, 
            provider=x_model_provider
        )
        
        world_id = request.world_bible.get("world_id")
        if world_id:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            if os.path.exists(world_dir):
                quest_path = os.path.join(world_dir, "quests.json")
                existing_quests = []
                if os.path.exists(quest_path):
                    with open(quest_path, "r", encoding="utf-8") as f:
                        existing_quests = json.load(f)
                
                # Append new side quest
                # Maybe remove old quest for this NPC if exists? 
                # For now, just append.
                existing_quests.extend(quests)
                
                with open(quest_path, "w", encoding="utf-8") as f:
                    json.dump(existing_quests, f, indent=2, ensure_ascii=False)

        # ✅ NEW: Return Updated Assets
        optimized_items = []
        optimized_locations = []
        
        if world_id:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            items_path = os.path.join(world_dir, "items.json")
            locations_path = os.path.join(world_dir, "locations.json")
            
            if os.path.exists(items_path):
                with open(items_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    optimized_items = data.get("items", []) if isinstance(data, dict) else data
            
            if os.path.exists(locations_path):
                with open(locations_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    optimized_locations = data.get("locations", []) if isinstance(data, dict) else data

        return GenerateQuestsResponse(
            quests=quests,
            items=optimized_items,
            locations=optimized_locations
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate side quest: {str(e)}")

@router.post("/generate_quests", response_model=GenerateQuestsResponse)
async def generate_quests(
    request: GenerateQuestsRequest,
    x_model_provider: Optional[str] = Header(None)
):
    """Phase 3: Generate Quests (All in one)"""
    try:
        # ✅ NEW: Auto-confirm NPC Roster before generating quests
        world_id = request.world_bible.get("world_id")
        if world_id:
            print(f"DEBUG: Auto-confirming NPC roster for world {world_id} before quest generation")
            await genesis_service.handle_roster_confirm(world_id)
        
        quests = await genesis_service.generate_quests(
            request.world_bible, 
            request.npcs, 
            provider=x_model_provider
        )
        
        # Save to file if world_id exists
        world_id = request.world_bible.get("world_id")
        if world_id:
            world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
            if os.path.exists(world_dir):
                quest_path = os.path.join(world_dir, "quests.json")
                with open(quest_path, "w", encoding="utf-8") as f:
                    json.dump(quests, f, indent=2, ensure_ascii=False)
                    
        return GenerateQuestsResponse(quests=quests)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate quests: {str(e)}")

@router.post("/upload_avatar", response_model=NPC)
async def upload_avatar(
    world_id: str = Form(...),
    npc_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload custom avatar image for an NPC"""
    try:
        # Check file type
        filename = file.filename
        extension = filename.split(".")[-1] if "." in filename else "png"
        
        # Read file
        file_data = await file.read()
        
        # Upload to OSS (Custom Path)
        image_url = oss_service.upload_custom_avatar(file_data, world_id, npc_id, extension)
        
        if not image_url:
            raise HTTPException(status_code=500, detail="Failed to upload image")
            
        # Update JSON
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        npc_path = os.path.join(world_dir, "npcs.json")
        
        if not os.path.exists(npc_path):
            raise HTTPException(status_code=404, detail="World data not found")
            
        with open(npc_path, "r", encoding="utf-8") as f:
            npcs = json.load(f)
            
        target_npc = None
        target_index = -1
        for i, npc in enumerate(npcs):
            if npc.get("id") == npc_id:
                target_npc = npc
                target_index = i
                break
        
        if target_npc:
            # Update URL
            target_npc["profile"]["avatar_url"] = image_url
            npcs[target_index] = target_npc
            
            # Save to file
            with open(npc_path, "w", encoding="utf-8") as f:
                json.dump(npcs, f, indent=2, ensure_ascii=False)
                
            # Also update RuntimeEngine if active
            from ..core.runtime import RuntimeEngine
            if world_id in RuntimeEngine._instances:
                engine = RuntimeEngine.get_instance(world_id)
                for engine_npc in engine.npcs:
                    if engine_npc.id == npc_id:
                        engine_npc.profile.avatar_url = image_url
                        break

            return target_npc
        else:
             raise HTTPException(status_code=404, detail="NPC not found")
             
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading avatar: {str(e)}")

# --- Execution Endpoints for Chat Proposals ---

@router.post("/execute_add_npc")
async def execute_add_npc(request: dict):
    """Execute Add NPC Action"""
    world_id = request.get("world_id")
    count = request.get("count", 1)
    requirements = request.get("requirements", "")
    
    if not world_id:
        raise HTTPException(status_code=400, detail="Missing world_id")
        
    await genesis_service.execute_add_npc(world_id, count, requirements)
    return {"status": "success"}

@router.post("/execute_regenerate_npc")
async def execute_regenerate_npc(request: dict):
    """Execute Regenerate NPC Action (By Name)"""
    world_id = request.get("world_id")
    target_name = request.get("target_name")
    instruction = request.get("instruction")
    
    if not world_id or not target_name:
        raise HTTPException(status_code=400, detail="Missing parameters")
        
    await genesis_service.execute_npc_regenerate(world_id, target_name, instruction)
    return {"status": "success"}

@router.post("/execute_manage_images")
async def execute_manage_images(request: dict):
    """Execute Image Management Action"""
    world_id = request.get("world_id")
    action = request.get("action")
    target_name = request.get("target_name")
    
    if not world_id or not action:
        raise HTTPException(status_code=400, detail="Missing parameters")
        
    await genesis_service.execute_image_management(world_id, action, target_name)
    return {"status": "success"}

@router.post("/execute_confirm_roster")
async def execute_confirm_roster(request: dict):
    """Execute Confirm Roster Action"""
    world_id = request.get("world_id")
    
    if not world_id:
        raise HTTPException(status_code=400, detail="Missing world_id")
        
    await genesis_service.handle_roster_confirm(world_id)
    return {"status": "success"}

@router.post("/update_quest")
async def update_quest(request: dict):
    """Update quest details"""
    # Request: { "world_id": "...", "quest_id": "...", "title": "...", "description": "..." }
    world_id = request.get("world_id")
    quest_id = request.get("quest_id")
    title = request.get("title")
    description = request.get("description")
    
    if not world_id or not quest_id:
        raise HTTPException(status_code=400, detail="Missing parameters")
        
    try:
        world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
        quest_path = os.path.join(world_dir, "quests.json")
        
        if not os.path.exists(quest_path):
            raise HTTPException(status_code=404, detail="Quests not found")
            
        with open(quest_path, "r", encoding="utf-8") as f:
            quests = json.load(f)
            
        updated = False
        for quest in quests:
            if quest.get("id") == quest_id:
                if title: quest["title"] = title
                if description: quest["description"] = description
                updated = True
                break
                
        if not updated:
            raise HTTPException(status_code=404, detail="Quest not found")
            
        with open(quest_path, "w", encoding="utf-8") as f:
            json.dump(quests, f, indent=2, ensure_ascii=False)
            
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update quest: {str(e)}")

@router.post("/execute_confirm_quest_blueprint")
async def execute_confirm_quest_blueprint(request: dict):
    """Execute Confirm Quest Blueprint Action"""
    world_id = request.get("world_id")
    
    if not world_id:
        raise HTTPException(status_code=400, detail="Missing world_id")
        
    try:
        await genesis_service.finalize_quest_phase(world_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm quest blueprint: {str(e)}")
