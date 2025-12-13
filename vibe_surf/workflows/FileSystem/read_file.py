from pathlib import Path
from typing import Any
import os

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output, BoolInput
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem
import os

class ReadFileComponent(Component):
    display_name = "Read File"
    description = "Read content from a file. Supports both workspace files and external absolute paths."
    icon = "file-text"
    name = "ReadFile"

    inputs = [
        MessageTextInput(
            name="file_path",
            display_name="File Path",
            info="Path to the file (relative to workspace or absolute)",
            required=True,
        ),
        BoolInput(
            name="external_file",
            display_name="External File",
            info="If True, treat path as absolute external path",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="content",
            display_name="File Content",
            method="read_file",
            types=["Message"],
        ),
    ]

    async def read_file(self) -> Message:
        """Read content from file"""
        try:
            # Determine if external file
            external_file = self.external_file or os.path.exists(self.file_path)

            # Get session_id for file system initialization
            if hasattr(self, "graph"):
                session_id = self.graph.session_id
            elif hasattr(self, "_session_id"):
                session_id = self._session_id
            else:
                session_id = "default"

            # Initialize file system using workspace/workflows/session_id structure
            from vibe_surf.common import get_workspace_dir
            
            workspace_dir = get_workspace_dir()
            os.makedirs(workspace_dir, exist_ok=True)
            
            file_system = CustomFileSystem(base_dir=workspace_dir, create_default_files=False)

            # Read file
            result = await file_system.read_file(self.file_path, external_file=external_file)

            return Message(text=result)

        except Exception as e:
            error_message = f"Error reading file: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e