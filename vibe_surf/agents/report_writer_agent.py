import logging
import os
import time
import re
import asyncio
from datetime import datetime
from typing import Any, Dict, List
import json

from pydantic import BaseModel
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage, SystemMessage, AssistantMessage
from browser_use.utils import SignalHandler

from vibe_surf.agents.prompts.report_writer_prompt import REPORT_WRITER_PROMPT
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.tools.report_writer_tools import ReportWriterTools
from vibe_surf.agents.views import CustomAgentOutput
from vibe_surf.telemetry.service import ProductTelemetry
from vibe_surf.telemetry.views import ReportWriterTelemetryEvent

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class ReportTaskResult(BaseModel):
    """Result of a report generation task"""
    success: bool  # True only if LLM completed successfully
    msg: str  # Success message or error details
    report_path: str  # Path to the generated report file


class ReportWriterAgent:
    """Agent responsible for generating HTML reports using LLM-controlled flow"""

    def __init__(self, llm: BaseChatModel, workspace_dir: str, step_callback=None, use_thinking: bool = True):
        """
        Initialize ReportWriterAgent
        
        Args:
            llm: Language model for generating report content
            workspace_dir: Directory to save reports
            step_callback: Optional callback function to log each step
        """
        self.llm = llm
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.step_callback = step_callback
        self.use_thinking = use_thinking

        # Initialize file system and tools
        self.file_system = CustomFileSystem(self.workspace_dir)
        self.tools = ReportWriterTools()

        # Setup action model and agent output
        self.ActionModel = self.tools.registry.create_action_model()
        if self.use_thinking:
            self.AgentOutput = CustomAgentOutput.type_with_custom_actions(self.ActionModel)
        else:
            self.AgentOutput = CustomAgentOutput.type_with_custom_actions_no_thinking(self.ActionModel)

        # State management for pause/resume/stop control
        self.paused = False
        self.stopped = False
        self.consecutive_failures = 0
        self._external_pause_event = asyncio.Event()
        self._external_pause_event.set()
        
        # Initialize message history as instance variable
        self.message_history = []
        
        # Initialize telemetry
        self.telemetry = ProductTelemetry()

        logger.info("📄 ReportWriterAgent initialized with LLM-controlled flow")

    def pause(self) -> None:
        """Pause the agent before the next step"""
        logger.info('\n\n⏸️ Paused report writer agent.\n\tPress [Enter] to resume or [Ctrl+C] again to quit.')
        self.paused = True
        self._external_pause_event.clear()

    def resume(self) -> None:
        """Resume the agent"""
        logger.info('▶️  Resuming report writer agent execution where it left off...\n')
        self.paused = False
        self._external_pause_event.set()

    def stop(self) -> None:
        """Stop the agent"""
        logger.info('⏹️ Report writer agent stopping')
        self.stopped = True
        # Signal pause event to unblock any waiting code so it can check the stopped state
        self._external_pause_event.set()

    def add_new_task(self, new_task: str) -> None:
        """
        Add a new task or guidance to the report writer agent during execution.
        The new_task parameter contains a pre-formatted prompt from VibeSurfAgent.
        """
        # Add the pre-formatted prompt directly to message history
        from browser_use.llm.messages import UserMessage
        self.message_history.append(UserMessage(content=new_task))
        logger.info(f"📝 Report writer agent received new task guidance")

    async def generate_report(self, report_data: Dict[str, Any]) -> ReportTaskResult:
        """
        Generate HTML report using LLM-controlled flow
        
        Args:
            report_data: Dictionary containing:
                - report_task: Report requirements, tips, and possible insights
                - information: Collected information for the report
        
        Returns:
            ReportTaskResult: Result containing success status, message, and report path
        """
        logger.info("📝 Starting LLM-controlled report generation...")
        
        # Capture telemetry start event
        start_time = time.time()
        import vibe_surf
        start_event = ReportWriterTelemetryEvent(
            version=vibe_surf.__version__,
            action='start',
            model=getattr(self.llm, 'model_name', None),
            model_provider=getattr(self.llm, 'provider', None),
            report_type='html'
        )
        self.telemetry.capture(start_event)

        # Get current event loop
        loop = asyncio.get_event_loop()

        signal_handler = SignalHandler(
            loop=loop,
            pause_callback=self.pause,
            resume_callback=self.resume,
            exit_on_second_int=True,
        )
        signal_handler.register()

        try:
            # Extract task and information
            report_task = report_data.get('report_task', 'Generate a comprehensive report')
            report_information = report_data.get('report_information', 'No additional information provided')

            # Create report file with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"reports/report-{timestamp}.html"

            # Create the report file
            create_result = await self.file_system.create_file(report_filename)
            logger.info(f"Created report file: {create_result}")

            max_iterations = 20  # Prevent infinite loops

            # Add system message with unified prompt only if message history is empty
            if not self.message_history:
                report_system_prompt = REPORT_WRITER_PROMPT
                self.message_history.append(SystemMessage(content=report_system_prompt))

            # Add initial user message with task details
            user_message = f"""Please generate a report within MAX {max_iterations} steps based on the following:

**Report Task:**
{report_task}

**Available Information:**
{json.dumps(report_information, indent=2, ensure_ascii=False)}

**Report File:**
{report_filename}

The report file '{report_filename}' has been created and is ready for you to write content.
Please analyze the task, determine if you need to read any additional files, then generate the complete report content and format it as professional HTML.
"""
            self.message_history.append(UserMessage(content=user_message))

            # LLM-controlled loop
            iteration = 0
            agent_run_error = None
            task_completed = False

            while iteration < max_iterations:
                # Use the consolidated pause state management
                if self.paused:
                    logger.info(f'⏸️ Step {iteration}: Agent paused, waiting to resume...')
                    await self._external_pause_event.wait()
                    signal_handler.reset()

                # Check control flags before each step
                if self.stopped:
                    logger.info('🛑 Agent stopped')
                    agent_run_error = 'Agent stopped programmatically because user interrupted.'
                    break
                iteration += 1
                logger.info(f"🔄 LLM iteration {iteration}")
                self.message_history.append(UserMessage(content=f"Current step: {iteration} / {max_iterations}"))
                # Get LLM response
                response = await self.llm.ainvoke(self.message_history, output_format=self.AgentOutput)
                parsed = response.completion
                action = parsed.action

                # Call step callback if provided to log thinking + action
                if self.step_callback:
                    await self.step_callback(parsed, iteration)

                # Add assistant message to history
                self.message_history.append(AssistantMessage(
                    content=json.dumps(response.completion.model_dump(exclude_none=True, exclude_unset=True),
                                       ensure_ascii=False)))

                # Execute actions
                results = []
                time_start = time.time()

                action_data = action.model_dump(exclude_unset=True)
                action_name = next(iter(action_data.keys())) if action_data else 'unknown'
                logger.info(f"🛠️ Executing action: {action_name}")

                result = await self.tools.act(
                    action=action,
                    file_system=self.file_system,
                    llm=self.llm,
                )

                time_end = time.time()
                time_elapsed = time_end - time_start
                results.append(result)

                logger.info(f"✅ Action completed in {time_elapsed:.2f}s")

                # Check if task is done
                if action_name == 'task_done':
                    logger.info("🎉 Report Writing Task completed")
                    task_completed = True
                    break

                # Check if task is done - break out of main loop if task completed
                if task_completed:
                    break

                # Add results to message history using improved action result processing
                action_results = ''
                for idx, action_result in enumerate(results):
                    if hasattr(action_result, 'extracted_content') and action_result.extracted_content:
                        action_results += f'{action_result.extracted_content}\n'
                        logger.debug(f'Added extracted_content to action_results: {action_result.extracted_content}')

                    if hasattr(action_result, 'error') and action_result.error:
                        if len(action_result.error) > 200:
                            error_text = action_result.error[:100] + '......' + action_result.error[-100:]
                        else:
                            error_text = action_result.error
                        action_results += f'{error_text}\n'
                        logger.debug(f'Added error to action_results: {error_text}')

                if action_results:
                    formatted_results = f'Result:\n{action_results}'
                    self.message_history.append(UserMessage(content=formatted_results))

                # If no progress, add a prompt to continue
                if not results:
                    self.message_history.append(UserMessage(content="Please continue with the report generation."))

            # Handle different completion scenarios
            report_path = await self._finalize_report(report_filename)
            
            if agent_run_error:
                # Agent was stopped
                return ReportTaskResult(
                    success=False,
                    msg=agent_run_error,
                    report_path=report_path
                )
            elif task_completed:
                # Task completed successfully by LLM
                logger.info(f"✅ Report generated successfully: {report_path}")
                
                # Capture telemetry completion event
                end_time = time.time()
                duration = end_time - start_time
                completion_event = ReportWriterTelemetryEvent(
                    version=vibe_surf.__version__,
                    action='report_completed',
                    model=getattr(self.llm, 'model_name', None),
                    model_provider=getattr(self.llm, 'provider', None),
                    duration_seconds=duration,
                    success=True,
                    report_type='html'
                )
                self.telemetry.capture(completion_event)
                self.telemetry.flush()
                
                return ReportTaskResult(
                    success=True,
                    msg="Report generated successfully by LLM",
                    report_path=report_path
                )
            elif iteration >= max_iterations:
                # Maximum iterations reached
                logger.warning("⚠️ Maximum iterations reached, finishing report generation")
                return ReportTaskResult(
                    success=False,
                    msg="Maximum iterations reached without task completion",
                    report_path=report_path
                )
            else:
                # Unexpected exit from loop
                return ReportTaskResult(
                    success=False,
                    msg="Report generation ended unexpectedly",
                    report_path=report_path
                )

        except Exception as e:
            logger.error(f"❌ Failed to generate report: {e}")
            
            # Capture telemetry error event
            end_time = time.time()
            duration = end_time - start_time
            error_event = ReportWriterTelemetryEvent(
                version=vibe_surf.__version__,
                action='error',
                model=getattr(self.llm, 'model_name', None),
                model_provider=getattr(self.llm, 'provider', None),
                duration_seconds=duration,
                success=False,
                error_message=str(e)[:200],  # Limit error message length
                report_type='html'
            )
            self.telemetry.capture(error_event)
            self.telemetry.flush()
            
            # Generate a simple fallback report
            fallback_path = await self._generate_fallback_report(report_data)
            return ReportTaskResult(
                success=False,
                msg=f"Error occurred during report generation: {str(e)}",
                report_path=fallback_path
            )
        finally:
            signal_handler.unregister()
            self.stopped = False
            self.paused = False

    async def _finalize_report(self, report_filename: str) -> str:
        """
        Finalize the report by cleaning HTML and converting links
        
        Args:
            report_filename: Name of the report file
            
        Returns:
            str: Absolute path to the finalized report
        """
        try:
            # Read the current content
            content = await self.file_system.read_file(report_filename)

            # Extract HTML content from the read result
            if content.startswith('Read from file'):
                # Extract content between <content> tags
                start_tag = '<content>'
                end_tag = '</content>'
                start_idx = content.find(start_tag)
                end_idx = content.find(end_tag)

                if start_idx != -1 and end_idx != -1:
                    html_content = content[start_idx + len(start_tag):end_idx].strip()
                else:
                    html_content = content
            else:
                html_content = content

            # Clean HTML content
            cleaned_html = self._clean_html_content(html_content)

            # Convert relative file paths to absolute file:// URLs
            final_html = self._convert_file_links(cleaned_html)

            # Write the final content
            await self.file_system.write_file(report_filename, final_html)

            # Get absolute path
            # absolute_path = self.file_system.get_absolute_path(report_filename)

            return report_filename

        except Exception as e:
            logger.error(f"❌ Failed to finalize report: {e}")
            # Return the path anyway
            return self.file_system.get_absolute_path(report_filename)

    def _clean_html_content(self, html_content: str) -> str:
        """Clean and validate HTML content"""
        # Remove markdown code block markers if present
        html_content = html_content.strip()
        if html_content.startswith("```html"):
            html_content = html_content[7:].strip()
        if html_content.startswith("```"):
            html_content = html_content[3:].strip()
        if html_content.endswith("```"):
            html_content = html_content[:-3].strip()

        # Ensure it starts with <!DOCTYPE html> or <html>
        if not html_content.lower().startswith(('<!doctype', '<html')):
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VibeSurf Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; line-height: 1.6; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid #007bff; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f2f2f2; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        {html_content}
    </div>
</body>
</html>"""

        return html_content

    def _convert_file_links(self, html_content: str) -> str:
        """
        Convert relative file paths to absolute file:// URLs
        
        Args:
            html_content: HTML content with relative file paths
            
        Returns:
            str: HTML content with converted file:// URLs
        """
        # Pattern to match HTML href and src attributes with relative paths
        patterns = [
            (r'href\s*=\s*["\']([^"\']+)["\']', 'href'),  # <a href="path">
            (r'src\s*=\s*["\']([^"\']+)["\']', 'src'),  # <img src="path">
        ]

        for pattern, attr_name in patterns:
            def replace_path(match):
                full_match = match.group(0)
                file_path = match.group(1)

                # Check if it's already a URL or absolute path
                if file_path.startswith(('http://', 'https://', 'file://', '#', 'mailto:', 'tel:')):
                    return full_match  # Return unchanged

                # Convert to absolute path
                if not os.path.isabs(file_path):
                    absolute_path = os.path.abspath(os.path.join(self.workspace_dir, file_path))
                else:
                    absolute_path = file_path
                normalized_path = absolute_path.replace(os.path.sep, '/')
                file_url = f"file:///{normalized_path}"

                # Return the updated attribute
                quote = '"' if '"' in full_match else "'"
                return f'{attr_name}={quote}{file_url}{quote}'

            html_content = re.sub(pattern, replace_path, html_content)

        return html_content

    async def _generate_fallback_report(self, report_data: Dict[str, Any]) -> str:
        """Generate a simple fallback report when LLM generation fails"""
        logger.info("📝 Generating fallback report...")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"vibesurf_fallback_report-{timestamp}.html"

        # Create a simple HTML report
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VibeSurf Task Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
            background-color: #f8f9fa;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.2em;
            font-weight: 300;
        }}
        .section {{
            margin: 0;
            padding: 25px;
            border-bottom: 1px solid #eee;
        }}
        .section:last-child {{
            border-bottom: none;
        }}
        .section h2 {{
            color: #2c3e50;
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 1.4em;
            border-left: 4px solid #3498db;
            padding-left: 15px;
        }}
        .meta {{
            background: #ecf0f1;
            color: #7f8c8d;
            text-align: center;
            padding: 15px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>VibeSurf Task Report</h1>
            <p>Generated on {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}</p>
        </div>
        
        <div class="section">
            <h2>Report Task</h2>
            <p>{report_data.get('report_task', 'No task specified')}</p>
        </div>
        
        <div class="section">
            <h2>Available Information</h2>
            <p>{report_data.get('information', 'No information provided')}</p>
        </div>
        
        <div class="section">
            <h2>Notice</h2>
            <p>This is a fallback report generated when the advanced LLM-controlled report generation encountered an issue. The report contains basic information provided for the task.</p>
            <p>For future runs, ensure that the LLM service is properly configured and accessible for enhanced report generation capabilities.</p>
        </div>
        
        <div class="meta">
            Generated by VibeSurf Agent Framework - Fallback Mode
        </div>
    </div>
</body>
</html>"""

        # Create and write fallback report
        await self.file_system.create_file(report_filename)
        await self.file_system.write_file(report_filename, html_content)

        # Get absolute path
        # absolute_path = self.file_system.get_absolute_path(report_filename)

        logger.info(f"✅ Fallback report generated: {report_filename}")
        return report_filename
