from vibe_surf.langflow.custom.custom_component.component import Component
from vibe_surf.langflow.field_typing.range_spec import RangeSpec
from vibe_surf.langflow.inputs.inputs import DataInput, IntInput, DataFrameInput
from vibe_surf.langflow.io import Output
from vibe_surf.langflow.schema.data import Data


class SelectDataComponent(Component):
    display_name: str = "Select DataFrame"
    description: str = "Select a single data from DataFrame."
    name: str = "SelectDataFrame"
    icon = "prototypes"

    inputs = [
        DataFrameInput(
            name="data_frame",
            display_name="Data Frame",
            info="Data frame to select from.",
        ),
        IntInput(
            name="data_index",
            display_name="Data Index",
            info="Index of the data to select.",
            value=0,  # Will be populated dynamically based on the length of data_list
            range_spec=RangeSpec(min=0, max=15, step=1, step_type="int"),
        ),
    ]

    outputs = [
        Output(display_name="Selected Data", name="selected_data", method="select_data"),
    ]

    async def select_data(self) -> Data:
        # Retrieve the selected index from the dropdown
        selected_index = int(self.data_index)
        # Validate that the selected index is within bounds
        if selected_index < 0 or selected_index >= len(self.data_frame):
            msg = f"Selected index {selected_index} is out of range."
            raise ValueError(msg)

        # Return the selected Data object
        selected_data = self.data_frame.iloc[selected_index].to_dict()
        self.status = selected_data  # Update the component status to reflect the selected data
        return Data(data=selected_data)
