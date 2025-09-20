import os
import pdb
import time
import random
import dashscope
import sys

sys.path.append(".")

from dotenv import load_dotenv

load_dotenv()


async def test_qwen3_asr_flash():
    from vibe_surf.tools.voice_asr import QwenASR

    qwen_asr = QwenASR(model="qwen3-asr-flash")
    asr_text = qwen_asr.asr(wav_url="./tmp/voices/qiji-10s.mp3")
    print(asr_text)


async def test_openai_asr_flash():
    from vibe_surf.tools.voice_asr import OpenAIASR

    openai_asr = OpenAIASR()
    asr_text = openai_asr.asr(wav_url="./tmp/voices/qiji-10s.mp3")
    print(asr_text)


async def test_gemini_asr_flash():
    from vibe_surf.tools.voice_asr import GeminiASR

    gemini_asr = GeminiASR()
    asr_text = gemini_asr.asr(wav_url="./tmp/voices/qiji-10s.mp3")
    print(asr_text)


if __name__ == "__main__":
    import asyncio

    # asyncio.run(test_qwen3_asr_flash())
    # asyncio.run(test_openai_asr_flash())
    asyncio.run(test_gemini_asr_flash())
