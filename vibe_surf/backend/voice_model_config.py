"""
Voice Model Configuration

Centralized configuration for all supported voice providers and their models.
"""

# Voice Providers and their supported models
VOICE_MODELS = {
    "qwen3-asr-flash": {
        "model_type": "asr",
        "requires_api_key": True,
    }
}