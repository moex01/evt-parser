"""Utility functions for platform detection, validation, and file operations.

This module provides helper functions used throughout the converter library
for platform checks, file validation, and directory scanning.
"""

import platform
import shutil
from pathlib import Path
from typing import List, Optional

from .exceptions import (
    PlatformNotSupportedError,
    WevtutilNotFoundError,
    FileValidationError,
)

EVT_SIGNATURE_OFFSET = 0x04
EVT_SIGNATURE = b"LfLe"

# EVT Header structure constants
EVT_HEADER_SIZE = 48
EVT_FLAGS_OFFSET = 0x24  # Offset to flags field in EVT header
EVT_FLAG_DIRTY = 0x01  # File not properly closed (copied from live system)
EVT_FLAG_WRAP = 0x02  # Log has wrapped


def validate_legacy_evt_signature(input_file: Path) -> None:
    """Validate that a file looks like a legacy Windows Event Log (.evt).

    The classic EVT format (used by Windows XP / Windows Server 2003) contains the
    signature bytes "LfLe" at offset 0x04.

    Args:
        input_file: Path to the input file to validate.

    Raises:
        FileValidationError: If the signature is missing or the file is too small.
    """
    try:
        with input_file.open("rb") as f:
            header = f.read(EVT_SIGNATURE_OFFSET + len(EVT_SIGNATURE))
    except OSError as e:
        raise FileValidationError(f"Cannot read input file: {input_file} ({e})")

    if len(header) < EVT_SIGNATURE_OFFSET + len(EVT_SIGNATURE):
        raise FileValidationError(
            f"Input file is too small to be a valid legacy .evt: {input_file}"
        )

    if (
        header[EVT_SIGNATURE_OFFSET : EVT_SIGNATURE_OFFSET + len(EVT_SIGNATURE)]
        != EVT_SIGNATURE
    ):
        raise FileValidationError(
            "Input file does not appear to be a legacy Windows Event Log (.evt) "
            f"(missing {EVT_SIGNATURE!r} signature at offset 0x{EVT_SIGNATURE_OFFSET:02X}): "
            f"{input_file}"
        )


def check_platform() -> None:
    """Verify that the current platform is Windows.

    The EVT to EVTX conversion requires the Windows-native wevtutil tool,
    so this function ensures the code is running on a Windows system.

    Raises:
        PlatformNotSupportedError: If the current platform is not Windows.

    Example:
        >>> check_platform()  # On Windows - no exception
        >>> check_platform()  # On Linux - raises PlatformNotSupportedError
    """
    current_platform = platform.system()
    if current_platform != "Windows":
        raise PlatformNotSupportedError(current_platform)


def check_wevtutil_available() -> None:
    """Verify that the wevtutil command-line tool is available.

    Uses shutil.which() to check if wevtutil is in the system PATH
    and can be executed.

    Raises:
        WevtutilNotFoundError: If wevtutil cannot be found in the system PATH.

    Example:
        >>> check_wevtutil_available()  # On Windows with wevtutil - no exception
        >>> check_wevtutil_available()  # Without wevtutil - raises WevtutilNotFoundError
    """
    if shutil.which("wevtutil") is None:
        raise WevtutilNotFoundError()


def validate_evt_file(
    input_file: Path, output_file: Optional[Path] = None, overwrite: bool = False
) -> None:
    """Validate input and output files before conversion.

    Performs the following checks:
    - Input file exists and is a file (not a directory)
    - Input file has a .evt extension
    - If output_file is specified, its parent directory must exist
    - If output_file exists and is a directory, validation fails

    Args:
        input_file: Path to the input .evt file.
        output_file: Path to the output .evtx file (optional).
        overwrite: Whether to allow overwriting existing output files.
                   Note: existing output handling (skip vs overwrite) is done by
                   the conversion function, not this validator.

    Raises:
        FileValidationError: If any validation check fails.

    Example:
        >>> validate_evt_file(Path("System.evt"))  # Valid .evt file
        >>> validate_evt_file(Path("missing.evt"))  # Raises FileValidationError
        >>> validate_evt_file(Path("System.txt"))  # Raises FileValidationError (wrong extension)
    """
    # Check if input file exists
    if not input_file.exists():
        raise FileValidationError(f"Input file does not exist: {input_file}")

    # Check if input is a file (not a directory)
    if not input_file.is_file():
        raise FileValidationError(f"Input path is not a file: {input_file}")

    # Check if input file has .evt extension
    if input_file.suffix.lower() != ".evt":
        raise FileValidationError(
            f"Input file must have .evt extension. Got: {input_file.suffix}"
        )

    validate_legacy_evt_signature(input_file)

    # Check output file if specified
    if output_file is not None:
        # Ensure parent directory exists (wevtutil won't create it)
        if not output_file.parent.exists():
            raise FileValidationError(
                f"Output directory does not exist: {output_file.parent}"
            )

        if output_file.exists() and output_file.is_dir():
            raise FileValidationError(f"Output path is a directory: {output_file}")


def generate_output_path(input_file: Path, output_dir: Optional[Path] = None) -> Path:
    """Generate the output .evtx file path from the input .evt file path.

    Replaces the .evt extension with .evtx and optionally places the output
    in a different directory while preserving the filename.

    Args:
        input_file: Path to the input .evt file.
        output_dir: Optional directory for the output file.
                   If None, uses the same directory as the input file.

    Returns:
        Path object for the output .evtx file.

    Example:
        >>> generate_output_path(Path("C:/Logs/System.evt"))
        Path("C:/Logs/System.evtx")
        >>> generate_output_path(Path("C:/Logs/System.evt"), Path("C:/Output"))
        Path("C:/Output/System.evtx")
    """
    # Get the filename without extension and add .evtx
    output_filename = input_file.stem + ".evtx"

    # Use specified output directory or input file's directory
    if output_dir is not None:
        return output_dir / output_filename
    else:
        return input_file.parent / output_filename


def find_evt_files(directory: Path, recursive: bool = False) -> List[Path]:
    """Find all .evt files in a directory.

    Scans the specified directory for files with the .evt extension.
    Can optionally search recursively through subdirectories.

    Args:
        directory: Path to the directory to search.
        recursive: If True, search subdirectories recursively.
                  If False, only search the immediate directory.

    Returns:
        List of Path objects for all .evt files found, sorted alphabetically.

    Raises:
        FileValidationError: If the directory does not exist or is not a directory.

    Example:
        >>> find_evt_files(Path("C:/Logs"))
        [Path("C:/Logs/Application.evt"), Path("C:/Logs/System.evt")]
        >>> find_evt_files(Path("C:/Logs"), recursive=True)
        [Path("C:/Logs/Application.evt"), Path("C:/Logs/Archive/Old.evt"), ...]
    """
    # Validate directory
    if not directory.exists():
        raise FileValidationError(f"Directory does not exist: {directory}")

    if not directory.is_dir():
        raise FileValidationError(f"Path is not a directory: {directory}")

    # Find .evt files
    if recursive:
        pattern = "**/*.evt"
    else:
        pattern = "*.evt"

    # Use glob to find files and sort them
    evt_files = sorted(directory.glob(pattern))

    return evt_files


def is_evt_dirty(input_file: Path) -> bool:
    """Check if an EVT file has the DIRTY flag set.

    The DIRTY flag (bit 0 at offset 0x24) indicates the event log was not
    properly closed, typically because it was copied from a running system.

    Args:
        input_file: Path to the EVT file to check.

    Returns:
        True if the DIRTY flag is set, False otherwise.

    Raises:
        FileValidationError: If the file cannot be read or is too small.
    """
    from .exceptions import FileValidationError

    try:
        with input_file.open("rb") as f:
            f.seek(EVT_FLAGS_OFFSET)
            flags_bytes = f.read(4)
    except OSError as e:
        raise FileValidationError(f"Cannot read EVT flags: {input_file} ({e})")

    if len(flags_bytes) < 4:
        raise FileValidationError(
            f"File too small to contain flags field: {input_file}"
        )

    flags = int.from_bytes(flags_bytes, byteorder="little")
    return bool(flags & EVT_FLAG_DIRTY)


def repair_dirty_evt(input_file: Path, output_file: Optional[Path] = None) -> Path:
    """Create a repaired copy of a dirty EVT file with the DIRTY flag cleared.

    EVT files copied from running Windows systems have the DIRTY flag set,
    which causes wevtutil to reject them. This function creates a copy with
    the flag cleared and the end_offset corrected, preserving the original file.

    Args:
        input_file: Path to the dirty EVT file.
        output_file: Path for the repaired copy. If None, creates a temp file
                    in the same directory with a .tmp extension.

    Returns:
        Path to the repaired file.

    Raises:
        FileValidationError: If the file cannot be read or written.
    """
    import shutil
    import tempfile
    import os
    from .exceptions import FileValidationError

    # EOF record signature: 0x11111111 0x22222222 0x33333333 0x44444444
    EOF_SIGNATURE = bytes.fromhex("11111111222222223333333344444444")
    EOF_RECORD_SIZE = 40  # Size of the EOF record
    END_OFFSET_LOCATION = 0x14  # Offset to end_offset field in header
    CURRENT_RECORD_LOCATION = 0x18  # Offset to current record number in header
    OLDEST_RECORD_LOCATION = 0x1C  # Offset to oldest record number in header

    # Determine output path
    if output_file is None:
        # Create temp file in same directory to avoid cross-device issues
        fd, temp_path = tempfile.mkstemp(
            suffix=".evt.tmp",
            prefix=input_file.stem + "_repaired_",
            dir=input_file.parent,
        )
        os.close(fd)
        output_file = Path(temp_path)

    try:
        # Copy the entire file first
        shutil.copy2(input_file, output_file)

        with output_file.open("r+b") as f:
            # Read entire file to find EOF record
            f.seek(0)
            content = f.read()

            # Find EOF signature (starts 4 bytes into EOF record, after size field)
            eof_sig_pos = content.find(EOF_SIGNATURE)

            # Clear the DIRTY flag (bit 0)
            f.seek(EVT_FLAGS_OFFSET)
            flags_bytes = f.read(4)
            flags = int.from_bytes(flags_bytes, byteorder="little")
            new_flags = flags & ~EVT_FLAG_DIRTY
            f.seek(EVT_FLAGS_OFFSET)
            f.write(new_flags.to_bytes(4, byteorder="little"))

            # Fix header fields using EOF record data if found
            if eof_sig_pos >= 0:
                # EOF record starts 4 bytes before signature (size field)
                eof_record_start = eof_sig_pos - 4
                # end_offset should point to after the EOF record
                correct_end_offset = eof_record_start + EOF_RECORD_SIZE

                # Read current and oldest record numbers from EOF record
                # EOF record layout after signature: begin(4), end(4), current(4), oldest(4), size(4)
                # Offsets from signature start: +16=begin, +20=end, +24=current, +28=oldest
                eof_current_record = int.from_bytes(
                    content[eof_sig_pos + 24 : eof_sig_pos + 28], "little"
                )
                eof_oldest_record = int.from_bytes(
                    content[eof_sig_pos + 28 : eof_sig_pos + 32], "little"
                )

                # Update end_offset in header
                f.seek(END_OFFSET_LOCATION)
                f.write(correct_end_offset.to_bytes(4, byteorder="little"))

                # Sync current record number with EOF record
                f.seek(CURRENT_RECORD_LOCATION)
                f.write(eof_current_record.to_bytes(4, byteorder="little"))

                # Sync oldest record number with EOF record
                f.seek(OLDEST_RECORD_LOCATION)
                f.write(eof_oldest_record.to_bytes(4, byteorder="little"))

        return output_file

    except OSError as e:
        # Clean up on failure
        if output_file.exists():
            output_file.unlink()
        raise FileValidationError(f"Failed to repair EVT file: {input_file} ({e})")
