"""
Telemetry for VibeSurf.
"""

from typing import TYPE_CHECKING

# Type stubs for lazy imports
if TYPE_CHECKING:
    from vibe_surf.telemetry.service import ProductTelemetry
    from vibe_surf.telemetry.views import (
        BaseTelemetryEvent,
        CLITelemetryEvent,
        MCPClientTelemetryEvent,
        MCPServerTelemetryEvent,
        VibeSurfAgentTelemetryEvent,
        ReportWriterTelemetryEvent,
        BackendTelemetryEvent,
    )

# Lazy imports mapping
_LAZY_IMPORTS = {
    'ProductTelemetry': ('vibe_surf.telemetry.service', 'ProductTelemetry'),
    'BaseTelemetryEvent': ('vibe_surf.telemetry.views', 'BaseTelemetryEvent'),
    'CLITelemetryEvent': ('vibe_surf.telemetry.views', 'CLITelemetryEvent'),
    'MCPClientTelemetryEvent': ('vibe_surf.telemetry.views', 'MCPClientTelemetryEvent'),
    'MCPServerTelemetryEvent': ('vibe_surf.telemetry.views', 'MCPServerTelemetryEvent'),
    'VibeSurfAgentTelemetryEvent': ('vibe_surf.telemetry.views', 'VibeSurfAgentTelemetryEvent'),
    'ReportWriterTelemetryEvent': ('vibe_surf.telemetry.views', 'ReportWriterTelemetryEvent'),
    'BackendTelemetryEvent': ('vibe_surf.telemetry.views', 'BackendTelemetryEvent'),
}


def __getattr__(name: str):
    """Lazy import mechanism for telemetry components."""
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        try:
            from importlib import import_module

            module = import_module(module_path)
            attr = getattr(module, attr_name)
            # Cache the imported attribute in the module's globals
            globals()[name] = attr
            return attr
        except ImportError as e:
            raise ImportError(f'Failed to import {name} from {module_path}: {e}') from e

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    'BaseTelemetryEvent',
    'ProductTelemetry',
    'CLITelemetryEvent',
    'MCPClientTelemetryEvent',
    'MCPServerTelemetryEvent',
    'VibeSurfAgentTelemetryEvent',
    'ReportWriterTelemetryEvent',
    'BackendTelemetryEvent',
]
