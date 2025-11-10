import asyncio
import json
from typing import Any, List
from uuid import uuid4
from browser_use.llm.base import BaseChatModel
import os
from typing import Optional
from pydantic import BaseModel

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput, TableInput, MultilineInput, \
    FileInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.schema.data import Data
from vibe_surf.langflow.schema.dataframe import DataFrame
from vibe_surf.langflow.schema.table import EditMode
from vibe_surf.langflow.helpers.base_model import build_model_from_schema
from vibe_surf.agents.browser_use_agent import BrowserUseAgent
from vibe_surf.tools.browser_use_tools import BrowserUseTools
from vibe_surf.langflow.field_typing import LanguageModel

class VibeSurfAgentComponent(Component):
    display_name = "VibeSurf Agent"
    description = "VibeSurf Agent"
    icon = "bot"

    inputs = [
        MultilineInput(
            name="task",
            display_name="Task",
            info="Task for browser-use.",
            required=True,

        ),
        HandleInput(
            name="llm",
            display_name="LLM Model",
            info="LLM Model defined by VibeSurf",
            input_types=["LanguageModel"],
            required=True
        ),
        MultilineInput(
            name="extend_system_prompt",
            display_name="Extend System Prompt",
            info="Extend system prompt for browser-use.",
            required=False,
            advanced=True
        ),
        FileInput(
            name="upload_files",
            display_name="Upload Files",
            info="Upload Files defined by VibeSurf workspace",
            advanced=True,
            list=True,
            fileTypes=['json', 'md', 'csv', 'pdf', 'png', 'jpg', 'jpeg', 'txt', 'py', 'js'],
        ),
        DropdownInput(
            name="agent_mode",
            display_name="Agent Mode",
            options=["thinking", "non-thinking", "flash"],
            value="thinking",
            advanced=True,
            info="VibeSurf agent mode.",
        )
    ]

    outputs = [
        Output(
            display_name="Agent Result",
            name="agent_result",
            method="run_vibesurf_agent",
            types=["Message"],
            group_outputs=True,
        ),
    ]

    _agent_result = None

    async def run_vibesurf_agent(self) -> Message:
        try:
            from vibe_surf.backend import shared_state
            from vibe_surf.common import get_workspace_dir
            from vibe_surf.agents.vibe_surf_agent import VibeSurfAgent

            if hasattr(self, "graph"):
                session_id = self.graph.session_id
            elif hasattr(self, "_session_id"):
                session_id = self._session_id
            else:
                session_id = None

            workspace_dir = get_workspace_dir()
            os.makedirs(workspace_dir, exist_ok=True)
            vibesurf_agent = VibeSurfAgent(
                llm=self.llm,
                browser_manager=shared_state.browser_manager,
                tools=shared_state.vibesurf_tools,
                workspace_dir=workspace_dir,
                extend_system_prompt=self.extend_system_prompt
            )

            agent_result = await vibesurf_agent.run(task=self.task, session_id=session_id,
                                                    upload_files=self.upload_files, agent_mode=self.agent_mode)
            self._agent_result = agent_result

            return Message(text=self._agent_result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
