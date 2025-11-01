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
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
import anyio
from pydantic_core import PydanticSerializationError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from http import HTTPStatus
import re
from urllib.parse import urlencode
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
import httpx

# Import routers
from vibe_surf.backend.api.task import router as agents_router
from vibe_surf.backend.api.files import router as files_router
from vibe_surf.backend.api.activity import router as activity_router
from vibe_surf.backend.api.config import router as config_router
from vibe_surf.backend.api.browser import router as browser_router
from vibe_surf.backend.api.voices import router as voices_router
from vibe_surf.backend.api.agent import router as agent_router
from vibe_surf.backend.api.composio import router as composio_router
from vibe_surf.backend.api.schedule import router as schedule_router
from vibe_surf.backend.api.vibesurf import router as vibesurf_router
from vibe_surf.backend import shared_state

# Configure logging
from vibe_surf.logger import get_logger
from vibe_surf.telemetry.service import ProductTelemetry
from vibe_surf.telemetry.views import BackendTelemetryEvent

logger = get_logger(__name__)

# Global variables to control background tasks
browser_monitor_task = None
langflow_init_task = None
sync_flows_from_fs_task = None
mcp_init_task = None
component_cache_task = None
schedule_manager_task = None


def configure_langflow_envs():
    # langflow setup envs
    from vibe_surf import common
    workspace_dir = common.get_workspace_dir()
    os.makedirs(workspace_dir, exist_ok=True)
    current_date = datetime.now().strftime("%Y-%m-%d")

    langflow_db_path = str(Path(workspace_dir) / 'langflow.db')
    os.environ["LANGFLOW_DATABASE_URL"] = f"sqlite:///{langflow_db_path}"
    logger.info(f"Langflow database: {os.environ['LANGFLOW_DATABASE_URL']}")
    os.environ["LANGFLOW_SKIP_AUTH_AUTO_LOGIN"] = "true"
    os.environ["LANGFLOW_AUTO_LOGIN"] = "true"
    os.environ["LANGFLOW_LOG_FILE"] = os.path.join(workspace_dir, "logs", f'langflow_{current_date}.log')
    os.environ["LANGFLOW_LOG_LEVEL"] = "debug" if os.environ.get("VIBESURF_DEBUG", "false").lower() in ['1', 'true',
                                                                                                        'yes'] else "info"

    logger.info("Configure Langflow environment")


def setup_sentry(app: FastAPI) -> None:
    from vibe_surf.langflow.services.deps import (
        get_queue_service,
        get_settings_service,
    )
    settings = get_settings_service().settings
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
        )
        app.add_middleware(SentryAsgiMiddleware)


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


async def load_bundles_with_error_handling():
    try:
        from vibe_surf.langflow.initial_setup.setup import (
            create_or_update_starter_projects,
            initialize_auto_login_default_superuser,
            load_bundles_from_urls,
            load_flows_from_directory,
            sync_flows_from_fs,
        )
        return await load_bundles_from_urls()
    except (httpx.TimeoutException, httpx.HTTPError, httpx.RequestError) as exc:
        logger.error(f"Error loading bundles from URLs: {exc}")
        return [], []


async def initialize_langflow_in_background():
    """Initialize Langflow in background to avoid blocking startup"""
    global sync_flows_from_fs_task, mcp_init_task, component_cache_task

    try:
        logger.info("Starting Langflow initialization in background...")

        from vibe_surf.langflow.initial_setup.setup import (
            create_or_update_starter_projects,
            initialize_auto_login_default_superuser,
            load_flows_from_directory,
            sync_flows_from_fs,
        )
        from vibe_surf.langflow.interface.components import get_and_cache_all_types_dict
        from vibe_surf.langflow.interface.utils import setup_llm_caching
        from vibe_surf.langflow.services.deps import (
            get_queue_service,
            get_settings_service,
        )
        from vibe_surf.langflow.services.utils import initialize_services, initialize_settings_service, \
            teardown_services
        from vibe_surf.langflow.services.utils import initialize_services
        from vibe_surf.langflow.services.deps import get_queue_service, get_service, get_settings_service, \
            get_telemetry_service
        from vibe_surf.langflow.logging.logger import configure
        from vibe_surf.langflow.services.deps import ServiceType

        configure_langflow_envs()

        settings_service = get_settings_service()
        custom_workflow_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workflows"))
        logger.info("Custom workflow path: {}".format(custom_workflow_path))
        settings_service.settings.update_settings(components_path=custom_workflow_path)

        for key, value in os.environ.items():
            if key.startswith("LANGFLOW_"):
                new_key = key.replace("LANGFLOW_", "").lower()
                if hasattr(settings_service.auth_settings, new_key):
                    setattr(settings_service.auth_settings, new_key, value)

                if hasattr(settings_service.settings, new_key):
                    setattr(settings_service.settings, new_key, value)

        configure()

        start_time = asyncio.get_event_loop().time()

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
        # Start sync flows task (store reference for proper cleanup)
        sync_flows_from_fs_task = asyncio.create_task(sync_flows_from_fs())
        queue_service = get_queue_service()
        if not queue_service.is_started():
            queue_service.start()
        logger.info(f"Flows loaded in {asyncio.get_event_loop().time() - current_time:.2f}s")

        current_time = asyncio.get_event_loop().time()
        logger.info("Starting telemetry service")
        telemetry_service.start()
        logger.info(f"started telemetry service in {asyncio.get_event_loop().time() - current_time:.2f}s")

        # Start MCP Composer service
        current_time = asyncio.get_event_loop().time()
        logger.info("Starting MCP Composer service")
        mcp_composer_service = get_service(ServiceType.MCP_COMPOSER_SERVICE)
        await mcp_composer_service.start()
        logger.info(f"MCP Composer service started in {asyncio.get_event_loop().time() - current_time:.2f}s")

        # Delayed MCP server initialization
        from vibe_surf.langflow.api.v1.mcp_projects import init_mcp_servers

        async def delayed_init_mcp_servers():
            await asyncio.sleep(10.0)  # Increased delay to allow starter projects to be created
            current_time = asyncio.get_event_loop().time()
            logger.info("Loading MCP servers for projects")
            try:
                await init_mcp_servers()
                logger.info(f"MCP servers loaded in {asyncio.get_event_loop().time() - current_time:.2f}s")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"First MCP server initialization attempt failed: {e}")
                await asyncio.sleep(5.0)  # Increased retry delay
                current_time = asyncio.get_event_loop().time()
                logger.info("Retrying MCP servers initialization")
                try:
                    await init_mcp_servers()
                    logger.info(
                        f"MCP servers loaded on retry in {asyncio.get_event_loop().time() - current_time:.2f}s"
                    )
                except Exception as e2:  # noqa: BLE001
                    logger.error(f"Failed to initialize MCP servers after retry: {e2}")

        # Start the delayed initialization as a background task
        mcp_init_task = asyncio.create_task(delayed_init_mcp_servers())

        async def components_cache_in_background():
            try:
                # give app a little time to fully start
                await asyncio.sleep(1.0)
                current_time = asyncio.get_event_loop().time()
                logger.debug("Loading bundles")
                temp_dirs, bundles_components_paths = await load_bundles_with_error_handling()
                get_settings_service().settings.components_path.extend(bundles_components_paths)
                logger.debug(f"Bundles loaded in {asyncio.get_event_loop().time() - current_time:.2f}s")
                current_time = asyncio.get_event_loop().time()
                logger.info("Background: Starting full component caching")
                all_types_dict = await get_and_cache_all_types_dict(get_settings_service())
                current_time = asyncio.get_event_loop().time()
                logger.info("Creating/updating starter projects")
                import tempfile

                from filelock import FileLock

                lock_file = Path(tempfile.gettempdir()) / "langflow_starter_projects.lock"
                lock = FileLock(lock_file, timeout=1)
                with lock:
                    await create_or_update_starter_projects(all_types_dict)
                    logger.info(
                        f"Starter projects created/updated in {asyncio.get_event_loop().time() - current_time:.2f}s"
                    )

                logger.info(
                    f"Background: Full component caching completed in {asyncio.get_event_loop().time() - current_time:.2f}s")
            except Exception as e:
                logger.error(f"Background: Full component caching failed: {e}")
                import traceback
                traceback.print_exc()

        # start background full cache task
        component_cache_task = asyncio.create_task(components_cache_in_background())

        total_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"Langflow initialization completed in {total_time:.2f}s")
        logger.info(f"Langflow database: {settings_service.settings.database_url}")

    except Exception as e:
        logger.error(f"Error during Langflow initialization: {e}")
        import traceback
        traceback.print_exc()


def get_lifespan():
    """Get the lifespan context manager for the FastAPI app"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global browser_monitor_task, langflow_init_task, schedule_manager_task

        try:
            await initialize_langflow_in_background()
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

            await shared_state.initialize_schedule_manager()

            # Start browser monitoring task
            browser_monitor_task = asyncio.create_task(monitor_browser_connection())
            logger.info("🔍 Started browser connection monitor")

            # Initialize and start schedule manager
            if shared_state.schedule_manager:
                schedule_manager_task = asyncio.create_task(shared_state.schedule_manager.start())
                logger.info("📅 Started schedule manager")

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

            await shared_state.shutdown_schedule_manager()

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

            # Stop schedule manager
            if schedule_manager_task and not schedule_manager_task.done():
                logger.info("Stopping schedule manager...")
                if shared_state.schedule_manager:
                    await shared_state.schedule_manager.stop()
                schedule_manager_task.cancel()
                try:
                    await asyncio.wait_for(schedule_manager_task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                logger.info("Schedule manager stopped")

            # Cancel background tasks
            tasks_to_cancel = []

            # Cancel sync flows task
            if sync_flows_from_fs_task and not sync_flows_from_fs_task.done():
                logger.info("Stopping sync flows task...")
                sync_flows_from_fs_task.cancel()
                tasks_to_cancel.append(sync_flows_from_fs_task)

            # Cancel MCP initialization task
            if mcp_init_task and not mcp_init_task.done():
                logger.info("Stopping MCP initialization task...")
                mcp_init_task.cancel()
                tasks_to_cancel.append(mcp_init_task)

            # Cancel Langflow initialization task if still running
            if langflow_init_task and not langflow_init_task.done():
                logger.info("Stopping Langflow initialization...")
                langflow_init_task.cancel()
                tasks_to_cancel.append(langflow_init_task)

            if component_cache_task and not component_cache_task.done():
                logger.info("Cancelling background cache task...")
                component_cache_task.cancel()
                tasks_to_cancel.append(component_cache_task)

            # Wait for all tasks to complete
            if tasks_to_cancel:
                try:
                    results = await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
                    # Log any non-cancellation exceptions
                    for result in results:
                        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                            logger.error(f"Error during task cleanup: {result}", exc_info=result)
                except Exception as e:
                    logger.warning(f"Error during task cancellation: {e}")

                logger.info("Background tasks stopped")

            # Cleanup Langflow services if they were initialized
            try:
                from vibe_surf.langflow.services.utils import teardown_services
                logger.info("Cleaning up Langflow services...")
                await asyncio.wait_for(teardown_services(), timeout=30)
                logger.info("Langflow services cleaned up")
            except ImportError:
                # Services weren't initialized, nothing to clean up
                pass
            except asyncio.TimeoutError:
                logger.warning("Teardown services timed out after 30s.")
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
        static_files_dir (str): Path to the static files directory.
    """
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )

    @app.exception_handler(404)
    async def custom_404_handler(_request, _exc):
        path = anyio.Path(static_files_dir) / "index.html"

        if not await path.exists():
            msg = f"File at path {path} does not exist."
            raise RuntimeError(msg)
        return FileResponse(path)


def get_static_files_dir():
    """Get the static files directory relative to VibeSurf's main.py file."""
    frontend_path = Path(__file__).parent / "frontend"
    logger.debug(f"Checking static files directory: {frontend_path}")
    logger.debug(f"Directory exists: {frontend_path.exists()}")
    if frontend_path.exists():
        logger.debug(f"Found static files at: {frontend_path}")
        return frontend_path
    else:
        logger.error(f"Static files directory does not exist: {frontend_path}")
        return None


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


def create_app() -> FastAPI:
    """Create the FastAPI app and include all routers."""
    from vibe_surf.langflow.services.deps import (
        get_queue_service,
        get_settings_service,
    )
    from vibe_surf.langflow.middleware import ContentSizeLimitMiddleware
    from vibe_surf.langflow.logging.logger import configure

    lifespan = get_lifespan()

    configure()

    app = FastAPI(
        title="VibeSurf Backend API",
        description="Simplified single-task execution model for VibeSurf with Langflow integration",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(ContentSizeLimitMiddleware)

    settings = get_settings_service().settings

    # Apply current CORS configuration (maintains backward compatibility)
    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(JavaScriptMIMETypeMiddleware)

    setup_sentry(app)

    # Include VibeSurf routers
    app.include_router(agents_router, prefix="/api", tags=["tasks"])
    app.include_router(files_router, prefix="/api", tags=["files"])
    app.include_router(activity_router, prefix="/api", tags=["activity"])
    app.include_router(config_router, prefix="/api", tags=["config"])
    app.include_router(browser_router, prefix="/api", tags=["browser"])
    app.include_router(voices_router, prefix="/api", tags=["voices"])
    app.include_router(agent_router, prefix="/api", tags=["agent"])
    app.include_router(composio_router, prefix="/api", tags=["composio"])
    app.include_router(schedule_router, prefix="/api", tags=["schedule"])
    app.include_router(vibesurf_router, prefix="/api", tags=["vibesurf"])

    @app.middleware("http")
    async def check_boundary(request: Request, call_next):
        if "/api/v1/files/upload" in request.url.path:
            content_type = request.headers.get("Content-Type")

            if not content_type or "multipart/form-data" not in content_type or "boundary=" not in content_type:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Content-Type header must be 'multipart/form-data' with a boundary parameter."},
                )

            boundary = content_type.split("boundary=")[-1].strip()

            if not re.match(r"^[\w\-]{1,70}$", boundary):
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Invalid boundary format"},
                )

            body = await request.body()

            boundary_start = f"--{boundary}".encode()
            # The multipart/form-data spec doesn't require a newline after the boundary, however many clients do
            # implement it that way
            boundary_end = f"--{boundary}--\r\n".encode()
            boundary_end_no_newline = f"--{boundary}--".encode()

            if not body.startswith(boundary_start) or not body.endswith((boundary_end, boundary_end_no_newline)):
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Invalid multipart formatting"},
                )

        return await call_next(request)

    @app.middleware("http")
    async def flatten_query_string_lists(request: Request, call_next):
        flattened: list[tuple[str, str]] = []
        for key, value in request.query_params.multi_items():
            flattened.extend((key, entry) for entry in value.split(","))

        request.scope["query_string"] = urlencode(flattened, doseq=True).encode("utf-8")

        return await call_next(request)

    # Include Langflow routers (no additional prefix needed as they already have /api)
    from vibe_surf.langflow.api import health_check_router, log_router, router as langflow_main_router

    if settings.mcp_server_enabled:
        from vibe_surf.langflow.api.v1 import mcp_router

        app.include_router(mcp_router, tags=["langflow-mcp"])

    app.include_router(langflow_main_router, tags=["langflow"])
    app.include_router(health_check_router, tags=["langflow-health"])
    app.include_router(log_router, tags=["langflow-logs"])

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
    from vibe_surf.langflow.logging.logger import configure

    # Set environment variables based on arguments
    os.environ["VIBESURF_BACKEND_PORT"] = str(args.vibesurf_port)
    if args.vibesurf_extension:
        os.environ["VIBESURF_EXTENSION"] = args.vibesurf_extension

    # Setup app with arguments
    app = setup_app(backend_only=args.backend_only)

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.vibesurf_port,
                workers=1, log_level="error", reload=False, loop="asyncio")
