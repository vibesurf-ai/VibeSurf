"""LangFlow Components module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibe_surf.langflow.components._importing import import_mod

if TYPE_CHECKING:
    from vibe_surf.langflow.components import (
        Notion,
        agents,
        amazon,
        anthropic,
        azure,
        bing,
        composio,
        custom_component,
        data,
        deepseek,
        duckduckgo,
        git,
        google,
        groq,
        helpers,
        input_output,
        langchain_utilities,
        logic,
        models,
        openai,
        openrouter,
        processing,
        tools,
        vertexai,
        xai,
        youtube
    )

_dynamic_imports = {
    "agents": "vibe_surf.langflow.components.agents",
    "data": "vibe_surf.langflow.components.data",
    "processing": "vibe_surf.langflow.components.processing",
    "tools": "vibe_surf.langflow.components.tools",
    "models": "vibe_surf.langflow.components.models",
    "helpers": "vibe_surf.langflow.components.helpers",
    "input_output": "vibe_surf.langflow.components.input_output",
    "logic": "vibe_surf.langflow.components.logic",
    "custom_component": "vibe_surf.langflow.components.custom_component",
    "openai": "vibe_surf.langflow.components.openai",
    "anthropic": "vibe_surf.langflow.components.anthropic",
    "google": "vibe_surf.langflow.components.google",
    "azure": "vibe_surf.langflow.components.azure",
    "groq": "vibe_surf.langflow.components.groq",
    "deepseek": "vibe_surf.langflow.components.deepseek",
    "amazon": "vibe_surf.langflow.components.amazon",
    "vertexai": "vibe_surf.langflow.components.vertexai",
    "xai": "vibe_surf.langflow.components.xai",
    "openrouter": "vibe_surf.langflow.components.openrouter",
    "langchain_utilities": "vibe_surf.langflow.components.langchain_utilities",
    "composio": "vibe_surf.langflow.components.composio",
    "bing": "vibe_surf.langflow.components.bing",
    "duckduckgo": "vibe_surf.langflow.components.duckduckgo",
    "git": "vibe_surf.langflow.components.git",
    "youtube": "vibe_surf.langflow.components.youtube",
    "Notion": "vibe_surf.langflow.components.Notion",
}

__all__: list[str] = [
    "Notion",
    "agents",
    "amazon",
    "anthropic",
    "azure",
    "bing",
    "composio",
    "custom_component",
    "data",
    "deepseek",
    "duckduckgo",
    "git",
    "google",
    "groq",
    "helpers",
    "input_output",
    "langchain_utilities",
    "logic",
    "models",
    "openai",
    "openrouter",
    "processing",
    "tools",
    "vertexai",
    "xai",
    "youtube"
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import component modules on attribute access.

    Args:
        attr_name (str): The attribute/module name to import.

    Returns:
        Any: The imported module or attribute.

    Raises:
        AttributeError: If the attribute is not a known component or cannot be imported.
    """
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        # Use import_mod as in LangChain, passing the module name and package
        result = import_mod(attr_name, "__module__", __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result  # Cache for future access
    return result


def __dir__() -> list[str]:
    """Return list of available attributes for tab-completion and dir()."""
    return list(__all__)


# Optional: Consistency check (can be removed in production)
_missing = set(__all__) - set(_dynamic_imports)
if _missing:
    msg = f"Missing dynamic import mapping for: {', '.join(_missing)}"
    raise ImportError(msg)
