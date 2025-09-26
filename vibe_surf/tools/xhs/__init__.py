"""
XiaoHongShu (Little Red Book) Tools for VibeSurf

This module provides tools for interacting with XiaoHongShu platform including:
- Searching notes by keywords
- Getting home feed recommendations
- Retrieving note content and ALL comments
- Getting creator information and ALL notes
- Posting comments
- Downloading media files

All tools automatically handle cookie validation and will navigate to login page if needed.
"""

from .xhs_api import XiaoHongShuClient
from .xhs_tools import (
    XhsTools,
    XhsSearchAction,
    XhsNoteContentAction,
    XhsNoteAllCommentsAction,
    XhsPostCommentAction,
    XhsDownloadMediaAction,
    XhsCreatorInfoAction,
    XhsCreatorNotesAction,
)
from .utils import (
    get_search_id,
    convert_cookies,
    extract_note_id_token,
    SearchSortType,
    SearchNoteType,
    IPBlockError,
    DataFetchError,
)

__all__ = [
    'XiaoHongShuClient',
    'XhsTools',
    'XhsSearchAction',
    'XhsNoteContentAction',
    'XhsNoteAllCommentsAction',
    'XhsPostCommentAction',
    'XhsDownloadMediaAction',
    'XhsCreatorInfoAction',
    'XhsCreatorNotesAction',
    'get_search_id',
    'convert_cookies',
    'extract_note_id_token',
    'SearchSortType',
    'SearchNoteType',
    'IPBlockError',
    'DataFetchError',
]