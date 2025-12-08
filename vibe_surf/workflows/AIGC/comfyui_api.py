import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image

from vibe_surf.common import get_workspace_dir
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import (
    BoolInput,
    FileInput,
    MessageTextInput,
    Output,
    TableInput,
)
from vibe_surf.langflow.schema import Data, DataFrame
from vibe_surf.langflow.schema.table import EditMode


class ComfyUIAPIComponent(Component):
    display_name = "ComfyUI API"
    description = "Execute ComfyUI workflows via API."
    icon = "cpu"
    name = "ComfyUIAPI"

    inputs = [
        MessageTextInput(
            name="base_url",
            display_name="ComfyUI Base URL",
            info="The address of the ComfyUI server (e.g., localhost:8188).",
            value="localhost:8188",
            required=True,
        ),
        FileInput(
            name="workflow_file",
            display_name="Workflow JSON File",
            file_types=["json"],
            info="Upload the workflow.json or workflow_api.json file.",
        ),
        MessageTextInput(
            name="workflow_path",
            display_name="Workflow JSON Path",
            info="Path to the workflow.json file (alternative to upload).",
            advanced=True,
        ),
        TableInput(
            name="parameters",
            display_name="Parameters",
            info="Set parameters for workflow nodes (e.g., Prompt, Seed).",
            table_schema=[
                {
                    "name": "node_key",
                    "display_name": "Node Key",
                    "type": "str",
                    "description": "Node title or class type (e.g., 'KSampler', 'CLIPTextEncode').",
                    "default": "CLIPTextEncode",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "param_name",
                    "display_name": "Param Name",
                    "type": "str",
                    "description": "Parameter name (e.g., 'seed', 'text', 'steps').",
                    "default": "text",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "param_value",
                    "display_name": "Value",
                    "type": "str",
                    "description": "Parameter value.",
                    "default": "",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "param_type",
                    "display_name": "Type",
                    "type": "str",
                    "description": "Data type (str, int, float, bool).",
                    "options": ["str", "int", "float", "bool", "dict"],
                    "default": "str",
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[
                {
                    "node_key": "Node Key",
                    "param_name": "Param Name",
                    "param_value": "Param Value",
                    "param_type": "str",
                }
            ],
        ),
        MessageTextInput(
            name="output_node_names",
            display_name="Output Node Names",
            info="Optional: Comma-separated list of node titles to fetch results from (e.g. 'Save Image'). If empty, fetches all outputs.",
        ),
        BoolInput(
            name="is_list",
            display_name="Is List",
            info="If true, return a list of results (DataFrame). Otherwise return a single Data object.",
            value=False,
            real_time_refresh=True,
        ),
    ]

    outputs = [
        Output(
            name="data",
            display_name="Data",
            method="generate_images",
            types=['Data'],
        ),
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "is_list":
            frontend_node["outputs"] = []
            if field_value:
                frontend_node["outputs"].append(
                    Output(
                        name="data",
                        display_name="Data Frame",
                        method="generate_images",
                        types=['DataFrame'],
                    ).to_dict()
                )
            else:
                frontend_node["outputs"].append(
                    Output(
                        name="data",
                        display_name="Data",
                        method="generate_images",
                        types=['Data'],
                    ).to_dict()
                )
        return frontend_node

    def generate_images(self) -> Data | DataFrame:
        try:
            from comfyuiclient import ComfyUIClient
        except ImportError as e:
            raise ImportError("Please install comfyuiclient to use this component.") from e

        # Resolve workflow file
        workflow_path_str = self.workflow_path
        if self.workflow_file:
            workflow_path_str = self.resolve_path(self.workflow_file)
        
        if not workflow_path_str:
            raise ValueError("Please provide either a Workflow File or Workflow Path.")

        # Initialize Client
        try:
            client = ComfyUIClient(self.base_url, workflow_path_str)
            client.connect()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to ComfyUI at {self.base_url}: {str(e)}")

        # Set Parameters
        if self.parameters:
            for row in self.parameters:
                node_key = row.get("node_key")
                param_name = row.get("param_name")
                param_value_str = row.get("param_value")
                param_type = row.get("param_type", "str")

                if not node_key or not param_name:
                    continue

                # Cast value
                value = param_value_str
                if param_type == "int":
                    try:
                        value = int(param_value_str)
                    except (ValueError, TypeError):
                        self.status = f"Invalid int value for {param_name}: {param_value_str}"
                        continue
                elif param_type == "float":
                    try:
                        value = float(param_value_str)
                    except (ValueError, TypeError):
                        self.status = f"Invalid float value for {param_name}: {param_value_str}"
                        continue
                elif param_type == "bool":
                    value = str(param_value_str).lower() in ("true", "1", "yes", "on")
                elif param_type == "image_path":
                    # Load image
                    try:
                        resolved_img_path = self.resolve_path(param_value_str)
                        value = Image.open(resolved_img_path)
                    except Exception as e:
                        self.status = f"Failed to load image from {param_value_str}: {e}"
                        continue
                
                # Construct kwargs
                kwargs = {param_name: value}
                try:
                    client.set_data(key=node_key, **kwargs)
                except Exception as e:
                    print(f"Failed to set data for {node_key}: {e}")

        # Generate
        try:
            node_names = None
            if self.output_node_names:
                node_names = [n.strip() for n in self.output_node_names.split(",") if n.strip()]
            
            results = client.generate(node_names)
        except Exception as e:
            client.close()
            raise ValueError(f"Generation failed: {str(e)}")
        
        # Save results
        saved_files = []
        workspace_dir = get_workspace_dir()
        
        # Determine session ID
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = "default"

        output_dir = Path(workspace_dir) / "AIGC" / session_id
        os.makedirs(output_dir, exist_ok=True)

        for key, image in results.items():
            filename = f"comfy_{uuid.uuid4()}.png"
            file_path = output_dir / filename
            try:
                image.save(file_path)
                
                saved_files.append({
                    "path": str(file_path),
                    "type": "image",
                    "alt": f"Generated by ComfyUI node {key}",
                    "node": key,
                    "showControls": True,
                    "autoPlay": False,
                    "loop": False,
                })
            except Exception as e:
                print(f"Failed to save image {key}: {e}")

        client.close()

        if not saved_files:
            self.status = "No images generated."
            if self.is_list:
                return DataFrame([])
            return Data(data={})

        self.status = f"Generated {len(saved_files)} images."

        if self.is_list:
            return DataFrame([Data(data=f) for f in saved_files])
        else:
            # If not list, return the first one
            return Data(data=saved_files[0])