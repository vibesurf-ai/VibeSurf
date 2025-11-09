"""
LLM Provider Configuration

Centralized configuration for all supported LLM providers and their models.
"""

# LLM Providers and their supported models
LLM_PROVIDERS = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1"
        "gpt-4.1-mini",
        "gpt-5",
        "gpt-5-mini",
    ],
    "anthropic": [
        "claude-opus-4-1-20250805",
        "claude-sonnet-4-20250514",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-haiku-20241022"
    ],
    "google": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ],
    "kimi": [
        "kimi-k2-0905-preview",
        "kimi-k2-0711-preview",
        "kimi-k2-turbo-preview",
        "kimi-k2-thinking",
        "kimi-k2-thinking-turbo"
    ],
    "qwen": [
        "qwen-flash",
        "qwen-plus",
        "qwen3-vl-plus",
        "qwen3-vl-flash"
    ],
    "azure_openai": [
        "gpt-4o",
        "gpt-4o-mini",
    ],
    "groq": [
        "moonshotai/kimi-k2-instruct",
        "deepseek-r1-distill-llama-70b",
        "qwen/qwen3-32b",
    ],
    "ollama": [
        "deepseek-r1:14b",
        "gpt-oss:20b",
        "qwen3:latest",
    ],
    "openrouter": [
        "deepseek/deepseek-chat-v3.1",
        "qwen/qwen3-235b-a22b-thinking-2507",
        "moonshotai/kimi-k2",
        "z-ai/glm-4.5"
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-reasoner"
    ],
    "aws_bedrock": [
        "anthropic.claude-opus-4-1-20250805-v1:0",
        "anthropic.claude-opus-4-20250514-v1:0",
        "anthropic.claude-sonnet-4-20250514-v1:0",
        "anthropic.claude-3-7-sonnet-20250219-v1:0",
        "anthropic.claude-3-5-haiku-20241022-v1:0",
    ],
    "anthropic_bedrock": [
    ],
    "openai_compatible": [
    ],
    "lm_studio":[
        "qwen/qwen3-vl-8b",
        "qwen/qwen3-vl-30b",
        "qwen/qwen3-14b",
        "openai/gpt-oss-20b"
    ]
}

# Provider metadata
PROVIDER_METADATA = {
    "openai": {
        "display_name": "OpenAI",
        "requires_api_key": True,
        "supports_base_url": False,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": "gpt-4.1-mini"
    },
    "anthropic": {
        "display_name": "Anthropic",
        "requires_api_key": True,
        "supports_base_url": False,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": "claude-3-7-sonnet-20250219"
    },
    "google": {
        "display_name": "Google Gemini",
        "requires_api_key": True,
        "supports_base_url": False,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": "gemini-2.5-flash"
    },
    "azure_openai": {
        "display_name": "Azure OpenAI",
        "requires_api_key": True,
        "requires_base_url": True,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": "gpt-4o-mini"
    },
    "groq": {
        "display_name": "Groq",
        "requires_api_key": True,
        "supports_base_url": False,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": "moonshotai/kimi-k2-instruct"
    },
    "ollama": {
        "display_name": "Ollama",
        "requires_api_key": False,
        "requires_base_url": True,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": "qwen/qwen3-32b",
        "default_base_url": "http://localhost:11434"
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "requires_api_key": True,
        "supports_base_url": False,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": "moonshotai/kimi-k2",
        "base_url": "https://openrouter.ai/api/v1"
    },
    "deepseek": {
        "display_name": "DeepSeek",
        "requires_api_key": True,
        "supports_base_url": False,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": "deepseek-chat"
    },
    "aws_bedrock": {
        "display_name": "AWS Bedrock",
        "requires_api_key": True,
        "supports_base_url": False,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": "anthropic.claude-3-7-sonnet-20250219-v1:0"
    },
    "anthropic_bedrock": {
        "display_name": "Anthropic via AWS Bedrock",
        "requires_api_key": True,
        "supports_base_url": False,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": ""
    },
    "openai_compatible": {
        "display_name": "OpenAI Compatible",
        "requires_api_key": True,
        "requires_base_url": True,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": ""
    },
    "qwen": {
        "display_name": "Qwen",
        "requires_api_key": True,
        "requires_base_url": False,
        "supports_tools": True,
        "supports_vision": False,
        "default_model": ""
    },
    "kimi": {
        "display_name": "Kimi",
        "requires_api_key": True,
        "requires_base_url": False,
        "supports_tools": True,
        "supports_vision": False,
        "default_model": ""
    },
    "lm_studio": {
        "display_name": "LM Studio",
        "requires_api_key": False,
        "requires_base_url": False,
        "supports_tools": True,
        "supports_vision": True,
        "default_model": ""
    }
}


def get_supported_providers():
    """Get list of all supported provider names"""
    return list(LLM_PROVIDERS.keys())


def get_provider_models(provider_name: str):
    """Get list of models for a specific provider"""
    return LLM_PROVIDERS.get(provider_name, [])


def get_provider_metadata(provider_name: str):
    """Get metadata for a specific provider"""
    return PROVIDER_METADATA.get(provider_name, {})


def is_provider_supported(provider_name: str):
    """Check if a provider is supported"""
    return provider_name in LLM_PROVIDERS


def get_default_model(provider_name: str):
    """Get default model for a provider"""
    metadata = get_provider_metadata(provider_name)
    return metadata.get("default_model", "")
