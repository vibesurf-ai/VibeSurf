"""DOM watchdog for browser DOM tree management using CDP."""

import asyncio
import pdb
import time
from typing import TYPE_CHECKING

from browser_use.browser.events import (
    BrowserErrorEvent,
    BrowserStateRequestEvent,
    ScreenshotEvent,
    TabCreatedEvent,
)
from browser_use.browser.watchdog_base import BaseWatchdog
from browser_use.browser.watchdogs.dom_watchdog import DOMWatchdog
from browser_use.dom.service import DomService
from browser_use.dom.views import (
    EnhancedDOMTreeNode,
    SerializedDOMState,
)

if TYPE_CHECKING:
    from browser_use.browser.views import BrowserStateSummary, PageInfo


class CustomDOMWatchdog(DOMWatchdog):

    async def get_browser_state_no_event_bus(self, include_dom: bool = True,
                                             include_screenshot: bool = True,
                                             include_recent_events: bool = False) -> 'BrowserStateSummary':
        """Handle browser state request by coordinating DOM building and screenshot capture.

        This is the main entry point for getting the complete browser state.

        Args:
            event: The browser state request event with options

        Returns:
            Complete BrowserStateSummary with DOM, screenshot, and target info
        """
        from browser_use.browser.views import BrowserStateSummary, PageInfo

        self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: STARTING browser state request')
        page_url = await self.browser_session.get_current_page_url()
        self.logger.debug(f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Got page URL: {page_url}')
        if self.browser_session.agent_focus:
            self.logger.debug(
                f'📍 Current page URL: {page_url}, target_id: {self.browser_session.agent_focus.target_id}, session_id: {self.browser_session.agent_focus.session_id}'
            )
        else:
            self.logger.debug(f'📍 Current page URL: {page_url}, no cdp_session attached')

        # check if we should skip DOM tree build for pointless pages
        not_a_meaningful_website = page_url.lower().split(':', 1)[0] not in ('http', 'https')

        # Wait for page stability using browser profile settings (main branch pattern)
        if not not_a_meaningful_website:
            self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: ⏳ Waiting for page stability...')
            try:
                await self._wait_for_stable_network()
                self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: ✅ Page stability complete')
            except Exception as e:
                self.logger.warning(
                    f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Network waiting failed: {e}, continuing anyway...'
                )

        # Get tabs info once at the beginning for all paths
        self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: Getting tabs info...')
        tabs_info = await self.browser_session.get_tabs()
        self.logger.debug(f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Got {len(tabs_info)} tabs')
        self.logger.debug(f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Tabs info: {tabs_info}')

        try:
            # Execute DOM building and screenshot capture in parallel
            dom_task = None
            screenshot_task = None

            # Start DOM building task if requested
            if include_dom:
                self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: 🌳 Starting DOM tree build task...')

                previous_state = (
                    self.browser_session._cached_browser_state_summary.dom_state
                    if self.browser_session._cached_browser_state_summary
                    else None
                )

                dom_task = asyncio.create_task(self._build_dom_tree_without_highlights(previous_state))

            # Start clean screenshot task if requested (without JS highlights)
            if include_screenshot:
                self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: 📸 Starting clean screenshot task...')
                screenshot_task = asyncio.create_task(self.browser_session.take_screenshot_base64())

            # Wait for both tasks to complete
            content = None
            screenshot_b64 = None

            if dom_task:
                try:
                    content = await dom_task
                    self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: ✅ DOM tree build completed')
                except Exception as e:
                    self.logger.warning(
                        f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: DOM build failed: {e}, using minimal state')
                    content = SerializedDOMState(_root=None, selector_map={})
            else:
                content = SerializedDOMState(_root=None, selector_map={})

            if screenshot_task:
                try:
                    screenshot_b64 = await screenshot_task
                    self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: ✅ Clean screenshot captured')
                except Exception as e:
                    self.logger.warning(f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Clean screenshot failed: {e}')
                    screenshot_b64 = None

            # Apply Python-based highlighting if both DOM and screenshot are available
            if screenshot_b64 and content and content.selector_map and self.browser_session.browser_profile.highlight_elements:
                try:
                    self.logger.debug(
                        '🔍 DOMWatchdog.on_BrowserStateRequestEvent: 🎨 Applying Python-based highlighting...')
                    # from browser_use.browser.python_highlights import create_highlighted_screenshot_async
                    from vibe_surf.browser.utils import create_highlighted_screenshot_async

                    # Get CDP session for viewport info
                    cdp_session = await self.browser_session.get_or_create_cdp_session()

                    screenshot_b64 = await create_highlighted_screenshot_async(
                        screenshot_b64,
                        content.selector_map,
                        cdp_session,
                    )
                    #
                    # import base64
                    # import os
                    # image_data = base64.b64decode(screenshot_b64)
                    # output_path = os.path.join("./tmp/vibesurf_workspace/", "screenshots", f"{time.time()}.png")
                    # os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    # with open(output_path, 'wb') as f:
                    #     f.write(image_data)
                    # pdb.set_trace()

                    self.logger.debug(
                        f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: ✅ Applied highlights to {len(content.selector_map)} elements'
                    )
                except Exception as e:
                    self.logger.warning(f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Python highlighting failed: {e}')

            # Ensure we have valid content
            if not content:
                content = SerializedDOMState(_root=None, selector_map={})

            # Tabs info already fetched at the beginning

            # Get target title safely
            try:
                self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: Getting page title...')
                title = await asyncio.wait_for(self.browser_session.get_current_page_title(), timeout=2.0)
                self.logger.debug(f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Got title: {title}')
            except Exception as e:
                self.logger.debug(f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Failed to get title: {e}')
                title = 'Page'

            # Get comprehensive page info from CDP
            try:
                self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: Getting page info from CDP...')
                page_info = await self._get_page_info()
                self.logger.debug(f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Got page info from CDP: {page_info}')
            except Exception as e:
                self.logger.debug(
                    f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Failed to get page info from CDP: {e}, using fallback'
                )
                # Fallback to default viewport dimensions
                viewport = self.browser_session.browser_profile.viewport or {'width': 1280, 'height': 720}
                page_info = PageInfo(
                    viewport_width=viewport['width'],
                    viewport_height=viewport['height'],
                    page_width=viewport['width'],
                    page_height=viewport['height'],
                    scroll_x=0,
                    scroll_y=0,
                    pixels_above=0,
                    pixels_below=0,
                    pixels_left=0,
                    pixels_right=0,
                )

            # Check for PDF viewer
            is_pdf_viewer = page_url.endswith('.pdf') or '/pdf/' in page_url

            # Build and cache the browser state summary
            if screenshot_b64:
                self.logger.debug(
                    f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: 📸 Creating BrowserStateSummary with screenshot, length: {len(screenshot_b64)}'
                )
            else:
                self.logger.debug(
                    '🔍 DOMWatchdog.on_BrowserStateRequestEvent: 📸 Creating BrowserStateSummary WITHOUT screenshot'
                )

            browser_state = BrowserStateSummary(
                dom_state=content,
                url=page_url,
                title=title,
                tabs=tabs_info,
                screenshot=screenshot_b64,
                page_info=page_info,
                pixels_above=0,
                pixels_below=0,
                browser_errors=[],
                is_pdf_viewer=is_pdf_viewer,
                recent_events=self._get_recent_events_str() if include_recent_events else None,
            )

            # Cache the state
            self.browser_session._cached_browser_state_summary = browser_state

            self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: ✅ COMPLETED - Returning browser state')
            return browser_state

        except Exception as e:
            self.logger.error(f'Failed to get browser state: {e}')

            # Return minimal recovery state
            return BrowserStateSummary(
                dom_state=SerializedDOMState(_root=None, selector_map={}),
                url=page_url if 'page_url' in locals() else '',
                title='Error',
                tabs=[],
                screenshot=None,
                page_info=PageInfo(
                    viewport_width=1280,
                    viewport_height=720,
                    page_width=1280,
                    page_height=720,
                    scroll_x=0,
                    scroll_y=0,
                    pixels_above=0,
                    pixels_below=0,
                    pixels_left=0,
                    pixels_right=0,
                ),
                pixels_above=0,
                pixels_below=0,
                browser_errors=[str(e)],
                is_pdf_viewer=False,
                recent_events=None,
            )
