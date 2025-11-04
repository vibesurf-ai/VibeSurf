import json
from typing import Dict, Any, List, Optional
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import Output, TableInput
from vibe_surf.langflow.io import (
    BoolInput,
    HandleInput,
    MessageTextInput,
    MultilineInput,
    Output,
    TableInput,
)
from vibe_surf.langflow.schema.data import Data
from vibe_surf.langflow.schema.dataframe import DataFrame
from vibe_surf.langflow.schema.table import EditMode


class VariableManagerComponent(Component):
    display_name = "Variable Manager"
    description = "Manage variables with key-value pairs, descriptions, and types"
    icon = "settings"
    name = "VariableManager"

    inputs = [
        TableInput(
            name="variables",
            display_name="Variables",
            info="Manage your variables with key, value, description and type.",
            required=False,
            table_schema=[
                {
                    "name": "key",
                    "display_name": "Key",
                    "type": "str",
                    "description": "The variable key/name",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "value",
                    "display_name": "Value",
                    "type": "str",
                    "description": "The variable value",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Optional description of the variable",
                    "edit_mode": EditMode.POPOVER,
                    "required": False,
                },
                {
                    "name": "type",
                    "display_name": "Type",
                    "type": "str",
                    "edit_mode": EditMode.INLINE,
                    "description": "Data type of the variable",
                    "options": ["str", "int", "float", "bool", "dict", "list"],
                    "default": "str",
                },
            ],
            value=[],
            real_time_refresh=True
        ),
        MessageTextInput(
            name="var_input",
            display_name="Variable Input",
            info='JSON string to update variables (format: {"key": "value", "key2": "value2"})',
            required=False
        ),
    ]

    outputs = [
        Output(display_name="Variables Data", name="variables_data", method="build_variables", types=['Data'],
               group_outputs=True),
    ]

    def build_variables(self) -> Data:
        variables_dict = {}

        if self.variables:
            for row in self.variables:
                if "key" in row and "value" in row:
                    key = row["key"]
                    value = row["value"]
                    var_type = row.get("type", "str")

                    try:
                        if var_type == "int":
                            value = int(value)
                        elif var_type == "float":
                            value = float(value)
                        elif var_type == "bool":
                            value = value.lower() in ("true", "1", "yes", "on")
                        elif var_type == "dict":
                            value = json.loads(value) if isinstance(value, str) else value
                        elif var_type == "list":
                            value = json.loads(value) if isinstance(value, str) else value
                    except (ValueError, json.JSONDecodeError) as e:
                        self.log(f"Error converting value for key '{key}': {e}")

                    variables_dict[key] = value

        if self.var_input:
            try:
                try:
                    json_data = json.loads(self.var_input)
                except json.JSONDecodeError as e:
                    from json_repair import repair_json
                    json_data = json.loads(repair_json(self.var_input))

                if isinstance(json_data, dict):
                    current_table = list(self.variables_table) if self.variables_table else []

                    for json_key, json_value in json_data.items():
                        found = False
                        for i, row in enumerate(current_table):
                            if row.get("key") == json_key:
                                current_table[i]["value"] = str(json_value)
                                found = True
                                break

                        if not found:
                            current_table.append({
                                "key": json_key,
                                "value": str(json_value),
                                "description": "",
                                "type": "str"
                            })

                    variables_dict.update(json_data)

                    self.log(f"Updated variables from JSON input: {json_data}")
                else:
                    self.log("JSON input must be a dictionary")
            except json.JSONDecodeError as e:
                self.log(f"Invalid JSON input: {e}")

        return Data(data=variables_dict)
