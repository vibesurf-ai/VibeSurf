from pathlib import Path
from typing import Any

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem

class ReplaceFileStrComponent(Component):
    display_name = "Replace File String"
    description = "Replace a string in a file with a new string."
    icon = "replace"
    name = "ReplaceFileStr"

    inputs = [
        MessageTextInput(
            name="file_name",
            display_name="File Name",
            info="Path to the file (relative to workspace)",
            required=True,
        ),
        MessageTextInput(
            name="old_str",
            display_name="Old String",
            info="String to be replaced",
            required=True,
        ),
        MessageTextInput(
            name="new_str",
            display_name="New String",
            info="String to replace with",
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            method="replace_str",
            types=["Message"],
        ),
    ]

    async def replace_str(self) -> Message:
        """Replace string in file"""
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
            
            workspace_dir = get_workspace_dir()
            os.makedirs(workspace_dir, exist_ok=True)
            
            file_system = CustomFileSystem(base_dir=workspace_dir, create_default_files=False)

            # Replace string in file
            result = await file_system.replace_file_str(
                self.file_name,
                self.old_str,
                self.new_str
            )

            return Message(text=result)

        except Exception as e:
            error_message = f"Error replacing string in file: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e