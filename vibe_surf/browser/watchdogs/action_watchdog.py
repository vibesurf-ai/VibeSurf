import asyncio

from browser_use.browser.default_action_watchdog import DefaultActionWatchdog
from browser_use.browser.events import (
	ClickElementEvent,
	GetDropdownOptionsEvent,
	GoBackEvent,
	GoForwardEvent,
	RefreshEvent,
	ScrollEvent,
	ScrollToTextEvent,
	SelectDropdownOptionEvent,
	SendKeysEvent,
	TypeTextEvent,
	UploadFileEvent,
	WaitEvent,
)
from browser_use.browser.views import BrowserError, URLNotAllowedError
from browser_use.browser.watchdog_base import BaseWatchdog
from browser_use.dom.service import EnhancedDOMTreeNode

class CustomActionWatchdog(DefaultActionWatchdog):
    async def on_ClickElementEvent(self, event: ClickElementEvent) -> None:
        """Handle click request with CDP."""
        try:
            # Check if session is alive before attempting any operations
            if not self.browser_session.agent_focus or not self.browser_session.agent_focus.target_id:
                error_msg = 'Cannot execute click: browser session is corrupted (target_id=None). Session may have crashed.'
                self.logger.error(f'⚠️ {error_msg}')
                raise BrowserError(error_msg)

            # Use the provided node
            element_node = event.node
            index_for_logging = element_node.element_index or 'unknown'
            starting_target_id = self.browser_session.agent_focus.target_id

            # Track initial number of tabs to detect new tab opening
            if hasattr(self.browser_session, "main_browser_session") and self.browser_session.main_browser_session:
                initial_target_ids = await self.browser_session.main_browser_session._cdp_get_all_pages()
            else:
                initial_target_ids = await self.browser_session._cdp_get_all_pages()

            # Check if element is a file input (should not be clicked)
            if self.browser_session.is_file_input(element_node):
                msg = f'Index {index_for_logging} - has an element which opens file upload dialog. To upload files please use a specific function to upload files'
                self.logger.info(msg)
                raise BrowserError(
                    'Click triggered a file input element which could not be handled, use the dedicated file upload function instead'
                )

            # Perform the actual click using internal implementation
            await self._click_element_node_impl(element_node, while_holding_ctrl=event.while_holding_ctrl)
            download_path = None  # moved to downloads_watchdog.py

            # Build success message
            if download_path:
                msg = f'Downloaded file to {download_path}'
                self.logger.info(f'💾 {msg}')
            else:
                msg = f'Clicked button with index {index_for_logging}: {element_node.get_all_children_text(max_depth=2)}'
                self.logger.debug(f'🖱️ {msg}')
            self.logger.debug(f'Element xpath: {element_node.xpath}')

            # Wait a bit for potential new tab to be created
            # This is necessary because tab creation is async and might not be immediate
            await asyncio.sleep(1)

            # Clear cached state after click action since DOM might have changed
            self.logger.debug('🔄 Click action completed, clearing cached browser state')
            self.browser_session._cached_browser_state_summary = None
            self.browser_session._cached_selector_map.clear()
            if self.browser_session._dom_watchdog:
                self.browser_session._dom_watchdog.clear_cache()
            # Successfully clicked, always reset session back to parent page session context
            self.browser_session.agent_focus = await self.browser_session.get_or_create_cdp_session(
                target_id=starting_target_id, focus=True
            )

            # Check if a new tab was opened
            if hasattr(self.browser_session, "main_browser_session") and self.browser_session.main_browser_session:
                after_target_ids = await self.browser_session.main_browser_session._cdp_get_all_pages()
            else:
                after_target_ids = await self.browser_session._cdp_get_all_pages()
            new_target_ids = {t['targetId'] for t in after_target_ids} - {t['targetId'] for t in initial_target_ids}
            if new_target_ids:
                new_tab_msg = 'New tab opened - switching to it'
                msg += f' - {new_tab_msg}'
                self.logger.info(f'🔗 {new_tab_msg}')
                new_target_id = new_target_ids.pop()
                if not event.while_holding_ctrl:
                    # if while_holding_ctrl=False it means agent was not expecting a new tab to be opened
                    # so we need to switch to the new tab to make the agent aware of the surprise new tab that was opened.
                    # when while_holding_ctrl=True we dont actually want to switch to it,
                    # we should match human expectations of ctrl+click which opens in the background,
                    # so in multi_act it usually already sends [click_element_by_index(123, while_holding_ctrl=True), switch_tab(tab_id=None)] anyway
                    from browser_use.browser.events import SwitchTabEvent

                    await self.browser_session.get_or_create_cdp_session(
                        target_id=new_target_id, focus=True
                    )
                else:
                    await self.browser_session.get_or_create_cdp_session(
                        target_id=new_target_id, focus=False
                    )

            return None
        except Exception as e:
            raise

    async def _input_text_element_node_impl(self, element_node, text: str, clear_existing: bool = True) -> dict | None:
        """
        Input text into an element using pure CDP with improved focus fallbacks.
        """

        try:
            # Get CDP client
            cdp_session = await self.browser_session.cdp_client_for_node(element_node)

            # Get element info
            backend_node_id = element_node.backend_node_id

            # Track coordinates for metadata
            input_coordinates = None

            # Scroll element into view
            try:
                await cdp_session.cdp_client.send.DOM.scrollIntoViewIfNeeded(
                    params={'backendNodeId': backend_node_id}, session_id=cdp_session.session_id
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.warning(
                    f'⚠️ Failed to focus the page {cdp_session} and scroll element {element_node} into view before typing in text: {type(e).__name__}: {e}'
                )

            # Get object ID for the element
            result = await cdp_session.cdp_client.send.DOM.resolveNode(
                params={'backendNodeId': backend_node_id},
                session_id=cdp_session.session_id,
            )
            assert 'object' in result and 'objectId' in result['object'], (
                'Failed to find DOM element based on backendNodeId, maybe page content changed?'
            )
            object_id = result['object']['objectId']

            # Check element focusability before attempting focus
            element_info = await self._check_element_focusability(element_node, object_id, cdp_session.session_id)
            self.logger.debug(f'Element focusability check: {element_info}')

            # Extract coordinates from element bounds for metadata
            bounds = element_info.get('bounds', {})
            if bounds.get('width', 0) > 0 and bounds.get('height', 0) > 0:
                center_x = bounds['x'] + bounds['width'] / 2
                center_y = bounds['y'] + bounds['height'] / 2
                input_coordinates = {"input_x": center_x, "input_y": center_y}
                self.logger.debug(f'📍 Input coordinates: x={center_x:.1f}, y={center_y:.1f}')

            # Provide helpful warnings for common issues
            if not element_info.get('visible', False):
                self.logger.warning('⚠️ Target element appears to be invisible or has zero dimensions')
            if element_info.get('disabled', False):
                self.logger.warning('⚠️ Target element appears to be disabled')
            if not element_info.get('focusable', False):
                self.logger.warning('⚠️ Target element may not be focusable by standard criteria')

            # Clear existing text if requested
            if clear_existing:
                await cdp_session.cdp_client.send.Runtime.callFunctionOn(
                    params={
                        'functionDeclaration': 'function() { if (this.value !== undefined) this.value = ""; if (this.textContent !== undefined) this.textContent = ""; }',
                        'objectId': object_id,
                    },
                    session_id=cdp_session.session_id,
                )

            # Try multiple focus strategies
            focused_successfully = False

            # Strategy 1: Try CDP DOM.focus (original method)
            try:
                await cdp_session.cdp_client.send.DOM.focus(
                    params={'backendNodeId': backend_node_id},
                    session_id=cdp_session.session_id,
                )
                focused_successfully = True
                self.logger.debug('✅ Element focused using CDP DOM.focus')
            except Exception as e:
                self.logger.debug(f'CDP DOM.focus failed: {e}')

                # Strategy 2: Try JavaScript focus as fallback
                try:
                    await cdp_session.cdp_client.send.Runtime.callFunctionOn(
                        params={
                            'functionDeclaration': 'function() { this.focus(); }',
                            'objectId': object_id,
                        },
                        session_id=cdp_session.session_id,
                    )
                    focused_successfully = True
                    self.logger.debug('✅ Element focused using JavaScript focus()')
                except Exception as js_e:
                    self.logger.debug(f'JavaScript focus failed: {js_e}')

                    # Strategy 3: Try click-to-focus for stubborn elements
                    try:
                        await cdp_session.cdp_client.send.Runtime.callFunctionOn(
                            params={
                                'functionDeclaration': 'function() { this.click(); this.focus(); }',
                                'objectId': object_id,
                            },
                            session_id=cdp_session.session_id,
                        )
                        focused_successfully = True
                        self.logger.debug('✅ Element focused using click + focus combination')
                    except Exception as click_e:
                        self.logger.debug(f'Click + focus failed: {click_e}')

                        # Strategy 4: Try simulated mouse click for maximum compatibility
                        try:
                            # Use coordinates already calculated from element bounds
                            if input_coordinates and 'input_x' in input_coordinates and 'input_y' in input_coordinates:
                                click_x = input_coordinates['input_x']
                                click_y = input_coordinates['input_y']

                                await cdp_session.cdp_client.send.Input.dispatchMouseEvent(
                                    params={
                                        'type': 'mousePressed',
                                        'x': click_x,
                                        'y': click_y,
                                        'button': 'left',
                                        'clickCount': 1,
                                    },
                                    session_id=cdp_session.session_id,
                                )
                                await cdp_session.cdp_client.send.Input.dispatchMouseEvent(
                                    params={
                                        'type': 'mouseReleased',
                                        'x': click_x,
                                        'y': click_y,
                                        'button': 'left',
                                        'clickCount': 1,
                                    },
                                    session_id=cdp_session.session_id,
                                )
                                focused_successfully = True
                                self.logger.debug('✅ Element focused using simulated mouse click')
                            else:
                                self.logger.debug('Element bounds not available for mouse click')
                        except Exception as mouse_e:
                            self.logger.debug(f'Simulated mouse click failed: {mouse_e}')

            # Log focus result
            if not focused_successfully:
                self.logger.warning('⚠️ All focus strategies failed, typing without explicit focus')

            # Type the text character by character
            for char in text:
                # Send keydown (without text to avoid duplication)
                await cdp_session.cdp_client.send.Input.dispatchKeyEvent(
                    params={
                        'type': 'keyDown',
                        'key': char,
                    },
                    session_id=cdp_session.session_id,
                )
                # Send char (for actual text input)
                await cdp_session.cdp_client.send.Input.dispatchKeyEvent(
                    params={
                        'type': 'char',
                        'text': char,
                        'key': char,
                    },
                    session_id=cdp_session.session_id,
                )
                # Send keyup (without text to avoid duplication)
                await cdp_session.cdp_client.send.Input.dispatchKeyEvent(
                    params={
                        'type': 'keyUp',
                        'key': char,
                    },
                    session_id=cdp_session.session_id,
                )
                # Small delay between characters
                await asyncio.sleep(0.01)

            # Return coordinates metadata if available
            return input_coordinates

        except Exception as e:
            self.logger.error(f'Failed to input text via CDP: {type(e).__name__}: {e}')
            raise BrowserError(f'Failed to input text into element: {repr(element_node)}')