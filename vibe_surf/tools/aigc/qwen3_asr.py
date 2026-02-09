"""
Qwen3 ASR (Automatic Speech Recognition) Processor

This module provides an interface to process audio/video files and generate
transcriptions with optional SRT subtitle files using Qwen3-ASR-Flash API.

Note: This module requires the 'full' extras to be installed:
    pip install vibesurf[full]
"""

import os
import io
import re
import time
import random
import requests
import dashscope
import subprocess
import numpy as np
import concurrent.futures

from tqdm import tqdm
from datetime import timedelta
from collections import Counter
from urllib.parse import urlparse
from typing import Optional, Tuple, List

# Optional dependencies - only required when using ASR functionality
try:
    import srt
    import soundfile as sf
    from pydub import AudioSegment
    from silero_vad import load_silero_vad, get_speech_timestamps
    _ASR_DEPS_AVAILABLE = True
except ImportError:
    _ASR_DEPS_AVAILABLE = False


WAV_SAMPLE_RATE = 16000
MAX_API_RETRY = 10
API_RETRY_SLEEP = (1, 2)

language_code_mapping = {
    "ar": "Arabic",
    "zh": "Chinese",
    "en": "English",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "es": "Spanish"
}


class Qwen3ASRProcessor:
    """
    Qwen3 ASR (Automatic Speech Recognition) Processor
    
    This class provides an interface to process audio/video files and generate
    transcriptions with optional SRT subtitle files using Qwen3-ASR-Flash API.
    
    Example:
        >>> processor = Qwen3ASRProcessor(dashscope_api_key="your_api_key")
        >>> srt_path = processor.run("path/to/video.mp4", save_srt=True)
        >>> print(f"SRT file saved to: {srt_path}")
    """
    
    def __init__(
        self,
        dashscope_api_key: Optional[str] = None,
        model: str = "qwen3-asr-flash",
        num_threads: int = 4,
        vad_segment_threshold: int = 120,
        min_speech_duration_ms: int = 150,
        min_silence_duration_ms: int = 100,
        max_srt_duration: float = 3.0,
        min_srt_duration: float = 2.0,
        tmp_dir: Optional[str] = None,
        silence: bool = True,
    ):
        """
        Initialize Qwen3ASRProcessor
        
        Args:
            dashscope_api_key: DashScope API key (if not provided, uses DASHSCOPE_API_KEY env var)
            model: Model name (default: "qwen3-asr-flash")
            num_threads: Number of threads for parallel API calls (default: 4)
            vad_segment_threshold: VAD segment threshold in SECONDS (default: 120s = 2min)
            min_speech_duration_ms: Minimum speech duration in MILLISECONDS (default: 150ms)
            min_silence_duration_ms: Minimum silence duration in MILLISECONDS (default: 500ms)
            max_srt_duration: Maximum SRT subtitle duration in SECONDS (default: 3.0s)
                - Sentences longer than this will be force-split in SRT output
            min_srt_duration: Minimum SRT subtitle duration in SECONDS (default: 2.0s)
                - Chunks shorter than this (after natural breakpoint split) will be merged
            tmp_dir: Temporary directory for processing (default: ~/qwen3-asr-cache)
            silence: Reduce terminal output (default: False)
            vad_threshold: VAD detection threshold 0.0-1.0 (default: 0.5)
        """
        if dashscope_api_key:
            dashscope.api_key = dashscope_api_key
        else:
            assert "DASHSCOPE_API_KEY" in os.environ, \
                "Please set DASHSCOPE_API_KEY as an environment variable, or pass it to the constructor"
        
        self.model = model
        self.num_threads = num_threads
        self.vad_segment_threshold = vad_segment_threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.max_srt_duration = max_srt_duration
        self.min_srt_duration = min_srt_duration
        self.tmp_dir = tmp_dir or os.path.join(os.path.expanduser("~"), "qwen3-asr-cache")
        self.silence = silence
        
    def _check_asr_deps(self):
        """Check if ASR dependencies are available."""
        if not _ASR_DEPS_AVAILABLE:
            raise ImportError(
                "ASR functionality requires additional dependencies. "
                "Please install with: pip install vibesurf[full]"
            )

    def run(
        self,
        input_file: str,
        context: str = "",
        save_srt: bool = True,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Process audio/video file and generate transcription with optional SRT subtitles

        Args:
            input_file: Path to input media file (local path or HTTP URL)
            context: Context text for Qwen3-ASR-Flash
            save_srt: Whether to save SRT subtitle file (default: True)
            output_dir: Output directory for results (default: same as input file)

        Returns:
            str: Path to the generated SRT file (or text file if save_srt=False)
        """
        # Check if ASR dependencies are available
        self._check_asr_deps()

        # Check if input file exists
        if input_file.startswith(("http://", "https://")):
            try:
                response = requests.head(input_file, allow_redirects=True, timeout=5)
                if response.status_code >= 400:
                    raise FileNotFoundError(f"returned status code {response.status_code}")
            except Exception as e:
                raise FileNotFoundError(
                    f"HTTP link {input_file} does not exist or is inaccessible: {str(e)}"
                )
        elif not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file \"{input_file}\" does not exist!")
        
        # Load audio
        wav = self._load_audio(input_file)
        if not self.silence:
            print(f"Loaded wav duration: {len(wav) / WAV_SAMPLE_RATE:.2f}s")
        
        # Segment audio using VAD
        if not self.silence:
            print(f"Initializing Silero VAD model for segmenting...")
        from silero_vad import load_silero_vad
        worker_vad_model = load_silero_vad(onnx=True)
        wav_list = self._process_vad(wav, worker_vad_model)

        if not self.silence:
            print(f"Segmenting done, total segments: {len(wav_list)}")
        
        # Save processed audio to tmp dir
        wav_name = os.path.basename(input_file)
        wav_dir_name = os.path.splitext(wav_name)[0]
        save_dir = os.path.join(self.tmp_dir, wav_dir_name)
        
        wav_path_list = []
        for idx, (_, _, wav_data) in enumerate(wav_list):
            wav_path = os.path.join(save_dir, f"{wav_name}_{idx}.wav")
            self._save_audio_file(wav_data, wav_path)
            wav_path_list.append(wav_path)
        
        # Multithread call qwen3-asr-flash api
        results = []
        languages = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_dict = {
                executor.submit(self._asr, wav_path, context): idx
                for idx, wav_path in enumerate(wav_path_list)
            }
            pbar = tqdm(total=len(future_dict), desc="Calling Qwen3-ASR-Flash API")
            for future in concurrent.futures.as_completed(future_dict):
                idx = future_dict[future]
                language, recog_text = future.result()
                results.append((idx, recog_text))
                languages.append(language)
                if not self.silence:
                    pbar.update(1)
            if not self.silence:
                pbar.close()
        
        # Sort and splice in the original order
        results.sort(key=lambda x: x[0])
        full_text = " ".join(text for _, text in results)
        language = Counter(languages).most_common(1)[0][0]
        
        if not self.silence:
            print(f"Detected Language: {language}")
            print(f"Full Transcription: {full_text}")
        
        # Delete tmp save dir
        try:
            import shutil
            shutil.rmtree(save_dir)
        except Exception as e:
            if not self.silence:
                print(f"Warning: Failed to delete temp directory: {e}")
        
        # Determine output file path
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            save_file = os.path.join(output_dir, base_name + ".txt")
        elif os.path.exists(input_file):
            save_file = os.path.splitext(input_file)[0] + ".txt"
        else:
            save_file = os.path.splitext(urlparse(input_file).path)[0].split('/')[-1] + '.txt'
        
        # Save full text to local file
        with open(save_file, 'w', encoding='utf-8') as f:
            f.write(language + '\n')
            f.write(full_text + '\n')
        
        # Save subtitles to local SRT file with sentence-based splitting
        if save_srt:
            subtitles = self._generate_sentence_based_srt(results, wav_list)
            final_srt_content = srt.compose(subtitles)
            srt_file = os.path.splitext(save_file)[0] + ".srt"
            
            # Write SRT file with UTF-8 encoding (no BOM) and proper line endings
            with open(srt_file, 'w', encoding='utf-8', newline='') as f:
                # Ensure proper line endings for SRT format
                # Most players expect \r\n or \n, normalized by newline=''
                f.write(final_srt_content)
                # Add extra newline at end if not present (SRT standard)
                if not final_srt_content.endswith('\n'):
                    f.write('\n')

            return srt_file
        
        return save_file
    
    def _load_audio(self, file_path: str) -> np.ndarray:
        """Load audio file and convert to 16kHz mono WAV"""
        import soundfile as sf
        try:
            command = [
                'ffmpeg',
                '-i', file_path,
                '-ar', str(WAV_SAMPLE_RATE),
                '-ac', '1',
                '-c:a', 'pcm_s16le',
                '-f', 'wav',
                '-'
            ]
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout_data, stderr_data = process.communicate()

            if process.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg error: {stderr_data.decode('utf-8', errors='ignore')}"
                )

            with io.BytesIO(stdout_data) as data_io:
                wav_data, sr = sf.read(data_io, dtype='float32')

            return wav_data
        except Exception as ffmpeg_e:
            raise RuntimeError(
                f"Failed to load audio from '{file_path}'. Error: {ffmpeg_e}"
            )
    
    def _process_vad(
        self,
        wav: np.ndarray,
        worker_vad_model,
        max_segment_threshold_s: int = 180
    ) -> List[Tuple[int, int, np.ndarray]]:
        """Process VAD and segment audio"""
        from silero_vad import get_speech_timestamps
        try:
            speech_timestamps = get_speech_timestamps(wav, worker_vad_model)

            if not speech_timestamps:
                return []
            
            # Convert to segmented_wavs format
            segmented_wavs = []
            for sample in speech_timestamps:
                start_sample, end_sample = sample["start"], sample["end"]
                segmented_wavs.append((start_sample, end_sample, wav[start_sample:end_sample]))
            
            # Merge chunks shorter than 1 second
            segmented_wavs = self._merge_short_vad_segments(segmented_wavs, wav, min_duration_s=0.5)
            
            return segmented_wavs
            
        except Exception as e:
            # Fallback: simple chunking
            if not self.silence:
                print(f"VAD processing failed, using simple chunking: {e}")
            segmented_wavs = []
            total_samples = len(wav)
            max_chunk_size_samples = max_segment_threshold_s * WAV_SAMPLE_RATE
            
            for start_sample in range(0, total_samples, max_chunk_size_samples):
                end_sample = min(start_sample + max_chunk_size_samples, total_samples)
                segment = wav[start_sample:end_sample]
                if len(segment) > 0:
                    segmented_wavs.append((start_sample, end_sample, segment))
            
            return segmented_wavs
    
    def _merge_short_vad_segments(
        self,
        segmented_wavs: List[Tuple[int, int, np.ndarray]],
        full_wav: np.ndarray,
        min_duration_s: float = 1.0
    ) -> List[Tuple[int, int, np.ndarray]]:
        """
        Merge VAD segments that are shorter than min_duration_s
        
        This ensures that all audio chunks sent to ASR are at least 1 second long,
        regardless of how VAD split them.
        
        Args:
            segmented_wavs: List of (start_sample, end_sample, wav_data) tuples
            full_wav: The original full audio array
            min_duration_s: Minimum duration in seconds (default: 1.0s)
            
        Returns:
            List of merged (start_sample, end_sample, wav_data) tuples
        """
        if len(segmented_wavs) <= 1:
            return segmented_wavs
        
        min_samples = int(min_duration_s * WAV_SAMPLE_RATE)
        merged = True
        
        # Repeatedly merge short segments until none remain below threshold
        while merged:
            merged = False
            new_segments = []
            i = 0
            
            while i < len(segmented_wavs):
                start_sample, end_sample, wav_data = segmented_wavs[i]
                segment_samples = end_sample - start_sample
                
                # Check if current segment is too short
                if segment_samples < min_samples and len(segmented_wavs) > 1:
                    # Decide whether to merge with previous or next
                    can_merge_prev = i > 0 and len(new_segments) > 0
                    can_merge_next = i < len(segmented_wavs) - 1
                    
                    if can_merge_prev and can_merge_next:
                        # Merge with the shorter neighbor
                        prev_start, prev_end, _ = new_segments[-1]
                        next_start, next_end, _ = segmented_wavs[i + 1]
                        prev_samples = prev_end - prev_start
                        next_samples = next_end - next_start
                        
                        if prev_samples <= next_samples:
                            # Merge with previous
                            new_start = prev_start
                            new_end = end_sample
                            new_segments[-1] = (new_start, new_end, full_wav[new_start:new_end])
                        else:
                            # Merge with next
                            new_start = start_sample
                            new_end = next_end
                            new_segments.append((new_start, new_end, full_wav[new_start:new_end]))
                            i += 1  # Skip next segment as it's merged
                        merged = True
                    elif can_merge_prev:
                        # Only can merge with previous
                        prev_start, prev_end, _ = new_segments[-1]
                        new_start = prev_start
                        new_end = end_sample
                        new_segments[-1] = (new_start, new_end, full_wav[new_start:new_end])
                        merged = True
                    elif can_merge_next:
                        # Only can merge with next
                        next_start, next_end, _ = segmented_wavs[i + 1]
                        new_start = start_sample
                        new_end = next_end
                        new_segments.append((new_start, new_end, full_wav[new_start:new_end]))
                        i += 1  # Skip next segment as it's merged
                        merged = True
                    else:
                        # Can't merge, keep as is
                        new_segments.append((start_sample, end_sample, wav_data))
                else:
                    # Segment is long enough, keep it
                    new_segments.append((start_sample, end_sample, wav_data))
                
                i += 1
            
            segmented_wavs = new_segments
        
        return segmented_wavs
    
    def _generate_sentence_based_srt(
        self,
        results: List[Tuple[int, str]],
        wav_list: List[Tuple[int, int, np.ndarray]]
    ):
        """
        Generate SRT subtitles by splitting text at sentence boundaries
        and estimating timestamps based on character count

        Args:
            results: List of (segment_idx, transcribed_text) tuples
            wav_list: List of (start_sample, end_sample, wav_data) tuples

        Returns:
            List of srt.Subtitle objects
        """
        import srt
        subtitles = []
        subtitle_index = 1
        
        for segment_idx, text in results:
            if not text.strip():
                continue
                
            # Get segment time range
            seg_start_sample = wav_list[segment_idx][0]
            seg_end_sample = wav_list[segment_idx][1]
            seg_start_time = seg_start_sample / WAV_SAMPLE_RATE
            seg_duration = (seg_end_sample - seg_start_sample) / WAV_SAMPLE_RATE
            
            # Split text by sentence delimiters (。！？!?.)
            sentences = re.split(r'([。！？!?.])', text)
            
            # Recombine sentences with their delimiters
            combined_sentences = []
            for i in range(0, len(sentences), 2):
                sentence = sentences[i]
                delimiter = sentences[i + 1] if i + 1 < len(sentences) else ''
                combined = (sentence + delimiter).strip()
                if combined:
                    combined_sentences.append(combined)
            
            # If no sentence delimiters found, treat whole text as one sentence
            if not combined_sentences:
                combined_sentences = [text.strip()]
            
            # Calculate total character count (for time estimation)
            total_chars = sum(len(s) for s in combined_sentences)
            if total_chars == 0:
                continue
            
            # Distribute time across sentences based on character count
            current_time = seg_start_time
            for sentence in combined_sentences:
                sentence_chars = len(sentence)
                # Estimate sentence duration based on character ratio
                estimated_duration = seg_duration * (sentence_chars / total_chars)
                sentence_end_time = current_time + estimated_duration
                
                # Check if sentence exceeds max duration, if so, force split
                if estimated_duration > self.max_srt_duration:
                    # Force split long sentence into smaller chunks
                    chunks = self._split_long_sentence(sentence, self.max_srt_duration, estimated_duration)
                    chunk_duration = estimated_duration / len(chunks)
                    
                    for chunk in chunks:
                        chunk_end = current_time + chunk_duration
                        subtitles.append(srt.Subtitle(
                            index=subtitle_index,
                            start=timedelta(seconds=current_time),
                            end=timedelta(seconds=chunk_end),
                            content=chunk
                        ))
                        subtitle_index += 1
                        current_time = chunk_end
                else:
                    # Add sentence as single subtitle
                    subtitles.append(srt.Subtitle(
                        index=subtitle_index,
                        start=timedelta(seconds=current_time),
                        end=timedelta(seconds=sentence_end_time),
                        content=sentence
                    ))
                    subtitle_index += 1
                    current_time = sentence_end_time
        
        return subtitles
    
    def _merge_short_subtitles(
        self,
        subtitles: List,
        merge_threshold: float = 1.0
    ) -> List:
        """
        Merge subtitles that are shorter than merge_threshold seconds

        This method merges any chunk shorter than the threshold,
        regardless of whether it was separated by commas or periods.

        Args:
            subtitles: List of srt.Subtitle objects
            merge_threshold: Duration threshold in seconds (default: 1.0s)
                Chunks shorter than this will be merged with adjacent chunks

        Returns:
            List of srt.Subtitle objects with short ones merged
        """
        if len(subtitles) <= 1:
            return subtitles
        
        # Repeatedly merge short subtitles until none remain below threshold
        merged = True
        while merged:
            merged = False
            new_subtitles = []
            i = 0
            
            while i < len(subtitles):
                current_subtitle = subtitles[i]
                duration = (current_subtitle.end - current_subtitle.start).total_seconds()
                
                # Check if current subtitle is too short
                if duration < merge_threshold and len(subtitles) > 1:
                    # Decide whether to merge with previous or next
                    can_merge_prev = i > 0 and len(new_subtitles) > 0
                    can_merge_next = i < len(subtitles) - 1
                    
                    if can_merge_prev and can_merge_next:
                        # Merge with the shorter neighbor
                        prev_duration = (new_subtitles[-1].end - new_subtitles[-1].start).total_seconds()
                        next_duration = (subtitles[i+1].end - subtitles[i+1].start).total_seconds()
                        
                        if prev_duration <= next_duration:
                            # Merge with previous
                            prev_subtitle = new_subtitles[-1]
                            merged_content = self._smart_merge(prev_subtitle.content, current_subtitle.content)
                            new_subtitles[-1] = srt.Subtitle(
                                index=prev_subtitle.index,
                                start=prev_subtitle.start,
                                end=current_subtitle.end,
                                content=merged_content
                            )
                        else:
                            # Merge with next
                            next_subtitle = subtitles[i+1]
                            merged_content = self._smart_merge(current_subtitle.content, next_subtitle.content)
                            new_subtitles.append(srt.Subtitle(
                                index=len(new_subtitles) + 1,
                                start=current_subtitle.start,
                                end=next_subtitle.end,
                                content=merged_content
                            ))
                            i += 1  # Skip next subtitle as it's merged
                        merged = True
                    elif can_merge_prev:
                        # Only can merge with previous
                        prev_subtitle = new_subtitles[-1]
                        merged_content = self._smart_merge(prev_subtitle.content, current_subtitle.content)
                        new_subtitles[-1] = srt.Subtitle(
                            index=prev_subtitle.index,
                            start=prev_subtitle.start,
                            end=current_subtitle.end,
                            content=merged_content
                        )
                        merged = True
                    elif can_merge_next:
                        # Only can merge with next
                        next_subtitle = subtitles[i+1]
                        merged_content = self._smart_merge(current_subtitle.content, next_subtitle.content)
                        new_subtitles.append(srt.Subtitle(
                            index=len(new_subtitles) + 1,
                            start=current_subtitle.start,
                            end=next_subtitle.end,
                            content=merged_content
                        ))
                        i += 1  # Skip next subtitle as it's merged
                        merged = True
                    else:
                        # Can't merge, keep as is
                        new_subtitles.append(srt.Subtitle(
                            index=len(new_subtitles) + 1,
                            start=current_subtitle.start,
                            end=current_subtitle.end,
                            content=current_subtitle.content
                        ))
                else:
                    # Subtitle is long enough, keep it
                    new_subtitles.append(srt.Subtitle(
                        index=len(new_subtitles) + 1,
                        start=current_subtitle.start,
                        end=current_subtitle.end,
                        content=current_subtitle.content
                    ))
                
                i += 1
            
            subtitles = new_subtitles
        
        # Re-index all subtitles to ensure sequential numbering
        for idx, subtitle in enumerate(subtitles, start=1):
            subtitle.index = idx
        
        return subtitles
    
    def _split_long_sentence(
        self,
        sentence: str,
        max_duration: float,
        total_duration: float
    ) -> List[str]:
        """
        Split a long sentence into smaller chunks at natural break points
        
        Args:
            sentence: The sentence to split
            max_duration: Maximum duration per chunk in seconds
            total_duration: Total estimated duration of the sentence
            
        Returns:
            List of sentence chunks
        """
        # Calculate how many chunks we need
        num_chunks = int(np.ceil(total_duration / max_duration))
        
        # Split by commas first if possible
        parts = re.split(r'([，,、])', sentence)
        combined_parts = []
        for i in range(0, len(parts), 2):
            part = parts[i]
            delimiter = parts[i + 1] if i + 1 < len(parts) else ''
            combined = (part + delimiter).strip()
            if combined:
                combined_parts.append(combined)
        
        # If we have enough comma-separated parts, distribute them
        if len(combined_parts) >= num_chunks:
            chunks = []
            chunk_size = len(combined_parts) // num_chunks
            for i in range(num_chunks):
                start_idx = i * chunk_size
                end_idx = start_idx + chunk_size if i < num_chunks - 1 else len(combined_parts)
                chunks.append(''.join(combined_parts[start_idx:end_idx]))
            # Merge short chunks from natural breakpoint splitting
            chunks = self._merge_short_chunks(chunks, total_duration)
            return chunks
        
        # Otherwise, split at natural break points (commas, spaces, punctuation)
        chars_per_chunk = len(sentence) // num_chunks
        chunks = []
        current_pos = 0
        used_natural_breakpoint = False
        
        for i in range(num_chunks):
            if i == num_chunks - 1:
                # Last chunk: take everything remaining
                chunks.append(sentence[current_pos:])
            else:
                # Find ideal split position
                ideal_pos = current_pos + chars_per_chunk
                
                # Search window: ±20% around ideal position
                search_window = max(5, chars_per_chunk // 5)
                search_start = max(current_pos, ideal_pos - search_window)
                search_end = min(len(sentence), ideal_pos + search_window)
                
                # Find natural break points in search window
                # Priority: comma/pause markers > space > any position
                best_split = ideal_pos
                
                # Look for comma or pause markers (，,、;；)
                for pos in range(search_start, search_end):
                    if sentence[pos] in '，,、;；':
                        best_split = pos + 1  # Split after the comma
                        used_natural_breakpoint = True
                        break
                else:
                    # No comma found, look for space
                    for pos in range(search_start, search_end):
                        if sentence[pos] in ' \t\n':
                            best_split = pos + 1  # Split after the space
                            used_natural_breakpoint = True
                            break
                    else:
                        # No space found either, use ideal position
                        best_split = ideal_pos
                
                # Extract chunk and update position
                chunks.append(sentence[current_pos:best_split].strip())
                current_pos = best_split
        
        # Filter out empty chunks
        chunks = [c for c in chunks if c]
        
        # Only merge if we used natural breakpoints
        if used_natural_breakpoint:
            chunks = self._merge_short_chunks(chunks, total_duration)
        
        return chunks
    
    def _merge_short_chunks(
        self,
        chunks: List[str],
        total_duration: float
    ) -> List[str]:
        """
        Merge chunks that are shorter than min_srt_duration with adjacent chunks
        
        Args:
            chunks: List of text chunks
            total_duration: Total duration of all chunks combined
            
        Returns:
            List of chunks with short ones merged
        """
        if len(chunks) <= 1:
            return chunks
        
        # Calculate estimated duration for each chunk based on character ratio
        total_chars = sum(len(c) for c in chunks)
        if total_chars == 0:
            return chunks
        
        chunk_durations = [
            total_duration * (len(c) / total_chars) for c in chunks
        ]
        
        # Repeatedly merge short chunks until none remain
        merged = True
        while merged:
            merged = False
            new_chunks = []
            new_durations = []
            i = 0
            
            while i < len(chunks):
                # Check if current chunk is too short
                if chunk_durations[i] < self.min_srt_duration and len(chunks) > 1:
                    # Decide whether to merge with previous or next
                    can_merge_prev = i > 0 and len(new_chunks) > 0
                    can_merge_next = i < len(chunks) - 1
                    
                    if can_merge_prev and can_merge_next:
                        # Merge with the shorter neighbor
                        if chunk_durations[i-1] <= chunk_durations[i+1]:
                            # Merge with previous - add space if needed
                            new_chunks[-1] = self._smart_merge(new_chunks[-1], chunks[i])
                            new_durations[-1] = new_durations[-1] + chunk_durations[i]
                        else:
                            # Merge with next - add space if needed
                            new_chunks.append(self._smart_merge(chunks[i], chunks[i+1]))
                            new_durations.append(chunk_durations[i] + chunk_durations[i+1])
                            i += 1  # Skip next chunk as it's merged
                        merged = True
                    elif can_merge_prev:
                        # Only can merge with previous - add space if needed
                        new_chunks[-1] = self._smart_merge(new_chunks[-1], chunks[i])
                        new_durations[-1] = new_durations[-1] + chunk_durations[i]
                        merged = True
                    elif can_merge_next:
                        # Only can merge with next - add space if needed
                        new_chunks.append(self._smart_merge(chunks[i], chunks[i+1]))
                        new_durations.append(chunk_durations[i] + chunk_durations[i+1])
                        i += 1  # Skip next chunk as it's merged
                        merged = True
                    else:
                        # Can't merge, keep as is
                        new_chunks.append(chunks[i])
                        new_durations.append(chunk_durations[i])
                else:
                    # Chunk is long enough, keep it
                    new_chunks.append(chunks[i])
                    new_durations.append(chunk_durations[i])
                
                i += 1
            
            chunks = new_chunks
            chunk_durations = new_durations
        
        return chunks
    
    def _smart_merge(self, chunk1: str, chunk2: str) -> str:
        """
        Smart merge two chunks, adding space if needed
        
        Args:
            chunk1: First chunk
            chunk2: Second chunk
            
        Returns:
            Merged string with appropriate spacing
        """
        if not chunk1:
            return chunk2
        if not chunk2:
            return chunk1
        
        # Check if we need to add space between chunks
        # Add space if both chunks end/start with alphanumeric or CJK characters
        last_char = chunk1[-1]
        first_char = chunk2[0]
        
        # Check if either is English letter, number, or common word boundary
        needs_space = False
        if last_char.isalnum() and first_char.isalnum():
            # Both are alphanumeric - likely need space (e.g., "hello" + "world")
            needs_space = True
        elif last_char.isalpha() and first_char.isalpha():
            # Both are letters - check if they're not CJK
            # CJK characters don't need spaces between them
            is_cjk_last = '\u4e00' <= last_char <= '\u9fff'
            is_cjk_first = '\u4e00' <= first_char <= '\u9fff'
            if not (is_cjk_last and is_cjk_first):
                needs_space = True
        
        if needs_space:
            return chunk1 + ' ' + chunk2
        else:
            return chunk1 + chunk2
    
    def _save_audio_file(self, wav: np.ndarray, file_path: str):
        """Save audio to file"""
        import soundfile as sf
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        sf.write(file_path, wav, WAV_SAMPLE_RATE)
    
    def _post_text_process(self, text: str, threshold: int = 20) -> str:
        """Post-process transcription text to fix repetitions"""
        def fix_char_repeats(s, thresh):
            res = []
            i = 0
            n = len(s)
            while i < n:
                count = 1
                while i + count < n and s[i + count] == s[i]:
                    count += 1
                
                if count > thresh:
                    res.append(s[i])
                    i += count
                else:
                    res.append(s[i:i + count])
                    i += count
            return ''.join(res)
        
        def fix_pattern_repeats(s, thresh, max_len=20):
            n = len(s)
            min_repeat_chars = thresh * 2
            if n < min_repeat_chars:
                return s
            
            i = 0
            result = []
            while i <= n - min_repeat_chars:
                found = False
                for k in range(1, max_len + 1):
                    if i + k * thresh > n:
                        break
                    
                    pattern = s[i:i + k]
                    
                    valid = True
                    for rep in range(1, thresh):
                        start_idx = i + rep * k
                        if s[start_idx:start_idx + k] != pattern:
                            valid = False
                            break
                    
                    if valid:
                        total_rep = thresh
                        end_index = i + thresh * k
                        while end_index + k <= n and s[end_index:end_index + k] == pattern:
                            total_rep += 1
                            end_index += k
                        
                        result.append(pattern)
                        result.append(fix_pattern_repeats(s[end_index:], thresh, max_len))
                        i = n
                        found = True
                        break
                
                if found:
                    break
                else:
                    result.append(s[i])
                    i += 1
            
            if not found:
                result.append(s[i:])
            return ''.join(result)
        
        text = fix_char_repeats(text, threshold)
        return fix_pattern_repeats(text, threshold)
    
    def _asr(self, wav_url: str, context: str = "") -> Tuple[str, str]:
        """Call Qwen3-ASR-Flash API for transcription"""
        from pydub import AudioSegment
        if not wav_url.startswith("http"):
            assert os.path.exists(wav_url), f"{wav_url} not exists!"
            file_path = wav_url
            file_size = os.path.getsize(file_path)

            # Convert to mp3 if file size > 10M
            if file_size > 10 * 1024 * 1024:
                mp3_path = os.path.splitext(file_path)[0] + ".mp3"
                audio = AudioSegment.from_file(file_path)
                audio.export(mp3_path, format="mp3")
                wav_url = mp3_path

            wav_url = f"file://{wav_url}"
        
        # Submit the ASR task
        for attempt in range(MAX_API_RETRY):
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
                
                recog_text = None
                if len(output["message"]["content"]):
                    recog_text = output["message"]["content"][0]["text"]
                if recog_text is None:
                    recog_text = ""
                
                lang_code = None
                if "annotations" in output["message"]:
                    lang_code = output["message"]["annotations"][0]["language"]
                language = language_code_mapping.get(lang_code, "Not Supported")
                
                return language, self._post_text_process(recog_text)
            except Exception as e:
                try:
                    if not self.silence:
                        print(f"Retry {attempt + 1}...  {wav_url}\n{response}")
                    if hasattr(response, 'code') and response.code == "DataInspectionFailed":
                        print(f"DataInspectionFailed! Invalid input audio \"{wav_url}\"")
                        break
                except Exception:
                    if not self.silence:
                        print(f"Retry {attempt + 1}...  {wav_url}\n{e}")
                time.sleep(random.uniform(*API_RETRY_SLEEP))
        
        raise Exception(f"{wav_url} task failed!\n{response}")