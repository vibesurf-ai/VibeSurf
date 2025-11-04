from vibe_surf.langflow.services.base import Service
from vibe_surf.langflow.services.factory import ServiceFactory
from vibe_surf.langflow.services.job_queue.service import JobQueueService


class JobQueueServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(JobQueueService)

    def create(self) -> Service:
        return JobQueueService()
