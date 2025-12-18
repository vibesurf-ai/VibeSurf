"""
Qwen Machine Translation (MT) Processor

This module provides an interface to translate text using Qwen-MT models
via DashScope API with OpenAI-compatible interface.
"""

import os
import re
import srt
from typing import Optional, Literal, List, Tuple
from openai import OpenAI


# Supported models
QwenMTModel = Literal["qwen-mt-plus", "qwen-mt-flash", "qwen-mt-turbo", "qwen-mt-lite"]

# Token limit for Qwen-MT models
MAX_TOKENS = 8192
# Conservative estimate: ~2 characters per token for mixed Chinese/English
CHARS_PER_TOKEN = 2
MAX_CHARS_PER_REQUEST = MAX_TOKENS * CHARS_PER_TOKEN


class QwenMTProcessor:
    """
    Qwen Machine Translation Processor
    
    This class provides an interface to translate text using Qwen-MT models.
    Automatically handles long text by splitting into semantic paragraphs.
    
    Example:
        >>> processor = QwenMTProcessor(dashscope_api_key="your_api_key")
        >>> result = processor.run(
        ...     text="Hello, world!",
        ...     target_language="中文"
        ... )
        >>> print(result)
        你好，世界！
        
        >>> # Translate SRT file
        >>> srt_path = processor.translate_srt(
        ...     srt_file="video.srt",
        ...     target_language="Chinese"
        ... )
    """
    
    def __init__(
        self,
        dashscope_api_key: Optional[str] = None,
        model: QwenMTModel = "qwen-mt-plus",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        source_lang: str = "auto"
    ):
        """
        Initialize QwenMTProcessor
        
        Args:
            dashscope_api_key: DashScope API key (if not provided, uses DASHSCOPE_API_KEY env var)
            model: Model name, options:
                - "qwen-mt-plus": Best quality (supports 92 languages)
                - "qwen-mt-flash": Balanced (supports 92 languages)
                - "qwen-mt-turbo": Fast (supports 92 languages)
                - "qwen-mt-lite": Most economical (supports 31 languages)
            base_url: API base URL
                - Beijing: https://dashscope.aliyuncs.com/compatible-mode/v1
                - Singapore: https://dashscope-intl.aliyuncs.com/compatible-mode/v1
            source_lang: Source language code or "auto" for auto-detection
                - Use "auto" for uncertain source languages (e.g., social media)
                - Use specific code for fixed languages (e.g., "zh", "en")
        """
        api_key = dashscope_api_key or os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError(
                "Please set DASHSCOPE_API_KEY as an environment variable, "
                "or pass it to the constructor"
            )
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.source_lang = source_lang
    
    def run(
        self,
        text: str,
        target_language: str,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        Translate text to target language
        
        Automatically splits long text into semantic paragraphs to stay within
        the 8192 token limit while preserving context.
        
        Args:
            text: Text to translate
            target_language: Target language (can be language name or code)
                - Examples: "Chinese", "English", "zh", "en", "日本語"
            custom_prompt: Optional custom prompt for domain-specific translation
                - Use {target_language} placeholder for target language
                - Use {text_to_translate} placeholder for the text
                
        Returns:
            str: Translated text
        """
        # Split text into paragraphs for semantic preservation
        paragraphs = self._split_into_paragraphs(text)
        
        # Group paragraphs into batches within token limit
        batches = self._group_paragraphs_into_batches(paragraphs)
        
        # Translate each batch
        translated_batches = []
        for batch_paragraphs in batches:
            batch_text = '\n\n'.join(batch_paragraphs)
            translated = self._translate_batch(batch_text, target_language, custom_prompt)
            translated_batches.append(translated)
        
        # Join translated batches
        return '\n\n'.join(translated_batches)
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs while preserving semantic integrity
        
        Args:
            text: Input text
            
        Returns:
            List of paragraph strings
        """
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Clean up and filter empty paragraphs
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        return paragraphs
    
    def _group_paragraphs_into_batches(
        self,
        paragraphs: List[str]
    ) -> List[List[str]]:
        """
        Group paragraphs into batches within token limit
        
        Args:
            paragraphs: List of paragraph strings
            
        Returns:
            List of batches, where each batch is a list of paragraphs
        """
        batches = []
        current_batch = []
        current_chars = 0
        
        for para in paragraphs:
            para_chars = len(para)
            
            # If single paragraph exceeds limit, keep it as separate batch
            if para_chars > MAX_CHARS_PER_REQUEST:
                # Save current batch if not empty
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_chars = 0
                
                # Add oversized paragraph as its own batch
                batches.append([para])
                continue
            
            # Check if adding this paragraph would exceed limit
            # Add 2 for the '\n\n' separator
            if current_chars + para_chars + 2 > MAX_CHARS_PER_REQUEST:
                # Save current batch and start new one
                batches.append(current_batch)
                current_batch = [para]
                current_chars = para_chars
            else:
                # Add to current batch
                current_batch.append(para)
                current_chars += para_chars + 2
        
        # Don't forget the last batch
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _translate_batch(
        self,
        text: str,
        target_language: str,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        Translate a single batch of text
        
        Args:
            text: Text to translate (single batch)
            target_language: Target language
            custom_prompt: Optional custom prompt
            
        Returns:
            Translated text
        """
        # Build prompt
        if custom_prompt:
            prompt = custom_prompt.format(
                target_language=target_language,
                text_to_translate=text
            )
        else:
            # Simple default prompt
            prompt = f"Translate the following text to {target_language}:\n\n{text}"
        
        # Prepare messages
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Call API
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        
        # Extract translation result
        translation_result = completion.choices[0].message.content
        return translation_result.strip()
    
    def translate_srt(
        self,
        srt_file: str,
        target_language: str,
        output_file: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        Translate SRT subtitle file with timestamp preservation
        
        Translates subtitles in batches to preserve semantic context while
        maintaining original timestamps.
        
        Args:
            srt_file: Path to input SRT file
            target_language: Target language
            output_file: Path to output SRT file (default: input_file.{target_language}.srt)
            custom_prompt: Optional custom prompt for translation
            
        Returns:
            str: Path to translated SRT file
        """
        # Read SRT file
        with open(srt_file, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        # Parse SRT
        subtitles = list(srt.parse(srt_content))
        
        # Group subtitles into batches for translation
        subtitle_batches = self._group_subtitles_into_batches(subtitles)
        
        # Translate each batch
        for batch_indices, batch_subtitles in subtitle_batches:
            # Combine batch content for translation
            batch_texts = [sub.content for sub in batch_subtitles]
            combined_text = '\n\n'.join(batch_texts)
            
            # Translate the batch
            translated_text = self._translate_batch(
                combined_text,
                target_language,
                custom_prompt
            )
            
            # Split translated text back into individual subtitles
            translated_parts = re.split(r'\n\s*\n', translated_text)
            translated_parts = [p.strip() for p in translated_parts if p.strip()]
            
            # Update subtitle content while preserving timestamps
            for i, sub_idx in enumerate(batch_indices):
                if i < len(translated_parts):
                    subtitles[sub_idx].content = translated_parts[i]
                else:
                    # Fallback if split didn't match expected count
                    # Keep original or use last translation
                    if translated_parts:
                        subtitles[sub_idx].content = translated_parts[-1]
        
        # Compose back to SRT format
        translated_srt = srt.compose(subtitles)
        
        # Determine output file path
        if output_file is None:
            base_name = os.path.splitext(srt_file)[0]
            output_file = f"{base_name}.{target_language}.srt"
        
        # Write translated SRT with proper encoding and line endings
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            f.write(translated_srt)
            if not translated_srt.endswith('\n'):
                f.write('\n')
        
        return output_file
    
    def _group_subtitles_into_batches(
        self,
        subtitles: List[srt.Subtitle]
    ) -> List[Tuple[List[int], List[srt.Subtitle]]]:
        """
        Group subtitles into batches for translation
        
        Args:
            subtitles: List of srt.Subtitle objects
            
        Returns:
            List of (indices, subtitle_batch) tuples
        """
        batches = []
        current_indices = []
        current_subs = []
        current_chars = 0
        
        for idx, sub in enumerate(subtitles):
            if not sub.content.strip():
                continue
            
            content_chars = len(sub.content)
            
            # Check if adding this subtitle would exceed limit
            if current_chars + content_chars + 2 > MAX_CHARS_PER_REQUEST:
                # Save current batch and start new one
                if current_subs:
                    batches.append((current_indices, current_subs))
                current_indices = [idx]
                current_subs = [sub]
                current_chars = content_chars
            else:
                # Add to current batch
                current_indices.append(idx)
                current_subs.append(sub)
                current_chars += content_chars + 2
        
        # Don't forget the last batch
        if current_subs:
            batches.append((current_indices, current_subs))
        
        return batches