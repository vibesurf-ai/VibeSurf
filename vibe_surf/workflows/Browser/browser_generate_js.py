import asyncio
import json
from typing import Any, List
from uuid import uuid4
from browser_use.llm.base import BaseChatModel
import os
from typing import Optional
from pydantic import BaseModel

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput, TableInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.schema.data import Data
from vibe_surf.langflow.schema.dataframe import DataFrame
from vibe_surf.langflow.schema.table import EditMode
from vibe_surf.langflow.helpers.base_model import build_model_from_schema
from vibe_surf.tools.utils import generate_java_script_code
from vibe_surf.langflow.field_typing import LanguageModel

class BrowserGenerateJavaScriptComponent(Component):
    display_name = "Generate JavaScript Code"
    description = "Browser generates JavaScript code"
    icon = "code"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MessageTextInput(
            name="code_requirement",
            display_name="Code Requirement",
            info="Requirement for generating JavaScript code",
            required=True
        ),
        HandleInput(
            name="llm",
            display_name="LLM Model",
            info="LLM Model defined by VibeSurf",
            input_types=["LanguageModel"],
            required=True
        ),
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
            display_name="Generated Result",
            name="generated_result",
            method="gen_js_code",
            types=["Data"],
            group_outputs=True,
        ),
    ]
    async def gen_js_code(self) -> Data:
        try:
            success, execute_result, js_code = await generate_java_script_code(self.code_requirement, self.llm,
                                                                               self.browser_session)
            if not success:
                self.status = "Failed to generate JS code."
            else:
                self.status = "Successfully generated JS code."
            return Data(data={
                "success": success,
                "execute_result": execute_result,
                "js_code": js_code,
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    async def pass_browser_session(self) -> AgentBrowserSession:
        return self.browser_session
