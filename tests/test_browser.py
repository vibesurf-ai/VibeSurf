import asyncio
import base64
import logging
import os
import sys
import pdb

sys.path.append(".")

from dotenv import load_dotenv

load_dotenv()

from browser_use.browser.events import NavigateToUrlEvent
from browser_use.browser.session import BrowserSession, BrowserProfile

from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.browser.agen_browser_profile import AgentBrowserProfile


async def test_multi_agent_isolation(manager: BrowserManager):
    """Verify that two agents can operate on separate pages concurrently."""
    logging.info("--- Running Test: Multi-Agent Isolation ---")
    agent1 = await manager.register_agent("agent-iso-1")
    agent2 = await manager.register_agent("agent-iso-2")

    nav1 = agent1.event_bus.dispatch(
        NavigateToUrlEvent(url=f"https://www.google.com/search?q=browser-use")
    )
    nav2 = agent2.event_bus.dispatch(
        NavigateToUrlEvent(url=f"https://www.google.com/search?q=langflow")
    )
    await asyncio.gather(nav1, nav2)
    logging.info("✅ Agents navigated to different pages concurrently.")
    await asyncio.sleep(3)


async def test_agent_cleanup(manager: BrowserManager):
    """Verify that unregistering an agent closes all its pages."""
    logging.info("--- Running Test: Agent Cleanup ---")
    agent = await manager.register_agent("agent-cleanup")
    await manager.assign_target_to_agent("agent-cleanup")  # Assign a second page

    agent_tabs = await agent.get_tabs()
    print(agent_tabs)
    num_pages = len(agent_tabs)
    logging.info(f"Agent for cleanup has {num_pages} pages.")
    assert num_pages > 1

    logging.info("🧹 Unregistering agent...")
    await manager.unregister_agent("agent-cleanup", close_tabs=True)

    # Verify the agent and its pages are gone
    assert not manager.get_agent_sessions("agent-cleanup")
    logging.info("✅ Agent unregistered and all its pages were closed.")
    await asyncio.sleep(3)


async def test_agent_tab_isolation(manager: BrowserManager):
    """Verify that one agent closing its tab does not affect another agent."""
    logging.info("--- Running Test: Agent Tab Isolation ---")
    agent1 = await manager.register_agent("agent-tab-iso-1")
    agent2 = await manager.register_agent("agent-tab-iso-2")

    # Both agents have one page
    agent1_tabs = await agent1.get_tabs()
    agent2_tabs = await agent2.get_tabs()
    assert len(agent1_tabs) == 1
    assert len(agent2_tabs) == 1

    # Agent 1 closes its page
    logging.info("Agent 1 closing its page...")
    await manager.unregister_agent("agent-tab-iso-1", close_tabs=True)

    # Verify agent 1 is gone, but agent 2 remains
    assert not manager.get_agent_sessions("agent-tab-iso-1")
    agent2_tabs = await agent2.get_tabs()
    assert len(agent2_tabs) == 1
    logging.info("✅ Agent 1's tab closed, Agent 2's tab remains.")
    await asyncio.sleep(3)


async def test_browser_state_capture(manager: BrowserManager):
    """Verify two agents can concurrently capture their state and save screenshots."""
    logging.info("--- Running Test: Concurrent State Capture ---")

    agent1, agent2, agent3 = await asyncio.gather(
        manager.register_agent("agent-state-1"),
        manager.register_agent("agent-state-2"),
        manager.register_agent("agent-state-3")
    )

    # 添加并发诊断日志
    import time
    start_time = time.time()
    logging.info(f"🔍 DIAGNOSIS: Starting concurrent navigation at {start_time}")

    # 创建带时间戳的导航任务
    async def navigate_with_timing(agent, url, agent_name):
        task_start = time.time()
        logging.info(f"🔍 DIAGNOSIS: {agent_name} navigation started at {task_start - start_time:.3f}s")
        # 使用新的并发导航方法绕过串行瓶颈
        await agent.navigate_to_url(url)
        task_end = time.time()
        logging.info(
            f"🔍 DIAGNOSIS: {agent_name} navigation completed at {task_end - start_time:.3f}s (duration: {task_end - task_start:.3f}s)")
        return None

    # async def navigate_with_timing(agent, url, agent_name):
    #     task_start = time.time()
    #     logging.info(f"🔍 DIAGNOSIS: {agent_name} navigation started at {task_start - start_time:.3f}s")
    #     # 使用新的并发导航方法绕过串行瓶颈
    #     await agent.event_bus.dispatch(NavigateToUrlEvent(url=url, new_tab=False))
    #     task_end = time.time()
    #     logging.info(
    #         f"🔍 DIAGNOSIS: {agent_name} navigation completed at {task_end - start_time:.3f}s (duration: {task_end - task_start:.3f}s)")
    #     return None

    # Navigate to different pages
    await asyncio.gather(
        navigate_with_timing(agent1, "https://www.python.org", "agent1"),
        navigate_with_timing(agent2, "https://www.rust-lang.org", "agent2"),
        navigate_with_timing(agent3, "https://www.github.com", "agent3"),
    )

    end_time = time.time()
    total_duration = end_time - start_time
    logging.info(f"🔍 DIAGNOSIS: All navigation completed in {total_duration:.3f}s")

    # 创建带时间戳的导航任务
    async def take_screenshot_with_timing(agent: AgentBrowserSession, agent_name):
        task_start = time.time()
        logging.info(f"🔍 DIAGNOSIS: {agent_name} taking screenshot started at {task_start - start_time:.3f}s")
        # 使用新的并发导航方法绕过串行瓶颈
        image = await agent.take_screenshot()
        task_end = time.time()
        logging.info(
            f"🔍 DIAGNOSIS: {agent_name} taking screenshot completed at {task_end - start_time:.3f}s (duration: {task_end - task_start:.3f}s)")
        return image

    # Navigate to different pages
    screenshot1, screenshot2, screenshot3 = await asyncio.gather(
        take_screenshot_with_timing(agent1, "agent1"),
        take_screenshot_with_timing(agent2, "agent2"),
        take_screenshot_with_timing(agent3, "agent3"),
    )
    os.makedirs("./tmp/screenshots", exist_ok=True)
    with open("./tmp/screenshots/agent1_python.png", "wb") as f:
        f.write(base64.b64decode(screenshot1))
    with open("./tmp/screenshots/agent2_rust.png", "wb") as f:
        f.write(base64.b64decode(screenshot2))
    with open("./tmp/screenshots/agent3_github.png", "wb") as f:
        f.write(base64.b64decode(screenshot3))
    end_time = time.time()
    total_duration = end_time - start_time
    logging.info(f"🔍 DIAGNOSIS: All taking screenshot completed in {total_duration:.3f}s")
    # Concurrently get browser state
    start_time = time.time()

    async def get_state_with_timing(agent, agent_name):
        task_start = time.time()
        logging.info(f"🔍 DIAGNOSIS: {agent_name} get state started at {task_start - start_time:.3f}s")
        # 使用新的并发导航方法绕过串行瓶颈
        state = await agent.get_browser_state_summary()
        # state = await agent.get_browser_state()
        task_end = time.time()
        logging.info(
            f"🔍 DIAGNOSIS: {agent_name} get state completed at {task_end - start_time:.3f}s (duration: {task_end - task_start:.3f}s)")
        return state

    # async def get_state_with_timing(agent, agent_name):
    #     task_start = time.time()
    #     logging.info(f"🔍 DIAGNOSIS: {agent_name} get state started at {task_start - start_time:.3f}s")
    #     # 使用新的并发导航方法绕过串行瓶颈
    #     # state = await agent.get_browser_state_summary()
    #     state = await agent.get_browser_state_summary()
    #     task_end = time.time()
    #     logging.info(
    #         f"🔍 DIAGNOSIS: {agent_name} get state completed at {task_end - start_time:.3f}s (duration: {task_end - task_start:.3f}s)")
    #     return state

    logging.info("Capturing browser states concurrently...")
    state1, state2, state3 = await asyncio.gather(
        get_state_with_timing(agent1, "agent1"),
        get_state_with_timing(agent2, "agent2"),
        get_state_with_timing(agent3, "agent3"),
    )
    end_time = time.time()
    total_duration = end_time - start_time
    logging.info(f"🔍 DIAGNOSIS: All Get state completed in {total_duration:.3f}s")
    print(state1.tabs)
    print(state2.tabs)
    print(state3.tabs)

    # Ensure screenshots are present
    assert state1.screenshot, "Agent 1 failed to capture screenshot."
    assert state2.screenshot, "Agent 2 failed to capture screenshot."
    logging.info("✅ Both agents captured screenshots.")

    # Save screenshots
    os.makedirs("./tmp/screenshots", exist_ok=True)
    with open("./tmp/screenshots/agent1_python_highlight.png", "wb") as f:
        f.write(base64.b64decode(state1.screenshot))
    with open("./tmp/screenshots/agent2_rust_highlight.png", "wb") as f:
        f.write(base64.b64decode(state2.screenshot))
    with open("./tmp/screenshots/agent3_github_highlight.png", "wb") as f:
        f.write(base64.b64decode(state3.screenshot))
    logging.info("✅ Screenshots saved to ./tmp/screenshots/")

    # Agent 1 creates a new page and navigates
    logging.info("Agent 1 creating a new page and navigating to GitHub...")
    new_page_target_id = await agent1.navigate_to_url(url="https://www.realestate.com.au/", new_tab=True)

    # Get new state for agent 1
    logging.info("Capturing new state for agent 1...")
    state1_new = await agent1.get_browser_state_summary()

    # Print new tabs and save screenshot
    logging.info(f"Agent 1 new tabs: {state1_new.tabs}")
    assert state1_new.screenshot, "Agent 1 failed to capture new screenshot."
    with open("./tmp/screenshots/agent1_new_realestate.png", "wb") as f:
        f.write(base64.b64decode(state1_new.screenshot))
    logging.info("✅ Agent 1's new screenshot saved.")

    # Use manager to get active page info
    logging.info("Verifying active page with manager...")
    active_target_id = await manager._get_active_target()
    logging.info(f"Manager sees active target: {active_target_id}")
    active_tab1 = await manager._get_activate_tab_info()
    print(active_tab1)
    await agent2.active_focus_page()
    active_target_id = await manager._get_active_target()
    logging.info(f"After switching, Manager sees active target: {active_target_id}")
    active_tab2 = await manager._get_activate_tab_info()
    print(active_tab2)
    await manager.unregister_agent("agent-state-1", close_tabs=True)
    main_tabs = await manager.main_browser_session.get_tabs()
    print(main_tabs)


async def get_all_css_selector(browser_session: AgentBrowserSession):
    target_id = await browser_session.navigate_to_url("https://github.com/", new_tab=True)
    result = await browser_session.cdp_client.send.Target.attachToTarget({'targetId': target_id, 'flatten': True})
    session_id = result['sessionId']
    doc_result = await browser_session.cdp_client.send.DOM.getDocument(session_id=session_id)
    document_node_id = doc_result['root']['nodeId']
    from browser_use.dom.service import DomService
    dom_service = DomService(browser_session)
    pdb.set_trace()
    # Query selector all
    query_params = {'nodeId': document_node_id}
    result = await browser_session.cdp_client.send.DOM.querySelectorAll(query_params, session_id=session_id)

    elements = []

    # Convert node IDs to backend node IDs
    for node_id in result['nodeIds']:
        # Get backend node ID
        describe_params = {'nodeId': node_id}
        node_result = await browser_session.cdp_client.send.DOM.describeNode(describe_params, session_id=session_id)
        pdb.set_trace()


async def main():
    """
    Main function to run all browser session tests.
    """
    main_browser_session = None
    try:
        logging.info("🚀 Launching browser...")
        import platform
        if platform.system() != "Darwin":
            browser_exec_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        else:
            browser_exec_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        from pathlib import Path
        current_file = Path(__file__)
        project_root = current_file.parent.parent  # vibe_surf/browser -> vibe_surf -> project_root
        chrome_extension_path = project_root / "vibe_surf" / "chrome_extension"
        assert os.path.exists(chrome_extension_path)

        browser_profile = AgentBrowserProfile(
            executable_path=browser_exec_path,
            user_data_dir=os.path.abspath('./tmp/chrome/profiles/default'),
            headless=False,
            highlight_elements=True,
            custom_extensions=[str(chrome_extension_path.absolute())]
        )
        # Use SwarmBrowserSession instead of BrowserSession to disable DVD animation
        main_browser_session = AgentBrowserSession(browser_profile=browser_profile)
        await main_browser_session.start()
        async with BrowserManager(main_browser_session=main_browser_session) as manager:
            # await test_multi_agent_isolation(manager)
            # await test_manual_page_assignment(manager)
            # await test_agent_cleanup(manager)
            # await test_agent_tab_isolation(manager)
            # await test_browser_state_capture(manager)
            await get_all_css_selector(main_browser_session)

    except Exception as e:
        logging.error(f"An error occurred during tests: {e}", exc_info=True)

    finally:
        if main_browser_session:
            await main_browser_session.kill()
            logging.info("✅ Browser session killed.")


if __name__ == "__main__":
    asyncio.run(main())
