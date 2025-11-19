from typing import Any, Generic, TypeVar
from browser_use.tools.registry.service import Registry
from pydantic import BaseModel
import pdb
import os
import asyncio
import json
import enum
import base64
import mimetypes
import yfinance as yf
import pprint
import pandas as pd
import numpy as np
import matplotlib

matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import io
import json
import re
import os
import openpyxl
from datetime import datetime, timedelta
from pathlib import Path
import csv

from json_repair import repair_json
from datetime import datetime
from typing import Optional, Type, Callable, Dict, Any, Union, Awaitable, TypeVar
from pathvalidate import sanitize_filename
from pydantic import BaseModel
from browser_use.tools.service import Controller, Tools, handle_browser_error
import logging
from browser_use.agent.views import ActionModel, ActionResult
from browser_use.utils import time_execution_sync
from browser_use.filesystem.file_system import FileSystem
from browser_use.browser import BrowserSession
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage, ContentPartTextParam, ContentPartImageParam, ImageURL, \
    AssistantMessage
from browser_use.dom.service import EnhancedDOMTreeNode
from browser_use.browser.views import BrowserError
from browser_use.mcp.client import MCPClient
from browser_use.tools.views import NoParamsAction
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.tools.views import HoverAction, ExtractionAction, FileExtractionAction, BrowserUseAgentExecution, \
    ReportWriterTask, TodoGenerateAction, TodoModifyAction, VibeSurfDoneAction, SkillSearchAction, SkillCrawlAction, \
    SkillSummaryAction, SkillTakeScreenshotAction, SkillDeepResearchAction, SkillCodeAction, SkillFinanceAction, \
    SkillXhsAction, SkillDouyinAction, SkillYoutubeAction, SkillWeiboAction, GrepContentAction, \
    SearchToolAction, GetToolInfoAction, ExecuteExtraToolAction, ExecutePythonCodeAction
from vibe_surf.tools.finance_tools import FinanceDataRetriever, FinanceMarkdownFormatter, FinanceMethod
from vibe_surf.tools.mcp_client import CustomMCPClient
from vibe_surf.tools.composio_client import ComposioClient
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.tools.vibesurf_registry import VibeSurfRegistry
from bs4 import BeautifulSoup
from vibe_surf.logger import get_logger
from vibe_surf.tools.utils import clean_html_basic
from vibe_surf.tools.utils import _extract_structured_content, _rank_search_results_with_llm, \
    extract_file_content_with_llm, remove_import_statements

logger = get_logger(__name__)

Context = TypeVar('Context')

T = TypeVar('T', bound=BaseModel)


class VibeSurfTools:
    def __init__(self, exclude_actions: list[str] = [], mcp_server_config: Optional[Dict[str, Any]] = None,
                 composio_client: ComposioClient = None):
        self.registry = VibeSurfRegistry(exclude_actions)
        self._register_file_actions()
        self._register_browser_use_agent()
        self._register_report_writer_agent()
        self._register_todo_actions()
        self._register_done_action()
        self._register_skills()
        self._register_extra_tools()
        self.mcp_server_config = mcp_server_config
        self.mcp_clients: Dict[str, MCPClient] = {}
        self.composio_toolkits: Dict[str, Any] = {}
        self.composio_client: ComposioClient = composio_client

    def get_all_action_names(self, exclude_actions: Optional[list] = None) -> list[str]:
        action_names = []
        for action_name in self.registry.registry.actions:
            add_flag = True
            for ex_action_name in exclude_actions:
                if action_name.startswith(ex_action_name) or ex_action_name in action_name:
                    add_flag = False
                    break
            if add_flag:
                action_names.append(action_name)
        return action_names

    def _register_skills(self):
        @self.registry.action(
            'Advanced search',
            param_model=SkillSearchAction,
        )
        async def skill_search(
                params: SkillSearchAction,
                browser_manager: BrowserManager,
                page_extraction_llm: BaseChatModel
        ):
            """
            Advanced search skill that uses Google AI model search as primary method,
            with fallback to parallel search across all/news/videos tabs.
            
            Primary Method: Google AI model search (udm=50) with "show more" button click
            Fallback Method: Parallel search across all, news, and videos tabs
            
            Args:
                params: SkillSearchAction containing query and rank parameters
                browser_manager: Browser manager for creating browser sessions
                page_extraction_llm: LLM for ranking results when rank=True
            
            Returns:
                ActionResult with formatted search results
            """
            from vibe_surf.tools.utils import google_ai_model_search, fallback_parallel_search

            agent_ids = []
            try:
                # Step 1: Try Google AI model search first (primary method)
                logger.info(f'🔍 Starting Google AI model search for: {params.query}')

                # Attempt Google AI model search with udm=50
                ai_search_results = await google_ai_model_search(browser_manager, params.query, max_results=15)

                # Step 2: If AI search fails or returns insufficient results, use fallback method
                if not ai_search_results or len(ai_search_results) == 0:
                    logger.info(f'🔄 Google AI search returned no results, using fallback parallel search')

                    # Use parallel search across all, news, and videos tabs
                    fallback_results = await fallback_parallel_search(browser_manager, params.query, max_results=15)
                    all_results = fallback_results
                else:
                    logger.info(f'✅ Google AI search found {len(ai_search_results)} results')
                    all_results = ai_search_results

                # Step 3: Process results based on rank parameter
                if params.rank and all_results and len(all_results) > 10:
                    logger.info(f'🔄 Using LLM ranking for {len(all_results)} results')

                    if not page_extraction_llm:
                        logger.warning("LLM not available for ranking, returning unranked results")
                        top_results = all_results[:15]
                    else:
                        # Use LLM ranking when rank=True and we have many results
                        top_results = await _rank_search_results_with_llm(
                            all_results, params.query, page_extraction_llm
                        )
                elif params.rank and all_results and len(all_results) <= 10:
                    logger.info(f'⭐ Skipping LLM ranking for {len(all_results)} results (≤10)')
                    top_results = all_results
                else:
                    # When rank=False, return results from different tabs (5 each from all, news, videos)
                    if hasattr(all_results, '__iter__') and all_results:
                        # Group results by source_tab if available, otherwise take first 15
                        tab_groups = {'all': [], 'news': [], 'videos': [], 'other': []}

                        for result in all_results:
                            source_tab = result.get('source_tab', 'other')
                            tab_groups[source_tab].append(result)

                        # Take up to 5 results from each tab
                        top_results = []
                        for tab_name in ['all', 'news', 'videos', 'other']:
                            top_results.extend(tab_groups[tab_name][:5])

                        # If we don't have enough results from tabs, take the first 15 overall
                        if len(top_results) < 15:
                            top_results = all_results[:15]
                    else:
                        top_results = all_results[:15] if all_results else []

                # Step 4: Format results for display
                if top_results:
                    results_text = f"🔍 Search Results for '{params.query}':\n\n"
                    for i, result in enumerate(top_results):
                        title = result.get('title', 'Unknown Title')
                        url = result.get('url', 'No URL')
                        summary = result.get('summary', 'No description available')

                        results_text += f"{i + 1}. **{title}**\n   URL: {url}\n   Summary: {summary}\n\n"
                else:
                    results_text = f"No results found for query: {params.query}"

                logger.info(f'🔍 Skill Search completed for: {params.query}, found {len(top_results)} results')
                return ActionResult(
                    extracted_content=results_text,
                    include_extracted_content_only_once=True,
                    long_term_memory=f'Search completed for: {params.query}, found {len(top_results)} relevant results using {"AI model search" if ai_search_results else "fallback search"}'
                )

            except Exception as e:
                logger.error(f'❌ Skill Search failed: {e}')
                return ActionResult(error=f'Skill search failed: {str(e)}')
            finally:
                # Clean up browser sessions
                for agent_id in agent_ids:
                    try:
                        await browser_manager.unregister_agent(agent_id, close_tabs=True)
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup agent {agent_id}: {cleanup_error}")

        @self.registry.action(
            '',
            param_model=SkillCrawlAction,
        )
        async def skill_crawl(
                params: SkillCrawlAction,
                browser_manager: BrowserManager,
                page_extraction_llm: BaseChatModel
        ):
            """
            Skill: Extract structured content from current or specified webpage
            """
            llm = page_extraction_llm
            try:
                if not llm:
                    raise RuntimeError("LLM is required for skill_crawl")

                # Get browser session
                browser_session = browser_manager.main_browser_session

                # If tab_id is provided, switch to that tab
                target_id = None
                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                    url = await browser_session.get_current_page_url()
                    current_target_id = None
                    current_url = None
                    if browser_session._dom_watchdog and browser_session._dom_watchdog.enhanced_dom_tree:
                        current_target_id = browser_session._dom_watchdog.enhanced_dom_tree.target_id
                    if browser_session._cached_browser_state_summary:
                        current_url = browser_session._cached_browser_state_summary.url
                    if current_target_id != target_id or url != current_url:
                        browser_session._dom_watchdog.clear_cache()
                        browser_session._cached_browser_state_summary = None
                    await browser_session.get_or_create_cdp_session(target_id, focus=True)

                # Extract structured content using the existing method
                extracted_content = await _extract_structured_content(
                    browser_session, params.query, llm, target_id=target_id
                )

                current_url = await browser_session.get_current_page_url()
                result_text = f'### URL:{current_url}\n\n{extracted_content}'

                # Handle memory storage
                MAX_MEMORY_LENGTH = 1000
                if len(result_text) < MAX_MEMORY_LENGTH:
                    memory = result_text
                    include_extracted_content_only_once = False
                else:
                    memory = f'Extracted structured content from {current_url} for query: {params.query}'
                    include_extracted_content_only_once = True

                logger.info(f'📄 Skill Crawl completed for: {current_url}')
                return ActionResult(
                    extracted_content=result_text,
                    include_extracted_content_only_once=include_extracted_content_only_once,
                    long_term_memory=memory,
                )

            except Exception as e:
                logger.error(f'❌ Skill Crawl failed: {e}')
                return ActionResult(error=f'Skill crawl failed: {str(e)}')

        @self.registry.action(
            '',
            param_model=SkillSummaryAction,
        )
        async def skill_summary(
                params: SkillSummaryAction,
                browser_manager: BrowserManager,
                page_extraction_llm: BaseChatModel
        ):
            """
            Skill: Summarize webpage content using LLM
            """
            llm = page_extraction_llm
            try:
                if not llm:
                    raise RuntimeError("LLM is required for skill_summary")

                # Get browser session
                browser_session = browser_manager.main_browser_session

                # If tab_id is provided, switch to that tab
                target_id = None
                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                    url = await browser_session.get_current_page_url()
                    current_target_id = None
                    current_url = None
                    if browser_session._dom_watchdog and browser_session._dom_watchdog.enhanced_dom_tree:
                        current_target_id = browser_session._dom_watchdog.enhanced_dom_tree.target_id
                    if browser_session._cached_browser_state_summary:
                        current_url = browser_session._cached_browser_state_summary.url
                    if current_target_id != target_id or url != current_url:
                        browser_session._dom_watchdog.clear_cache()
                        browser_session._cached_browser_state_summary = None
                    await browser_session.get_or_create_cdp_session(target_id, focus=True)

                # Extract and summarize content
                summary = await _extract_structured_content(
                    browser_session, "Provide a comprehensive summary of this webpage", llm, target_id=target_id
                )

                current_url = await browser_session.get_current_page_url()
                result_text = f'📝 Summary of {current_url}:\n\n{summary}'

                # Handle memory storage
                MAX_MEMORY_LENGTH = 1000
                if len(result_text) < MAX_MEMORY_LENGTH:
                    memory = result_text
                    include_extracted_content_only_once = False
                else:
                    memory = f'Summarized webpage: {current_url}'
                    include_extracted_content_only_once = True

                logger.info(f'📝 Skill Summary completed for: {current_url}')
                return ActionResult(
                    extracted_content=result_text,
                    include_extracted_content_only_once=include_extracted_content_only_once,
                    long_term_memory=memory,
                )

            except Exception as e:
                logger.error(f'❌ Skill Summary failed: {e}')
                return ActionResult(error=f'Skill summary failed: {str(e)}')

        @self.registry.action(
            '',
            param_model=SkillTakeScreenshotAction,
        )
        async def skill_screenshot(
                params: SkillTakeScreenshotAction,
                browser_manager: BrowserManager,
                file_system: CustomFileSystem
        ):
            """
            Skill: Take screenshot with optional tab selection
            """
            try:
                # Get browser session
                browser_session = browser_manager.main_browser_session

                # If tab_id is provided, switch to that tab
                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                    await browser_session.get_or_create_cdp_session(target_id, focus=True)

                # Take screenshot using browser session
                screenshot_bytes = await browser_session.take_screenshot()

                # Generate timestamp for filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # Get file system directory path (Path type)
                fs_dir = file_system.get_dir()

                # Create screenshots directory if it doesn't exist
                screenshots_dir = fs_dir / "screenshots"
                screenshots_dir.mkdir(exist_ok=True)

                # Save screenshot to file system
                page_title = await browser_session.get_current_page_title()
                from pathvalidate import sanitize_filename
                page_title = sanitize_filename(page_title)
                filename = f"{page_title}-{timestamp}.png"
                filepath = screenshots_dir / filename

                with open(filepath, "wb") as f:
                    f.write(screenshot_bytes)

                msg = f'📸 Screenshot saved to path: [{filename}]({str(filepath.relative_to(fs_dir))})'
                logger.info(msg)
                return ActionResult(
                    extracted_content=msg,
                    include_in_memory=True,
                    long_term_memory=f'Screenshot saved to {str(filepath.relative_to(fs_dir))}',
                )

            except Exception as e:
                error_msg = f'❌ Failed to take screenshot: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg)

        @self.registry.action(
            'Execute JavaScript code on webpage',
            param_model=SkillCodeAction,
        )
        async def skill_code(
                params: SkillCodeAction,
                browser_manager: BrowserManager,
                page_extraction_llm: BaseChatModel,
                file_system: CustomFileSystem
        ):
            """
            Skill: Generate and execute JavaScript code from functional requirements or code prompts with iterative retry logic
            """

            try:
                if not page_extraction_llm:
                    raise RuntimeError("LLM is required for skill_code")

                # Get browser session
                browser_session = browser_manager.main_browser_session

                # If tab_id is provided, switch to that tab
                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                    await browser_session.get_or_create_cdp_session(target_id, focus=True)

                from vibe_surf.tools.utils import generate_java_script_code

                success, execute_result, js_code = await generate_java_script_code(params.code_requirement,
                                                                                   page_extraction_llm, browser_session,
                                                                                   MAX_ITERATIONS=5)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                code_file = f"codes/{timestamp}.js"
                with open(code_file, "w") as f:
                    await file_system.write_file(code_file, execute_result)

                if len(execute_result) < 1000:
                    msg = f'JavaScript Code save at:{code_file}\nResult:\n```json\n {execute_result}\n```\n'
                else:
                    result_file = f"codes/{timestamp}.json"
                    await file_system.write_file(result_file, execute_result)
                    msg = f'JavaScript Code save at:{code_file}\nResult:\n```json\n {execute_result[:1000]}\n...TRUNCATED...\n```\nView more in {result_file}\n'
                if success:
                    return ActionResult(extracted_content=msg)
                else:
                    return ActionResult(error=msg)

            except Exception as e:
                logger.error(f'❌ Skill Code failed: {e}')
                return ActionResult(error=f'Skill code failed: {str(e)}')

        @self.registry.action(
            'Get comprehensive financial data for stocks - retrieve company information, historical prices, news, earnings, dividends, analyst recommendations and other financial data using Yahoo Finance.',
            param_model=SkillFinanceAction,
        )
        async def skill_finance(
                params: SkillFinanceAction,
        ):
            """
            Skill: Get comprehensive financial data using Yahoo Finance
            
            Available methods include:
            - get_info: Company information including sector, industry, market cap, business summary
            - get_history: Historical stock prices and volume data over time periods
            - get_news: Latest news articles about the company
            - get_dividends: Historical dividend payments and yield data
            - get_earnings: Quarterly and annual earnings data and growth trends
            - get_recommendations: Analyst recommendations, price targets, and ratings
            - get_balance_sheet: Company balance sheet data (assets, liabilities, equity)
            - get_income_stmt: Income statement data (revenue, expenses, profit)
            - get_cashflow: Cash flow statement data (operating, investing, financing)
            - get_fast_info: Quick statistics like current price, volume, market cap
            - get_institutional_holders: Institutional ownership and holdings data
            - get_major_holders: Major shareholders and insider ownership percentages
            - get_sustainability: ESG (Environmental, Social, Governance) scores and data
            - get_upgrades_downgrades: Recent analyst upgrades and downgrades
            - get_splits: Historical stock splits and stock split dates
            - get_actions: Corporate actions including dividends and splits
            - get_sec_filings: Recent SEC filings and regulatory documents
            - get_calendar: Upcoming earnings dates and events
            - get_mutualfund_holders: Mutual fund ownership data
            - get_insider_purchases: Recent insider buying activity
            - get_insider_transactions: All insider trading transactions
            - get_shares: Outstanding shares and float data
            """
            try:
                # Default to get_info if no methods specified
                methods = params.methods if params.methods else [FinanceMethod.GET_INFO]

                # Convert string methods to FinanceMethod enum if needed
                if methods and isinstance(methods[0], str):
                    try:
                        methods = [FinanceMethod(method) for method in methods]
                    except ValueError as e:
                        available_methods = [method.value for method in FinanceMethod]
                        return ActionResult(
                            error=f'Invalid method in {methods}. Available methods: {available_methods}'
                        )

                # Create data retriever with symbol
                retriever = FinanceDataRetriever(params.symbol)

                # Convert FinanceMethod enum values to strings for the retriever
                method_strings = [method.value for method in methods]

                # Retrieve financial data
                financial_data = retriever.get_finance_data(
                    methods=method_strings,
                    period=getattr(params, 'period', '1y'),
                    start_date=getattr(params, 'start_date', None),
                    end_date=getattr(params, 'end_date', None),
                    interval=getattr(params, 'interval', '1d'),
                    num_news=getattr(params, 'num_news', 5)
                )

                # Format as markdown using the static method
                markdown_content = FinanceMarkdownFormatter.format_finance_data(
                    symbol=params.symbol,
                    results=financial_data,
                    methods=method_strings
                )

                method_names = [method.value for method in methods]
                logger.info(f'💹 Comprehensive finance data retrieved for {params.symbol} with methods: {method_names}')

                return ActionResult(
                    extracted_content=markdown_content,
                    include_extracted_content_only_once=True,
                    long_term_memory=f'Retrieved comprehensive financial data for {params.symbol} using methods: {", ".join(method_names)}',
                )

            except Exception as e:
                error_msg = f'❌ Failed to retrieve financial data for {params.symbol}: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg, extracted_content=error_msg)

        @self.registry.action(
            '',
            param_model=SkillXhsAction,
        )
        async def skill_xhs(
                params: SkillXhsAction,
                browser_manager: BrowserManager,
                file_system: CustomFileSystem
        ):
            """
            Skill: Xiaohongshu API integration
            
            Available methods:
            - search_content_by_keyword: Search content by keyword with sorting options
            - fetch_content_details: Get detailed information about specific content
            - fetch_all_content_comments: Get all comments for specific content
            - get_user_profile: Get user profile information
            - fetch_all_user_content: Get all content posted by a user
            - get_home_recommendations: Get homepage recommended content
            """
            try:
                from vibe_surf.tools.website_api.xhs.client import XiaoHongShuApiClient

                # Initialize client
                xhs_client = XiaoHongShuApiClient(browser_session=browser_manager.main_browser_session)
                await xhs_client.setup()

                # Parse params JSON string
                import json
                from json_repair import repair_json
                try:
                    method_params = json.loads(params.params)
                except json.JSONDecodeError:
                    method_params = json.loads(repair_json(params.params))

                # Execute the requested method
                result = None
                if params.method == "search_content_by_keyword":
                    result = await xhs_client.search_content_by_keyword(**method_params)
                elif params.method == "fetch_content_details":
                    result = await xhs_client.fetch_content_details(**method_params)
                elif params.method == "fetch_all_content_comments":
                    result = await xhs_client.fetch_all_content_comments(**method_params)
                elif params.method == "get_user_profile":
                    result = await xhs_client.get_user_profile(**method_params)
                elif params.method == "fetch_all_user_content":
                    result = await xhs_client.fetch_all_user_content(**method_params)
                elif params.method == "get_home_recommendations":
                    result = await xhs_client.get_home_recommendations()
                else:
                    return ActionResult(error=f"Unknown method: {params.method}")

                # Save result to file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"xhs_{params.method}_{timestamp}.json"
                filepath = file_system.get_dir() / "data" / filename
                filepath.parent.mkdir(exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                # Format result as markdown
                if isinstance(result, list):
                    display_count = min(5, len(result))
                    md_content = f"## Xiaohongshu {params.method.replace('_', ' ').title()}\n\n"
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
                else:
                    md_content = f"## Xiaohongshu {params.method.replace('_', ' ').title()}\n\n"
                    for key, value in result.items():
                        if isinstance(value, str) and len(value) > 200:
                            md_content += f"- **{key}**: {value[:200]}...\n"
                        else:
                            md_content += f"- **{key}**: {value}\n"
                    md_content += "\n"

                # Add file path to markdown
                relative_path = str(filepath.relative_to(file_system.get_dir()))
                md_content += f"\n> 📁 Full data saved to: [{filename}]({relative_path})\n"
                md_content += f"> 💡 Click the link above to view all results.\n"

                logger.info(f'📕 Xiaohongshu data retrieved with method: {params.method}')

                # Close client
                await xhs_client.close()

                return ActionResult(
                    extracted_content=md_content
                )

            except Exception as e:
                error_msg = f'❌ Failed to retrieve Xiaohongshu data: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg, extracted_content=error_msg)

        @self.registry.action(
            '',
            param_model=SkillWeiboAction,
        )
        async def skill_weibo(
                params: SkillWeiboAction,
                browser_manager: BrowserManager,
                file_system: CustomFileSystem
        ):
            """
            Skill: Weibo API integration
            
            Available methods:
            - search_posts_by_keyword: Search posts by keyword with sorting options
            - get_post_detail: Get detailed information about specific post
            - get_all_post_comments: Get all comments for specific post
            - get_user_info: Get user profile information
            - get_all_user_posts: Get all posts by a user
            - get_hot_posts: Get hot posts
            - get_trending_list: Get trending list
            """
            try:
                from vibe_surf.tools.website_api.weibo.client import WeiboApiClient

                # Initialize client
                wb_client = WeiboApiClient(browser_session=browser_manager.main_browser_session)
                await wb_client.setup()

                # Parse params JSON string
                import json
                from json_repair import repair_json
                try:
                    method_params = json.loads(params.params)
                except json.JSONDecodeError:
                    method_params = json.loads(repair_json(params.params))

                # Execute the requested method
                result = None
                if params.method == "search_posts_by_keyword":
                    result = await wb_client.search_posts_by_keyword(**method_params)
                elif params.method == "get_post_detail":
                    result = await wb_client.get_post_detail(**method_params)
                elif params.method == "get_all_post_comments":
                    result = await wb_client.get_all_post_comments(**method_params)
                elif params.method == "get_user_info":
                    result = await wb_client.get_user_info(**method_params)
                elif params.method == "get_all_user_posts":
                    result = await wb_client.get_all_user_posts(**method_params)
                elif params.method == "get_hot_posts":
                    result = await wb_client.get_hot_posts()
                elif params.method == "get_trending_posts":
                    result = await wb_client.get_trending_posts()
                else:
                    return ActionResult(error=f"Unknown method: {params.method}")

                # Save result to file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"weibo_{params.method}_{timestamp}.json"
                filepath = file_system.get_dir() / "data" / filename
                filepath.parent.mkdir(exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                # Format result as markdown
                if isinstance(result, list):
                    display_count = min(5, len(result))
                    md_content = f"## Weibo {params.method.replace('_', ' ').title()}\n\n"
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
                else:
                    md_content = f"## Weibo {params.method.replace('_', ' ').title()}\n\n"
                    for key, value in result.items():
                        if isinstance(value, str) and len(value) > 200:
                            md_content += f"- **{key}**: {value[:200]}...\n"
                        else:
                            md_content += f"- **{key}**: {value}\n"
                    md_content += "\n"

                # Add file path to markdown
                relative_path = str(filepath.relative_to(file_system.get_dir()))
                md_content += f"\n> 📁 Full data saved to: [{filename}]({relative_path})\n"
                md_content += f"> 💡 Click the link above to view all results.\n"

                logger.info(f'🐦 Weibo data retrieved with method: {params.method}')

                # Close client
                await wb_client.close()

                return ActionResult(
                    extracted_content=md_content
                )

            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = f'❌ Failed to retrieve Weibo data: {str(e)}. \nMost likely you are not login, please go to: [Weibo login page](https://passport.weibo.com/sso/signin?entry=miniblog&source=miniblog) and login.'
                logger.error(error_msg)
                return ActionResult(error=error_msg, extracted_content=error_msg)

        @self.registry.action(
            '',
            param_model=SkillDouyinAction,
        )
        async def skill_douyin(
                params: SkillDouyinAction,
                browser_manager: BrowserManager,
                file_system: CustomFileSystem
        ):
            """
            Skill: Douyin API integration
            
            Available methods:
            - search_content_by_keyword: Search content by keyword with filtering options
            - fetch_video_details: Get detailed information about specific video
            - fetch_all_video_comments: Get all comments for specific video
            - fetch_user_info: Get user profile information
            - fetch_all_user_videos: Get all videos by a user
            """
            try:
                from vibe_surf.tools.website_api.douyin.client import DouyinApiClient

                # Initialize client
                dy_client = DouyinApiClient(browser_session=browser_manager.main_browser_session)
                await dy_client.setup()

                # Parse params JSON string
                import json
                from json_repair import repair_json
                try:
                    method_params = json.loads(params.params)
                except json.JSONDecodeError:
                    method_params = json.loads(repair_json(params.params))

                # Execute the requested method
                result = None
                if params.method == "search_content_by_keyword":
                    result = await dy_client.search_content_by_keyword(**method_params)
                elif params.method == "fetch_video_details":
                    result = await dy_client.fetch_video_details(**method_params)
                elif params.method == "fetch_all_video_comments":
                    result = await dy_client.fetch_all_video_comments(**method_params)
                elif params.method == "fetch_user_info":
                    result = await dy_client.fetch_user_info(**method_params)
                elif params.method == "fetch_all_user_videos":
                    result = await dy_client.fetch_all_user_videos(**method_params)
                else:
                    return ActionResult(error=f"Unknown method: {params.method}")

                # Save result to file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"douyin_{params.method}_{timestamp}.json"
                filepath = file_system.get_dir() / "data" / filename
                filepath.parent.mkdir(exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                # Format result as markdown
                if isinstance(result, list):
                    display_count = min(5, len(result))
                    md_content = f"## Douyin {params.method.replace('_', ' ').title()}\n\n"
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
                else:
                    md_content = f"## Douyin {params.method.replace('_', ' ').title()}\n\n"
                    for key, value in result.items():
                        if isinstance(value, str) and len(value) > 200:
                            md_content += f"- **{key}**: {value[:200]}...\n"
                        else:
                            md_content += f"- **{key}**: {value}\n"
                    md_content += "\n"

                # Add file path to markdown
                relative_path = str(filepath.relative_to(file_system.get_dir()))
                md_content += f"\n> 📁 Full data saved to: [{filename}]({relative_path})\n"
                md_content += f"> 💡 Click the link above to view all results.\n"

                logger.info(f'🎵 Douyin data retrieved with method: {params.method}')

                # Close client
                await dy_client.close()

                return ActionResult(
                    extracted_content=md_content
                )

            except Exception as e:
                error_msg = f'❌ Failed to retrieve Douyin data: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg, extracted_content=error_msg)

        @self.registry.action(
            """YouTube API - If users want to know the specific content of this video, please use get_video_transcript to get detailed video content first.""",
            param_model=SkillYoutubeAction,
        )
        async def skill_youtube(
                params: SkillYoutubeAction,
                browser_manager: BrowserManager,
                file_system: CustomFileSystem
        ):
            """
            Skill: YouTube API integration
            
            Available methods:
            - search_videos: Search videos by keyword
            - get_video_details: Get detailed information about specific video
            - get_video_comments: Get comments for specific video
            - get_channel_info: Get channel information
            - get_channel_videos: Get videos from specific channel
            - get_trending_videos: Get trending videos
            - get_video_transcript: Get video transcript in multiple languages
            """
            try:
                from vibe_surf.tools.website_api.youtube.client import YouTubeApiClient

                # Initialize client
                yt_client = YouTubeApiClient(browser_session=browser_manager.main_browser_session)
                await yt_client.setup()

                # Parse params JSON string
                import json
                from json_repair import repair_json
                try:
                    method_params = json.loads(params.params)
                except json.JSONDecodeError:
                    method_params = json.loads(repair_json(params.params))

                # Execute the requested method
                result = None
                if params.method == "search_videos":
                    result = await yt_client.search_videos(**method_params)
                elif params.method == "get_video_details":
                    result = await yt_client.get_video_details(**method_params)
                elif params.method == "get_video_comments":
                    result = await yt_client.get_video_comments(**method_params)
                elif params.method == "get_channel_info":
                    result = await yt_client.get_channel_info(**method_params)
                elif params.method == "get_channel_videos":
                    result = await yt_client.get_channel_videos(**method_params)
                elif params.method == "get_trending_videos":
                    result = await yt_client.get_trending_videos()
                elif params.method == "get_video_transcript":
                    result = await yt_client.get_video_transcript(**method_params)
                else:
                    return ActionResult(error=f"Unknown method: {params.method}")

                # Save result to file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"youtube_{params.method}_{timestamp}.json"
                filepath = file_system.get_dir() / "data" / filename
                filepath.parent.mkdir(exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                # Format result as markdown
                if isinstance(result, list):
                    display_count = min(5, len(result))
                    md_content = f"## YouTube {params.method.replace('_', ' ').title()}\n\n"
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
                else:
                    md_content = f"## YouTube {params.method.replace('_', ' ').title()}\n\n"
                    for key, value in result.items():
                        if isinstance(value, str) and len(value) > 200:
                            md_content += f"- **{key}**: {value[:200]}...\n"
                        else:
                            md_content += f"- **{key}**: {value}\n"
                    md_content += "\n"

                # Add file path to markdown
                relative_path = str(filepath.relative_to(file_system.get_dir()))
                md_content += f"\n> 📁 Full data saved to: [{filename}]({relative_path})\n"
                md_content += f"> 💡 Click the link above to view all results.\n"

                logger.info(f'🎬 YouTube data retrieved with method: {params.method}')

                # Close client
                await yt_client.close()

                return ActionResult(
                    extracted_content=md_content
                )

            except Exception as e:
                error_msg = f'❌ Failed to retrieve YouTube data: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg, extracted_content=error_msg)

        @self.registry.action(
            """Execute Python code for data processing, visualization, and analysis.
            """,
            param_model=ExecutePythonCodeAction,
        )
        async def execute_python_code(
                params: ExecutePythonCodeAction,
                file_system: CustomFileSystem
        ):
            try:
                # Get base directory from file system
                base_dir = str(file_system.get_dir())
                
                # Create a secure namespace with pre-imported libraries
                namespace = {
                    '__builtins__': {
                        # Safe built-ins only
                        'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
                        'chr': chr, 'dict': dict, 'dir': dir, 'divmod': divmod,
                        'enumerate': enumerate, 'filter': filter, 'float': float,
                        'format': format, 'frozenset': frozenset, 'getattr': getattr,
                        'hasattr': hasattr, 'hash': hash, 'hex': hex, 'id': id,
                        'int': int, 'isinstance': isinstance, 'issubclass': issubclass,
                        'iter': iter, 'len': len, 'list': list, 'map': map,
                        'max': max, 'min': min, 'next': next, 'oct': oct,
                        'ord': ord, 'pow': pow, 'print': print, 'range': range,
                        'repr': repr, 'reversed': reversed, 'round': round,
                        'set': set, 'setattr': setattr, 'slice': slice,
                        'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple,
                        'type': type, 'zip': zip,
                    },
                    'SAVE_DIR': base_dir,
                }
                
                # Import common libraries safely
                try:

                    # Add libraries to namespace
                    namespace.update({
                        'pd': pd,
                        'pandas': pd,
                        'np': np,
                        'numpy': np,
                        'plt': plt,
                        'matplotlib': matplotlib,
                        'sns': sns,
                        'seaborn': sns,
                        'json': json,
                        're': re,
                        'os': os,
                        'openpyxl': openpyxl,
                        'datetime': datetime,
                        'timedelta': timedelta,
                        'Path': Path,
                        'csv': csv,
                        'io': io
                    })
                    
                    # Add secure file helper functions
                    def safe_open(path, mode='r', **kwargs):
                        """Secure file open that restricts operations to BASE_DIR"""
                        if (not path.startswith(base_dir)) and os.path.isabs(path):
                            raise PermissionError("Absolute paths are not allowed. Only relative paths within workspace are supported.")
                        if not path.startswith(base_dir):
                            full_path = os.path.join(base_dir, path)
                        else:
                            full_path = path
                        if not full_path.startswith(base_dir):
                            raise PermissionError("File operations are restricted to workspace directory only.")
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        return open(full_path, mode, **kwargs)
                    
                    def safe_path(path):
                        """Get safe path within BASE_DIR"""
                        if (not path.startswith(base_dir)) and os.path.isabs(path):
                            raise PermissionError(
                                "Absolute paths are not allowed. Only relative paths within workspace are supported.")
                        if not path.startswith(base_dir):
                            full_path = os.path.join(base_dir, path)
                        else:
                            full_path = path
                        if not full_path.startswith(base_dir):
                            raise PermissionError("File operations are restricted to workspace directory only.")
                        return full_path
                    
                    namespace.update({
                        'open': safe_open,
                        'safe_path': safe_path,
                    })
                    
                except ImportError as e:
                    logger.warning(f"Failed to import some libraries: {e}")
                
                # Remove import statements from user code since modules are pre-imported
                cleaned_code = remove_import_statements(params.code)
                logger.info(cleaned_code)
                
                # Check for dangerous operations
                dangerous_keywords = [
                    'import subprocess', 'import sys', 'import importlib',
                    '__import__', 'eval(', 'exec(', 'compile(',
                    'open(', 'file(', 'input(', 'raw_input(',
                    'execfile', 'reload', 'vars(', 'globals(', 'locals(',
                    'delattr', 'setattr', 'getattr', '__'
                ]
                
                code_lower = cleaned_code.lower()
                for keyword in dangerous_keywords:
                    if keyword in code_lower and keyword not in ['open(', '__']:  # Allow our safe open
                        if keyword == 'open(' and 'safe_open' in cleaned_code:
                            continue  # Allow our safe open function
                        return ActionResult(
                            error=f"🚫 Security Error: Dangerous operation '{keyword}' detected. Code execution blocked for security reasons."
                        )
                
                # Capture stdout to get print outputs
                import sys
                from io import StringIO
                
                old_stdout = sys.stdout
                sys.stdout = captured_output = StringIO()
                
                try:
                    # Compile and execute the cleaned code
                    compiled_code = compile(cleaned_code, '<code>', 'exec')
                    exec(compiled_code, namespace, namespace)
                    
                    # Get the captured output
                    output_value = captured_output.getvalue()
                    if output_value.strip():
                        result_text = output_value
                    else:
                        result_text = "No output printed to console after executing the Python code."
                finally:
                    # Restore stdout
                    sys.stdout = old_stdout
                
                logger.info(f'🐍 Python code executed successfully')
                return ActionResult(
                    extracted_content=result_text)
                
            except PermissionError as e:
                error_msg = f'🚫 Security Error: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg, extracted_content=error_msg)
            except SyntaxError as e:
                error_msg = f'❌ Syntax Error in Python code: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg, extracted_content=error_msg)
            except Exception as e:
                error_msg = f'❌ Python code execution failed: {str(e)}'
                logger.error(error_msg)
                return ActionResult(error=error_msg, extracted_content=error_msg)

    def _register_extra_tools(self):
        """
        Register extra tools for dynamic toolkit and MCP tool access
        """

        @self.registry.action(
            'Get all available toolkit types from both Composio and MCP clients',
            param_model=NoParamsAction,
        )
        async def get_all_toolkit_types():
            """
            Get all toolkit types available in composio_toolkits and mcp_clients
            
            Returns:
                ActionResult with list of all toolkit type names
            """
            try:
                toolkit_types = []

                # Add Composio toolkit types
                if self.composio_toolkits:
                    toolkit_types.extend(list(self.composio_toolkits.keys()))

                # Add MCP client types
                if self.mcp_clients:
                    toolkit_types.extend(list(self.mcp_clients.keys()))

                result_text = f"Available toolkit types ({len(toolkit_types)} total):\n\n"

                # Group by type
                composio_types = list(self.composio_toolkits.keys()) if self.composio_toolkits else []
                mcp_types = list(self.mcp_clients.keys()) if self.mcp_clients else []

                if composio_types:
                    result_text += f"**Composio Toolkits ({len(composio_types)}):**\n"
                    for toolkit in composio_types:
                        result_text += f"- {toolkit}\n"
                    result_text += "\n"

                if mcp_types:
                    result_text += f"**MCP Clients ({len(mcp_types)}):**\n"
                    for client in mcp_types:
                        result_text += f"- {client}\n"
                    result_text += "\n"

                if not toolkit_types:
                    result_text = "No toolkit types available. Please register Composio toolkits or MCP clients first."

                logger.info(f'📋 Retrieved {len(toolkit_types)} toolkit types')
                return ActionResult(
                    extracted_content=result_text,
                )

            except Exception as e:
                logger.error(f'❌ Failed to get toolkit types: {e}')
                return ActionResult(error=f'Failed to get toolkit types: {str(e)}')

        @self.registry.action(
            'Search tools within a specific toolkit type by name and description filters',
            param_model=SearchToolAction,
        )
        async def search_tool(params: SearchToolAction):
            """
            Search tools by toolkit type and filters
            
            Args:
                params: SearchToolAction containing toolkit_type and filters
                
            Returns:
                ActionResult with matching tools and their descriptions
            """
            try:
                toolkit_type = params.toolkit_type
                if params.filters:
                    filters = [f.lower() for f in params.filters]
                else:
                    filters = []

                matching_tools = []

                # Search in registry actions with prefixes
                for action_name, action in self.registry.registry.actions.items():
                    # Check if this action belongs to the specified toolkit type
                    if toolkit_type in self.composio_toolkits and action_name.startswith(f"cpo.{toolkit_type}."):
                        # Get tool description from param_model
                        try:
                            param_dict = action.param_model.model_json_schema()
                            description = param_dict.get('description', action_name)
                        except:
                            description = action_name

                        # Check if any filter matches tool name or description
                        search_text = f"{action_name} {description}".lower()
                        if any(filter_term in search_text for filter_term in filters):
                            matching_tools.append({
                                'tool_name': action_name,
                                'description': description
                            })

                    elif toolkit_type in self.mcp_clients and action_name.startswith(f"mcp.{toolkit_type}."):
                        # Get tool description from param_model
                        try:
                            param_dict = action.param_model.model_json_schema()
                            description = param_dict.get('description', action_name)
                        except:
                            description = action_name

                        # Check if any filter matches tool name or description
                        search_text = f"{action_name} {description}".lower()
                        if any(filter_term in search_text for filter_term in filters):
                            matching_tools.append({
                                'tool_name': action_name,
                                'description': description
                            })

                # Format results
                if matching_tools:
                    result_text = f"Found {len(matching_tools)} tools in '{toolkit_type}' matching filters {params.filters}:\n\n"
                    for i, tool in enumerate(matching_tools, 1):
                        result_text += f"{i}. **{tool['tool_name']}**\n"
                        result_text += f"   Description: {tool['description']}\n\n"
                else:
                    result_text = f"No tools found in '{toolkit_type}' matching filters {params.filters}"

                logger.info(f'🔍 Found {len(matching_tools)} tools in {toolkit_type} matching filters')
                return ActionResult(
                    extracted_content=result_text,
                    include_extracted_content_only_once=True,
                    long_term_memory=f'Found {len(matching_tools)} tools in {toolkit_type} matching filters: {", ".join(params.filters)}'
                )

            except Exception as e:
                logger.error(f'❌ Failed to search tools: {e}')
                return ActionResult(error=f'Failed to search tools: {str(e)}')

        @self.registry.action(
            'Get detailed information about a specific tool including its parameters',
            param_model=GetToolInfoAction,
        )
        async def get_tool_info(params: GetToolInfoAction):
            """
            Get tool information including parameter model
            
            Args:
                params: GetToolInfoAction containing tool_name
                
            Returns:
                ActionResult with tool parameter information
            """
            try:
                tool_name = params.tool_name

                if tool_name not in self.registry.registry.actions:
                    return ActionResult(error=f'Tool "{tool_name}" not found in registry')

                action = self.registry.registry.actions[tool_name]

                # Convert param_model to dict
                try:
                    param_dict = action.param_model.model_json_schema()
                    result_text = json.dumps(param_dict, indent=2, ensure_ascii=False)
                except Exception as e:
                    result_text = f"Tool: {tool_name}\nError getting parameter info: {str(e)}"

                logger.info(f'ℹ️ Retrieved tool info for: {tool_name}')
                return ActionResult(
                    extracted_content=f"```json\n{result_text}\n```"
                )

            except Exception as e:
                logger.error(f'❌ Failed to get tool info: {e}')
                return ActionResult(error=f'Failed to get tool info: {str(e)}')

        @self.registry.action(
            'Execute a specific extra tool with provided parameters',
            param_model=ExecuteExtraToolAction,
        )
        async def execute_extra_tool(
                params: ExecuteExtraToolAction,
                browser_manager: BrowserManager,
                page_extraction_llm: BaseChatModel,
                file_system: CustomFileSystem
        ):
            """
            Execute an extra tool with given parameters
            
            Args:
                params: ExecuteExtraToolAction containing tool_name and tool_params
                browser_manager: Browser manager instance
                page_extraction_llm: LLM instance
                file_system: File system instance
                
            Returns:
                ActionResult from the executed tool
            """
            try:
                tool_name = params.tool_name

                if tool_name not in self.registry.registry.actions:
                    return ActionResult(error=f'Tool "{tool_name}" not found in registry')

                # Parse tool parameters
                try:
                    tool_params_dict = json.loads(params.tool_params)
                except json.JSONDecodeError:
                    try:
                        tool_params_dict = json.loads(repair_json(params.tool_params))
                    except Exception as e:
                        return ActionResult(error=f'Failed to parse tool parameters: {str(e)}')

                # Get the action
                action = self.registry.registry.actions[tool_name]

                # Create special context (same as in act method)
                special_context = {
                    'browser_manager': browser_manager,
                    'page_extraction_llm': page_extraction_llm,
                    'file_system': file_system,
                }

                # Validate parameters
                try:
                    validated_params = action.param_model(**tool_params_dict)
                except Exception as e:
                    return ActionResult(
                        error=f'Invalid parameters {tool_params_dict} for action {tool_name}: {type(e)}: {e}')

                # Execute the tool
                result = await action.function(params=validated_params, **special_context)

                logger.info(f'🔧 Successfully executed extra tool: {tool_name}')
                return result

            except Exception as e:
                logger.error(f'❌ Failed to execute extra tool: {e}')
                return ActionResult(error=f'Failed to execute extra tool: {str(e)}')

    def _register_browser_use_agent(self):
        @self.registry.action(
            'Execute browser_use agent tasks. Please specify a tab id to an agent, if you want to let agent work on this tab. When using Parallel Task Processing, each `tab_id` in parameter must be unique - one tab_id can only be assigned to one agent during parallel execution. Otherwise, please use single bu agent to complete the task.',
            param_model=BrowserUseAgentExecution,
        )
        async def execute_browser_use_agent(
                params: BrowserUseAgentExecution,
        ):
            """
            Execute browser_use agent tasks in parallel for improved efficiency.
            
            Args:
                params: BrowserUseAgentExecution containing list of tasks to execute
                browser_manager: Browser manager instance
                llm: Language model instance
                file_system: File system instance
                
            Returns:
                ActionResult with execution results
            """
            # TODO: Implement parallel execution of browser_use agent tasks
            # This is a placeholder implementation
            pass

    def _register_report_writer_agent(self):
        @self.registry.action(
            'Execute report writer agent to generate HTML reports. ',
            param_model=ReportWriterTask,
        )
        async def execute_report_writer_agent(
                params: ReportWriterTask,
        ):
            """
            Execute report writer agent to generate HTML reports.
            
            Args:
                params: ReportWriterTask containing task description with requirements and insights
                browser_manager: Browser manager instance
                llm: Language model instance
                file_system: File system instance
                
            Returns:
                ActionResult with generated report path
            """
            # TODO: Implement report writer agent execution
            # This is a placeholder implementation
            pass

    def _register_todo_actions(self):
        @self.registry.action(
            'Generate a new todo.md file with the provided todo items in markdown checkbox format.',
            param_model=TodoGenerateAction
        )
        async def generate_todos(params: TodoGenerateAction, file_system: CustomFileSystem):
            """Generate a new todo.md file with todo items in markdown format"""
            try:
                # Format todo items as markdown checkboxes
                formatted_items = []
                todo_items = params.todo_items
                for item in todo_items:
                    # Clean item and ensure it doesn't already have checkbox format
                    clean_item = item.strip()
                    if clean_item.startswith('- ['):
                        formatted_items.append(clean_item)
                    else:
                        formatted_items.append(f'- [ ] {clean_item}')

                # Create content for todo.md
                content = '\n'.join(formatted_items) + '\n'

                # Write to todo.md file
                todo_path = file_system.get_dir() / 'todo.md'
                if todo_path.exists():
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    await file_system.move_file('todo.md', f'todos/todo-{timestamp}.md')
                result = await file_system.write_file('todo.md', content)

                logger.info(f'📝 Generated todo.md with {len(todo_items)} items')
                return ActionResult(
                    extracted_content=f'Todo file generated successfully with {len(todo_items)} items:\n{content}',
                    long_term_memory=f'Generated todo.md with {len(todo_items)} items',
                )

            except Exception as e:
                logger.error(f'❌ Failed to generate todo file: {e}')
                raise RuntimeError(f'Failed to generate todo file: {str(e)}')

        @self.registry.action(
            'Read the current todo.md file content.'
        )
        async def read_todos(file_system: CustomFileSystem):
            """Read the current todo.md file content"""
            try:
                # Read todo.md file
                result = await file_system.read_file('todo.md')

                logger.info(f'📖 Read todo.md file')
                return ActionResult(
                    extracted_content=result,
                    long_term_memory='Read current todo list',
                    include_in_memory=True,
                )

            except Exception as e:
                logger.error(f'❌ Failed to read todo file: {e}')
                return ActionResult(
                    extracted_content='Error: todo.md file not found or could not be read',
                    long_term_memory='Failed to read todo file',
                )

        @self.registry.action(
            'Modify existing todo items in todo.md file. Supports add, remove, complete, and uncomplete operations.',
            param_model=TodoModifyAction,
        )
        async def modify_todos(params: TodoModifyAction, file_system: CustomFileSystem):
            """Modify existing todo items using various operations"""
            try:
                # First read current content
                current_content = await file_system.read_file('todo.md')

                # Extract just the content part (remove the "Read from file..." prefix)
                if '<content>' in current_content and '</content>' in current_content:
                    start = current_content.find('<content>') + len('<content>')
                    end = current_content.find('</content>')
                    content = current_content[start:end].strip()
                else:
                    content = current_content.strip()

                modified_content = content
                changes_made = []

                # Process each modification
                for modification in params.modifications:
                    action = modification.action
                    item = modification.item.strip()

                    if action == 'add':
                        # Add new item
                        if item:
                            # Format as checkbox if not already formatted
                            if not item.startswith('- ['):
                                item = f'- [ ] {item}'
                            modified_content += f'\n{item}'
                            changes_made.append(f'Added: {item}')

                    elif action == 'remove':
                        # Remove item
                        if item:
                            # Try to find and remove the item (with some flexibility)
                            lines = modified_content.split('\n')
                            new_lines = []
                            removed = False
                            for line in lines:
                                if item in line or line.strip().endswith(item):
                                    removed = True
                                    changes_made.append(f'Removed: {line.strip()}')
                                else:
                                    new_lines.append(line)
                            modified_content = '\n'.join(new_lines)
                            if not removed:
                                changes_made.append(f'Item not found for removal: {item}')

                    elif action == 'complete':
                        # Mark item as complete: - [ ] → - [x]
                        if item:
                            lines = modified_content.split('\n')
                            completed = False
                            for i, line in enumerate(lines):
                                if item in line and '- [ ]' in line:
                                    lines[i] = line.replace('- [ ]', '- [x]')
                                    completed = True
                                    changes_made.append(f'Completed: {line.strip()} → {lines[i].strip()}')
                                    break
                            modified_content = '\n'.join(lines)
                            if not completed:
                                changes_made.append(f'Item not found for completion: {item}')

                    elif action == 'uncompleted':
                        # Mark item as uncomplete: - [x] → - [ ]
                        if item:
                            lines = modified_content.split('\n')
                            uncompleted = False
                            for i, line in enumerate(lines):
                                if item in line and '- [x]' in line:
                                    lines[i] = line.replace('- [x]', '- [ ]')
                                    uncompleted = True
                                    changes_made.append(f'Uncompleted: {line.strip()} → {lines[i].strip()}')
                                    break
                            modified_content = '\n'.join(lines)
                            if not uncompleted:
                                changes_made.append(f'Item not found for uncompletion: {item}')

                # If we made any add/remove/complete/uncomplete changes, write the updated content
                if any(change.startswith(('Added:', 'Removed:', 'Completed:', 'Uncompleted:')) for change in
                       changes_made):
                    await file_system.write_file('todo.md', modified_content + '\n')

                changes_summary = '\n'.join(changes_made) if changes_made else 'No changes made'

                logger.info(f'✏️ Modified todo.md: {len(changes_made)} changes')
                return ActionResult(
                    extracted_content=f'Todo modifications completed:\n{changes_summary}\n\nUpdated content:\n{modified_content}',
                    long_term_memory=f'Modified todo list: {len(changes_made)} changes made',
                )

            except Exception as e:
                logger.error(f'❌ Failed to modify todo file: {e}')
                raise RuntimeError(f'Failed to modify todo file: {str(e)}')

    def _register_done_action(self):
        @self.registry.action(
            'Complete task and output final response. Use for simple responses or comprehensive markdown summaries with optional follow-up task suggestions.',
            param_model=VibeSurfDoneAction,
        )
        async def task_done(
                params: VibeSurfDoneAction,
        ):
            """
            Complete task execution and provide final response.

            """
            pass

    def _register_file_actions(self):
        @self.registry.action(
            ''
        )
        async def replace_file_str(file_name: str, old_str: str, new_str: str, file_system: CustomFileSystem):
            result = await file_system.replace_file_str(file_name, old_str, new_str)
            logger.info(f'💾 {result}')
            return ActionResult(extracted_content=result, long_term_memory=result)

        @self.registry.action(
            'Read file content from file system. If this is a file not in current file system, please provide an absolute path.')
        async def read_file(file_path: str, file_system: CustomFileSystem):
            if os.path.exists(file_path):
                external_file = True
            else:
                external_file = False
            result = await file_system.read_file(file_path, external_file=external_file)

            MAX_MEMORY_SIZE = 1000
            if len(result) > MAX_MEMORY_SIZE:
                lines = result.splitlines()
                display = ''
                lines_count = 0
                for line in lines:
                    if len(display) + len(line) < MAX_MEMORY_SIZE:
                        display += line + '\n'
                        lines_count += 1
                    else:
                        break
                remaining_lines = len(lines) - lines_count
                memory = f'{display}{remaining_lines} more lines...' if remaining_lines > 0 else display
            else:
                memory = result
            logger.info(f'💾 {memory}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=memory,
                include_extracted_content_only_once=True,
            )

        @self.registry.action(
            'Extract content from a file. Support image files, pdf, markdown, txt, json, csv.',
            param_model=FileExtractionAction,
        )
        async def extract_content_from_file(
                params: FileExtractionAction,
                page_extraction_llm: BaseChatModel,
                file_system: CustomFileSystem,
        ):
            try:
                # Get file path
                file_path = params.file_path
                full_file_path = file_path
                # Check if file exists
                if not os.path.exists(full_file_path):
                    full_file_path = os.path.join(str(file_system.get_dir()), file_path)

                # Use the utility function to extract content from file
                extracted_content = await extract_file_content_with_llm(
                    file_path=file_path,
                    query=params.query,
                    llm=page_extraction_llm,
                    file_system=file_system
                )

                # Handle memory storage
                if len(extracted_content) < 1000:
                    memory = extracted_content
                    include_extracted_content_only_once = False
                else:
                    save_result = await file_system.save_extracted_content(extracted_content)
                    memory = (
                        f'Extracted content from file {file_path} for query: {params.query}\nContent saved to file system: {save_result}'
                    )
                    include_extracted_content_only_once = True

                logger.info(f'📄 Extracted content from file: {file_path}')
                return ActionResult(
                    extracted_content=extracted_content,
                    include_extracted_content_only_once=include_extracted_content_only_once,
                    long_term_memory=memory,
                )

            except Exception as e:
                logger.debug(f'Error extracting content from file: {e}')
                raise RuntimeError(str(e))

        @self.registry.action(
            ''
        )
        async def write_file(
                file_path: str,
                content: str,
                file_system: CustomFileSystem,
                append: bool = False,
                trailing_newline: bool = True,
                leading_newline: bool = False,
        ):
            if trailing_newline:
                content += '\n'
            if leading_newline:
                content = '\n' + content
            if append:
                result = await file_system.append_file(file_path, content)
            else:
                result = await file_system.write_file(file_path, content)
            logger.info(f'💾 {result}')
            return ActionResult(extracted_content=result, long_term_memory=result)

        @self.registry.action(
            'Set external_src=True to copy from external file(absolute path)to FileSystem, False to copy within FileSystem.'
        )
        async def copy_file(src_file_path: str, dst_file_path: str, file_system: CustomFileSystem,
                            external_src: bool = False):
            result = await file_system.copy_file(src_file_path, dst_file_path, external_src)
            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

        @self.registry.action(
            'Rename a file to new_filename. src_file_path is a relative path to the FileSystem.'
        )
        async def rename_file(src_file_path: str, new_filename: str, file_system: CustomFileSystem):
            result = await file_system.rename_file(src_file_path, new_filename)
            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

        @self.registry.action(
            'Move a file within the FileSystem from old_filename to new_filename.'
        )
        async def move_file(old_file_path: str, new_file_path: str, file_system: CustomFileSystem):
            result = await file_system.move_file(old_file_path, new_file_path)
            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

        @self.registry.action(
            'Check file exist or not.'
        )
        async def file_exist(file_path: str, file_system: CustomFileSystem):
            if os.path.exists(file_path):
                result = f"{file_path} is a external file and it exists."
            else:
                is_file_exist = await file_system.file_exist(file_path)
                if is_file_exist:
                    result = f"{file_path} is in file system and it exists."
                else:
                    result = f"{file_path} does not exists."

            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

        @self.registry.action(
            'List a directory within the FileSystem. Use empty string "" or "." to list the root FileSystem, or provide relative path for subdirectory.'
        )
        async def list_directory(directory_path: str, file_system: CustomFileSystem):
            result = await file_system.list_directory(directory_path)
            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

        @self.registry.action(
            'search for query or keywords and return surrounding context',
            param_model=GrepContentAction,
        )
        async def grep_content_from_file(
                params: GrepContentAction,
                page_extraction_llm: BaseChatModel,
                file_system: CustomFileSystem,
        ):
            try:
                # Get file path
                file_path = params.file_path
                full_file_path = file_path
                # Check if file exists
                if not os.path.exists(full_file_path):
                    full_file_path = os.path.join(str(file_system.get_dir()), file_path)

                # Determine if file is an image based on MIME type
                mime_type, _ = mimetypes.guess_type(file_path)
                is_image = mime_type and mime_type.startswith('image/')

                if is_image:
                    # Handle image files with LLM vision for OCR
                    try:
                        # Read image file and encode to base64
                        with open(full_file_path, 'rb') as image_file:
                            image_data = image_file.read()
                            image_base64 = base64.b64encode(image_data).decode('utf-8')

                        # Create content parts for OCR
                        content_parts: list[ContentPartTextParam | ContentPartImageParam] = [
                            ContentPartTextParam(
                                text="Please extract all text content from this image for search purposes. Return only the extracted text, no additional explanations.")
                        ]

                        # Add the image
                        content_parts.append(
                            ContentPartImageParam(
                                image_url=ImageURL(
                                    url=f'data:{mime_type};base64,{image_base64}',
                                    media_type=mime_type,
                                    detail='high',
                                ),
                            )
                        )

                        # Create user message and invoke LLM for OCR
                        user_message = UserMessage(content=content_parts, cache=True)
                        response = await asyncio.wait_for(
                            page_extraction_llm.ainvoke([user_message]),
                            timeout=120.0,
                        )

                        file_content = response.completion

                    except Exception as e:
                        raise Exception(f'Failed to process image file {file_path} for OCR: {str(e)}')

                else:
                    # Handle non-image files by reading content
                    try:
                        file_content = await file_system.read_file(full_file_path, external_file=True)
                    except Exception as e:
                        raise Exception(f'Failed to read file {file_path}: {str(e)}')

                # Perform grep search
                search_query = params.query.lower()
                context_chars = params.context_chars

                # Find all matches with context
                matches = []
                content_lower = file_content.lower()
                search_start = 0

                while True:
                    match_pos = content_lower.find(search_query, search_start)
                    if match_pos == -1:
                        break

                    # Calculate context boundaries
                    start_pos = max(0, match_pos - context_chars)
                    end_pos = min(len(file_content), match_pos + len(search_query) + context_chars)

                    # Extract context with the match
                    context_before = file_content[start_pos:match_pos]
                    matched_text = file_content[match_pos:match_pos + len(search_query)]
                    context_after = file_content[match_pos + len(search_query):end_pos]

                    # Add ellipsis if truncated
                    if start_pos > 0:
                        context_before = "..." + context_before
                    if end_pos < len(file_content):
                        context_after = context_after + "..."

                    matches.append({
                        'context_before': context_before,
                        'matched_text': matched_text,
                        'context_after': context_after,
                        'position': match_pos
                    })

                    search_start = match_pos + 1

                # Format results
                if not matches:
                    extracted_content = f'File: {file_path}\nQuery: "{params.query}"\nResult: No matches found'
                else:
                    result_text = f'File: {file_path}\nQuery: "{params.query}"\nFound {len(matches)} match(es):\n\n'

                    for i, match in enumerate(matches, 1):
                        result_text += f"Match {i} (position: {match['position']}):\n"
                        result_text += f"{match['context_before']}[{match['matched_text']}]{match['context_after']}\n\n"

                    extracted_content = result_text.strip()

                # Handle memory storage
                if len(extracted_content) < 1000:
                    memory = extracted_content
                    include_extracted_content_only_once = False
                else:
                    save_result = await file_system.save_extracted_content(extracted_content)
                    memory = (
                        f'Grep search completed in file {file_path} for query: {params.query}\nFound {len(matches)} match(es)\nContent saved to file system: {save_result}'
                    )
                    include_extracted_content_only_once = True

                logger.info(f'🔍 Grep search completed in file: {file_path}, found {len(matches)} match(es)')
                return ActionResult(
                    extracted_content=extracted_content,
                    include_extracted_content_only_once=include_extracted_content_only_once,
                    long_term_memory=memory,
                )

            except Exception as e:
                logger.debug(f'Error grep searching content from file: {e}')
                raise RuntimeError(str(e))

        @self.registry.action(
            'Create a directory within the FileSystem.'
        )
        async def create_directory(directory_path: str, file_system: CustomFileSystem):
            result = await file_system.create_directory(directory_path)
            logger.info(f'📁 {result}')
            return ActionResult(
                extracted_content=result,
                include_in_memory=True,
                long_term_memory=result,
            )

    async def register_mcp_clients(self, mcp_server_config: Optional[Dict[str, Any]] = None):
        self.mcp_server_config = mcp_server_config or self.mcp_server_config
        if self.mcp_server_config:
            await self.unregister_mcp_clients()
            await self.register_mcp_tools()

    async def register_mcp_tools(self):
        """
        Register the MCP tools used by this tools.
        """
        if not self.mcp_server_config:
            return

        # Handle both formats: with or without "mcpServers" key
        mcp_servers = self.mcp_server_config.get('mcpServers', self.mcp_server_config)

        if not mcp_servers:
            return

        for server_name, server_config in mcp_servers.items():
            try:
                logger.info(f'Connecting to MCP server: {server_name}')

                # Create MCP client
                client = CustomMCPClient(
                    server_name=server_name,
                    command=server_config['command'],
                    args=server_config['args'],
                    env=server_config.get('env', None)
                )

                # Connect to the MCP server
                await client.connect(timeout=200)

                # Register tools to tools with prefix
                prefix = f"mcp.{server_name}."
                await client.register_to_tools(
                    tools=self,
                    prefix=prefix
                )

                # Store client for later cleanup
                self.mcp_clients[server_name] = client

                logger.info(f'Successfully registered MCP server: {server_name} with prefix: {prefix}')

            except Exception as e:
                logger.error(f'Failed to register MCP server {server_name}: {str(e)}')
                # Continue with other servers even if one fails

    async def unregister_mcp_clients(self):
        """
        Unregister and disconnect all MCP clients.
        """
        # Disconnect all MCP clients
        for server_name, client in self.mcp_clients.items():
            try:
                logger.info(f'Disconnecting MCP server: {server_name}')
                await client.disconnect()
            except Exception as e:
                logger.error(f'Failed to disconnect MCP server {server_name}: {str(e)}')

        # Remove MCP tools from registry
        try:
            # Get all registered actions
            actions_to_remove = []
            for action_name in list(self.registry.registry.actions.keys()):
                if action_name.startswith('mcp.'):
                    actions_to_remove.append(action_name)

            # Remove MCP actions from registry
            for action_name in actions_to_remove:
                if action_name in self.registry.registry.actions:
                    del self.registry.registry.actions[action_name]
                    logger.info(f'Removed MCP action: {action_name}')

        except Exception as e:
            logger.error(f'Failed to remove MCP actions from registry: {str(e)}')

        # Clear the clients dictionary
        self.mcp_clients.clear()
        logger.info('All MCP clients unregistered and disconnected')

    async def register_composio_clients(self, composio_instance: Optional[Any] = None,
                                        toolkit_tools_dict: Optional[Dict[str, Any]] = None):
        """
        Register Composio tools to the registry.
        
        Args:
            composio_instance: Composio instance (optional, can be None initially)
            toolkit_tools_dict: Dict of toolkit_slug -> tools list
        """
        try:
            # Initialize Composio client if not exists
            if self.composio_client is None:
                self.composio_client = ComposioClient(composio_instance=composio_instance)
            else:
                # Update the composio instance
                self.composio_client.update_composio_instance(composio_instance)
            self.composio_toolkits = toolkit_tools_dict
            # Register tools if we have both instance and toolkit tools
            if composio_instance and toolkit_tools_dict:
                await self.composio_client.register_to_tools(
                    tools=self,
                    toolkit_tools_dict=toolkit_tools_dict,
                    prefix="cpo."
                )
                logger.info(f'Successfully registered Composio tools from {len(toolkit_tools_dict)} toolkits')
            elif not composio_instance:
                logger.info("Composio client initialized without instance - will register tools later")
            elif not toolkit_tools_dict:
                logger.info("Composio client initialized without toolkit tools - will register tools later")

        except Exception as e:
            logger.error(f'Failed to register Composio clients: {str(e)}')

    async def unregister_composio_clients(self):
        """
        Unregister all Composio tools from the registry.
        """
        try:
            if self.composio_client:
                self.composio_client.unregister_all_tools(self)
                logger.info('All Composio tools unregistered')
            self.composio_toolkits.clear()
        except Exception as e:
            logger.error(f'Failed to unregister Composio clients: {str(e)}')

    async def update_composio_tools(self, composio_instance: Optional[Any] = None,
                                    toolkit_tools_dict: Optional[Dict[str, Any]] = None):
        """
        Update Composio tools by unregistering old ones and registering new ones.
        
        Args:
            composio_instance: Composio instance
            toolkit_tools_dict: Dict of toolkit_slug -> tools list
        """
        try:
            # Unregister existing tools
            await self.unregister_composio_clients()

            # Register new tools
            await self.register_composio_clients(composio_instance, toolkit_tools_dict)
            self.composio_toolkits = toolkit_tools_dict
            logger.info('Composio tools updated successfully')

        except Exception as e:
            logger.error(f'Failed to update Composio tools: {str(e)}')

    @time_execution_sync('--act')
    async def act(
            self,
            action: ActionModel,
            browser_manager: BrowserManager | None = None,
            llm: BaseChatModel | None = None,
            file_system: CustomFileSystem | None = None,
    ) -> ActionResult:
        """Execute an action"""

        for action_name, params in action.model_dump(exclude_unset=True).items():
            if params is not None:
                try:
                    if action_name not in self.registry.registry.actions:
                        raise ValueError(f'Action {action_name} not found')
                    action = self.registry.registry.actions[action_name]
                    special_context = {
                        'browser_manager': browser_manager,
                        'page_extraction_llm': llm,
                        'file_system': file_system,
                    }
                    try:
                        validated_params = action.param_model(**params)
                    except Exception as e:
                        raise ValueError(f'Invalid parameters {params} for action {action_name}: {type(e)}: {e}') from e

                    result = await action.function(params=validated_params, **special_context)
                except BrowserError as e:
                    logger.error(f'❌ Action {action_name} failed with BrowserError: {str(e)}')
                    result = handle_browser_error(e)
                except TimeoutError as e:
                    logger.error(f'❌ Action {action_name} failed with TimeoutError: {str(e)}')
                    result = ActionResult(error=f'{action_name} was not executed due to timeout.')
                except Exception as e:
                    # Log the original exception with traceback for observability
                    logger.error(f"Action '{action_name}' failed with error: {str(e)}")
                    result = ActionResult(error=str(e))

                if isinstance(result, str):
                    return ActionResult(extracted_content=result)
                elif isinstance(result, ActionResult):
                    return result
                elif result is None:
                    return ActionResult()
                else:
                    raise ValueError(f'Invalid action result type: {type(result)} of {result}')
        return ActionResult()
