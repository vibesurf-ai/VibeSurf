import pdb

from bs4 import BeautifulSoup
import asyncio
import json
import os
import base64
import mimetypes

from browser_use.dom.service import EnhancedDOMTreeNode
from vibe_surf.logger import get_logger
from browser_use.llm.messages import SystemMessage, UserMessage, AssistantMessage, ContentPartTextParam, ContentPartImageParam, ImageURL
from browser_use.llm.base import BaseChatModel

logger = get_logger(__name__)


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


async def generate_java_script_code(code_requirement, llm, browser_session, MAX_ITERATIONS=5):
    page_html_content = await browser_session.get_html_content()
    web_page_html = clean_html_basic(page_html_content)

    max_html_len = 60000
    if len(web_page_html) > max_html_len:
        gap_len = (len(web_page_html) - max_html_len) // 2
        clip_len = max_html_len // 3
        web_page_html = (web_page_html[:clip_len] + "\n\n...\n\n" +
                         web_page_html[
                         clip_len + gap_len: clip_len + gap_len + clip_len + 10000] + "\n\n...\n\n" +
                         web_page_html[
                         clip_len + gap_len * 2 + clip_len: clip_len + gap_len * 2 + 2 * clip_len - 10000])

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
    message_history = [SystemMessage(content=base_system_prompt)]

    # Initial user prompt
    initial_user_prompt = f"""Current Page URL: {current_url}

    USER REQUIREMENT: {code_requirement}

    Web Page Content:
    {web_page_html}

    Generate JavaScript code to fulfill the requirement:"""

    message_history.append(UserMessage(content=initial_user_prompt))

    # Get CDP session for JavaScript execution
    cdp_session = await browser_session.get_or_create_cdp_session()
    gen_success = True
    generated_js_code = ""
    execute_result = ""

    # Iterative code generation and execution
    for iteration in range(1, MAX_ITERATIONS + 1):
        try:
            logger.info(f'🔄 Skill Code iteration {iteration}/{MAX_ITERATIONS}')

            # Generate JavaScript code using LLM with message history
            response = await asyncio.wait_for(
                llm.ainvoke(message_history),
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
                logger.debug(generated_js_code)
                # Always use awaitPromise=True - it's ignored for non-promises
                result = await cdp_session.cdp_client.send.Runtime.evaluate(
                    params={'expression': generated_js_code, 'returnByValue': True, 'awaitPromise': True},
                    session_id=cdp_session.session_id,
                )
                execute_result = str(result)
                logger.debug(result)
                # Check for JavaScript execution errors
                if result.get('exceptionDetails'):
                    exception = result['exceptionDetails']
                    error_msg = f'JavaScript execution error: {exception.get("text", "Unknown error")}'
                    if 'lineNumber' in exception:
                        error_msg += f' at line {exception["lineNumber"]}'

                    error_feedback = f"""The previous JavaScript code failed with error:
                        {error_msg}

                        Please fix the error and generate corrected JavaScript code:"""
                    message_history.append(UserMessage(content=error_feedback))
                    continue

                # Get the result data
                result_data = result.get('result', {})

                # Check for wasThrown flag (backup error detection)
                if result_data.get('wasThrown'):
                    error_msg = 'JavaScript execution failed (wasThrown=true)'

                    error_feedback = f"""The previous JavaScript code failed with error:
                        {error_msg}

                        Please fix the error and generate corrected JavaScript code:"""
                    message_history.append(UserMessage(content=error_feedback))
                    continue  # Try next iteration

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
                    empty_feedback = f"""The previous JavaScript code executed successfully but returned empty/meaningless result:
                        Result: {result_text}

                        The result is empty or not useful. Please generate improved JavaScript code that returns meaningful data:"""
                    message_history.append(UserMessage(content=empty_feedback))
                    continue  # Try next iteration

                # Apply length limit with better truncation
                if len(result_text) > 30000:
                    result_text = result_text[:30000] + '\n... [Truncated after 30000 characters]'

                # Success! Return the result
                msg = f'Generated Code (Iteration {iteration}): \n```javascript\n{generated_js_code}\n```\nResult:\n```json\n {result_text}\n```\n'
                logger.info(f'✅ Skill Code succeeded on iteration {iteration}')
                logger.debug(msg)
                execute_result = result_text
                break

            except Exception as e:
                # CDP communication or other system errors
                error_msg = f'Failed to execute JavaScript: {type(e).__name__}: {e}'

                # Add system error feedback to message history for next iteration
                system_error_feedback = f"""The previous JavaScript code failed to execute due to system error:
                    {error_msg}

                    Please generate alternative JavaScript code that avoids this system error:"""
                message_history.append(UserMessage(content=system_error_feedback))
                continue  # Try next iteration

        except Exception as e:
            logger.error(f'❌ LLM generation failed on iteration {iteration}: {e}')
            continue

    else:
        gen_success = False

    return gen_success, execute_result, generated_js_code


async def google_ai_model_search(browser_manager, query: str, max_results: int = 100):
    """
    Google AI model Search
    """
    agent_id = "ai_search_agent"
    try:
        browser_session = await browser_manager.register_agent(agent_id, target_id=None)

        # Navigate to Google AI model search with udm=50
        search_url = f'https://www.google.com/search?q={query}&udm=50'
        await browser_session.navigate_to_url(search_url, new_tab=False)

        # Wait for page to load
        await asyncio.sleep(2)

        # Try to click "显示更多" button
        try:
            cdp_session = await browser_session.get_or_create_cdp_session()

            # JavaScript to click the "显示更多" button with retry logic
            click_more_js = """
(async function() {
    try {
        // Retry logic: attempt 3 times with delays
        for (let attempt = 1; attempt <= 5; attempt++) {
            // Wait before each attempt (longer wait for first attempt)
            await new Promise(resolve => setTimeout(resolve, attempt === 1 ? 1500 : 800));
            
            let clicked = false;
            
            // Search for button by text content (more reliable than complex selectors)
            const textPatterns = [
                '全部显示',
                '显示所有相关链接',
                '显示更多',
                'Show more',
                'More',
                'Show all'
            ];
            
            // Find all potential button elements
            const potentialButtons = document.querySelectorAll([
                'div[role="button"]',
                'button',
                'div[jsaction*="click"]',
                '[aria-label*="显示"]',
                '[aria-label*="Show"]',
                '.BjvG9b',
                'div[tabindex="0"]'
            ].join(', '));
            
            // Check each potential button for matching text
            for (const element of potentialButtons) {
                if (!element) continue;
                
                const elementText = element.textContent || '';
                const ariaLabel = element.getAttribute('aria-label') || '';
                
                // Check if element contains any of our target text patterns (case-insensitive for English)
                const hasMatchingText = textPatterns.some(pattern => {
                    const lowerPattern = pattern.toLowerCase();
                    const lowerElementText = elementText.toLowerCase();
                    const lowerAriaLabel = ariaLabel.toLowerCase();
                    
                    return lowerElementText.includes(lowerPattern) || lowerAriaLabel.includes(lowerPattern);
                });
                
                if (hasMatchingText) {
                    try {
                        // Try clicking the element
                        element.click();
                        clicked = true;
                        
                        // Wait a moment to see if click worked
                        await new Promise(resolve => setTimeout(resolve, 500));
                        
                        return `Successfully clicked show more button on attempt ${attempt}. Text: "${elementText}", Aria-label: "${ariaLabel}"`;
                    } catch (clickError) {
                        console.log(`Click failed on attempt ${attempt}:`, clickError);
                        continue;
                    }
                }
            }
            
            if (!clicked && attempt < 5) {
                console.log(`Attempt ${attempt}: Show more button not found, retrying...`);
                continue;
            }
            
            if (clicked) break;
        }
        
        return 'Show more button not found after 3 attempts';
    } catch (e) {
        return 'Error: ' + e.message;
    }
})()
"""

            result = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={'expression': click_more_js, 'returnByValue': True, 'awaitPromise': True},
                session_id=cdp_session.session_id,
            )

            logger.info(f"Click result: {result.get('result', {}).get('value', 'No result')}")

        except Exception as e:
            logger.warning(f"Failed to click show more button: {e}")

        # Wait a bit more for content to load after clicking
        await asyncio.sleep(1)

        # Extract news list using JavaScript
        extraction_js = """
(function() {
    try {
        const results = [];
        
        // Try to find news list container
        const listSelectors = [
            'ul.bTFeG[data-processed="true"][data-complete="true"]',
            'ul.bTFeG',
            '.bTFeG',
            'li.CyMdWb'
        ];
        
        let newsItems = [];
        
        // Try to find news items directly
        for (const selector of listSelectors) {
            const container = document.querySelector(selector);
            if (container) {
                newsItems = Array.from(container.querySelectorAll('li.CyMdWb, li[data-processed="true"]'));
                if (newsItems.length > 0) break;
            }
        }
        
        // If no news items found in container, try direct search
        if (newsItems.length === 0) {
            newsItems = Array.from(document.querySelectorAll('li.CyMdWb, .MFrAxb, [data-src-id]'));
        }
        
        // Extract information from each news item
        for (let i = 0; i < Math.min(newsItems.length, 20); i++) {
            const item = newsItems[i];
            
            // Extract title
            let title = '';
            const titleSelectors = ['.Nn35F', 'h3', '.LC20lb', '[role="heading"]'];
            for (const sel of titleSelectors) {
                const titleEl = item.querySelector(sel);
                if (titleEl && titleEl.textContent.trim()) {
                    title = titleEl.textContent.trim();
                    break;
                }
            }
            
            // Extract URL
            let url = '';
            const linkEl = item.querySelector('a[href]');
            if (linkEl && linkEl.href) {
                url = linkEl.href;
                // Clean Google redirect URLs
                if (url.includes('/url?q=')) {
                    const urlMatch = url.match(/[?&]q=([^&]*)/);
                    if (urlMatch) {
                        url = decodeURIComponent(urlMatch[1]);
                    }
                }
            }
            
            // Extract summary/description
            let summary = '';
            const summarySelectors = ['.vhJ6Pe', '.VwiC3b', '.yXK7lf', '.s'];
            for (const sel of summarySelectors) {
                const summaryEl = item.querySelector(sel);
                if (summaryEl && summaryEl.textContent.trim() && summaryEl.textContent.length > 10) {
                    summary = summaryEl.textContent.trim();
                    break;
                }
            }
            
            // Extract source
            let source = '';
            const sourceSelectors = ['.R0r5R span', '.jEYmO span', 'span.R0r5R'];
            for (const sel of sourceSelectors) {
                const sourceEl = item.querySelector(sel);
                if (sourceEl && sourceEl.textContent.trim()) {
                    source = sourceEl.textContent.trim();
                    break;
                }
            }
            
            // Only add if we have meaningful data
            if (title || url) {
                results.push({
                    title: title || 'No title',
                    url: url || 'No URL',
                    summary: summary || 'No description available',
                    source: source || 'Unknown source'
                });
            }
        }
        
        return JSON.stringify(results);
        
    } catch (e) {
        return JSON.stringify([{
            title: 'Error extracting results',
            url: window.location.href,
            summary: 'JavaScript extraction failed: ' + e.message,
            source: 'Error'
        }]);
    }
})()
"""

        # Execute extraction JavaScript
        cdp_session = await browser_session.get_or_create_cdp_session()
        result = await cdp_session.cdp_client.send.Runtime.evaluate(
            params={'expression': extraction_js, 'returnByValue': True, 'awaitPromise': True},
            session_id=cdp_session.session_id,
        )

        if result.get('exceptionDetails'):
            logger.warning(f"JavaScript extraction failed: {result['exceptionDetails']}")
            return []

        result_data = result.get('result', {})
        value = result_data.get('value', '[]')

        try:
            extracted_results = json.loads(value)
            return extracted_results[:max_results] if isinstance(extracted_results, list) else []
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse extraction results: {value}")
            return []

    except Exception as e:
        logger.error(f"Google AI model search failed for query '{query}': {e}")
        return []

    finally:
        try:
            await browser_manager.unregister_agent(agent_id, close_tabs=True)
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup agent {agent_id}: {cleanup_error}")


async def fallback_parallel_search(browser_manager, query: str, max_results: int = 100):
    """
    Fallback method: Parallel search across all, news, and videos tabs using separate browser sessions
    """
    agent_ids = []
    try:
        # Define search URLs for different tabs
        search_urls = {
            'all': f'https://www.google.com/search?q={query}&udm=14',
            'news': f'https://www.google.com/search?q={query}&tbm=nws',
            'videos': f'https://www.google.com/search?q={query}&tbm=vid'
        }

        # Step 1: Create browser sessions for parallel searching
        register_sessions = []

        for tab_name in search_urls.keys():
            agent_id = f"fallback_search_{tab_name}"
            register_sessions.append(
                browser_manager.register_agent(agent_id, target_id=None)
            )
            agent_ids.append(agent_id)

        # Wait for all browser sessions to be created
        browser_sessions = await asyncio.gather(*register_sessions)

        # Step 2: Create parallel search tasks
        search_tasks = []
        for (tab_name, search_url), browser_session in zip(search_urls.items(), browser_sessions):
            search_tasks.append(
                _perform_tab_search(browser_session, search_url, tab_name, query)
            )

        # Step 3: Execute all searches in parallel
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Step 4: Aggregate results from all tabs
        all_results = []
        for i, result in enumerate(search_results):
            tab_name = list(search_urls.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"Search task for {tab_name} tab failed: {result}")
                continue
            if result:
                all_results.extend(result)

        # Step 5: Remove duplicates based on URL
        unique_results = []
        seen_urls = set()

        for result in all_results:
            url = result.get('url', '')
            if url and url not in seen_urls and url != 'No URL':
                seen_urls.add(url)
                unique_results.append(result)

        return unique_results[:max_results]

    except Exception as e:
        logger.error(f"Fallback parallel search failed for query '{query}': {e}")
        return []
    finally:
        # Clean up browser sessions
        for agent_id in agent_ids:
            try:
                await browser_manager.unregister_agent(agent_id, close_tabs=True)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup agent {agent_id}: {cleanup_error}")


def _generate_video_extraction_js() -> str:
    """Generate JavaScript code for robust video search extraction"""
    js_code = r"""
(function(){
  try {
    const results = [];
    let extractionMethod = 'unknown';
    
    // Video platform domains to look for
    const videoDomains = [
      'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
      'twitch.tv', 'tiktok.com', 'bilibili.com', 'niconico.jp'
    ];
    
    // Non-video domains to exclude
    const excludeDomains = [
      'maps.google.com', 'google.com/search', 'google.com/travel',
      'google.com/finance', 'google.com/shopping', 'google.com/books'
    ];
    
    // Strategy 1: Look for actual video containers with video elements
    let containers = document.querySelectorAll('div[data-hveid]:has(video), div[data-hveid]:has(img[src*="ytimg"]), div[jscontroller*="rTuANe"]');
    if (containers.length > 0) {
      extractionMethod = 'video_elements';
      console.log('Strategy 1 - Video elements found:', containers.length);
    }
    
    // Strategy 2: Look for YouTube/video platform specific links
    if (containers.length === 0) {
      const videoSelectors = videoDomains.map(domain =>
        `div[data-hveid]:has(a[href*="${domain}"])`
      ).join(', ');
      containers = document.querySelectorAll(videoSelectors);
      if (containers.length > 0) {
        extractionMethod = 'video_platform_links';
        console.log('Strategy 2 - Video platform links:', containers.length);
      }
    }
    
    // Strategy 3: Look for containers with duration indicators
    if (containers.length === 0) {
      containers = document.querySelectorAll('div[data-hveid]:has(.kSFuOd), div[data-hveid]:has(.c8rnLc), div[data-hveid]:has([class*="duration"])');
      if (containers.length > 0) {
        extractionMethod = 'duration_indicators';
        console.log('Strategy 3 - Duration indicators:', containers.length);
      }
    }
    
    console.log('Using extraction method:', extractionMethod, 'with', containers.length, 'containers');
    
    // Helper function to check if URL is a video URL
    function isVideoUrl(url) {
      if (!url) return false;
      
      // Check if URL contains video platform domains
      const hasVideoDomain = videoDomains.some(domain => url.includes(domain));
      
      // Check if URL contains excluded domains
      const hasExcludedDomain = excludeDomains.some(domain => url.includes(domain));
      
      // Check for video-specific URL patterns
      const hasVideoPattern = /\/(watch|video|v)[\?\/]/.test(url) || url.includes('watch?v=');
      
      return hasVideoDomain || (hasVideoPattern && !hasExcludedDomain);
    }
    
    // Helper function to check if container has video indicators
    function hasVideoIndicators(container) {
      // Check for video elements
      if (container.querySelector('video')) return true;
      
      // Check for YouTube thumbnail patterns
      if (container.querySelector('img[src*="ytimg"]')) return true;
      if (container.querySelector('img[src*="encrypted-tbn"]')) return true;
      
      // Check for duration indicators
      const durationElements = container.querySelectorAll('span, div');
      for (const el of durationElements) {
        if (el.textContent && /\\d+:\\d+/.test(el.textContent.trim())) {
          return true;
        }
      }
      
      // Check for video-specific classes
      if (container.querySelector('.DqfBw, .kSFuOd, .c8rnLc, [class*="video"], [class*="duration"]')) {
        return true;
      }
      
      return false;
    }
    
    console.log('Using extraction method:', extractionMethod, 'with', containers.length, 'containers');
    
    for (let i = 0; i < containers.length && results.length < 10; i++) {
      const container = containers[i];
      console.log('Processing video container', i + 1, '/', containers.length);
      
      // Extract URL first to validate if it's a video
      let url = '';
      const linkSelectors = [
        'a[href*="youtube.com/watch"]', 'a[href*="youtu.be"]',
        'a[href*="vimeo.com"]', 'a[href*="bilibili.com"]',
        'a[data-curl]', 'a[href*="video"]', 'a[href]'
      ];
      
      for (const sel of linkSelectors) {
        const linkEl = container.querySelector(sel);
        if (linkEl && linkEl.href) {
          url = linkEl.href;
          // Clean Google redirect URLs
          if (url.includes('/url?q=')) {
            const urlMatch = url.match(/[?&]q=([^&]*)/);
            if (urlMatch) {
              url = decodeURIComponent(urlMatch[1]);
            }
          }
          console.log('Found URL with selector:', sel);
          break;
        }
      }
      
      // Skip if URL is not a video URL
      if (!isVideoUrl(url)) {
        console.log('Skipping non-video URL:', url.substring(0, 50));
        continue;
      }
      
      // Skip if container doesn't have video indicators
      if (!hasVideoIndicators(container)) {
        console.log('Skipping container without video indicators');
        continue;
      }
      
      // Extract title with multiple strategies
      let title = '';
      const titleSelectors = [
        'h3.LC20lb', 'h3.MBeuO', 'h3.DKV0Md', 'h3',
        '[role="heading"]', '.LC20lb', '.DKV0Md'
      ];
      
      for (const sel of titleSelectors) {
        const titleEl = container.querySelector(sel);
        if (titleEl && titleEl.textContent && titleEl.textContent.trim()) {
          title = titleEl.textContent.trim();
          console.log('Found title with selector:', sel);
          break;
        }
      }
      
      // Extract duration
      let duration = '';
      const durationSelectors = [
        '.c8rnLc span', '.kSFuOd span', '[class*="duration"]',
        '.zKugA span', '.kSFuOd', '.c8rnLc'
      ];
      
      for (const sel of durationSelectors) {
        const durationEl = container.querySelector(sel);
        if (durationEl && durationEl.textContent) {
          const durationText = durationEl.textContent.trim();
          if (/\\d+:\\d+/.test(durationText)) {
            duration = durationText;
            console.log('Found duration with selector:', sel);
            break;
          }
        }
      }
      
      // Fallback: search all spans for duration pattern
      if (!duration) {
        const allSpans = container.querySelectorAll('span');
        for (const span of allSpans) {
          if (span.textContent && /\\d+:\\d+/.test(span.textContent.trim())) {
            duration = span.textContent.trim();
            console.log('Found duration in span fallback:', duration);
            break;
          }
        }
      }
      
      // Extract source/channel
      let source = '';
      const sourceSelectors = [
        '.gqF9jc span', '.ApHyTb span', 'cite', '.qLRx3b',
        '.notranslate span', '[role="text"]'
      ];
      
      for (const sel of sourceSelectors) {
        const sourceEl = container.querySelector(sel);
        if (sourceEl && sourceEl.textContent && sourceEl.textContent.trim()) {
          const sourceText = sourceEl.textContent.trim();
          if (sourceText && sourceText.length > 2 && !sourceText.includes('›')) {
            source = sourceText;
            console.log('Found source with selector:', sel);
            break;
          }
        }
      }
      
      // Extract description/summary
      let summary = '';
      const summarySelectors = [
        '.ITZIwc', '.fzUZNc div', '.VwiC3b', '.yXK7lf'
      ];
      
      for (const sel of summarySelectors) {
        const summaryEl = container.querySelector(sel);
        if (summaryEl && summaryEl.textContent) {
          const summaryText = summaryEl.textContent.trim();
          if (summaryText && summaryText.length > 10 && summaryText.length < 500) {
            summary = summaryText;
            console.log('Found summary with selector:', sel);
            break;
          }
        }
      }
      
      // Only add if we have meaningful data (at least title OR url)
      if (title || url) {
        console.log('Adding video result:', {
          title: title.substring(0, 50),
          url: url.substring(0, 50),
          source: source,
          duration: duration
        });
        
        results.push({
          title: title || 'No title',
          url: url || 'No URL',
          summary: summary || 'No description available',
          source: source || 'Unknown source',
          duration: duration || '',
          source_tab: 'videos',
          extraction_method: extractionMethod
        });
      } else {
        console.log('Skipped container - no title and no URL found');
      }
    }
    
    console.log('Extracted', results.length, 'video results using', extractionMethod);
    return JSON.stringify(results);
    
  } catch(e) {
    console.error('Video extraction error:', e);
    return JSON.stringify([{
      title: 'Error extracting video results',
      url: window.location.href,
      summary: 'JavaScript extraction failed: ' + e.message,
      source_tab: 'videos',
      error: e.toString()
    }]);
  }
})()"""

    return js_code

def _generate_news_extraction_js() -> str:
    """Generate JavaScript code for news search extraction"""
    return """
(function () {
    try {
        const results = [];
        let extractionMethod = 'unknown';
        
        // Strategy 1: Enhanced news selector strategy with CB data-hveid
        let containers = document.querySelectorAll('div[data-hveid*="CB"]');
        console.log(`Strategy 1 - CB containers: ${containers.length}`);
        
        // Strategy 2: General news containers
        if (containers.length === 0) {
            containers = document.querySelectorAll('div[data-hveid]:has(.WlydOe), .SoaBEf, .MjjYud');
            extractionMethod = 'general_news';
            console.log(`Strategy 2 - General news containers: ${containers.length}`);
        } else {
            extractionMethod = 'cb_hveid';
        }
        
        // Strategy 3: Fallback to any div with news-like content
        if (containers.length === 0) {
            containers = document.querySelectorAll('.g, .tF2Cxc, div:has(h3):has(a[href])');
            extractionMethod = 'broad_fallback';
            console.log(`Strategy 3 - Broad fallback: ${containers.length}`);
        }
        
        // Strategy 4: Final fallback - search by text patterns
        if (containers.length === 0) {
            const allDivs = document.querySelectorAll('div');
            containers = Array.from(allDivs).filter(div => {
                const text = div.textContent || '';
                const hasTimePattern = /\\d+\\s*(hours?|mins?|days?|ago|前|小时|分钟|天)/.test(text);
                const hasLink = div.querySelector('a[href]');
                const hasHeading = div.querySelector('h3, [role="heading"]');
                return hasTimePattern && hasLink && hasHeading;
            });
            extractionMethod = 'pattern_based';
            console.log(`Strategy 4 - Pattern-based fallback: ${containers.length}`);
        }
        
        console.log(`Using extraction method: ${extractionMethod} with ${containers.length} containers`);
        
        for (let i = 0; i < containers.length && results.length < 10; i++) {
            const item = containers[i];
            console.log(`Processing news container ${i + 1}/${containers.length}`);
            
            // Multiple strategies for different news layouts with debugging
            let linkEl = item.querySelector('a.WlydOe') ||
                        item.querySelector('a[href*="news"]') ||
                        item.querySelector('a[href]');
                        
            let titleEl = item.querySelector('[role="heading"]') ||
                         item.querySelector('h3') ||
                         item.querySelector('.LC20lb') ||
                         item.querySelector('.DKV0Md');
            
            console.log(`News container ${i + 1}: found link=${!!linkEl}, found title=${!!titleEl}`);
            
            // Enhanced link finding for news
            if (!linkEl) {
                const linkSelectors = ['a[href*="http"]', 'a[href^="/url"]', 'a'];
                for (const sel of linkSelectors) {
                    const links = item.querySelectorAll(sel);
                    for (const link of links) {
                        if (link.href && !link.href.includes('google.com/search')) {
                            linkEl = link;
                            console.log(`News container ${i + 1}: found link with selector "${sel}"`);
                            break;
                        }
                    }
                    if (linkEl) break;
                }
            }
            
            // Enhanced title finding for news
            if (!titleEl) {
                const titleSelectors = ['.BNeawe', '.LC20lb', 'h1', 'h2', 'h3', 'h4', '[data-hveid] h3'];
                for (const sel of titleSelectors) {
                    titleEl = item.querySelector(sel);
                    if (titleEl && titleEl.textContent.trim()) {
                        console.log(`News container ${i + 1}: found title with selector "${sel}"`);
                        break;
                    }
                }
            }
                         
            let snippetEl = item.querySelector('.GI74Re') ||
                           item.querySelector('.VwiC3b') ||
                           item.querySelector('.yXK7lf') ||
                           item.querySelector('.s') ||
                           item.querySelector('.BNeawe');
                           
            let sourceEl = item.querySelector('.MgUUmf span') ||
                          item.querySelector('.ApHyTb') ||
                          item.querySelector('.fG8Fp') ||
                          item.querySelector('.citation') ||
                          item.querySelector('.iUh30');
                          
            let timeEl = item.querySelector('[data-ts]') ||
                        item.querySelector('.f') ||
                        item.querySelector('.LEwnzc') ||
                        item.querySelector('time') ||
                        item.querySelector('.SlP8xc');
            
            // Enhanced time extraction
            if (!timeEl) {
                const textContent = item.textContent || '';
                const timeMatch = textContent.match(/(\\d+\\s*(hours?|mins?|days?)\\s*ago|\\d+天前|\\d+小时前|\\d+分钟前)/i);
                if (timeMatch) {
                    timeEl = { textContent: timeMatch[0] };
                }
            }
            
            // Relaxed condition: only need link OR title
            if (linkEl || titleEl) {
                let url = '';
                if (linkEl) {
                    url = linkEl.href;
                    // Clean Google redirect URLs
                    if (url && url.includes('/url?q=')) {
                        const urlMatch = url.match(/[?&]q=([^&]*)/);
                        if (urlMatch) {
                            url = decodeURIComponent(urlMatch[1]);
                        }
                    }
                }
                
                let title = '';
                if (titleEl) {
                    title = titleEl.textContent ? titleEl.textContent.trim() : '';
                }
                
                // If no title but we have link, try to extract from container
                if (!title && linkEl) {
                    const containerText = item.textContent || item.innerText || '';
                    const lines = containerText.split('\\n').filter(l => l.trim());
                    title = lines.find(line => line.length > 10 && line.length < 200) || 'News Article';
                }
                
                console.log(`News container ${i + 1}: Adding item - title="${title.substring(0, 50)}", url="${url.substring(0, 50)}"`);
                
                results.push({
                    title: title || 'No title',
                    summary: snippetEl ? snippetEl.textContent.trim() : 'No description available',
                    source: sourceEl ? sourceEl.textContent.trim() : 'Unknown source',
                    time: timeEl ? timeEl.textContent.trim() : '',
                    url: url || 'No URL',
                    source_tab: 'news',
                    extraction_method: extractionMethod
                });
            } else {
                console.log(`News container ${i + 1}: Skipped - no link and no title found`);
            }
        }
        
        console.log(`Extracted ${results.length} news results using ${extractionMethod}`);
        return JSON.stringify(results);
    } catch (e) {
        console.error('News extraction error:', e);
        return JSON.stringify([{
            title: 'Error extracting news results',
            link: window.location.href,
            snippet: 'JavaScript extraction failed: ' + e.message,
            source_tab: 'news',
            error: e.toString()
        }]);
    }
})()"""

def _generate_general_extraction_js() -> str:
    """Generate JavaScript code for general search extraction"""
    return """
(function() {
    try {
        const results = [];
        
        // Multiple selector strategies for general search results
        const selectors = [
            'div[data-sokoban-container] div[data-sokoban-feature]',
            'div.g:not(.g-blk)',
            '.tF2Cxc',
            '.MjjYud',
            '.SoaBEf'
        ];
        
        let resultElements = [];
        let selectorUsed = '';
        
        // Try each selector until we find results
        for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            if (elements.length > 0) {
                resultElements = Array.from(elements).slice(0, 10);
                selectorUsed = selector;
                break;
            }
        }
        
        console.log(`Used selector: ${selectorUsed}, found ${resultElements.length} elements`);
        
        // If no results found with specific selectors, try broader search
        if (resultElements.length === 0) {
            const h3Elements = document.querySelectorAll('h3');
            resultElements = Array.from(h3Elements)
                .map(h3 => h3.closest('div'))
                .filter(div => div && div.querySelector('a[href]'))
                .slice(0, 10);
            console.log(`Fallback h3 search found ${resultElements.length} elements`);
        }
        
        for (let i = 0; i < Math.min(resultElements.length, 10); i++) {
            const element = resultElements[i];
            
            // Extract title
            let title = '';
            const titleSelectors = ['h3', '[role="heading"]', '.LC20lb', '.DKV0Md'];
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
                '.VwiC3b',
                '.yXK7lf',
                '.s',
                '.Y3v8qd',
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
                    summary: summary || 'No description available',
                    source_tab: 'all'
                });
            }
        }
        
        console.log(`Extracted ${results.length} general search results`);
        return JSON.stringify(results);
        
    } catch (e) {
        console.error('General search extraction error:', e);
        return JSON.stringify([{
            title: 'Error extracting results',
            url: window.location.href,
            summary: 'JavaScript extraction failed: ' + e.message,
            source_tab: 'all'
        }]);
    }
})()"""

async def _execute_extraction_with_retry(browser_session, extraction_js: str, tab_name: str, max_retries: int = 2):
    """Execute JavaScript extraction with retry logic and detailed logging"""
    cdp_session = await browser_session.get_or_create_cdp_session()

    for attempt in range(max_retries + 1):
        try:
            result = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={'expression': extraction_js, 'returnByValue': True, 'awaitPromise': True},
                session_id=cdp_session.session_id,
            )

            if result.get('exceptionDetails'):
                logger.warning(f"JavaScript extraction failed for {tab_name} (attempt {attempt + 1}): {result['exceptionDetails']}")
                if attempt < max_retries:
                    await asyncio.sleep(1)  # Wait before retry
                    continue
                return []

            result_data = result.get('result', {})
            value = result_data.get('value', '[]')

            try:
                tab_results = json.loads(value)
                if isinstance(tab_results, list):
                    # Log detailed results for debugging
                    logger.info(f"Found {len(tab_results)} results in {tab_name} tab")
                    if tab_results and isinstance(tab_results[0], dict):
                        extraction_method = tab_results[0].get('extraction_method', 'unknown')
                        logger.info(f"{tab_name} tab used extraction method: {extraction_method}")
                    return tab_results
                return []
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse results from {tab_name} tab (attempt {attempt + 1}): {value[:200]}... Error: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1)  # Wait before retry
                    continue
                return []

        except Exception as e:
            logger.warning(f"CDP execution failed for {tab_name} (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(1)  # Wait before retry
                continue
            return []

    return []

async def _perform_tab_search(browser_session, search_url: str, tab_name: str, query: str):
    """
    Optimized helper function to perform search on a specific tab with tab-specific extraction logic
    
    Args:
        browser_session: Active browser session
        search_url: URL to navigate to for search
        tab_name: Type of search tab ('videos', 'news', 'all')
        query: Search query for logging purposes
        
    Returns:
        List of extracted search results
    """
    try:
        logger.info(f"Searching {tab_name} tab for query: {query}")

        # Navigate to search URL
        await browser_session.navigate_to_url(search_url, new_tab=False)

        for _ in range(5):
            try:
                cdp_session = await browser_session.get_or_create_cdp_session()
                ready_state = await cdp_session.cdp_client.send.Runtime.evaluate(
                    params={'expression': 'document.readyState'}, session_id=cdp_session.session_id
                )
                if ready_state and ready_state.get("value", "loading") == "complete":
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

        # Get tab-specific extraction JavaScript
        if tab_name == 'videos':
            extraction_js = _generate_video_extraction_js()
        elif tab_name == 'news':
            extraction_js = _generate_news_extraction_js()
        else:  # 'all' tab - general search
            extraction_js = _generate_general_extraction_js()

        # Execute extraction with retry logic
        return await _execute_extraction_with_retry(browser_session, extraction_js, tab_name)

    except Exception as e:
        logger.warning(f"Failed to search {tab_name} tab: {e}")
        return []


async def _extract_structured_content(browser_session, query: str, llm: BaseChatModel,
                                      target_id: str | None = None, extract_links: bool = False):
    """Helper method to extract structured content from current page"""
    MAX_CHAR_LIMIT = 30000

    # Extract clean markdown using the existing method
    try:
        from browser_use.dom.markdown_extractor import extract_clean_markdown

        content, content_stats = await extract_clean_markdown(
            browser_session=browser_session, extract_links=extract_links
        )
    except Exception as e:
        raise RuntimeError(f'Could not extract clean markdown: {e}')

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

async def _rank_search_results_with_llm(results: list, query: str, llm: BaseChatModel) -> list:
    """
    Rank search results using LLM for relevance and value assessment.

    Args:
        results: List of search results to rank
        query: Original search query for context
        llm: Language model for ranking

    Returns:
        List of ranked results (top 10)
    """
    try:
        max_ret = 15
        # Create indexed results for LLM prompt
        indexed_results = []
        for i, result in enumerate(results):
            indexed_results.append({
                "index": i,
                "title": result.get('title', 'Unknown Title'),
                "url": result.get('url', 'No URL'),
                "summary": result.get('summary', 'No summary available')
            })

        ranking_prompt = f"""
Rank these search results for the query "{query}" by relevance and value.
Select the TOP 10 most relevant and valuable results.

Search Results ({len(indexed_results)} total):
{json.dumps(indexed_results, indent=2, ensure_ascii=False)}

Return ONLY the indices of the top 10 results as a JSON array of numbers.
For example: [0, 5, 2, 8, 1, 9, 3, 7, 4, 6]

Format: [index1, index2, index3, ...]
"""

        from browser_use.llm.messages import SystemMessage, UserMessage
        ranking_response = await llm.ainvoke([
            SystemMessage(
                content="You are an expert at ranking search results for relevance and value. Return only the indices of the top results."),
            UserMessage(content=ranking_prompt)
        ])

        try:
            selected_indices = json.loads(ranking_response.completion.strip())
            if not isinstance(selected_indices, list):
                raise ValueError("Invalid ranking results format")
            # Ensure indices are valid and limit to 10
            valid_indices = [i for i in selected_indices if
                             isinstance(i, int) and 0 <= i < len(results)][:max_ret]
            if valid_indices:
                return [results[i] for i in valid_indices]
            else:
                return results[:max_ret]
        except (json.JSONDecodeError, ValueError):
            try:
                from json_repair import repair_json
                selected_indices_s = repair_json(ranking_response.completion.strip())
                selected_indices = json.loads(selected_indices_s)
                if isinstance(selected_indices, list):
                    valid_indices = [i for i in selected_indices if
                                     isinstance(i, int) and 0 <= i < len(results)][:max_ret]
                    if valid_indices:
                        return [results[i] for i in valid_indices]
                    else:
                        return results[:max_ret]
                else:
                    return results[:max_ret]
            except Exception:
                # Fallback to first 10 results
                return results[:max_ret]

    except Exception as e:
        logger.error(f"LLM ranking failed: {e}")
        return results[:max_ret]


async def extract_file_content_with_llm(file_path: str, query: str, llm: BaseChatModel, file_system):
    """
    Extract content from a file using LLM, with support for both image and text files.
    
    Args:
        file_path: Relative path to the file
        query: Query for content extraction
        llm: Language model for processing
        file_system: File system instance for reading files
        
    Returns:
        str: Extracted content formatted as "File: {file_path}\nQuery: {query}\nExtracted Content:\n{content}"
        
    Raises:
        Exception: If file processing fails
    """
    # Get full file path
    full_file_path = file_path
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
                ContentPartTextParam(text=f"Query: {query}")
            ]

            # Add the image
            content_parts.append(
                ContentPartImageParam(
                    image_url=ImageURL(
                        url=f'data:{mime_type};base64,{image_base64}',
                        media_type=mime_type,
                        detail='auto',
                    ),
                )
            )

            # Create user message and invoke LLM
            user_message = UserMessage(content=content_parts, cache=True)
            response = await asyncio.wait_for(
                llm.ainvoke([user_message]),
                timeout=120.0,
            )

            extracted_content = f'File: {file_path}\nQuery: {query}\nExtracted Content:\n{response.completion}'

        except Exception as e:
            raise Exception(f'Failed to process image file {file_path}: {str(e)}')

    else:
        # Handle non-image files by reading content
        try:
            file_content = await file_system.read_file(full_file_path, external_file=True)

            # Create a simple prompt for text extraction
            prompt = f"""Extract the requested information from this file content.

Query: {query}

File: {file_path}
File Content:
{file_content}

Provide the extracted information in a clear, structured format."""

            response = await asyncio.wait_for(
                llm.ainvoke([UserMessage(content=prompt)]),
                timeout=120.0,
            )

            extracted_content = f'File: {file_path}\nQuery: {query}\nExtracted Content:\n{response.completion}'

        except Exception as e:
            raise Exception(f'Failed to read file {file_path}: {str(e)}')

    return extracted_content

def remove_import_statements(code: str) -> str:
    """
    Remove import statements from Python code since modules are pre-imported in namespace
    """
    lines = code.split('\n')
    filtered_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        # Skip import statements but preserve other lines
        if (stripped_line.startswith('import ') or
            stripped_line.startswith('from ') and ' import ' in stripped_line):
            # Add comment to show what was removed
            filtered_lines.append(f"# REMOVED: {line}")
        else:
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)