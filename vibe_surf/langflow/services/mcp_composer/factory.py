"""Factory for creating MCP Composer service instances."""

from vibe_surf.langflow.services.factory import ServiceFactory
from vibe_surf.langflow.services.mcp_composer.service import MCPComposerService


class MCPComposerServiceFactory(ServiceFactory):
    """Factory for creating MCP Composer service instances."""

    def __init__(self):
        super().__init__(MCPComposerService)

    def create(self):
        """Create a new MCP Composer service instance."""
        return MCPComposerService()
