import asyncio
from typing import Any, List
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, SliderInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.field_typing import RangeSpec

class BrowserScrollComponent(Component):
    display_name = "Scroll"
    description = "Scroll down or up on a browser page"
    icon = "scroll-text"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MessageTextInput(
            name="text_to_scroll",
            display_name="Text to Scroll",
            info="Text you want to scroll to. If specified, priority to scroll to text instead of using coordinates.",
        ),
        SliderInput(
            name="scroll_x",
            display_name="Scroll X",
            info="The start X coordinate for scrolling",
            value=0.5,
            range_spec=RangeSpec(min=0, max=1),

        ),
        SliderInput(
            name="scroll_y",
            display_name="Scroll Y",
            info="The start Y coordinate for scrolling",
            value=0.5,
            range_spec=RangeSpec(min=0, max=1),
        ),
        IntInput(
            name="scroll_delta_x",
            display_name="Scroll Delta X",
            info="Scroll delta X. Positive for scrolling right. Negative for scrolling left.",
            value=0,
        ),
        IntInput(
            name="scroll_delta_y",
            display_name="Scroll Delta Y",
            info="Scroll delta Y. Positive for scrolling down. Negative for scrolling up.",
            value=500,
        ),
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="browser_scroll",
            types=["AgentBrowserSession"]
        )
    ]

    async def browser_scroll(self) -> AgentBrowserSession:
        try:
            if self.text_to_scroll:
                from vibe_surf.browser.page_operations import scroll_to_text
                self.status = await scroll_to_text(self.text_to_scroll, self.browser_session)
            else:
                cdp_client = self.browser_session.agent_focus.cdp_client
                session_id = self.browser_session.agent_focus.session_id

                # Get viewport dimensions
                layout_metrics = await cdp_client.send.Page.getLayoutMetrics(session_id=session_id)
                viewport_width = layout_metrics['layoutViewport']['clientWidth']
                viewport_height = layout_metrics['layoutViewport']['clientHeight']

                x = int(max(1, viewport_width * self.scroll_x))
                y = int(max(1, viewport_height * self.scroll_y))
                await cdp_client.send.Input.dispatchMouseEvent(
                    params={
                        'type': 'mouseWheel',
                        'x': x,
                        'y': y,
                        'deltaX': self.scroll_delta_x,
                        'deltaY': self.scroll_delta_y,
                    },
                    session_id=session_id,
                )
                self.status = f"Successfully scrolled {x}, {y}, {self.scroll_delta_x}, {self.scroll_delta_y} on page."
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
        finally:
            return self.browser_session
