import asyncio
import logging
import time
from typing import Any

from browser_use.telemetry import MCPClientTelemetryEvent
from browser_use.utils import get_browser_use_version
from browser_use.mcp.client import MCPClient
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from vibe_surf.telemetry.service import ProductTelemetry
from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class CustomMCPClient(MCPClient):
    def __init__(
            self,
            server_name: str,
            command: str,
            args: list[str] | None = None,
            env: dict[str, str] | None = None,
    ):
        """Initialize MCP client.

        Args:
            server_name: Name of the MCP server (for logging and identification)
            command: Command to start the MCP server (e.g., "npx", "python")
            args: Arguments for the command (e.g., ["@playwright/mcp@latest"])
            env: Environment variables for the server process
        """
        super().__init__(server_name=server_name, command=command, args=args, env=env)

        self._telemetry = ProductTelemetry()

    async def connect(self, timeout: int = 200) -> None:
        """Connect to the MCP server and discover available tools."""
        if self._connected:
            logger.debug(f'Already connected to {self.server_name}')
            return

        start_time = time.time()
        error_msg = None

        try:
            logger.info(f"🔌 Connecting to MCP server '{self.server_name}': {self.command} {' '.join(self.args)}")

            # Create server parameters
            server_params = StdioServerParameters(command=self.command, args=self.args, env=self.env)

            # Start stdio client in background task
            self._stdio_task = asyncio.create_task(self._run_stdio_client(server_params))

            # Wait for connection to be established
            retries = 0
            max_retries = timeout / 0.1  # 10 second timeout (increased for parallel test execution)
            while not self._connected and retries < max_retries:
                await asyncio.sleep(0.1)
                retries += 1

            if not self._connected:
                error_msg = f"Failed to connect to MCP server '{self.server_name}' after {max_retries * 0.1} seconds"
                raise RuntimeError(error_msg)

            logger.info(f"📦 Discovered {len(self._tools)} tools from '{self.server_name}': {list(self._tools.keys())}")

        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            # Capture telemetry for connect action
            duration = time.time() - start_time
            self._telemetry.capture(
                MCPClientTelemetryEvent(
                    server_name=self.server_name,
                    command=self.command,
                    tools_discovered=len(self._tools),
                    version=get_browser_use_version(),
                    action='connect',
                    duration_seconds=duration,
                    error_message=error_msg,
                )
            )
