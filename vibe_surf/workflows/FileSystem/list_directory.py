from pathlib import Path
from typing import Any

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem

class ListDirectoryComponent(Component):
    display_name = "List Directory"
    description = "List files and directories in a specified path."
    icon = "folder-open"
    name = "ListDirectory"

    inputs = [
        MessageTextInput(
            name="directory_path",
            display_name="Directory Path",
            info='Directory path (use "" or "." for root workspace)',
            value=".",
            required=False,
        ),
    ]

    outputs = [
        Output(
            name="listing",
            display_name="Directory Listing",
            method="list_directory",
            types=["Message"],
        ),
    ]

    async def list_directory(self) -> Message:
        """List directory contents"""
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

            # List directory
            directory_path = self.directory_path if self.directory_path else "."
            result = await file_system.list_directory(directory_path)

            return Message(text=result)

        except Exception as e:
            error_message = f"Error listing directory: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e