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


class BrowserUseAgentTask(BaseModel):
    """Parameters for a single browser_use agent task"""
    tab_id: str | None = Field(
        default=None,
        description='Tab ID to execute the task on. If None, a new blank page will be created',
    )
    task: str = Field(
        description='Task description focusing on what needs to be done, goals, and expected returns. Browser_use agent has its own planning and execution capabilities',
    )
    necessary_files: list[str] | None = Field(
        default=None,
        description='Optional list of file paths that may be needed for executing this task',
    )


class BrowserUseAgentExecution(BaseModel):
    """Parameters for executing browser_use agent tasks in parallel"""
    tasks: list[BrowserUseAgentTask] = Field(
        description='List of tasks to execute concurrently using browser_use agents for improved efficiency',
        min_length=1,
    )


class ReportWriterTask(BaseModel):
    """Parameters for report writer agent task"""
    task: str = Field(
        description='Task description including report requirements, goals, insights seen, and any hints or tips for generating the report',
    )


class TodoGenerateAction(BaseModel):
    """Parameters for generating todo.md file"""
    todo_items: list[str] = Field(
        description='List of todo items to write to todo.md file',
        min_length=1,
    )


class TodoModifyAction(BaseModel):
    """Parameters for modifying todo items"""
    modifications: list[dict] = Field(
        description='List of modifications to apply. Each dict should have "action" key with values "add"/"remove"/"complete"/"uncomplete" and "item" key for the todo item text',
        min_length=1,
    )
