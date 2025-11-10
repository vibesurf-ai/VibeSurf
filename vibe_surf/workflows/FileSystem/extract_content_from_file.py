import asyncio
from pathlib import Path
from typing import Any
from browser_use.llm.base import BaseChatModel

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import FileInput, MessageTextInput, MultilineInput, Output, HandleInput
from vibe_surf.langflow.schema import Data
from vibe_surf.langflow.schema.message import Message
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.tools.utils import extract_file_content_with_llm
from vibe_surf.langflow.field_typing import LanguageModel

class ExtractContentFromFileComponent(Component):
    display_name = "Extract Content From File"
    description = "Extract content from a file using LLM. Supports both image and text files."
    icon = "file-search"
    name = "ExtractContentFromFile"

    inputs = [
        HandleInput(
            name="llm",
            display_name="LLM Model",
            info="Language model for content extraction",
            input_types=["LanguageModel"],
            required=True
        ),
        MultilineInput(
            name="query",
            display_name="Query",
            info="Query or instruction for content extraction",
            required=True,
        ),
        FileInput(
            name="file",
            display_name="File",
            fileTypes=["pdf", "md", "txt", "json", "csv", "png", "jpg", "jpeg", "gif", "bmp", "webp"],
            info="File to extract content from",
            required=False,
        ),
        MessageTextInput(
            name="file_path",
            display_name="File Path",
            info="Path to the file (alternative to file upload)",
            required=False,
            advanced=True
        ),
    ]

    outputs = [
        Output(
            name="extracted_content",
            display_name="Extracted Content",
            method="extract_content",
            types=["Message"],
        ),
    ]

    async def extract_content(self) -> Message:
        """Extract content from file using LLM"""
        try:
            # Validate inputs
            if not self.file and not self.file_path:
                raise ValueError("Please provide either a file upload or file path")
            
            if self.file and self.file_path:
                raise ValueError("Please provide either a file upload or file path, not both")

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
            workflows_dir = Path(workspace_dir) / "workflows" / session_id
            os.makedirs(workflows_dir, exist_ok=True)
            
            file_system = CustomFileSystem(base_dir=workflows_dir, create_default_files=False)

            # Determine file path
            if self.file:
                # Handle uploaded file
                file_path = self.file
                # If it's an uploaded file, we might need to copy it to our file system
                if hasattr(self, 'resolve_path'):
                    resolved_path = self.resolve_path(self.file)
                    file_path = resolved_path
            else:
                # Handle file path
                file_path = self.file_path

            # Extract content using the utility function
            extracted_content = await extract_file_content_with_llm(
                file_path=file_path,
                query=self.query,
                llm=self.llm,
                file_system=file_system
            )

            return Message(text=extracted_content)

        except Exception as e:
            error_message = f"Error extracting content from file: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e