import asyncio
import json
import re
from typing import Any, List, Dict
from uuid import uuid4
from typing import Optional
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, MultilineInput, StrInput
from vibe_surf.langflow.io import BoolInput, IntInput, Output
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.langflow.schema.message import Message
import json

class BrowserEvaluateJavaScriptComponent(Component):
    display_name = "Evaluate JavaScript Code"
    description = "Browser evaluate JavaScript code"
    icon = "square-function"

    inputs = [
        HandleInput(
            name="browser_session",
            display_name="Browser Session",
            info="Browser Session defined by VibeSurf",
            input_types=["AgentBrowserSession"],
            required=True
        ),
        MultilineInput(
            name="js_code",
            display_name="JavaScript Code",
            info="JavaScript Code to run in this page",
            required=True,
            multiline=True
        ),
        MessageTextInput(
            name="func_params",
            display_name="Function Params in Json String(Optional)",
            info="Input Params(Json String) for js code function"
        )
    ]

    outputs = [
        Output(
            display_name="Browser Session",
            name="output_browser_session",
            method="pass_browser_session",
            types=["AgentBrowserSession"],
            group_outputs=True,
        ),
        Output(
            display_name="Evaluate Result",
            name="evaluate_result",
            method="browser_evaluate_result",
            types=["Message"],
            group_outputs=True,
        ),
    ]

    _operation_message: Optional[str] = None

    def _extract_js_function_params(self, js_code: str) -> List[str]:
        """Extract parameter names from JavaScript function definition."""
        try:
            # Match function declarations: function name(param1, param2) or (param1, param2) =>
            # Also match: function(param1, param2) and async function(param1, param2)
            patterns = [
                r'function\s*\w*\s*\(([^)]*)\)',  # function name(params) or function(params)
                r'\(([^)]*)\)\s*=>', # (params) => arrow function
                r'async\s+function\s*\w*\s*\(([^)]*)\)',  # async function
                r'async\s*\(([^)]*)\)\s*=>', # async (params) =>
            ]
            
            for pattern in patterns:
                match = re.search(pattern, js_code.strip())
                if match:
                    params_str = match.group(1).strip()
                    if not params_str:
                        return []
                    # Split by comma and clean up parameter names
                    params = [param.strip().split('=')[0].strip() for param in params_str.split(',')]
                    # Filter out empty strings and destructuring patterns
                    params = [p for p in params if p and not p.startswith('{') and not p.startswith('[')]
                    return params
            
            return []
        except Exception as e:
            print(f"Error extracting JS function parameters: {e}")
            return []

    def _match_params_to_args(self, js_params: List[str], func_params_dict: Dict[str, Any]) -> List[Any]:
        """Match JavaScript function parameters with provided dictionary values."""
        args = []
        for param in js_params:
            if param in func_params_dict:
                args.append(func_params_dict[param])
            else:
                # If parameter not found, append None as placeholder
                args.append(None)
        return args

    async def browser_evaluate_result(self) :
        try:
            import json
            # Parse func_params if provided
            args = []
            if self.func_params:
                try:
                    # Parse JSON string to dictionary
                    try:
                        func_params_dict = json.loads(self.func_params)
                    except Exception as e:
                        from json_repair import repair_json
                        func_params_dict = json.loads(repair_json(self.func_params))
                    
                    # Extract parameter names from JavaScript code
                    js_params = self._extract_js_function_params(self.js_code)
                    
                    if js_params:
                        # Match parameters and create ordered args list
                        args = self._match_params_to_args(js_params, func_params_dict)
                        self.log(f"JavaScript params: {js_params}")
                        self.log(f"Matched args: {args}")
                    else:
                        # If no parameters found in JS, try to use values in original order
                        args = list(func_params_dict.values())
                        self.log(f"No JS params found, using values in order: {args}")
                        
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in func_params: {e}")
                except Exception as e:
                    raise ValueError(f"Error processing func_params: {e}")
            
            # Execute JavaScript with or without arguments
            if not (self.js_code.endswith('()') or self.js_code.endswith('();')):
                if args:
                    # Convert args to JSON representation for safe passing
                    import json

                    arg_strs = [json.dumps(arg) for arg in args]
                    expression = f'({self.js_code})({", ".join(arg_strs)})'
                else:
                    expression = f'({self.js_code})()'
            else:
                expression = self.js_code

            cdp_session = await self.browser_session.get_or_create_cdp_session()
            result = await cdp_session.cdp_client.send.Runtime.evaluate(
                params={'expression': expression, 'returnByValue': True, 'awaitPromise': True},
                session_id=cdp_session.session_id,
            )

            if 'exceptionDetails' in result:
                raise RuntimeError(f'JavaScript evaluation failed: {result["exceptionDetails"]}')

            value = result.get('result', {}).get('value')

            # Always return string representation
            if value is None:
                return ''
            elif isinstance(value, str):
                return value
            else:
                try:
                    return json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                except (TypeError, ValueError):
                    return str(value)
                
            self.status = self._operation_message = str(result)
            return Message(text=str(result))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    async def pass_browser_session(self) -> AgentBrowserSession:
        if not self._operation_message:
            await self.browser_evaluate_result()
        return self.browser_session
