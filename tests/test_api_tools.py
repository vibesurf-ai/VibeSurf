import asyncio
import base64
import logging
import os
import sys
import pdb

sys.path.append(".")

# from dotenv import load_dotenv
#
# load_dotenv()

from browser_use.browser.events import NavigateToUrlEvent
from browser_use.browser.session import BrowserSession, BrowserProfile

from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.browser.agen_browser_profile import AgentBrowserProfile


async def test_xhs_api(browser_session):
    from vibe_surf.tools.website_api.xhs.client import XiaoHongShuApiClient

    client = XiaoHongShuApiClient(browser_session)

    try:
        await client.setup()
        # ret1 = await client.get_home_recommendations()
        # ret2 = await client.search_content_by_keyword("browser-use")
        # pdb.set_trace()
        ret3 = await client.get_user_profile("564e76f40bf90c7d349960be")
    except Exception as e:
        print(e)
        pdb.set_trace()


async def test_weibo_api(browser_session):
    from vibe_surf.tools.website_api.weibo.client import WeiboApiClient

    client = WeiboApiClient(browser_session)

    try:
        await client.setup()
        ret1 = await client.get_hot_posts()
        pdb.set_trace()
        ret2 = await client.get_trending_posts()
        pdb.set_trace()
    except Exception as e:
        print(e)
        pdb.set_trace()


async def test_douyin_api(browser_session):
    from vibe_surf.tools.website_api.douyin.client import DouyinApiClient

    client = DouyinApiClient(browser_session)

    try:
        await client.setup()
        pdb.set_trace()
        ret1 = await client.search_content_by_keyword("browser-use")
        pdb.set_trace()
    except Exception as e:
        print(e)
        pdb.set_trace()


async def test_youtube_api(browser_session):
    from vibe_surf.tools.website_api.youtube.client import YouTubeApiClient

    client = YouTubeApiClient(browser_session)

    try:
        await client.setup()
        ret1 = await client.search_videos("browser-use")
        ret2 = await client.get_trending_videos()
        ret3 = await client.get_video_transcript(video_id="LCEmiRjPEtQ")
        pdb.set_trace()
    except Exception as e:
        print(e)


async def test_yh_finance_api():
    from vibe_surf.tools.finance_tools import FinanceDataRetriever

    client = FinanceDataRetriever(symbol="TSLA")

    try:
        ret1 = client._get_balance_sheet()
        ret2 = client._get_calendar()
        ret3 = client._get_info()
        pdb.set_trace()
    except Exception as e:
        print(e)


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
            user_data_dir=os.path.abspath('./tmp/chrome/profiles/default2'),
            headless=False,
            highlight_elements=True
        )
        # Use SwarmBrowserSession instead of BrowserSession to disable DVD animation
        main_browser_session = AgentBrowserSession(browser_profile=browser_profile)
        await main_browser_session.start()
        async with BrowserManager(main_browser_session=main_browser_session) as manager:
            await test_xhs_api(browser_session=main_browser_session)
            # await test_weibo_api(browser_session=main_browser_session)
            # await test_douyin_api(browser_session=main_browser_session)
            # await test_youtube_api(browser_session=main_browser_session)
            # await test_yh_finance_api()
    except Exception as e:
        logging.error(f"An error occurred during tests: {e}", exc_info=True)

    finally:
        if main_browser_session:
            await main_browser_session.kill()
            logging.info("✅ Browser session killed.")


if __name__ == "__main__":
    asyncio.run(main())
