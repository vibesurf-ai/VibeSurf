"""
LLM Factory utilities for creating LLM instances from profiles
"""

from typing import Optional
import logging
# Import LLM classes from browser_use and vibe_surf
from browser_use.llm import (
    BaseChatModel,
    ChatOpenAI, ChatAnthropic, ChatGoogle, ChatAzureOpenAI,
    ChatGroq, ChatOllama, ChatOpenRouter, ChatDeepSeek,
    ChatAWSBedrock, ChatAnthropicBedrock
)
from vibe_surf.llm import ChatOpenAICompatible

from ..llm_config import get_supported_providers, is_provider_supported

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


def create_llm_from_profile(llm_profile) -> BaseChatModel:
    """Create LLM instance from LLMProfile database record (dict or object)"""
    try:

        # Handle both dict and object access patterns
        def get_attr(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            else:
                return getattr(obj, key, default)

        provider = get_attr(llm_profile, 'provider')
        model = get_attr(llm_profile, 'model')
        api_key = get_attr(llm_profile, 'api_key')  # Should already be decrypted by queries
        base_url = get_attr(llm_profile, 'base_url')
        temperature = get_attr(llm_profile, 'temperature') or 0.7
        max_tokens = get_attr(llm_profile, 'max_tokens')
        top_p = get_attr(llm_profile, 'top_p')
        frequency_penalty = get_attr(llm_profile, 'frequency_penalty')
        seed = get_attr(llm_profile, 'seed')
        provider_config = get_attr(llm_profile, 'provider_config', {})

        # Validate provider
        if not is_provider_supported(provider):
            raise ValueError(f"Unsupported provider: {provider}. Supported: {get_supported_providers()}")

        # Define provider-specific parameter support
        provider_param_support = {
            "openai": ["temperature"],
            "anthropic": ["temperature"],
            "google": ["temperature"],
            "azure_openai": ["temperature"],
            "groq": ["temperature"],
            "ollama": [],
            "openrouter": ["temperature"],  # OpenRouter doesn't support max_tokens
            "deepseek": ["temperature"],
            "aws_bedrock": ["temperature"],
            "anthropic_bedrock": ["temperature"],
            "openai_compatible": ["temperature", "max_tokens"]
        }

        # Build common parameters based on provider support
        supported_params = provider_param_support.get(provider, [])
        common_params = {}

        if temperature is not None and "temperature" in supported_params:
            common_params["temperature"] = temperature
        if max_tokens is not None and "max_tokens" in supported_params:
            common_params["max_tokens"] = max_tokens
        if top_p is not None and "top_p" in supported_params:
            common_params["top_p"] = top_p
        if frequency_penalty is not None and "frequency_penalty" in supported_params:
            common_params["frequency_penalty"] = frequency_penalty
        if seed is not None and "seed" in supported_params:
            common_params["seed"] = seed

        # Add provider-specific config if available
        if provider_config:
            common_params.update(provider_config)

        # Create LLM instance based on provider
        if provider == "openai":
            params = {
                "model": model,
                "api_key": api_key,
                **common_params
            }
            if base_url:
                params["base_url"] = base_url
            return ChatOpenAI(**params)

        elif provider == "anthropic":
            return ChatAnthropic(
                model=model,
                api_key=api_key,
                **common_params
            )

        elif provider == "google":
            return ChatGoogle(
                model=model,
                api_key=api_key,
                **common_params
            )

        elif provider == "azure_openai":
            if not base_url:
                raise ValueError("Azure OpenAI requires base_url (azure_endpoint)")
            return ChatAzureOpenAI(
                model=model,
                api_version="2025-01-01-preview",
                api_key=api_key,
                azure_endpoint=base_url,
                **common_params
            )

        elif provider == "groq":
            return ChatGroq(
                model=model,
                api_key=api_key,
                **common_params
            )

        elif provider == "ollama":
            params = {
                "model": model,
                **common_params
            }
            if base_url:
                params["host"] = base_url
            else:
                params["host"] = "http://localhost:11434"  # Default Ollama URL
            return ChatOllama(**params)

        elif provider == "openrouter":
            return ChatOpenRouter(
                model=model,
                api_key=api_key,
                **common_params
            )

        elif provider == "deepseek":
            return ChatOpenAICompatible(
                model=model,
                base_url="https://api.deepseek.com",
                api_key=api_key,
                **common_params
            )

        elif provider == "aws_bedrock":
            params = {
                "model": model,
                "aws_access_key_id": api_key,  # AWS uses different auth
                **common_params
            }
            # Add AWS-specific parameters from provider_config
            if "aws_secret_access_key" in provider_config:
                params["aws_secret_access_key"] = provider_config["aws_secret_access_key"]
            if "aws_region" in provider_config:
                params["aws_region"] = provider_config["aws_region"]
            if 'aws_region' not in params:
                params["aws_region"] = "us-east-1"
            return ChatAWSBedrock(**params)

        elif provider == "anthropic_bedrock":
            params = {
                "model": model,
                "aws_access_key_id": api_key,  # AWS uses different auth
                **common_params
            }
            # Add AWS-specific parameters from provider_config
            if "aws_secret_access_key" in provider_config:
                params["aws_secret_access_key"] = provider_config["aws_secret_access_key"]
            if "region_name" in provider_config:
                params["region_name"] = provider_config["region_name"]
            return ChatAnthropicBedrock(**params)

        elif provider == "qwen":
            return ChatOpenAICompatible(
                model=model,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1" or base_url,
                api_key=api_key,
                **common_params
            )

        elif provider == "kimi":
            return ChatOpenAICompatible(
                model=model,
                base_url="https://api.moonshot.cn/v1" or base_url,
                api_key=api_key,
                **common_params
            )

        elif provider == "lm_studio":
            return ChatOpenAI(
                model=model,
                base_url="http://localhost:1234/v1" or base_url,
                api_key="lm_studio",
                **common_params
            )

        elif provider == "openai_compatible":
            if not base_url:
                raise ValueError("OpenAI Compatible provider requires base_url")
            return ChatOpenAICompatible(
                model=model,
                api_key=api_key,
                base_url=base_url,
                **common_params
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    except Exception as e:
        logger.error(f"Failed to create LLM from profile: {e}")
        raise RuntimeError(f"Failed to create LLM from profile: {str(e)}")


def validate_llm_configuration(provider: str, model: str, api_key: str, base_url: Optional[str] = None):
    """Validate LLM configuration parameters"""
    if not provider:
        raise ValueError("Provider is required")

    if not model:
        raise ValueError("Model is required")

    if not is_provider_supported(provider):
        raise ValueError(f"Unsupported provider: {provider}. Supported: {get_supported_providers()}")

    # Provider-specific validation
    from ..llm_config import get_provider_metadata
    metadata = get_provider_metadata(provider)

    if metadata.get("requires_api_key", True) and not api_key:
        raise ValueError(f"API key is required for provider: {provider}")

    if metadata.get("requires_base_url", False) and not base_url:
        raise ValueError(f"Base URL is required for provider: {provider}")

    return True


def get_llm_creation_parameters(provider: str):
    """Get the required and optional parameters for creating an LLM instance"""
    from ..llm_config import get_provider_metadata

    if not is_provider_supported(provider):
        raise ValueError(f"Unsupported provider: {provider}")

    metadata = get_provider_metadata(provider)

    required_params = ["model"]
    optional_params = ["temperature", "max_tokens", "top_p", "frequency_penalty", "seed"]

    if metadata.get("requires_api_key", True):
        required_params.append("api_key")

    if metadata.get("requires_base_url", False):
        required_params.append("base_url")
    elif metadata.get("supports_base_url", False):
        optional_params.append("base_url")

    # Special cases for AWS Bedrock
    if provider in ["aws_bedrock", "anthropic_bedrock"]:
        required_params.extend(["aws_secret_access_key", "region_name"])

    return {
        "required": required_params,
        "optional": optional_params,
        "metadata": metadata
    }
