from pathlib import Path
from typing import Any
import os

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem

class FileExistComponent(Component):
    display_name = "File Exist"
    description = "Check if a file exists in the workspace or as an external file."
    icon = "file-search"
    name = "FileExist"

    inputs = [
        MessageTextInput(
            name="file_path",
            display_name="File Path",
            info="Path to check (relative to workspace or absolute)",
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            method="file_exist",
            types=["Message"],
        ),
    ]

    async def file_exist(self) -> Message:
        """Check if file exists"""
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

            # Check file existence
            if os.path.exists(self.file_path):
                result = f"{self.file_path} is an external file and it exists."
            else:
                is_file_exist = await file_system.file_exist(self.file_path)
                if is_file_exist:
                    result = f"{self.file_path} is in file system and it exists."
                else:
                    result = f"{self.file_path} does not exist."

            return Message(text=result)

        except Exception as e:
            error_message = f"Error checking file existence: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e