import os
import ffmpeg
from pathlib import Path
from vibe_surf.langflow.custom.custom_component.component import Component
from vibe_surf.langflow.io import MessageTextInput, Output, DropdownInput
from vibe_surf.langflow.schema.data import Data


class VideoSubtitleComponent(Component):
    display_name = "Video Subtitle Merger"
    description = "Embed subtitle files into video using FFmpeg"
    documentation: str = "https://docs.vibe_surf.langflow.org/components-custom-components"
    icon = "video"
    name = "VideoSubtitleComponent"

    inputs = [
        MessageTextInput(
            name="video_path",
            display_name="Video Path",
            info="Path to the input video file",
            value="",
        ),
        MessageTextInput(
            name="primary_subtitle",
            display_name="Primary Subtitle (SRT)",
            info="Path to the primary subtitle file (optional)",
            value="",
        ),
        MessageTextInput(
            name="secondary_subtitle",
            display_name="Secondary Subtitle (SRT)",
            info="Path to the secondary subtitle file (optional)",
            value="",
        ),
        DropdownInput(
            name="subtitle_mode",
            display_name="Subtitle Mode",
            info="Choose how to embed subtitles: soft (selectable) or hard (burned into video)",
            options=["soft", "hard"],
            value="hard",
        ),
        DropdownInput(
            name="subtitle_background",
            display_name="Subtitle Background",
            info="Add semi-transparent background to subtitles for better readability",
            options=["none", "light", "dark"],
            value="dark",
        ),
        MessageTextInput(
            name="font_size",
            display_name="Font Size",
            info="Subtitle font size (default: 24)",
            value="24",
        ),
        MessageTextInput(
            name="primary_margin",
            display_name="Primary Subtitle Margin",
            info="Distance from bottom for primary subtitle in pixels (default: 40)",
            value="35",
        ),
        MessageTextInput(
            name="secondary_margin",
            display_name="Secondary Subtitle Margin",
            info="Distance from bottom for secondary subtitle in pixels (default: 10)",
            value="10",
        ),
    ]

    outputs = [
        Output(display_name="Output Video", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        try:
            # Check if video file exists
            if not self.video_path or not os.path.exists(self.video_path):
                raise FileNotFoundError(f"Video file not found: {self.video_path}")

            # Get video file info
            video_path = Path(self.video_path)
            import time
            output_filename = f"{time.time()}-{video_path.stem}_with_subtitles{video_path.suffix}"
            output_path = video_path.parent / output_filename

            # Check subtitle files
            primary_exists = self.primary_subtitle and os.path.exists(self.primary_subtitle)
            secondary_exists = self.secondary_subtitle and os.path.exists(self.secondary_subtitle)

            if not primary_exists and not secondary_exists:
                # No subtitles to add, just copy the original file
                import shutil
                shutil.copy2(self.video_path, output_path)
                status_msg = "No subtitle files found, copied original video"
            else:
                subtitle_mode = getattr(self, 'subtitle_mode', 'soft')
                
                if subtitle_mode == 'soft':
                    # Soft subtitle embedding (selectable subtitles)
                    status_msg = self._embed_soft_subtitles(
                        video_path, output_path, primary_exists, secondary_exists
                    )
                else:
                    # Hard subtitle embedding (burned into video)
                    status_msg = self._embed_hard_subtitles(
                        video_path, output_path, primary_exists, secondary_exists
                    )

            # Prepare media data
            media_data = {
                "path": str(output_path),
                "type": "video",
                "alt": f"Video with embedded subtitles: {output_path.name}",
                "showControls": True,
                "autoPlay": False,
                "loop": False,
            }

            # Set component status
            self.status = status_msg

            return Data(data=media_data)

        except Exception as e:
            error_msg = f"Error processing video: {str(e)}"
            self.status = error_msg
            raise RuntimeError(error_msg)

    def _embed_soft_subtitles(self, video_path, output_path, primary_exists, secondary_exists):
        """Embed subtitles as soft (selectable) subtitle streams"""
        try:
            # Start with video input
            video = ffmpeg.input(str(video_path))
            
            # Prepare inputs list
            inputs = [video]
            
            # Add subtitle inputs
            if primary_exists:
                primary_sub = ffmpeg.input(str(self.primary_subtitle))
                inputs.append(primary_sub)
            
            if secondary_exists:
                secondary_sub = ffmpeg.input(str(self.secondary_subtitle))
                inputs.append(secondary_sub)
            
            # Build output arguments
            output_args = {
                'c:v': 'copy',  # Copy video stream
                'c:a': 'copy',  # Copy audio stream
                'c:s': 'mov_text',  # Subtitle codec for MP4
            }
            
            # Add metadata for subtitle streams
            subtitle_index = 0
            if primary_exists:
                output_args[f'metadata:s:s:{subtitle_index}'] = 'language=eng'
                output_args[f'metadata:s:s:{subtitle_index}:title'] = 'Primary'
                output_args[f'disposition:s:s:{subtitle_index}'] = 'default'
                subtitle_index += 1
            
            if secondary_exists:
                output_args[f'metadata:s:s:{subtitle_index}'] = 'language=eng'
                output_args[f'metadata:s:s:{subtitle_index}:title'] = 'Secondary'
            
            # Create output
            output = ffmpeg.output(*inputs, str(output_path), **output_args)
            
            # Run with error handling
            try:
                ffmpeg.run(output, overwrite_output=True, quiet=True)
            except ffmpeg.Error as e:
                print(f"FFmpeg error output: {e.stderr.decode() if e.stderr else 'No stderr'}")
                
                # Try with srt codec if mov_text fails
                output_args['c:s'] = 'srt'
                output = ffmpeg.output(*inputs, str(output_path), **output_args)
                ffmpeg.run(output, overwrite_output=True, quiet=True)
            
            return f"Successfully embedded soft subtitles into video: {output_path.name}"
            
        except Exception as e:
            raise RuntimeError(f"Error embedding soft subtitles: {str(e)}")

    def _embed_hard_subtitles(self, video_path, output_path, primary_exists, secondary_exists):
        """Embed subtitles as hard-burned (permanent) subtitles"""
        try:
            # Start with video input
            video = ffmpeg.input(str(video_path))
            audio = video.audio
            
            # Fix Windows path issues: replace backslashes with forward slashes
            # FFmpeg accepts forward slashes on all platforms, including Windows
            def fix_path_for_ffmpeg(path):
                """Convert Windows paths to use forward slashes for FFmpeg compatibility"""
                return str(path).replace('\\', '/')
            
            # Get background style preference
            background_mode = getattr(self, 'subtitle_background', 'dark')
            
            # Get font size preference
            try:
                font_size = int(getattr(self, 'font_size', '24'))
            except (ValueError, TypeError):
                font_size = 24
            
            # Get margin preferences
            try:
                primary_margin = int(getattr(self, 'primary_margin', '40'))
            except (ValueError, TypeError):
                primary_margin = 40
            
            try:
                secondary_margin = int(getattr(self, 'secondary_margin', '10'))
            except (ValueError, TypeError):
                secondary_margin = 10
            
            # Build style based on background preference
            # BackColour format: &HAABBGGRR (AA=alpha, BB=blue, GG=green, RR=red)
            # BorderStyle: 1=outline, 3=box background, 4=no border
            # &H00000000 = completely transparent background
            if background_mode == "dark":
                # Dark semi-transparent background (80% opacity black) - no outline
                base_style = f"FontSize={font_size},BorderStyle=4,BackColour=&H80000000,Outline=0,Shadow=0,Spacing=0.2"
            elif background_mode == "light":
                # Light semi-transparent background (80% opacity white) - no outline
                base_style = f"FontSize={font_size},BorderStyle=4,BackColour=&H80FFFFFF,Outline=0,Shadow=0,Spacing=0.2"
            else:
                # No background - pure white text with completely transparent background
                base_style = f"FontSize={font_size},BorderStyle=1,PrimaryColour=&HFFFFFF,BackColour=&H00000000,Outline=0,Shadow=0,Spacing=0.2"
            
            # Apply subtitle filter to video
            # Use filename parameter to avoid path/filter argument conflicts on Windows
            if primary_exists:
                primary_path = fix_path_for_ffmpeg(self.primary_subtitle)
                # Primary subtitle positioned using user-defined margin
                primary_style = f"Alignment=2,MarginV={primary_margin},{base_style}"
                video_with_subs = video.filter('subtitles',
                                               filename=primary_path,
                                               force_style=primary_style)
            else:
                secondary_path = fix_path_for_ffmpeg(self.secondary_subtitle)
                # Single subtitle uses secondary margin
                single_style = f"Alignment=2,MarginV={secondary_margin},{base_style}"
                video_with_subs = video.filter('subtitles',
                                               filename=secondary_path,
                                               force_style=single_style)
            
            # If dual subtitles, apply second subtitle filter for secondary subtitle at bottom
            if primary_exists and secondary_exists:
                secondary_path = fix_path_for_ffmpeg(self.secondary_subtitle)
                # Secondary subtitle using user-defined margin
                secondary_style = f"Alignment=2,MarginV={secondary_margin},{base_style}"
                video_with_subs = video_with_subs.filter('subtitles',
                                                         filename=secondary_path,
                                                         force_style=secondary_style)
            
            # Create output with both video and audio
            output = ffmpeg.output(video_with_subs, audio, str(output_path))
            
            # Run FFmpeg
            ffmpeg.run(output, overwrite_output=True, quiet=True)
            
            subtitle_count = "dual" if (primary_exists and secondary_exists) else "single"
            return f"Successfully burned {subtitle_count} subtitle(s) into video: {output_path.name}"
            
        except Exception as e:
            raise RuntimeError(f"Error embedding hard subtitles: {str(e)}")