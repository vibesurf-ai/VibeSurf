import asyncio
import base64
import logging
import os
import sys
import pdb

sys.path.append(".")

from dotenv import load_dotenv

load_dotenv()


def qwen3_asr():
    from vibe_surf.tools.aigc.qwen3_asr import Qwen3ASRProcessor
    from vibe_surf.tools.aigc.qwen_mt import QwenMTProcessor

    asr_processor = Qwen3ASRProcessor(dashscope_api_key=os.getenv("ALIBABA_API_KEY"))
    mt_processor = QwenMTProcessor(dashscope_api_key=os.getenv("ALIBABA_API_KEY"))
    video_path = r"E:\AIBrowser\VibeSurf\tmp\vibesurf_workspace\workflows\downloads\OcgSDPexsCt4ZYZc.mp4"

    srt_path = asr_processor.run(video_path)
    target_srt_path = mt_processor.translate_srt(srt_path, target_language="zh_tw")

if __name__ == '__main__':
    qwen3_asr()