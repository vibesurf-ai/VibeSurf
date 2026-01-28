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
            info="JavaScript Code to run in this page. Leave empty if using JS File Path.",
            required=False,
            multiline=True
        ),
        MessageTextInput(
            name="js_file_path",
            display_name="JS File Path (Optional)",
            info="Path to .js file. Use this as alternative to direct code input to avoid paste issues.",
            required=False
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
            await self.browser_session._wait_for_stable_network()
            import json

            # Determine code source: file or direct input
            if self.js_file_path:
                # Read code from file
                import os
                if not os.path.exists(self.js_file_path):
                    raise FileNotFoundError(f"JavaScript file not found: {self.js_file_path}")
                with open(self.js_file_path, 'r', encoding='utf-8') as f:
                    js_code_source = f.read()
            elif self.js_code:
                # Use direct input
                js_code_source = self.js_code
            else:
                raise ValueError("Either 'JavaScript Code' or 'JS File Path' must be provided")

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
                    js_params = self._extract_js_function_params(js_code_source)

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

            # Clean the JavaScript code (same as in skill_code tool)
            js_code_cleaned = js_code_source.strip()

            # Remove markdown code blocks if present
            if js_code_cleaned.startswith('```javascript'):
                js_code_cleaned = js_code_cleaned.replace('```javascript', '').replace('```', '').strip()
            elif js_code_cleaned.startswith('```js'):
                js_code_cleaned = js_code_cleaned.replace('```js', '').replace('```', '').strip()
            elif js_code_cleaned.startswith('```'):
                js_code_cleaned = js_code_cleaned.replace('```', '').strip()

            # Normalize characters that might be corrupted during copy-paste
            # Replace smart quotes with regular quotes
            js_code_cleaned = js_code_cleaned.replace('"', '"').replace('"', '"')
            js_code_cleaned = js_code_cleaned.replace(''', "'").replace(''', "'")

            # Remove BOM if present
            if js_code_cleaned.startswith('\ufeff'):
                js_code_cleaned = js_code_cleaned[1:]

            # Normalize line endings to \n (in case of \r\n from Windows)
            js_code_cleaned = js_code_cleaned.replace('\r\n', '\n').replace('\r', '\n')

            # CRITICAL FIX: Repair broken escape sequences in string literals
            # When code passes through Langflow's frontend/backend JSON serialization,
            # escape sequences like '\n' inside JavaScript string literals may get
            # converted to actual newline characters, breaking the syntax.
            # We need to detect and fix this by re-escaping these characters.
            import re

            def fix_string_literals(code):
                """Fix actual newlines and tabs inside single/double quoted strings."""
                result = []
                i = 0
                while i < len(code):
                    char = code[i]

                    # Check if we're starting a string literal
                    if char in ('"', "'"):
                        quote = char
                        result.append(char)
                        i += 1

                        # Process the string content
                        while i < len(code):
                            char = code[i]

                            # Check for string end
                            if char == quote:
                                result.append(char)
                                i += 1
                                break

                            # Check for escape sequence (already properly escaped)
                            elif char == '\\' and i + 1 < len(code):
                                # Keep existing escape sequences as-is
                                result.append(char)
                                result.append(code[i + 1])
                                i += 2

                            # Fix actual newline/tab characters inside string
                            elif char == '\n':
                                result.append('\\n')  # Convert actual newline to \n
                                i += 1
                            elif char == '\t':
                                result.append('\\t')  # Convert actual tab to \t
                                i += 1
                            elif char == '\r':
                                result.append('\\r')  # Convert actual CR to \r
                                i += 1

                            else:
                                result.append(char)
                                i += 1

                    # Check for template literal (backtick strings can have real newlines)
                    elif char == '`':
                        # Template literals are allowed to have real newlines, keep as-is
                        result.append(char)
                        i += 1
                        while i < len(code):
                            char = code[i]
                            if char == '`' and (i == 0 or code[i-1] != '\\'):
                                result.append(char)
                                i += 1
                                break
                            result.append(char)
                            i += 1

                    else:
                        result.append(char)
                        i += 1

                return ''.join(result)

            js_code_cleaned = fix_string_literals(js_code_cleaned)

            # Execute JavaScript with or without arguments
            if not (js_code_cleaned.endswith('()') or js_code_cleaned.endswith('();')):
                if args:
                    # Convert args to JSON representation for safe passing
                    import json

                    arg_strs = [json.dumps(arg) for arg in args]
                    expression = f'({js_code_cleaned})({", ".join(arg_strs)})'
                else:
                    expression = f'({js_code_cleaned})()'
            else:
                expression = js_code_cleaned

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
        return self.browser_session
