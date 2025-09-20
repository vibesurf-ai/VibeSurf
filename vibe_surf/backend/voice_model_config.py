"""
Voice Model Configuration

Centralized configuration for all supported voice providers and their models.
"""

# Voice Providers and their supported models
VOICE_MODELS = {
    "qwen-asr": {
        "model_type": "asr",
        "requires_api_key": True,
        "provider": "qwen",
    },
    "openai-asr": {
        "model_type": "asr",
        "requires_api_key": True,
        "provider": "openai",
        "supports_base_url": True,
    },
    "gemini-asr": {
        "model_type": "asr",
        "requires_api_key": True,
        "provider": "gemini",
    }
}