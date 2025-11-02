import asyncio
import os
from typing import Any, List
from uuid import uuid4
from typing import Optional

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message

class BrowserHtmlContentComponent(Component):
    display_name = "Html Content"
    description = "Browser get html content"
    icon = "code-xml"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="pass_browser_session",
            types=["AgentBrowserSession"],
            group_outputs=True,
        ),
        Output(
            display_name="Screenshot Path",
            name="screenshot_path",
            method="browser_get_html_content",
            types=["Message"],
            group_outputs=True,
        ),
    ]

    _html_path: Optional[str] = None

    async def browser_get_html_content(self):
        try:
            from datetime import datetime
            import base64
            import io
            from pathlib import Path

            html_content = await self.browser_session.get_html_content()
            from vibe_surf.common import get_workspace_dir
            workspace_dir = get_workspace_dir()
            html_dir = os.path.join(workspace_dir, "workflows", "htmls")
            os.makedirs(html_dir, exist_ok=True)
            _html_path = os.path.join(html_dir, f"{self._id}-{datetime.now().strftime('%d-%m-%Y-%H-%M-%S')}.html")
            with open(_html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            self._html_path = _html_path
            self.status = f"Get html content and save it at {_html_path}"
            return Message(text=self._html_path)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    async def pass_browser_session(self) -> AgentBrowserSession:
        if not self._html_path:
            await self.browser_get_html_content()
        return self.browser_session
