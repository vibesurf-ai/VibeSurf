import logging
import os
import time
import re
from datetime import datetime
from typing import Any, Dict, List
from pathlib import Path

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage, SystemMessage, AssistantMessage

from vibe_surf.agents.prompts.report_writer_prompt import REPORT_WRITER_PROMPT
from vibe_surf.tools.file_system import CustomFileSystem
from vibe_surf.tools.report_writer_tools import ReportWriterTools
from vibe_surf.agents.views import CustomAgentOutput

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class ReportWriterAgent:
    """Agent responsible for generating HTML reports using LLM-controlled flow"""

    def __init__(self, llm: BaseChatModel, workspace_dir: str):
        """
        Initialize ReportWriterAgent
        
        Args:
            llm: Language model for generating report content
            workspace_dir: Directory to save reports
        """
        self.llm = llm
        self.workspace_dir = os.path.abspath(workspace_dir)

        # Initialize file system and tools
        self.file_system = CustomFileSystem(self.workspace_dir)
        self.tools = ReportWriterTools()

        # Setup action model and agent output
        self.ActionModel = self.tools.registry.create_action_model()
        self.AgentOutput = CustomAgentOutput.type_with_custom_actions(self.ActionModel)

        logger.info("📄 ReportWriterAgent initialized with LLM-controlled flow")

    async def generate_report(self, report_data: Dict[str, Any]) -> str:
        """
        Generate HTML report using LLM-controlled flow
        
        Args:
            report_data: Dictionary containing:
                - report_task: Report requirements, tips, and possible insights
                - information: Collected information for the report
        
        Returns:
            str: Absolute path to the generated report file
        """
        logger.info("📝 Starting LLM-controlled report generation...")

        try:
            # Extract task and information
            report_task = report_data.get('report_task', 'Generate a comprehensive report')
            information = report_data.get('information', 'No additional information provided')

            # Create report file with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"reports/report-{timestamp}.html"

            # Create the report file
            create_result = await self.file_system.create_file(report_filename)
            logger.info(f"Created report file: {create_result}")

            # Initialize message history
            message_history = []

            # Add system message with unified prompt
            message_history.append(SystemMessage(content=REPORT_WRITER_PROMPT))

            # Add initial user message with task details
            user_message = f"""Please generate a comprehensive report based on the following:

**Report Task:**
{report_task}

**Available Information:**
{information}

**Report File:**
{report_filename}

The report file '{report_filename}' has been created and is ready for you to write content. Please analyze the task, determine if you need to read any additional files, then generate the complete report content and format it as professional HTML."""
            message_history.append(UserMessage(content=user_message))

            # LLM-controlled loop
            max_iterations = 10  # Prevent infinite loops
            iteration = 0

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"🔄 LLM iteration {iteration}")

                # Get LLM response
                response = await self.llm.ainvoke(message_history, output_format=self.AgentOutput)
                parsed = response.completion
                actions = parsed.action

                # Add assistant message to history
                message_history.append(AssistantMessage(content=response.completion))

                # Execute actions
                results = []
                time_start = time.time()

                for i, action in enumerate(actions):
                    action_data = action.model_dump(exclude_unset=True)
                    action_name = next(iter(action_data.keys())) if action_data else 'unknown'
                    logger.info(f"🛠️ Executing action {i + 1}/{len(actions)}: {action_name}")

                    result = await self.tools.act(
                        action=action,
                        file_system=self.file_system,
                        page_extraction_llm=self.llm,
                    )

                    time_end = time.time()
                    time_elapsed = time_end - time_start
                    results.append(result)

                    logger.info(f"✅ Action completed in {time_elapsed:.2f}s")

                    # Check if task is done
                    if action_name == 'task_done':
                        logger.info("🎉 Report Writing Task completed")
                        break

                # Check if task is done
                if any(action.name == 'task_done' for action in actions):
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
                    message_history.append(UserMessage(content=formatted_results))

                # If no progress, add a prompt to continue
                if not results:
                    message_history.append(UserMessage(content="Please continue with the report generation."))

            if iteration >= max_iterations:
                logger.warning("⚠️ Maximum iterations reached, finishing report generation")

            # Post-process the generated HTML
            report_path = await self._finalize_report(report_filename)

            logger.info(f"✅ Report generated successfully: {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"❌ Failed to generate report: {e}")
            # Generate a simple fallback report
            fallback_path = await self._generate_fallback_report(report_data)
            return fallback_path

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
            absolute_path = self.file_system.get_absolute_path(report_filename)

            return absolute_path

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
                if file_path.startswith(('http://', 'https://', 'file://', '/', '#', 'mailto:', 'tel:')):
                    return full_match  # Return unchanged

                # Convert to absolute path
                if not os.path.isabs(file_path):
                    absolute_path = os.path.abspath(os.path.join(self.workspace_dir, file_path))
                else:
                    absolute_path = file_path

                file_url = f"file://{absolute_path}"

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
        absolute_path = self.file_system.get_absolute_path(report_filename)

        logger.info(f"✅ Fallback report generated: {absolute_path}")
        return absolute_path
