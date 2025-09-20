import os
import pdb

import dashscope
from openai import OpenAI
from google import genai
from typing import Optional
from vibe_surf.logger import get_logger

logger = get_logger(__name__)

class QwenASR:
    def __init__(self, model="qwen3-asr-flash", api_key: Optional[str] = None):
        dashscope.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model or "qwen3-asr-flash"

    def asr(self, wav_url: str):
        if not wav_url.startswith("http"):
            assert os.path.exists(wav_url), f"{wav_url} not exists!"
            wav_url = f"file://{wav_url}"

        try:
            messages = [
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


class OpenAIASR:
    def __init__(self, model="whisper-1", api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_ENDPOINT")
        self.model = model or "whisper-1"
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def asr(self, wav_url: str):
        try:
            # Handle file path
            if wav_url.startswith("file://"):
                file_path = wav_url[7:]  # Remove file:// prefix
            elif not wav_url.startswith("http"):
                file_path = wav_url
            else:
                raise ValueError("OpenAI Whisper ASR only supports local files")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found: {file_path}")
            
            # Open and transcribe the audio file
            with open(file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text"
                )
            
            return transcript if isinstance(transcript, str) else transcript.text
        except Exception as e:
            logger.warning(f"OpenAI Whisper ASR error: {str(e)}")
            return ""


class GeminiASR:
    def __init__(self, model="gemini-2.5-flash", api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model = model or "gemini-2.5-flash"
        if not self.api_key:
            raise ValueError("Google API key is required for Gemini ASR")
        
        # Initialize the genai client
        self.client = genai.Client(api_key=self.api_key)

    def asr(self, wav_url: str):
        try:
            # Handle file path
            if wav_url.startswith("file://"):
                file_path = wav_url[7:]  # Remove file:// prefix
            elif not wav_url.startswith("http"):
                file_path = wav_url
            else:
                raise ValueError("Gemini ASR only supports local files")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found: {file_path}")
            
            # Upload the audio file using the client
            audio_file = self.client.files.upload(file=file_path)
            
            # Generate content with the audio file
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    "Please transcribe the audio to text. Only return the transcribed text without any additional commentary.",
                    audio_file
                ]
            )
            
            return response.text if response.text else ""
        except Exception as e:
            logger.warning(f"Gemini ASR error: {str(e)}")
            return ""