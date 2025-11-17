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
        f.write(screenshot1)
    with open("./tmp/screenshots/agent2_rust.png", "wb") as f:
        f.write(screenshot2)
    with open("./tmp/screenshots/agent3_github.png", "wb") as f:
        f.write(screenshot3)
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
    pdb.set_trace()
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
    active_tab1 = await manager.get_activate_tab()
    print(active_tab1)
    await agent2.active_focus_page()
    active_target_id = await manager._get_active_target()
    logging.info(f"After switching, Manager sees active target: {active_target_id}")
    active_tab2 = await manager.get_activate_tab()
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


async def test_website_api(main_browser_session: AgentBrowserSession):
    # from vibe_surf.tools.website_api.xhs.client import XiaoHongShuApiClient, SearchType
    # xhs_client = XiaoHongShuApiClient(browser_session=main_browser_session)
    # await xhs_client.setup()
    # user_info = await xhs_client.get_me()
    # user_id = user_info['user_id']
    # ret = await xhs_client.search_content_by_keyword("browser-use", sort_type=SearchType.POPULAR)
    # pdb.set_trace()
    # ret = await xhs_client.get_home_recommendations()
    # pdb.set_trace()
    # ret = await xhs_client.get_user_profile(user_id=user_id)
    # ret = await xhs_client.fetch_all_user_content(user_id=user_id)
    # note_id = ret[1]['note_id']
    # xsec_token = ret[1]['xsec_token']
    # ret1 = await xhs_client.fetch_content_details(content_id=note_id, xsec_token=xsec_token)
    # pdb.set_trace()
    # ret2 = await xhs_client.fetch_all_content_comments(content_id=note_id, xsec_token=xsec_token)
    # pdb.set_trace()

    from vibe_surf.tools.website_api.weibo.client import WeiboApiClient
    from vibe_surf.tools.website_api.weibo.helpers import SearchType
    wb_client = WeiboApiClient(browser_session=main_browser_session)
    await wb_client.setup()
    # ret = await wb_client.search_posts_by_keyword("邓紫棋", page=4, search_type=SearchType.POPULAR)
    # pdb.set_trace()
    # mid = ret[0]['note_id']
    # user_id = ret[0]['user_id']
    # ret = await wb_client.get_post_detail(mid=mid)
    # pdb.set_trace()
    # ret = await wb_client.get_all_post_comments(mid=mid)
    # pdb.set_trace()
    # ret1 = await wb_client.get_user_info(user_id=user_id)
    # ret3 = await wb_client.get_all_user_posts(user_id=user_id)
    # pdb.set_trace()
    ret = await wb_client.get_hot_posts()
    pdb.set_trace()
    ret = await wb_client.get_trending_posts()
    pdb.set_trace()

    # from vibe_surf.tools.website_api.douyin.client import DouyinApiClient
    #
    # dy_client = DouyinApiClient(main_browser_session)
    # await dy_client.setup()
    # ret = await dy_client.search_content_by_keyword("Sora2")
    # aweme_id = ret[0]['aweme_id']
    # user_id = ret[0]['user_id']
    # ret1 = await dy_client.fetch_video_details(aweme_id=aweme_id)
    # ret2 = await dy_client.fetch_video_comments(aweme_id=aweme_id)
    # ret3 = await dy_client.fetch_user_info(sec_user_id=user_id)
    # ret3 = await dy_client.fetch_user_videos(sec_user_id=user_id)
    # pdb.set_trace()

    # from vibe_surf.tools.website_api.youtube.client import YouTubeApiClient
    # yt_client = YouTubeApiClient(browser_session=main_browser_session)
    # await yt_client.setup()
    # ret = await yt_client.get_trending_videos()
    # pdb.set_trace()
    # ret = await yt_client.search_videos(query="何同学", max_results=30)
    # pdb.set_trace()
    # ret = await yt_client.get_video_details(ret[0]['video_id'])
    # pdb.set_trace()
    # ret = await yt_client.get_video_comments(ret[0]['video_id'])
    # pdb.set_trace()
    # ret = await yt_client.get_channel_info(ret[0]['channel_id'])
    # pdb.set_trace()
    # ret = await yt_client.get_channel_videos(ret[0]['channel_id'], max_videos=50)
    # pdb.set_trace()


async def test_page_element(browser_session: AgentBrowserSession):
    # await browser_session.navigate_to_url("https://github.com/", new_tab=True)
    # await asyncio.sleep(1)
    # page = await browser_session.get_current_page()
    # css_selector = r"#FormControl--\:Rjqhb\: > div > button"
    # element = await page.get_elements_by_css_selector(css_selector)
    # await page.get_element()
    # mouse = await page.mouse
    # await mouse.scroll(x=0, y=100, delta_x=0, delta_y=1000)
    # await page.press("Enter")
    #
    # if element:
    #     await element[0].click()
    #     await element[0].click(button='left', click_count=1, modifiers=['Control'])
    #     await element[0].fill("Hello World")

    from vibe_surf.browser.find_page_element import SemanticExtractor

    semantic_extractor = SemanticExtractor()
    await browser_session.navigate_to_url("https://www.google.com/search?q=langflow/", new_tab=True)
    await browser_session._wait_for_stable_network()

    page = await browser_session.get_current_page()

    element_mappings = await semantic_extractor.extract_semantic_mapping(page)
    element_info = semantic_extractor.find_element_by_hierarchy(element_mappings, target_text="新闻")
    element = await page.get_elements_by_css_selector(element_info["hierarchical_selector"] or element_info["selectors"])
    if element:
        await element[0].click()
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
            await test_browser_state_capture(manager)
            # await get_all_css_selector(main_browser_session)
            # await test_website_api(main_browser_session)
            # await test_page_element(browser_session=main_browser_session)

    except Exception as e:
        logging.error(f"An error occurred during tests: {e}", exc_info=True)

    finally:
        if main_browser_session:
            await main_browser_session.kill()
            logging.info("✅ Browser session killed.")


if __name__ == "__main__":
    asyncio.run(main())
