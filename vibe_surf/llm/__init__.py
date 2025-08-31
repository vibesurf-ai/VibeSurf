"""
Vibe Surf LLM implementations.

This module provides LLM implementations for vibe_surf, including:
- ChatOpenAICompatible: OpenAI-compatible implementation with Gemini schema fix support

Example usage:
    from vibe_surf.llm import ChatOpenAICompatible
    
    # Using with Azure OpenAI for Gemini models
    llm = ChatOpenAICompatible(
        model="gemini-2.5-pro",
        base_url="https://your-endpoint.openai.azure.com/",
        api_key="your-api-key",
        temperature=0,
    )
"""

from vibe_surf.llm.openai_compatible import ChatOpenAICompatible

__all__ = ['ChatOpenAICompatible']