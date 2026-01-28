from pathlib import Path
from typing import Any

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, MultilineInput, Output, BoolInput
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem

class WriteFileComponent(Component):
    display_name = "Write File"
    description = "Write content to a file in the workspace. Creates directories if needed."
    icon = "file-edit"
    name = "WriteFile"

    inputs = [
        MessageTextInput(
            name="file_path",
            display_name="File Path",
            info="Relative path to the file (e.g., 'data/output.txt')",
            required=True,
        ),
        MultilineInput(
            name="content",
            display_name="Content",
            info="Content to write to the file",
            required=True,
        ),
        BoolInput(
            name="append",
            display_name="Append",
            info="If True, append to existing file instead of overwriting",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="trailing_newline",
            display_name="Trailing Newline",
            info="Add newline at end of content",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            method="write_file",
            types=["Message"],
        ),
    ]

    async def write_file(self) -> Message:
        """Write content to file"""
        try:
            # Get session_id for file system initialization
            if hasattr(self, "graph"):
                session_id = self.graph.session_id
            elif hasattr(self, "_session_id"):
                session_id = self._session_id
            else:
                session_id = "default"

            # Initialize file system using workspace/workflows/session_id structure
            from vibe_surf.common import get_workspace_dir
            import os
            
            workspace_dir = os.path.join(get_workspace_dir(), session_id)
            os.makedirs(workspace_dir, exist_ok=True)
            
            file_system = CustomFileSystem(base_dir=workspace_dir, create_default_files=False)

            # Prepare content
            content = self.content
            if self.trailing_newline:
                content += '\n'

            # Write or append to file
            if self.append:
                result = await file_system.append_file(self.file_path, content)
            else:
                result = await file_system.write_file(self.file_path, content)
            abs_file_path = file_system.get_dir() / self.file_path
            return Message(text=str(abs_file_path))

        except Exception as e:
            error_message = f"Error writing to file: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e