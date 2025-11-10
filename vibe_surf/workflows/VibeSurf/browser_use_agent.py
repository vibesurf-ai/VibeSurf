import asyncio
import json
from typing import Any, List
from uuid import uuid4
from browser_use.llm.base import BaseChatModel
import os
from typing import Optional
from pydantic import BaseModel

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput, TableInput, MultilineInput
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


class BrowserUseAgentComponent(Component):
    display_name = "Browser Use Agent"
    description = "Browser Use Agent"
    icon = "bot"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
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
        BoolInput(
            name="flash_mode",
            display_name="Flash Mode",
            value=False,
            advanced=True,
            info="Flash mode for browser-use.",
        ),
        BoolInput(
            name="think_mode",
            display_name="Think Mode",
            value=True,
            advanced=True,
            info="Think mode for browser-use.",
        ),
        IntInput(
            name="max_steps",
            display_name="Max Steps",
            info="Max Steps for browser-use.",
            required=False,
            advanced=True,
            value=100
        )
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="pass_browser_session",
            types=["AgentBrowserSession"],
            group_outputs=True
        ),
        Output(
            display_name="Agent Result",
            name="agent_result",
            method="run_browser_use_agent",
            types=["Message"],
            group_outputs=True,
        ),
    ]

    _agent_result = None

    async def run_browser_use_agent(self) -> Message:
        try:
            from vibe_surf.backend import shared_state
            from vibe_surf.common import get_workspace_dir

            bu_tools = BrowserUseTools()
            for mcp_server_name, mcp_client in shared_state.vibesurf_tools.mcp_clients.items():
                await mcp_client.register_to_tools(
                    tools=bu_tools,
                    prefix=f"mcp.{mcp_server_name}."
                )
            if hasattr(self, "graph"):
                session_id = self.graph.session_id
            elif hasattr(self, "_session_id"):
                session_id = self._session_id
            else:
                session_id = None

            workspace_dir = get_workspace_dir()
            bu_agent_workdir = os.path.join(workspace_dir, "workflows", "agents", f"{self._id}-{session_id}")
            os.makedirs(bu_agent_workdir, exist_ok=True)
            agent = BrowserUseAgent(
                task=self.task,
                llm=self.llm,
                browser_session=self.browser_session,
                tools=bu_tools,
                file_system_path=str(bu_agent_workdir),
                extend_system_message=self.extend_system_prompt,
                flash_mode=self.flash_mode,
                use_thinking=self.think_mode,
            )

            agent_result = await agent.run(max_steps=self.max_steps)
            self._agent_result = agent_result

            if agent_result.is_successful():
                return Message(
                    text=agent_result.final_result() if hasattr(agent_result, 'final_result') else "Task completed")
            else:
                return Message(text=str(agent_result.errors()) if agent_result.has_errors() else "")

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    async def pass_browser_session(self) -> AgentBrowserSession:
        if not self._agent_result:
            await self.run_browser_use_agent()
        return self.browser_session
