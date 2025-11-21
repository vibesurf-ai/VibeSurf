from pydantic import BaseModel, Field, create_model

from vibe_surf.langflow.custom.custom_component.component import Component
from vibe_surf.langflow.helpers.base_model import build_model_from_schema
from vibe_surf.langflow.io import (
    HandleInput,
    MessageTextInput,
    MultilineInput,
    Output,
    TableInput,
)
from vibe_surf.langflow.schema.data import Data
from vibe_surf.langflow.schema.dataframe import DataFrame
from vibe_surf.langflow.schema.table import EditMode
from browser_use.llm.messages import (
	BaseMessage,
	ContentPartImageParam,
	ContentPartTextParam,
	SystemMessage,
    UserMessage
)


class VibeSurfStructuredOutputComponent(Component):
    display_name = "Structured Output"
    description = "Uses an LLM to generate structured data. Ideal for extraction and consistency."
    documentation: str = "https://docs.vibe_surf.langflow.org/components-processing#structured-output"
    name = "VibeSurfStructuredOutput"
    icon = "braces"

    inputs = [
        HandleInput(
            name="llm",
            display_name="Language Model",
            info="The language model to use to generate the structured output.",
            input_types=["LanguageModel"],
            required=True,
        ),
        MultilineInput(
            name="input_value",
            display_name="Input Message",
            info="The input message to the language model.",
            tool_mode=True,
            required=True,
        ),
        MultilineInput(
            name="system_prompt",
            display_name="Format Instructions",
            info="The instructions to the language model for formatting the output.",
            value=(
                "You are an AI that extracts structured JSON objects from unstructured text. "
                "Use a predefined schema with expected types (str, int, float, bool, dict). "
                "Extract ALL relevant instances that match the schema - if multiple patterns exist, capture them all. "
                "Fill missing or ambiguous values with defaults: null for missing values. "
                "Remove exact duplicates but keep variations that have different field values. "
                "Always return valid JSON in the expected format, never throw errors. "
                "If multiple objects can be extracted, return them all in the structured format."
            ),
            required=True,
            advanced=True,
        ),
        MessageTextInput(
            name="schema_name",
            display_name="Schema Name",
            info="Provide a name for the output data schema.",
            advanced=True,
        ),
        TableInput(
            name="output_schema",
            display_name="Output Schema",
            info="Define the structure and data types for the model's output.",
            required=True,
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
            name="structured_output",
            display_name="Structured Output",
            method="build_structured_output",
        ),
    ]

    async def build_structured_output(self) -> Data:
        schema_name = self.schema_name or "OutputModel"

        if not hasattr(self.llm, "ainvoke"):
            msg = "Language model does not support ainvoke method."
            raise TypeError(msg)
        if not self.output_schema:
            msg = "Output schema cannot be empty"
            raise ValueError(msg)

        # Build the pydantic model from the schema
        AgentOutput = build_model_from_schema(self.output_schema)
        
        # Prepare messages for the LLM
        input_messages = [
            SystemMessage(content=self.system_prompt),
            UserMessage(content=self.input_value),
        ]

        try:
            # Call LLM with the output format directly (like in vibe_surf_agent.py:402)
            response = await self.llm.ainvoke(input_messages, output_format=AgentOutput)
            parsed: AgentOutput = response.completion
        except Exception as exc:
            msg = f"Error invoking LLM with structured output: {exc}"
            raise ValueError(msg) from exc

        return Data(data=parsed.model_dump())