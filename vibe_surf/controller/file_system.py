import asyncio
from pathlib import Path
from browser_use.filesystem.file_system import FileSystem, FileSystemError, INVALID_FILENAME_ERROR_MESSAGE


class CustomFileSystem(FileSystem):
    async def read_file(self, full_filename: str, external_file: bool = False) -> str:
        """Read file content using file-specific read method and return appropriate message to LLM"""
        if external_file:
            try:
                try:
                    _, extension = self._parse_filename(full_filename)
                except Exception:
                    return f'Error: Invalid filename format {full_filename}. Must be alphanumeric with a supported extension.'
                if extension in ['md', 'txt', 'json', 'csv']:
                    import anyio

                    async with await anyio.open_file(full_filename, 'r', encoding="utf-8") as f:
                        content = await f.read()
                        return f'Read from file {full_filename}.\n<content>\n{content}\n</content>'
                elif extension == 'pdf':
                    import pypdf

                    reader = pypdf.PdfReader(full_filename)
                    num_pages = len(reader.pages)
                    MAX_PDF_PAGES = 10
                    extra_pages = num_pages - MAX_PDF_PAGES
                    extracted_text = ''
                    for page in reader.pages[:MAX_PDF_PAGES]:
                        extracted_text += page.extract_text()
                    extra_pages_text = f'{extra_pages} more pages...' if extra_pages > 0 else ''
                    return f'Read from file {full_filename}.\n<content>\n{extracted_text}\n{extra_pages_text}</content>'
                else:
                    return f'Error: Cannot read file {full_filename} as {extension} extension is not supported.'
            except FileNotFoundError:
                return f"Error: File '{full_filename}' not found."
            except PermissionError:
                return f"Error: Permission denied to read file '{full_filename}'."
            except Exception as e:
                return f"Error: Could not read file '{full_filename}'."

        if not self._is_valid_filename(full_filename):
            return INVALID_FILENAME_ERROR_MESSAGE

        file_obj = self.get_file(full_filename)
        if not file_obj:
            return f"File '{full_filename}' not found."

        try:
            content = file_obj.read()
            return f'Read from file {full_filename}.\n<content>\n{content}\n</content>'
        except FileSystemError as e:
            return str(e)
        except Exception:
            return f"Error: Could not read file '{full_filename}'."

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

            # Check if source file exists
            if not src_path.exists() if hasattr(src_path, 'exists') else not Path(src_path).exists():
                return f"Error: Source file '{src_filename}' not found."

            # Use shutil to copy file
            with ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(executor, shutil.copy2, str(src_path), str(dst_path))

            # Read the copied file content and create file object for internal tracking
            content = dst_path.read_text(encoding='utf-8')
            dst_name, dst_extension = self._parse_filename(dst_filename)
            file_class = self._get_file_type_class(dst_extension)

            if file_class:
                dst_file = file_class(name=dst_name, content=content)
                self.files[dst_filename] = dst_file

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
        if not self.get_file(old_filename):
            return f"Error: File '{old_filename}' not found."

        # Check if new filename already exists
        if self.get_file(new_filename):
            return f"Error: File '{new_filename}' already exists."

        try:
            old_path = self.data_dir / old_filename
            new_path = self.data_dir / new_filename

            # Use shutil to move/rename file
            with ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(executor, shutil.move, str(old_path), str(new_path))

            # Update internal file tracking
            old_file = self.files[old_filename]
            del self.files[old_filename]

            # Update file object name if needed
            new_name, new_extension = self._parse_filename(new_filename)
            old_file.name = new_name
            self.files[new_filename] = old_file

            return f"File '{old_filename}' renamed to '{new_filename}' successfully."

        except Exception as e:
            return f"Error: Could not rename file '{old_filename}' to '{new_filename}'. {str(e)}"

    async def move_file(self, old_filename: str, new_filename: str) -> str:
        """Move a file within the FileSystem from old_filename to new_filename"""
        import shutil
        from concurrent.futures import ThreadPoolExecutor

        # Check if old file exists
        if not self.get_file(old_filename):
            return f"Error: File '{old_filename}' not found."

        # Check if new filename already exists
        if self.get_file(new_filename):
            return f"Error: File '{new_filename}' already exists."

        try:
            old_path = self.data_dir / old_filename
            new_path = self.data_dir / new_filename

            # Use shutil to move file
            with ThreadPoolExecutor() as executor:
                await asyncio.get_event_loop().run_in_executor(executor, shutil.move, str(old_path), str(new_path))

            # Update internal file tracking
            old_file = self.files[old_filename]
            del self.files[old_filename]

            # Update file object name if needed
            new_name, new_extension = self._parse_filename(new_filename)
            old_file.name = new_name
            self.files[new_filename] = old_file

            return f"File '{old_filename}' moved to '{new_filename}' successfully."

        except Exception as e:
            return f"Error: Could not move file '{old_filename}' to '{new_filename}'. {str(e)}"
