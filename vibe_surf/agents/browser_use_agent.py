import asyncio
import gc
import inspect
import json
import logging
import os.path
import pdb
import re
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

from browser_use.agent.cloud_events import (
    CreateAgentOutputFileEvent,
    CreateAgentSessionEvent,
    CreateAgentStepEvent,
    CreateAgentTaskEvent,
    UpdateAgentTaskEvent,
)
from browser_use.agent.message_manager.utils import save_conversation
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import BaseMessage, UserMessage
from browser_use.llm.openai.chat import ChatOpenAI
from browser_use.tokens.service import TokenCost

from bubus import EventBus
from pydantic import ValidationError
from uuid_extensions import uuid7str

# Lazy import for gif to avoid heavy agent.views import at startup
# from browser_use.agent.gif import create_history_gif
from browser_use.agent.message_manager.service import (
    MessageManager,
)
from browser_use.agent.prompts import SystemPrompt
from browser_use.agent.views import (
    ActionResult,
    AgentError,
    AgentHistory,
    AgentHistoryList,
    AgentOutput,
    AgentSettings,
    AgentState,
    AgentStepInfo,
    AgentStructuredOutput,
    BrowserStateHistory,
    StepMetadata,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model, model_validator
from browser_use import Browser, BrowserProfile, BrowserSession
from browser_use.browser.session import DEFAULT_BROWSER_PROFILE
from browser_use.browser.views import BrowserStateSummary
from browser_use.config import CONFIG
from browser_use.tools.registry.views import ActionModel
from browser_use.tools.service import Controller, Tools
from browser_use.dom.views import DOMInteractedElement
from browser_use.filesystem.file_system import FileSystem
from browser_use.observability import observe, observe_debug
from browser_use.sync import CloudSync
from browser_use.telemetry.views import AgentTelemetryEvent
from browser_use.utils import (
    _log_pretty_path,
    get_browser_use_version,
    get_git_info,
    time_execution_async,
    time_execution_sync,
)
from browser_use.llm.messages import BaseMessage, ContentPartImageParam, ContentPartTextParam, UserMessage
from browser_use.agent.service import Agent, AgentHookFunc
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.telemetry.service import ProductTelemetry

Context = TypeVar('Context')


class BrowserUseAgent(Agent):
    @time_execution_sync('--init')
    def __init__(
            self,
            task: str,
            llm: BaseChatModel = ChatOpenAI(model='gpt-4.1-mini'),
            # Optional parameters
            browser_profile: BrowserProfile | None = None,
            browser_session: BrowserSession | None = None,
            browser: Browser | None = None,  # Alias for browser_session
            tools: Tools[Context] | None = None,
            controller: Tools[Context] | None = None,  # Alias for tools
            # Initial agent run parameters
            sensitive_data: dict[str, str | dict[str, str]] | None = None,
            initial_actions: list[dict[str, dict[str, Any]]] | None = None,
            # Cloud Callbacks
            register_new_step_callback: (
                    Callable[['BrowserStateSummary', 'AgentOutput', int], None]  # Sync callback
                    | Callable[['BrowserStateSummary', 'AgentOutput', int], Awaitable[None]]  # Async callback
                    | None
            ) = None,
            register_done_callback: (
                    Callable[['AgentHistoryList'], Awaitable[None]]  # Async Callback
                    | Callable[['AgentHistoryList'], None]  # Sync Callback
                    | None
            ) = None,
            register_external_agent_status_raise_error_callback: Callable[[], Awaitable[bool]] | None = None,
            register_should_stop_callback: Callable[[], Awaitable[bool]] | None = None,
            # Agent settings
            output_model_schema: type[AgentStructuredOutput] | None = None,
            use_vision: bool = True,
            save_conversation_path: str | Path | None = None,
            save_conversation_path_encoding: str | None = 'utf-8',
            max_failures: int = 3,
            override_system_message: str | None = None,
            extend_system_message: str | None = None,
            generate_gif: bool | str = False,
            available_file_paths: list[str] | None = None,
            include_attributes: list[str] | None = None,
            max_actions_per_step: int = 10,
            use_thinking: bool = True,
            flash_mode: bool = False,
            max_history_items: int | None = None,
            page_extraction_llm: BaseChatModel | None = None,
            injected_agent_state: AgentState | None = None,
            source: str | None = None,
            file_system_path: str | None = None,
            task_id: str | None = None,
            calculate_cost: bool = False,
            display_files_in_done_text: bool = True,
            include_tool_call_examples: bool = False,
            vision_detail_level: Literal['auto', 'low', 'high'] = 'auto',
            llm_timeout: int = 90,
            step_timeout: int = 120,
            directly_open_url: bool = False,
            include_recent_events: bool = False,
            sample_images: list[ContentPartTextParam | ContentPartImageParam] | None = None,
            final_response_after_failure: bool = True,
            _url_shortening_limit: int = 25,
            token_cost_service: Optional[TokenCost] = None,
            **kwargs,
    ):
        if page_extraction_llm is None:
            page_extraction_llm = llm
        if available_file_paths is None:
            available_file_paths = []

        self.id = task_id or uuid7str()
        self.task_id: str = self.id
        self.session_id: str = uuid7str()
        self._url_shortening_limit = _url_shortening_limit
        self.sample_images = sample_images
        browser_profile = browser_profile or DEFAULT_BROWSER_PROFILE

        # Handle browser vs browser_session parameter (browser takes precedence)
        if browser and browser_session:
            raise ValueError(
                'Cannot specify both "browser" and "browser_session" parameters. Use "browser" for the cleaner API.')
        browser_session = browser or browser_session

        self.browser_session = browser_session or BrowserSession(
            browser_profile=browser_profile,
            id=uuid7str()[:-4] + self.id[-4:],  # re-use the same 4-char suffix so they show up together in logs
        )

        # Initialize available file paths as direct attribute
        self.available_file_paths = available_file_paths

        # Core components
        self.task = task
        self.llm = llm
        self.directly_open_url = directly_open_url
        self.include_recent_events = include_recent_events
        if tools is not None:
            self.tools = tools
        elif controller is not None:
            self.tools = controller
        else:
            self.tools = Tools(display_files_in_done_text=display_files_in_done_text)

        # Structured output
        self.output_model_schema = output_model_schema
        if self.output_model_schema is not None:
            self.tools.use_structured_output_action(self.output_model_schema)

        self.sensitive_data = sensitive_data

        self.settings = AgentSettings(
            use_vision=use_vision,
            vision_detail_level=vision_detail_level,
            save_conversation_path=save_conversation_path,
            save_conversation_path_encoding=save_conversation_path_encoding,
            max_failures=max_failures,
            override_system_message=override_system_message,
            extend_system_message=extend_system_message,
            generate_gif=generate_gif,
            include_attributes=include_attributes,
            max_actions_per_step=max_actions_per_step,
            use_thinking=use_thinking,
            flash_mode=flash_mode,
            max_history_items=max_history_items,
            page_extraction_llm=page_extraction_llm,
            calculate_cost=calculate_cost,
            include_tool_call_examples=include_tool_call_examples,
            llm_timeout=llm_timeout,
            step_timeout=step_timeout,
            final_response_after_failure=final_response_after_failure,
        )

        # Token cost service
        if token_cost_service is None:
            self.token_cost_service = TokenCost(include_cost=calculate_cost)
        else:
            self.token_cost_service = token_cost_service
        self.token_cost_service.register_llm(llm)
        self.token_cost_service.register_llm(page_extraction_llm)

        # Initialize state
        self.state = injected_agent_state or AgentState()

        # Initialize history
        self.history = AgentHistoryList(history=[], usage=None)

        # Initialize agent directory
        import time

        timestamp = int(time.time())
        base_tmp = Path(tempfile.gettempdir())
        self.agent_directory = base_tmp / f'browser_use_agent_{self.id}_{timestamp}'

        # Initialize file system and screenshot service
        self._set_file_system(file_system_path)
        self._set_screenshot_service()

        # Action setup
        self._setup_action_models()
        self._set_browser_use_version_and_source(source)

        initial_url = None

        # only load url if no initial actions are provided
        if self.directly_open_url and not self.state.follow_up_task and not initial_actions:
            initial_url = self._extract_url_from_task(self.task)
            if initial_url:
                self.logger.info(f'🔗 Found URL in task: {initial_url}, adding as initial action...')
                initial_actions = [{'go_to_url': {'url': initial_url, 'new_tab': False}}]

        self.initial_url = initial_url

        self.initial_actions = self._convert_initial_actions(initial_actions) if initial_actions else None
        # Verify we can connect to the model
        self._verify_and_setup_llm()

        # TODO: move this logic to the LLMs
        # Handle users trying to use use_vision=True with DeepSeek models
        if 'deepseek' in self.llm.model.lower():
            self.logger.warning(
                '⚠️ DeepSeek models do not support use_vision=True yet. Setting use_vision=False for now...')
            self.settings.use_vision = False

        if 'kimi-k2' in self.llm.model.lower():
            self.logger.warning(
                '⚠️ Kimi-k2 models do not support use_vision=True yet. Setting use_vision=False for now...')
            self.settings.use_vision = False

        if "qwen" in self.llm.model.lower() and "vl" not in self.llm.model.lower():
            self.logger.warning("⚠️ Qwen without VL doesn't support vision. Ignore Vision input.")
            self.settings.use_vision = False

        # Handle users trying to use use_vision=True with XAI models
        if 'grok' in self.llm.model.lower():
            self.logger.warning('⚠️ XAI models do not support use_vision=True yet. Setting use_vision=False for now...')
            self.settings.use_vision = False

        self.logger.info(f'🧠 Starting a browser-use version {self.version} with model={self.llm.model}')
        self.logger.info(
            f'{" +vision" if self.settings.use_vision else ""}'
            f' extraction_model={self.settings.page_extraction_llm.model if self.settings.page_extraction_llm else "Unknown"}'
            f'{" +file_system" if self.file_system else ""}'
        )

        # Initialize available actions for system prompt (only non-filtered actions)
        # These will be used for the system prompt to maintain caching
        self.unfiltered_actions = self.tools.registry.get_prompt_description()

        # Initialize message manager with state
        # Initial system prompt with all actions - will be updated during each step
        self._message_manager = MessageManager(
            task=task,
            system_message=SystemPrompt(
                max_actions_per_step=self.settings.max_actions_per_step,
                override_system_message=override_system_message,
                extend_system_message=extend_system_message,
                use_thinking=self.settings.use_thinking,
                flash_mode=self.settings.flash_mode,
            ).get_system_message(),
            file_system=self.file_system,
            state=self.state.message_manager_state,
            use_thinking=self.settings.use_thinking,
            # Settings that were previously in MessageManagerSettings
            include_attributes=self.settings.include_attributes,
            sensitive_data=sensitive_data,
            max_history_items=self.settings.max_history_items,
            vision_detail_level=self.settings.vision_detail_level,
            include_tool_call_examples=self.settings.include_tool_call_examples,
            include_recent_events=self.include_recent_events,
            sample_images=self.sample_images,
        )

        if self.sensitive_data:
            # Check if sensitive_data has domain-specific credentials
            has_domain_specific_credentials = any(isinstance(v, dict) for v in self.sensitive_data.values())

            # If no allowed_domains are configured, show a security warning
            if not self.browser_profile.allowed_domains:
                self.logger.error(
                    '⚠️⚠️⚠️ Agent(sensitive_data=••••••••) was provided but BrowserSession(allowed_domains=[...]) is not locked down! ⚠️⚠️⚠️\n'
                    '          ☠️ If the agent visits a malicious website and encounters a prompt-injection attack, your sensitive_data may be exposed!\n\n'
                    '             https://docs.browser-use.com/customize/browser-settings#restrict-urls\n'
                    'Waiting 10 seconds before continuing... Press [Ctrl+C] to abort.'
                )
                if sys.stdin.isatty():
                    try:
                        time.sleep(10)
                    except KeyboardInterrupt:
                        print(
                            '\n\n 🛑 Exiting now... set BrowserSession(allowed_domains=["example.com", "example.org"]) to only domains you trust to see your sensitive_data.'
                        )
                        sys.exit(0)
                else:
                    pass  # no point waiting if we're not in an interactive shell
                self.logger.warning(
                    '‼️ Continuing with insecure settings for now... but this will become a hard error in the future!'
                )

            # If we're using domain-specific credentials, validate domain patterns
            elif has_domain_specific_credentials:
                # For domain-specific format, ensure all domain patterns are included in allowed_domains
                domain_patterns = [k for k, v in self.sensitive_data.items() if isinstance(v, dict)]

                # Validate each domain pattern against allowed_domains
                for domain_pattern in domain_patterns:
                    is_allowed = False
                    for allowed_domain in self.browser_profile.allowed_domains:
                        # Special cases that don't require URL matching
                        if domain_pattern == allowed_domain or allowed_domain == '*':
                            is_allowed = True
                            break

                        # Need to create example URLs to compare the patterns
                        # Extract the domain parts, ignoring scheme
                        pattern_domain = domain_pattern.split('://')[-1] if '://' in domain_pattern else domain_pattern
                        allowed_domain_part = allowed_domain.split('://')[
                            -1] if '://' in allowed_domain else allowed_domain

                        # Check if pattern is covered by an allowed domain
                        # Example: "google.com" is covered by "*.google.com"
                        if pattern_domain == allowed_domain_part or (
                                allowed_domain_part.startswith('*.')
                                and (
                                        pattern_domain == allowed_domain_part[2:]
                                        or pattern_domain.endswith('.' + allowed_domain_part[2:])
                                )
                        ):
                            is_allowed = True
                            break

                    if not is_allowed:
                        self.logger.warning(
                            f'⚠️ Domain pattern "{domain_pattern}" in sensitive_data is not covered by any pattern in allowed_domains={self.browser_profile.allowed_domains}\n'
                            f'   This may be a security risk as credentials could be used on unintended domains.'
                        )

        # Callbacks
        self.register_new_step_callback = register_new_step_callback
        self.register_done_callback = register_done_callback
        self.register_should_stop_callback = register_should_stop_callback
        self.register_external_agent_status_raise_error_callback = register_external_agent_status_raise_error_callback

        # Telemetry
        self.telemetry = ProductTelemetry()

        if self.settings.save_conversation_path:
            self.settings.save_conversation_path = Path(self.settings.save_conversation_path).expanduser().resolve()
            self.logger.info(f'💬 Saving conversation to {_log_pretty_path(self.settings.save_conversation_path)}')

        # Initialize download tracking
        assert self.browser_session is not None, 'BrowserSession is not set up'
        self.has_downloads_path = self.browser_session.browser_profile.downloads_path is not None
        if self.has_downloads_path:
            self._last_known_downloads: list[str] = []
            self.logger.debug('📁 Initialized download tracking for agent')

        self._external_pause_event = asyncio.Event()
        self._external_pause_event.set()

    def _set_file_system(self, file_system_path: str | None = None) -> None:
        # Check for conflicting parameters
        if self.state.file_system_state and file_system_path:
            raise ValueError(
                'Cannot provide both file_system_state (from agent state) and file_system_path. '
                'Either restore from existing state or create new file system at specified path, not both.'
            )

        # Check if we should restore from existing state first
        if self.state.file_system_state:
            try:
                # Restore file system from state at the exact same location
                self.file_system = CustomFileSystem.from_state(self.state.file_system_state)
                # The parent directory of base_dir is the original file_system_path
                self.file_system_path = str(self.file_system.base_dir)
                self.logger.debug(f'💾 File system restored from state to: {self.file_system_path}')
                return
            except Exception as e:
                self.logger.error(f'💾 Failed to restore file system from state: {e}')
                raise e

        # Initialize new file system
        try:
            if file_system_path:
                self.file_system = CustomFileSystem(file_system_path)
                self.file_system_path = file_system_path
            else:
                # Use the agent directory for file system
                self.file_system = CustomFileSystem(self.agent_directory)
                self.file_system_path = str(self.agent_directory)
        except Exception as e:
            self.logger.error(f'💾 Failed to initialize file system: {e}.')
            raise e

        # Save file system state to agent state
        self.state.file_system_state = self.file_system.get_state()

        self.logger.debug(f'💾 File system path: {self.file_system_path}')

    @property
    def logger(self) -> logging.Logger:
        """Get instance-specific logger with task ID and browser session info"""
        # Update target ID dynamically if available
        _browser_session_id = self.browser_session.id if self.browser_session else self.id
        _current_target_id = (
            self.browser_session.agent_focus.target_id[-4:]
            if self.browser_session and hasattr(self.browser_session,
                                                'agent_focus') and self.browser_session.agent_focus and hasattr(
                self.browser_session.agent_focus, 'target_id')
            else '--'
        )
        return logging.getLogger(
            f'browser-use.Agent:{self.task_id[-4:]} on target:{_current_target_id} of browser:{_browser_session_id[-4:]}')

    async def _finalize(self, browser_state_summary: BrowserStateSummary | None) -> None:
        """Finalize the step with history, logging, and events"""
        step_end_time = time.time()
        if not self.state.last_result:
            return

        if browser_state_summary:
            metadata = StepMetadata(
                step_number=self.state.n_steps,
                step_start_time=self.step_start_time,
                step_end_time=step_end_time,
            )

            # Use _make_history_item like main branch
            await self._make_history_item(self.state.last_model_output, browser_state_summary, self.state.last_result,
                                          metadata, state_message=self._message_manager.last_state_message_text,)

        # Log step completion summary
        self._log_step_completion_summary(self.step_start_time, self.state.last_result)

        # Save file system state after step completion
        self.save_file_system_state()

        # Emit both step created and executed events
        if browser_state_summary and self.state.last_model_output:
            # Extract key step data for the event
            actions_data = []
            if self.state.last_model_output.action:
                for action in self.state.last_model_output.action:
                    action_dict = action.model_dump() if hasattr(action, 'model_dump') else {}
                    actions_data.append(action_dict)

        # Increment step counter after step is fully completed
        self.state.n_steps += 1

    def add_new_task(self, new_task: str) -> None:
        """Add a new task to the agent, keeping the same task_id as tasks are continuous"""
        # Simply delegate to message manager - no need for new task_id or events
        # The task continues with new instructions, it doesn't end and start a new one
        self.task = new_task
        self._message_manager.add_new_task(new_task)

        # Mark as follow-up task and recreate eventbus (gets shut down after each run)
        self.state.follow_up_task = True

    @observe(name='agent.run', metadata={'task': '{{task}}', 'debug': '{{debug}}'})
    @time_execution_async('--run')
    async def run(
            self,
            max_steps: int = 100,
            on_step_start: AgentHookFunc | None = None,
            on_step_end: AgentHookFunc | None = None,
    ) -> AgentHistoryList[AgentStructuredOutput]:
        """Execute the task with maximum number of steps"""

        loop = asyncio.get_event_loop()
        agent_run_error: str | None = None  # Initialize error tracking variable
        self._force_exit_telemetry_logged = False  # ADDED: Flag for custom telemetry on force exit

        # Set up the  signal handler with callbacks specific to this agent
        from browser_use.utils import SignalHandler

        # Define the custom exit callback function for second CTRL+C
        def on_force_exit_log_telemetry():
            self._log_agent_event(max_steps=max_steps, agent_run_error='SIGINT: Cancelled by user')
            # NEW: Call the flush method on the telemetry instance
            if hasattr(self, 'telemetry') and self.telemetry:
                self.telemetry.flush()
            self._force_exit_telemetry_logged = True  # Set the flag

        signal_handler = SignalHandler(
            loop=loop,
            pause_callback=self.pause,
            resume_callback=self.resume,
            custom_exit_callback=on_force_exit_log_telemetry,  # Pass the new telemetrycallback
            exit_on_second_int=True,
        )
        signal_handler.register()

        try:
            await self._log_agent_run()

            self.logger.debug(
                f'🔧 Agent setup: Task ID {self.task_id[-4:]}, Session ID {self.session_id[-4:]}, Browser Session ID {self.browser_session.id[-4:] if self.browser_session else "None"}'
            )

            # Initialize timing for session and task
            self._session_start_time = time.time()
            self._task_start_time = self._session_start_time  # Initialize task start time

            self.logger.debug('🔧 Browser session started with watchdogs attached')

            # Execute initial actions if provided
            if self.initial_actions:
                self.logger.debug(f'⚡ Executing {len(self.initial_actions)} initial actions...')
                result = await self.multi_act(self.initial_actions, check_for_new_elements=False)
                self.state.last_result = result
                self.logger.debug('✅ Initial actions completed')

            self.logger.debug(f'🔄 Starting main execution loop with max {max_steps} steps...')
            for step in range(max_steps):
                # Replace the polling with clean pause-wait
                if self.state.paused:
                    self.logger.debug(f'⏸️ Step {step}: Agent paused, waiting to resume...')
                    await self._external_pause_event.wait()
                    signal_handler.reset()

                # Check if we should stop due to too many failures
                if (self.state.consecutive_failures) >= self.settings.max_failures + int(
                        self.settings.final_response_after_failure
                ):
                    self.logger.error(f'❌ Stopping due to {self.settings.max_failures} consecutive failures')
                    agent_run_error = f'Stopped due to {self.settings.max_failures} consecutive failures'
                    break

                # Check control flags before each step
                if self.state.stopped:
                    self.logger.info('🛑 Agent stopped')
                    agent_run_error = 'Agent stopped programmatically'
                    break

                if on_step_start is not None:
                    await on_step_start(self)

                self.logger.debug(f'🚶 Starting step {step + 1}/{max_steps}...')
                step_info = AgentStepInfo(step_number=step, max_steps=max_steps)
                is_done = await self._execute_step(step, max_steps, step_info, on_step_start, on_step_end)

                if is_done:
                    # Task completed
                    break
            else:
                agent_run_error = 'Failed to complete task in maximum steps'

                self.history.add_item(
                    AgentHistory(
                        model_output=None,
                        result=[ActionResult(error=agent_run_error, include_in_memory=True)],
                        state=BrowserStateHistory(
                            url='',
                            title='',
                            tabs=[],
                            interacted_element=[],
                            screenshot_path=None,
                        ),
                        metadata=None,
                    )
                )

                self.logger.info(f'❌ {agent_run_error}')

            self.logger.debug('📊 Collecting usage summary...')
            self.history.usage = await self.token_cost_service.get_usage_summary()

            # set the model output schema and call it on the fly
            if self.history._output_model_schema is None and self.output_model_schema is not None:
                self.history._output_model_schema = self.output_model_schema

            self.logger.debug('🏁 Agent.run() completed successfully')
            return self.history

        except KeyboardInterrupt:
            # Already handled by our signal handler, but catch any direct KeyboardInterrupt as well
            self.logger.debug('Got KeyboardInterrupt during execution, returning current history')
            agent_run_error = 'KeyboardInterrupt'

            self.history.usage = await self.token_cost_service.get_usage_summary()

            return self.history

        except Exception as e:
            self.logger.error(f'Agent run failed with exception: {e}', exc_info=True)
            agent_run_error = str(e)
            raise e

        finally:
            # Log token usage summary
            await self.token_cost_service.log_usage_summary()

            self.save_history(os.path.join(self.file_system_path, 'AgentHistory.json'))

            # Unregister signal handlers before cleanup
            signal_handler.unregister()

            if not self._force_exit_telemetry_logged:  # MODIFIED: Check the flag
                try:
                    self._log_agent_event(max_steps=max_steps, agent_run_error=agent_run_error)
                except Exception as log_e:  # Catch potential errors during logging itself
                    self.logger.error(f'Failed to log telemetry event: {log_e}', exc_info=True)
            else:
                # ADDED: Info message when custom telemetry for SIGINT was already logged
                self.logger.debug('Telemetry for force exit (SIGINT) was logged by custom exit callback.')

            # Generate GIF if needed before stopping event bus
            if self.settings.generate_gif:
                output_path: str = 'agent_history.gif'
                if isinstance(self.settings.generate_gif, str):
                    output_path = self.settings.generate_gif

                # Lazy import gif module to avoid heavy startup cost
                from browser_use.agent.gif import create_history_gif

                create_history_gif(task=self.task, history=self.history, output_path=output_path)

            await self.close()