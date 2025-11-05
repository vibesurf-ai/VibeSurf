import asyncio
import json
import logging
import os
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid_extensions import uuid7str
from json_repair import repair_json

from browser_use.browser.session import BrowserSession
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage, SystemMessage, BaseMessage, AssistantMessage, ContentPartTextParam, \
    ContentPartImageParam, ImageURL
from browser_use.browser.views import TabInfo, BrowserStateSummary
from browser_use.filesystem.file_system import FileSystem
from browser_use.agent.views import AgentSettings
from pydantic import BaseModel, Field, ConfigDict, create_model
from browser_use.agent.views import AgentSettings, DEFAULT_INCLUDE_ATTRIBUTES
from browser_use.tools.registry.views import ActionModel


class VibeSurfAgentOutput(BaseModel):
    """Agent output model following browser_use patterns"""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra='forbid')

    thinking: str | None = None
    action: List[Any] = Field(
        ...,
        description='List of actions to execute',
        json_schema_extra={'min_items': 1},
    )

    @classmethod
    def model_json_schema(cls, **kwargs):
        schema = super().model_json_schema(**kwargs)
        schema['required'] = ['thinking', 'action']
        return schema

    @staticmethod
    def type_with_custom_actions(custom_actions: type) -> type:
        """Extend actions with custom actions"""
        model_ = create_model(
            'VibeSurfAgentOutput',
            __base__=VibeSurfAgentOutput,
            action=(
                list[custom_actions],  # type: ignore
                Field(..., description='List of actions to execute', json_schema_extra={'min_items': 1}),
            ),
            __module__=VibeSurfAgentOutput.__module__,
        )
        model_.__doc__ = 'VibeSurfAgentOutput model with custom actions'
        return model_


class VibeSurfAgentSettings(BaseModel):
    use_vision: bool = True
    max_failures: int = 3
    override_system_message: str | None = None
    extend_system_message: str | None = None
    include_attributes: list[str] | None = DEFAULT_INCLUDE_ATTRIBUTES
    max_actions_per_step: int = 4
    max_history_items: int | None = None
    include_token_cost: bool = False

    calculate_cost: bool = True
    include_tool_call_examples: bool = False
    llm_timeout: int = 60  # Timeout in seconds for LLM calls
    step_timeout: int = 180  # Timeout in seconds for each step

    agent_mode: str = "thinking"  # thinking, no-thinking, flash


class CustomAgentOutput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra='forbid')
    thinking: str | None = None
    action: ActionModel = Field(
        ...,
        description='Action to execute',
    )
    @classmethod
    def model_json_schema(cls, **kwargs):
        schema = super().model_json_schema(**kwargs)
        schema['required'] = ['action']
        return schema
    @staticmethod
    def type_with_custom_actions(custom_actions: type[ActionModel]) -> type['CustomAgentOutput']:
        """Extend actions with custom actions"""
        model_ = create_model(
            'AgentOutput',
            __base__=CustomAgentOutput,
            action=(
                custom_actions,  # type: ignore
                Field(..., description='Action to execute'),
            ),
            __module__=CustomAgentOutput.__module__,
        )
        model_.__doc__ = 'AgentOutput model with custom actions'
        return model_
    @staticmethod
    def type_with_custom_actions_no_thinking(custom_actions: type[ActionModel]) -> type['CustomAgentOutput']:
        """Extend actions with custom actions and exclude thinking field"""
        class AgentOutputNoThinking(CustomAgentOutput):
            @classmethod
            def model_json_schema(cls, **kwargs):
                schema = super().model_json_schema(**kwargs)
                del schema['properties']['thinking']
                schema['required'] = ['action']
                return schema
        model = create_model(
            'AgentOutputNoThinking',
            __base__=AgentOutputNoThinking,
            action=(
                custom_actions,  # type: ignore
                Field(..., description='Action to execute'),
            ),
            __module__=AgentOutputNoThinking.__module__,
        )
        model.__doc__ = 'AgentOutput model with custom actions'
        return model
