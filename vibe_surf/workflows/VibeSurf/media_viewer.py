from typing import Optional
from pathlib import Path

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output, BoolInput
from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.schema.data import Data


class MediaViewerComponent(Component):
    display_name = "Media Viewer"
    description = "Display images and videos with advanced controls (zoom, download, fullscreen, play/pause)"
    icon = "image"
    name = "MediaViewer"

    inputs = [
        MessageTextInput(
            name="media_path",
            display_name="Media Path",
            info="Path to the image or video file (can be a local path or URL). Type is automatically detected from file extension.",
            required=True,
        ),
        MessageTextInput(
            name="alt_text",
            display_name="Alt Text",
            info="Alternative text description for the media",
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="show_controls",
            display_name="Show Controls",
            value=True,
            info="Show media controls (zoom, download, fullscreen, etc.)",
            advanced=True,
        ),
        BoolInput(
            name="auto_play",
            display_name="Auto Play (Video)",
            value=False,
            info="Auto play video when loaded",
            advanced=True,
        ),
        BoolInput(
            name="loop",
            display_name="Loop (Video)",
            value=False,
            info="Loop video playback",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="media_output",
            display_name="Media Output",
            method="display_media",
        ),
    ]

    def _detect_media_type(self, path: str) -> str:
        """
        Detect media type from file extension.
        
        Args:
            path: File path or URL
            
        Returns:
            "image" or "video"
        """
        # Common image extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'}
        
        # Common video extensions
        video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'}
        
        # Get file extension (handle both local paths and URLs)
        # Remove query parameters from URLs
        import os
        clean_path = path.split('?')[0]
        ext = os.path.splitext(clean_path)[1].lower()
        
        if ext in image_extensions:
            return "image"
        elif ext in video_extensions:
            return "video"
        else:
            # Default to image if extension is unknown
            return "image"
    
    def display_media(self) -> Data:
        """
        Display media (image or video) with advanced controls.
        Media type is automatically detected from file extension.
        
        Returns a Data object with media information for frontend rendering.
        """
        try:
            # Validate media path
            if not self.media_path:
                raise ValueError("Media path is required")

            # Auto-detect media type from file extension
            media_type = self._detect_media_type(self.media_path)

            # Create Data object with media information
            # Frontend expects: resultMessage.data.type and resultMessage.data.path
            media_data = {
                "path": self.media_path,
                "type": media_type,
                "alt": self.alt_text or f"{media_type.capitalize()} content",
                "showControls": self.show_controls,
                "autoPlay": self.auto_play if media_type == "video" else False,
                "loop": self.loop if media_type == "video" else False,
            }

            # DEBUG: Log the media data structure being returned
            print(f"[MediaViewer Backend] Returning media_data: {media_data}")

            # Set status message
            self.status = f"Displaying {media_type}: {self.media_path}"

            # Return Data with media information directly in 'data'
            # Frontend expects: resultMessage.data.type (not resultMessage.data.media_data.type)
            return Data(data=media_data)

        except Exception as e:
            error_message = f"Error displaying media: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e