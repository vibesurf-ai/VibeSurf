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

from dataclasses import dataclass
from typing import Any, TypeVar, overload
from pydantic import BaseModel

from browser_use.llm.openai.chat import ChatOpenAI
from browser_use.llm.messages import BaseMessage
from browser_use.llm.schema import SchemaOptimizer
from browser_use.llm.views import ChatInvokeCompletion

T = TypeVar('T', bound=BaseModel)


@dataclass
class ChatOpenAICompatible(ChatOpenAI):
    """
    OpenAI-compatible chat model with automatic Gemini schema fix support.
    
    This class extends browser_use's ChatOpenAI to automatically detect Gemini models
    and apply the necessary schema fixes to work with OpenAI-compatible APIs.
    
    When a model name starts with 'gemini', this class will automatically apply
    the schema transformations required by Gemini models to prevent validation errors
    like "Unable to submit request because one or more response schemas specified 
    other fields alongside any_of".
    """
    
    def _is_gemini_model(self) -> bool:
        """Check if the current model is a Gemini model."""
        return str(self.model).lower().startswith('gemini')
    
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
    
    @overload
    async def ainvoke(self, messages: list[BaseMessage], output_format: None = None) -> ChatInvokeCompletion[str]: ...
    
    @overload  
    async def ainvoke(self, messages: list[BaseMessage], output_format: type[T]) -> ChatInvokeCompletion[T]: ...
    
    async def ainvoke(
        self, messages: list[BaseMessage], output_format: type[T] | None = None
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """
        Invoke the model with the given messages.
        
        Automatically applies Gemini schema fixes when using Gemini models.
        
        Args:
            messages: List of chat messages
            output_format: Optional Pydantic model class for structured output
            
        Returns:
            Either a string response or an instance of output_format
        """
        
        # If this is not a Gemini model or no structured output is requested,
        # use the parent implementation directly
        if not self._is_gemini_model() or output_format is None:
            return await super().ainvoke(messages, output_format)
        
        # For Gemini models with structured output, we need to intercept and fix the schema
        from browser_use.llm.openai.serializer import OpenAIMessageSerializer
        from browser_use.llm.exceptions import ModelProviderError
        from openai.types.shared_params.response_format_json_schema import JSONSchema, ResponseFormatJSONSchema
        from typing import Any
        from collections.abc import Iterable
        from openai.types.chat import ChatCompletionContentPartTextParam
        
        openai_messages = OpenAIMessageSerializer.serialize_messages(messages)
        
        try:
            model_params: dict[str, Any] = {}
            
            if self.temperature is not None:
                model_params['temperature'] = self.temperature
            
            if self.frequency_penalty is not None:
                model_params['frequency_penalty'] = self.frequency_penalty
            
            if self.max_completion_tokens is not None:
                model_params['max_completion_tokens'] = self.max_completion_tokens
            
            if self.top_p is not None:
                model_params['top_p'] = self.top_p
            
            if self.seed is not None:
                model_params['seed'] = self.seed
            
            if self.service_tier is not None:
                model_params['service_tier'] = self.service_tier
            
            # Create the JSON schema and apply Gemini fixes
            original_schema = SchemaOptimizer.create_optimized_json_schema(output_format)
            fixed_schema = self._fix_gemini_schema(original_schema)
            
            response_format: JSONSchema = {
                'name': 'agent_output',
                'strict': True,
                'schema': fixed_schema,
            }
            
            # Add JSON schema to system prompt if requested
            if self.add_schema_to_system_prompt and openai_messages and openai_messages[0]['role'] == 'system':
                schema_text = f'\n<json_schema>\n{response_format}\n</json_schema>'
                if isinstance(openai_messages[0]['content'], str):
                    openai_messages[0]['content'] += schema_text
                elif isinstance(openai_messages[0]['content'], Iterable):
                    openai_messages[0]['content'] = list(openai_messages[0]['content']) + [
                        ChatCompletionContentPartTextParam(text=schema_text, type='text')
                    ]
            
            # Make the API call with the fixed schema
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
            
            parsed = output_format.model_validate_json(response.choices[0].message.content)
            
            return ChatInvokeCompletion(
                completion=parsed,
                usage=usage,
            )
            
        except Exception as e:
            # Let parent class handle all exception types
            raise ModelProviderError(message=str(e), model=self.name) from e