from vibe_surf.langflow.base.io.text import TextComponent
from vibe_surf.langflow.io import MultilineInput, Output
from vibe_surf.langflow.schema.message import Message
import json
from typing import Any, List, Dict
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, IntInput, DataInput
from vibe_surf.langflow.io import BoolInput, Output
from vibe_surf.logger import get_logger
from vibe_surf.langflow.schema.data import Data


class DataOutputComponent(Component):
    display_name = "Data Output"
    description = "Sends data output via API."
    icon = "database"
    name = "DataOutput"

    inputs = [
        DataInput(
            name="input_data",
            display_name="Data Input",
            info="Data to be passed as output.",
        ),
    ]
    outputs = [
        Output(display_name="Output Data", name="output_data", method="data_response"),
    ]

    def data_response(self) -> Data:
        return self.input_data