from fastapi import APIRouter, HTTPException
from ..services.manga_service import manga_service
import datetime

router = APIRouter(prefix="/api/worlds/{world_id}/manga", tags=["manga"])

@router.post("/start")
async def start_manga_generation(world_id: str):
    await manga_service.start_generation(world_id)
    return {"status": "started"}

@router.post("/stop")
async def stop_manga_generation(world_id: str):
    await manga_service.stop_generation(world_id)
    return {"status": "stopped"}

@router.get("/pages")
async def get_manga_pages(world_id: str):
    pages = await manga_service.get_pages(world_id)
    return {"pages": pages}

@router.get("/status")
async def get_manga_status(world_id: str):
    return {"is_running": manga_service.is_running(world_id)}

@router.get("/progress")
async def get_manga_progress(world_id: str):
    return await manga_service.get_progress(world_id)

@router.post("/regenerate/{page_id}")
async def regenerate_manga_page(world_id: str, page_id: str):
    result = await manga_service.regenerate_page(world_id, page_id)
    if not result:
        raise HTTPException(status_code=404, detail="Page not found or regeneration failed")
    return result
