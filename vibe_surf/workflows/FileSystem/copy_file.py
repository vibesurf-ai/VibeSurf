from pathlib import Path
from typing import Any

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output, BoolInput
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem

class CopyFileComponent(Component):
    display_name = "Copy File"
    description = "Copy a file from source to destination. Can copy from external paths to workspace."
    icon = "copy"
    name = "CopyFile"

    inputs = [
        MessageTextInput(
            name="src_file_path",
            display_name="Source File Path",
            info="Path to source file (relative or absolute if external_src=True)",
            required=True,
        ),
        MessageTextInput(
            name="dst_file_path",
            display_name="Destination File Path",
            info="Destination path (relative to workspace)",
            required=True,
        ),
        BoolInput(
            name="external_src",
            display_name="External Source",
            info="If True, source is an absolute path outside workspace",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="result",
            display_name="Result",
            method="copy_file",
            types=["Message"],
        ),
    ]

    async def copy_file(self) -> Message:
        """Copy file from source to destination"""
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

            # Copy file
            result = await file_system.copy_file(
                self.src_file_path,
                self.dst_file_path,
                self.external_src
            )

            return Message(text=result)

        except Exception as e:
            error_message = f"Error copying file: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e