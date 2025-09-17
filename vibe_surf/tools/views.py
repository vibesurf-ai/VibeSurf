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
    task_files: list[str] | None = Field(
        default=None,
        description='Optional list of file paths that may be needed for executing this task',
    )


class BrowserUseAgentExecution(BaseModel):
    """Parameters for executing browser_use agent tasks in parallel"""
    tasks: list[BrowserUseAgentTask] = Field(
        description='List of tasks to execute concurrently using browser_use agents for improved efficiency. '
                    'If only one task is provided, the agent can take over the entire browser and can also see and operate all tabs.',
        min_length=1,
    )

class BrowserUseFile(BaseModel):
    file_path: str = Field(description='Path to the file')
    file_description: str = Field(
        description='Description of the file. Briefly describe what this file is and what key information it contains.',
    )


class BrowserUseDoneAction(BaseModel):
    """Parameters for done browser_use agent tasks"""
    text: str
    files_to_return: list[BrowserUseFile] | None = Field(
        description='List of files relative to user request or task.',
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


class TodoModification(BaseModel):
    """Single todo modification operation"""
    action: str = Field(
        description='Type of modification: "add", "remove", "complete", or "uncompleted"',
    )
    item: str = Field(
        description='Text of the todo item to operate on',
    )

class TodoModifyAction(BaseModel):
    """Parameters for modifying todo items"""
    modifications: list[TodoModification] = Field(
        description='List of todo modifications to apply',
        min_length=1,
    )



class VibeSurfDoneAction(BaseModel):
    """Parameters for task completion output"""
    response: str = Field(
        description='Task completion response - can be simple response for basic tasks or comprehensive markdown summary for complex tasks with key findings, results, and file links',
    )
    suggestion_follow_tasks: list[str] | None = Field(
        default=None,
        description='Optional list of 1-3 suggested follow-up tasks. Each task can only be described in one sentence, and each task must be strongly related to or extended from the original task.',
        max_length=3,
    )
