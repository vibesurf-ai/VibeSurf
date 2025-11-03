from bs4 import BeautifulSoup
import asyncio
import json

from browser_use.dom.service import EnhancedDOMTreeNode
from vibe_surf.logger import get_logger
from browser_use.llm.messages import SystemMessage, UserMessage, AssistantMessage

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
                logger.info(generated_js_code)
                # Always use awaitPromise=True - it's ignored for non-promises
                result = await cdp_session.cdp_client.send.Runtime.evaluate(
                    params={'expression': generated_js_code, 'returnByValue': True, 'awaitPromise': True},
                    session_id=cdp_session.session_id,
                )
                execute_result = str(result)
                logger.info(result)
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
