import asyncio
from typing import Any, List
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, DropdownInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession


class BrowserSearchComponent(Component):
    display_name = "Search"
    description = "Search information in Browser"
    icon = "search"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Query to search for",
            required=True,
        ),
        DropdownInput(
            name="engine",
            display_name="Engine Type",
            options=["duckduckgo", "google", "bing"],
            value="google",
            advanced=True
        )
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="browser_search",
            types=["AgentBrowserSession"],
            required_inputs=['browser_session']
        )
    ]

    async def browser_search(self) -> AgentBrowserSession:
        """Close a specific session."""
        try:
            import urllib.parse
            from browser_use.browser.events import NavigateToUrlEvent

            # Encode query for URL safety
            encoded_query = urllib.parse.quote_plus(self.query)

            search_engines = {
                'duckduckgo': f'https://duckduckgo.com/?q={encoded_query}',
                'google': f'https://www.google.com/search?q={encoded_query}&udm=14',
                'bing': f'https://www.bing.com/search?q={encoded_query}',
            }

            if self.engine.lower() not in search_engines:
                self.status = f'Unsupported search engine: {self.engine.lower()}. Options: duckduckgo, google, bing'
                raise ValueError(self.status)

            search_url = search_engines[self.engine.lower()]

            # Simple tab logic: use current tab by default
            use_new_tab = False

            # Dispatch navigation event
            event = self.browser_session.event_bus.dispatch(
                NavigateToUrlEvent(
                    url=search_url,
                    new_tab=use_new_tab,
                )
            )
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)
            self.status = f"Searched {self.engine.title()} for {self.query}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
        finally:
            return self.browser_session
