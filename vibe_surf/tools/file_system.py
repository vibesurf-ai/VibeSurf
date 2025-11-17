import asyncio
import pdb
import re
import os
from pathlib import Path
from browser_use.filesystem.file_system import FileSystem, FileSystemError, INVALID_FILENAME_ERROR_MESSAGE, \
    FileSystemState
from browser_use.filesystem.file_system import BaseFile, MarkdownFile, TxtFile, JsonFile, CsvFile, PdfFile
from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class PythonFile(BaseFile):
    """Plain text file implementation"""

    @property
    def extension(self) -> str:
        return 'py'


class HtmlFile(BaseFile):
    """Plain text file implementation"""

    @property
    def extension(self) -> str:
        return 'html'


class JSFile(BaseFile):
    """Plain text file implementation"""

    @property
    def extension(self) -> str:
        return 'js'


class CustomFileSystem(FileSystem):
    def __init__(self, base_dir: str | Path, create_default_files: bool = False):
        # Handle the Path conversion before calling super().__init__
        self.base_dir = Path(base_dir).absolute() if isinstance(base_dir, str) else base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Create and use a dedicated subfolder for all operations
        self.data_dir = self.base_dir

        self.data_dir.mkdir(exist_ok=True)

        self._file_types: dict[str, type[BaseFile]] = {
            'md': MarkdownFile,
            'txt': TxtFile,
            'json': JsonFile,
            'csv': CsvFile,
            'pdf': PdfFile,
            'py': PythonFile,
            'html': HtmlFile,
            'js': JSFile,
        }

        self.files = {}
        if create_default_files:
            self.default_files = ['todo.md']
            self._create_default_files()

        self.extracted_content_count = 0

    async def display_file(self, full_filename: str) -> str | None:
        """Display file content using file-specific display method"""
        if_file_exist = await self.file_exist(full_filename)
        if not if_file_exist:
            return f"{full_filename} does not exist."

        file_content = await self.read_file(full_filename)

        return file_content

    def get_todo_contents(self) -> str:
        """Get todo file contents"""
        full_filepath = str(self.data_dir / "todo.md")
        if not os.path.exists(full_filepath):
            return f"TODO '{full_filepath}' not found."
        try:
            with open(str(full_filepath), 'r', encoding="utf-8") as f:
                todo_content = f.read()
            return todo_content
        except Exception as e:
            return ""

    async def read_file(self, full_filename: str, external_file: bool = False) -> str:
        """Read file content using file-specific read method and return appropriate message to LLM"""
        try:
            full_filepath = full_filename if external_file else str(self.data_dir / full_filename)
            is_file_exist = await self.file_exist(full_filepath)
            if not is_file_exist:
                return f"Error: File '{full_filepath}' not found."
            try:
                _, extension = self._parse_filename(full_filename)
            except Exception:
                return f'Error: Invalid filename format {full_filename}. Must be alphanumeric with a supported extension.'
            if extension != 'pdf' and extension in self._file_types.keys():
                with open(str(full_filepath), 'r', encoding="utf-8") as f:
                    content = f.read()
                    return f'Read from file {full_filename}.\n<content>\n{content}\n</content>'

            elif extension == 'pdf':
                import pypdf

                reader = pypdf.PdfReader(full_filepath)
                num_pages = len(reader.pages)
                MAX_PDF_PAGES = 10
                extra_pages = num_pages - MAX_PDF_PAGES
                extracted_text = ''
                for page in reader.pages[:MAX_PDF_PAGES]:
                    extracted_text += page.extract_text()
                extra_pages_text = f'{extra_pages} more pages...' if extra_pages > 0 else ''
                return f'Read from file {full_filename}.\n<content>\n{extracted_text}\n{extra_pages_text}</content>'
            else:
                return f'Error: Cannot read content from file {full_filename}.'
        except FileNotFoundError:
            return f"Error: File '{full_filepath}' not found."
        except PermissionError:
            return f"Error: Permission denied to read file '{full_filepath}'."
        except Exception as e:
            return f"Error: Could not read file '{full_filepath}': {str(e)}."

    async def copy_file(self, src_filename: str, dst_filename: str, external_src_file: bool = False) -> str:
        """Copy a file to the FileSystem from src (can be external) to dst filename"""
        import shutil
        from concurrent.futures import ThreadPoolExecutor

        # Check if destination file already exists
        if self.get_file(dst_filename):
            return f"Error: Destination file '{dst_filename}' already exists."

        try:
            src_path = src_filename if external_src_file else (self.data_dir / src_filename)
            dst_path = self.data_dir / dst_filename
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            # Check if source file exists
            if not src_path.exists() if hasattr(src_path, 'exists') else not Path(src_path).exists():
                return f"Error: Source file '{src_filename}' not found."

            # Use shutil to copy file
            with ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(executor, shutil.copy2, str(src_path), str(dst_path))

            # Read the copied file content and create file object for internal tracking
            # content = self.read_file(dst_filename)
            # dst_name, dst_extension = self._parse_filename(dst_filename)
            # file_class = self._get_file_type_class(dst_extension)
            #
            # if file_class:
            #     dst_file = file_class(name=dst_name, content=content)
            #     self.files[dst_filename] = dst_file

            source_type = "external file" if external_src_file else "file"
            return f"{source_type.capitalize()} '{src_filename}' copied to '{dst_filename}' successfully."

        except FileNotFoundError:
            return f"Error: Source file '{src_filename}' not found."
        except PermissionError:
            return f"Error: Permission denied to access files."
        except Exception as e:
            return f"Error: Could not copy file '{src_filename}' to '{dst_filename}'. {str(e)}"

    async def rename_file(self, old_filename: str, new_filename: str) -> str:
        """Rename a file within the FileSystem from old_filename to new_filename"""
        import shutil
        from concurrent.futures import ThreadPoolExecutor

        # Check if old file exists
        file_exist = await self.file_exist(old_filename)
        if not file_exist:
            return f"Error: Source File '{old_filename}' not found."

        try:
            new_file_path = os.path.join(os.path.dirname(old_filename), new_filename)
            old_path = self.data_dir / old_filename
            new_path = self.data_dir / new_file_path

            # Use shutil to move/rename file
            with ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(executor, shutil.move, str(old_path), str(new_path))

            # Update internal file tracking
            # old_file = self.files[old_filename]
            # del self.files[old_filename]
            #
            # # Update file object name if needed
            # new_name, new_extension = self._parse_filename(new_file_path)
            # old_file.name = new_name
            # self.files[new_file_path] = old_file

            return f"File '{old_filename}' renamed to '{new_file_path}' successfully."

        except Exception as e:
            return f"Error: Could not rename file '{old_filename}' to '{new_file_path}'. {str(e)}"

    async def move_file(self, old_filename: str, new_filename: str) -> str:
        """Move a file within the FileSystem from old_filename to new_filename"""
        import shutil
        from concurrent.futures import ThreadPoolExecutor

        # Check if old file exists
        src_file_exist = await self.file_exist(old_filename)
        if not src_file_exist:
            return f"Error: Source File '{old_filename}' not found."

        # Check if new filename already exists
        dst_file_exist = await self.file_exist(new_filename)
        if dst_file_exist:
            return f"Error: Destination File '{new_filename}' already exists."

        try:
            old_path = self.data_dir / old_filename
            new_path = self.data_dir / new_filename
            new_path.parent.mkdir(parents=True, exist_ok=True)
            # Use shutil to move file
            with ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(executor, shutil.move, str(old_path), str(new_path))

            # Update internal file tracking
            # old_file = self.files[old_filename]
            # del self.files[old_filename]
            #
            # # Update file object name if needed
            # new_name, new_extension = self._parse_filename(new_filename)
            # old_file.name = new_name
            # self.files[new_filename] = old_file

            return f"File '{old_filename}' moved to '{new_filename}' successfully."

        except Exception as e:
            return f"Error: Could not move file '{old_filename}' to '{new_filename}'. {str(e)}"

    def get_absolute_path(self, full_filename: str) -> str:
        full_path = self.data_dir.absolute() / full_filename
        return str(full_path)

    def _is_valid_filename(self, file_name: str) -> bool:
        """Check if filename matches the required pattern: name.extension"""
        # Build extensions pattern from _file_types
        file_name = os.path.splitext(file_name)[1]
        extensions = '|'.join(self._file_types.keys())
        pattern = rf'\.({extensions})$'
        return bool(re.match(pattern, file_name))

    async def append_file(self, full_filename: str, content: str) -> str:
        """Append content to file using file-specific append method"""
        if not self._is_valid_filename(full_filename):
            return INVALID_FILENAME_ERROR_MESSAGE

        full_path = self.data_dir / full_filename
        is_file_exist = await self.file_exist(full_filename)
        if not is_file_exist:
            return f"File '{full_filename}' not found."

        try:
            with open(str(full_path), encoding='utf-8', mode='a') as f:
                f.write(content)

            return f'Data appended to file {full_filename} successfully.'
        except FileSystemError as e:
            return str(e)
        except Exception as e:
            return f"Error: Could not append to file '{full_filename}'. {str(e)}"

    async def write_file(self, full_filename: str, content: str) -> str:
        """Write content to file using file-specific write method"""
        if not self._is_valid_filename(full_filename):
            return INVALID_FILENAME_ERROR_MESSAGE

        try:
            full_path = self.data_dir / full_filename
            full_path.parent.mkdir(parents=True, exist_ok=True)
            name_without_ext, extension = self._parse_filename(full_filename)
            file_class = self._get_file_type_class(extension)
            if not file_class:
                raise ValueError(f"Error: Invalid file extension '{extension}' for file '{full_filename}'.")

            # Create or get existing file using full filename as key
            if full_filename in self.files:
                file_obj = self.files[full_filename]
            else:
                file_obj = file_class(name=name_without_ext)
                self.files[full_filename] = file_obj  # Use full filename as key

            with open(str(full_path), encoding='utf-8', mode='w') as f:
                f.write(content)

            return f'Data written to file {full_filename} successfully.'
        except FileSystemError as e:
            return str(e)
        except Exception as e:
            return f"Error: Could not write to file '{full_filename}'. {str(e)}"

    async def file_exist(self, full_filename: str) -> bool:
        full_file_path = self.data_dir / full_filename
        return bool(full_file_path.exists())

    async def create_file(self, full_filename: str) -> str:
        """Create a file with empty content"""
        if not self._is_valid_filename(full_filename):
            return INVALID_FILENAME_ERROR_MESSAGE

        try:
            full_path = self.data_dir / full_filename
            full_path.parent.mkdir(parents=True, exist_ok=True)
            name_without_ext, extension = self._parse_filename(full_filename)
            file_class = self._get_file_type_class(extension)
            if not file_class:
                raise ValueError(f"Error: Invalid file extension '{extension}' for file '{full_filename}'.")

            # Create or get existing file using full filename as key
            if full_filename in self.files:
                file_obj = self.files[full_filename]
            else:
                file_obj = file_class(name=name_without_ext)
                self.files[full_filename] = file_obj  # Use full filename as key

            # Use file-specific write method
            with open(str(full_path), encoding='utf-8', mode='w') as f:
                f.write('')
            return f'Create file {full_filename} successfully.'
        except FileSystemError as e:
            return str(e)
        except Exception as e:
            return f"Error: Could not write to file '{full_filename}'. {str(e)}"

    async def save_extracted_content(self, content: str) -> str:
        """Save extracted content to a numbered file"""
        initial_filename = f'extracted_content_{self.extracted_content_count}'
        extracted_filename = f'{initial_filename}.md'
        write_result = await self.write_file(extracted_filename, content)
        logger.info(write_result)
        self.extracted_content_count += 1
        return extracted_filename

    async def list_directory(self, directory_path: str = "") -> str:
        """List contents of a directory within the file system (data_dir only)"""
        try:
            # Construct the full path within data_dir
            if directory_path and directory_path.strip() != ".":
                # Remove leading slash if present and ensure relative path
                directory_path = directory_path.lstrip('/')
                full_path = self.data_dir / directory_path
            else:
                full_path = self.data_dir

            # Ensure the path is within data_dir for security
            try:
                full_path = full_path.resolve()
                self.data_dir.resolve()
                if not str(full_path).startswith(str(self.data_dir.resolve())):
                    return f"Error: Access denied. Path '{directory_path}' is outside the file system."
            except Exception:
                return f"Error: Invalid directory path '{directory_path}'."

            # Check if directory exists
            if not full_path.exists():
                return f"Error: Directory '{directory_path or '.'}' does not exist."

            if not full_path.is_dir():
                return f"Error: '{directory_path or '.'}' is not a directory."

            # List directory contents
            items = []
            for item in sorted(full_path.iterdir()):
                relative_path = item.relative_to(full_path)
                if item.is_dir():
                    items.append(f"📁 {relative_path}/")
                else:
                    file_size = item.stat().st_size
                    if file_size < 1024:
                        size_str = f"{file_size}B"
                    elif file_size < 1024 * 1024:
                        size_str = f"{file_size // 1024}KB"
                    else:
                        size_str = f"{file_size // (1024 * 1024)}MB"
                    items.append(f"📄 {relative_path} ({size_str})")

            if not items:
                return f"Directory '{directory_path or '.'}' is empty."

            directory_display = directory_path or "."
            return f"Contents of directory '{directory_display}':\n" + "\n".join(items)

        except Exception as e:
            return f"Error: Could not list directory '{directory_path or '.'}': {str(e)}"

    async def create_directory(self, directory_path: str) -> str:
        """Create a directory within the file system (data_dir only)"""
        try:
            if not directory_path or not directory_path.strip():
                return "Error: Directory path cannot be empty."

            # Remove leading slash if present and ensure relative path
            directory_path = directory_path.strip().lstrip('/')
            full_path = self.data_dir / directory_path

            # Ensure the path is within data_dir for security
            try:
                full_path = full_path.resolve()
                self.data_dir.resolve()
                if not str(full_path).startswith(str(self.data_dir.resolve())):
                    return f"Error: Access denied. Cannot create directory '{directory_path}' outside the file system."
            except Exception:
                return f"Error: Invalid directory path '{directory_path}'."

            # Check if directory already exists
            if full_path.exists():
                if full_path.is_dir():
                    return f"Directory '{directory_path}' already exists."
                else:
                    return f"Error: '{directory_path}' already exists as a file."

            # Create directory (including parent directories)
            full_path.mkdir(parents=True, exist_ok=True)

            return f"Directory '{directory_path}' created successfully."

        except Exception as e:
            return f"Error: Could not create directory '{directory_path}': {str(e)}"

    @classmethod
    def from_state(cls, state: FileSystemState) -> 'FileSystem':
        """Restore file system from serializable state at the exact same location"""
        # Create file system without default files
        fs = cls(base_dir=Path(state.base_dir), create_default_files=False)
        fs.extracted_content_count = state.extracted_content_count

        # Restore all files
        for full_filename, file_data in state.files.items():
            file_type = file_data['type']
            file_info = file_data['data']

            # Create the appropriate file object based on type
            if file_type == 'MarkdownFile':
                file_obj = MarkdownFile(**file_info)
            elif file_type == 'TxtFile':
                file_obj = TxtFile(**file_info)
            elif file_type == 'JsonFile':
                file_obj = JsonFile(**file_info)
            elif file_type == 'CsvFile':
                file_obj = CsvFile(**file_info)
            elif file_type == 'PdfFile':
                file_obj = PdfFile(**file_info)
            elif file_type == 'JSFile':
                file_obj = JSFile(**file_info)
            elif file_type == 'PythonFile':
                file_obj = PythonFile(**file_info)
            elif file_type == 'HtmlFile':
                file_obj = HtmlFile(**file_info)
            else:
                # Skip unknown file types
                continue

            # Add to files dict and sync to disk
            fs.files[full_filename] = file_obj
            file_obj.sync_to_disk_sync(fs.data_dir)

        return fs
