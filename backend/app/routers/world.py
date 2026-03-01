from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Body
import os
import json
import shutil
from typing import List
from datetime import datetime
from ..core.config import settings
from ..schemas.world import WorldListResponse, WorldMeta, LoadWorldResponse, WorldConfigUpdate, WorldConfig
from ..core.runtime import RuntimeEngine

router = APIRouter(prefix="/api/worlds", tags=["worlds"])

@router.get("/", response_model=WorldListResponse)
async def list_worlds():
    """List all saved worlds"""
    worlds_dir = os.path.join(settings.DATA_DIR, "worlds")
    if not os.path.exists(worlds_dir):
        return {"worlds": []}
    
    world_list = []
    
    try:
        # Scan directories
        for world_id in os.listdir(worlds_dir):
            world_path = os.path.join(worlds_dir, world_id)
            if not os.path.isdir(world_path):
                continue
            
            bible_path = os.path.join(world_path, "bible.json")
            npc_path = os.path.join(world_path, "npcs.json")
            
            if os.path.exists(bible_path):
                try:
                    with open(bible_path, "r", encoding="utf-8") as f:
                        bible_data = json.load(f)
                    
                    # Basic Meta from Bible
                    title = bible_data.get("title")
                    scene_name = bible_data.get("scene", {}).get("name", "Unknown World")
                    era = bible_data.get("background", {}).get("era", "Unknown Era")
                    
                    # Count NPCs
                    npc_count = 0
                    if os.path.exists(npc_path):
                        with open(npc_path, "r", encoding="utf-8") as f:
                            npcs = json.load(f)
                            npc_count = len(npcs)
                    
                    # Get file creation time as creation time
                    ctime = os.path.getctime(bible_path)
                    created_at = datetime.fromtimestamp(ctime)
                    
                    world_list.append(WorldMeta(
                        world_id=world_id,
                        title=title,
                        name=scene_name,
                        era=era,
                        created_at=created_at,
                        npc_count=npc_count,
                        preview=bible_data.get("scene", {}).get("description", "")[:50] + "..."
                    ))
                except Exception as e:
                    print(f"Error reading world {world_id}: {e}")
                    continue
        
        # Sort by creation time desc
        world_list.sort(key=lambda x: x.created_at, reverse=True)
        return {"worlds": world_list}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/{world_id}")
async def websocket_endpoint(websocket: WebSocket, world_id: str):
    # 1. Accept connection immediately
    await websocket.accept()
    
    engine = RuntimeEngine.get_instance(world_id)
    
    # Check for data updates (Smart Reload) BEFORE connecting
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    needs_reload = False
    
    # 检查 schedules/ 目录是否存在（新格式：每个NPC一个JSON文件）
    schedules_dir = os.path.join(world_dir, "schedules")
    
    if not engine.world_bible or not engine.npcs:
        needs_reload = True
    elif not os.path.exists(schedules_dir) or not os.path.isdir(schedules_dir):
        # Fallback: 检查旧格式 schedules.json
        schedules_file = os.path.join(world_dir, "schedules.json")
        if not os.path.exists(schedules_file):
            print(f"DEBUG: Neither schedules/ directory nor schedules.json found for {world_id}.")
            # 不再需要生成，只是记录日志
    elif os.path.exists(os.path.join(world_dir, "npcs.json")):
        try:
            # Check if NPC count increased
            with open(os.path.join(world_dir, "npcs.json"), "r", encoding="utf-8") as f:
                file_npcs = json.load(f)
            if len(file_npcs) > len(engine.npcs):
                print(f"DEBUG: NPC count mismatch (File: {len(file_npcs)}, Engine: {len(engine.npcs)}). Reloading...")
                needs_reload = True
        except Exception:
            pass

    # Status callback with WebSocket exception handling
    async def status_callback(msg: str):
        try:
            await websocket.send_json({"type": "status", "message": msg})
        except RuntimeError as e:
            print(f"WebSocket closed during status update: {e}")
        except Exception as e:
            print(f"Error sending status: {e}")

    # Load data FIRST if needed
    if needs_reload:
        try:
            await websocket.send_json({"type": "status", "message": "正在唤醒沉睡的世界..."})
        except RuntimeError:
            print("WebSocket closed before initialization")
            return
            
        if os.path.exists(world_dir):
            try:
                with open(os.path.join(world_dir, "bible.json"), "r", encoding="utf-8") as f:
                    bible = json.load(f)
                
                npc_path = os.path.join(world_dir, "npcs.json")
                npcs = []
                if os.path.exists(npc_path):
                    with open(npc_path, "r", encoding="utf-8") as f:
                        npcs = json.load(f)
                        
                engine.load_data(bible, npcs)
                
                # Send status update
                try:
                    await websocket.send_json({"type": "status", "message": "正在回溯时间线..."})
                except RuntimeError:
                    print("WebSocket closed during initialization")
                    return
                
                # Note: Schedules are pre-generated in Genesis phase, no LLM call needed here
                # load_data() already loads schedules from schedules/ directory
                
            except Exception as e:
                print(f"Error loading world data for runtime: {e}")
                try:
                    await websocket.send_json({"type": "error", "message": f"Load failed: {str(e)}"})
                except RuntimeError:
                    print("WebSocket closed, cannot send error message")
    
    # NOW connect and send initial state (with loaded data)
    await engine.connect(websocket)
    
    # Send Ready signal at the end of initialization
    try:
        await websocket.send_json({"type": "ready"})
    except RuntimeError:
        print("WebSocket closed before sending ready signal")

    try:
        while True:
            # Keep alive and listen for client commands (e.g. pause/play)
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "start":
                engine.start()
            elif message.get("action") == "stop":
                engine.stop()
            elif message.get("action") == "load_history":
                await engine.send_history_chunk(message.get("before_timestamp"), websocket)
            elif message.get("action") == "player_action":
                await engine.handle_player_action(message)
            elif message.get("action") == "set_time_scale":
                scale = int(message.get("scale", 60))
                engine.set_time_scale(scale)
            # ==================== Quest Chip Handling ====================
            elif message.get("action") == "chip_click":
                # 前端发送数据在消息根层级，重新组装 chip_data
                chip_data = {
                    "type": message.get("chip_type"),
                    "label": message.get("chip_label"),
                    "quest_id": message.get("quest_id"),
                    "node_id": message.get("node_id"),
                    "npc_id": message.get("npc_id"),
                    "line_index": message.get("line_index"),
                    "action": message.get("item_action")  # 物品操作
                }
                result = await engine.handle_chip_click(chip_data)
                
                # 根据结果返回不同类型的响应
                if result.get("new_chips"):
                    # 有新的 chips 需要显示（对话流下一步）
                    await websocket.send_json({
                        "type": "chip_response",
                        "new_chips": result.get("new_chips"),
                        "clear_chips": False,
                        "result": result
                    })
                elif result.get("rejected") or result.get("ignored"):
                    # 玩家拒绝或忽略
                    await websocket.send_json({
                        "type": "chip_response",
                        "clear_chips": True,
                        "result": result
                    })
                elif result.get("flow_ended"):
                    # 对话流结束
                    await websocket.send_json({
                        "type": "dialogue_flow_end",
                        "result": result
                    })
                else:
                    await websocket.send_json({
                        "type": "chip_response",
                        "result": result
                    })
                    
            elif message.get("action") == "dialogue_flow":
                action_data = message.get("data", {})
                result = await engine.handle_dialogue_flow_action(action_data)
                await websocket.send_json({
                    "type": "dialogue_flow_response",
                    "result": result
                })
            # ==================== END: Quest Chip Handling ====================
                
    except WebSocketDisconnect:
        engine.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket Error: {e}")
        engine.disconnect(websocket)

@router.patch("/{world_id}/config")
async def update_world_config(world_id: str, payload: WorldConfigUpdate):
    """Update world configuration"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    if not os.path.exists(world_dir):
        raise HTTPException(status_code=404, detail="World not found")
    
    bible_path = os.path.join(world_dir, "bible.json")
    try:
        with open(bible_path, "r", encoding="utf-8") as f:
            world_bible = json.load(f)
        
        # Update config
        world_bible["config"] = payload.config.dict()
        
        with open(bible_path, "w", encoding="utf-8") as f:
            json.dump(world_bible, f, ensure_ascii=False, indent=2)
            
        return {"status": "success", "config": world_bible["config"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

@router.patch("/{world_id}/title")
async def update_world_title(world_id: str, payload: dict = Body(...)):
    """Update world title"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    if not os.path.exists(world_dir):
        raise HTTPException(status_code=404, detail="World not found")
    
    bible_path = os.path.join(world_dir, "bible.json")
    try:
        with open(bible_path, "r", encoding="utf-8") as f:
            world_bible = json.load(f)
        
        new_title = payload.get("title")
        if not new_title:
            raise HTTPException(status_code=400, detail="Title is required")

        # Update title
        world_bible["title"] = new_title
        
        with open(bible_path, "w", encoding="utf-8") as f:
            json.dump(world_bible, f, ensure_ascii=False, indent=2)
            
        return {"status": "success", "title": new_title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update title: {str(e)}")

@router.get("/{world_id}", response_model=LoadWorldResponse)
async def load_world(world_id: str):
    """Load a specific world"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    if not os.path.exists(world_dir):
        raise HTTPException(status_code=404, detail="World not found")
    
    try:
        # Load Bible
        with open(os.path.join(world_dir, "bible.json"), "r", encoding="utf-8") as f:
            world_bible = json.load(f)
            
        # Load NPCs (Prioritize Runtime State)
        npcs = []
        if world_id in RuntimeEngine._instances:
             # If world is running, get live state (Single Source of Truth)
             engine = RuntimeEngine.get_instance(world_id)
             npcs = [npc.model_dump() for npc in engine.npcs]
        else:
             # Fallback to static file
             npc_path = os.path.join(world_dir, "npcs.json")
             if os.path.exists(npc_path):
                 with open(npc_path, "r", encoding="utf-8") as f:
                     npcs = json.load(f)
                
        # Load History
        chat_history = []
        chat_path = os.path.join(world_dir, "chat.json")
        if os.path.exists(chat_path):
            with open(chat_path, "r", encoding="utf-8") as f:
                chat_history = json.load(f)
        
        # Load Schedules
        schedules = {}
        schedules_dir = os.path.join(world_dir, "schedules")
        
        # 1. Try loading from schedules/ directory (New Format)
        if os.path.exists(schedules_dir) and os.path.isdir(schedules_dir):
            try:
                for filename in os.listdir(schedules_dir):
                    if filename.endswith(".json"):
                        npc_id = filename[:-5]
                        filepath = os.path.join(schedules_dir, filename)
                        with open(filepath, "r", encoding="utf-8") as f:
                            schedule_data = json.load(f)
                            if isinstance(schedule_data, list):
                                schedules[npc_id] = schedule_data
                            elif isinstance(schedule_data, dict):
                                schedules[npc_id] = [schedule_data]
            except Exception as e:
                print(f"Error loading schedules from directory: {e}")

        # 2. Fallback to schedules.json (Old Format) if empty
        if not schedules:
            schedules_path = os.path.join(world_dir, "schedules.json")
            if os.path.exists(schedules_path):
                with open(schedules_path, "r", encoding="utf-8") as f:
                    schedules = json.load(f)

        # Load Quests
        quests = []
        quests_path = os.path.join(world_dir, "quests.json")
        if os.path.exists(quests_path):
            with open(quests_path, "r", encoding="utf-8") as f:
                quests_data = json.load(f)
                # Handle both formats: {"quests": [...]} or [...]
                quests = quests_data.get("quests", []) if isinstance(quests_data, dict) else quests_data

        # Load Items (Phase 2 Update)
        items = []
        items_path = os.path.join(world_dir, "items.json")
        if os.path.exists(items_path):
            with open(items_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("items", [])

        # Load Locations
        locations = []
        locations_path = os.path.join(world_dir, "locations.json")
        if os.path.exists(locations_path):
            with open(locations_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                locations = data.get("locations", [])

        # Load Time Config
        time_config = None
        time_path = os.path.join(world_dir, "time.json")
        if os.path.exists(time_path):
            with open(time_path, "r", encoding="utf-8") as f:
                time_config = json.load(f)

        # Check Lock Status
        is_locked = False
        if os.path.exists(os.path.join(world_dir, "schedules.json")): is_locked = True
        if os.path.exists(os.path.join(world_dir, "events.jsonl")): is_locked = True
        archives_dir = os.path.join(world_dir, "archives")
        if os.path.exists(archives_dir) and os.listdir(archives_dir): is_locked = True

        # Extract Config from Bible
        config_data = world_bible.get("config", {})
        config = WorldConfig(**config_data)

        return LoadWorldResponse(
            status="success",
            world_bible=world_bible,
            npcs=npcs,
            items=items,
            locations=locations,
            time_config=time_config,
            quests=quests,
            chat_history=chat_history,
            schedules=schedules,
            is_locked=is_locked,
            config=config
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load world: {str(e)}")

@router.get("/{world_id}/intro")
async def get_world_intro(world_id: str):
    """Get world introduction text"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    if not os.path.exists(world_dir):
        raise HTTPException(status_code=404, detail="World not found")
        
    try:
        intro_path = os.path.join(world_dir, "intro.txt")
        if not os.path.exists(intro_path):
            return {"intro": ""}
            
        with open(intro_path, "r", encoding="utf-8") as f:
            intro = f.read()
            
        return {"intro": intro}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load intro: {str(e)}")

@router.delete("/{world_id}")
async def delete_world(world_id: str):
    """Delete a world"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    if not os.path.exists(world_dir):
        raise HTTPException(status_code=404, detail="World not found")
    
    try:
        shutil.rmtree(world_dir)
        return {"status": "success", "message": "World deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{world_id}/archive")
async def create_archive(world_id: str):
    """Create a new archive (snapshot)"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    if not os.path.exists(world_dir):
        raise HTTPException(status_code=404, detail="World not found")
    
    # Force save runtime state if active
    if world_id in RuntimeEngine._instances:
        RuntimeEngine.get_instance(world_id).save_world_state()
        
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = os.path.join(world_dir, "archives", timestamp)
        os.makedirs(archive_dir, exist_ok=True)
        
        # Copy critical files
        files_to_copy = ["bible.json", "npcs.json", "events.jsonl", "schedules.json", "chat.json", "manga.json"]
        for filename in files_to_copy:
            src = os.path.join(world_dir, filename)
            if os.path.exists(src):
                shutil.copy2(src, archive_dir)
        
        # Copy Memory DB (Vector Database)
        memory_src = os.path.join(world_dir, "memory_db")
        if os.path.exists(memory_src):
            memory_dst = os.path.join(archive_dir, "memory_db")
            # copytree requires destination to NOT exist, which is true here (new archive dir)
            shutil.copytree(memory_src, memory_dst)
            
        # Create meta.json for custom names
        meta = {
            "id": timestamp,
            "name": timestamp, # Default name is timestamp
            "created_at": datetime.now().isoformat()
        }
        with open(os.path.join(archive_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
                
        return {"status": "success", "archive_id": timestamp}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create archive: {str(e)}")

@router.get("/{world_id}/archives")
async def list_archives(world_id: str):
    """List all archives"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    archives_dir = os.path.join(world_dir, "archives")
    
    if not os.path.exists(archives_dir):
        return {"archives": []}
        
    try:
        archives = []
        for name in os.listdir(archives_dir):
            path = os.path.join(archives_dir, name)
            if os.path.isdir(path):
                # Format timestamp for creation time
                try:
                    dt = datetime.strptime(name, "%Y%m%d_%H%M%S")
                    display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    display_time = name
                
                # Read meta.json for custom name
                display_name = display_time # Default to formatted time
                meta_path = os.path.join(path, "meta.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            # If user renamed it, use that. Otherwise use timestamp default.
                            # But wait, create_archive sets name=timestamp (raw).
                            # We probably want to show the custom name if it differs from ID?
                            # Or just always use 'name' from meta if available?
                            # Let's use 'name' from meta.
                            meta_name = meta.get("name")
                            if meta_name:
                                # If it looks like the raw ID, show formatted time instead (prettier default)
                                if meta_name == name:
                                    display_name = display_time
                                else:
                                    display_name = meta_name
                    except:
                        pass
                    
                archives.append({
                    "id": name,
                    "name": display_name,
                    "created_at": display_time
                })
        
        # Sort by ID (timestamp) desc
        archives.sort(key=lambda x: x["id"], reverse=True)
        return {"archives": archives}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{world_id}/archives/{archive_id}")
async def rename_archive(world_id: str, archive_id: str, payload: dict = Body(...)):
    """Rename an archive"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    archive_dir = os.path.join(world_dir, "archives", archive_id)
    
    if not os.path.exists(archive_dir):
        raise HTTPException(status_code=404, detail="Archive not found")
        
    new_name = payload.get("name")
    if not new_name:
        raise HTTPException(status_code=400, detail="Name is required")
        
    meta_path = os.path.join(archive_dir, "meta.json")
    meta = {}
    
    # Read existing or init new
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except:
            pass
    
    meta["name"] = new_name
    if "id" not in meta:
        meta["id"] = archive_id
    if "created_at" not in meta:
        meta["created_at"] = datetime.now().isoformat()
    
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        
    return {"status": "success", "name": new_name}

@router.delete("/{world_id}/archives/{archive_id}")
async def delete_archive(world_id: str, archive_id: str):
    """Delete an archive"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    archive_dir = os.path.join(world_dir, "archives", archive_id)
    
    if not os.path.exists(archive_dir):
        raise HTTPException(status_code=404, detail="Archive not found")
        
    try:
        shutil.rmtree(archive_dir)
        return {"status": "success", "message": "Archive deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{world_id}/archives/{archive_id}/restore")
async def restore_archive(world_id: str, archive_id: str):
    """Restore an archive"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    archive_dir = os.path.join(world_dir, "archives", archive_id)
    
    if not os.path.exists(archive_dir):
        raise HTTPException(status_code=404, detail="Archive not found")
        
    try:
        # Stop Runtime if running
        if world_id in RuntimeEngine._instances:
            engine = RuntimeEngine.get_instance(world_id)
            engine.stop()
            # We don't delete the instance, just stop it.
            # The WebSocket will reconnect/reload logic handles data reload?
            # WebSocket checks 'needs_reload' if file changes?
            # No, 'needs_reload' checks if schedules MISSING.
            # Here schedules WILL exist (restored).
            # We need to FORCE reload.
            # Best way: Remove instance from memory?
            # del RuntimeEngine._instances[world_id] 
            # But that might break active websocket references?
            # Actually, if we overwrite files, and then call load_data(), it should work.
            # Let's rely on the frontend to disconnect/reconnect after restore.
            
        # Copy files back
        files_to_copy = ["bible.json", "npcs.json", "events.jsonl", "schedules.json", "chat.json", "manga.json"]
        for filename in files_to_copy:
            src = os.path.join(archive_dir, filename)
            dst = os.path.join(world_dir, filename)
            if os.path.exists(src):
                shutil.copy2(src, dst)
            elif os.path.exists(dst):
                # If file missing in archive but exists in current (e.g. schedules), should we delete it?
                # Yes, to be safe.
                os.remove(dst)
        
        # Restore Memory DB
        memory_src = os.path.join(archive_dir, "memory_db")
        memory_dst = os.path.join(world_dir, "memory_db")
        if os.path.exists(memory_src):
            if os.path.exists(memory_dst):
                shutil.rmtree(memory_dst)
            shutil.copytree(memory_src, memory_dst)
        elif os.path.exists(memory_dst):
            # If archive has no memory (old archive), but current has memory,
            # we should probably keep current memory OR delete it?
            # Deleting it is safer to avoid mismatch, but might lose data if archive was partial.
            # Given the importance of sync, deleting is probably better to force a fresh start 
            # (though losing memories is bad, mismatch is worse).
            # But let's assume if archive is old, we keep current memory as best effort?
            # No, if we restore Day 1 archive, we don't want Day 10 memory.
            # So we should delete memory_dst.
            shutil.rmtree(memory_dst)

        # Force Reload in Memory if instance exists
        if world_id in RuntimeEngine._instances:
            engine = RuntimeEngine.get_instance(world_id)
            # Reload Data
            with open(os.path.join(world_dir, "bible.json"), "r", encoding="utf-8") as f:
                bible = json.load(f)
            with open(os.path.join(world_dir, "npcs.json"), "r", encoding="utf-8") as f:
                npcs = json.load(f)
            engine.load_data(bible, npcs)
            engine.reset() # Clear history buffers to reload from file
            # load_data loads history from file.
            
        return {"status": "success", "message": "Archive restored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restore archive: {str(e)}")

@router.post("/{world_id}/reset")
async def reset_world(world_id: str):
    """Reset world to initial state (Keep Bible/NPCs, clear History/Schedules)"""
    world_dir = os.path.join(settings.DATA_DIR, "worlds", world_id)
    if not os.path.exists(world_dir):
        raise HTTPException(status_code=404, detail="World not found")
        
    try:
        # Stop Runtime
        if world_id in RuntimeEngine._instances:
            RuntimeEngine.get_instance(world_id).stop()
            
        # Delete Files
        for filename in ["events.jsonl", "manga.json"]: # schedules.json handled by restore
            path = os.path.join(world_dir, filename)
            if os.path.exists(path):
                os.remove(path)

        # Restore Factory Settings (New Mechanism)
        initial_state_dir = os.path.join(world_dir, "initial_state")
        
        if os.path.exists(initial_state_dir):
            print(f"DEBUG: Restoring from initial_state backup: {initial_state_dir}")
            # Restore everything from initial_state
            for item in os.listdir(initial_state_dir):
                src = os.path.join(initial_state_dir, item)
                dst = os.path.join(world_dir, item)
                
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                elif os.path.isdir(src):
                    # For directories (schedules, quest_enrichments), replace entirely
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
        else:
            # Legacy Fallback (Old worlds without initial_state)
            print("DEBUG: initial_state not found, using legacy fallback.")
            
            # Clean schedules manually since restore didn't happen
            schedules_path = os.path.join(world_dir, "schedules.json")
            if os.path.exists(schedules_path):
                os.remove(schedules_path)
            
            npc_orig = os.path.join(world_dir, "npcs.original.json")
            npc_curr = os.path.join(world_dir, "npcs.json")
            if os.path.exists(npc_orig):
                shutil.copy2(npc_orig, npc_curr)

            bible_orig = os.path.join(world_dir, "bible.original.json")
            bible_curr = os.path.join(world_dir, "bible.json")
            if os.path.exists(bible_orig):
                shutil.copy2(bible_orig, bible_curr)
                
        # Reset Runtime & Memory
        if world_id in RuntimeEngine._instances:
            engine = RuntimeEngine.get_instance(world_id)
            
            # 1. Clear Memory (Vector DB)
            try:
                engine.memory_service.clear_all_memories()
            except Exception as e:
                print(f"Warning: Failed to clear active memory service: {e}")

            # 2. Reset In-Memory Buffers
            engine.reset()
            
            # 3. Force Reload Data from Disk
            # This ensures any in-memory state (like added goals) is reverted to what's in the JSON file
            try:
                with open(os.path.join(world_dir, "bible.json"), "r", encoding="utf-8") as f:
                    bible = json.load(f)
                with open(os.path.join(world_dir, "npcs.json"), "r", encoding="utf-8") as f:
                    npcs = json.load(f)
                engine.load_data(bible, npcs)
            except Exception as e:
                print(f"Error reloading data after reset: {e}")
                
        else:
            # If runtime not active, manually delete memory_db folder
            memory_path = os.path.join(world_dir, "memory_db")
            if os.path.exists(memory_path):
                try:
                    shutil.rmtree(memory_path)
                except Exception as e:
                    print(f"Failed to delete inactive memory_db: {e}")
            
        return {"status": "success", "message": "World reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset world: {str(e)}")
