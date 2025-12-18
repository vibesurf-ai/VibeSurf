import asyncio
import os
import urllib.parse
from typing import Optional
from datetime import datetime
from pathvalidate import sanitize_filename

from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput
from vibe_surf.langflow.io import Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.tools.utils import _detect_file_format, _format_file_size
from vibe_surf.langflow.schema.data import Data

class BrowserDownloadMediaComponent(Component):
    display_name = "Download Media"
    description = "Download media from URL and save to downloads folder"
    icon = "download"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="URL",
            info="URL of the media to download",
            required=True,
        ),
        MessageTextInput(
            name="filename",
            display_name="Filename",
            info="Optional custom filename (extension will be auto-detected)",
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="File Info",
            name="file_path",
            method="download_media",
            types=["Data"],
            group_outputs=True,
        ),
    ]

    _file_path: Optional[str] = None

    async def download_media(self):
        try:
            import aiohttp
            from pathlib import Path
            from vibe_surf.common import get_workspace_dir

            # Get workspace directory and create downloads folder
            workspace_dir = get_workspace_dir()
            downloads_dir = os.path.join(workspace_dir, "workflows", "downloads")
            os.makedirs(downloads_dir, exist_ok=True)

            # Download the file and detect format
            # trust_env=True enables proxy from environment variables (HTTP_PROXY, HTTPS_PROXY)
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}: Failed to download from {self.url}")

                    # Get content
                    content = await response.read()
                    headers_dict = dict(response.headers)

                    # Detect file format and extension
                    file_extension = await _detect_file_format(self.url, headers_dict, content)

                    # Generate filename
                    if self.filename:
                        # Use provided filename, add extension if missing
                        filename = self.filename
                        if not filename.endswith(file_extension):
                            filename = f"{filename}{file_extension}"
                    else:
                        # Generate filename from URL or timestamp
                        url_path = urllib.parse.urlparse(self.url).path
                        url_filename = os.path.basename(url_path)

                        if url_filename and not url_filename.startswith('.'):
                            # Use URL filename, ensure correct extension
                            filename = url_filename
                            if not filename.endswith(file_extension):
                                base_name = os.path.splitext(filename)[0]
                                filename = f"{base_name}{file_extension}"
                        else:
                            # Generate filename with ID and timestamp
                            timestamp = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')
                            filename = f"{self._id}-media_{timestamp}{file_extension}"

                    # Sanitize filename
                    filename = sanitize_filename(filename)
                    filepath = os.path.join(downloads_dir, filename)

                    # Save file
                    Path(filepath).write_bytes(content)

                    # Calculate file size for display
                    file_size = len(content)
                    size_str = _format_file_size(file_size)

                    self._file_path = filepath
                    self.status = f"Downloaded media to {filepath} ({size_str})"
                    media_type = "image" if os.path.splitext(self._file_path)[-1].lower() in [".jpg", ".jpeg",
                                                                                              ".png"] else "video"
                    media_data = {
                        "path": self._file_path,
                        "type": media_type,
                        "alt": "",
                        "showControls": True,
                        "autoPlay": False,
                        "loop": False,
                    }
                    return Data(data=media_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
