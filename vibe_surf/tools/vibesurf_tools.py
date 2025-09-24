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
    SkillSummaryAction, SkillTakeScreenshotAction, SkillDeepResearchAction, SkillCodeAction, SkillFinanceAction
from vibe_surf.tools.finance_tools import FinanceDataRetriever, FinanceMarkdownFormatter, FinanceMethod
from vibe_surf.tools.mcp_client import CustomMCPClient
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.tools.vibesurf_registry import VibeSurfRegistry
from bs4 import BeautifulSoup
from vibe_surf.logger import get_logger

logger = get_logger(__name__)

Context = TypeVar('Context')

T = TypeVar('T', bound=BaseModel)


def clean_html_basic(page_html_content, max_text_length=100):
    soup = BeautifulSoup(page_html_content, 'html.parser')

    for script in soup(["script", "style"]):
        script.decompose()

    from bs4 import Comment
    comments = soup.findAll(text=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment.extract()

    for text_node in soup.find_all(string=True):
        if text_node.parent.name not in ['script', 'style']:
            clean_text = ' '.join(text_node.split())

            if len(clean_text) > max_text_length:
                clean_text = clean_text[:max_text_length].rstrip() + "..."

            if clean_text != text_node:
                text_node.replace_with(clean_text)

    important_attrs = ['id', 'class', 'name', 'role', 'type',
                       'colspan', 'rowspan', 'headers', 'scope',
                       'href', 'src', 'alt', 'title']

    for tag in soup.find_all():
        attrs_to_keep = {}
        for attr in list(tag.attrs.keys()):
            if (attr in important_attrs or
                    attr.startswith('data-') or
                    attr.startswith('aria-')):
                attrs_to_keep[attr] = tag.attrs[attr]
        tag.attrs = attrs_to_keep

    return str(soup)


def get_sibling_position(node: EnhancedDOMTreeNode) -> int:
    """Get the position of node among its siblings with the same tag"""
    if not node.parent_node:
        return 1

    tag_name = node.tag_name
    position = 1

    # Find siblings with same tag name before this node
    for sibling in node.parent_node.children:
        if sibling == node:
            break
        if sibling.tag_name == tag_name:
            position += 1

    return position


def extract_css_hints(node: EnhancedDOMTreeNode) -> dict:
    """Extract CSS selector construction hints"""
    hints = {}

    if "id" in node.attributes:
        hints["id"] = f"#{node.attributes['id']}"

    if "class" in node.attributes:
        classes = node.attributes["class"].split()
        hints["class"] = f".{'.'.join(classes[:3])}"  # Limit class count

    # Attribute selector hints
    for attr in ["name", "data-testid", "type"]:
        if attr in node.attributes:
            hints[f"attr_{attr}"] = f"[{attr}='{node.attributes[attr]}']"

    return hints


def convert_selector_map_for_llm(selector_map) -> dict:
    """
    Convert complex selector_map to simplified format suitable for LLM understanding and JS code writing
    """
    simplified_elements = []

    for element_index, node in selector_map.items():
        if node.is_visible and node.element_index is not None:  # Only include visible interactive elements
            element_info = {
                "tag": node.tag_name,
                "text": node.get_meaningful_text_for_llm()[:200],  # Limit text length

                # Selector information - most needed for JS code
                "selectors": {
                    "xpath": node.xpath,
                    "css_hints": extract_css_hints(node),  # Extract id, class etc
                },

                # Element semantics
                "role": node.ax_node.role if node.ax_node else None,
                "type": node.attributes.get("type"),
                "aria_label": node.attributes.get("aria-label"),

                # Key attributes
                "attributes": {k: v for k, v in node.attributes.items()
                               if k in ["id", "class", "name", "href", "src", "value", "placeholder", "data-testid"]},

                # Interactivity
                "is_clickable": node.snapshot_node.is_clickable if node.snapshot_node else False,
                "is_input": node.tag_name.lower() in ["input", "textarea", "select"],

                # Structure information
                "parent_tag": node.parent_node.tag_name if node.parent_node else None,
                "position_info": f"{node.tag_name}[{get_sibling_position(node)}]"
            }
            simplified_elements.append(element_info)

    return {
        "page_elements": simplified_elements,
        "total_elements": len(simplified_elements)
    }


class VibeSurfTools:
    def __init__(self, exclude_actions: list[str] = [], mcp_server_config: Optional[Dict[str, Any]] = None):
        self.registry = VibeSurfRegistry(exclude_actions)
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
            agent_ids = []
            try:
                if not llm:
                    raise RuntimeError("LLM is required for skill_search")

                # Step 1: Use LLM to analyze user intent and generate different search tasks
                query_num = 6
                from datetime import datetime
                analysis_prompt = f"""
Analyze the user query and generate 5 different Google search strategies to comprehensively find relevant information.

Current Time: {datetime.now().isoformat()}

User Query: "{params.query}"

Generate {query_num} different search queries that approach this topic from different angles. Each search should be:
1. Specific and concrete (good for Google search)
2. Different from the others (different perspectives/aspects)
3. Likely to return valuable, unique information

Return your response as a JSON array of {query_num} search query strings.
Example format: ["query 1", "query 2", "query 3", "query 4", "query 5", "query 6"]
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
                    search_queries = search_queries[:query_num]
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
                        logger.error(f"Search task {i + 1} failed: {result}")
                        continue
                    if result:
                        all_results.extend(result)

                # Step 4.5: Rule-based deduplication to reduce LLM processing load
                # if all_results:
                #     deduplicated_results = self._rule_based_deduplication(all_results)
                #     logger.info(f"Rule-based deduplication: {len(all_results)} -> {len(deduplicated_results)} results")
                # else:
                #     deduplicated_results = []

                # Step 5: Use LLM only for final ranking and selection (much smaller dataset now)
                if all_results and len(all_results) > 10:
                    # Only use LLM if we have more than 10 results to rank
                    ranking_prompt = f"""
Rank these search results for the query "{params.query}" by relevance and value.
Select the TOP 10 most relevant and valuable results.

Search Results ({len(all_results)} total):
{json.dumps(all_results, indent=2)}

Return the top 10 results as a JSON array with each result containing:
- title: string
- url: string
- summary: string (brief description of why this result is valuable)

Format: [{{"title": "...", "url": "...", "summary": "..."}}, ...]
"""

                    ranking_response = await llm.ainvoke([
                        SystemMessage(
                            content="You are an expert at ranking search results for relevance and value."),
                        UserMessage(content=ranking_prompt)
                    ])

                    try:
                        top_results = json.loads(ranking_response.completion.strip())
                        if not isinstance(top_results, list):
                            raise ValueError("Invalid ranking results format")
                        top_results = top_results[:10]  # Ensure max 10 results
                    except (json.JSONDecodeError, ValueError):
                        try:
                            top_results = repair_json(ranking_response.completion.strip())
                            if isinstance(top_results, list):
                                top_results = top_results[:10]
                            else:
                                top_results = all_results[:10]
                        except Exception:
                            # Fallback to first 10 deduplicated results
                            top_results = all_results[:10]
                elif all_results:
                    # If we have 10 or fewer results, skip LLM ranking
                    top_results = all_results[:10]
                    logger.info(f"Skipping LLM ranking for {len(all_results)} results (≤10)")
                else:
                    top_results = []

                # Format results for display
                if top_results:
                    results_text = f"🔍 Advanced Search Results for '{params.query}':\n\n"
                    for i, result in enumerate(top_results[:10]):
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
            finally:
                for i, agent_id in enumerate(agent_ids):
                    await browser_manager.unregister_agent(agent_id, close_tabs=True)

        @self.registry.action(
            'Skill: Crawl a web page and extract structured information from a webpage with optional tab selection',
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
            'Skill: Execute JavaScript code on webpage with optional tab selection - accepts functional requirements, code prompts, or code snippets that will be processed by LLM to generate proper executable JavaScript',
            param_model=SkillCodeAction,
        )
        async def skill_code(
                params: SkillCodeAction,
                browser_manager: BrowserManager,
                page_extraction_llm: BaseChatModel,
        ):
            """
            Skill: Generate and execute JavaScript code from functional requirements or code prompts with iterative retry logic
            """
            MAX_ITERATIONS = 5

            try:
                if not page_extraction_llm:
                    raise RuntimeError("LLM is required for skill_code")

                # Get browser session
                browser_session = browser_manager.main_browser_session

                # If tab_id is provided, switch to that tab
                if params.tab_id:
                    target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
                    await browser_session.get_or_create_cdp_session(target_id, focus=True)

                # Get browser state and convert for LLM
                # browser_state = await browser_session.get_browser_state_summary()
                # web_page_description = browser_state.dom_state.llm_representation()

                page_html_content = await browser_session.get_html_content()
                web_page_html = clean_html_basic(page_html_content)
                if len(web_page_html) > 30000:
                    web_page_html = web_page_html[:24000] + "..." + web_page_html[-6000:]

                # Get current page URL for context
                current_url = await browser_session.get_current_page_url()

                # Create base system prompt for JavaScript code generation
                base_system_prompt = """You are an expert JavaScript developer specializing in browser automation and DOM manipulation.

You will be given a functional requirement or code prompt, along with the current page's DOM structure information.
Your task is to generate valid, executable JavaScript code that accomplishes the specified requirement.

IMPORTANT GUIDELINES:
This JavaScript code gets executed with Runtime.evaluate and 'returnByValue': True, 'awaitPromise': True

SYNTAX RULES - FAILURE TO FOLLOW CAUSES "Uncaught at line 0" ERRORS:
- ALWAYS wrap your code in IIFE: (function(){ ... })() or (async function(){ ... })() for async code
- ALWAYS add try-catch blocks to prevent execution errors
- ALWAYS use proper semicolons and valid JavaScript syntax
- NEVER write multiline code without proper IIFE wrapping
- ALWAYS validate elements exist before accessing them

EXAMPLES:
Use this tool when other tools do not work on the first try as expected or when a more general tool is needed, e.g. for filling a form all at once, hovering, dragging, extracting only links, extracting content from the page, press and hold, hovering, clicking on coordinates, zooming, use this if the user provides custom selectors which you can otherwise not interact with ....
You can also use it to explore the website.
- Write code to solve problems you could not solve with other tools.
- Don't write comments in here, no human reads that.
- Write only valid js code.
- use this to e.g. extract + filter links, convert the page to json into the format you need etc...

- limit the output otherwise your context will explode
- think if you deal with special elements like iframes / shadow roots etc
- Adopt your strategy for React Native Web, React, Angular, Vue, MUI pages etc.
- e.g. with  synthetic events, keyboard simulation, shadow DOM, etc.

PROPER SYNTAX EXAMPLES:
CORRECT: (function(){ try { const el = document.querySelector('#id'); return el ? el.value : 'not found'; } catch(e) { return 'Error: ' + e.message; } })()
CORRECT: (async function(){ try { await new Promise(r => setTimeout(r, 100)); return 'done'; } catch(e) { return 'Error: ' + e.message; } })()

WRONG: const el = document.querySelector('#id'); el ? el.value : '';
WRONG: document.querySelector('#id').value
WRONG: Multiline code without IIFE wrapping

SHADOW DOM ACCESS EXAMPLE:
(function(){
    try {
        const hosts = document.querySelectorAll('*');
        for (let host of hosts) {
            if (host.shadowRoot) {
                const el = host.shadowRoot.querySelector('#target');
                if (el) return el.textContent;
            }
        }
        return 'Not found';
    } catch(e) {
        return 'Error: ' + e.message;
    }
})()

## Return values:
- Async functions (with await, promises, timeouts) are automatically handled
- Returns strings, numbers, booleans, and serialized objects/arrays
- Use JSON.stringify() for complex objects: JSON.stringify(Array.from(document.querySelectorAll('a')).map(el => el.textContent.trim()))

OUTPUT FORMAT:
Return ONLY the JavaScript code, no explanations or markdown formatting."""

                # Initialize message history for iterative prompting
                from browser_use.llm.messages import SystemMessage, UserMessage
                message_history = [SystemMessage(content=base_system_prompt)]

                # Initial user prompt
                initial_user_prompt = f"""Current Page URL: {current_url}

USER REQUIREMENT: {params.code_requirement}

Web Page Html Content:
{web_page_html}

Generate JavaScript code to fulfill the requirement:"""

                message_history.append(UserMessage(content=initial_user_prompt))

                # Get CDP session for JavaScript execution
                cdp_session = await browser_session.get_or_create_cdp_session()

                # Iterative code generation and execution
                for iteration in range(1, MAX_ITERATIONS + 1):
                    try:
                        logger.info(f'🔄 Skill Code iteration {iteration}/{MAX_ITERATIONS}')

                        # Generate JavaScript code using LLM with message history
                        response = await asyncio.wait_for(
                            page_extraction_llm.ainvoke(message_history),
                            timeout=60.0,
                        )

                        generated_js_code = response.completion.strip()
                        message_history.append(AssistantMessage(content=generated_js_code))

                        # Clean up the generated code (remove markdown if present)
                        if generated_js_code.startswith('```javascript'):
                            generated_js_code = generated_js_code.replace('```javascript', '').replace('```',
                                                                                                       '').strip()
                        elif generated_js_code.startswith('```js'):
                            generated_js_code = generated_js_code.replace('```js', '').replace('```', '').strip()
                        elif generated_js_code.startswith('```'):
                            generated_js_code = generated_js_code.replace('```', '').strip()

                        # Execute the generated JavaScript code
                        try:
                            logger.info(generated_js_code)
                            # Always use awaitPromise=True - it's ignored for non-promises
                            result = await cdp_session.cdp_client.send.Runtime.evaluate(
                                params={'expression': generated_js_code, 'returnByValue': True, 'awaitPromise': True},
                                session_id=cdp_session.session_id,
                            )

                            logger.info(result)
                            # Check for JavaScript execution errors
                            if result.get('exceptionDetails'):
                                exception = result['exceptionDetails']
                                error_msg = f'JavaScript execution error: {exception.get("text", "Unknown error")}'
                                if 'lineNumber' in exception:
                                    error_msg += f' at line {exception["lineNumber"]}'

                                # Add error feedback to message history for next iteration
                                if iteration < MAX_ITERATIONS:
                                    error_feedback = f"""The previous JavaScript code failed with error:
{error_msg}

Please fix the error and generate corrected JavaScript code:"""
                                    message_history.append(UserMessage(content=error_feedback))
                                    continue  # Try next iteration
                                else:
                                    # Final iteration, return error
                                    msg = f'Requirement: {params.code_requirement}\n\nFinal Generated Code (Iteration {iteration}): {generated_js_code}\n\nError: {error_msg}'
                                    logger.info(msg)
                                    return ActionResult(error=msg)

                            # Get the result data
                            result_data = result.get('result', {})

                            # Check for wasThrown flag (backup error detection)
                            if result_data.get('wasThrown'):
                                error_msg = 'JavaScript execution failed (wasThrown=true)'

                                # Add error feedback to message history for next iteration
                                if iteration < MAX_ITERATIONS:
                                    error_feedback = f"""The previous JavaScript code failed with error:
{error_msg}

Please fix the error and generate corrected JavaScript code:"""
                                    message_history.append(UserMessage(content=error_feedback))
                                    continue  # Try next iteration
                                else:
                                    # Final iteration, return error
                                    msg = f'Requirement: {params.code_requirement}\n\nFinal Generated Code (Iteration {iteration}): {generated_js_code}\n\nError: {error_msg}'
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
                                    result_text = json.dumps(value, ensure_ascii=False, indent=2)
                                except (TypeError, ValueError):
                                    # Fallback for non-serializable objects
                                    result_text = str(value)
                            else:
                                # Primitive values (string, number, boolean)
                                result_text = str(value)

                            # Check if result is empty or meaningless
                            if (not result_text or
                                    result_text.strip() in ['', 'null', 'undefined', '[]', '{}'] or
                                    len(result_text.strip()) == 0):

                                # Add empty result feedback to message history for next iteration
                                if iteration < MAX_ITERATIONS:
                                    empty_feedback = f"""The previous JavaScript code executed successfully but returned empty/meaningless result:
Result: {result_text}

The result is empty or not useful. Please generate improved JavaScript code that returns meaningful data:"""
                                    message_history.append(UserMessage(content=empty_feedback))
                                    continue  # Try next iteration
                                else:
                                    # Final iteration, return empty result with warning
                                    msg = f'Requirement: {params.code_requirement}\n\nFinal Generated Code (Iteration {iteration}): {generated_js_code}\n\nWarning: Empty or meaningless result: {result_text}'
                                    logger.info(msg)
                                    return ActionResult(
                                        extracted_content=msg,
                                        long_term_memory=f'Generated JavaScript code (iteration {iteration}) for requirement: {params.code_requirement} - Empty result warning',
                                    )

                            # Apply length limit with better truncation
                            if len(result_text) > 30000:
                                result_text = result_text[:30000] + '\n... [Truncated after 30000 characters]'

                            # Success! Return the result
                            msg = f'Generated Code (Iteration {iteration}): \n```javascript\n{generated_js_code}\n```\nResult:\n```json\n {result_text}\n```\n'
                            logger.info(f'✅ Skill Code succeeded on iteration {iteration}')

                            return ActionResult(
                                extracted_content=msg,
                                long_term_memory=f'Generated and executed JavaScript code (iteration {iteration}) for requirement: {params.code_requirement}',
                            )

                        except Exception as e:
                            # CDP communication or other system errors
                            error_msg = f'Failed to execute JavaScript: {type(e).__name__}: {e}'

                            # Add system error feedback to message history for next iteration
                            if iteration < MAX_ITERATIONS:
                                system_error_feedback = f"""The previous JavaScript code failed to execute due to system error:
{error_msg}

Please generate alternative JavaScript code that avoids this system error:"""
                                message_history.append(UserMessage(content=system_error_feedback))
                                continue  # Try next iteration
                            else:
                                # Final iteration, return system error
                                error_msg = f'Requirement: {params.code_requirement}\n\nFinal Generated Code (Iteration {iteration}): {generated_js_code}\n\nError: {error_msg}'
                                logger.info(error_msg)
                                return ActionResult(error=error_msg)

                    except Exception as e:
                        # LLM generation error
                        logger.error(f'❌ LLM generation failed on iteration {iteration}: {e}')
                        if iteration == MAX_ITERATIONS:
                            return ActionResult(
                                error=f'LLM generation failed after {MAX_ITERATIONS} iterations: {str(e)}')
                        continue  # Try next iteration with same message history

                # Should not reach here, but just in case
                return ActionResult(error=f'Skill code failed after {MAX_ITERATIONS} iterations')

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

        @self.registry.action(
            'Skill: Get comprehensive financial data for stocks - retrieve company information, historical prices, news, earnings, dividends, analyst recommendations and other financial data using Yahoo Finance. Available methods include: get_info (company info), get_history (price history), get_news (latest news), get_dividends (dividend history), get_earnings (earnings data), get_recommendations (analyst recommendations), get_balance_sheet (balance sheet data), get_income_stmt (income statement), get_cashflow (cash flow statement), get_fast_info (quick stats), get_institutional_holders (institutional ownership), get_major_holders (major shareholders), get_sustainability (ESG data), get_upgrades_downgrades (analyst upgrades/downgrades), and more. If no methods specified, defaults to get_info.',
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
                return ActionResult(error=error_msg)


    async def _extract_google_results_rule_based(self, browser_session):
        """Rule-based extraction of Google search results using JavaScript"""
        try:
            cdp_session = await browser_session.get_or_create_cdp_session()
            
            # JavaScript code to extract Google search results using DOM selectors
            js_extraction_code = """
(function() {
    try {
        const results = [];
        
        // Multiple selector strategies for different Google layouts
        const selectors = [
            'div[data-sokoban-container] div[data-sokoban-feature]', // Standard results
            'div.g:not(.g-blk)', // Classic results container
            '.tF2Cxc', // Modern result container
            'div[data-ved] h3', // Result titles
        ];
        
        let resultElements = [];
        
        // Try each selector until we find results
        for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            if (elements.length > 0) {
                resultElements = Array.from(elements).slice(0, 10); // Get up to 10 results
                break;
            }
        }
        
        // If no results found with specific selectors, try broader search
        if (resultElements.length === 0) {
            // Look for any divs containing h3 elements (likely search results)
            const h3Elements = document.querySelectorAll('h3');
            resultElements = Array.from(h3Elements)
                .map(h3 => h3.closest('div'))
                .filter(div => div && div.querySelector('a[href]'))
                .slice(0, 10);
        }
        
        for (let i = 0; i < Math.min(resultElements.length, 10); i++) {
            const element = resultElements[i];
            
            // Extract title
            let title = '';
            const titleSelectors = ['h3', '[role="heading"]', 'a > span', '.LC20lb'];
            for (const sel of titleSelectors) {
                const titleEl = element.querySelector(sel);
                if (titleEl && titleEl.textContent.trim()) {
                    title = titleEl.textContent.trim();
                    break;
                }
            }
            
            // Extract URL
            let url = '';
            const linkSelectors = ['a[href^="http"]', 'a[href^="/url?q="]', 'a[href]'];
            for (const sel of linkSelectors) {
                const linkEl = element.querySelector(sel);
                if (linkEl && linkEl.href) {
                    url = linkEl.href;
                    // Clean Google redirect URLs
                    if (url.includes('/url?q=')) {
                        const urlMatch = url.match(/[?&]q=([^&]*)/);
                        if (urlMatch) {
                            url = decodeURIComponent(urlMatch[1]);
                        }
                    }
                    break;
                }
            }
            
            // Extract summary/description
            let summary = '';
            const summarySelectors = [
                '.VwiC3b', // Description text
                '.yXK7lf', // Snippet text
                '[data-content-feature="1"] span',
                '.s', // Classic description
                'span:not(:has(a))'
            ];
            for (const sel of summarySelectors) {
                const summaryEl = element.querySelector(sel);
                if (summaryEl && summaryEl.textContent.trim() && summaryEl.textContent.length > 10) {
                    summary = summaryEl.textContent.trim();
                    break;
                }
            }
            
            // Only add if we have at least title or URL
            if (title || url) {
                results.push({
                    title: title || 'No title',
                    url: url || 'No URL',
                    summary: summary || 'No description available'
                });
            }
        }
        
        return JSON.stringify(results);
        
    } catch (e) {
        return JSON.stringify([{
            title: 'Error extracting results',
            url: window.location.href,
            summary: 'JavaScript extraction failed: ' + e.message
        }]);
    }
})()
"""
            
            # Execute JavaScript to extract results
            result = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={'expression': js_extraction_code, 'returnByValue': True, 'awaitPromise': True},
                session_id=cdp_session.session_id,
            )
            
            if result.get('exceptionDetails'):
                logger.warning(f"JavaScript extraction failed: {result['exceptionDetails']}")
                return []
            
            result_data = result.get('result', {})
            value = result_data.get('value', '[]')
            
            try:
                extracted_results = json.loads(value)
                return extracted_results if isinstance(extracted_results, list) else []
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"Failed to parse extraction results: {value}")
                return []
                
        except Exception as e:
            logger.error(f"Rule-based extraction failed: {e}")
            return []

    async def _perform_google_search(self, browser_session, query: str, llm: BaseChatModel):
        """Helper method to perform Google search and extract top 5 results using rule-based extraction"""
        try:
            # Navigate to Google search
            search_url = f'https://www.google.com/search?q={query}&udm=14'
            await browser_session.navigate_to_url(search_url, new_tab=False)

            # Wait a moment for page to load
            await asyncio.sleep(2)

            # Use rule-based extraction first (much faster than LLM)
            search_ret_len = 10
            results = await self._extract_google_results_rule_based(browser_session)
            if results and len(results) > 0:
                # Rule-based extraction succeeded
                logger.info(f"Rule-based extraction found {len(results)} results for query: {query}")
                return results[:search_ret_len]  # Return top 6 results
            
            # Fallback to LLM extraction if rule-based fails
            logger.warning(f"Rule-based extraction failed for query '{query}', falling back to LLM")
            
            extraction_query = f"""
Extract the top {search_ret_len} search results from this Google search page. For each result, provide:
- title: The clickable title/headline
- url: The website URL
- summary: A brief description of what this result contains

Return results as a JSON array: [{{"title": "...", "url": "...", "summary": "..."}}, ...]
"""

            results_text = await self._extract_structured_content(browser_session, extraction_query, llm)

            # Try to parse JSON results
            try:
                results = json.loads(results_text.strip())
                if isinstance(results, list):
                    return results[:search_ret_len]  # Ensure max 5 results
            except (json.JSONDecodeError, ValueError):
                try:
                    results = repair_json(results_text.strip())
                    if isinstance(results, list):
                        return results[:search_ret_len]  # Ensure max 5 results
                except Exception as e:
                    logger.warning(f"Failed to parse JSON from LLM search results: {results_text}")

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

    def _rule_based_deduplication(self, results):
        """Rule-based deduplication to reduce dataset before LLM processing"""
        if not results:
            return []
        
        deduplicated = []
        seen_urls = set()
        seen_titles = set()
        
        for result in results:
            url = result.get('url', '').strip()
            title = result.get('title', '').strip().lower()
            
            # Skip results with missing essential data
            if not url or not title or url == 'No URL' or title == 'no title':
                continue
            
            # Normalize URL for comparison (remove fragments, query params for deduplication)
            normalized_url = url.split('#')[0].split('?')[0].lower()
            
            # Check for duplicate URLs
            if normalized_url in seen_urls:
                continue
            
            # Check for very similar titles (basic similarity)
            title_normalized = ''.join(c for c in title if c.isalnum()).lower()
            if len(title_normalized) > 10:  # Only check titles with substantial content
                similar_found = False
                for seen_title in seen_titles:
                    # Simple similarity check: if 80% of characters match
                    if len(title_normalized) > 0 and len(seen_title) > 0:
                        common_chars = sum(1 for c in title_normalized if c in seen_title)
                        similarity = common_chars / max(len(title_normalized), len(seen_title))
                        if similarity > 0.8:
                            similar_found = True
                            break
                
                if similar_found:
                    continue
            
            # Add to deduplicated results
            seen_urls.add(normalized_url)
            seen_titles.add(title_normalized)
            deduplicated.append(result)
        
        # Sort by relevance indicators (prioritize results with longer summaries, non-generic titles)
        def relevance_score(result):
            score = 0
            title = result.get('title', '')
            summary = result.get('summary', '')
            
            # Longer summaries are typically more informative
            score += min(len(summary), 200) / 10
            
            # Non-generic titles score higher
            generic_terms = ['search results', 'no title', 'error', 'loading']
            if not any(term in title.lower() for term in generic_terms):
                score += 10
            
            # Prefer results with actual descriptions
            if summary and summary != 'No description available' and len(summary) > 20:
                score += 5
                
            return score
        
        deduplicated.sort(key=relevance_score, reverse=True)
        return deduplicated

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
