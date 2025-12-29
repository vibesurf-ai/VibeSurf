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
        logger.info(f"Detected proxies: {proxies}")
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

    # 4. Configure no_proxy to exclude local and backend services
    if http_proxy or https_proxy:
        current_no_proxy = os.environ.get('no_proxy', '')
        current_NO_PROXY = os.environ.get('NO_PROXY', '')

        # Use NO_PROXY if no_proxy is not set
        if not current_no_proxy and current_NO_PROXY:
            current_no_proxy = current_NO_PROXY

        required_no_proxy_hosts = ['localhost', '127.0.0.1', '::1', 'backend.composio.dev', 'us.i.posthog.com']

        # Parse current no_proxy list
        if current_no_proxy:
            no_proxy_list = [h.strip() for h in current_no_proxy.split(',')]
        else:
            no_proxy_list = []

        # Add required hosts if not already present
        for host in required_no_proxy_hosts:
            if host not in no_proxy_list:
                no_proxy_list.append(host)

        new_no_proxy = ','.join(no_proxy_list)
        os.environ['no_proxy'] = new_no_proxy
        os.environ['NO_PROXY'] = new_no_proxy
        logger.info(f"Set no_proxy to: {new_no_proxy}")