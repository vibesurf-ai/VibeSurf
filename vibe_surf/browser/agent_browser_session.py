from __future__ import annotations

import asyncio
import os
import pdb
from pathlib import Path
from typing import Any, List, Optional

from browser_use.browser.session import BrowserSession, CDPSession
from pydantic import Field
from browser_use.browser.events import (
    NavigationCompleteEvent,
)
from browser_use.utils import _log_pretty_url, is_new_tab_page, time_execution_async
import time
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.views import BrowserStateSummary
from browser_use.dom.views import TargetInfo
from vibe_surf.browser.agen_browser_profile import AgentBrowserProfile
from typing import Self
from uuid_extensions import uuid7str
import httpx
from browser_use.browser.views import BrowserStateSummary, TabInfo
from browser_use.dom.views import EnhancedDOMTreeNode, TargetInfo
from browser_use.observability import observe_debug
from cdp_use import CDPClient
from browser_use.browser.events import (
    AgentFocusChangedEvent,
    BrowserConnectedEvent,
    BrowserErrorEvent,
    BrowserLaunchEvent,
    BrowserLaunchResult,
    BrowserStartEvent,
    BrowserStateRequestEvent,
    BrowserStopEvent,
    BrowserStoppedEvent,
    CloseTabEvent,
    FileDownloadedEvent,
    NavigateToUrlEvent,
    NavigationCompleteEvent,
    NavigationStartedEvent,
    SwitchTabEvent,
    TabClosedEvent,
    TabCreatedEvent,
)
from browser_use.browser.profile import BrowserProfile, ProxySettings

DEFAULT_BROWSER_PROFILE = AgentBrowserProfile()


class AgentBrowserSession(BrowserSession):
    """Isolated browser session for a specific agent."""

    def __init__(
            self,
            # Core configuration
            id: str | None = None,
            cdp_url: str | None = None,
            is_local: bool = False,
            browser_profile: AgentBrowserProfile | None = None,
            # Custom AgentBrowserSession fields
            main_browser_session: BrowserSession | None = None,
            # BrowserProfile fields that can be passed directly
            # From BrowserConnectArgs
            headers: dict[str, str] | None = None,
            # From BrowserLaunchArgs
            env: dict[str, str | float | bool] | None = None,
            executable_path: str | Path | None = None,
            headless: bool | None = None,
            args: list[str] | None = None,
            ignore_default_args: list[str] | list[bool] | None = None,
            channel: str | None = None,
            chromium_sandbox: bool | None = None,
            devtools: bool | None = None,
            downloads_path: str | Path | None = None,
            traces_dir: str | Path | None = None,
            # From BrowserContextArgs
            accept_downloads: bool | None = None,
            permissions: list[str] | None = None,
            user_agent: str | None = None,
            screen: dict | None = None,
            viewport: dict | None = None,
            no_viewport: bool | None = None,
            device_scale_factor: float | None = None,
            record_har_content: str | None = None,
            record_har_mode: str | None = None,
            record_har_path: str | Path | None = None,
            record_video_dir: str | Path | None = None,
            # From BrowserLaunchPersistentContextArgs
            user_data_dir: str | Path | None = None,
            # From BrowserNewContextArgs
            storage_state: str | Path | dict[str, Any] | None = None,
            # BrowserProfile specific fields
            disable_security: bool | None = None,
            deterministic_rendering: bool | None = None,
            allowed_domains: list[str] | None = None,
            keep_alive: bool | None = None,
            proxy: ProxySettings | None = None,
            enable_default_extensions: bool | None = None,
            window_size: dict | None = None,
            window_position: dict | None = None,
            cross_origin_iframes: bool | None = None,
            minimum_wait_page_load_time: float | None = None,
            wait_for_network_idle_page_load_time: float | None = None,
            wait_between_actions: float | None = None,
            highlight_elements: bool | None = None,
            filter_highlight_ids: bool | None = None,
            auto_download_pdfs: bool | None = None,
            profile_directory: str | None = None,
            cookie_whitelist_domains: list[str] | None = None,
            # AgentBrowserProfile specific fields
            custom_extensions: list[str] | None = None,
    ):
        # Filter out AgentBrowserSession specific parameters
        agent_session_params = {
            'main_browser_session': main_browser_session,
        }

        # Get all browser profile parameters
        profile_kwargs = {k: v for k, v in locals().items()
                          if k not in ['self', 'browser_profile', 'id', 'main_browser_session']
                          and v is not None}

        # Apply BrowserSession's is_local logic first
        effective_is_local = is_local
        if is_local is False and executable_path is not None:
            effective_is_local = True
        if not cdp_url:
            effective_is_local = True

        # Always include is_local in profile_kwargs to ensure it's properly set
        profile_kwargs['is_local'] = effective_is_local

        # Create AgentBrowserProfile from direct parameters or use provided one
        if browser_profile is not None:
            # Always merge to ensure is_local logic is applied
            merged_kwargs = {**browser_profile.model_dump(), **profile_kwargs}
            resolved_browser_profile = AgentBrowserProfile(**merged_kwargs)
        else:
            resolved_browser_profile = AgentBrowserProfile(**profile_kwargs)

        # Initialize the Pydantic model directly (like BrowserSession does)
        # Don't call BrowserSession.__init__ as it would recreate BrowserProfile and lose custom_extensions
        from pydantic import BaseModel
        BaseModel.__init__(
            self,
            id=id or str(uuid7str()),
            browser_profile=resolved_browser_profile,
        )

        # Set AgentBrowserSession specific fields
        self.main_browser_session = main_browser_session

    # Override browser_profile field to ensure it's always AgentBrowserProfile
    browser_profile: AgentBrowserProfile = Field(
        default_factory=lambda: DEFAULT_BROWSER_PROFILE,
        description='AgentBrowserProfile() options to use for the session',
    )
    main_browser_session: BrowserSession | None = Field(default=None)

    async def connect(self, cdp_url: str | None = None) -> Self:
        """Connect to a remote chromium-based browser via CDP using cdp-use.

        This MUST succeed or the browser is unusable. Fails hard on any error.
        """

        self.browser_profile.cdp_url = cdp_url or self.cdp_url
        if not self.cdp_url:
            raise RuntimeError('Cannot setup CDP connection without CDP URL')

        if not self.cdp_url.startswith('ws'):
            # If it's an HTTP URL, fetch the WebSocket URL from /json/version endpoint
            url = self.cdp_url.rstrip('/')
            if not url.endswith('/json/version'):
                url = url + '/json/version'

            # Run a tiny HTTP client to query for the WebSocket URL from the /json/version endpoint
            async with httpx.AsyncClient() as client:
                headers = self.browser_profile.headers or {}
                version_info = await client.get(url, headers=headers)
                self.browser_profile.cdp_url = version_info.json()['webSocketDebuggerUrl']

        assert self.cdp_url is not None

        browser_location = 'local browser' if self.is_local else 'remote browser'
        self.logger.debug(
            f'🌎 Connecting to existing chromium-based browser via CDP: {self.cdp_url} -> ({browser_location})')

        try:
            # Import cdp-use client

            # Convert HTTP URL to WebSocket URL if needed

            # Create and store the CDP client for direct CDP communication
            self._cdp_client_root = CDPClient(self.cdp_url)
            assert self._cdp_client_root is not None
            await self._cdp_client_root.start()
            await self._cdp_client_root.send.Target.setAutoAttach(
                params={'autoAttach': True, 'waitForDebuggerOnStart': False, 'flatten': True}
            )
            self.logger.debug('CDP client connected successfully')

            # Get browser targets to find available contexts/pages
            targets = await self._cdp_client_root.send.Target.getTargets()

            # Find main browser pages (avoiding iframes, workers, extensions, etc.)
            page_targets: list[TargetInfo] = [
                t
                for t in targets['targetInfos']
                if self._is_valid_target(
                    t, include_http=True, include_about=True, include_pages=True, include_iframes=False,
                    include_workers=False
                )
            ]

            # Check for chrome://newtab pages and immediately redirect them
            # to about:blank to avoid JS issues from CDP on chrome://* urls
            from browser_use.utils import is_new_tab_page

            # Collect all targets that need redirection
            redirected_targets = []
            redirect_sessions = {}  # Store sessions created for redirection to potentially reuse
            for target in page_targets:
                target_url = target.get('url', '')
                if is_new_tab_page(target_url) and target_url != '':
                    # Redirect chrome://newtab to about:blank to avoid JS issues preventing driving chrome://newtab
                    target_id = target['targetId']
                    self.logger.debug(f'🔄 Redirecting {target_url} to about:blank for target {target_id}')
                    try:
                        # Create a CDP session for redirection (minimal domains to avoid duplicate event handlers)
                        # Only enable Page domain for navigation, avoid duplicate event handlers
                        redirect_session = await CDPSession.for_target(self._cdp_client_root, target_id,
                                                                       domains=['Page'])
                        # Navigate to about:blank
                        await redirect_session.cdp_client.send.Page.navigate(
                            params={'url': ''}, session_id=redirect_session.session_id
                        )
                        redirected_targets.append(target_id)
                        redirect_sessions[target_id] = redirect_session  # Store for potential reuse
                        # Update the target's URL in our list for later use
                        target['url'] = ''
                        # Small delay to ensure navigation completes
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        self.logger.warning(f'Failed to redirect {target_url} to about:blank: {e}')

            # Log summary of redirections
            if redirected_targets:
                self.logger.debug(f'Redirected {len(redirected_targets)} chrome://newtab pages to about:blank')

            if not page_targets:
                # No pages found, create a new one
                new_target = await self._cdp_client_root.send.Target.createTarget(params={'url': ''})
                target_id = new_target['targetId']
                self.logger.debug(f'📄 Created new blank page with target ID: {target_id}')
            else:
                # Use the first available page
                target_id = [page for page in page_targets if page.get('type') == 'page'][0]['targetId']
                self.logger.debug(f'📄 Using existing page with target ID: {target_id}')

            # Store the current page target ID and add to pool
            # Reuse redirect session if available, otherwise create new one
            if target_id in redirect_sessions:
                self.logger.debug(f'Reusing redirect session for target {target_id}')
                self.agent_focus = redirect_sessions[target_id]
            else:
                # For the initial connection, we'll use the shared root WebSocket
                self.agent_focus = await CDPSession.for_target(self._cdp_client_root, target_id, new_socket=False)
            if self.agent_focus:
                self._cdp_session_pool[target_id] = self.agent_focus

            # Enable proxy authentication handling if configured
            await self._setup_proxy_auth()

            # Verify the session is working
            try:
                if self.agent_focus:
                    assert self.agent_focus.title != 'Unknown title'
                else:
                    raise RuntimeError('Failed to create CDP session')
            except Exception as e:
                self.logger.warning(f'Failed to create CDP session: {e}')
                raise

            # Dispatch TabCreatedEvent for all initial tabs (so watchdogs can initialize)
            # This replaces the duplicated logic from navigation_watchdog's _initialize_agent_focus
            for idx, target in enumerate(page_targets):
                target_url = target.get('url', '')
                self.logger.debug(f'Dispatching TabCreatedEvent for initial tab {idx}: {target_url}')
                await self.event_bus.dispatch(TabCreatedEvent(url=target_url, target_id=target['targetId']))

            # Dispatch initial focus event
            if page_targets:
                initial_url = page_targets[0].get('url', '')
                await self.event_bus.dispatch(
                    AgentFocusChangedEvent(target_id=page_targets[0]['targetId'], url=initial_url))
                self.logger.debug(f'Initial agent focus set to tab 0: {initial_url}')

        except Exception as e:
            # Fatal error - browser is not usable without CDP connection
            self.logger.error(f'❌ FATAL: Failed to setup CDP connection: {e}')
            self.logger.error('❌ Browser cannot continue without CDP connection')
            # Clean up any partial state
            self._cdp_client_root = None
            self.agent_focus = None
            # Re-raise as a fatal error
            raise RuntimeError(f'Failed to establish CDP connection to browser: {e}') from e

        return self

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
        return self

    async def disconnect_agent(self) -> None:
        """Disconnect all agent-specific CDP sessions and cleanup security context."""
        for session in self._cdp_session_pool.values():
            await session.disconnect()
        self._cdp_session_pool.clear()
        self.main_browser_session = None

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
        if self.main_browser_session is not None:
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

        from browser_use.browser.watchdogs.downloads_watchdog import DownloadsWatchdog
        from browser_use.browser.watchdogs.local_browser_watchdog import LocalBrowserWatchdog
        from browser_use.browser.watchdogs.permissions_watchdog import PermissionsWatchdog
        from browser_use.browser.watchdogs.popups_watchdog import PopupsWatchdog
        from browser_use.browser.watchdogs.screenshot_watchdog import ScreenshotWatchdog
        from browser_use.browser.watchdogs.security_watchdog import SecurityWatchdog

        # NOTE: AboutBlankWatchdog is deliberately excluded to disable DVD animation

        self.logger.info('🚫 VibeSurfBrowserSession: AboutBlankWatchdog disabled - no DVD animation will be shown')

        # Initialize DownloadsWatchdog
        # DownloadsWatchdog.model_rebuild()
        # self._downloads_watchdog = DownloadsWatchdog(event_bus=self.event_bus, browser_session=self)
        # self._downloads_watchdog.attach_to_session()
        # if self.browser_profile.auto_download_pdfs:
        #     self.logger.info('📄 PDF auto-download enabled for this session')

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
        # PermissionsWatchdog.model_rebuild()
        # self._permissions_watchdog = PermissionsWatchdog(event_bus=self.event_bus, browser_session=self)
        # self._permissions_watchdog.attach_to_session()

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

    def get_cdp_session_pool(self):
        return self._cdp_session_pool

    async def active_focus_page(self):
        if self.agent_focus is None:
            self.logger.info('No active focus page found, cannot active!')
            return
        await self.get_or_create_cdp_session(self.agent_focus.target_id, focus=True)

    async def navigate_to_url(self, url: str, new_tab: bool = False) -> Optional[str]:
        """
        Concurrent navigation method that bypasses serial bottlenecks in on_NavigateToUrlEvent.
        
        This method performs minimal event dispatching and direct CDP calls for maximum concurrency.
        """
        if not self.agent_focus:
            self.logger.warning('Cannot navigate - browser not connected')
            return None

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
        finally:
            return target_id

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

    @observe_debug(ignore_input=True, ignore_output=True, name='get_tabs')
    async def get_tabs(self) -> list[TabInfo]:
        """Get information about all open tabs using CDP Target.getTargetInfo for speed."""
        tabs = []

        # Safety check - return empty list if browser not connected yet
        if not self._cdp_client_root:
            return tabs

        # Get all page targets using CDP
        pages = await self._cdp_get_all_pages()

        for i, page_target in enumerate(pages):
            target_id = page_target['targetId']
            url = page_target['url']

            # Try to get the title directly from Target.getTargetInfo - much faster!
            # The initial getTargets() doesn't include title, but getTargetInfo does
            try:
                target_info = await self.cdp_client.send.Target.getTargetInfo(params={'targetId': target_id})
                # The title is directly available in targetInfo
                title = target_info.get('targetInfo', {}).get('title', '')

                # Skip JS execution for chrome:// pages and new tab pages
                if not title:
                    # For chrome:// pages without a title, use the URL itself
                    title = url

                # Special handling for PDF pages without titles
                if (not title or title == '') and (url.endswith('.pdf') or 'pdf' in url):
                    # PDF pages might not have a title, use URL filename
                    try:
                        from urllib.parse import urlparse

                        filename = urlparse(url).path.split('/')[-1]
                        if filename:
                            title = filename
                    except Exception:
                        pass

            except Exception as e:
                # Fallback to basic title handling
                self.logger.debug(
                    f'⚠️ Failed to get target info for tab #{i}: {_log_pretty_url(url)} - {type(e).__name__}')
                title = ''

            tab_info = TabInfo(
                target_id=target_id,
                url=url,
                title=title,
                parent_target_id=None,
            )
            tabs.append(tab_info)

        return tabs

    async def refresh_page(self):
        cdp_session = await self.browser_session.get_or_create_cdp_session()
        try:
            # Reload the target
            await cdp_session.cdp_client.send.Page.reload(session_id=cdp_session.session_id)

            # Wait for reload
            await asyncio.sleep(1.0)

            self.logger.info('🔄 Target refreshed')
        except Exception as e:
            raise
