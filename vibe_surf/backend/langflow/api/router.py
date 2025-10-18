# Router for base api
from fastapi import APIRouter

from vibe_surf.backend.langflow.api.v1 import (
    api_key_router,
    chat_router,
    endpoints_router,
    files_router,
    flows_router,
    folders_router,
    mcp_projects_router,
    mcp_router,
    monitor_router,
    openai_responses_router,
    store_router,
    validate_router,
    variables_router,
    projects_router,
    starter_projects_router
)
# from vibe_surf.backend.langflow.api.v1.voice_mode import router as voice_mode_router
from vibe_surf.backend.langflow.api.v2 import files_router as files_router_v2
from vibe_surf.backend.langflow.api.v2 import mcp_router as mcp_router_v2

router_v1 = APIRouter(
    prefix="/v1",
)

router_v2 = APIRouter(
    prefix="/v2",
)

router_v1.include_router(chat_router)
router_v1.include_router(endpoints_router)
router_v1.include_router(validate_router)
router_v1.include_router(store_router)
router_v1.include_router(flows_router)
router_v1.include_router(api_key_router)
router_v1.include_router(variables_router)
router_v1.include_router(files_router)
router_v1.include_router(monitor_router)
router_v1.include_router(folders_router)
router_v1.include_router(mcp_router)
router_v1.include_router(mcp_projects_router)
router_v1.include_router(openai_responses_router)

router_v1.include_router(projects_router)
router_v1.include_router(starter_projects_router)
router_v2.include_router(files_router_v2)
router_v2.include_router(mcp_router_v2)

router = APIRouter(
    prefix="/api",
)
router.include_router(router_v1)
router.include_router(router_v2)
