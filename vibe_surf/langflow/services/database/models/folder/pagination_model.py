from fastapi_pagination import Page

from vibe_surf.langflow.helpers.base_model import BaseModel
from vibe_surf.langflow.services.database.models.flow.model import Flow
from vibe_surf.langflow.services.database.models.folder.model import FolderRead


class FolderWithPaginatedFlows(BaseModel):
    folder: FolderRead
    flows: Page[Flow]
