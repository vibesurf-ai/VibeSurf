import asyncio
import pdb
from typing import Any, List
from uuid import uuid4
from browser_use.llm.base import BaseChatModel

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.schema.dotdict import dotdict
from vibe_surf.langflow.field_typing import LanguageModel

class LLMProfilesComponent(Component):
    display_name = "LLM profiles"
    description = "Available llm profiles"
    icon = "brain"

    inputs = [
        DropdownInput(
            name="llm_profile_name",
            display_name="LLM profile",
            info="LLM profile name",
            options=[],  
            value=None,
            real_time_refresh=True
        )
    ]

    outputs = [
        Output(
            display_name="LLM Model",
            name="llm_model",
            method="get_llm_profile_model",
            types=["LanguageModel"]
        )
    ]

    async def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        """Update build config with dynamic LLM profile options."""
        if field_name == "llm_profile_name":
            # Get LLM profiles dynamically
            llm_profile_options = await self.get_llm_profile_names()
            build_config[field_name]["options"] = llm_profile_options

            if "value" in build_config[field_name] and not build_config[field_name]["value"]:
                default_llm_profile = await self.get_default_llm_profiles()
                if default_llm_profile:
                    build_config[field_name]["value"] = default_llm_profile[0]
        return build_config

    async def get_llm_profile_names(self) -> list[str]:
        """Get all available LLM profile names."""
        try:
            from vibe_surf.backend.database.queries import LLMProfileQueries
            from vibe_surf.backend import shared_state
            from vibe_surf.backend.utils.llm_factory import create_llm_from_profile

            async for db_session in shared_state.db_manager.get_session():
                profiles = await LLMProfileQueries.list_profiles(
                    db=db_session,
                    active_only=True,
                    limit=1000,
                    offset=0
                )
                return [profile.profile_name for profile in profiles if profile.profile_name]
        except Exception:
            return []

    async def get_default_llm_profiles(self) -> list[str]:
        """Get default LLM profile names."""
        try:
            from vibe_surf.backend.database.queries import LLMProfileQueries
            from vibe_surf.backend import shared_state
            from vibe_surf.backend.utils.llm_factory import create_llm_from_profile

            async for db_session in shared_state.db_manager.get_session():
                profiles = await LLMProfileQueries.list_profiles(
                    db=db_session,
                    active_only=True,
                    limit=1000,
                    offset=0
                )
                return [profile.profile_name for profile in profiles if profile.is_default]
        except Exception:
            return []

    async def get_llm_profile_model(self) -> LanguageModel:
        """Get the LLM model from the selected profile."""
        from vibe_surf.backend.database.queries import LLMProfileQueries
        from vibe_surf.backend import shared_state
        from vibe_surf.backend.utils.llm_factory import create_llm_from_profile

        async for db_session in shared_state.db_manager.get_session():
            llm_profile = await LLMProfileQueries.get_profile_with_decrypted_key(db_session, self.llm_profile_name)
            if not llm_profile:
                self.status = f"{self.llm_profile_name} not found!"
                raise ValueError(self.status)

            llm = create_llm_from_profile(llm_profile)

            return llm
