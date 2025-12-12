import os
from typing import Any, Dict

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import HandleInput
from vibe_surf.langflow.io import Output
from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.schema.data import Data
from vibe_surf.agents.report_writer_agent import ReportWriterAgent
from vibe_surf.langflow.field_typing import LanguageModel
from vibe_surf.langflow.inputs.inputs import DataInput, IntInput, DataFrameInput, BoolInput, MultilineInput

class ReportWriterAgentComponent(Component):
    display_name = "Report Writer Agent"
    description = "Generate HTML reports using LLM-controlled flow"
    icon = "file-text"

    inputs = [
        MultilineInput(
            name="report_task",
            display_name="Report Task",
            info="Report Task",
            value="Generate a comprehensive report."

        ),
        MultilineInput(
            name="report_information",
            display_name="Report Information",
            info="Requirement Information for report.",
            required=True,

        ),
        HandleInput(
            name="llm",
            display_name="LLM Model",
            info="LLM Model for report generation",
            input_types=["LanguageModel"],
            required=True
        ),
        BoolInput(
            name="think_mode",
            display_name="Think Mode",
            value=True,
            advanced=True,
            info="Think mode.",
        ),
    ]

    outputs = [
        Output(
            display_name="Report Path",
            name="report_path",
            method="generate_report",
            types=["Message"],
        ),
    ]

    async def generate_report(self) -> Message:
        """Generate HTML report and return the absolute path"""
        try:
            from vibe_surf.common import get_workspace_dir

            # Get workspace directory and create reports subdirectory
            workspace_dir = get_workspace_dir()
            reports_dir = os.path.join(workspace_dir, "workflows")
            os.makedirs(reports_dir, exist_ok=True)

            # Convert Data input to dictionary
            report_data = {}
            report_data["report_task"] = self.report_task
            report_data["report_information"] = self.report_information

            # Initialize ReportWriterAgent
            agent = ReportWriterAgent(
                llm=self.llm,
                workspace_dir=reports_dir,
                use_thinking=self.think_mode
            )

            # Generate report
            result = await agent.generate_report(report_data)

            # Get absolute path for the report
            absolute_report_path = os.path.abspath(os.path.join(reports_dir, result.report_path))

            # Return Message with absolute path
            if result.success:
                return Message(text=absolute_report_path)
            else:
                # Even on failure, return the path with error message
                return Message(text=f"{absolute_report_path}\nError: {result.msg}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e