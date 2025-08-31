from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import List, Optional

from browser_use.browser.session import BrowserSession, CDPSession
from pydantic import Field
from browser_use.browser.events import (
    NavigationCompleteEvent,
)
import time
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.views import BrowserStateSummary
from browser_use.dom.views import TargetInfo
from vibe_surf.browser.agen_browser_profile import AgentBrowserProfile
from typing import Self

DEFAULT_BROWSER_PROFILE = AgentBrowserProfile()

class AgentBrowserSession(BrowserSession):
    """Isolated browser session for a specific agent."""
    browser_profile: AgentBrowserProfile = Field(
        default_factory=lambda: DEFAULT_BROWSER_PROFILE,
        description='BrowserProfile() options to use for the session, otherwise a default profile will be used',
    )
    main_browser_session: BrowserSession | None = Field(default=None)
    connected_agent: bool = False
    # Add a flag to control DVD animation (for future extensibility)
    disable_dvd_animation: bool = Field(
        default=True,
        description="Disable the DVD screensaver animation on about:blank pages"
    )
    # Custom extensions to load
    custom_extension_paths: List[str] = Field(
        default_factory=list,
        description="List of paths to custom Chrome extensions to load"
    )

    async def connect_agent(self, target_id: str) -> Self:
        """Register agent to browser with optional target assignment."""
        # First ensure the parent BrowserSession is properly connected
        if not hasattr(self, '_cdp_client_root') or self._cdp_client_root is None:
            await self.connect()

        assigned_target_ids = self._cdp_session_pool.keys()
        if target_id not in assigned_target_ids:
            self.logger.info(f"Agent {self.id}: Assigned target {target_id}")
            self.agent_focus = await CDPSession.for_target(self._cdp_client_root, target_id, new_socket=True,
                                                           cdp_url=self.cdp_url)
            await self.agent_focus.cdp_client.send.Target.activateTarget(
                params={'targetId': target_id})
            await self.agent_focus.cdp_client.send.Runtime.runIfWaitingForDebugger(
                session_id=self.agent_focus.session_id)
            self._cdp_session_pool[target_id] = self.agent_focus
        self.connected_agent = True
        return self

    async def disconnect_agent(self) -> None:
        """Disconnect all agent-specific CDP sessions and cleanup security context."""
        for session in self._cdp_session_pool.values():
            await session.disconnect()
        self._cdp_session_pool.clear()
        self.connected_agent = False

    async def _cdp_get_all_pages(
            self,
            include_http: bool = True,
            include_about: bool = True,
            include_pages: bool = True,
            include_iframes: bool = False,
            include_workers: bool = False,
            include_chrome: bool = False,
            include_chrome_extensions: bool = False,
            include_chrome_error: bool = False,
    ) -> list[TargetInfo]:
        """Get all browser pages/tabs using CDP Target.getTargets."""
        # Safety check - return empty list if browser not connected yet
        if not self._cdp_client_root:
            return []
        targets = await self.cdp_client.send.Target.getTargets()
        if self.connected_agent:
            assigned_target_ids = self._cdp_session_pool.keys()
            return [
                t
                for t in targets.get('targetInfos', [])
                if self._is_valid_target(
                    t,
                    include_http=include_http,
                    include_about=include_about,
                    include_pages=include_pages,
                    include_iframes=include_iframes,
                    include_workers=include_workers,
                    include_chrome=include_chrome,
                    include_chrome_extensions=include_chrome_extensions,
                    include_chrome_error=include_chrome_error,
                ) and t.get('targetId') in assigned_target_ids
            ]
        else:
            # Filter for valid page/tab targets only
            return [
                t
                for t in targets.get('targetInfos', [])
                if self._is_valid_target(
                    t,
                    include_http=include_http,
                    include_about=include_about,
                    include_pages=include_pages,
                    include_iframes=include_iframes,
                    include_workers=include_workers,
                    include_chrome=include_chrome,
                    include_chrome_extensions=include_chrome_extensions,
                    include_chrome_error=include_chrome_error,
                )
            ]

    async def attach_all_watchdogs(self) -> None:
        """Initialize and attach all watchdogs EXCEPT AboutBlankWatchdog to disable DVD animation."""
        # Prevent duplicate watchdog attachment
        if hasattr(self, '_watchdogs_attached') and self._watchdogs_attached:
            self.logger.debug('Watchdogs already attached, skipping duplicate attachment')
            return

        # Import all watchdogs except AboutBlankWatchdog
        from vibe_surf.browser.watchdogs.action_watchdog import CustomActionWatchdog
        from vibe_surf.browser.watchdogs.dom_watchdog import CustomDOMWatchdog

        from browser_use.browser.downloads_watchdog import DownloadsWatchdog
        from browser_use.browser.local_browser_watchdog import LocalBrowserWatchdog
        from browser_use.browser.permissions_watchdog import PermissionsWatchdog
        from browser_use.browser.popups_watchdog import PopupsWatchdog
        from browser_use.browser.screenshot_watchdog import ScreenshotWatchdog
        from browser_use.browser.security_watchdog import SecurityWatchdog

        # NOTE: AboutBlankWatchdog is deliberately excluded to disable DVD animation

        self.logger.info('🚫 VibeSurfBrowserSession: AboutBlankWatchdog disabled - no DVD animation will be shown')

        # Initialize DownloadsWatchdog
        DownloadsWatchdog.model_rebuild()
        self._downloads_watchdog = DownloadsWatchdog(event_bus=self.event_bus, browser_session=self)
        self._downloads_watchdog.attach_to_session()
        if self.browser_profile.auto_download_pdfs:
            self.logger.info('📄 PDF auto-download enabled for this session')

        # Initialize LocalBrowserWatchdog
        LocalBrowserWatchdog.model_rebuild()
        self._local_browser_watchdog = LocalBrowserWatchdog(event_bus=self.event_bus, browser_session=self)
        self._local_browser_watchdog.attach_to_session()

        # Initialize SecurityWatchdog (hooks NavigationWatchdog and implements allowed_domains restriction)
        SecurityWatchdog.model_rebuild()
        self._security_watchdog = SecurityWatchdog(event_bus=self.event_bus, browser_session=self)
        self._security_watchdog.attach_to_session()

        # Initialize PopupsWatchdog (handles accepting and dismissing JS dialogs, alerts, confirm, onbeforeunload, etc.)
        PopupsWatchdog.model_rebuild()
        self._popups_watchdog = PopupsWatchdog(event_bus=self.event_bus, browser_session=self)
        self._popups_watchdog.attach_to_session()

        # Initialize PermissionsWatchdog (handles granting and revoking browser permissions like clipboard, microphone, camera, etc.)
        PermissionsWatchdog.model_rebuild()
        self._permissions_watchdog = PermissionsWatchdog(event_bus=self.event_bus, browser_session=self)
        self._permissions_watchdog.attach_to_session()

        # Initialize DefaultActionWatchdog (handles all default actions like click, type, scroll, go back, go forward, refresh, wait, send keys, upload file, scroll to text, etc.)
        CustomActionWatchdog.model_rebuild()
        self._default_action_watchdog = CustomActionWatchdog(event_bus=self.event_bus, browser_session=self)
        self._default_action_watchdog.attach_to_session()

        # Initialize ScreenshotWatchdog (handles taking screenshots of the browser)
        ScreenshotWatchdog.model_rebuild()
        self._screenshot_watchdog = ScreenshotWatchdog(event_bus=self.event_bus, browser_session=self)
        self._screenshot_watchdog.attach_to_session()

        # Initialize DOMWatchdog (handles building the DOM tree and detecting interactive elements, depends on ScreenshotWatchdog)
        CustomDOMWatchdog.model_rebuild()
        self._dom_watchdog = CustomDOMWatchdog(event_bus=self.event_bus, browser_session=self)
        self._dom_watchdog.attach_to_session()

        # Mark watchdogs as attached to prevent duplicate attachment
        self._watchdogs_attached = True

        self.logger.info('✅ VibeSurfBrowserSession: All watchdogs attached (AboutBlankWatchdog excluded)')

    async def _ensure_minimal_about_blank_tab(self) -> None:
        """
        Ensure there's at least one about:blank tab without any animation.
        This replaces AboutBlankWatchdog's functionality but without the DVD animation.
        """
        try:
            # Get all page targets using CDP
            page_targets = await self._cdp_get_all_pages()

            # If no tabs exist at all, create one to keep browser alive
            if len(page_targets) == 0:
                self.logger.info('[VibeSurfBrowserSession] No tabs exist, creating new about:blank tab (no animation)')
                from browser_use.browser.events import NavigateToUrlEvent
                navigate_event = self.event_bus.dispatch(NavigateToUrlEvent(url='about:blank', new_tab=True))
                await navigate_event
                # Note: NO DVD screensaver injection here!

        except Exception as e:
            self.logger.error(f'[VibeSurfBrowserSession] Error ensuring about:blank tab: {e}')

    async def on_BrowserStartEvent(self, event) -> dict[str, str]:
        """Override to ensure minimal about:blank handling without animation."""
        # Call parent implementation first
        result = await super().on_BrowserStartEvent(event)

        # Ensure we have at least one tab without animation
        await self._ensure_minimal_about_blank_tab()

        return result

    def get_cdp_session_pool(self):
        return self._cdp_session_pool

    async def active_focus_page(self):
        if self.agent_focus is None:
            self.logger.info('No active focus page found, cannot active!')
            return
        await self.get_or_create_cdp_session(self.agent_focus.target_id, focus=True)

    async def navigate_to_url(self, url: str, new_tab: bool = False) -> None:
        """
        Concurrent navigation method that bypasses serial bottlenecks in on_NavigateToUrlEvent.
        
        This method performs minimal event dispatching and direct CDP calls for maximum concurrency.
        """
        if not self.agent_focus:
            self.logger.warning('Cannot navigate - browser not connected')
            return

        target_id = None

        try:
            # Minimal target handling - avoid expensive _cdp_get_all_pages() call
            if new_tab:
                # Create new tab directly via CDP - no event system overhead
                result = await self._cdp_client_root.send.Target.createTarget(
                    params={'url': 'about:blank', 'newWindow': False, 'background': False}
                )
                target_id = result['targetId']

                # Create CDP session with dedicated WebSocket for this target
                session = await self.get_or_create_cdp_session(target_id, focus=True)
                self.agent_focus = session

                # Activate target without events
                await session.cdp_client.send.Target.activateTarget(params={'targetId': target_id})
                await session.cdp_client.send.Runtime.runIfWaitingForDebugger(session_id=session.session_id)
            else:
                # Use current tab - no tab switching events
                target_id = self.agent_focus.target_id

            # Direct CDP navigation - bypasses all event system overhead
            await self.agent_focus.cdp_client.send.Page.navigate(
                params={
                    'url': url,
                    'transitionType': 'address_bar',
                },
                session_id=self.agent_focus.session_id,
            )

            # Minimal delay for navigation to start
            await asyncio.sleep(0.2)

            # Optional: Dispatch only essential completion event (non-blocking)
            self.event_bus.dispatch(
                NavigationCompleteEvent(
                    target_id=target_id,
                    url=url,
                    status=None,
                )
            )

        except Exception as e:
            self.logger.error(f'Concurrent navigation failed: {type(e).__name__}: {e}')
            if target_id:
                # Non-blocking error event
                self.event_bus.dispatch(
                    NavigationCompleteEvent(
                        target_id=target_id,
                        url=url,
                        error_message=f'{type(e).__name__}: {e}',
                    )
                )
            raise

    async def _wait_for_stable_network(self):
        """Wait for page stability - simplified for CDP-only branch."""
        start_time = time.time()
        page_url = await self.get_current_page_url()
        not_a_meaningful_website = page_url.lower().split(':', 1)[0] not in ('http', 'https')

        # Wait for page stability using browser profile settings (main branch pattern)
        if not not_a_meaningful_website:
            self.logger.debug('🔍 DOMWatchdog.on_BrowserStateRequestEvent: ⏳ Waiting for page stability...')
            try:
                # Apply minimum wait time first (let page settle)
                min_wait = self.browser_profile.minimum_wait_page_load_time
                if min_wait > 0:
                    self.logger.debug(f'⏳ Minimum wait: {min_wait}s')
                    await asyncio.sleep(min_wait)

                # Apply network idle wait time (for dynamic content like iframes)
                network_idle_wait = self.browser_profile.wait_for_network_idle_page_load_time
                if network_idle_wait > 0:
                    self.logger.debug(f'⏳ Network idle wait: {network_idle_wait}s')
                    await asyncio.sleep(network_idle_wait)

                elapsed = time.time() - start_time
                self.logger.debug(f'✅ Page stability wait completed in {elapsed:.2f}s')
            except Exception as e:
                self.logger.warning(
                    f'🔍 DOMWatchdog.on_BrowserStateRequestEvent: Network waiting failed: {e}, continuing anyway...'
                )

    async def take_screenshot(self, target_id: Optional[str] = None, format: str = 'png') -> str:
        """
        Concurrent screenshot method that bypasses serial bottlenecks in ScreenshotWatchdog.
        
        This method performs direct CDP calls for maximum concurrency.
        """
        if target_id is None:
            if not self.agent_focus:
                self.logger.warning('No page focus to get html, please specify a target id.')
                return ''
            target_id = self.agent_focus.target_id
        cdp_session = await self.get_or_create_cdp_session(target_id, focus=False)
        await self._wait_for_stable_network()

        try:
            ready_state = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={'expression': 'document.readyState'}, session_id=cdp_session.session_id
            )
        except Exception:
            pass

        try:
            from cdp_use.cdp.page import CaptureScreenshotParameters
            # Direct CDP screenshot - bypasses all event system overhead
            params = CaptureScreenshotParameters(format=format, captureBeyondViewport=False, quality=90)
            result = await cdp_session.cdp_client.send.Page.captureScreenshot(
                params=params,
                session_id=cdp_session.session_id,
            )
            return result['data']

        except Exception as e:
            self.logger.error(f'Concurrent screenshot failed: {type(e).__name__}: {e}')
            raise

    async def get_html_content(self, target_id: Optional[str] = None) -> str:
        """
        Get html content of current page
        :return:
        """
        if target_id is None:
            if not self.agent_focus:
                self.logger.warning('No page focus to get html, please specify a target id.')
                return ''
            target_id = self.agent_focus.target_id
        cdp_session = await self.get_or_create_cdp_session(target_id, focus=True)
        await self._wait_for_stable_network()

        try:
            ready_state = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={'expression': 'document.readyState'}, session_id=cdp_session.session_id
            )
        except Exception:
            await self._wait_for_stable_network()

        try:
            # Get the HTML content
            body_id = await cdp_session.cdp_client.send.DOM.getDocument(session_id=cdp_session.session_id)
            page_html_result = await cdp_session.cdp_client.send.DOM.getOuterHTML(
                params={'backendNodeId': body_id['root']['backendNodeId']}, session_id=cdp_session.session_id
            )
        except Exception as e:
            raise RuntimeError(f"Couldn't extract page content: {e}")

        page_html = page_html_result['outerHTML']
        return page_html

    async def get_browser_state_summary(
            self,
            cache_clickable_elements_hashes: bool = True,
            include_screenshot: bool = True,
            cached: bool = False,
            include_recent_events: bool = False,
    ) -> BrowserStateSummary:
        if cached and self._cached_browser_state_summary is not None and self._cached_browser_state_summary.dom_state:
            # Don't use cached state if it has 0 interactive elements
            selector_map = self._cached_browser_state_summary.dom_state.selector_map

            # Don't use cached state if we need a screenshot but the cached state doesn't have one
            if include_screenshot and not self._cached_browser_state_summary.screenshot:
                self.logger.debug('⚠️ Cached browser state has no screenshot, fetching fresh state with screenshot')
            # Fall through to fetch fresh state with screenshot
            elif selector_map and len(selector_map) > 0:
                self.logger.debug('🔄 Using pre-cached browser state summary for open tab')
                return self._cached_browser_state_summary
            else:
                self.logger.debug('⚠️ Cached browser state has 0 interactive elements, fetching fresh state')
            # Fall through to fetch fresh state

        browser_state = await self._dom_watchdog.get_browser_state_no_event_bus(
            include_dom=True,
            include_screenshot=include_screenshot,
            cache_clickable_elements_hashes=cache_clickable_elements_hashes,
            include_recent_events=include_recent_events
        )
        return browser_state
