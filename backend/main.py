from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.llm import llm_client
from app.routers import genesis, world, manga
import uvicorn
import logging
import traceback

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend for theNPC - Generative Agent Sandbox",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(manga.router)
app.include_router(genesis.router)
app.include_router(world.router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Exception: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": traceback.format_exc()},
    )

@app.get("/")
async def root():
    return {"message": "Welcome to theNPC Backend", "status": "running"}

@app.get("/health")
async def health_check():
    """Check backend health and LLM connection"""
    llm_status = await llm_client.check_health()
    return {
        "status": "healthy",
        "llm_service": "connected" if llm_status else "disconnected"
    }

if __name__ == "__main__":
    # Ensure reloading works
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
