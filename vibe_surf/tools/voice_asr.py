import os
import pdb

import dashscope
from typing import Optional
from vibe_surf.logger import get_logger

logger = get_logger(__name__)

class Qwen3ASRFlash:
    def __init__(self, model="qwen3-asr-flash", api_key: Optional[str] = None):
        dashscope.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model

    def asr(self, wav_url: str, context=""):
        if not wav_url.startswith("http"):
            assert os.path.exists(wav_url), f"{wav_url} not exists!"
            wav_url = f"file://{wav_url}"

        try:
            messages = [
                {
                    "role": "system",
                    "content": [
                        {"text": context},
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"audio": wav_url},
                    ]
                }
            ]
            response = dashscope.MultiModalConversation.call(
                model=self.model,
                messages=messages,
                result_format="message",
                asr_options={
                    "enable_lid": True,
                    "enable_itn": False
                }
            )
            if response.status_code != 200:
                raise Exception(f"http status_code: {response.status_code} {response}")
            output = response['output']['choices'][0]
            if output['finish_reason'] not in ('stop', 'function_call'):
                logger.warning(f'{self.model} finish with error...\n{response}')
                return ""
            recog_text = output["message"]["content"][0]["text"]
            return recog_text
        except Exception as e:
            logger.warning(str(e))
            return ""