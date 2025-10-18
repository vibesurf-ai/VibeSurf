import httpx
from lfx.load.utils import UploadError, replace_tweaks_with_env, upload, upload_file

from vibe_surf.backend.langflow.services.database.models.flow.model import FlowBase


def get_flow(url: str, flow_id: str):
    """Get the details of a flow from vibe_surf.backend.langflow.

    Args:
        url (str): The host URL of vibe_surf.backend.langflow.
        port (int): The port number of vibe_surf.backend.langflow.
        flow_id (UUID): The ID of the flow to retrieve.

    Returns:
        dict: A dictionary containing the details of the flow.

    Raises:
        UploadError: If an error occurs during the retrieval process.
    """
    try:
        flow_url = f"{url}/api/v1/flows/{flow_id}"
        response = httpx.get(flow_url)
        if response.status_code == httpx.codes.OK:
            json_response = response.json()
            return FlowBase(**json_response).model_dump()
    except Exception as e:
        msg = f"Error retrieving flow: {e}"
        raise UploadError(msg) from e


__all__ = ["UploadError", "get_flow", "replace_tweaks_with_env", "upload", "upload_file"]
