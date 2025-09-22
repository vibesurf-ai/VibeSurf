from browser_use.tools.registry.service import Registry, Context
import asyncio
import functools
import inspect
import logging
import re
from collections.abc import Callable
from inspect import Parameter, iscoroutinefunction, signature
from types import UnionType
from typing import Any, Generic, Optional, TypeVar, Union, get_args, get_origin

import pyotp
from pydantic import BaseModel, Field, RootModel, create_model

from browser_use.browser import BrowserSession
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.base import BaseChatModel
from browser_use.observability import observe_debug
from browser_use.telemetry.service import ProductTelemetry
from browser_use.tools.registry.views import (
    ActionModel,
    ActionRegistry,
    RegisteredAction,
    SpecialActionParameters,
)
from browser_use.utils import is_new_tab_page, match_url_with_domain_pattern, time_execution_async

from vibe_surf.logger import get_logger
from vibe_surf.browser.browser_manager import BrowserManager

logger = get_logger(__name__)


class VibeSurfRegistry(Registry):
    def _get_special_param_types(self) -> dict[str, type | UnionType | None]:
        """Get the expected types for special parameters from SpecialActionParameters"""
        # Manually define the expected types to avoid issues with Optional handling.
        # we should try to reduce this list to 0 if possible, give as few standardized objects to all the actions
        # but each driver should decide what is relevant to expose the action methods,
        # e.g. CDP client, 2fa code getters, sensitive_data wrappers, other context, etc.
        return {
            'context': None,  # Context is a TypeVar, so we can't validate type
            'browser_session': BrowserSession,
            'page_url': str,
            'cdp_client': None,  # CDPClient type from cdp_use, but we don't import it here
            'page_extraction_llm': BaseChatModel,
            'available_file_paths': list,
            'has_sensitive_data': bool,
            'file_system': FileSystem,
            'llm': BaseChatModel,
            'browser_manager': BrowserManager
        }
