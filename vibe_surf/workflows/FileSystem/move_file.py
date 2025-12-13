from pathlib import Path
from typing import Any

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem

class MoveFileComponent(Component):
    display_name = "Move File"
    description = "Move a file from one location to another within the workspace."
    icon = "move"
    name = "MoveFile"

    inputs = [
        MessageTextInput(
            name="old_file_path",
            display_name="Source Path",
            info="Current file path (relative to workspace)",
            required=True,
        ),
        MessageTextInput(
            name="new_file_path",
            display_name="Destination Path",
            info="New file path (relative to workspace)",
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            method="move_file",
            types=["Message"],
        ),
    ]

    async def move_file(self) -> Message:
        """Move file from old path to new path"""
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

            # Move file
            result = await file_system.move_file(self.old_file_path, self.new_file_path)

            return Message(text=result)

        except Exception as e:
            error_message = f"Error moving file: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e