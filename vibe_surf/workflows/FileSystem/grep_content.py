from pathlib import Path
from typing import Any
import os
import mimetypes
import base64
import asyncio

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, IntInput, Output, HandleInput
from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.field_typing import LanguageModel
from vibe_surf.tools.file_system import CustomFileSystem
from browser_use.llm.messages import UserMessage, ContentPartTextParam, ContentPartImageParam, ImageURL

class GrepContentComponent(Component):
    display_name = "Grep Content"
    description = "Search for query/keywords in a file and return surrounding context. Supports both text and image files (with OCR)."
    icon = "search"
    name = "GrepContent"

    inputs = [
        HandleInput(
            name="llm",
            display_name="LLM Model",
            info="Language model for OCR on image files",
            input_types=["LanguageModel"],
            required=True
        ),
        MessageTextInput(
            name="file_path",
            display_name="File Path",
            info="Path to the file to search in",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Query or keywords to search for",
            required=True,
        ),
        IntInput(
            name="context_chars",
            display_name="Context Characters",
            info="Number of characters to show before and after match",
            value=100,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="search_results",
            display_name="Search Results",
            method="grep_content",
            types=["Message"],
        ),
    ]

    async def grep_content(self) -> Message:
        """Search for content in file and return matches with context"""
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

            # Get file path
            file_path = self.file_path
            full_file_path = file_path
            
            # Check if file exists
            if not os.path.exists(full_file_path):
                full_file_path = os.path.join(str(file_system.get_dir()), file_path)

            # Determine if file is an image based on MIME type
            mime_type, _ = mimetypes.guess_type(file_path)
            is_image = mime_type and mime_type.startswith('image/')

            if is_image:
                # Handle image files with LLM vision for OCR
                try:
                    # Read image file and encode to base64
                    with open(full_file_path, 'rb') as image_file:
                        image_data = image_file.read()
                        image_base64 = base64.b64encode(image_data).decode('utf-8')

                    # Create content parts for OCR
                    content_parts: list[ContentPartTextParam | ContentPartImageParam] = [
                        ContentPartTextParam(
                            text="Please extract all text content from this image for search purposes. Return only the extracted text, no additional explanations.")
                    ]

                    # Add the image
                    content_parts.append(
                        ContentPartImageParam(
                            image_url=ImageURL(
                                url=f'data:{mime_type};base64,{image_base64}',
                                media_type=mime_type,
                                detail='high',
                            ),
                        )
                    )

                    # Create user message and invoke LLM for OCR
                    user_message = UserMessage(content=content_parts, cache=True)
                    response = await asyncio.wait_for(
                        self.llm.ainvoke([user_message]),
                        timeout=120.0,
                    )

                    file_content = response.completion

                except Exception as e:
                    raise Exception(f'Failed to process image file {file_path} for OCR: {str(e)}')

            else:
                # Handle non-image files by reading content
                try:
                    file_content = await file_system.read_file(full_file_path, external_file=True)
                except Exception as e:
                    raise Exception(f'Failed to read file {file_path}: {str(e)}')

            # Perform grep search
            search_query = self.query.lower()
            context_chars = self.context_chars

            # Find all matches with context
            matches = []
            content_lower = file_content.lower()
            search_start = 0

            while True:
                match_pos = content_lower.find(search_query, search_start)
                if match_pos == -1:
                    break

                # Calculate context boundaries
                start_pos = max(0, match_pos - context_chars)
                end_pos = min(len(file_content), match_pos + len(search_query) + context_chars)

                # Extract context with the match
                context_before = file_content[start_pos:match_pos]
                matched_text = file_content[match_pos:match_pos + len(search_query)]
                context_after = file_content[match_pos + len(search_query):end_pos]

                # Add ellipsis if truncated
                if start_pos > 0:
                    context_before = "..." + context_before
                if end_pos < len(file_content):
                    context_after = context_after + "..."

                matches.append({
                    'context_before': context_before,
                    'matched_text': matched_text,
                    'context_after': context_after,
                    'position': match_pos
                })

                search_start = match_pos + 1

            # Format results
            if not matches:
                extracted_content = f'File: {file_path}\nQuery: "{self.query}"\nResult: No matches found'
            else:
                result_text = f'File: {file_path}\nQuery: "{self.query}"\nFound {len(matches)} match(es):\n\n'

                for i, match in enumerate(matches, 1):
                    result_text += f"Match {i} (position: {match['position']}):\n"
                    result_text += f"{match['context_before']}[{match['matched_text']}]{match['context_after']}\n\n"

                extracted_content = result_text.strip()

            return Message(text=extracted_content)

        except Exception as e:
            error_message = f"Error searching file: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e