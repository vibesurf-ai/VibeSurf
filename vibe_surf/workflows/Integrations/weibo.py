import inspect
import asyncio
from typing import Any, Dict, List, Optional

from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.custom.custom_component.component import Component
from vibe_surf.langflow.inputs.inputs import DropdownInput, MessageTextInput, IntInput, BoolInput
from vibe_surf.langflow.io import Output
from vibe_surf.tools.website_api.weibo.client import WeiboApiClient
from vibe_surf.browser.browser_manager import BrowserManager


class WeiboComponent(Component):
    display_name = "Weibo API"
    description = "Access Weibo platform data including posts, users, comments, trending topics and hot content"
    icon = "Weibo"
    name = "Weibo"

    inputs = [
        DropdownInput(
            name="method",
            display_name="API Method",
            info="Select the Weibo API method to use",
            options=[],
            value="",
            real_time_refresh=True,
        ),
    ]

    outputs = [
        Output(display_name="WeiboResult", name="weibo_result", method="execute_weibo_method"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._method_params: Dict[str, List[Dict]] = {}
        self._init_method_params()

    def _init_method_params(self):
        """Initialize method parameters using inspect"""
        # Get all public methods from WeiboApiClient
        methods_to_inspect = [
            'search_posts_by_keyword',
            'get_post_detail',
            'get_all_post_comments',
            'get_user_info',
            'get_all_user_posts',
            'get_hot_posts',
            'get_trending_posts'
        ]

        for method_name in methods_to_inspect:
            try:
                method = getattr(WeiboApiClient, method_name)
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
                
                self._method_params[method_name] = params
            except Exception as e:
                print(f"Error inspecting method {method_name}: {e}")

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update dropdown options and create dynamic parameter inputs"""
        
        if field_name == "method" or not build_config["method"]["options"]:
            # Update method options
            methods = [
                {"name": "search_posts_by_keyword", "display_name": "Search Posts by Keyword"},
                {"name": "get_post_detail", "display_name": "Get Post Details"},
                {"name": "get_all_post_comments", "display_name": "Get Post Comments"},
                {"name": "get_user_info", "display_name": "Get User Profile"},
                {"name": "get_all_user_posts", "display_name": "Get User Posts"},
                {"name": "get_hot_posts", "display_name": "Get Hot Posts (推荐榜)"},
                {"name": "get_trending_posts", "display_name": "Get Trending Posts (热搜榜)"}
            ]
            
            build_config["method"]["options"] = [
                {"name": method["name"], "display_name": method["display_name"]}
                for method in methods
            ]

        # When method is selected, create dynamic parameter inputs
        if field_name == "method" and field_value:
            # Remove existing parameter inputs (except method)
            original_inputs = ["method"]
            for input_name in list(build_config.keys()):
                if input_name not in original_inputs:
                    del build_config[input_name]
            
            # Add parameter inputs for selected method
            if field_value in self._method_params:
                for param in self._method_params[field_value]:
                    input_name = f"param_{param['name']}"
                    
                    # Create appropriate input type based on parameter type
                    if param['type'] == int:
                        build_config[input_name] = {
                            "type": "int",
                            "display_name": param['name'].replace('_', ' ').title(),
                            "name": input_name,
                            "value": param['default'] if param['default'] is not None else 0,
                            "required": param['required'],
                            "info": f"Parameter: {param['name']} (type: {param['type'].__name__})"
                        }
                    elif param['type'] == bool:
                        build_config[input_name] = {
                            "type": "bool", 
                            "display_name": param['name'].replace('_', ' ').title(),
                            "name": input_name,
                            "value": param['default'] if param['default'] is not None else False,
                            "required": param['required'],
                            "info": f"Parameter: {param['name']} (type: {param['type'].__name__})"
                        }
                    else:  # str or other types
                        build_config[input_name] = {
                            "type": "str",
                            "display_name": param['name'].replace('_', ' ').title(),
                            "name": input_name,
                            "value": param['default'] if param['default'] is not None else "",
                            "required": param['required'],
                            "info": f"Parameter: {param['name']} (type: {param['type'].__name__})",
                            "placeholder": f"Enter {param['name']}"
                        }

        return build_config

    async def execute_weibo_method(self) -> Message:
        """Execute the selected Weibo API method with dynamic parameters"""
        try:
            if not hasattr(self, 'method') or not self.method:
                raise ValueError("Please select an API method")
            
            method_name = self.method
            
            # Collect parameters from dynamic inputs
            params = {}
            if method_name in self._method_params:
                for param in self._method_params[method_name]:
                    param_attr = f"param_{param['name']}"
                    if hasattr(self, param_attr):
                        value = getattr(self, param_attr)
                        if value is not None and value != "":
                            params[param['name']] = value

            # Direct client execution (like in test_api_tools.py)
            result_text = f"🐦 Weibo API Method: {method_name}\n\nParameters:\n"
            for key, value in params.items():
                result_text += f"- {key}: {value}\n"
            
            result_text += f"\n⚠️ Note: This component is ready for integration with browser session.\n"
            result_text += f"Implementation pattern:\n"
            result_text += f"```python\n"
            result_text += f"client = WeiboApiClient(browser_session)\n"
            result_text += f"await client.setup()\n"
            result_text += f"result = await client.{method_name}({', '.join([f'{k}={repr(v)}' for k, v in params.items()])})\n"
            result_text += f"```"
            
            return Message(text=result_text)
            
        except Exception as e:
            error_message = f"❌ Failed to execute Weibo API call: {str(e)}"
            return Message(text=error_message)

    # Override to handle dynamic attributes
    def __getattr__(self, name: str) -> Any:
        # Handle dynamic parameter attributes
        if name.startswith('param_'):
            return getattr(self, name, None)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")