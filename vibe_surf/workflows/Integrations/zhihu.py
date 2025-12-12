import inspect
import asyncio
import pdb
import pprint
from typing import Any, Dict, List, Optional

from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.custom.custom_component.component import Component
from vibe_surf.langflow.inputs.inputs import DropdownInput, MessageTextInput, IntInput, BoolInput, HandleInput
from vibe_surf.langflow.io import Output
from vibe_surf.tools.website_api.zhihu.client import ZhiHuClient
from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.data import Data

zhihu_methods = [
    {
        "name": "get_note_by_keyword",
        "display_name": "Search Content by Keyword",
        "description": "Search Zhihu content (questions, articles, videos) by keyword",
        "params": '{"keyword": "search keyword", "page": 1, "page_size": 20}'
    },
    {
        "name": "get_note_all_comments",
        "display_name": "Get Content Comments",
        "description": "Get all comments for a specific content (answer, article, or video)",
        "params": '{"content_id": "content ID", "content_type": "answer", "crawl_interval": 1.0}'
    },
    {
        "name": "get_creator_info",
        "display_name": "Get Creator Profile",
        "description": "Get creator profile information",
        "params": '{"url_token": "creator url token"}'
    },
    {
        "name": "get_all_answer_by_creator",
        "display_name": "Get Creator Answers",
        "description": "Get all answers by a creator",
        "params": '{"url_token": "creator url token", "crawl_interval": 1.0}'
    },
    {
        "name": "get_all_articles_by_creator",
        "display_name": "Get Creator Articles",
        "description": "Get all articles by a creator",
        "params": '{"url_token": "creator url token", "crawl_interval": 1.0}'
    },
    {
        "name": "get_all_videos_by_creator",
        "display_name": "Get Creator Videos",
        "description": "Get all videos by a creator",
        "params": '{"url_token": "creator url token", "crawl_interval": 1.0}'
    },
    {
        "name": "get_answer_info",
        "display_name": "Get Answer Details",
        "description": "Get detailed answer information",
        "params": '{"question_id": "question ID", "answer_id": "answer ID"}'
    },
    {
        "name": "get_article_info",
        "display_name": "Get Article Details",
        "description": "Get detailed article information",
        "params": '{"article_id": "article ID"}'
    },
    {
        "name": "get_video_info",
        "display_name": "Get Video Details",
        "description": "Get detailed video information",
        "params": '{"video_id": "video ID"}'
    }
]

zhihu_func_names = [method_info["display_name"] for method_info in zhihu_methods]

class ZhihuComponent(Component):
    display_name = "Zhihu API"
    description = "Access Zhihu platform data including questions, answers, articles, videos, creators and comments"
    icon = "Zhihu"
    name = "Zhihu"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        DropdownInput(
            name="method",
            display_name="API Method",
            info="Select the Zhihu API method to use",
            options=zhihu_func_names,
            real_time_refresh=True,
            value="Search Content by Keyword"
        ),
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="pass_browser_session",
            types=["AgentBrowserSession"],
            group_outputs=True
        ),
        Output(
            display_name="ZhihuResult",
            name="zhihu_result",
            method="execute_zhihu_method",
            group_outputs=True
        ),
    ]

    _api_result: Optional[str] = None

    async def pass_browser_session(self) -> AgentBrowserSession:
        return self.browser_session

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update dropdown options and create dynamic parameter inputs"""

        if field_name == "method" and field_value:
            original_inputs = ['_type', 'browser_session', 'code', 'method']
            for input_name in list(build_config.keys()):
                if input_name not in original_inputs:
                    del build_config[input_name]

            method_name = field_value
            method_info = None
            for method_info_ in zhihu_methods:
                if method_info_["display_name"] == method_name:
                    method_info = method_info_
                    break
            build_config["method"]["info"] = method_info["description"]

            method_func_name = method_info["name"]
            method = getattr(ZhiHuClient, method_info["name"])
            sig = inspect.signature(method)
            params = []

            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'browser_session']:
                    continue

                # Determine parameter type and create appropriate input
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
                default_value = param.default if param.default != inspect.Parameter.empty else None

                param_info = {
                    'name': param_name,
                    'type': param_type,
                    'default': default_value,
                    'required': param.default == inspect.Parameter.empty
                }
                params.append(param_info)

            # Add parameter inputs for selected method
            for param in params:
                input_name = param['name']

                # Create appropriate input type based on parameter type
                if param['type'] == int:
                    build_config[input_name] = {
                        "type": "int",
                        "display_name": param['name'].replace('_', ' ').title(),
                        "name": input_name,
                        "value": param['default'] if param['default'] is not None else 0,
                        "required": param['required'],
                        "info": f"{param['name']} (Parameter of {method_func_name})",
                        "show": True
                    }
                elif param['type'] == bool:
                    build_config[input_name] = {
                        "type": "bool",
                        "display_name": param['name'].replace('_', ' ').title(),
                        "name": input_name,
                        "value": param['default'] if param['default'] is not None else False,
                        "required": param['required'],
                        "info": f"{param['name']} (Parameter of {method_func_name})",
                        "show": True
                    }
                elif param['type'] == float:
                    build_config[input_name] = {
                        "type": "float",
                        "display_name": param['name'].replace('_', ' ').title(),
                        "name": input_name,
                        "value": param['default'] if param['default'] is not None else 0.0,
                        "required": param['required'],
                        "info": f"{param['name']} (Parameter of {method_func_name})",
                        "show": True
                    }
                else:  # str or other types
                    build_config[input_name] = {
                        "type": "str",
                        "display_name": param['name'].replace('_', ' ').title(),
                        "name": input_name,
                        "value": param['default'] if param['default'] is not None else "",
                        "required": param['required'],
                        "info": f"{param['name']} (Parameter of {method_func_name})",
                        "placeholder": "",
                        "show": True,
                        "_input_type": "MessageTextInput",
                        'input_types': ['Message']
                    }

        return build_config

    async def execute_zhihu_method(self) -> Message:
        """Execute the selected Zhihu API method with dynamic parameters"""
        client = None
        try:
            if not hasattr(self, 'method') or not self.method:
                raise ValueError("Please select an API method")

            method_name = self.method
            method_info = None
            for method_info_ in zhihu_methods:
                if method_info_["display_name"] == method_name:
                    method_info = method_info_
                    break

            client = ZhiHuClient(self.browser_session)
            await client.setup()

            params = {}
            method = getattr(ZhiHuClient, method_info["name"])
            sig = inspect.signature(method)

            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'browser_session']:
                    continue
                if hasattr(self, param_name):
                    value = getattr(self, param_name)
                    if value is not None and value != "":
                        params[param_name] = value.get_text() if isinstance(value, Data) else value
            method = getattr(client, method_info["name"])
            if inspect.iscoroutinefunction(method):
                if params:
                    api_result = await method(**params)
                else:
                    api_result = await method()
            else:
                if params:
                    api_result = method(**params)
                else:
                    api_result = method()
            self._api_result = pprint.pformat(api_result)
            return Message(text=self._api_result)

        except Exception as e:
            self.status = f"❌ Failed to execute Zhihu API call: {str(e)}"
            raise e
        finally:
            if client:
                await client.close()