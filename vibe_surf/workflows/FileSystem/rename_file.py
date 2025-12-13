from pathlib import Path
from typing import Any

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem

class RenameFileComponent(Component):
    display_name = "Rename File"
    description = "Rename a file within the workspace."
    icon = "file-signature"
    name = "RenameFile"

    inputs = [
        MessageTextInput(
            name="src_file_path",
            display_name="File Path",
            info="Current file path (relative to workspace)",
            required=True,
        ),
        MessageTextInput(
            name="new_filename",
            display_name="New Filename",
            info="New filename (just the name, not the full path)",
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            method="rename_file",
            types=["Message"],
        ),
    ]

    async def rename_file(self) -> Message:
        """Rename file to new filename"""
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

            # Rename file
            result = await file_system.rename_file(self.src_file_path, self.new_filename)

            return Message(text=result)

        except Exception as e:
            error_message = f"Error renaming file: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e