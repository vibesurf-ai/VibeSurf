import asyncio
import json
import os
import base64
import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from browser_use.agent.views import ActionResult
from browser_use.tools.service import Tools
from browser_use.filesystem.file_system import FileSystem
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import logging
import requests
from pathvalidate import sanitize_filename

from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.tools.xhs.xhs_api import XiaoHongShuClient
from vibe_surf.tools.xhs.utils import extract_note_id_token, SearchSortType, SearchNoteType
from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class XhsSearchAction(BaseModel):
    keywords: str
    limit: Optional[int] = 20


class XhsNoteContentAction(BaseModel):
    url: str


class XhsNoteAllCommentsAction(BaseModel):
    url: str
    max_count: Optional[int] = 1000


class XhsPostCommentAction(BaseModel):
    note_id: str
    comment: str


class XhsDownloadMediaAction(BaseModel):
    url: str
    save_path: Optional[str] = None


class XhsCreatorInfoAction(BaseModel):
    user_id: str


class XhsCreatorNotesAction(BaseModel):
    user_id: str
    max_count: Optional[int] = 1000


class XhsTools(Tools):
    def __init__(self):
        super().__init__()
        self.xhs_client = XiaoHongShuClient()
        self._register_xhs_actions()

    def _register_xhs_actions(self):
        """Register XiaoHongShu specific actions"""

        @self.registry.action(
            'Search XiaoHongShu notes by keywords',
            param_model=XhsSearchAction,
        )
        async def search_xhs_notes(params: XhsSearchAction, browser_session: AgentBrowserSession):
            """Search XiaoHongShu notes by keywords"""
            try:
                data = await self.xhs_client.get_note_by_keyword(
                    browser_session, params.keywords, page_size=params.limit
                )
                logger.info(f'Keywords: {params.keywords}, Data: {data}')
                
                result = "Search Results:\n\n"
                if 'items' in data and len(data['items']) > 0:
                    for i, item in enumerate(data['items']):
                        if 'note_card' in item and 'display_title' in item['note_card']:
                            title = item['note_card']['display_title']
                            liked_count = item['note_card']['interact_info']['liked_count']
                            url = f'https://www.xiaohongshu.com/explore/{item["id"]}?xsec_token={item["xsec_token"]}'
                            result += f"{i+1}. {title}\n   Likes: {liked_count}\n   URL: {url}\n\n"
                else:
                    # Check if login is still valid
                    if await self.xhs_client.pong(browser_session):
                        result = f"No notes found for '{params.keywords}'"
                    else:
                        result = "XHS cookies are invalid. Please login to xiaohongshu.com first."
                
                return ActionResult(
                    extracted_content=result,
                    include_in_memory=True,
                    long_term_memory=f"Searched XHS notes for '{params.keywords}'"
                )
            except Exception as e:
                error_msg = f"Failed to search XHS notes: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Get XiaoHongShu home feed recommendations',
        )
        async def get_xhs_home_feed(browser_session: AgentBrowserSession):
            """Get XiaoHongShu home feed recommendations"""
            try:
                data = await self.xhs_client.home_feed(browser_session)
                
                result = "Home Feed:\n\n"
                if 'items' in data and len(data['items']) > 0:
                    for i, item in enumerate(data['items']):
                        if 'note_card' in item and 'display_title' in item['note_card']:
                            title = item['note_card']['display_title']
                            liked_count = item['note_card']['interact_info']['liked_count']
                            url = f'https://www.xiaohongshu.com/explore/{item["id"]}?xsec_token={item["xsec_token"]}'
                            result += f"{i+1}. {title}\n   Likes: {liked_count}\n   URL: {url}\n\n"
                else:
                    # Check if login is still valid
                    if await self.xhs_client.pong(browser_session):
                        result = "No feed items found"
                    else:
                        result = "XHS cookies are invalid. Please login to xiaohongshu.com first."
                
                return ActionResult(
                    extracted_content=result,
                    include_in_memory=True,
                    long_term_memory="Retrieved XHS home feed"
                )
            except Exception as e:
                error_msg = f"Failed to get XHS home feed: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Get XiaoHongShu note content (URL must include xsec_token)',
            param_model=XhsNoteContentAction,
        )
        async def get_xhs_note_content(params: XhsNoteContentAction, browser_session: AgentBrowserSession):
            """Get XiaoHongShu note content"""
            try:
                note_params = extract_note_id_token(url=params.url)
                note_card = await self.xhs_client.get_note_by_id(
                    browser_session, 
                    note_params["note_id"], 
                    xsec_token=note_params["xsec_token"]
                )
                logger.info(f'URL: {params.url}, Data: {note_card}')
                
                if note_card and 'user' in note_card:
                    cover = ''
                    if 'image_list' in note_card and len(note_card['image_list']) > 0:
                        cover = note_card['image_list'][0].get('url_pre', '')

                    note_time = datetime.fromtimestamp(note_card.get('time', 0) / 1000)
                    liked_count = note_card['interact_info']['liked_count']
                    comment_count = note_card['interact_info']['comment_count']
                    collected_count = note_card['interact_info']['collected_count']

                    url = f'https://www.xiaohongshu.com/explore/{note_params["note_id"]}?xsec_token={note_params["xsec_token"]}'
                    result = f"Title: {note_card.get('title', '')}\n"
                    result += f"Author: {note_card['user'].get('nickname', '')}\n"
                    result += f"Published: {note_time}\n"
                    result += f"Likes: {liked_count}\n"
                    result += f"Comments: {comment_count}\n"
                    result += f"Collections: {collected_count}\n"
                    result += f"URL: {url}\n\n"
                    result += f"Content:\n{note_card.get('desc', '')}\n"
                    if cover:
                        result += f"Cover Image: {cover}"
                else:
                    result = "Failed to get note content"
                
                return ActionResult(
                    extracted_content=result,
                    include_in_memory=True,
                    long_term_memory=f"Retrieved XHS note content for {note_params['note_id']}"
                )
            except Exception as e:
                error_msg = f"Failed to get XHS note content: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Get ALL comments of XiaoHongShu note (URL must include xsec_token)',
            param_model=XhsNoteAllCommentsAction,
        )
        async def get_xhs_note_all_comments(params: XhsNoteAllCommentsAction, browser_session: AgentBrowserSession):
            """Get ALL comments of XiaoHongShu note"""
            try:
                note_params = extract_note_id_token(url=params.url)
                comments = await self.xhs_client.get_note_all_comments(
                    browser_session,
                    note_params["note_id"],
                    note_params["xsec_token"],
                    max_count=params.max_count
                )
                logger.info(f'URL: {params.url}, Comments count: {len(comments)}')

                result = f"All Comments (Total: {len(comments)}):\n\n"
                if comments:
                    for i, comment in enumerate(comments):
                        comment_time = datetime.fromtimestamp(comment['create_time'] / 1000)
                        result += f"{i+1}. {comment['user_info']['nickname']} ({comment_time}): {comment['content']}\n\n"
                else:
                    result = "No comments found"

                return ActionResult(
                    extracted_content=result,
                    include_in_memory=True,
                    long_term_memory=f"Retrieved {len(comments)} comments for XHS note {note_params['note_id']}"
                )
            except Exception as e:
                error_msg = f"Failed to get XHS note comments: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Post comment to XiaoHongShu note',
            param_model=XhsPostCommentAction,
        )
        async def post_xhs_comment(params: XhsPostCommentAction, browser_session: AgentBrowserSession):
            """Post comment to XiaoHongShu note"""
            try:
                response = await self.xhs_client.post_comment(browser_session, params.note_id, params.comment)
                
                if response.get('success'):
                    result = "Comment posted successfully"
                else:
                    result = "Failed to post comment"
                
                return ActionResult(
                    extracted_content=result,
                    include_in_memory=True,
                    long_term_memory=f"Posted comment to XHS note {params.note_id}"
                )
            except Exception as e:
                error_msg = f"Failed to post XHS comment: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Get XiaoHongShu creator information',
            param_model=XhsCreatorInfoAction,
        )
        async def get_xhs_creator_info(params: XhsCreatorInfoAction, browser_session: AgentBrowserSession):
            """Get XiaoHongShu creator information"""
            try:
                creator_info = await self.xhs_client.get_creator_info(browser_session, params.user_id)
                
                result = f"Creator Information for {params.user_id}:\n\n"
                for key, value in creator_info.items():
                    result += f"{key}: {value}\n"
                
                return ActionResult(
                    extracted_content=result,
                    include_in_memory=True,
                    long_term_memory=f"Retrieved creator info for {params.user_id}"
                )
            except Exception as e:
                error_msg = f"Failed to get XHS creator info: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Get ALL notes by XiaoHongShu creator',
            param_model=XhsCreatorNotesAction,
        )
        async def get_xhs_creator_all_notes(params: XhsCreatorNotesAction, browser_session: AgentBrowserSession):
            """Get ALL notes by XiaoHongShu creator"""
            try:
                notes = await self.xhs_client.get_all_notes_by_creator(
                    browser_session,
                    params.user_id,
                    max_count=params.max_count
                )
                
                result = f"All Notes by Creator {params.user_id} (Total: {len(notes)}):\n\n"
                if notes:
                    for i, note in enumerate(notes):
                        title = note.get('display_title', 'No title')
                        note_id = note.get('note_id', '')
                        liked_count = note.get('interact_info', {}).get('liked_count', 0)
                        note_time = datetime.fromtimestamp(note.get('time', 0) / 1000) if note.get('time') else 'Unknown'
                        
                        result += f"{i+1}. {title}\n"
                        result += f"   Note ID: {note_id}\n"
                        result += f"   Likes: {liked_count}\n"
                        result += f"   Published: {note_time}\n\n"
                else:
                    result = f"No notes found for creator {params.user_id}"
                
                return ActionResult(
                    extracted_content=result,
                    include_in_memory=True,
                    long_term_memory=f"Retrieved {len(notes)} notes for creator {params.user_id}"
                )
            except Exception as e:
                error_msg = f"Failed to get XHS creator notes: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Download XiaoHongShu media (images/videos) to downloads/xhs folder',
            param_model=XhsDownloadMediaAction,
        )
        async def download_xhs_media(params: XhsDownloadMediaAction, browser_session: AgentBrowserSession, file_system: FileSystem):
            """Download XiaoHongShu media files"""
            try:
                # Create downloads/xhs directory
                fs_dir = file_system.get_dir()
                xhs_dir = fs_dir / "downloads" / "xhs"
                xhs_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate timestamp for filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Download the media
                media_content = await self.xhs_client.get_note_media(params.url)
                if not media_content:
                    raise Exception("Failed to download media content")
                
                # Determine file extension from URL
                url_path = urlparse(params.url).path
                ext = os.path.splitext(url_path)[1] or '.jpg'
                
                # Create filename
                if params.save_path:
                    filename = sanitize_filename(params.save_path)
                    if not filename.endswith(ext):
                        filename += ext
                else:
                    filename = f"xhs_media_{timestamp}{ext}"
                
                filepath = xhs_dir / filename
                
                # Save the file
                with open(filepath, 'wb') as f:
                    f.write(media_content)
                
                relative_path = str(filepath.relative_to(fs_dir))
                result = f"Media downloaded successfully to: {relative_path}"
                
                return ActionResult(
                    extracted_content=result,
                    include_in_memory=True,
                    long_term_memory=f"Downloaded XHS media to {relative_path}",
                    attachments=[relative_path]
                )
            except Exception as e:
                error_msg = f"Failed to download XHS media: {str(e)}"
                logger.error(error_msg)
                return ActionResult(error=error_msg)