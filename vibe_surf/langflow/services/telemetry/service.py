from __future__ import annotations

import asyncio
import hashlib
import os
import pdb
import platform
import traceback
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from posthog import Posthog
from uuid_extensions import uuid7str

from vibe_surf.langflow.logging.logger import logger
from vibe_surf.langflow.services.base import Service
from vibe_surf.langflow.services.telemetry.schema import (
    ComponentPayload,
    ExceptionPayload,
    PlaygroundPayload,
    RunPayload,
    ShutdownPayload,
    VersionPayload,
)
from vibe_surf.langflow.utils.version import get_version_info
from vibe_surf import common

if TYPE_CHECKING:
    from pydantic import BaseModel

    from vibe_surf.langflow.services.settings.service import SettingsService


class TelemetryService(Service):
    name = "telemetry_service"

    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        self.base_url = settings_service.settings.telemetry_base_url
        self.telemetry_queue: asyncio.Queue = asyncio.Queue()
        self.client = httpx.AsyncClient(timeout=10.0)  # Set a reasonable timeout
        self.running = False
        self._stopping = False

        # PostHog configuration
        self.project_api_key = 'phc_lCYnQqFlfNHAlh1TJGqaTvD8EFPCKR7ONsEHbbWuPVr'
        self.host = 'https://us.i.posthog.com'
        self.posthog_client = None
        self._curr_user_id = None
        
        # User ID persistence path
        self.workspace_dir = common.get_workspace_dir()
        self.user_id_path = os.path.join(self.workspace_dir, 'telemetry', 'userid')
        
        self.architecture: str | None = None
        self.worker_task: asyncio.Task | None = None
        # Check for do-not-track settings
        self.do_not_track = not os.getenv('VIBESURF_ANONYMIZED_TELEMETRY', 'true').lower() in ("true", "1", "yes", "on")
        self.log_package_version_task: asyncio.Task | None = None
        
        # Initialize PostHog client if telemetry is enabled
        if not self.do_not_track:
            self._initialize_posthog()

    def _initialize_posthog(self) -> None:
        """Initialize PostHog client and user ID."""
        try:
            self.posthog_client = Posthog(
                project_api_key=self.project_api_key,
                host=self.host,
                disable_geoip=False,
                enable_exception_autocapture=True,
            )
            
            # Generate or retrieve user ID
            logger.debug("PostHog client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PostHog client: {e}")
            self.posthog_client = None

    @property
    def user_id(self) -> str:
        """Get or create a unique user ID for telemetry with persistence."""
        if self._curr_user_id:
            return self._curr_user_id

        # File access may fail due to permissions or other reasons. We don't want to
        # crash so we catch all exceptions.
        try:
            if not os.path.exists(self.user_id_path):
                os.makedirs(os.path.dirname(self.user_id_path), exist_ok=True)
                with open(self.user_id_path, 'w') as f:
                    new_user_id = uuid7str()
                    f.write(new_user_id)
                self._curr_user_id = new_user_id
            else:
                with open(self.user_id_path) as f:
                    self._curr_user_id = f.read()
        except Exception:
            self._curr_user_id = 'UNKNOWN_USER_ID'
        return self._curr_user_id

    async def telemetry_worker(self) -> None:
        while self.running:
            func, payload, path = await self.telemetry_queue.get()
            try:
                await func(payload, path)
            except Exception:  # noqa: BLE001
                await logger.aerror("Error sending telemetry data")
            finally:
                self.telemetry_queue.task_done()

    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None) -> None:
        if self.do_not_track or self.posthog_client is None:
            await logger.adebug("Telemetry tracking is disabled.")
            return

        try:
            # Convert payload to dictionary using PostHog-friendly format
            payload_dict = payload.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)

            # Determine event name based on path or payload type
            event_name = self._get_event_name(payload, path)

            # Add common properties
            properties = {
                **payload_dict,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": path,
            }

            # Send to PostHog
            self.posthog_client.capture(
                distinct_id=self.user_id,
                event=event_name,
                properties=properties
            )

            await logger.adebug(f"Telemetry data sent successfully: {event_name}")
        except Exception as e:
            await logger.aerror(f"Failed to send telemetry data: {e}")

    def _get_event_name(self, payload: BaseModel, path: str | None = None) -> str:
        """Determine the event name based on payload type and path."""
        if path:
            return f"langflow_{path}"

        # Map payload types to event names
        if isinstance(payload, RunPayload):
            return "langflow_run"
        elif isinstance(payload, VersionPayload):
            return "langflow_version"
        elif isinstance(payload, PlaygroundPayload):
            return "langflow_playground"
        elif isinstance(payload, ComponentPayload):
            return "langflow_component"
        elif isinstance(payload, ExceptionPayload):
            return "langflow_exception"
        elif isinstance(payload, ShutdownPayload):
            return "langflow_shutdown"
        else:
            return "langflow_generic"

    async def log_package_run(self, payload: RunPayload) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "run"))

    async def log_package_shutdown(self) -> None:
        payload = ShutdownPayload(time_running=(datetime.now(timezone.utc) - self._start_time).seconds)
        await self._queue_event(payload)

    async def _queue_event(self, event_data) -> None:
        if self.do_not_track or self._stopping:
            return
        await self.telemetry_queue.put(event_data)

    def _get_langflow_desktop(self) -> bool:
        # Coerce to bool, could be 1, 0, True, False, "1", "0", "True", "False"
        return str(os.getenv("LANGFLOW_DESKTOP", "False")).lower() in {"1", "true"}

    async def log_package_version(self) -> None:
        python_version = ".".join(platform.python_version().split(".")[:2])
        version_info = get_version_info()
        if self.architecture is None:
            self.architecture = (await asyncio.to_thread(platform.architecture))[0]
        payload = VersionPayload(
            package=version_info["package"].lower(),
            version=version_info["version"],
            platform=platform.platform(),
            python=python_version,
            cache_type=self.settings_service.settings.cache_type,
            backend_only=self.settings_service.settings.backend_only,
            arch=self.architecture,
            auto_login=self.settings_service.auth_settings.AUTO_LOGIN,
            desktop=self._get_langflow_desktop(),
        )
        await self._queue_event((self.send_telemetry_data, payload, None))

    async def log_package_playground(self, payload: PlaygroundPayload) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "playground"))

    async def log_package_component(self, payload: ComponentPayload) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "component"))

    async def log_exception(self, exc: Exception, context: str) -> None:
        """Log unhandled exceptions to telemetry.

        Args:
            exc: The exception that occurred
            context: Context where exception occurred ("lifespan" or "handler")
        """
        # Get the stack trace and hash it for grouping similar exceptions
        stack_trace = traceback.format_exception(type(exc), exc, exc.__traceback__)
        stack_trace_str = "".join(stack_trace)
        #  Hash stack trace for grouping similar exceptions, truncated to save space
        stack_trace_hash = hashlib.sha256(stack_trace_str.encode()).hexdigest()[:16]

        payload = ExceptionPayload(
            exception_type=exc.__class__.__name__,
            exception_message=str(exc)[:500],  # Truncate long messages
            exception_context=context,
            stack_trace_hash=stack_trace_hash,
        )
        await self._queue_event((self.send_telemetry_data, payload, "exception"))

    def start(self) -> None:
        if self.running or self.do_not_track:
            return
        try:
            self.running = True
            self._start_time = datetime.now(timezone.utc)
            self.worker_task = asyncio.create_task(self.telemetry_worker())
            self.log_package_version_task = asyncio.create_task(self.log_package_version())
        except Exception:  # noqa: BLE001
            logger.exception("Error starting telemetry service")

    async def flush(self) -> None:
        if self.do_not_track:
            return
        try:
            await self.telemetry_queue.join()
        except Exception:  # noqa: BLE001
            await logger.aexception("Error flushing logs")

    @staticmethod
    async def _cancel_task(task: asyncio.Task, cancel_msg: str) -> None:
        task.cancel(cancel_msg)
        await asyncio.wait([task])
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                raise exc

    async def stop(self) -> None:
        if self.do_not_track or self._stopping:
            return
        try:
            self._stopping = True
            # flush all the remaining events and then stop
            await self.flush()
            self.running = False
            if self.worker_task:
                await self._cancel_task(self.worker_task, "Cancel telemetry worker task")
            if self.log_package_version_task:
                await self._cancel_task(self.log_package_version_task, "Cancel telemetry log package version task")
            
            # Flush PostHog client
            if self.posthog_client:
                try:
                    self.posthog_client.flush()
                    logger.debug("PostHog client flushed successfully")
                except Exception as e:
                    logger.error(f"Failed to flush PostHog client: {e}")
            
            await self.client.aclose()
        except Exception:  # noqa: BLE001
            await logger.aexception("Error stopping tracing service")

    async def teardown(self) -> None:
        await self.stop()
