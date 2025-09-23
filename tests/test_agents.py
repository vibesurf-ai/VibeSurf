import os
import asyncio
import pprint

from dotenv import load_dotenv
import sys
import pdb

sys.path.append(".")
load_dotenv()

from browser_use.browser.session import BrowserSession, BrowserProfile
from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.browser.agent_browser_session import AgentBrowserSession

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.browser.agen_browser_profile import AgentBrowserProfile
from vibe_surf.tools.browser_use_tools import BrowserUseTools
from vibe_surf.tools.vibesurf_tools import VibeSurfTools
from vibe_surf.llm.openai_compatible import ChatOpenAICompatible
from browser_use.llm.deepseek.chat import ChatDeepSeek
from vibe_surf.agents.browser_use_agent import BrowserUseAgent
from vibe_surf.agents.vibe_surf_agent import VibeSurfAgent


async def run_single_bu_agent():
    import platform
    if platform.system() != "Darwin":
        browser_exec_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    else:
        browser_exec_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    browser_profile = AgentBrowserProfile(
        executable_path=browser_exec_path,
        user_data_dir=os.path.abspath('./tmp/chrome/profiles/default'),
        headless=False,
        keep_alive=True
    )
    # Use SwarmBrowserSession instead of BrowserSession to disable DVD animation
    main_browser_session = AgentBrowserSession(browser_profile=browser_profile)
    await main_browser_session.start()
    bu_tools = BrowserUseTools()

    # llm = ChatOpenAICompatible(model='gemini-2.5-flash',
    #                            base_url=os.getenv("OPENAI_ENDPOINT"),
    #                            api_key=os.getenv("OPENAI_API_KEY"))

    # llm = ChatOpenAICompatible(model='qwen-plus',
    #                            base_url=os.getenv("ALIBABA_ENDPOINT"),
    #                            api_key=os.getenv("ALIBABA_API_KEY"))

    # llm = ChatOpenAICompatible(model='kimi-k2-turbo-preview',
    #                            base_url=os.getenv("MOONSHOT_ENDPOINT"),
    #                            api_key=os.getenv("MOONSHOT_API_KEY"))

    llm = ChatOpenAICompatible(model='deepseek-reasoner',
                               base_url=os.getenv("DEEPSEEK_ENDPOINT"),
                               api_key=os.getenv("DEEPSEEK_API_KEY"))

    task = "Search Google for 'Elon Mask' and tell me the top 3 results"

    # task = r"""
    # 1. 在新的tab 导航到 https://github.com/
    # 2. 在新的tab 导航到 https://vibemotion.co/
    # 3. 在新的tab 导航到 https://browser-use.com/
    # 4. 分别总结所有tab的内容(在一步中使用parallel的extract操作, 不要分开三步)，然后保存到 tabs_summary.txt
    # """
    agent = BrowserUseAgent(task=task,
                            llm=llm,
                            browser_session=main_browser_session,
                            tools=bu_tools,
                            task_id=main_browser_session.id,
                            file_system_path="./tmp/single_bu_tests")
    history = await agent.run()
    print(history.final_result())
    await main_browser_session.kill()


async def run_multi_bu_agents():
    import platform
    if platform.system() != "Darwin":
        browser_exec_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    else:
        browser_exec_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    browser_profile = AgentBrowserProfile(
        executable_path=browser_exec_path,
        user_data_dir=os.path.abspath('./tmp/chrome/profiles/default'),
        headless=False,
        keep_alive=True
    )
    mcp_server_config = {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "E:\\AIBrowser\\VibeSurf\\tmp\\code",
                ]
            },
        }
    }
    # Use SwarmBrowserSession instead of BrowserSession to disable DVD animation
    # Use SwarmBrowserSession instead of BrowserSession to disable DVD animation
    main_browser_session = AgentBrowserSession(browser_profile=browser_profile)
    await main_browser_session.start()
    bu_tools = BrowserUseTools()
    browser_manager = BrowserManager(main_browser_session=main_browser_session)
    # await tools.register_mcp_clients(mcp_server_config)

    llm = ChatOpenAICompatible(model='gemini-2.5-flash',
                               base_url=os.getenv("OPENAI_ENDPOINT"),
                               api_key=os.getenv("OPENAI_API_KEY"))
    agent_browser_sessions = await asyncio.gather(
        browser_manager.register_agent("agent-1"),
        browser_manager.register_agent("agent-2"),
        browser_manager.register_agent("agent-3")
    )
    agents = [
        BrowserUseAgent(task=task,
                        llm=llm,
                        browser_session=agent_browser_sessions[i],
                        tools=bu_tools,
                        file_system_path="./tmp/multi_bu_tests")
        for i, task in enumerate([
            # 'Search Google for weather in Tokyo',
            # 'Check Reddit front page title',
            # 'Look up Bitcoin price on Coinbase',
            # 'Find NASA image of the day',
            # 'Check top story on CNN',
            # 'Search latest SpaceX launch date',
            # 'Look up population of Paris',
            # 'Find current time in Sydney',
            # 'Check who won last Super Bowl',
            # 'Search trending topics on Twitter',
            'search browser-use and click into the most relevant url and scroll down one page',
            'search langflow and click into the most relevant url and scroll down one page',
            'search langgraph and click into the most relevant url and scroll down one page',
        ])
    ]

    results = await asyncio.gather(*[agent.run() for agent in agents])
    for i, ret in enumerate(results):
        print(await agent_browser_sessions[i].get_tabs())
        print(ret.final_result())
    await browser_manager.close()
    await main_browser_session.kill()
    await bu_tools.unregister_mcp_clients()


async def test_vibe_surf_agent():
    """Test VibeSurfAgent with both simple and browser tasks"""
    import platform
    if platform.system() != "Darwin":
        browser_exec_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    else:
        browser_exec_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    browser_profile = AgentBrowserProfile(
        executable_path=browser_exec_path,
        user_data_dir=os.path.abspath('./tmp/chrome/profiles/default'),
        headless=False,
        keep_alive=True
    )
    # Use SwarmBrowserSession instead of BrowserSession to disable DVD animation
    main_browser_session = AgentBrowserSession(browser_profile=browser_profile)
    await main_browser_session.start()
    vs_tools = VibeSurfTools()
    browser_manager = BrowserManager(main_browser_session=main_browser_session)
    # llm = ChatOpenAICompatible(model='gemini-2.5-flash',
    #                            base_url=os.getenv("OPENAI_ENDPOINT"),
    #                            api_key=os.getenv("OPENAI_API_KEY"))

    llm = ChatOpenAICompatible(model='deepseek-chat',
                               base_url=os.getenv("DEEPSEEK_ENDPOINT"),
                               api_key=os.getenv("DEEPSEEK_API_KEY"))

    # Create VibeSurfAgent
    agent = VibeSurfAgent(
        llm=llm,
        browser_manager=browser_manager,
        tools=vs_tools,
        workspace_dir=os.path.abspath("./tmp/vibesurf_tests")
    )

    try:
        # Test 1: Simple task (should not require browser)
        print("🧪 Testing simple task...")
        simple_task = "What is 2 + 2? Explain the basic concept."
        result1 = await agent.run(simple_task)
        print(f"✅ Simple task result: {result1}...")
        assert result1 is not None and len(result1) > 0
        #
        # # Test 2: Simple task with upload files
        # print("🧪 Testing simple task with upload files...")
        # upload_files = [r"E:\AIBrowser\VibeSurf\tmp\code\test.py"]
        # simple_task_with_files = "What files were uploaded? Summarize their purpose."
        # result2 = await agent.run(simple_task_with_files, upload_files=upload_files)
        # print(f"✅ Simple task with files result: {result2}...")
        # assert result2 is not None and len(result2) > 0
        #
        # # Test 3: Browser task
        # print("🧪 Testing browser task...")
        # browser_task = "Search Google for 'LangGraph framework' and get basic information"
        # result3 = await agent.run(browser_task)
        # print(f"✅ Browser task result:")
        # pprint.pprint(result3)
        # assert result3 is not None and len(result3) > 0
        # pdb.set_trace()
        # print("🎉 All VibeSurfAgent tests passed!")

        # Test 4: Browser parallel task
        # print("🧪 Testing browser parallel tasks...")
        # browser_task = "Search for Dify, n8n, browser-use and click into their own homepage, take screenshot and save"
        # result4 = await agent.run(browser_task)
        # print(f"✅ Browser task result:")
        # pprint.pprint(result4)
        # with open("./tmp/vibesurf_tests/parallel_test.md", "w", encoding='utf-8') as fw:
        #     fw.write(result4)
        # assert result4 is not None and len(result4) > 0
        print("🎉 All VibeSurfAgent tests passed!")

    except Exception as e:
        print(f"❌ VibeSurfAgent test failed: {e}")
        raise e
    finally:
        # Cleanup
        await browser_manager.close()
        await main_browser_session.kill()


async def test_vibe_surf_agent_control():
    """Test VibeSurfAgent control functionality (pause/resume/stop)"""
    import platform
    if platform.system() != "Darwin":
        browser_exec_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    else:
        browser_exec_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    browser_profile = AgentBrowserProfile(
        executable_path=browser_exec_path,
        user_data_dir=os.path.abspath('./tmp/chrome/profiles/default'),
        headless=False,
        keep_alive=True
    )
    # Use SwarmBrowserSession instead of BrowserSession to disable DVD animation
    main_browser_session = AgentBrowserSession(browser_profile=browser_profile)
    await main_browser_session.start()
    vs_tools = VibeSurfTools()
    browser_manager = BrowserManager(main_browser_session=main_browser_session)
    llm = ChatOpenAICompatible(model='gemini-2.5-pro',
                               base_url=os.getenv("OPENAI_ENDPOINT"),
                               api_key=os.getenv("OPENAI_API_KEY"))

    # Create VibeSurfAgent
    agent = VibeSurfAgent(
        llm=llm,
        browser_manager=browser_manager,
        tools=vs_tools,
        workspace_dir=os.path.abspath("./tmp/vibesurf_tests"),
        calculate_token_cost=True
    )

    try:
        print("🧪 Testing VibeSurfAgent control functionality...")

        # Test 1: Status check when idle
        print("📊 Testing initial status...")
        status = agent.get_status()
        print(f"Initial status: {status.overall_status}")
        assert status.overall_status == "idle"

        # Test 2: Start a long-running browser task
        print("🚀 Starting long-running browser task...")
        browser_task = "Search for Dify, n8n, langflow and gather relative information, and generate a detailed report for comparison"

        # Start task in background
        async def run_task():
            return await agent.run(browser_task)

        task_coroutine = asyncio.create_task(run_task())

        # Wait a bit for task to start
        await asyncio.sleep(10)

        # Test 3: Check status during execution
        print("📊 Checking status during execution...")
        status = agent.get_status()
        print(f"Running status: {status.overall_status}")
        print(f"Progress: {status.progress}")
        print(f"Active agents: {len(status.agent_statuses)}")

        # Test 4: Pause execution
        print("⏸️ Testing pause functionality...")
        pause_result = await agent.pause("Testing pause functionality")
        print(f"Pause result: {pause_result.success} - {pause_result.message}")
        assert pause_result.success

        # Check status after pause
        await asyncio.sleep(1)
        status = agent.get_status()
        print(f"Paused status: {status.overall_status}")
        assert status.overall_status == "paused"

        # Test 5: Resume execution
        print("▶️ Testing resume functionality...")
        resume_result = await agent.resume("Testing resume functionality")
        print(f"Resume result: {resume_result.success} - {resume_result.message}")
        assert resume_result.success

        # Check status after resume
        await asyncio.sleep(1)
        status = agent.get_status()
        print(f"Resumed status: {status.overall_status}")

        # Let it run a bit more
        await asyncio.sleep(50)

        # Test 6: Stop execution
        print("🛑 Testing stop functionality...")
        stop_result = await agent.stop("Testing stop functionality")
        print(f"Stop result: {stop_result.success} - {stop_result.message}")

        # Check status after stop (should be stopped even if stop had issues)
        await asyncio.sleep(1)
        status = agent.get_status()
        print(f"Stopped status: {status.overall_status}")

        # Wait for task to complete (it should be cancelled)
        try:
            result = await asyncio.wait_for(task_coroutine, timeout=3)
            print(f"Task result after stop: {result[:100]}...")
        except asyncio.TimeoutError:
            print("✅ Task properly cancelled after stop (timeout)")
            task_coroutine.cancel()
            try:
                await task_coroutine
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            print("✅ Task was cancelled as expected")

        # Verify stop worked (may have timed out but should still be effective)
        if stop_result.success:
            assert status.overall_status == "idle"
        else:
            print(f"⚠️ Stop operation had issues but continuing: {stop_result.message}")

        # Test 7: Test simple task control (should work quickly)
        print("🔄 Testing control on simple task...")
        simple_task = "Find out who is the founder of Browser-Use."

        async def run_simple_task():
            return await agent.run(simple_task)

        simple_task_coroutine = asyncio.create_task(run_simple_task())

        # Pause quickly
        await asyncio.sleep(0.5)
        pause_result = await agent.pause("Testing simple task pause")
        print(f"Simple task pause: {pause_result.success}")

        # Resume
        await asyncio.sleep(0.5)
        resume_result = await agent.resume("Testing simple task resume")
        print(f"Simple task resume: {resume_result.success}")

        # Let it complete
        simple_result = await simple_task_coroutine
        print(f"Simple task completed: {len(simple_result) > 0}")
        print(simple_result)
        print("🎉 All VibeSurfAgent control tests passed!")

    except Exception as e:
        print(f"❌ VibeSurfAgent control test failed: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        # Cleanup
        try:
            await agent.stop("Cleanup")
        except:
            pass
        await browser_manager.close()
        await main_browser_session.kill()


if __name__ == "__main__":
    # asyncio.run(run_single_bu_agent())
    # asyncio.run(run_multi_bu_agents())
    asyncio.run(test_vibe_surf_agent())
    # asyncio.run(test_vibe_surf_agent_control())
