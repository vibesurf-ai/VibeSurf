"""Langflow backwards compatibility layer.

This module provides backwards compatibility by forwarding imports from
vibe_surf.backend.langflow.* to lfx.* to maintain compatibility with existing code that
references the old langflow module structure.
"""

import importlib
import importlib.util
import sys
from types import ModuleType
from typing import Any


class LangflowCompatibilityModule(ModuleType):
    """A module that forwards attribute access to the corresponding lfx module."""

    def __init__(self, name: str, lfx_module_name: str):
        super().__init__(name)
        self._lfx_module_name = lfx_module_name
        self._lfx_module = None

    def _get_lfx_module(self):
        """Lazily import and cache the lfx module."""
        if self._lfx_module is None:
            try:
                self._lfx_module = importlib.import_module(self._lfx_module_name)
            except ImportError as e:
                msg = f"Cannot import {self._lfx_module_name} for backwards compatibility with {self.__name__}"
                raise ImportError(msg) from e
        return self._lfx_module

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the lfx module with caching."""
        lfx_module = self._get_lfx_module()
        try:
            attr = getattr(lfx_module, name)
        except AttributeError as e:
            msg = f"module '{self.__name__}' has no attribute '{name}'"
            raise AttributeError(msg) from e
        else:
            # Cache the attribute in our __dict__ for faster subsequent access
            setattr(self, name, attr)
            return attr

    def __dir__(self):
        """Return directory of the lfx module."""
        try:
            lfx_module = self._get_lfx_module()
            return dir(lfx_module)
        except ImportError:
            return []


def _setup_compatibility_modules():
    """Set up comprehensive compatibility modules for vibe_surf.backend.langflow.base imports."""
    # First, set up the base attribute on this module (langflow)
    current_module = sys.modules[__name__]

    # Define all the modules we need to support
    module_mappings = {
        # Core base module
        "vibe_surf.backend.langflow.base": "lfx.base",
        # Inputs module - critical for class identity
        "vibe_surf.backend.langflow.inputs": "lfx.inputs",
        "vibe_surf.backend.langflow.inputs.inputs": "lfx.inputs.inputs",
        # Schema modules - also critical for class identity
        "vibe_surf.backend.langflow.schema": "lfx.schema",
        "vibe_surf.backend.langflow.schema.data": "lfx.schema.data",
        "vibe_surf.backend.langflow.schema.serialize": "lfx.schema.serialize",
        # Template modules
        "vibe_surf.backend.langflow.template": "lfx.template",
        "vibe_surf.backend.langflow.template.field": "lfx.template.field",
        "vibe_surf.backend.langflow.template.field.base": "lfx.template.field.base",
        # Components modules
        "vibe_surf.backend.langflow.components": "lfx.components",
        "vibe_surf.backend.langflow.components.helpers": "lfx.components.helpers",
        "vibe_surf.backend.langflow.components.helpers.calculator_core": "lfx.components.helpers.calculator_core",
        "vibe_surf.backend.langflow.components.helpers.create_list": "lfx.components.helpers.create_list",
        "vibe_surf.backend.langflow.components.helpers.current_date": "lfx.components.helpers.current_date",
        "vibe_surf.backend.langflow.components.helpers.id_generator": "lfx.components.helpers.id_generator",
        "vibe_surf.backend.langflow.components.helpers.memory": "lfx.components.helpers.memory",
        "vibe_surf.backend.langflow.components.helpers.output_parser": "lfx.components.helpers.output_parser",
        "vibe_surf.backend.langflow.components.helpers.store_message": "lfx.components.helpers.store_message",
        # Individual modules that exist in lfx
        "vibe_surf.backend.langflow.base.agents": "lfx.base.agents",
        "vibe_surf.backend.langflow.base.chains": "lfx.base.chains",
        "vibe_surf.backend.langflow.base.data": "lfx.base.data",
        "vibe_surf.backend.langflow.base.data.utils": "lfx.base.data.utils",
        "vibe_surf.backend.langflow.base.document_transformers": "lfx.base.document_transformers",
        "vibe_surf.backend.langflow.base.embeddings": "lfx.base.embeddings",
        "vibe_surf.backend.langflow.base.flow_processing": "lfx.base.flow_processing",
        "vibe_surf.backend.langflow.base.io": "lfx.base.io",
        "vibe_surf.backend.langflow.base.io.chat": "lfx.base.io.chat",
        "vibe_surf.backend.langflow.base.io.text": "lfx.base.io.text",
        "vibe_surf.backend.langflow.base.langchain_utilities": "lfx.base.langchain_utilities",
        "vibe_surf.backend.langflow.base.memory": "lfx.base.memory",
        "vibe_surf.backend.langflow.base.models": "lfx.base.models",
        "vibe_surf.backend.langflow.base.models.google_generative_ai_constants": "lfx.base.models.google_generative_ai_constants",
        "vibe_surf.backend.langflow.base.models.openai_constants": "lfx.base.models.openai_constants",
        "vibe_surf.backend.langflow.base.models.anthropic_constants": "lfx.base.models.anthropic_constants",
        "vibe_surf.backend.langflow.base.models.aiml_constants": "lfx.base.models.aiml_constants",
        "vibe_surf.backend.langflow.base.models.aws_constants": "lfx.base.models.aws_constants",
        "vibe_surf.backend.langflow.base.models.groq_constants": "lfx.base.models.groq_constants",
        "vibe_surf.backend.langflow.base.models.novita_constants": "lfx.base.models.novita_constants",
        "vibe_surf.backend.langflow.base.models.ollama_constants": "lfx.base.models.ollama_constants",
        "vibe_surf.backend.langflow.base.models.sambanova_constants": "lfx.base.models.sambanova_constants",
        "vibe_surf.backend.langflow.base.models.cometapi_constants": "lfx.base.models.cometapi_constants",
        "vibe_surf.backend.langflow.base.prompts": "lfx.base.prompts",
        "vibe_surf.backend.langflow.base.prompts.api_utils": "lfx.base.prompts.api_utils",
        "vibe_surf.backend.langflow.base.prompts.utils": "lfx.base.prompts.utils",
        "vibe_surf.backend.langflow.base.textsplitters": "lfx.base.textsplitters",
        "vibe_surf.backend.langflow.base.tools": "lfx.base.tools",
        "vibe_surf.backend.langflow.base.vectorstores": "lfx.base.vectorstores",
    }

    # Create compatibility modules for each mapping
    for langflow_name, lfx_name in module_mappings.items():
        if langflow_name not in sys.modules:
            # Check if the lfx module exists
            try:
                spec = importlib.util.find_spec(lfx_name)
                if spec is not None:
                    # Create compatibility module
                    compat_module = LangflowCompatibilityModule(langflow_name, lfx_name)
                    sys.modules[langflow_name] = compat_module

                    # Set up the module hierarchy
                    parts = langflow_name.split(".")
                    if len(parts) > 1:
                        parent_name = ".".join(parts[:-1])
                        parent_module = sys.modules.get(parent_name)
                        if parent_module is not None:
                            setattr(parent_module, parts[-1], compat_module)

                    # Special handling for top-level modules
                    if langflow_name == "vibe_surf.backend.langflow.base":
                        current_module.base = compat_module
                    elif langflow_name == "vibe_surf.backend.langflow.inputs":
                        current_module.inputs = compat_module
                    elif langflow_name == "vibe_surf.backend.langflow.schema":
                        current_module.schema = compat_module
                    elif langflow_name == "vibe_surf.backend.langflow.template":
                        current_module.template = compat_module
                    elif langflow_name == "vibe_surf.backend.langflow.components":
                        current_module.components = compat_module
            except (ImportError, ValueError):
                # Skip modules that don't exist in lfx
                continue

    # Handle modules that exist only in langflow (like knowledge_bases)
    # These need special handling because they're not in lfx yet
    langflow_only_modules = {
        "vibe_surf.backend.langflow.base.data.kb_utils": "vibe_surf.backend.langflow.base.data.kb_utils",
        "vibe_surf.backend.langflow.base.knowledge_bases": "vibe_surf.backend.langflow.base.knowledge_bases",
        "vibe_surf.backend.langflow.components.knowledge_bases": "vibe_surf.backend.langflow.components.knowledge_bases",
    }

    for langflow_name in langflow_only_modules:
        if langflow_name not in sys.modules:
            try:
                # Try to find the actual physical module file
                from pathlib import Path

                base_dir = Path(__file__).parent

                if langflow_name == "vibe_surf.backend.langflow.base.data.kb_utils":
                    kb_utils_file = base_dir / "base" / "data" / "kb_utils.py"
                    if kb_utils_file.exists():
                        spec = importlib.util.spec_from_file_location(langflow_name, kb_utils_file)
                        if spec is not None and spec.loader is not None:
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[langflow_name] = module
                            spec.loader.exec_module(module)

                            # Also add to parent module
                            parent_module = sys.modules.get("vibe_surf.backend.langflow.base.data")
                            if parent_module is not None:
                                parent_module.kb_utils = module

                elif langflow_name == "vibe_surf.backend.langflow.base.knowledge_bases":
                    kb_dir = base_dir / "base" / "knowledge_bases"
                    kb_init_file = kb_dir / "__init__.py"
                    if kb_init_file.exists():
                        spec = importlib.util.spec_from_file_location(langflow_name, kb_init_file)
                        if spec is not None and spec.loader is not None:
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[langflow_name] = module
                            spec.loader.exec_module(module)

                            # Also add to parent module
                            parent_module = sys.modules.get("vibe_surf.backend.langflow.base")
                            if parent_module is not None:
                                parent_module.knowledge_bases = module

                elif langflow_name == "vibe_surf.backend.langflow.components.knowledge_bases":
                    components_kb_dir = base_dir / "components" / "knowledge_bases"
                    components_kb_init_file = components_kb_dir / "__init__.py"
                    if components_kb_init_file.exists():
                        spec = importlib.util.spec_from_file_location(langflow_name, components_kb_init_file)
                        if spec is not None and spec.loader is not None:
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[langflow_name] = module
                            spec.loader.exec_module(module)

                            # Also add to parent module
                            parent_module = sys.modules.get("vibe_surf.backend.langflow.components")
                            if parent_module is not None:
                                parent_module.knowledge_bases = module
            except (ImportError, AttributeError):
                # If direct file loading fails, skip silently
                continue


# Set up all the compatibility modules
_setup_compatibility_modules()
