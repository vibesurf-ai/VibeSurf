import logging
import os
import time
from typing import Any, Dict, List

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage

from vibe_surf.agents.prompts.vibe_surf_prompt import (
    REPORT_CONTENT_PROMPT,
    REPORT_FORMAT_PROMPT
)

logger = logging.getLogger(__name__)


class ReportWriterAgent:
    """Agent responsible for generating HTML reports using two-phase LLM generation"""
    
    def __init__(self, llm: BaseChatModel, workspace_dir: str):
        """
        Initialize ReportWriterAgent
        
        Args:
            llm: Language model for generating report content
            workspace_dir: Directory to save reports
        """
        self.llm = llm
        self.workspace_dir = workspace_dir
        
        logger.info("📄 ReportWriterAgent initialized")
    
    async def generate_report(self, report_data: Dict[str, Any]) -> str:
        """
        Generate HTML report using two-phase approach: content generation then formatting
        
        Args:
            report_data: Dictionary containing:
                - original_task: The original user task
                - execution_results: List of BrowserTaskResult objects
                - report_type: Type of report ("summary", "detailed", "none")
                - upload_files: Optional list of uploaded files
        
        Returns:
            str: Path to the generated report file
        """
        logger.info(f"📝 Generating {report_data.get('report_type', 'summary')} report...")
        
        try:
            # Phase 1: Generate report content
            logger.info("📖 Phase 1: Generating report content...")
            report_content = await self._generate_content(report_data)
            
            # Phase 2: Format content as HTML
            logger.info("🎨 Phase 2: Formatting as HTML...")
            html_content = await self._format_as_html(report_content)
            
            # Save report to file
            report_filename = f"report_{int(time.time())}.html"
            reports_dir = os.path.join(self.workspace_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            report_path = os.path.join(reports_dir, report_filename)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"✅ Report generated successfully: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"❌ Failed to generate report: {e}")
            # Generate a simple fallback report
            fallback_path = await self._generate_fallback_report(report_data)
            return fallback_path
    
    async def _generate_content(self, report_data: Dict[str, Any]) -> str:
        """Generate the textual content for the report"""
        # Format execution results for the prompt
        results_text = self._format_execution_results(report_data.get('execution_results', []))
        
        # Format upload files
        upload_files = report_data.get('upload_files', [])
        upload_files_text = "None" if not upload_files else ", ".join(upload_files)
        
        # Generate content using the content prompt
        content_prompt = REPORT_CONTENT_PROMPT.format(
            original_task=report_data.get('original_task', 'No task specified'),
            report_type=report_data.get('report_type', 'summary'),
            upload_files=upload_files_text,
            execution_results=results_text
        )
        
        response = await self.llm.ainvoke([UserMessage(content=content_prompt)])
        logger.debug(f"Content generation response type: {type(response)}")
        logger.debug(f"Content generation completion: {response.completion}")
        logger.debug(f"Content generation completion type: {type(response.completion)}")
        
        if response.completion is None:
            logger.error("❌ Content generation returned None completion")
            raise ValueError("LLM response completion is None - unable to generate report content")
        
        return response.completion
    
    async def _format_as_html(self, content: str) -> str:
        """Format the content as a professional HTML document"""
        format_prompt = REPORT_FORMAT_PROMPT.format(report_content=content)
        
        response = await self.llm.ainvoke([UserMessage(content=format_prompt)])
        logger.debug(f"Format generation response type: {type(response)}")
        logger.debug(f"Format generation completion: {response.completion}")
        logger.debug(f"Format generation completion type: {type(response.completion)}")
        
        if response.completion is None:
            logger.error("❌ Format generation returned None completion")
            raise ValueError("LLM response completion is None - unable to format report as HTML")
        
        html_content = response.completion
        
        # Clean up the HTML content if needed
        html_content = self._clean_html_content(html_content)
        
        return html_content
    
    def _format_execution_results(self, execution_results) -> str:
        """Format execution results for the LLM prompt"""
        if not execution_results:
            return "No execution results available."
        
        formatted_results = []
        for i, result in enumerate(execution_results, 1):
            status = "✅ Success" if result.success else "❌ Failed"
            
            # Extract meaningful result content
            result_content = "No result available"
            if result.result:
                # Truncate very long results but keep meaningful content
                if len(result.result) > 500:
                    result_content = result.result[:497] + "..."
                else:
                    result_content = result.result
            elif result.error:
                result_content = f"Error: {result.error}"
            
            formatted_results.append(f"""
**Task {i}:** {result.task}
**Status:** {status}
**Agent:** {result.agent_id}
**Result:** {result_content}
**Success:** {'Yes' if result.success else 'No'}
            """)
        
        return "\n".join(formatted_results)
    
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
    <title>VibeSurf Task Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid #007bff; }}
    </style>
</head>
<body>
    <div class="container">
        {html_content}
    </div>
</body>
</html>"""
        
        return html_content
    
    async def _generate_fallback_report(self, report_data: Dict[str, Any]) -> str:
        """Generate a simple fallback report when LLM generation fails"""
        logger.info("📝 Generating fallback report...")
        
        upload_files = report_data.get('upload_files', [])
        upload_files_section = ""
        if upload_files:
            upload_files_section = f"""
    <div class="section">
        <h2>Upload Files</h2>
        <ul>
            {"".join([f"<li>{file}</li>" for file in upload_files])}
        </ul>
    </div>"""
        
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
        .success {{
            color: #27ae60;
            font-weight: 600;
        }}
        .error {{
            color: #e74c3c;
            font-weight: 600;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: white;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #34495e;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f8f9fa;
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
            <p>Generated on {time.strftime('%B %d, %Y at %H:%M:%S')}</p>
        </div>
        
        <div class="section">
            <h2>Task Overview</h2>
            <p><strong>Original Task:</strong> {report_data.get('original_task', 'No task specified')}</p>
            <p><strong>Report Type:</strong> {report_data.get('report_type', 'summary').title()}</p>
        </div>
        {upload_files_section}
        
        <div class="section">
            <h2>Execution Results</h2>
            <table>
                <thead>
                    <tr>
                        <th>Task</th>
                        <th>Status</th>
                        <th>Agent</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        # Add execution results to table
        execution_results = report_data.get('execution_results', [])
        if execution_results:
            for result in execution_results:
                status_class = "success" if result.success else "error"
                status_text = "✅ Success" if result.success else "❌ Failed"
                result_text = result.result or result.error or "No result"
                # Truncate long results
                if len(result_text) > 150:
                    result_text = result_text[:147] + "..."
                
                html_content += f"""
                    <tr>
                        <td>{result.task}</td>
                        <td class="{status_class}">{status_text}</td>
                        <td>{result.agent_id}</td>
                        <td>{result_text}</td>
                    </tr>
"""
        else:
            html_content += """
                    <tr>
                        <td colspan="4" style="text-align: center; color: #7f8c8d; font-style: italic;">No execution results available</td>
                    </tr>
"""
        
        html_content += """
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>Summary</h2>
            <p>This report was automatically generated by VibeSurf as a fallback when the advanced report generation encountered an issue. The report contains basic information about the task execution and results.</p>
            <p>For future runs, ensure that the LLM service is properly configured and accessible for enhanced report generation capabilities.</p>
        </div>
        
        <div class="meta">
            Generated by VibeSurf Agent Framework
        </div>
    </div>
</body>
</html>"""
        
        # Save fallback report
        report_filename = f"fallback_report_{int(time.time())}.html"
        reports_dir = os.path.join(self.workspace_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, report_filename)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"✅ Fallback report generated: {report_path}")
        return report_path