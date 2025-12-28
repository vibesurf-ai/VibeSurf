import re
from typing import Optional

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.io import MessageTextInput, Output, DropdownInput
from vibe_surf.langflow.logging import logger
from vibe_surf.langflow.schema.message import Message


class RegexComponent(Component):
    display_name = "Regex Processor"
    description = "Process text using regular expressions with various operations like findall and replace."
    icon = "regex"
    name = "RegexProcessor"

    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Input Text",
            info="The text to process with regex",
            required=True,
        ),
        MessageTextInput(
            name="pattern",
            display_name="Regex Pattern",
            info="The regular expression pattern to use",
            value=r"",
            required=True,
        ),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["findall", "replace"],
            value="findall",
            info="findall | replace",
        ),
        MessageTextInput(
            name="replacement",
            display_name="Replacement Text",
            info="Text to replace matches with (only used for 'sub' operation)",
            value="",
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Result",
            name="result",
            method="process_regex",
            types=["Message"]
        ),
    ]

    def process_regex(self) -> Message:
        """Process the input text using the specified regex operation."""
        
        # Validate inputs
        if not self.input_text:
            error_msg = "Input text is required"
            self.status = error_msg
            logger.warning(error_msg)
            return Message(text=f"Error: {error_msg}")
        
        if not self.pattern:
            error_msg = "Regex pattern is required"
            self.status = error_msg
            logger.warning(error_msg)
            return Message(text=f"Error: {error_msg}")

        try:
            # Compile the regex pattern
            compiled_pattern = re.compile(self.pattern, re.DOTALL | re.MULTILINE)
            
            # Perform the specified operation
            if self.operation == "findall":
                result = self._findall_operation(compiled_pattern)
            elif self.operation == "replace":
                result = self._sub_operation(compiled_pattern)
            else:
                error_msg = f"Unknown operation: {self.operation}"
                self.status = error_msg
                logger.error(error_msg)
                return Message(text=f"Error: {error_msg}")
            
            self.status = f"Successfully performed {self.operation} operation"
            logger.info(f"Regex {self.operation} operation completed successfully")
            return Message(text=result)
            
        except re.error as e:
            error_msg = f"Invalid regex pattern: {str(e)}"
            self.status = error_msg
            logger.error(error_msg)
            return Message(text=f"Error: {error_msg}")
        except Exception as e:
            error_msg = f"Error processing regex: {str(e)}"
            self.status = error_msg
            logger.error(error_msg)
            return Message(text=f"Error: {error_msg}")

    def _findall_operation(self, pattern: re.Pattern) -> str:
        """Perform regex findall operation (finds all matches)."""
        matches = pattern.findall(self.input_text)
        return "\n".join(matches)

    def _sub_operation(self, pattern: re.Pattern) -> str:
        """Perform regex substitution operation."""
        if not hasattr(self, 'replacement') or self.replacement is None:
            replacement_text = ""
        else:
            replacement_text = self.replacement
        
        return pattern.sub(replacement_text, self.input_text)