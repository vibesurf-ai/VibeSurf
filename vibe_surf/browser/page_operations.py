from typing import Optional, List, Tuple

import asyncio
from vibe_surf.logger import get_logger

logger = get_logger(__name__)


async def scroll_to_text(text, browser_session):
    cdp_client = browser_session.cdp_client
    if browser_session.agent_focus is None:
        raise RuntimeError('CDP session not initialized - browser may not be connected yet')
    session_id = browser_session.agent_focus.session_id

    # Enable DOM
    await cdp_client.send.DOM.enable(session_id=session_id)

    # Get document
    doc = await cdp_client.send.DOM.getDocument(params={'depth': -1}, session_id=session_id)
    root_node_id = doc['root']['nodeId']

    # Search for text using XPath
    search_queries = [
        f'//*[contains(text(), "{text}")]',
        f'//*[contains(., "{text}")]',
        f'//*[@*[contains(., "{text}")]]',
    ]

    found = False
    for query in search_queries:
        try:
            # Perform search
            search_result = await cdp_client.send.DOM.performSearch(params={'query': query}, session_id=session_id)
            search_id = search_result['searchId']
            result_count = search_result['resultCount']

            if result_count > 0:
                # Get the first match
                node_ids = await cdp_client.send.DOM.getSearchResults(
                    params={'searchId': search_id, 'fromIndex': 0, 'toIndex': 1},
                    session_id=session_id,
                )

                if node_ids['nodeIds']:
                    node_id = node_ids['nodeIds'][0]

                    # Scroll the element into view
                    await cdp_client.send.DOM.scrollIntoViewIfNeeded(params={'nodeId': node_id}, session_id=session_id)

                    found = True
                    logger.debug(f'📜 Scrolled to text: "{text}"')
                    break

            # Clean up search
            await cdp_client.send.DOM.discardSearchResults(params={'searchId': search_id}, session_id=session_id)
        except Exception as e:
            logger.debug(f'Search query failed: {query}, error: {e}')
            continue

    if not found:
        # Fallback: Try JavaScript search
        js_result = await cdp_client.send.Runtime.evaluate(
            params={
                'expression': f'''
                        (() => {{
                            const walker = document.createTreeWalker(
                                document.body,
                                NodeFilter.SHOW_TEXT,
                                null,
                                false
                            );
                            let node;
                            while (node = walker.nextNode()) {{
                                if (node.textContent.includes("{text}")) {{
                                    node.parentElement.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                                    return true;
                                }}
                            }}
                            return false;
                        }})()
                    '''
            },
            session_id=session_id,
        )

        if js_result.get('result', {}).get('value'):
            logger.debug(f'📜 Scrolled to text: "{text}" (via JS)')
            return None
        else:
            logger.warning(f'⚠️ Text not found: "{text}"')
            raise RuntimeError(f'Text not found: "{text}"', details={'text': text})

    # If we got here and found is True, return None (success)
    if found:
        return None
    else:
        raise RuntimeError(f'Text not found: "{text}"', details={'text': text})


async def _try_direct_selector(browser_session, target_text: str) -> Optional[str]:
    """Try to use target_text as a direct selector (ID or name) with improved robustness."""
    if not target_text or not target_text.replace('_', '').replace('-', '').replace('.', '').isalnum():
        return None

    # Clean the target text to make it a valid selector
    cleaned_text = target_text.strip()

    # Try as ID first, then name attribute, then other common patterns
    selectors_to_try = [
        f'#{cleaned_text}',
        f"[name='{cleaned_text}']",
        f"[id='{cleaned_text}']",
        f"[data-testid='{cleaned_text}']",
        f"[placeholder='{cleaned_text}']",
    ]

    # Also try with common variations
    if '_' in cleaned_text or '-' in cleaned_text:
        # Try camelCase version
        camel_case = ''.join(
            word.capitalize() if i > 0 else word for i, word in enumerate(cleaned_text.replace('-', '_').split('_'))
        )
        selectors_to_try.extend([f'#{camel_case}', f"[name='{camel_case}']", f"[id='{camel_case}']"])

        # Try lowercase version
        lower_case = cleaned_text.lower()
        selectors_to_try.extend([f'#{lower_case}', f"[name='{lower_case}']", f"[id='{lower_case}']"])

    for selector in selectors_to_try:
        try:
            page = await browser_session.get_current_page()

            # Check if element exists first
            elements = await page.get_elements_by_css_selector(selector)
            element_count = len(elements)
            if element_count == 0:
                continue

            # Check if it's visible
            await page.wait_for_selector(selector, timeout=2000, state='visible')

            # Check if this selector resolves to multiple elements (strict mode violation)
            if element_count > 1:
                logger.warning(f'Selector {selector} matches {element_count} elements, trying to make it more specific')

                # Try to make it more specific for form elements
                specific_selectors = [f"{selector}:not([type='hidden'])", f'{selector}:visible',
                                      f'{selector}:first-of-type']

                for specific_selector in specific_selectors:
                    try:
                        specific_elements = await page.get_elements_by_css_selector(specific_selector)
                        specific_count = len(specific_elements)
                        if specific_count == 1:
                            await page.wait_for_selector(specific_selector, timeout=1000, state='visible')
                            logger.info(f'Found specific element using selector: {specific_selector}')
                            return specific_selector
                    except Exception:
                        continue

                # If we can't make it specific, return the original but log the issue
                logger.warning(f'Using non-specific selector {selector} (matches {element_count} elements)')
                return selector

            logger.info(f'Found element using direct selector: {selector}')
            return selector

        except Exception as e:
            logger.debug(f'Element not found with selector {selector}: {e}')
            continue

    return None


async def _wait_for_element(
        browser_session, selector: str, timeout_ms: int = 5000, fallback_selectors: List[str] = None
) -> Tuple[bool, str]:
    """Wait for element to be available, with hierarchical fallback options.

    Returns:
        Tuple of (success, actual_selector_used)
    """
    selectors_to_try = [selector]
    if fallback_selectors:
        selectors_to_try.extend(fallback_selectors)

    page = await browser_session.get_current_page()
    end_time = asyncio.get_event_loop().time() + (timeout_ms / 1000)

    for sel in selectors_to_try:
        try:
            # XPath selectors need special handling - skip for now in CDP
            if sel.startswith('xpath='):
                logger.debug(f'XPath selector not supported in CDP: {sel}')
                continue

            # Poll for element with timeout
            while asyncio.get_event_loop().time() < end_time:
                try:
                    elements = await page.get_elements_by_css_selector(sel)

                    if len(elements) > 0:
                        if len(elements) > 1:
                            logger.warning(f'Selector {sel} matches {len(elements)} elements during wait')
                            # Try to make it more specific if it's the hierarchical selector
                            if sel != selector and ':nth-of-type' in sel:
                                return True, sel  # Hierarchical selectors with nth-of-type are usually fine
                            return True, sel  # Element exists, but we'll handle the strict mode later

                        return True, sel
                except Exception as e:
                    logger.debug(f'Error checking selector {sel}: {e}')

                # Wait a bit before retrying
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.debug(f'Element not found with selector {sel}: {e}')
            continue

    logger.warning(f'Element not found with any selector: {selectors_to_try}')
    return False, selector
