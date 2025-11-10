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
from vibe_surf.langflow.field_typing import LanguageModel

class BrowserExtractContentComponent(Component):
    display_name = "Extract Content"
    description = "Browser extract content"
    icon = "text-search"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MessageTextInput(
            name="extract_goal",
            display_name="Extract Goal",
            info="Goal for extraction.",
            required=True
        ),
        HandleInput(
            name="llm",
            display_name="LLM Model",
            info="LLM Model defined by VibeSurf",
            input_types=["LanguageModel"],
            required=True
        ),
        BoolInput(
            name="structured_output",
            display_name="Structured Output",
            info="Structured Output for extracted content.",
            real_time_refresh=True,
            value=False
        ),
        TableInput(
            name="output_schema",
            display_name="Output Schema",
            info="Define the structure and data types for the model's output.",
            required=False,
            table_schema=[
                {
                    "name": "name",
                    "display_name": "Name",
                    "type": "str",
                    "description": "Specify the name of the output field.",
                    "default": "field",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the output field.",
                    "default": "description of field",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "type",
                    "display_name": "Type",
                    "type": "str",
                    "edit_mode": EditMode.INLINE,
                    "description": ("Indicate the data type of the output field (e.g., str, int, float, bool, dict)."),
                    "options": ["str", "int", "float", "bool", "dict"],
                    "default": "str",
                },
                {
                    "name": "multiple",
                    "display_name": "As List",
                    "type": "boolean",
                    "description": "Set to True if this output field should be a list of the specified type.",
                    "default": "False",
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[
                {
                    "name": "field",
                    "description": "description of field",
                    "type": "str",
                    "multiple": "False",
                }
            ],
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
            display_name="Extracted Content",
            name="extracted_content",
            method="browser_extract_content",
            types=["Message"],
            group_outputs=True,
        ),
    ]

    _extracted_content = None

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "structured_output":
            # Start with empty outputs
            frontend_node["outputs"] = [Output(
                display_name="Browser Session",
                name="output_browser_session",
                method="pass_browser_session",
                types=["AgentBrowserSession"],
                group_outputs=True
            ).to_dict()]

            # Add only the selected output type
            if field_value:
                frontend_node["outputs"].append(
                    Output(
                        display_name="Extracted Content",
                        name="extracted_content",
                        method="browser_extract_structured_content",
                        types=["Data"],
                        group_outputs=True,
                    ).to_dict()
                )
            else:
                frontend_node["outputs"].append(
                    Output(
                        display_name="Extracted Content",
                        name="extracted_content",
                        method="browser_extract_content",
                        types=["Message"],
                        group_outputs=True,
                    ).to_dict()
                )

        return frontend_node

    async def browser_extract_structured_content(self):
        try:
            output_model_ = build_model_from_schema(self.output_schema)
            page = await self.browser_session.get_current_page()
            extracted_result = await page.extract_content(
                self.extract_goal,
                output_model_,
                llm=self.llm,
            )
            extracted_result = extracted_result.model_dump(exclude_none=True)
            self._extracted_content = self.status = json.dumps(extracted_result, indent=2, ensure_ascii=False)
            return Data(data=extracted_result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    async def browser_extract_content(self) -> Message:
        try:
            class CommonExtractModel(BaseModel):
                extracted_content: str
            page = await self.browser_session.get_current_page()
            extracted_result = await page.extract_content(
                self.extract_goal,
                CommonExtractModel,
                llm=self.llm,
            )
            self._extracted_content = self.status = extracted_result.extracted_content
            return Message(text=self._extracted_content)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    async def pass_browser_session(self) -> AgentBrowserSession:
        if not self._extracted_content:
            await self.browser_extract_content()
        return self.browser_session
