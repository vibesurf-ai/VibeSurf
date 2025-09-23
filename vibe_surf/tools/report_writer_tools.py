from browser_use.tools.registry.service import Registry
from vibe_surf.tools.vibesurf_tools import VibeSurfTools
from vibe_surf.tools.file_system import CustomFileSystem
from browser_use.tools.views import NoParamsAction
from vibe_surf.tools.vibesurf_registry import VibeSurfRegistry


class ReportWriterTools(VibeSurfTools):
    def __init__(self, exclude_actions: list[str] = []):
        self.registry = VibeSurfRegistry(exclude_actions)
        self._register_file_actions()
        self._register_done_action()

    def _register_done_action(self):
        @self.registry.action(
            description="Finish writing report.",
            param_model=NoParamsAction
        )
        async def task_done(
                _: NoParamsAction,
        ):
            pass
