import json
from pathlib import Path
from typing import Any

from json_repair import repair_json
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import FileInput, MessageTextInput, MultilineInput, Output, BoolInput
from vibe_surf.langflow.schema import Data, DataFrame
from vibe_surf.langflow.io import Output, MessageTextInput


class LoadJSONComponent(Component):
    display_name = "Load JSON"
    description = "Convert a JSON file or a JSON string to Data or Data list."
    icon = "braces"
    name = "LoadJSON"

    inputs = [
        FileInput(
            name="json_file",
            display_name="JSON File",
            fileTypes=["json"],
            info="Import a valid JSON file",
        ),
        MessageTextInput(
            name="json_path",
            display_name="JSON File Path",
            info="File path to the JSON file",
            advanced=True
        ),
        MultilineInput(
            name="json_string",
            display_name="JSON String",
            info="Enter a valid JSON string",
        ),
        BoolInput(
            name="is_list",
            display_name="Is List",
            info="If true, return DataFrame instead of Data",
            value=False,
            real_time_refresh=True
        )

    ]

    outputs = [
        Output(
            name="data",
            display_name="Data",
            method="convert_json_to_data",
            types=['Data'],
        ),
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "is_list":
            frontend_node["outputs"] = []
            # Add only the selected output type
            if field_value:
                frontend_node["outputs"].append(
                    Output(
                        name="data",
                        display_name="Data Frame",
                        method="convert_json_to_data",
                        types=['DataFrame'],
                    ).to_dict()
                )
            else:
                frontend_node["outputs"].append(
                    Output(
                        name="data",
                        display_name="Data",
                        method="convert_json_to_data",
                        types=['Data'],
                    ).to_dict()
                )

        return frontend_node

    def convert_json_to_data(self) -> Data | DataFrame:
        if sum(bool(field) for field in [self.json_file, self.json_path, self.json_string]) != 1:
            msg = "Please provide exactly one of: JSON file, file path, or JSON string."
            self.status = msg
            raise ValueError(msg)

        json_data = None

        try:
            if self.json_file:
                resolved_path = self.resolve_path(self.json_file)
                file_path = Path(resolved_path)
                if file_path.suffix.lower() != ".json":
                    self.status = "The provided file must be a JSON file."
                else:
                    json_data = file_path.read_text(encoding="utf-8")

            elif self.json_path:
                file_path = Path(self.json_path)
                if file_path.suffix.lower() != ".json":
                    self.status = "The provided file must be a JSON file."
                else:
                    json_data = file_path.read_text(encoding="utf-8")

            else:
                json_data = self.json_string

            if json_data:
                # Try to parse the JSON string
                try:
                    parsed_data = json.loads(json_data)
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to repair the JSON string
                    repaired_json_string = repair_json(json_data)
                    parsed_data = json.loads(repaired_json_string)

                # Check if the parsed data is a list
                if isinstance(parsed_data, list):
                    result = DataFrame([Data(data=item) for item in parsed_data])
                else:
                    result = Data(data=parsed_data)
                self.status = result
                return result

        except (json.JSONDecodeError, SyntaxError, ValueError) as e:
            error_message = f"Invalid JSON or Python literal: {e}"
            self.status = error_message
            raise ValueError(error_message) from e

        except Exception as e:
            error_message = f"An error occurred: {e}"
            self.status = error_message
            raise ValueError(error_message) from e

        # An error occurred
        raise ValueError(self.status)
