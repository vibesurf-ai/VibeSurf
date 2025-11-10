import inspect
import asyncio
import pdb
import pprint
from typing import Any, Dict, List, Optional

from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.custom.custom_component.component import Component
from vibe_surf.langflow.inputs.inputs import DropdownInput, MessageTextInput, IntInput, BoolInput, HandleInput
from vibe_surf.langflow.io import Output
from vibe_surf.tools.website_api.weibo.client import WeiboApiClient
from vibe_surf.browser.browser_manager import BrowserManager
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.data import Data

weibo_methods = [
    {
        "name": "search_posts_by_keyword",
        "display_name": "Search Posts by Keyword",
        "description": "Search Weibo posts by keyword",
        "params": '{"keyword": "search keyword", "page": 1, "search_type": "SearchType.DEFAULT"}'
    },
    {
        "name": "get_post_detail",
        "display_name": "Get Post Details",
        "description": "Get detailed post information by mid ID",
        "params": '{"mid": "Weibo post ID"}'
    },
    {
        "name": "get_all_post_comments",
        "display_name": "Get Post Comments",
        "description": "Fetch all comments for a post including sub-comments",
        "params": '{"mid": "Weibo post ID", "fetch_interval": 1.0, "include_sub_comments": false, "max_comments": 1000}'
    },
    {
        "name": "get_user_info",
        "display_name": "Get User Profile",
        "description": "Get user profile information",
        "params": '{"user_id": "user ID"}'
    },
    {
        "name": "get_all_user_posts",
        "display_name": "Get User Posts",
        "description": "Fetch all posts by a user",
        "params": '{"user_id": "user ID", "fetch_interval": 1.0, "max_posts": 1000}'
    },
    {
        "name": "get_hot_posts",
        "display_name": "Get Hot Posts (推荐榜)",
        "description": "Get Weibo hot posts (热门推荐)",
        "params": '{}'
    },
    {
        "name": "get_trending_posts",
        "display_name": "Get Trending Posts (热搜榜)",
        "description": "Get Weibo trending posts (热搜榜)",
        "params": '{}'
    }
]

weibo_func_names = [method_info["display_name"] for method_info in weibo_methods]

class WeiboComponent(Component):
    display_name = "Weibo API"
    description = "Access Weibo platform data including posts, users, comments, trending topics and hot content"
    icon = "Weibo"
    name = "Weibo"

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
            info="Select the Weibo API method to use",
            options=weibo_func_names,
            real_time_refresh=True,
            value="Search Posts by Keyword"
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
            display_name="WeiboResult",
            name="weibo_result",
            method="execute_weibo_method",
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
            for method_info_ in weibo_methods:
                if method_info_["display_name"] == method_name:
                    method_info = method_info_
                    break
            build_config["method"]["info"] = method_info["description"]

            method_func_name = method_info["name"]
            method = getattr(WeiboApiClient, method_info["name"])
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

    async def execute_weibo_method(self) -> Message:
        """Execute the selected Weibo API method with dynamic parameters"""
        client = None
        try:
            if not hasattr(self, 'method') or not self.method:
                raise ValueError("Please select an API method")

            method_name = self.method
            method_info = None
            for method_info_ in weibo_methods:
                if method_info_["display_name"] == method_name:
                    method_info = method_info_
                    break

            client = WeiboApiClient(self.browser_session)
            await client.setup()

            params = {}
            method = getattr(WeiboApiClient, method_info["name"])
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
            self.status = f"❌ Failed to execute Weibo API call: {str(e)}"
            raise e
        finally:
            if client:
                await client.close()