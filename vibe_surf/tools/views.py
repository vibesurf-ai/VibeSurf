from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field


class HoverAction(BaseModel):
    """Parameters for hover action"""
    index: int | None = None
    xpath: str | None = None
    selector: str | None = None


class ExtractionAction(BaseModel):
    query: str = Field(
        default="summary this page",
        description='Extraction goal',
    )
    extract_links: bool | None = Field(
        default=False,
        description='Whether to extract links',
    )
    tab_id: str | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description='exact 4 character Tab ID of the tab for extraction',
    )  # last 4 chars of TargetID


class FileExtractionAction(BaseModel):
    """Parameters for file content extraction action"""
    file_path: str = Field(
        description='Path to the file to extract content from',
    )
    query: str = Field(
        default="Extract and summarize the content from this file",
        description='Query or instruction for content extraction',
    )
