import asyncio
import os
from typing import Any, List
from uuid import uuid4
from typing import Optional

from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, SliderInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.langflow.field_typing import RangeSpec
from vibe_surf.browser.agent_browser_session import AgentBrowserSession


class BrowserTakeScreenshotComponent(Component):
    display_name = "Take Screenshot"
    description = "Browser take screenshot"
    icon = "camera"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        SliderInput(
            name="crop_x1",
            display_name="Crop X1",
            info="The left edge of the crop region (0-1)",
            value=0.0,
            range_spec=RangeSpec(min=0, max=1),
        ),
        SliderInput(
            name="crop_y1",
            display_name="Crop Y1",
            info="The top edge of the crop region (0-1)",
            value=0.0,
            range_spec=RangeSpec(min=0, max=1),
        ),
        SliderInput(
            name="crop_x2",
            display_name="Crop X2",
            info="The right edge of the crop region (0-1)",
            value=1.0,
            range_spec=RangeSpec(min=0, max=1),
        ),
        SliderInput(
            name="crop_y2",
            display_name="Crop Y2",
            info="The bottom edge of the crop region (0-1)",
            value=1.0,
            range_spec=RangeSpec(min=0, max=1),
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
            method="browser_take_screenshot",
            types=["Message"],
            group_outputs=True,
        ),
    ]

    _screenshot_path: Optional[str] = None

    async def browser_take_screenshot(self):
        try:
            from datetime import datetime
            import base64
            import io
            from pathlib import Path
            from PIL import Image

            page = await self.browser_session.get_current_page()
            page_png = await page.screenshot(format="png", quality=90)
            from vibe_surf.common import get_workspace_dir
            workspace_dir = get_workspace_dir()
            screenshot_dir = os.path.join(workspace_dir, "workflows", "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            _screenshot_path = os.path.join(screenshot_dir, f"{self._id}-{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.png")
            
            # Decode screenshot data
            screenshot_data = base64.b64decode(page_png)
            
            # Load image and crop if needed
            image = Image.open(io.BytesIO(screenshot_data))
            width, height = image.size
            
            # Calculate crop coordinates
            x1 = int(width * self.crop_x1)
            y1 = int(height * self.crop_y1)
            x2 = int(width * self.crop_x2)
            y2 = int(height * self.crop_y2)
            
            # Crop the image if coordinates are not full size
            if x1 > 0 or y1 > 0 or x2 < width or y2 < height:
                image = image.crop((x1, y1, x2, y2))
                self.status = f"Screenshot cropped to ({x1}, {y1}, {x2}, {y2}) and saved at {_screenshot_path}"
            else:
                self.status = f"Take Screenshot and save it at {_screenshot_path}"
            
            # Save the cropped image
            image.save(_screenshot_path, format="PNG")
            self._screenshot_path = _screenshot_path
            
            return Message(text=self._screenshot_path)

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    async def pass_browser_session(self) -> AgentBrowserSession:
        if not self._screenshot_path:
            await self.browser_take_screenshot()
        return self.browser_session
