"""
Qwen ASR Langflow Component

This component provides automatic speech recognition (ASR) functionality
using Qwen3-ASR-Flash API to transcribe audio/video files.
"""

import os
from pathlib import Path
from typing import Optional

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, SecretStrInput, BoolInput, Output
from vibe_surf.langflow.schema import Data
from vibe_surf.tools.aigc.qwen3_asr import Qwen3ASRProcessor
from vibe_surf.langflow.schema.message import Message

class QwenASRComponent(Component):
    display_name = "Qwen ASR"
    description = "Automatic Speech Recognition using Qwen3-ASR-Flash API"
    icon = "mic"
    name = "QwenASR"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="DashScope API Key",
            info="The DashScope API Key for Qwen3-ASR-Flash",
            required=True,
        ),
        MessageTextInput(
            name="file_path",
            display_name="Audio/Video File Path",
            info="Path to the audio or video file to transcribe",
            required=True,
        ),
        MessageTextInput(
            name="context",
            display_name="Context",
            info="Optional context text for better transcription accuracy",
            advanced=True,
        ),
        BoolInput(
            name="save_srt",
            display_name="Save SRT Subtitles",
            info="Whether to generate SRT subtitle file",
            value=True,
        ),
        MessageTextInput(
            name="output_dir",
            display_name="Output Directory",
            info="Optional output directory for results (default: same as input file)",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="text_output",
            display_name="Text Output",
            method="transcribe_audio",
        ),
    ]

    def transcribe_audio(self) -> Message:
        """Transcribe audio/video file using Qwen3-ASR-Flash"""
        
        if not self.api_key:
            raise ValueError("DashScope API Key is required")
        
        if not self.file_path:
            raise ValueError("File path is required")
        
        # Get file path from MessageText if needed
        file_path = self.file_path
        if isinstance(file_path, Data):
            file_path = file_path.get_text()
        
        # Resolve path
        resolved_path = self.resolve_path(file_path)
        
        # Validate file exists (for local files)
        if not resolved_path.startswith(("http://", "https://")) and not os.path.exists(resolved_path):
            raise FileNotFoundError(f"File not found: {resolved_path}")
        
        # Get optional parameters
        context = ""
        if hasattr(self, 'context') and self.context:
            context = self.context
            if isinstance(context, Data):
                context = context.get_text()
        
        output_dir = None
        if hasattr(self, 'output_dir') and self.output_dir:
            output_dir = self.output_dir
            if isinstance(output_dir, Data):
                output_dir = output_dir.get_text()
            output_dir = self.resolve_path(output_dir)
        
        # Initialize processor
        processor = Qwen3ASRProcessor(
            dashscope_api_key=self.api_key,
            silence=False
        )
        
        # Process audio
        try:
            result_path = processor.run(
                input_file=resolved_path,
                context=context,
                save_srt=self.save_srt,
                output_dir=output_dir
            )
            
            # Set status
            file_type = "SRT subtitle" if self.save_srt else "text"
            self.status = f"✓ Transcription complete: {result_path}"
            
            # Return path as Data
            return Message(text=result_path)
            
        except Exception as e:
            self.status = f"✗ ASR failed: {str(e)}"
            raise e