"""
VibeSurf Backend API

uvicorn backend.main:app --host 127.0.0.1 --port 9335

FastAPI application for simplified single-task execution model with Langflow integration.
"""
import pdb

from dotenv import load_dotenv

load_dotenv()

import os
import json
import asyncio
import argparse
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from fastapi_pagination import add_pagination
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import anyio
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic_core import PydanticSerializationError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from http import HTTPStatus

# Import routers
from .api.task import router as agents_router
from .api.files import router as files_router
from .api.activity import router as activity_router
from .api.config import router as config_router
from .api.browser import router as browser_router
from .api.voices import router as voices_router
from .api.agent import router as agent_router
from .api.composio import router as composio_router
from . import shared_state

# Configure logging
from vibe_surf.logger import get_logger
from vibe_surf.telemetry.service import ProductTelemetry
from vibe_surf.telemetry.views import BackendTelemetryEvent

logger = get_logger(__name__)

# Global variables to control background tasks
browser_monitor_task = None
langflow_init_task = None


class JavaScriptMIMETypeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
        except Exception as exc:
            if isinstance(exc, PydanticSerializationError):
                message = (
                    "Something went wrong while serializing the response. "
                    "Please share this error on our GitHub repository."
                )
                error_messages = json.dumps([message, str(exc)])
                raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=error_messages) from exc
            raise
        if (
            "files/" not in request.url.path
            and request.url.path.endswith(".js")
            and response.status_code == HTTPStatus.OK
        ):
            response.headers["Content-Type"] = "text/javascript"
        return response

async def monitor_browser_connection():
    """Background task to monitor browser connection"""
    while True:
        try:
            await asyncio.sleep(2)  # Check every 2 seconds

            if shared_state.browser_manager:
                is_connected = await shared_state.browser_manager.check_browser_connected()
                if not is_connected:
                    logger.error("No Available Browser, Exiting...")

                    # Schedule a graceful shutdown using os.kill in a separate thread
                    import threading
                    import signal
                    import os

                    def trigger_shutdown():
                        try:
                            # Give a brief moment for any cleanup
                            import time
                            time.sleep(0.5)
                            # Send SIGTERM to current process for graceful shutdown
                            os.kill(os.getpid(), signal.SIGTERM)
                        except Exception as e:
                            logger.error(f"Error during shutdown trigger: {e}")
                            # Fallback to SIGKILL if SIGTERM doesn't work
                            try:
                                os.kill(os.getpid(), signal.SIGKILL)
                            except:
                                pass

                    # Start shutdown in a separate thread to avoid blocking the async loop
                    shutdown_thread = threading.Thread(target=trigger_shutdown)
                    shutdown_thread.daemon = True
                    shutdown_thread.start()

                    # Exit the monitoring loop
                    break

        except asyncio.CancelledError:
            logger.info("Browser monitor task cancelled")
            break
        except Exception as e:
            logger.warning(f"Browser monitor error: {e}")
            # Continue monitoring even if there's an error


async def initialize_langflow_in_background():
    """Initialize Langflow in background to avoid blocking startup"""
    try:
        from lfx.log.logger import configure

        logger.info("Starting Langflow initialization in background...")
        # langflow setup envs
        from vibe_surf import common
        workspace_dir = common.get_workspace_dir()
        os.makedirs(workspace_dir, exist_ok=True)
        current_date = datetime.now().strftime("%Y-%m-%d")

        from vibe_surf.backend.langflow.initial_setup.setup import (
            initialize_auto_login_default_superuser,
            load_flows_from_directory,
            sync_flows_from_fs,
        )
        from vibe_surf.backend.langflow.interface.components import get_and_cache_all_types_dict
        from vibe_surf.backend.langflow.interface.utils import setup_llm_caching
        from vibe_surf.backend.langflow.services.deps import (
            get_queue_service,
            get_settings_service,
        )
        from vibe_surf.backend.langflow.services.utils import initialize_services, initialize_settings_service, \
            teardown_services
        from vibe_surf.backend.langflow.services.utils import initialize_services
        from vibe_surf.backend.langflow.services.deps import get_queue_service, get_service, get_settings_service, \
            get_telemetry_service

        start_time = asyncio.get_event_loop().time()
        initialize_settings_service()
        telemetry_service = get_telemetry_service()

        # Initialize services
        logger.info("Initializing Langflow services...")
        await initialize_services(fix_migration=False)
        logger.info(f"Langflow services initialized in {asyncio.get_event_loop().time() - start_time:.2f}s")

        # Setup LLM caching
        current_time = asyncio.get_event_loop().time()
        logger.info("Setting up LLM caching...")
        setup_llm_caching()
        logger.info(f"LLM caching setup in {asyncio.get_event_loop().time() - current_time:.2f}s")

        # Initialize super user if needed
        current_time = asyncio.get_event_loop().time()
        logger.info("Initializing default super user")
        await initialize_auto_login_default_superuser()
        logger.info(
            f"Default super user initialized in {asyncio.get_event_loop().time() - current_time:.2f}s"
        )
        # Load flows and start queue service
        current_time = asyncio.get_event_loop().time()
        logger.info("Loading flows...")
        await load_flows_from_directory()

        # Start sync flows task (don't await, let it run)
        asyncio.create_task(sync_flows_from_fs())

        queue_service = get_queue_service()
        if not queue_service.is_started():
            queue_service.start()
        logger.info(f"Flows loaded in {asyncio.get_event_loop().time() - current_time:.2f}s")

        # Cache components in background (optional, non-blocking)
        current_time = asyncio.get_event_loop().time()
        logger.info("Caching components...")
        await get_and_cache_all_types_dict(get_settings_service(), telemetry_service)
        logger.info(f"Components cached in {asyncio.get_event_loop().time() - current_time:.2f}s")

        total_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"Langflow initialization completed in {total_time:.2f}s")

        current_time = asyncio.get_event_loop().time()
        logger.info("Starting telemetry service")
        telemetry_service.start()
        logger.info(f"started telemetry service in {asyncio.get_event_loop().time() - current_time:.2f}s")


    except Exception as e:
        logger.error(f"Error during Langflow initialization: {e}")
        # Don't raise the exception - let the main app continue running


def get_lifespan():
    """Get the lifespan context manager for the FastAPI app"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global browser_monitor_task, langflow_init_task

        try:
            # Start Langflow initialization in background (non-blocking)
            langflow_init_task = asyncio.create_task(initialize_langflow_in_background())
            # await initialize_langflow_in_background()
            logger.info("🚀 Started Langflow initialization in background")

            # Initialize telemetry and capture startup event
            telemetry = ProductTelemetry()
            import vibe_surf
            startup_event = BackendTelemetryEvent(
                version=vibe_surf.__version__,
                action='startup'
            )
            telemetry.capture(startup_event)

            # Initialize VibeSurf components and update shared state
            await shared_state.initialize_vibesurf_components()

            # Start browser monitoring task
            browser_monitor_task = asyncio.create_task(monitor_browser_connection())
            logger.info("🔍 Started browser connection monitor")

            logger.info("🚀 VibeSurf Backend API started with single-task execution model")

            # Flush telemetry
            telemetry.flush()

            yield

        except Exception as exc:
            logger.exception(exc)
            raise
        finally:
            # Cleanup on shutdown
            logger.info("Starting graceful shutdown...")

            # Capture telemetry shutdown event
            telemetry = ProductTelemetry()
            import vibe_surf
            shutdown_event = BackendTelemetryEvent(
                version=vibe_surf.__version__,
                action='shutdown'
            )
            telemetry.capture(shutdown_event)

            # Cancel browser monitor task
            if browser_monitor_task and not browser_monitor_task.done():
                browser_monitor_task.cancel()
                try:
                    await asyncio.wait_for(browser_monitor_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                logger.info("Browser monitor task stopped")

            # Cancel Langflow initialization task if still running
            if langflow_init_task and not langflow_init_task.done():
                logger.info("Stopping Langflow initialization...")
                langflow_init_task.cancel()
                try:
                    await asyncio.wait_for(langflow_init_task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                logger.info("Langflow initialization task stopped")

            # Cleanup Langflow services if they were initialized
            try:
                from vibe_surf.backend.langflow.services.utils import teardown_services
                logger.info("Cleaning up Langflow services...")
                await teardown_services()
                logger.info("Langflow services cleaned up")
            except ImportError:
                # Services weren't initialized, nothing to clean up
                pass
            except Exception as e:
                logger.warning(f"Error during Langflow cleanup: {e}")

            # Cleanup VibeSurf components
            if shared_state.browser_manager:
                try:
                    await shared_state.browser_manager.close()
                    await shared_state.browser_manager.main_browser_session.kill()
                    logger.info("Browser manager closed")
                except Exception as e:
                    logger.error(f"Error closing browser manager: {e}")

            # Close database
            if shared_state.db_manager:
                try:
                    await shared_state.db_manager.close()
                    logger.info("Database manager closed")
                except Exception as e:
                    logger.error(f"Error closing database manager: {e}")

            logger.info("VibeSurf Backend API stopped")

            # Flush telemetry before shutdown
            telemetry.flush()

    return lifespan


def setup_static_files(app: FastAPI, static_files_dir: Path) -> None:
    """Setup the static files directory.

    Args:
        app (FastAPI): FastAPI app.
        static_files_dir (Path): Path to the static files directory.
    """
    app.mount(
        "/static",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )

    @app.exception_handler(404)
    async def custom_404_handler(_request: Request, _exc: HTTPException):
        path = anyio.Path(static_files_dir) / "index.html"

        if not await path.exists():
            msg = f"File at path {path} does not exist."
            raise RuntimeError(msg)
        return FileResponse(path)


def get_static_files_dir():
    """Get the static files directory relative to VibeSurf's main.py file."""
    frontend_path = Path(__file__).parent / "frontend"
    return frontend_path if frontend_path.exists() else None


def create_app() -> FastAPI:
    """Create the FastAPI app and include all routers."""
    lifespan = get_lifespan()

    app = FastAPI(
        title="VibeSurf Backend API",
        description="Simplified single-task execution model for VibeSurf with Langflow integration",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(JavaScriptMIMETypeMiddleware)

    # Include VibeSurf routers
    app.include_router(agents_router, prefix="/api", tags=["tasks"])
    app.include_router(files_router, prefix="/api", tags=["files"])
    app.include_router(activity_router, prefix="/api", tags=["activity"])
    app.include_router(config_router, prefix="/api", tags=["config"])
    app.include_router(browser_router, prefix="/api", tags=["browser"])
    app.include_router(voices_router, prefix="/api", tags=["voices"])
    app.include_router(agent_router, prefix="/api", tags=["agent"])
    app.include_router(composio_router, prefix="/api", tags=["composio"])

    # Include Langflow routers (no additional prefix needed as they already have /api)
    from vibe_surf.backend.langflow.api import health_check_router, log_router, router as langflow_main_router

    app.include_router(langflow_main_router, tags=["langflow"])
    app.include_router(health_check_router, tags=["langflow-health"])
    app.include_router(log_router, tags=["langflow-logs"])

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

        # Check Langflow initialization status
        langflow_status = "not_started"
        if langflow_init_task:
            if langflow_init_task.done():
                if langflow_init_task.exception():
                    langflow_status = "failed"
                else:
                    langflow_status = "completed"
            else:
                langflow_status = "initializing"

        return {
            "system_status": "operational",
            "active_task": task_info,
            "langflow_status": langflow_status,
            "timestamp": datetime.now().isoformat()
        }

    # Langflow integration status endpoint
    @app.get("/api/langflow/status")
    async def get_langflow_status():
        """Get Langflow integration status"""
        status = "not_started"
        details = {}

        if langflow_init_task:
            if langflow_init_task.done():
                if langflow_init_task.exception():
                    status = "failed"
                    details["error"] = str(langflow_init_task.exception())
                else:
                    status = "completed"
                    details["message"] = "Langflow initialization completed successfully"
            else:
                status = "initializing"
                details["message"] = "Langflow is currently initializing in background"

        return {
            "status": status,
            "integration": "vibe_surf.langflow",
            "version": "2.0.0",
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "endpoints": {
                "main_api": "/api/v1",
                "health": "/health",
                "health_check": "/health_check",
                "logs": "/logs",
                "logs_stream": "/logs-stream"
            }
        }

    # Exception handler
    @app.exception_handler(Exception)
    async def exception_handler(_request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            logger.error(f"HTTPException: {exc}", exc_info=exc)
            return Response(
                content=json.dumps({"message": str(exc.detail)}),
                status_code=exc.status_code,
                media_type="application/json"
            )

        if isinstance(exc, PydanticSerializationError):
            message = (
                "Something went wrong while serializing the response. "
                "Please share this error on our GitHub repository."
            )
            error_messages = json.dumps([message, str(exc)])
            logger.error(f"PydanticSerializationError: {error_messages}", exc_info=exc)
            return Response(
                content=error_messages,
                status_code=500,
                media_type="application/json"
            )

        logger.error(f"Unhandled error: {exc}", exc_info=exc)
        return Response(
            content=json.dumps({"message": str(exc)}),
            status_code=500,
            media_type="application/json"
        )

    FastAPIInstrumentor.instrument_app(app)

    add_pagination(app)

    return app


def setup_app(static_files_dir: Path | None = None, *, backend_only: bool = False) -> FastAPI:
    """Setup the FastAPI app."""
    # Get the directory of the current file
    if not static_files_dir:
        static_files_dir = get_static_files_dir()

    if not backend_only and static_files_dir and not static_files_dir.exists():
        logger.warning(f"Static files directory {static_files_dir} does not exist. Running in backend-only mode.")
        backend_only = True

    app = create_app()

    if not backend_only and static_files_dir is not None:
        setup_static_files(app, static_files_dir)
        logger.info(f"Static files configured at {static_files_dir}")

    return app


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
    parser.add_argument(
        "--backend_only",
        action="store_true",
        help="Run in backend-only mode without static files"
    )
    return parser.parse_args()


# Create the app instance for uvicorn
app = setup_app()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()

    # Set environment variables based on arguments
    os.environ["VIBESURF_BACKEND_PORT"] = str(args.vibesurf_port)
    if args.vibesurf_extension:
        os.environ["VIBESURF_EXTENSION"] = args.vibesurf_extension

    # Setup app with arguments
    app = setup_app(backend_only=args.backend_only)

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.vibesurf_port)
