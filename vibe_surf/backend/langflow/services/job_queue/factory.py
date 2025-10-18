from vibe_surf.backend.langflow.services.base import Service
from vibe_surf.backend.langflow.services.factory import ServiceFactory
from vibe_surf.backend.langflow.services.job_queue.service import JobQueueService


class JobQueueServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(JobQueueService)

    def create(self) -> Service:
        return JobQueueService()
