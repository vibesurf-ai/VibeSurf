"""Backwards compatibility module for vibe_surf.backend.langflow.base.

This module imports from lfx.base to maintain compatibility with existing code
that expects to import from vibe_surf.backend.langflow.base.
"""

# Import all base modules from lfx for backwards compatibility
from lfx.base import *  # noqa: F403
