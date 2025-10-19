import pdb

import vibe_surf
from vibe_surf.telemetry.service import ProductTelemetry
from vibe_surf.telemetry.views import CLITelemetryEvent


def test_cli_telemetry_event():
    """Test CLITelemetryEvent structure."""
    event = CLITelemetryEvent(
        version=str(vibe_surf.__version__),
        action='start',
        mode='interactive',
        model='gpt-4o',
        model_provider='OpenAI',
        duration_seconds=10.5,
        error_message=None,
    )

    telemetry = ProductTelemetry()

    # Check that posthog client is created
    assert telemetry._posthog_client is not None

    telemetry.capture(event)
    telemetry.flush()


if __name__ == '__main__':
    test_cli_telemetry_event()
