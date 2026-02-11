"""
Unified Website API Skills Handler
Supports: Xiaohongshu (XHS), Weibo, Zhihu, Douyin, YouTube
"""

import json
from datetime import datetime
from typing import Any, Dict
from json_repair import repair_json

from browser_use.agent.views import ActionResult
from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.tools.views import (
    SkillXhsAction,
    SkillWeiboAction,
    SkillZhihuAction,
    SkillDouyinAction,
    SkillYoutubeAction,
    GetApiParamsAction,
    CallApiAction,
)
from vibe_surf.logger import get_logger
from vibe_surf.tools.website_api.xhs.client import XiaoHongShuApiClient
from vibe_surf.tools.website_api.weibo.client import WeiboApiClient
from vibe_surf.tools.website_api.zhihu.client import ZhiHuClient
from vibe_surf.tools.website_api.douyin.client import DouyinApiClient
from vibe_surf.tools.website_api.youtube.client import YouTubeApiClient

logger = get_logger(__name__)


# Platform configuration - simplified
PLATFORMS = {
    "xiaohongshu": {
        "name": "Xiaohongshu",
        "model": SkillXhsAction,
        "client": XiaoHongShuApiClient,
    },
    "weibo": {
        "name": "Weibo",
        "model": SkillWeiboAction,
        "client": WeiboApiClient,
    },
    "zhihu": {
        "name": "Zhihu",
        "model": SkillZhihuAction,
        "client": ZhiHuClient,
    },
    "douyin": {
        "name": "Douyin",
        "model": SkillDouyinAction,
        "client": DouyinApiClient,
    },
    "youtube": {
        "name": "YouTube",
        "model": SkillYoutubeAction,
        "client": YouTubeApiClient,
    }
}


async def get_api_params(params: GetApiParamsAction) -> ActionResult:
    """
    Get API parameters for a specific platform
    
    Args:
        params: GetApiParamsAction with platform name
        
    Returns:
        ActionResult with platform's API model schema in JSON format
    """
    try:
        platform = params.platform.lower()
        
        if platform not in PLATFORMS:
            available = ", ".join(PLATFORMS.keys())
            return ActionResult(error=f"Unknown platform: {platform}. Available: {available}")
        
        config = PLATFORMS[platform]
        model = config["model"]
        
        # Get model JSON schema
        schema = model.model_json_schema()
        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)
        
        md_content = f"## {config['name']} API Parameters\n\n```json\n{schema_json}\n```\n"
        
        logger.info(f"Retrieved API parameters for {config['name']}")
        
        return ActionResult(
            extracted_content=md_content,
            include_extracted_content_only_once=True,
        )
        
    except Exception as e:
        error_msg = f"❌ Failed to get API parameters: {str(e)}"
        logger.error(error_msg)
        return ActionResult(error=error_msg)


async def call_api(
    params: CallApiAction,
    browser_manager: BrowserManager,
    file_system: CustomFileSystem
) -> ActionResult | None:
    """
    Call website platform API with unified handling
    
    Args:
        params: CallApiAction with platform, method, and params
        browser_manager: Browser manager instance
        file_system: File system instance
        
    Returns:
        ActionResult with API call results
    """
    client = None
    try:
        platform = params.platform.lower()
        
        if platform not in PLATFORMS:
            available = ", ".join(PLATFORMS.keys())
            return ActionResult(error=f"Unknown platform: {platform}. Available: {available}")
        
        config = PLATFORMS[platform]
        
        # Initialize client
        ClientClass = config["client"]
        client = ClientClass(browser_session=browser_manager.main_browser_session)
        await client.setup()
        
        # Parse params JSON string
        try:
            method_params = json.loads(params.params)
        except json.JSONDecodeError:
            method_params = json.loads(repair_json(params.params))
        
        # Execute the requested method
        if not hasattr(client, params.method):
            return ActionResult(error=f"Unknown method '{params.method}' for {config['name']}")
        
        method = getattr(client, params.method)
        result = await method(**method_params)

        # Check if result is None
        if result is None:
            if platform == "youtube" and params.method == "get_video_transcript":
                error_msg = "⚠️ 该视频没有可用字幕"
            else:
                error_msg = f"⚠️ {config['name']} 未返回数据（内容不存在或不可用）"
            logger.warning(error_msg)
            return ActionResult(error=error_msg, extracted_content=error_msg)

        # Save result to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{platform}_{params.method}_{timestamp}.json"
        filepath = file_system.get_dir() / "data" / filename
        filepath.parent.mkdir(exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # Format result as markdown
        if isinstance(result, list):
            display_count = min(5, len(result))
            md_content = f"## {config['name']} {params.method.replace('_', ' ').title()}\n\n"
            md_content += f"Showing {display_count} of {len(result)} results:\n\n"
            for i, item in enumerate(result[:display_count]):
                md_content += f"### Result {i + 1}\n"
                for key, value in item.items():
                    if not value:
                        continue
                    if isinstance(value, str) and len(value) > 200:
                        md_content += f"- **{key}**: {value[:200]}...\n"
                    else:
                        md_content += f"- **{key}**: {value}\n"
                md_content += "\n"
        elif isinstance(result, dict):
            md_content = f"## {config['name']} {params.method.replace('_', ' ').title()}\n\n"
            for key, value in result.items():
                if isinstance(value, str) and len(value) > 200:
                    md_content += f"- **{key}**: {value[:200]}...\n"
                else:
                    md_content += f"- **{key}**: {value}\n"
            md_content += "\n"
        else:
            # Handle other types (str, int, etc.)
            md_content = f"## {config['name']} {params.method.replace('_', ' ').title()}\n\n"
            md_content += f"{result}\n"
        
        # Add file path to markdown
        relative_path = str(filepath.relative_to(file_system.get_dir()))
        md_content += f"\n> 📁 Full data saved to: [{filename}]({relative_path})\n"
        md_content += f"> 💡 Click the link above to view all results.\n"
        
        logger.info(f"{config['name']} data retrieved with method: {params.method}")

        return ActionResult(extracted_content=md_content)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        error_msg = f"❌ Failed to retrieve {PLATFORMS.get(params.platform.lower(), {}).get('name', params.platform)} data: {str(e)}"

        logger.error(error_msg)
        return ActionResult(error=error_msg, extracted_content=error_msg)
        
    finally:
        if client:
            try:
                await client.close()
            except:
                pass