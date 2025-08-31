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
