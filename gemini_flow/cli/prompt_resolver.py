from pathlib import Path
from typing import Optional, Union

from gemini_flow.domain.exceptions import (
    PromptConflictError,
    PromptEmptyError,
    PromptEncodingError,
    PromptFileNotFoundError,
    PromptInputError,
)


class PromptResolver:
    """
    Object-oriented prompt resolver responsible for loading and validating
    prompts from inline arguments or local files.
    """

    DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB sanity limit

    @classmethod
    def resolve_text(
        cls,
        inline_text: Optional[str] = None,
        file_path: Optional[Union[str, Path]] = None,
        *,
        field_name: str = "prompt",
        required: bool = True,
        max_size_bytes: int = DEFAULT_MAX_FILE_SIZE,
    ) -> Optional[str]:
        """
        Resolves text from either an inline string or a file path.

        :param inline_text: Text passed directly as a string.
        :param file_path: Path to a file.
        :param field_name: Field identifier used in error messages.
        :param required: Whether at least one source must be provided.
        :param max_size_bytes: Maximum allowed file size in bytes.
        :return: The resolved text, or None if not required and no input was provided.
        :raises PromptConflictError: If both inline text and file are provided.
        :raises PromptInputError: If required but neither source is provided.
        :raises PromptFileNotFoundError: If the specified file does not exist or is a directory.
        :raises PromptEncodingError: If the file content cannot be decoded as UTF-8 text.
        :raises PromptEmptyError: If required and the resolved content is empty.
        """
        has_inline = inline_text is not None and inline_text != ""
        has_file = file_path is not None

        # 1. Mutual exclusion check
        if has_inline and has_file:
            raise PromptConflictError(
                f"Cannot specify both inline {field_name} and file source. Please choose only one."
            )

        # 2. Neither provided check
        if not has_inline and not has_file:
            if required:
                raise PromptInputError(
                    f"No {field_name} provided. Please provide an inline {field_name} "
                    f"or use -f/--file <path>."
                )
            return None

        # 3. Read content
        if has_file:
            content = cls._read_file(file_path, field_name=field_name, max_size_bytes=max_size_bytes)
        else:
            content = inline_text

        # 4. Content emptiness validation
        if required and (content is None or not content.strip()):
            raise PromptEmptyError(f"The resolved {field_name} is empty or contains only whitespace.")

        if not required and content is not None and not content.strip():
            return None

        return content

    @classmethod
    def resolve_prompt(
        cls,
        inline_prompt: Optional[str] = None,
        file_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Convenience method for resolving the primary user prompt."""
        resolved = cls.resolve_text(
            inline_text=inline_prompt,
            file_path=file_path,
            field_name="prompt",
            required=True,
        )
        assert resolved is not None
        return resolved

    @classmethod
    def resolve_system_prompt(
        cls,
        inline_system_prompt: Optional[str] = None,
        file_path: Optional[Union[str, Path]] = None,
    ) -> Optional[str]:
        """Convenience method for resolving an optional system prompt."""
        return cls.resolve_text(
            inline_text=inline_system_prompt,
            file_path=file_path,
            field_name="system-prompt",
            required=False,
        )

    @classmethod
    def _read_file(
        cls,
        file_path: Union[str, Path],
        *,
        field_name: str,
        max_size_bytes: int,
    ) -> str:
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            raise PromptFileNotFoundError(f"Specified {field_name} file not found: {path}")

        if not path.is_file():
            raise PromptFileNotFoundError(f"Specified {field_name} path is not a file: {path}")

        try:
            stat_info = path.stat()
        except OSError as e:
            raise PromptInputError(f"Cannot access file '{path}': {e}") from e

        if stat_info.st_size > max_size_bytes:
            raise PromptInputError(
                f"File '{path.name}' exceeds maximum allowed size ({stat_info.st_size} > {max_size_bytes} bytes)."
            )

        try:
            raw_bytes = path.read_bytes()
        except PermissionError as e:
            raise PromptInputError(f"Permission denied while reading '{path}': {e}") from e
        except OSError as e:
            raise PromptInputError(f"Failed to read '{path}': {e}") from e

        # Decode using utf-8-sig to cleanly handle standard UTF-8 and BOM
        try:
            text = raw_bytes.decode("utf-8-sig")
            return text.replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError as e:
            raise PromptEncodingError(
                f"Failed to decode file '{path.name}' as UTF-8 text. "
                "If this is an image file, please use --image instead."
            ) from e
