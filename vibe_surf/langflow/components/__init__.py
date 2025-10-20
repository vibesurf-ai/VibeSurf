"""LangFlow Components module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibe_surf.langflow.components._importing import import_mod

if TYPE_CHECKING:
    from vibe_surf.langflow.components import (
        Notion,
        agentql,
        agents,
        aiml,
        amazon,
        anthropic,
        apify,
        arxiv,
        assemblyai,
        azure,
        baidu,
        bing,
        cleanlab,
        cloudflare,
        cohere,
        composio,
        confluence,
        crewai,
        custom_component,
        data,
        datastax,
        deepseek,
        docling,
        duckduckgo,
        embeddings,
        exa,
        firecrawl,
        git,
        glean,
        google,
        groq,
        helpers,
        homeassistant,
        huggingface,
        ibm,
        icosacomputing,
        input_output,
        langchain_utilities,
        langwatch,
        lmstudio,
        logic,
        maritalk,
        mem0,
        mistral,
        models,
        needle,
        notdiamond,
        novita,
        nvidia,
        olivya,
        ollama,
        openai,
        openrouter,
        perplexity,
        processing,
        redis,
        sambanova,
        scrapegraph,
        searchapi,
        serpapi,
        tavily,
        tools,
        twelvelabs,
        unstructured,
        vectorstores,
        vertexai,
        wikipedia,
        wolframalpha,
        xai,
        yahoosearch,
        youtube,
        zep,
    )

_dynamic_imports = {
    "agents": "vibe_surf.langflow.components.agents",
    "data": "vibe_surf.langflow.components.data",
    "processing": "vibe_surf.langflow.components.processing",
    "vectorstores": "vibe_surf.langflow.components.vectorstores",
    "tools": "vibe_surf.langflow.components.tools",
    "models": "vibe_surf.langflow.components.models",
    "embeddings": "vibe_surf.langflow.components.embeddings",
    "helpers": "vibe_surf.langflow.components.helpers",
    "input_output": "vibe_surf.langflow.components.input_output",
    "logic": "vibe_surf.langflow.components.logic",
    "custom_component": "vibe_surf.langflow.components.custom_component",
    "openai": "vibe_surf.langflow.components.openai",
    "anthropic": "vibe_surf.langflow.components.anthropic",
    "google": "vibe_surf.langflow.components.google",
    "azure": "vibe_surf.langflow.components.azure",
    "huggingface": "vibe_surf.langflow.components.huggingface",
    "ollama": "vibe_surf.langflow.components.ollama",
    "groq": "vibe_surf.langflow.components.groq",
    "cohere": "vibe_surf.langflow.components.cohere",
    "mistral": "vibe_surf.langflow.components.mistral",
    "deepseek": "vibe_surf.langflow.components.deepseek",
    "nvidia": "vibe_surf.langflow.components.nvidia",
    "amazon": "vibe_surf.langflow.components.amazon",
    "vertexai": "vibe_surf.langflow.components.vertexai",
    "xai": "vibe_surf.langflow.components.xai",
    "perplexity": "vibe_surf.langflow.components.perplexity",
    "openrouter": "vibe_surf.langflow.components.openrouter",
    "lmstudio": "vibe_surf.langflow.components.lmstudio",
    "sambanova": "vibe_surf.langflow.components.sambanova",
    "maritalk": "vibe_surf.langflow.components.maritalk",
    "novita": "vibe_surf.langflow.components.novita",
    "olivya": "vibe_surf.langflow.components.olivya",
    "notdiamond": "vibe_surf.langflow.components.notdiamond",
    "needle": "vibe_surf.langflow.components.needle",
    "cloudflare": "vibe_surf.langflow.components.cloudflare",
    "baidu": "vibe_surf.langflow.components.baidu",
    "aiml": "vibe_surf.langflow.components.aiml",
    "ibm": "vibe_surf.langflow.components.ibm",
    "langchain_utilities": "vibe_surf.langflow.components.langchain_utilities",
    "crewai": "vibe_surf.langflow.components.crewai",
    "composio": "vibe_surf.langflow.components.composio",
    "mem0": "vibe_surf.langflow.components.mem0",
    "datastax": "vibe_surf.langflow.components.datastax",
    "cleanlab": "vibe_surf.langflow.components.cleanlab",
    "langwatch": "vibe_surf.langflow.components.langwatch",
    "icosacomputing": "vibe_surf.langflow.components.icosacomputing",
    "homeassistant": "vibe_surf.langflow.components.homeassistant",
    "agentql": "vibe_surf.langflow.components.agentql",
    "assemblyai": "vibe_surf.langflow.components.assemblyai",
    "twelvelabs": "vibe_surf.langflow.components.twelvelabs",
    "docling": "vibe_surf.langflow.components.docling",
    "unstructured": "vibe_surf.langflow.components.unstructured",
    "redis": "vibe_surf.langflow.components.redis",
    "zep": "vibe_surf.langflow.components.zep",
    "bing": "vibe_surf.langflow.components.bing",
    "duckduckgo": "vibe_surf.langflow.components.duckduckgo",
    "serpapi": "vibe_surf.langflow.components.serpapi",
    "searchapi": "vibe_surf.langflow.components.searchapi",
    "tavily": "vibe_surf.langflow.components.tavily",
    "exa": "vibe_surf.langflow.components.exa",
    "glean": "vibe_surf.langflow.components.glean",
    "yahoosearch": "vibe_surf.langflow.components.yahoosearch",
    "apify": "vibe_surf.langflow.components.apify",
    "arxiv": "vibe_surf.langflow.components.arxiv",
    "confluence": "vibe_surf.langflow.components.confluence",
    "firecrawl": "vibe_surf.langflow.components.firecrawl",
    "git": "vibe_surf.langflow.components.git",
    "wikipedia": "vibe_surf.langflow.components.wikipedia",
    "youtube": "vibe_surf.langflow.components.youtube",
    "scrapegraph": "vibe_surf.langflow.components.scrapegraph",
    "Notion": "vibe_surf.langflow.components.Notion",
    "wolframalpha": "vibe_surf.langflow.components.wolframalpha",
}

__all__: list[str] = [
    "Notion",
    "agentql",
    "agents",
    "aiml",
    "amazon",
    "anthropic",
    "apify",
    "arxiv",
    "assemblyai",
    "azure",
    "baidu",
    "bing",
    "cleanlab",
    "cloudflare",
    "cohere",
    "composio",
    "confluence",
    "crewai",
    "custom_component",
    "data",
    "datastax",
    "deepseek",
    "docling",
    "duckduckgo",
    "embeddings",
    "exa",
    "firecrawl",
    "git",
    "glean",
    "google",
    "groq",
    "helpers",
    "homeassistant",
    "huggingface",
    "ibm",
    "icosacomputing",
    "input_output",
    "langchain_utilities",
    "langwatch",
    "lmstudio",
    "logic",
    "maritalk",
    "mem0",
    "mistral",
    "models",
    "needle",
    "notdiamond",
    "novita",
    "nvidia",
    "olivya",
    "ollama",
    "openai",
    "openrouter",
    "perplexity",
    "processing",
    "redis",
    "sambanova",
    "scrapegraph",
    "searchapi",
    "serpapi",
    "tavily",
    "tools",
    "twelvelabs",
    "unstructured",
    "vectorstores",
    "vertexai",
    "wikipedia",
    "wolframalpha",
    "xai",
    "yahoosearch",
    "youtube",
    "zep",
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
