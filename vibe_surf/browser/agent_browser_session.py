from __future__ import annotations

import asyncio
import os
import pdb
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, Union, cast, Optional
from cdp_use.cdp.target import AttachedToTargetEvent, SessionID, TargetID
from browser_use.browser.session import BrowserSession, CDPSession
from pydantic import Field
from browser_use.browser.events import (
    NavigationCompleteEvent,
)
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
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
            ignore_default_args: list[str] | Literal[True] | None = None,
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
            record_video_framerate: int | None = None,
            record_video_size: dict | None = None,
            # From BrowserLaunchPersistentContextArgs
            user_data_dir: str | Path | None = None,
            # From BrowserNewContextArgs
            storage_state: str | Path | dict[str, Any] | None = None,
            # BrowserProfile specific fields
            use_cloud: bool | None = None,
            cloud_browser: bool | None = None,  # Backward compatibility alias
            disable_security: bool | None = None,
            deterministic_rendering: bool | None = None,
            allowed_domains: list[str] | None = None,
            keep_alive: bool | None = None,
            proxy: ProxySettings | None = None,
            enable_default_extensions: bool | None = None,
            window_size: dict | None = None,
            window_position: dict | None = None,
            minimum_wait_page_load_time: float | None = None,
            wait_for_network_idle_page_load_time: float | None = None,
            wait_between_actions: float | None = None,
            filter_highlight_ids: bool | None = None,
            auto_download_pdfs: bool | None = None,
            profile_directory: str | None = None,
            cookie_whitelist_domains: list[str] | None = None,
            # DOM extraction layer configuration
            cross_origin_iframes: bool | None = None,
            highlight_elements: bool | None = None,
            dom_highlight_elements: bool | None = None,
            paint_order_filtering: bool | None = None,
            # Iframe processing limits
            max_iframes: int | None = None,
            max_iframe_depth: int | None = None,
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

    _connection_lock: Any = PrivateAttr(default=None)

    @observe_debug(ignore_input=True, ignore_output=True, name='browser_start_event_handler')
    async def on_BrowserStartEvent(self, event: BrowserStartEvent) -> dict[str, str]:
        """Handle browser start request.

        Returns:
            Dict with 'cdp_url' key containing the CDP URL

        Note: This method is idempotent - calling start() multiple times is safe.
        - If already connected, it skips reconnection
        - If you need to reset state, call stop() or kill() first
        """

        # Initialize and attach all watchdogs FIRST so LocalBrowserWatchdog can handle BrowserLaunchEvent
        await self.attach_all_watchdogs()

        try:
            # If no CDP URL, launch local browser or cloud browser
            if not self.cdp_url:
                if self.is_local:
                    # Launch local browser using event-driven approach
                    launch_event = self.event_bus.dispatch(BrowserLaunchEvent())
                    await launch_event

                    # Get the CDP URL from LocalBrowserWatchdog handler result
                    launch_result: BrowserLaunchResult = cast(
                        BrowserLaunchResult, await launch_event.event_result(raise_if_none=True, raise_if_any=True)
                    )
                    self.browser_profile.cdp_url = launch_result.cdp_url
                else:
                    raise ValueError('Got BrowserSession(is_local=False) but no cdp_url was provided to connect to!')

            assert self.cdp_url and '://' in self.cdp_url

            # Use lock to prevent concurrent connection attempts (race condition protection)
            async with self._connection_lock:
                # Only connect if not already connected
                if self._cdp_client_root is None:
                    # Setup browser via CDP (for both local and remote cases)
                    await self.connect(cdp_url=self.cdp_url)
                    assert self.cdp_client is not None

                    # Notify that browser is connected (single place)
                    self.event_bus.dispatch(BrowserConnectedEvent(cdp_url=self.cdp_url))

            # Return the CDP URL for other components
            return {'cdp_url': self.cdp_url}

        except Exception as e:
            self.event_bus.dispatch(
                BrowserErrorEvent(
                    error_type='BrowserStartEventError',
                    message=f'Failed to start browser: {type(e).__name__} {e}',
                    details={'cdp_url': self.cdp_url, 'is_local': self.is_local},
                )
            )
            raise

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
                params={'autoAttach': False, 'waitForDebuggerOnStart': False, 'flatten': True}
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
            if not page_targets:
                # No pages found, create a new one
                new_target = await self._cdp_client_root.send.Target.createTarget(params={'url': 'chrome://newtab/'})
                target_id = new_target['targetId']
                self.logger.debug(f'📄 Created new blank page with target ID: {target_id}')
            else:
                # Use the first available page
                target_id = [page for page in page_targets if page.get('type') == 'page'][0]['targetId']
                self.logger.debug(f'📄 Using existing page with target ID: {target_id}')

            self.agent_focus = await CDPSession.for_target(self._cdp_client_root, target_id)

            if self.agent_focus:
                self._cdp_session_pool[target_id] = self.agent_focus
                
                # Show welcome modal with extension setup instructions
                self.logger.info("Showing VibeSurf Welcome Modal")
                
                # Calculate extension path
                import vibe_surf
                import os
                vibe_surf_dir = os.path.dirname(vibe_surf.__file__)
                extension_path = os.path.join(vibe_surf_dir, 'chrome_extension')
                
                extension_path_js = extension_path.replace('\\', '/')
                
                welcome_js = f"""
                (function showVibeSurfWelcome() {{
                    // Check if user has dismissed the welcome modal
                    const dismissed = localStorage.getItem('vibesurf_welcome_dismissed');
                    if (dismissed === 'true') {{
                        console.log('[VibeSurf] Welcome modal was previously dismissed');
                        return;
                    }}
                    
                    // Add styles using createElement to avoid TrustedHTML issues
                    const style = document.createElement('style');
                    style.textContent = `
                        @keyframes fadeIn {{
                            from {{ opacity: 0; }}
                            to {{ opacity: 1; }}
                        }}
                        @keyframes slideIn {{
                            from {{ transform: translateY(-30px) scale(0.95); opacity: 0; }}
                            to {{ transform: translateY(0) scale(1); opacity: 1; }}
                        }}
                        @keyframes fadeOut {{
                            from {{ opacity: 1; }}
                            to {{ opacity: 0; }}
                        }}
                        @keyframes slideOut {{
                            from {{ transform: translateY(0) scale(1); opacity: 1; }}
                            to {{ transform: translateY(-30px) scale(0.95); opacity: 0; }}
                        }}
                        @keyframes pulse {{
                            0%, 100% {{ transform: scale(1); }}
                            50% {{ transform: scale(1.05); }}
                        }}
                        .vibesurf-title {{
                            font-size: 36px;
                            font-weight: 800;
                            margin: 0 0 12px 0;
                            text-align: left;
                            letter-spacing: -0.5px;
                            line-height: 1.2;
                        }}
                        .vibesurf-subtitle {{
                            font-size: 18px;
                            margin: 0 0 32px 0;
                            text-align: left;
                            opacity: 0.92;
                            font-weight: 400;
                            line-height: 1.5;
                        }}
                        .vibesurf-section {{
                            background: rgba(111, 233, 255, 0.08);
                            border-radius: 16px;
                            padding: 24px;
                            margin-bottom: 16px;
                            backdrop-filter: blur(10px);
                            border: 1px solid rgba(111, 233, 255, 0.15);
                        }}
                        .vibesurf-section-title {{
                            font-size: 20px;
                            font-weight: 700;
                            margin: 0 0 16px 0;
                            display: flex;
                            align-items: center;
                            gap: 8px;
                        }}
                        .vibesurf-steps {{
                            list-style: none;
                            padding: 0;
                            margin: 0;
                        }}
                        .vibesurf-steps li {{
                            padding: 10px 0;
                            padding-left: 32px;
                            position: relative;
                            line-height: 1.6;
                            font-size: 15px;
                        }}
                        .vibesurf-steps li:before {{
                            content: '✓';
                            position: absolute;
                            left: 0;
                            font-weight: bold;
                            color: #6FE9FF;
                            font-size: 18px;
                            width: 24px;
                            height: 24px;
                            background: rgba(111, 233, 255, 0.15);
                            border-radius: 50%;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            line-height: 1;
                        }}
                        .vibesurf-path-box {{
                            background: rgba(0, 0, 0, 0.4);
                            border-radius: 10px;
                            padding: 14px 16px;
                            margin: 12px 0 0 0;
                            font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
                            font-size: 13px;
                            word-break: break-all;
                            display: flex;
                            align-items: center;
                            gap: 12px;
                            border: 1px solid rgba(111, 233, 255, 0.2);
                        }}
                        .vibesurf-path-text {{
                            flex: 1;
                            user-select: all;
                            color: #6FE9FF;
                        }}
                        .vibesurf-copy-btn {{
                            background: rgba(111, 233, 255, 0.15);
                            border: 1px solid rgba(111, 233, 255, 0.3);
                            border-radius: 8px;
                            padding: 8px 16px;
                            color: #6FE9FF;
                            cursor: pointer;
                            font-size: 13px;
                            font-weight: 600;
                            transition: all 0.2s ease;
                            white-space: nowrap;
                            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
                        }}
                        .vibesurf-copy-btn:hover {{
                            background: rgba(111, 233, 255, 0.25);
                            border-color: rgba(111, 233, 255, 0.5);
                            transform: translateY(-1px);
                            box-shadow: 0 4px 12px rgba(111, 233, 255, 0.4);
                        }}
                        .vibesurf-copy-btn:active {{
                            transform: translateY(0);
                        }}
                        .vibesurf-warning {{
                            background: rgba(255, 193, 7, 0.15);
                            border-left: 4px solid #FFC107;
                            padding: 18px;
                            border-radius: 12px;
                            font-size: 14px;
                            line-height: 1.7;
                            border: 1px solid rgba(255, 193, 7, 0.3);
                        }}
                        .vibesurf-warning strong {{
                            font-size: 15px;
                            display: block;
                            margin-bottom: 8px;
                        }}
                        .vibesurf-footer {{
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            margin-top: 28px;
                            padding-top: 24px;
                            border-top: 1px solid rgba(255, 255, 255, 0.15);
                        }}
                        .vibesurf-checkbox-container {{
                            display: flex;
                            align-items: center;
                            gap: 10px;
                            cursor: pointer;
                            font-size: 15px;
                            user-select: none;
                        }}
                        .vibesurf-checkbox-container input {{
                            cursor: pointer;
                            width: 20px;
                            height: 20px;
                            accent-color: #60D394;
                        }}
                        .vibesurf-btn {{
                            background: linear-gradient(135deg, #6FE9FF 0%, #5AD4EB 100%);
                            color: #0D2435;
                            border: none;
                            border-radius: 12px;
                            padding: 14px 32px;
                            font-size: 16px;
                            font-weight: 700;
                            cursor: pointer;
                            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                            box-shadow: 0 4px 16px rgba(111, 233, 255, 0.3);
                            letter-spacing: 0.3px;
                        }}
                        .vibesurf-btn:hover {{
                            background: linear-gradient(135deg, #7FEFFF 0%, #6FE4F5 100%);
                            transform: translateY(-2px) scale(1.02);
                            box-shadow: 0 8px 24px rgba(111, 233, 255, 0.5);
                            animation: pulse 0.6s ease;
                        }}
                        .vibesurf-btn:active {{
                            transform: translateY(0) scale(0.98);
                        }}
                    `;
                    document.head.appendChild(style);
                    
                    // Create modal overlay
                    const overlay = document.createElement('div');
                    overlay.id = 'vibesurf-welcome-overlay';
                    overlay.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0, 0, 0, 0.7);
                        backdrop-filter: blur(5px);
                        z-index: 999999;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                        animation: fadeIn 0.3s ease-in;
                    `;
                    
                    // Create modal container
                    const modal = document.createElement('div');
                    modal.style.cssText = `
                        background: linear-gradient(145deg, #0D2435 0%, #14334A 50%, #1A4059 100%);
                        border-radius: 24px;
                        padding: 48px;
                        max-width: 650px;
                        width: 92%;
                        box-shadow: 0 24px 80px rgba(26, 64, 89, 0.8), 0 0 0 1px rgba(111, 233, 255, 0.2);
                        color: white;
                        animation: slideIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
                        position: relative;
                    `;
                    
                    // Create title
                    const title = document.createElement('h1');
                    title.className = 'vibesurf-title';
                    title.textContent = '🎉 Welcome to VibeSurf!';
                    modal.appendChild(title);
                    
                    // Create subtitle
                    const subtitle = document.createElement('p');
                    subtitle.className = 'vibesurf-subtitle';
                    subtitle.textContent = "Your Personal AI Browser Assistant - Let's Vibe Surfing the World!";
                    modal.appendChild(subtitle);
                    
                    // Create section 1: How to Enable
                    const section1 = document.createElement('div');
                    section1.className = 'vibesurf-section';
                    
                    const section1Title = document.createElement('h2');
                    section1Title.className = 'vibesurf-section-title';
                    section1Title.textContent = '📌 How to Enable the Extension';
                    section1.appendChild(section1Title);
                    
                    const stepsList1 = document.createElement('ul');
                    stepsList1.className = 'vibesurf-steps';
                    
                    const steps1 = [
                        'Click the Extensions icon (puzzle piece) in the top-right corner',
                        'Find VibeSurf in the list',
                        'Click the Pin icon to keep VibeSurf visible in your toolbar'
                    ];
                    
                    steps1.forEach(stepText => {{
                        const li = document.createElement('li');
                        li.textContent = stepText;
                        stepsList1.appendChild(li);
                    }});
                    
                    section1.appendChild(stepsList1);
                    modal.appendChild(section1);
                    
                    // Create warning section
                    const warningDiv = document.createElement('div');
                    warningDiv.className = 'vibesurf-warning';
                    
                    const warningStrong = document.createElement('strong');
                    warningStrong.textContent = '⚠️ Important Note: ';
                    warningDiv.appendChild(warningStrong);
                    
                    warningDiv.appendChild(document.createTextNode("Since Chrome 142+, extensions must be loaded manually. If you don't see VibeSurf:"));
                    
                    const warningSteps = document.createElement('ul');
                    warningSteps.className = 'vibesurf-steps';
                    warningSteps.style.marginTop = '10px';
                    
                    const warningStep1 = document.createElement('li');
                    warningStep1.textContent = 'Open chrome://extensions';
                    warningSteps.appendChild(warningStep1);
                    
                    const warningStep2 = document.createElement('li');
                    warningStep2.textContent = 'Enable Developer mode';
                    warningSteps.appendChild(warningStep2);
                    
                    const warningStep3 = document.createElement('li');
                    warningStep3.textContent = 'Click "Load unpacked" and select the following path:';
                    warningSteps.appendChild(warningStep3);
                    
                    // Add path box after step 3
                    const pathBox = document.createElement('div');
                    pathBox.className = 'vibesurf-path-box';
                    pathBox.style.marginTop = '12px';
                    pathBox.style.marginLeft = '32px';
                    
                    const pathText = document.createElement('span');
                    pathText.className = 'vibesurf-path-text';
                    pathText.id = 'extension-path';
                    pathText.textContent = '{extension_path_js}';
                    pathBox.appendChild(pathText);
                    
                    const copyBtn = document.createElement('button');
                    copyBtn.className = 'vibesurf-copy-btn';
                    copyBtn.id = 'copy-path-btn';
                    copyBtn.textContent = '📋 Copy';
                    pathBox.appendChild(copyBtn);
                    
                    warningSteps.appendChild(pathBox);
                    
                    warningDiv.appendChild(warningSteps);
                    modal.appendChild(warningDiv);
                    
                    // Create footer
                    const footer = document.createElement('div');
                    footer.className = 'vibesurf-footer';
                    
                    const checkboxLabel = document.createElement('label');
                    checkboxLabel.className = 'vibesurf-checkbox-container';
                    
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.id = 'dont-show-again';
                    checkboxLabel.appendChild(checkbox);
                    
                    const checkboxText = document.createElement('span');
                    checkboxText.textContent = "Don't show this again";
                    checkboxLabel.appendChild(checkboxText);
                    
                    footer.appendChild(checkboxLabel);
                    
                    const gotItBtn = document.createElement('button');
                    gotItBtn.className = 'vibesurf-btn';
                    gotItBtn.id = 'got-it-btn';
                    gotItBtn.textContent = 'Got It!';
                    footer.appendChild(gotItBtn);
                    
                    modal.appendChild(footer);
                    
                    // Append to overlay and document
                    overlay.appendChild(modal);
                    document.body.appendChild(overlay);
                    
                    // Copy button functionality
                    copyBtn.addEventListener('click', () => {{
                        const pathTextContent = document.getElementById('extension-path').textContent;
                        navigator.clipboard.writeText(pathTextContent).then(() => {{
                            copyBtn.textContent = '✅ Copied!';
                            setTimeout(() => {{
                                copyBtn.textContent = '📋 Copy';
                            }}, 2000);
                        }}).catch(err => {{
                            console.error('[VibeSurf] Failed to copy:', err);
                            copyBtn.textContent = '❌ Failed';
                            setTimeout(() => {{
                                copyBtn.textContent = '📋 Copy';
                            }}, 2000);
                        }});
                    }});
                    
                    // Close modal function
                    function closeModal() {{
                        overlay.style.animation = 'fadeOut 0.3s ease-out';
                        modal.style.animation = 'slideOut 0.3s ease-out';
                        
                        setTimeout(() => {{
                            if (document.body.contains(overlay)) {{
                                document.body.removeChild(overlay);
                            }}
                        }}, 300);
                        
                        if (checkbox.checked) {{
                            localStorage.setItem('vibesurf_welcome_dismissed', 'true');
                            console.log('[VibeSurf] Welcome modal dismissed permanently');
                        }}
                    }}
                    
                    // Got It button click handler
                    gotItBtn.addEventListener('click', closeModal);
                    
                    // Close when clicking outside modal
                    overlay.addEventListener('click', (e) => {{
                        if (e.target === overlay) {{
                            closeModal();
                        }}
                    }});
                    
                    console.log('[VibeSurf] Welcome modal displayed');
                }})();
                """
                
                try:
                    result = await self.agent_focus.cdp_client.send.Runtime.evaluate(
                        params={'expression': welcome_js, 'returnByValue': True},
                        session_id=self.agent_focus.session_id,
                    )
                    self.logger.info("✅ VibeSurf welcome modal injected successfully")
                except Exception as e:
                    self.logger.warning(f"Failed to inject welcome modal: {e}")

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
                self.event_bus.dispatch(TabCreatedEvent(url=target_url, target_id=target['targetId']))

            # Dispatch initial focus event
            if page_targets:
                initial_url = page_targets[0].get('url', '')
                self.event_bus.dispatch(AgentFocusChangedEvent(target_id=page_targets[0]['targetId'], url=initial_url))
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
            self.agent_focus = await CDPSession.for_target(self._cdp_client_root, target_id)
            # await self.agent_focus.cdp_client.send.Target.activateTarget(
            #     params={'targetId': target_id})
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

    def model_post_init(self, __context) -> None:
        """Register event handlers after model initialization."""
        # Check if handlers are already registered to prevent duplicates
        self._connection_lock = asyncio.Lock()

        from browser_use.browser.watchdog_base import BaseWatchdog

        start_handlers = self.event_bus.handlers.get('BrowserStartEvent', [])
        start_handler_names = [getattr(h, '__name__', str(h)) for h in start_handlers]

        if any('on_BrowserStartEvent' in name for name in start_handler_names):
            raise RuntimeError(
                '[BrowserSession] Duplicate handler registration attempted! '
                'on_BrowserStartEvent is already registered. '
                'This likely means BrowserSession was initialized multiple times with the same EventBus.'
            )

        BaseWatchdog.attach_handler_to_session(self, BrowserStartEvent, self.on_BrowserStartEvent)
        BaseWatchdog.attach_handler_to_session(self, BrowserStopEvent, self.on_BrowserStopEvent)
        BaseWatchdog.attach_handler_to_session(self, NavigateToUrlEvent, self.on_NavigateToUrlEvent)
        BaseWatchdog.attach_handler_to_session(self, SwitchTabEvent, self.on_SwitchTabEvent)
        BaseWatchdog.attach_handler_to_session(self, TabCreatedEvent, self.on_TabCreatedEvent)
        BaseWatchdog.attach_handler_to_session(self, TabClosedEvent, self.on_TabClosedEvent)
        BaseWatchdog.attach_handler_to_session(self, AgentFocusChangedEvent, self.on_AgentFocusChangedEvent)
        # BaseWatchdog.attach_handler_to_session(self, FileDownloadedEvent, self.on_FileDownloadedEvent)
        BaseWatchdog.attach_handler_to_session(self, CloseTabEvent, self.on_CloseTabEvent)

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
                    params={'url': 'chrome://newtab/', 'newWindow': False, 'background': False}
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
            session = await self.get_or_create_cdp_session(target_id, focus=True)
            await session.cdp_client.send.Page.navigate(
                params={
                    'url': url,
                    'transitionType': 'address_bar',
                },
                session_id=session.session_id,
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

    async def _wait_for_stable_network(self, target_id=None, max_attempt=3):
        """Wait for page stability - simplified for CDP-only branch."""
        cdp_session = await self.get_or_create_cdp_session(target_id=target_id)
        for _ in range(max_attempt):
            try:
                ready_state = await cdp_session.cdp_client.send.Runtime.evaluate(
                    params={'expression': 'document.readyState'}, session_id=cdp_session.session_id
                )
                if ready_state and ready_state.get("value", "loading") == "complete":
                    break
            except Exception as e:
                print(e)
            await asyncio.sleep(1.0)

    async def take_screenshot(self, target_id: Optional[str] = None,
                              path: str | None = None,
                              full_page: bool = False,
                              format: str = 'png',
                              quality: int | None = None,
                              clip: dict | None = None,
                              ) -> bytes:
        """
        Concurrent screenshot method that bypasses serial bottlenecks in ScreenshotWatchdog.
        
        This method performs direct CDP calls for maximum concurrency.
        """

        cdp_session = await self.get_or_create_cdp_session(target_id, focus=False)
        await self._wait_for_stable_network(target_id)

        try:
            import base64
            from cdp_use.cdp.page import CaptureScreenshotParameters

            # Build parameters dict explicitly to satisfy TypedDict expectations
            params: CaptureScreenshotParameters = {
                'format': format,
                'captureBeyondViewport': full_page,
            }

            if quality is not None and format == 'jpeg':
                params['quality'] = quality

            if clip:
                params['clip'] = {
                    'x': clip['x'],
                    'y': clip['y'],
                    'width': clip['width'],
                    'height': clip['height'],
                    'scale': 1,
                }

            params = CaptureScreenshotParameters(**params)

            result = await cdp_session.cdp_client.send.Page.captureScreenshot(params=params,
                                                                              session_id=cdp_session.session_id)

            if not result or 'data' not in result:
                raise Exception('Screenshot failed - no data returned')

            screenshot_data = base64.b64decode(result['data'])

            if path:
                Path(path).write_bytes(screenshot_data)

            return screenshot_data

        except Exception as e:
            self.logger.error(f'Concurrent screenshot failed: {type(e).__name__}: {e}')
            raise

    async def take_screenshot_base64(self, target_id: Optional[str] = None,
                                     full_page: bool = False,
                                     format: str = 'png',
                                     quality: int | None = None,
                                     clip: dict | None = None,
                                     ) -> str:
        """
        Concurrent screenshot method that bypasses serial bottlenecks in ScreenshotWatchdog.

        This method performs direct CDP calls for maximum concurrency.
        """

        cdp_session = await self.get_or_create_cdp_session(target_id, focus=False)
        await self._wait_for_stable_network(target_id)

        try:
            import base64
            from cdp_use.cdp.page import CaptureScreenshotParameters

            # Build parameters dict explicitly to satisfy TypedDict expectations
            params: CaptureScreenshotParameters = {
                'format': format,
                'captureBeyondViewport': full_page,
            }

            if quality is not None and format == 'jpeg':
                params['quality'] = quality

            if clip:
                params['clip'] = {
                    'x': clip['x'],
                    'y': clip['y'],
                    'width': clip['width'],
                    'height': clip['height'],
                    'scale': 1,
                }

            params = CaptureScreenshotParameters(**params)

            result = await cdp_session.cdp_client.send.Page.captureScreenshot(params=params,
                                                                              session_id=cdp_session.session_id)

            if not result or 'data' not in result:
                raise Exception('Screenshot failed - no data returned')

            return result['data']

        except Exception as e:
            self.logger.error(f'Concurrent screenshot failed: {type(e).__name__}: {e}')
            raise

    async def get_or_create_cdp_session(
            self, target_id: TargetID | None = None, focus: bool = True
    ) -> CDPSession:
        """Get or create a CDP session for a target.

        Args:
                target_id: Target ID to get session for. If None, uses current agent focus.
                focus: If True, switches agent focus to this target. If False, just returns session without changing focus.

        Returns:
                CDPSession for the specified target.
        """
        assert self.cdp_url is not None, 'CDP URL not set - browser may not be configured or launched yet'
        assert self._cdp_client_root is not None, 'Root CDP client not initialized - browser may not be connected yet'
        assert self.agent_focus is not None, 'CDP session not initialized - browser may not be connected yet'

        # If no target_id specified, use the current target_id
        if target_id is None:
            target_id = self.agent_focus.target_id

        # Check if we already have a session for this target in the pool
        if target_id in self._cdp_session_pool:
            session = self._cdp_session_pool[target_id]
            if focus and self.agent_focus.target_id != target_id:
                self.logger.debug(
                    f'[get_or_create_cdp_session] Switching agent focus from {self.agent_focus.target_id} to {target_id}'
                )
                self.agent_focus = session
            if focus:
                # await session.cdp_client.send.Target.activateTarget(params={'targetId': session.target_id})
                await session.cdp_client.send.Runtime.runIfWaitingForDebugger(session_id=session.session_id)
            # else:
            # self.logger.debug(f'[get_or_create_cdp_session] Reusing existing session for {target_id} (focus={focus})')
            return session

        # If it's the current focus target, return that session
        if self.agent_focus.target_id == target_id:
            self._cdp_session_pool[target_id] = self.agent_focus
            return self.agent_focus

        session = await CDPSession.for_target(
            self._cdp_client_root,
            target_id
        )
        self._cdp_session_pool[target_id] = session
        # log length of _cdp_session_pool
        self.logger.debug(f'[get_or_create_cdp_session] new _cdp_session_pool length: {len(self._cdp_session_pool)}')

        # Only change agent focus if requested
        if focus:
            self.logger.debug(
                f'[get_or_create_cdp_session] Switching agent focus from {self.agent_focus.target_id} to {target_id}'
            )
            self.agent_focus = session
            # await session.cdp_client.send.Target.activateTarget(params={'targetId': session.target_id})
            await session.cdp_client.send.Runtime.runIfWaitingForDebugger(session_id=session.session_id)
        else:
            self.logger.debug(
                f'[get_or_create_cdp_session] Created session for {target_id} without changing focus (still on {self.agent_focus.target_id})'
            )

        return session

    async def get_html_content(self, target_id: Optional[str] = None) -> str:
        """
        Get html content of current page
        :return:
        """

        cdp_session = await self.get_or_create_cdp_session(target_id, focus=False)
        await self._wait_for_stable_network(target_id)

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

    async def refresh_page(self, target_id: Optional[str] = None, ):
        try:
            cdp_session = await self.browser_session.get_or_create_cdp_session(target_id)
            # Reload the target
            await cdp_session.cdp_client.send.Page.reload(session_id=cdp_session.session_id)

            # Wait for reload
            await asyncio.sleep(1.0)

            self.logger.info('🔄 Target refreshed')
        except Exception as e:
            raise
