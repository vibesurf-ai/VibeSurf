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
