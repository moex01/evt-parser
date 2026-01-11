"""Custom exceptions for the EVT to EVTX converter.

This module defines the exception hierarchy used throughout the converter library
to handle various error conditions during validation and conversion.
"""

from __future__ import annotations

from typing import Optional


class EvtConverterError(Exception):
    """Base exception for all EVT converter errors.

    All custom exceptions in this library inherit from this base class,
    allowing users to catch all converter-related errors with a single except block.
    """

    pass


class PlatformNotSupportedError(EvtConverterError):
    """Raised when the converter is run on a non-Windows platform.

    The EVT to EVTX conversion relies on the Windows-native wevtutil tool,
    which is only available on Windows operating systems.
    """

    def __init__(self, platform: str) -> None:
        """Initialize the exception with the detected platform.

        Args:
            platform: The name of the detected operating system platform.
        """
        self.platform = platform
        super().__init__(
            f"EVT to EVTX conversion is only supported on Windows. "
            f"Current platform: {platform}"
        )


class WevtutilNotFoundError(EvtConverterError):
    """Raised when the wevtutil command-line tool cannot be found.

    This typically indicates that the system is missing the Windows Event Log
    utilities or they are not in the system PATH.
    """

    def __init__(self) -> None:
        super().__init__(
            "wevtutil command not found. Ensure Windows Event Log utilities "
            "are installed and available in the system PATH."
        )


class FileValidationError(EvtConverterError):
    """Raised when input file validation fails.

    This can occur when:
    - The input file does not exist
    - The file does not have a .evt extension
    - The file cannot be read due to permissions
    - The output file already exists and overwrite is disabled
    """

    pass


class EvtDirtyFlagError(FileValidationError):
    """Raised when an EVT file has the DIRTY flag set and auto-repair is disabled.

    EVT files copied from running Windows systems have this flag set,
    which prevents wevtutil from processing them.
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        super().__init__(
            f"EVT file has DIRTY flag set (copied from running system): {file_path}. "
            "Enable auto_repair or manually clear the flag at offset 0x24."
        )


class ConversionError(EvtConverterError):
    """Raised when the conversion process fails.

    This exception captures details about wevtutil execution failures,
    including return codes and error messages from stderr.
    """

    def __init__(
        self,
        message: str,
        return_code: Optional[int] = None,
        stderr: Optional[str] = None,
    ) -> None:
        """Initialize the conversion error with execution details.

        Args:
            message: Human-readable error description.
            return_code: The exit code returned by wevtutil (if available).
            stderr: Error output from wevtutil (if available).
        """
        self.return_code = return_code
        self.stderr = stderr

        error_parts = [message]
        if return_code is not None:
            error_parts.append(f"Return code: {return_code}")
        if stderr:
            error_parts.append(f"Error output: {stderr}")

        super().__init__(" | ".join(error_parts))


class ParserError(EvtConverterError):
    """Base exception for EVT parsing errors.

    Raised when the native EVT parser encounters issues reading
    or interpreting EVT file contents.
    """

    pass


class CorruptedEvtError(ParserError):
    """Raised when an EVT file is corrupted beyond repair.

    This indicates structural corruption in the EVT file that
    prevents reliable parsing of event records.
    """

    def __init__(self, file_path: str, details: Optional[str] = None) -> None:
        self.file_path = file_path
        self.details = details
        message = f"Corrupted EVT file: {file_path}"
        if details:
            message += f" ({details})"
        super().__init__(message)


class OutputFormatError(EvtConverterError):
    """Raised when output formatting fails.

    This can occur when:
    - The specified output format is not supported
    - Output file cannot be written
    - Encoding issues during formatting
    """

    def __init__(self, message: str, format_name: Optional[str] = None) -> None:
        self.format_name = format_name
        if format_name:
            message = f"[{format_name}] {message}"
        super().__init__(message)
