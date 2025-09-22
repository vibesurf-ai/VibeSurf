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
from browser_use.llm.messages import UserMessage, ContentPartTextParam, ContentPartImageParam, ImageURL
from browser_use.dom.service import EnhancedDOMTreeNode
from browser_use.browser.views import BrowserError
from browser_use.mcp.client import MCPClient
from browser_use.tools.views import NoParamsAction
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.tools.views import HoverAction, ExtractionAction, FileExtractionAction, BrowserUseAgentExecution, \
    ReportWriterTask, TodoGenerateAction, TodoModifyAction, VibeSurfDoneAction, SkillSearchAction, SkillCrawlAction, \
    SkillSummaryAction, SkillTakeScreenshotAction, SkillDeepResearchAction, SkillCodeAction
from vibe_surf.tools.mcp_client import CustomMCPClient
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.browser.browser_manager import BrowserManager

from vibe_surf.logger import get_logger

logger = get_logger(__name__)

Context = TypeVar('Context')

T = TypeVar('T', bound=BaseModel)


class VibeSurfTools:
    def __init__(self, exclude_actions: list[str] = [], mcp_server_config: Optional[Dict[str, Any]] = None):
        self.registry = Registry(exclude_actions)
        self._register_file_actions()
        self._register_browser_use_agent()
        self._register_report_writer_agent()
        self._register_todo_actions()
        self._register_done_action()
        self._register_skills()
        self.mcp_server_config = mcp_server_config
        self.mcp_clients: Dict[str, MCPClient] = {}


    def _register_skills(self):
        @self.registry.action(
            'Skill: Advanced parallel search - analyze user intent and generate 5 different search tasks, perform parallel Google searches, and return top 10 most relevant results',
            param_model=SkillSearchAction,
        )
        async def skill_search(
            params: SkillSearchAction,
            browser_manager: BrowserManager,
            page_extraction_llm: BaseChatModel
        ):
            """
            Skill: Advanced parallel search with LLM-generated search strategies
            """
            llm = page_extraction_llm
            try:
                if not llm:
                    raise RuntimeError("LLM is required for skill_search")
                
                # Step 1: Use LLM to analyze user intent and generate different search tasks
                analysis_prompt = f"""
Analyze the user query and generate 5 different Google search strategies to comprehensively find relevant information.

User Query: "{params.query}"

Generate 5 different search queries that approach this topic from different angles. Each search should be:
1. Specific and concrete (good for Google search)
2. Different from the others (different perspectives/aspects)
3. Likely to return valuable, unique information

Return your response as a JSON array of 5 search query strings.
Example format: ["query 1", "query 2", "query 3", "query 4", "query 5"]
"""

                from browser_use.llm.messages import SystemMessage, UserMessage
                response = await llm.ainvoke([
                    SystemMessage(content="You are an expert at generating comprehensive search strategies."),
                    UserMessage(content=analysis_prompt)
                ])
                
                # Parse the search queries
                import json
                try:
                    search_queries = json.loads(response.completion.strip())
                    if not isinstance(search_queries, list):
                        raise ValueError("Invalid search queries format")
                    search_queries = search_queries[:5]
                except (json.JSONDecodeError, ValueError):
                    # Fallback to simple queries if parsing fails
                    try:
                        from json_repair import repair_json
                        search_queries = repair_json(response.completion.strip())
                    except Exception as e:
                        search_queries = [
                            params.query,
                            f"{params.query} guide",
                            f"{params.query} best practices",
                            f"{params.query} examples",
                            f"{params.query} latest news"
                        ]

                # Step 2: Create browser sessions for parallel searching
                register_sessions = []
                agent_ids = []
                
                for i, query in enumerate(search_queries):
                    agent_id = f"search_agent_{i + 1:03d}"
                    register_sessions.append(
                        browser_manager.register_agent(agent_id, target_id=None)
                    )
                    agent_ids.append(agent_id)
                
                agent_browser_sessions = await asyncio.gather(*register_sessions)
                
                # Step 3: Perform parallel Google searches
                search_tasks = []
                for i, (browser_session, query) in enumerate(zip(agent_browser_sessions, search_queries)):
                    search_tasks.append(self._perform_google_search(browser_session, query, llm))
                
                search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
                
                # Step 4: Aggregate and filter results
                all_results = []
                for i, result in enumerate(search_results):
                    if isinstance(result, Exception):
                        logger.error(f"Search task {i+1} failed: {result}")
                        continue
                    if result:
                        all_results.extend(result)
                
                # Step 5: Use LLM to deduplicate and rank top 10 results
                if all_results:
                    ranking_prompt = f"""
Given these search results for the query "{params.query}", please:
1. Remove duplicates (same or very similar content)
2. Rank by relevance and value to the user
3. Select the TOP 10 most relevant and valuable results

Search Results:
{json.dumps(all_results, indent=2)}

Return the top 10 results as a JSON array, with each result containing:
- title: string
- url: string
- summary: string (brief description of why this result is valuable)

Format: [{"title": "...", "url": "...", "summary": "..."}, ...]
"""
                    
                    ranking_response = await llm.ainvoke([
                        SystemMessage(content="You are an expert at evaluating and ranking search results for relevance and value."),
                        UserMessage(content=ranking_prompt)
                    ])
                    
                    try:
                        top_results = json.loads(ranking_response.completion.strip())
                        if not isinstance(top_results, list):
                            raise ValueError("Invalid ranking results format")
                    except (json.JSONDecodeError, ValueError):
                        # Fallback to first 10 results if ranking fails
                        top_results = all_results[:10]
                else:
                    top_results = []
                
                # Cleanup browser sessions
                cleanup_tasks = [browser_manager.unregister_agent(agent_id) for agent_id in agent_ids]
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
                
                # Format results for display
                if top_results:
                    results_text = f"🔍 Advanced Search Results for '{params.query}':\n\n"
                    for i, result in enumerate(top_results[:10], 1):
                        title = result.get('title', 'Unknown Title')
                        url = result.get('url', 'No URL')
                        summary = result.get('summary', 'No summary available')
                        results_text += f"{i}. **{title}**\n   URL: {url}\n   Summary: {summary}\n\n"
                else:
                    results_text = f"No results found for query: {params.query}"
                
                logger.info(f'🔍 Skill Search completed for: {params.query}')
                return ActionResult(
                    extracted_content=results_text,
                    include_extracted_content_only_once=True,
                    long_term_memory=f'Advanced search completed for: {params.query}, found {len(top_results)} relevant results',
                )
                
            except Exception as e:
                logger.error(f'❌ Skill Search failed: {e}')
                return ActionResult(error=f'Skill search failed: {str(e)}')

        @self.registry.action(
            'Skill: Extract structured information from a webpage with optional tab selection',
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
                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                    await browser_session.get_or_create_cdp_session(target_id, focus=True)
                
                # Extract structured content using the existing method
                extracted_content = await self._extract_structured_content(
                    browser_session, params.query, llm
                )
                
                current_url = await browser_session.get_current_page_url()
                result_text = f'<url>\n{current_url}\n</url>\n<query>\n{params.query}\n</query>\n<result>\n{extracted_content}\n</result>'
                
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
            'Skill: Summarize webpage content with optional tab selection',
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
                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                    await browser_session.get_or_create_cdp_session(target_id, focus=True)
                
                # Extract and summarize content
                summary = await self._extract_structured_content(
                    browser_session, "Provide a comprehensive summary of this webpage", llm
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
            'Skill: Take screenshot of current page or specified tab',
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
                screenshot = await browser_session.take_screenshot()

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
                    f.write(base64.b64decode(screenshot))

                msg = f'📸 Screenshot saved to path: {str(filepath.relative_to(fs_dir))}'
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
            'Skill: Execute JavaScript code on webpage with optional tab selection',
            param_model=SkillCodeAction,
        )
        async def skill_code(
            params: SkillCodeAction,
            browser_manager: BrowserManager,
        ):
            """
            Skill: Execute JavaScript code on current or specified webpage
            """
            try:
                # Get browser session
                browser_session = browser_manager.main_browser_session
                
                # If tab_id is provided, switch to that tab
                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                    await browser_session.get_or_create_cdp_session(target_id, focus=True)
                
                # Execute JavaScript code
                cdp_session = await browser_session.get_or_create_cdp_session()

                try:
                    # Always use awaitPromise=True - it's ignored for non-promises
                    result = await cdp_session.cdp_client.send.Runtime.evaluate(
                        params={'expression': params.js_code, 'returnByValue': True, 'awaitPromise': True},
                        session_id=cdp_session.session_id,
                    )

                    # Check for JavaScript execution errors
                    if result.get('exceptionDetails'):
                        exception = result['exceptionDetails']
                        error_msg = f'JavaScript execution error: {exception.get("text", "Unknown error")}'
                        if 'lineNumber' in exception:
                            error_msg += f' at line {exception["lineNumber"]}'
                        msg = f'Code: {params.js_code}\n\nError: {error_msg}'
                        logger.info(msg)
                        return ActionResult(error=msg)

                    # Get the result data
                    result_data = result.get('result', {})

                    # Check for wasThrown flag (backup error detection)
                    if result_data.get('wasThrown'):
                        msg = f'Code: {params.js_code}\n\nError: JavaScript execution failed (wasThrown=true)'
                        logger.info(msg)
                        return ActionResult(error=msg)

                    # Get the actual value
                    value = result_data.get('value')

                    # Handle different value types
                    if value is None:
                        # Could be legitimate null/undefined result
                        result_text = str(value) if 'value' in result_data else 'undefined'
                    elif isinstance(value, (dict, list)):
                        # Complex objects - should be serialized by returnByValue
                        try:
                            result_text = json.dumps(value, ensure_ascii=False)
                        except (TypeError, ValueError):
                            # Fallback for non-serializable objects
                            result_text = str(value)
                    else:
                        # Primitive values (string, number, boolean)
                        result_text = str(value)

                    # Apply length limit with better truncation
                    if len(result_text) > 20000:
                        result_text = result_text[:19950] + '\n... [Truncated after 20000 characters]'
                    msg = f'Code: {params.js_code}\n\nResult: {result_text}'
                    logger.info(msg)
                    
                    return ActionResult(
                        extracted_content=f'Code: {params.js_code}\n\nResult: {result_text}',
                        long_term_memory=f'Executed JavaScript code successfully',
                    )

                except Exception as e:
                    # CDP communication or other system errors
                    error_msg = f'Code: {params.js_code}\n\nError: Failed to execute JavaScript: {type(e).__name__}: {e}'
                    logger.info(error_msg)
                    return ActionResult(error=error_msg)
                
            except Exception as e:
                logger.error(f'❌ Skill Code failed: {e}')
                return ActionResult(error=f'Skill code failed: {str(e)}')

        @self.registry.action(
            'Skill: Deep research mode - Only return the guideline for deep research. Please follow the guideline to do real deep research actions.',
            param_model=NoParamsAction,
        )
        async def skill_deep_research(
                _: NoParamsAction,
        ):
            """
            Skill: Deep research mode activation
            """
            research_prompt = f"""
        🔬 **DEEP RESEARCH GUIDELINE**

        To proceed with comprehensive research, please:

        1. **Set up a detailed TODO list** for this research project that includes:
           - Background research and context gathering
           - Key questions to investigate
           - Multiple source verification
           - Data collection and analysis steps
           - Report generation with proper citations

        2. **Conduct systematic research** following these principles:
           - Use multiple search strategies and sources
           - Verify information across different platforms
           - Document all sources with URLs for citation
           - Take notes and screenshots of key findings
           - Organize findings by themes or categories

        3. **Generate a comprehensive report** that includes:
           - Executive summary
           - Detailed findings with analysis
           - Proper citations and source references
           - Supporting evidence (screenshots, quotes)
           - Conclusions and recommendations
           - Areas for further investigation

        4. **Maintain research traceability** by:
           - Recording all search queries used
           - Saving important URLs and sources
           - Including direct quotes with attribution
           - Documenting methodology and approach

        This deep research mode ensures thorough, traceable, and well-documented investigation of your topic with proper academic rigor and source citation.
        """

            return ActionResult(
                extracted_content=research_prompt,
                include_extracted_content_only_once=True,
            )

    async def _perform_google_search(self, browser_session, query: str, llm: BaseChatModel):
        """Helper method to perform Google search and extract top 5 results"""
        try:
            # Navigate to Google search
            search_url = f'https://www.google.com/search?q={query}&udm=14'
            await browser_session.navigate_to_url(search_url, new_tab=False)
            
            # Wait a moment for page to load
            await asyncio.sleep(2)
            
            # Extract structured content
            extraction_query = f"""
Extract the top 5 search results from this Google search page. For each result, provide:
- title: The clickable title/headline
- url: The website URL
- summary: A brief description of what this result contains

Return results as a JSON array: [{{"title": "...", "url": "...", "summary": "..."}}, ...]
"""
            
            results_text = await self._extract_structured_content(browser_session, extraction_query, llm)
            
            # Try to parse JSON results
            import json
            try:
                results = json.loads(results_text.strip())
                if isinstance(results, list):
                    return results[:5]  # Ensure max 5 results
            except (json.JSONDecodeError, ValueError):
                try:
                    results = repair_json(results_text.strip())
                    if isinstance(results, list):
                        return results[:5]  # Ensure max 5 results
                except Exception as e:
                    logger.warning(f"Failed to parse JSON from search results: {results_text}")
            
            # Fallback: return raw text as single result
            current_url = await browser_session.get_current_page_url()
            return [{
                "title": f"Search results for: {query}",
                "url": current_url,
                "summary": results_text[:200] + "..." if len(results_text) > 200 else results_text
            }]
            
        except Exception as e:
            logger.error(f"Google search failed for query '{query}': {e}")
            return []

    async def _extract_structured_content(self, browser_session, query: str, llm: BaseChatModel):
        """Helper method to extract structured content from current page"""
        MAX_CHAR_LIMIT = 30000

        # Extract clean markdown using the existing method
        try:
            content, content_stats = await self.extract_clean_markdown(browser_session, extract_links=False)
        except Exception as e:
            raise RuntimeError(f'Could not extract clean markdown: {type(e).__name__}')

        # Smart truncation with context preservation
        if len(content) > MAX_CHAR_LIMIT:
            # Try to truncate at a natural break point
            truncate_at = MAX_CHAR_LIMIT
            paragraph_break = content.rfind('\n\n', MAX_CHAR_LIMIT - 500, MAX_CHAR_LIMIT)
            if paragraph_break > 0:
                truncate_at = paragraph_break
            else:
                sentence_break = content.rfind('.', MAX_CHAR_LIMIT - 200, MAX_CHAR_LIMIT)
                if sentence_break > 0:
                    truncate_at = sentence_break + 1
            content = content[:truncate_at]

        system_prompt = """
You are an expert at extracting data from the markdown of a webpage.

<input>
You will be given a query and the markdown of a webpage that has been filtered to remove noise and advertising content.
</input>

<instructions>
- You are tasked to extract information from the webpage that is relevant to the query.
- You should ONLY use the information available in the webpage to answer the query. Do not make up information or provide guess from your own knowledge.
- If the information relevant to the query is not available in the page, your response should mention that.
- If the query asks for all items, products, etc., make sure to directly list all of them.
</instructions>

<output>
- Your output should present ALL the information relevant to the query in a concise way.
- Do not answer in conversational format - directly output the relevant information or that the information is unavailable.
</output>
""".strip()

        prompt = f'<query>\n{query}\n</query>\n\n<webpage_content>\n{content}\n</webpage_content>'

        try:
            from browser_use.llm.messages import SystemMessage, UserMessage
            response = await asyncio.wait_for(
                llm.ainvoke([SystemMessage(content=system_prompt), UserMessage(content=prompt)]),
                timeout=120.0,
            )
            return response.completion
        except Exception as e:
            logger.debug(f'Error extracting content: {e}')
            raise RuntimeError(str(e))

    async def extract_clean_markdown(
        self, browser_session: BrowserSession, extract_links: bool = True
    ) -> tuple[str, dict[str, Any]]:
        """Extract clean markdown from the current page."""
        import re

        # Get HTML content from current page
        cdp_session = await browser_session.get_or_create_cdp_session()
        try:
            body_id = await cdp_session.cdp_client.send.DOM.getDocument(session_id=cdp_session.session_id)
            page_html_result = await cdp_session.cdp_client.send.DOM.getOuterHTML(
                params={'backendNodeId': body_id['root']['backendNodeId']}, session_id=cdp_session.session_id
            )
            page_html = page_html_result['outerHTML']
            current_url = await browser_session.get_current_page_url()
        except Exception as e:
            raise RuntimeError(f"Couldn't extract page content: {e}")

        original_html_length = len(page_html)

        # Use html2text for clean markdown conversion
        import html2text

        h = html2text.HTML2Text()
        h.ignore_links = not extract_links
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0  # Don't wrap lines
        h.unicode_snob = True
        h.skip_internal_links = True
        content = h.handle(page_html)

        initial_markdown_length = len(content)

        # Minimal cleanup - html2text already does most of the work
        content = re.sub(r'%[0-9A-Fa-f]{2}', '', content)  # Remove any remaining URL encoding

        # Apply light preprocessing to clean up excessive whitespace
        content, chars_filtered = self._preprocess_markdown_content(content)

        final_filtered_length = len(content)

        # Content statistics
        stats = {
            'url': current_url,
            'original_html_chars': original_html_length,
            'initial_markdown_chars': initial_markdown_length,
            'filtered_chars_removed': chars_filtered,
            'final_filtered_chars': final_filtered_length,
        }

        return content, stats

    def _preprocess_markdown_content(self, content: str, max_newlines: int = 3) -> tuple[str, int]:
        """Light preprocessing of html2text output - minimal cleanup since html2text is already clean."""
        import re

        original_length = len(content)

        # Compress consecutive newlines (4+ newlines become max_newlines)
        content = re.sub(r'\n{4,}', '\n' * max_newlines, content)

        # Remove lines that are only whitespace or very short (likely artifacts)
        lines = content.split('\n')
        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            # Keep lines with substantial content (html2text output is already clean)
            if len(stripped) > 2:
                filtered_lines.append(line)

        content = '\n'.join(filtered_lines)
        content = content.strip()

        chars_filtered = original_length - len(content)
        return content, chars_filtered

    def _register_browser_use_agent(self):
        @self.registry.action(
            'Execute browser_use agent tasks. Supports both single task execution (list length=1) and '
            'parallel execution of multiple tasks for improved efficiency. '
            'Accepts a list of tasks where each task can specify a tab_id (optional), '
            'task description (focusing on goals and expected returns), and task_files (optional). '
            'Browser_use agent has strong planning and execution capabilities, only needs task descriptions and desired outcomes.',
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
            'Execute report writer agent to generate HTML reports. '
            'Task should describe report requirements, goals, insights observed, and any hints or tips for generating the report.',
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
            'Replace old_str with new_str in file_name. old_str must exactly match the string to replace in original text. Recommended tool to mark completed items in todo.md or change specific contents in a file.'
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

                # Determine if file is an image based on MIME type
                mime_type, _ = mimetypes.guess_type(file_path)
                is_image = mime_type and mime_type.startswith('image/')

                if is_image:
                    # Handle image files with LLM vision
                    try:
                        # Read image file and encode to base64
                        with open(full_file_path, 'rb') as image_file:
                            image_data = image_file.read()
                            image_base64 = base64.b64encode(image_data).decode('utf-8')

                        # Create content parts similar to the user's example
                        content_parts: list[ContentPartTextParam | ContentPartImageParam] = [
                            ContentPartTextParam(text=f"Query: {params.query}")
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

                        # Create user message and invoke LLM
                        user_message = UserMessage(content=content_parts, cache=True)
                        response = await asyncio.wait_for(
                            page_extraction_llm.ainvoke([user_message]),
                            timeout=120.0,
                        )

                        extracted_content = f'File: {file_path}\nQuery: {params.query}\nExtracted Content:\n{response.completion}'

                    except Exception as e:
                        raise Exception(f'Failed to process image file {file_path}: {str(e)}')

                else:
                    # Handle non-image files by reading content
                    try:
                        file_content = await file_system.read_file(full_file_path, external_file=True)

                        # Create a simple prompt for text extraction
                        prompt = f"""Extract the requested information from this file content.

        Query: {params.query}

        File: {file_path}
        File Content:
        {file_content}

        Provide the extracted information in a clear, structured format."""

                        response = await asyncio.wait_for(
                            page_extraction_llm.ainvoke([UserMessage(content=prompt)]),
                            timeout=120.0,
                        )

                        extracted_content = f'File: {file_path}\nQuery: {params.query}\nExtracted Content:\n{response.completion}'

                    except Exception as e:
                        raise Exception(f'Failed to read file {file_path}: {str(e)}')

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
            'Write or append content to file_path in file system. Allowed extensions are .md, .txt, .json, .csv, .pdf. For .pdf files, write the content in markdown format and it will automatically be converted to a properly formatted PDF document.'
        )
        async def write_file(
                file_path: str,
                content: str,
                file_system: FileSystem,
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
            'Copy a file to the FileSystem. Set external_src=True to copy from external file(absolute path)to FileSystem, False to copy within FileSystem.'
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
            'List contents of a directory within the FileSystem. Use empty string "" or "." to list the root data_dir, or provide relative path for subdirectory.'
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
