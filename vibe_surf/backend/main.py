"""
VibeSurf Backend API

uvicorn backend.main:app --host 127.0.0.1 --port 9335

FastAPI application for simplified single-task execution model.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import argparse
import os
from datetime import datetime

# Import routers
from .api.task import router as agents_router
from .api.files import router as files_router
from .api.activity import router as activity_router
from .api.config import router as config_router

# Import shared state
from . import shared_state

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VibeSurf Backend API",
    description="Simplified single-task execution model for VibeSurf",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agents_router, prefix="/api", tags=["tasks"])
app.include_router(files_router, prefix="/api", tags=["files"])
app.include_router(activity_router, prefix="/api", tags=["activity"])
app.include_router(config_router, prefix="/api", tags=["config"])

@app.on_event("startup")
async def startup_event():
    """Initialize database and VibeSurf components on startup"""
    # Initialize VibeSurf components and update shared state
    await shared_state.initialize_vibesurf_components()

    logger.info("🚀 VibeSurf Backend API started with single-task execution model")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    
    # Cleanup VibeSurf components
    if shared_state.browser_manager:
        try:
            await shared_state.browser_manager.close()
            await shared_state.browser_manager.main_browser_session.kill()
            logger.info("✅ Browser manager closed")
        except Exception as e:
            logger.error(f"❌ Error closing browser manager: {e}")
    
    # Close database
    if shared_state.db_manager:
        await shared_state.db_manager.close()
    logger.info("🛑 VibeSurf Backend API stopped")

# Health check endpoint
@app.get("/health")
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "VibeSurf Backend API",
        "model": "single-task-execution",
        "version": "2.0.0"
    }

# Session ID generation endpoint
@app.get("/generate-session-id")
async def generate_session_id(prefix: str = ""):
    """Generate a new session ID using uuid7str"""
    from uuid_extensions import uuid7str
    session_id = f"{uuid7str()}"
    return {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat()
    }

# Simple status endpoint for the active task
@app.get("/api/status")
async def get_system_status():
    """Get current system status"""
    task_info = shared_state.get_active_task_info()
    
    return {
        "system_status": "operational",
        "active_task": task_info,
        "timestamp": datetime.now().isoformat()
    }

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="VibeSurf Backend API")
    parser.add_argument(
        "--vibesurf_port",
        type=int,
        default=9335,
        help="Port for VibeSurf backend (default: 9335)"
    )
    parser.add_argument(
        "--vibesurf_extension",
        type=str,
        help="VibeSurf chrome extension path (optional)"
    )
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()
    
    # Set environment variables based on arguments
    os.environ["VIBESURF_BACKEND_PORT"] = str(args.vibesurf_port)
    if args.vibesurf_extension:
        os.environ["VIBESURF_EXTENSION"] = args.vibesurf_extension
    
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.vibesurf_port)