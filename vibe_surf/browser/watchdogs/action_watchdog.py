import asyncio

from browser_use.browser.watchdogs.default_action_watchdog import DefaultActionWatchdog
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
                    message=msg,
                    long_term_memory=msg,
                )

            # Perform the actual click using internal implementation
            click_metadata = None
            click_metadata = await self._click_element_node_impl(element_node,
                                                                 while_holding_ctrl=event.while_holding_ctrl)
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
            await asyncio.sleep(0.5)

            # Clear cached state after click action since DOM might have changed
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