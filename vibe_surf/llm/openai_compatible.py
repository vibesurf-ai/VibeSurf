"""
OpenAI-compatible LLM implementation with Gemini schema fix support.

This module provides an OpenAI-compatible chat model that automatically applies
Gemini-specific schema fixes when using Gemini models through OpenAI-compatible APIs
like ChatAzureOpenAI, ChatOpenRouter, etc.

Example usage:
    from vibe_surf.llm.openai_compatible import ChatOpenAICompatible
    
    # Using with Azure OpenAI
    llm = ChatOpenAICompatible(
        model="gemini-2.5-pro",
        base_url="https://your-endpoint.openai.azure.com/",
        api_key="your-api-key",
        temperature=0,
    )
    
    # Using with OpenRouter
    llm = ChatOpenAICompatible(
        model="gemini-2.5-pro", 
        base_url="https://openrouter.ai/api/v1",
        api_key="your-openrouter-key",
        temperature=0,
    )
"""
import pdb
from dataclasses import dataclass
from typing import Any, TypeVar, overload
from pydantic import BaseModel

from browser_use.llm.openai.chat import ChatOpenAI
from browser_use.llm.messages import BaseMessage
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar, overload

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionContentPartTextParam
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.shared.chat_model import ChatModel
from openai.types.shared_params.reasoning_effort import ReasoningEffort
from openai.types.shared_params.response_format_json_schema import JSONSchema, ResponseFormatJSONSchema
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError
from browser_use.llm.messages import BaseMessage
from browser_use.llm.openai.serializer import OpenAIMessageSerializer
from browser_use.llm.schema import SchemaOptimizer
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage

from json_repair import repair_json

T = TypeVar('T', bound=BaseModel)

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChatOpenAICompatible(ChatOpenAI):
    """
    OpenAI-compatible chat model with automatic schema fix support for Gemini, Kimi, and Qwen models.
    
    This class extends browser_use's ChatOpenAI to automatically detect special models
    and apply the necessary schema fixes to work with OpenAI-compatible APIs.
    
    Supported models:
    - Gemini models: Removes 'additionalProperties', 'title', 'default' and resolves $ref
    - Kimi/Moonshot models: Removes 'min_items', 'max_items', 'minItems', 'maxItems', 'default' with anyOf
    - Qwen models: Ensures 'json' keyword is present in messages when using response_format
    
    The class automatically detects the model type and applies appropriate fixes.
    """

    max_completion_tokens: int | None = 8192

    def _is_gemini_model(self) -> bool:
        """Check if the current model is a Gemini model."""
        return str(self.model).lower().startswith('gemini')

    def _is_kimi_model(self) -> bool:
        """Check if the current model is a Kimi/Moonshot model."""
        model_str = str(self.model).lower()
        return 'kimi' in model_str or 'moonshot' in model_str

    def _is_deepseek_model(self) -> bool:
        """Check if the current model is a Kimi/Moonshot model."""
        model_str = str(self.model).lower()
        return 'deepseek' in model_str
    
    def _is_qwen_model(self) -> bool:
        """Check if the current model is a Qwen model."""
        model_str = str(self.model).lower()
        return 'qwen' in model_str

    def _fix_gemini_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a Pydantic model to a Gemini-compatible schema.
        
        This function removes unsupported properties like 'additionalProperties' and resolves
        $ref references that Gemini doesn't support.
        
        Adapted from browser_use.llm.google.chat.ChatGoogle._fix_gemini_schema
        """

        # Handle $defs and $ref resolution
        if '$defs' in schema:
            defs = schema.pop('$defs')

            def resolve_refs(obj: Any) -> Any:
                if isinstance(obj, dict):
                    if '$ref' in obj:
                        ref = obj.pop('$ref')
                        ref_name = ref.split('/')[-1]
                        if ref_name in defs:
                            # Replace the reference with the actual definition
                            resolved = defs[ref_name].copy()
                            # Merge any additional properties from the reference
                            for key, value in obj.items():
                                if key != '$ref':
                                    resolved[key] = value
                            return resolve_refs(resolved)
                        return obj
                    else:
                        # Recursively process all dictionary values
                        return {k: resolve_refs(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [resolve_refs(item) for item in obj]
                return obj

            schema = resolve_refs(schema)

        # Remove unsupported properties
        def clean_schema(obj: Any) -> Any:
            if isinstance(obj, dict):
                # Remove unsupported properties
                cleaned = {}
                for key, value in obj.items():
                    if key not in ['additionalProperties', 'title', 'default']:
                        cleaned_value = clean_schema(value)
                        # Handle empty object properties - Gemini doesn't allow empty OBJECT types
                        if (
                                key == 'properties'
                                and isinstance(cleaned_value, dict)
                                and len(cleaned_value) == 0
                                and isinstance(obj.get('type', ''), str)
                                and obj.get('type', '').upper() == 'OBJECT'
                        ):
                            # Convert empty object to have at least one property
                            cleaned['properties'] = {'_placeholder': {'type': 'string'}}
                        else:
                            cleaned[key] = cleaned_value

                # If this is an object type with empty properties, add a placeholder
                if (
                        isinstance(cleaned.get('type', ''), str)
                        and cleaned.get('type', '').upper() == 'OBJECT'
                        and 'properties' in cleaned
                        and isinstance(cleaned['properties'], dict)
                        and len(cleaned['properties']) == 0
                ):
                    cleaned['properties'] = {'_placeholder': {'type': 'string'}}

                return cleaned
            elif isinstance(obj, list):
                return [clean_schema(item) for item in obj]
            return obj

        return clean_schema(schema)

    def _fix_kimi_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a Pydantic model to a Kimi/Moonshot-compatible schema.
        
        This function removes unsupported keywords like 'min_items' that Moonshot API doesn't support.
        
        Args:
            schema: The original JSON schema
            
        Returns:
            A cleaned schema compatible with Moonshot API
        """

        def clean_schema(obj: Any) -> Any:
            if isinstance(obj, dict):
                cleaned = {}
                has_any_of = 'anyOf' in obj
                
                for key, value in obj.items():
                    # Remove unsupported keywords for Moonshot
                    if key in ['min_items', 'minItems']:
                        continue
                    # Remove 'default' when 'anyOf' is present (Moonshot restriction)
                    elif key == 'default' and has_any_of:
                        continue
                    # Remove other problematic keywords
                    elif key in ['title', 'additionalProperties']:
                        continue
                    else:
                        cleaned[key] = clean_schema(value)
                return cleaned
            elif isinstance(obj, list):
                return [clean_schema(item) for item in obj]
            return obj

        return clean_schema(schema)

    async def ainvoke(
            self, messages: list[BaseMessage], output_format: type[T] | None = None
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """
        Invoke the model with the given messages.

        Args:
            messages: List of chat messages
            output_format: Optional Pydantic model class for structured output

        Returns:
            Either a string response or an instance of output_format
        """
        # If this is not a special model or no structured output is requested,
        # use the parent implementation directly
        if self._is_qwen_model() or self._is_kimi_model() or self._is_deepseek_model() :
            self.add_schema_to_system_prompt = True

        if not (self._is_gemini_model() or self._is_kimi_model() or self._is_qwen_model() or self._is_deepseek_model()) or output_format is None:
            return await super().ainvoke(messages, output_format)
        openai_messages = OpenAIMessageSerializer.serialize_messages(messages)

        try:
            model_params: dict[str, Any] = {}

            if self.temperature is not None:
                model_params['temperature'] = self.temperature

            if self.frequency_penalty is not None:
                model_params['frequency_penalty'] = self.frequency_penalty

            if self.max_completion_tokens is not None:
                model_params['max_completion_tokens'] = self.max_completion_tokens
                model_params['max_tokens'] = self.max_completion_tokens

            if self.top_p is not None:
                model_params['top_p'] = self.top_p

            if self.seed is not None:
                model_params['seed'] = self.seed

            if self.service_tier is not None:
                model_params['service_tier'] = self.service_tier

            if self.reasoning_models and any(str(m).lower() in str(self.model).lower() for m in self.reasoning_models):
                model_params['reasoning_effort'] = self.reasoning_effort
                del model_params['temperature']
                del model_params['frequency_penalty']

            if output_format is None:
                # Return string response
                response = await self.get_client().chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    **model_params,
                )

                usage = self._get_usage(response)
                return ChatInvokeCompletion(
                    completion=response.choices[0].message.content or '',
                    usage=usage,
                )

            else:
                # Apply appropriate schema fix based on model type
                original_schema = SchemaOptimizer.create_optimized_json_schema(output_format)
                if self._is_gemini_model():
                    logger.debug(f"🔧 Applying Gemini schema fixes for model: {self.model}")
                    fixed_schema = self._fix_gemini_schema(original_schema)
                elif self._is_kimi_model():
                    logger.debug(f"🔧 Applying Kimi/Moonshot schema fixes for model: {self.model}")
                    fixed_schema = self._fix_kimi_schema(original_schema)
                else:
                    fixed_schema = original_schema
                response_format: JSONSchema = {
                    'name': 'agent_output',
                    'strict': True,
                    'schema': fixed_schema,
                }

                # Add JSON schema to system prompt if requested
                if self.add_schema_to_system_prompt and openai_messages and openai_messages[0]['role'] == 'system':
                    schema_text = "Your response must return JSON with followed format:\n"
                    schema_text += f'\n<json_schema>\n{response_format}\n</json_schema>'
                    if isinstance(openai_messages[0]['content'], str):
                        openai_messages[0]['content'] += schema_text
                    elif isinstance(openai_messages[0]['content'], Iterable):
                        openai_messages[0]['content'] = list(openai_messages[0]['content']) + [
                            ChatCompletionContentPartTextParam(text=schema_text, type='text')
                        ]

                # Return structured response
                if self.add_schema_to_system_prompt:
                    response = await self.get_client().chat.completions.create(
                        model=self.model,
                        messages=openai_messages,
                        response_format={
                            'type': 'json_object'
                        },
                        **model_params,
                    )
                else:
                    response = await self.get_client().chat.completions.create(
                        model=self.model,
                        messages=openai_messages,
                        response_format=ResponseFormatJSONSchema(json_schema=response_format, type='json_schema'),
                        **model_params,
                    )

                if response.choices[0].message.content is None:
                    raise ModelProviderError(
                        message='Failed to parse structured output from model response',
                        status_code=500,
                        model=self.name,
                    )

                usage = self._get_usage(response)
                output_content = response.choices[0].message.content
                try:
                    parsed = output_format.model_validate_json(output_content)
                except Exception as e:
                    repair_content = repair_json(output_content)
                    parsed = output_format.model_validate_json(repair_content)

                return ChatInvokeCompletion(
                    completion=parsed,
                    usage=usage,
                )

        except RateLimitError as e:
            error_message = e.response.json().get('error', {})
            error_message = (
                error_message.get('message', 'Unknown model error') if isinstance(error_message,
                                                                                  dict) else error_message
            )
            raise ModelProviderError(
                message=error_message,
                status_code=e.response.status_code,
                model=self.name,
            ) from e

        except APIConnectionError as e:
            raise ModelProviderError(message=str(e), model=self.name) from e

        except APIStatusError as e:
            try:
                error_message = e.response.json().get('error', {})
            except Exception:
                error_message = e.response.text
            error_message = (
                error_message.get('message', 'Unknown model error') if isinstance(error_message,
                                                                                  dict) else error_message
            )
            raise ModelProviderError(
                message=error_message,
                status_code=e.response.status_code,
                model=self.name,
            ) from e

        except Exception as e:
            raise ModelProviderError(message=str(e), model=self.name) from e
