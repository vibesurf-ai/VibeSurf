from lfx.services.settings.service import SettingsService
from typing_extensions import override

from vibe_surf.backend.langflow.services.factory import ServiceFactory
from vibe_surf.backend.langflow.services.state.service import InMemoryStateService


class StateServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(InMemoryStateService)

    @override
    def create(self, settings_service: SettingsService):
        return InMemoryStateService(
            settings_service,
        )
