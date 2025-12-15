import os
import uuid
import mimetypes
from pathlib import Path
from typing import Optional
from PIL import Image

from vibe_surf.common import get_workspace_dir
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import DropdownInput, FileInput, MessageTextInput, Output, StrInput, MultilineInput
from vibe_surf.langflow.schema.data import Data


class VertexImageGeneratorComponent(Component):
    display_name = "Vertex AI Image Generator"
    description = "Generate images using Vertex AI (Gemini/Nano Banana) via Google GenAI SDK."
    icon = "VertexAI"
    name = "VertexImageGenerator"

    inputs = [
        FileInput(
            name="credentials",
            display_name="Credentials",
            info="JSON credentials file. Leave empty to fallback to environment variables",
            file_types=["json"],
        ),
        MultilineInput(
            name="prompt",
            display_name="Prompt",
            info="Text description for the image",
            required=True,
        ),
        FileInput(
            name="image_file",
            display_name="Image File",
            file_types=["png", "jpg", "jpeg", "webp"],
            info="Optional reference image",
        ),
        MessageTextInput(
            name="image_path",
            display_name="Image Path",
            info="Optional path to reference image",
            advanced=True,
        ),
        StrInput(
            name="project",
            display_name="Project",
            info="The project ID.",
            advanced=True,
        ),
        StrInput(
            name="location",
            display_name="Location",
            value="global",
            advanced=True
        ),
        StrInput(
            name="proxy",
            display_name="Proxy",
            info="HTTP/HTTPS Proxy (e.g. http://127.0.0.1:7890)",
            advanced=True
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=["gemini-3-pro-image-preview", "gemini-2.5-flash-image"],
            value="gemini-3-pro-image-preview",
            info="Model name",
        ),
        DropdownInput(
            name="aspect_ratio",
            display_name="Aspect Ratio",
            options=["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
            value="1:1",
            info="Aspect ratio of the generated image",
            advanced=True
        ),
        DropdownInput(
            name="resolution",
            display_name="Resolution",
            options=["1K", "2K", "4K"],
            value="1K",
            info="Resolution of the generated image (NOTE: gemini-2.5-flash-image only supports 1K)",
            advanced=True
        ),
    ]

    outputs = [
        Output(
            name="media_output",
            display_name="Media Output",
            method="generate_image",
        ),
    ]

    def generate_image(self) -> Data:
        try:
            from google import genai
            from google.genai import types
            from google.auth import default
            from google.oauth2 import service_account
        except ImportError as e:
            raise ImportError("Please install google-genai and google-auth to use Vertex AI.") from e

        # Authentication
        # The new google.genai SDK client can accept credentials directly, or we can set env vars?
        # Looking at the SDK, client(vertexai=True, project=..., location=..., credentials=...) seems plausible
        # or we just set the GOOGLE_APPLICATION_CREDENTIALS env var if a file is provided.

        # Let's try to construct credentials explicitly if provided
        credentials = None
        project = self.project
        location = self.location

        if self.credentials:
            # If user provided a file path
            credentials = service_account.Credentials.from_service_account_file(self.credentials)
            if not project:
                project = credentials.project_id

        client_kwargs = {
            "vertexai": True,
            "project": project,
            "location": location,
        }

        # If user provided a credentials file path in self.credentials, let's strictly use that file for auth
        if self.credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials

        # Handle Proxy
        if self.proxy:
            os.environ["http_proxy"] = self.proxy
            os.environ["https_proxy"] = self.proxy

        client = genai.Client(**client_kwargs)

        # Handle Image Input and Aspect Ratio
        input_image_part = None
        image_source = self.image_file or self.image_path
        
        if image_source:
            try:
                resolved_path = self.resolve_path(image_source)
                p = Path(resolved_path)
                if p.exists():
                    # Calculate aspect ratio
                    try:
                        with Image.open(p) as img:
                            width, height = img.size
                            current_ratio = width / height
                            target_ratios = {
                                "1:1": 1/1, "3:2": 3/2, "2:3": 2/3, "3:4": 3/4, "4:3": 4/3,
                                "4:5": 4/5, "5:4": 5/4, "9:16": 9/16, "16:9": 16/9, "21:9": 21/9
                            }
                            closest = min(target_ratios.keys(), key=lambda k: abs(target_ratios[k] - current_ratio))
                            self.aspect_ratio = closest
                    except Exception as e:
                        print(f"Could not calculate aspect ratio: {e}")

                    # Prepare Image Part
                    mime_type, _ = mimetypes.guess_type(p)
                    if not mime_type:
                        mime_type = "image/png" # Default
                    
                    image_bytes = p.read_bytes()
                    input_image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            except Exception as e:
                print(f"Error processing input image: {e}")

        # Configure generation parameters
        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            response_modalities=["TEXT", "IMAGE"],
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
            ],
            image_config=types.ImageConfig(
                aspect_ratio=str(self.aspect_ratio),
                image_size=str(self.resolution),
                output_mime_type="image/png",
            ),
        )

        # Generate Content
        try:
            parts = [types.Part.from_text(text=str(self.prompt))]
            if input_image_part:
                parts.append(input_image_part)

            contents = [
                types.Content(
                    role="user",
                    parts=parts
                ),
            ]

            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=generate_content_config,
            )
        except Exception as e:
            raise ValueError(f"Error calling Vertex AI via GenAI SDK: {str(e)}")

        # Extract Image
        image_bytes = None

        try:
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        image_bytes = part.inline_data.data
                        break
        except Exception as e:
            self.log(response)
            raise ValueError(f"Failed to parse response from Vertex AI: {str(e)}")

        if not image_bytes:
            print(response)
            raise ValueError(f"No image generated in response.")

        # Save to FileSystem
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = "default"

        workspace_dir = get_workspace_dir()
        output_dir = Path(workspace_dir) / "AIGC" / session_id
        os.makedirs(output_dir, exist_ok=True)

        filename = f"vertex_{uuid.uuid4()}.png"
        file_path = output_dir / filename

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        media_path = str(file_path)
        media_type = "image"

        media_data = {
            "path": media_path,
            "type": media_type,
            "alt": self.prompt,
            "showControls": True,
            "autoPlay": False,
            "loop": False,
        }

        self.status = f"Generated image: {media_path}"

        return Data(data=media_data)
