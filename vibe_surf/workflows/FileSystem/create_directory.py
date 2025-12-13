from pathlib import Path
from typing import Any

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem

class CreateDirectoryComponent(Component):
    display_name = "Create Directory"
    description = "Create a new directory in the workspace."
    icon = "folder-plus"
    name = "CreateDirectory"

    inputs = [
        MessageTextInput(
            name="directory_path",
            display_name="Directory Path",
            info="Path for the new directory (relative to workspace)",
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            method="create_directory",
            types=["Message"],
        ),
    ]

    async def create_directory(self) -> Message:
        """Create a new directory"""
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

            # Create directory
            result = await file_system.create_directory(self.directory_path)

            return Message(text=result)

        except Exception as e:
            error_message = f"Error creating directory: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e