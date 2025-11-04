from typing_extensions import override

from vibe_surf.langflow.logging.logger import logger
from vibe_surf.langflow.services.factory import ServiceFactory
from vibe_surf.langflow.services.session.service import SessionService
from vibe_surf.langflow.services.settings.service import SettingsService
from vibe_surf.langflow.services.storage.service import StorageService


class StorageServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(
            StorageService,
        )

    @override
    def create(self, session_service: SessionService, settings_service: SettingsService):
        storage_type = settings_service.settings.storage_type
        if storage_type.lower() == "local":
            from .local import LocalStorageService

            return LocalStorageService(session_service, settings_service)
        if storage_type.lower() == "s3":
            from .s3 import S3StorageService

            return S3StorageService(session_service, settings_service)
        logger.warning(f"Storage type {storage_type} not supported. Using local storage.")
        from .local import LocalStorageService

        return LocalStorageService(session_service, settings_service)
