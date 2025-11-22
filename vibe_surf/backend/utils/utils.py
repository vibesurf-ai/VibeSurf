import pdb
import urllib.request
import os
from vibe_surf.logger import get_logger

logger = get_logger(__name__)

def configure_system_proxies():
    """
    Get system proxy settings using urllib.request.getproxies()
    and set them as HTTP_PROXY and HTTPS_PROXY environment variables.
    """

    # 1. Get system proxy setting
    try:
        proxies = urllib.request.getproxies()
        logger.info(proxies)
    except Exception as e:
        # Simple error handling
        logger.error(e)
        return

    if not proxies:
        logger.info("No system proxies detected.")
        return

    logger.debug(f"Detected system proxies: {proxies}")

    # 2. Configure HTTP_PROXY
    http_proxy = proxies.get('http')
    if http_proxy:
        os.environ['HTTP_PROXY'] = http_proxy
        logger.info(f"Set HTTP_PROXY to: {http_proxy}")

    # 3. Configure HTTPS_PROXY
    https_proxy = proxies.get('https')
    if https_proxy:
        os.environ['HTTPS_PROXY'] = https_proxy
        logger.info(f"Set HTTPS_PROXY to: {https_proxy}")

    if http_proxy or https_proxy:
        os.environ['no_proxy'] = 'localhost,127.0.0.1,::1,backend.composio.dev,us.i.posthog.com'