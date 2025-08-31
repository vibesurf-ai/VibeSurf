from __future__ import annotations

import asyncio
import logging
import pdb
import threading
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from browser_use.browser.session import CDPClient
from browser_use.browser.views import TabInfo
from cdp_use.cdp.target.types import TargetInfo
from bubus import EventBus

from vibe_surf.browser.agent_browser_session import AgentBrowserSession

if TYPE_CHECKING:
    from browser_use.browser.session import BrowserSession

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages isolated browser sessions for multiple agents with enhanced security."""

    def __init__(self, main_browser_session: BrowserSession):
        self.main_browser_session = main_browser_session

        # Store a list of sessions for each agent
        self._agent_sessions: Dict[str, AgentBrowserSession] = {}

    @property
    def _root_cdp_client(self) -> Optional[CDPClient]:
        """Get the root CDP client from the shared browser session."""
        return getattr(self.main_browser_session, '_cdp_client_root', None)

    async def _get_root_cdp_client(self) -> CDPClient:
        """Get the shared root CDP client from browser session."""
        if self._root_cdp_client is None:
            # Ensure the browser session is connected
            if not hasattr(self.main_browser_session,
                           '_cdp_client_root') or self.main_browser_session._cdp_client_root is None:
                await self.main_browser_session.connect()
        return self._root_cdp_client

    async def register_agent(
            self, agent_id: str, target_id: Optional[str] = None
    ) -> AgentBrowserSession:
        """
        Register an agent and return its primary isolated browser session.
        An agent can only be registered once.
        """
        if agent_id in self._agent_sessions:
            logger.info(f"Agent {agent_id} is already registered.")
            agent_session = self._agent_sessions[agent_id]
        else:
            agent_session = AgentBrowserSession(
                id=agent_id,
                cdp_url=self.main_browser_session.cdp_url,
                browser_profile=self.main_browser_session.browser_profile,
                main_browser_session=self.main_browser_session,
            )
            agent_session._cdp_client_root = await self._get_root_cdp_client()
            logger.info(f"🚀 Starting agent session for {agent_id} to initialize watchdogs...")
            await agent_session.start()
            
            self._agent_sessions[agent_id] = agent_session
        await self.assign_target_to_agent(agent_id, target_id)
        return agent_session

    async def assign_target_to_agent(
            self, agent_id: str, target_id: Optional[str] = None
    ) -> bool:
        """Assign a target to an agent, creating a new session for it with security validation."""
        # Validate agent exists
        if agent_id not in self._agent_sessions:
            logger.warning(f"Agent '{agent_id}' is not registered.")
            return False

        agent_session = self._agent_sessions[agent_id]

        # Validate target assignment
        if target_id:
            target_id_owner = self.get_target_owner(target_id)
            if target_id_owner and target_id_owner != agent_id:
                logger.warning(
                    f"Target id: {target_id} belongs to {target_id_owner}. You cannot assign it to {target_id_owner}.")
                return False

        # Get or create available target
        if target_id is None:
            new_target = await self.main_browser_session.cdp_client.send.Target.createTarget(
                params={'url': 'about:blank'})
            target_id = new_target["targetId"]

        await agent_session.connect_agent(target_id=target_id)
        return True

    async def unassign_target(self, target_id: str) -> bool:
        """Assign a target to an agent, creating a new session for it with security validation."""
        if not target_id:
            logger.warning(f"Please provide valid target id: {target_id}")
            return False
        target_id_owner = self.get_target_owner(target_id)
        if target_id_owner is None:
            logger.warning(f"Target id: {target_id} does not belong to any agent.")
            return False
        agent_session = self._agent_sessions[target_id_owner]
        target_cdp_session = agent_session.get_cdp_session_pool().pop(target_id, None)
        if target_cdp_session is not None:
            target_cdp_session.disconnect()
        return True

    async def unregister_agent(self, agent_id: str, close_tabs: bool = False):
        """Clean up all resources for an agent with enhanced security cleanup."""
        if agent_id not in self._agent_sessions:
            logger.warning(f"Agent '{agent_id}' is not registered.")
            return

        agent_session = self._agent_sessions.pop(agent_id, None)
        root_client = self.main_browser_session.cdp_client
        if close_tabs:
            for target_id in agent_session.get_cdp_session_pool():
                try:
                    logger.info(f"Close target id: {target_id}")
                    await root_client.send.Target.closeTarget(params={'targetId': target_id})
                except Exception as e:
                    # Log error if closing tab fails, but continue cleanup
                    logger.warning(f"Error closing target {target_id}: {e}")

        # Disconnect the agent's CDP session regardless
        await agent_session.disconnect_agent()
        await agent_session.stop()

    def get_agent_sessions(self, agent_id: str) -> Optional[AgentBrowserSession]:
        """Get all sessions (pages) for an agent."""
        return self._agent_sessions.get(agent_id, None)

    def get_active_agents(self) -> List[str]:
        """List all active agent IDs."""
        return list(self._agent_sessions.keys())

    def get_agent_target_ids(self, agent_id: str) -> List[str]:
        """Get all target IDs assigned to a specific agent."""
        agent_session = self.get_agent_sessions(agent_id)
        if agent_session is None:
            return []
        else:
            return list(agent_session.get_cdp_session_pool().keys())

    def get_target_owner(self, target_id: str) -> Optional[str]:
        """Get the agent ID that owns a specific target."""
        for agent_id in self._agent_sessions:
            agent_target_ids = self.get_agent_target_ids(agent_id)
            if target_id in agent_target_ids:
                return agent_id
        return None

    async def close(self) -> None:
        """Close all agent sessions but preserve the shared browser session."""
        # Unregister all agents first
        agent_ids = list(self._agent_sessions.keys())
        for agent_id in agent_ids:
            try:
                await self.unregister_agent(agent_id, True)
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Error during agent {agent_id} cleanup: {e}")

        # Note: We don't close the root browser session here as it's managed externally

    async def __aenter__(self) -> "BrowserManager":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _is_target_focused(self, target_id: str) -> bool:
        """Check if a given target has focus using multiple detection methods."""
        client = self.main_browser_session.cdp_client
        session_id = None

        try:
            # Use document.visibilityState and document.hasFocus()
            attach_result = await client.send.Target.attachToTarget(
                params={"targetId": target_id, "flatten": True}
            )
            session_id = attach_result["sessionId"]

            # Check both visibility and focus
            combined_script = """
            ({
                hasFocus: document.hasFocus(),
                visibilityState: document.visibilityState,
                hidden: document.hidden,
                activeElement: document.activeElement ? document.activeElement.tagName : null,
                timestamp: Date.now()
            })
            """

            eval_result = await client.send.Runtime.evaluate(
                params={
                    "expression": combined_script,
                    "returnByValue": True
                },
                session_id=session_id
            )

            # Detach immediately after checking
            await client.send.Target.detachFromTarget(
                params={"sessionId": session_id}
            )
            session_id = None

            if "result" in eval_result and "value" in eval_result["result"]:
                focus_data = eval_result["result"]["value"]
                has_focus = focus_data.get("hasFocus", False)
                visibility_state = focus_data.get("visibilityState", "")
                is_hidden = focus_data.get("hidden", True)

                # A target is considered focused if:
                # 1. Document has focus OR
                # 2. Document is visible (not hidden)
                is_focused = has_focus or (visibility_state == "visible" and not is_hidden)
                return is_focused
            else:
                return False

        except Exception:
            if session_id:
                try:
                    await client.send.Target.detachFromTarget(
                        params={"sessionId": session_id}
                    )
                except Exception:
                    pass  # Ignore cleanup errors
            return False

    async def _get_active_target(self) -> str:
        """Get current focused target, or an available target, or create a new one."""
        client = self.main_browser_session.cdp_client
        targets_info = await client.send.Target.getTargets()
        page_targets = [t for t in targets_info["targetInfos"] if t["type"] == "page"]

        # 1. Check for a focused page among ALL pages (not just unassigned)
        for target in page_targets:
            target_id = target["targetId"]
            try:
                is_focused = await self._is_target_focused(target_id)
                if is_focused:
                    return target_id
            except Exception as e:
                continue  # Skip invalid targets

        # 2. If no pages are available, create a new one
        if page_targets:
            target_id = page_targets[-1]["targetId"]
        else:
            new_target = await client.send.Target.createTarget(params={'url': 'about:blank'})
            target_id = new_target["targetId"]
        await self.main_browser_session.get_or_create_cdp_session(target_id, focus=False)
        return target_id

    async def _get_activate_tab_info(self) -> Optional[TabInfo]:
        """Get tab information for the currently active target."""
        try:
            # Get the active target ID
            active_target_id = await self._get_active_target()

            # Get target information from CDP
            client = self.main_browser_session.cdp_client
            targets_info = await client.send.Target.getTargets()

            # Find the active target in the targets list
            for target in targets_info["targetInfos"]:
                if target["targetId"] == active_target_id and target["type"] == "page":
                    # Get additional target info for title if needed
                    try:
                        target_info = await client.send.Target.getTargetInfo(
                            params={'targetId': active_target_id}
                        )
                        target_details = target_info.get('targetInfo', target)
                    except Exception:
                        target_details = target

                    # Create TabInfo object
                    return TabInfo(
                        url=target_details.get('url', ''),
                        title=target_details.get('title', ''),
                        target_id=active_target_id
                    )

            return None
        except Exception:
            return None
