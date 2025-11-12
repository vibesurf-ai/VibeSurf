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
from browser_use.observability import observe_debug


class CustomActionWatchdog(DefaultActionWatchdog):
	@observe_debug(ignore_input=True, ignore_output=True, name='click_element_event')
	async def on_ClickElementEvent(self, event: ClickElementEvent) -> dict | None:
		"""Handle click request with CDP."""
		try:
			# Check if session is alive before attempting any operations
			if not self.browser_session.agent_focus or not self.browser_session.agent_focus.target_id:
				error_msg = 'Cannot execute click: browser session is corrupted (target_id=None). Session may have crashed.'
				self.logger.error(f'{error_msg}')
				raise BrowserError(error_msg)

			# Use the provided node
			element_node = event.node
			index_for_logging = element_node.backend_node_id or 'unknown'
			starting_target_id = self.browser_session.agent_focus.target_id

			# Track initial number of tabs to detect new tab opening
			if hasattr(self.browser_session, "main_browser_session") and self.browser_session.main_browser_session:
				initial_target_ids = await self.browser_session.main_browser_session._cdp_get_all_pages()
			else:
				initial_target_ids = await self.browser_session._cdp_get_all_pages()

			# Check if element is a file input (should not be clicked)
			if self.browser_session.is_file_input(element_node):
				msg = f'Index {index_for_logging} - has an element which opens file upload dialog. To upload files please use a specific function to upload files'
				self.logger.info(f'{msg}')
				# Return validation error instead of raising to avoid ERROR logs
				return {'validation_error': msg}

			# Detect print-related elements and handle them specially
			is_print_element = self._is_print_related_element(element_node)
			if is_print_element:
				self.logger.info(
					f'🖨️ Detected print button (index {index_for_logging}), generating PDF directly instead of opening dialog...'
				)

				# Instead of clicking, directly generate PDF via CDP
				click_metadata = await self._handle_print_button_click(element_node)

				if click_metadata and click_metadata.get('pdf_generated'):
					msg = f'Generated PDF: {click_metadata.get("path")}'
					self.logger.info(f'💾 {msg}')
					return click_metadata
				else:
					# Fallback to regular click if PDF generation failed
					self.logger.warning('⚠️ PDF generation failed, falling back to regular click')

			# Perform the actual click using internal implementation
			click_metadata = await self._click_element_node_impl(element_node)
			download_path = None  # moved to downloads_watchdog.py

			# Check for validation errors - return them without raising to avoid ERROR logs
			if isinstance(click_metadata, dict) and 'validation_error' in click_metadata:
				self.logger.info(f'{click_metadata["validation_error"]}')
				return click_metadata

			# Build success message
			if download_path:
				msg = f'Downloaded file to {download_path}'
				self.logger.info(f'💾 {msg}')
			else:
				msg = f'Clicked button {element_node.node_name}: {element_node.get_all_children_text(max_depth=2)}'
				self.logger.debug(f'🖱️ {msg}')
			self.logger.debug(f'Element xpath: {element_node.xpath}')

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
				from browser_use.browser.events import SwitchTabEvent

				await self.browser_session.get_or_create_cdp_session(
					target_id=new_target_id, focus=True
				)

			return click_metadata if isinstance(click_metadata, dict) else None
		except Exception as e:
			raise