from pydantic import BaseModel, field_serializer
from pydantic_core import PydanticSerializationError

from vibe_surf.langflow.schema.log import LoggableType
from vibe_surf.langflow.serialization.serialization import serialize


class Log(BaseModel):
    name: str
    message: LoggableType
    type: str

    @field_serializer("message")
    def serialize_message(self, value):
        try:
            return serialize(value)
        except UnicodeDecodeError:
            return str(value)  # Fallback to string representation
        except PydanticSerializationError:
            return str(value)  # Fallback to string for Pydantic errors
