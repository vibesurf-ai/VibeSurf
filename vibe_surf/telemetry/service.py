import logging
import os
import pdb

from dotenv import load_dotenv
from posthog import Posthog
from uuid_extensions import uuid7str

from vibe_surf.telemetry.views import BaseTelemetryEvent
from vibe_surf.utils import singleton
from vibe_surf.logger import get_logger
from vibe_surf import common

load_dotenv()

logger = get_logger(__name__)

POSTHOG_EVENT_SETTINGS = {
    'process_person_profile': True,
}


@singleton
class ProductTelemetry:
    """
    Service for capturing anonymized telemetry data.

    If the environment variable `ANONYMIZED_TELEMETRY=False`, anonymized telemetry will be disabled.
    """
    WORKSPACE_DIR = common.get_workspace_dir()
    USER_ID_PATH = os.path.join(WORKSPACE_DIR, 'telemetry', 'userid')
    PROJECT_API_KEY = 'phc_lCYnQqFlfNHAlh1TJGqaTvD8EFPCKR7ONsEHbbWuPVr'
    HOST = 'https://us.i.posthog.com'
    UNKNOWN_USER_ID = 'UNKNOWN'

    _curr_user_id = None

    def __init__(self) -> None:
        telemetry_enabled = os.getenv('VIBESURF_ANONYMIZED_TELEMETRY', 'true').lower() in ("true", "1", "yes", "on")
        self.debug_logging = os.getenv("VIBESURF_DEBUG", "false").lower() in ("true", "1", "yes", "on")

        telemetry_disabled = not telemetry_enabled
        self._ensure_no_proxy()

        if telemetry_disabled:
            self._posthog_client = None
        else:
            self._posthog_client = Posthog(
                project_api_key=self.PROJECT_API_KEY,
                host=self.HOST,
                disable_geoip=False,
                enable_exception_autocapture=True,
            )

            # Silence posthog's logging
            if not self.debug_logging:
                posthog_logger = logging.getLogger('posthog')
                posthog_logger.disabled = True

        if self._posthog_client is None:
            logger.debug('Telemetry disabled')

    def _ensure_no_proxy(self):
        current_no_proxy = os.environ.get('no_proxy', '')
        current_NO_PROXY = os.environ.get('NO_PROXY', '')

        # Use NO_PROXY if no_proxy is not set
        if not current_no_proxy and current_NO_PROXY:
            current_no_proxy = current_NO_PROXY

        required_hosts = ['us.i.posthog.com']

        # Parse current no_proxy list
        if current_no_proxy:
            no_proxy_list = [h.strip() for h in current_no_proxy.split(',')]
        else:
            no_proxy_list = []

        # Add required hosts if not already present
        modified = False
        for host in required_hosts:
            if host not in no_proxy_list:
                no_proxy_list.append(host)
                modified = True

        # Update environment variables if modified
        if modified:
            new_no_proxy = ','.join(no_proxy_list)
            os.environ['no_proxy'] = new_no_proxy
            os.environ['NO_PROXY'] = new_no_proxy

    def capture(self, event: BaseTelemetryEvent) -> None:
        if self._posthog_client is None:
            return

        self._direct_capture(event)

    def _direct_capture(self, event: BaseTelemetryEvent) -> None:
        """
        Should not be thread blocking because posthog magically handles it
        """
        if self._posthog_client is None:
            return

        try:
            self._posthog_client.capture(
                distinct_id=self.user_id,
                event=event.name,
                properties={**event.properties, **POSTHOG_EVENT_SETTINGS},
            )
        except Exception as e:
            logger.error(f'Failed to send telemetry event {event.name}: {e}')

    def flush(self) -> None:
        if self._posthog_client:
            try:
                self._posthog_client.flush()
                logger.debug('PostHog client telemetry queue flushed.')
            except Exception as e:
                logger.error(f'Failed to flush PostHog client: {e}')
        else:
            logger.debug('PostHog client not available, skipping flush.')

    @property
    def user_id(self) -> str:
        if self._curr_user_id:
            return self._curr_user_id

        # File access may fail due to permissions or other reasons. We don't want to
        # crash so we catch all exceptions.
        try:
            if not os.path.exists(self.USER_ID_PATH):
                os.makedirs(os.path.dirname(self.USER_ID_PATH), exist_ok=True)
                with open(self.USER_ID_PATH, 'w') as f:
                    new_user_id = uuid7str()
                    f.write(new_user_id)
                self._curr_user_id = new_user_id
            else:
                with open(self.USER_ID_PATH) as f:
                    self._curr_user_id = f.read()
        except Exception:
            self._curr_user_id = 'UNKNOWN_USER_ID'
        return self._curr_user_id
