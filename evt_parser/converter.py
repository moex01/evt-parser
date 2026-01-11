"""Core conversion functionality for EVT to EVTX conversion.

This module provides the main conversion functions that use the Windows wevtutil
command-line tool to convert Windows XP / Windows Server 2003 legacy Event Log
(.evt) files to modern Windows Event Log (.evtx) format.
"""

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Union

from .exceptions import ConversionError, FileValidationError
from .utils import (
    check_platform,
    check_wevtutil_available,
    validate_evt_file,
    generate_output_path,
    find_evt_files,
    is_evt_dirty,
    repair_dirty_evt,
)


class ConversionStatus(Enum):
    """Status of a conversion operation.

    Attributes:
        SUCCESS: Conversion completed successfully.
        FAILED: Conversion failed due to an error.
        SKIPPED: Conversion was skipped (e.g., output file exists without overwrite).
    """

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ConversionResult:
    """Result of a single file conversion operation.

    Attributes:
        status: The outcome of the conversion (SUCCESS, FAILED, or SKIPPED).
        input_file: Path to the input .evt file.
        output_file: Path to the output .evtx file (None if conversion failed).
        error_message: Description of the error if conversion failed (None on success).
        duration_seconds: Time taken for the conversion in seconds (None if skipped).
    """

    status: ConversionStatus
    input_file: Path
    output_file: Optional[Path] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None

    @property
    def success(self) -> bool:
        """Check if the conversion was successful.

        Returns:
            True if status is SUCCESS, False otherwise.
        """
        return self.status == ConversionStatus.SUCCESS


@dataclass
class BatchConversionSummary:
    """Summary of a batch conversion operation.

    Attributes:
        total: Total number of files processed.
        successful: Number of successfully converted files.
        failed: Number of files that failed to convert.
        skipped: Number of files that were skipped.
        results: List of individual ConversionResult objects for each file.
        total_duration_seconds: Total time taken for all conversions in seconds.
    """

    total: int
    successful: int
    failed: int
    skipped: int
    results: List[ConversionResult]
    total_duration_seconds: float

    @property
    def success_rate(self) -> float:
        """Calculate the success rate as a percentage.

        Returns:
            Percentage of successful conversions (0-100), or 0 if no files processed.
        """
        if self.total == 0:
            return 0.0
        return (self.successful / self.total) * 100


def convert_evt_to_evtx(
    input_file: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
    timeout: int = 60,
    auto_repair: bool = True,
) -> ConversionResult:
    """Convert a single .evt file to .evtx format using wevtutil.

    This function uses the Windows wevtutil command-line tool to perform the conversion:
        wevtutil epl source.evt target.evtx /lf:true

    The /lf:true flag specifies that the source is a log file rather than a channel name.

    Args:
        input_file: Path to the input .evt file.
        output_file: Path for the output .evtx file. If None, automatically generates
                    the output path by replacing .evt with .evtx in the same directory.
        overwrite: If True, overwrite existing output files. If False, raise an error
                  if the output file already exists.
        timeout: Maximum time in seconds to wait for wevtutil to complete.
                Useful for very large log files. Default is 60 seconds.
        auto_repair: If True (default), automatically repair dirty EVT files
                    by clearing the DIRTY flag before conversion. The original
                    file is not modified; a temporary copy is used.

    Returns:
        ConversionResult object containing the conversion status and details.

    Raises:
        PlatformNotSupportedError: If not running on Windows.
        WevtutilNotFoundError: If wevtutil is not available.
        FileValidationError: If input file validation fails.
        ConversionError: If the conversion process fails critically.

    Example:
        >>> result = convert_evt_to_evtx("System.evt")
        >>> if result.success:
        ...     print(f"Converted to {result.output_file}")
        >>>
        >>> result = convert_evt_to_evtx("System.evt", "Output.evtx", overwrite=True)
    """
    import time

    # Convert to Path objects
    input_path = Path(input_file)
    output_path = Path(output_file) if output_file else generate_output_path(input_path)

    # Perform platform and tool checks
    check_platform()
    check_wevtutil_available()

    # Validate files
    try:
        validate_evt_file(input_path, output_path, overwrite)
    except Exception as e:
        # Return a FAILED result if validation fails
        return ConversionResult(
            status=ConversionStatus.FAILED,
            input_file=input_path,
            output_file=output_path,
            error_message=str(e),
        )

    # Check if output exists and we're not overwriting - skip this file
    if output_path.exists() and not overwrite:
        return ConversionResult(
            status=ConversionStatus.SKIPPED,
            input_file=input_path,
            output_file=output_path,
            error_message="Output file exists and overwrite is disabled",
        )

    # Check for and handle dirty EVT files
    temp_file = None
    effective_input = input_path

    try:
        is_dirty = is_evt_dirty(input_path)
    except FileValidationError:
        is_dirty = False

    if is_dirty:
        try:
            if auto_repair:
                temp_file = repair_dirty_evt(input_path)
                effective_input = temp_file
            else:
                return ConversionResult(
                    status=ConversionStatus.FAILED,
                    input_file=input_path,
                    output_file=output_path,
                    error_message=(
                        f"EVT file has DIRTY flag set: {input_path}. "
                        "Enable auto_repair to fix."
                    ),
                )
        except Exception as e:
            return ConversionResult(
                status=ConversionStatus.FAILED,
                input_file=input_path,
                output_file=output_path,
                error_message=str(e),
            )

    # Build the wevtutil command
    # Format: wevtutil epl source.evt target.evtx /lf:true
    command = [
        "wevtutil",
        "epl",
        str(effective_input.absolute()),
        str(output_path.absolute()),
        "/lf:true",
    ]

    # Execute the conversion
    start_time = time.time()
    try:
        subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=True
        )
        duration = time.time() - start_time

        # Verify output file was created
        if not output_path.exists():
            return ConversionResult(
                status=ConversionStatus.FAILED,
                input_file=input_path,
                output_file=output_path,
                error_message="Output file was not created by wevtutil",
                duration_seconds=duration,
            )

        # Success!
        return ConversionResult(
            status=ConversionStatus.SUCCESS,
            input_file=input_path,
            output_file=output_path,
            duration_seconds=duration,
        )

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return ConversionResult(
            status=ConversionStatus.FAILED,
            input_file=input_path,
            output_file=output_path,
            error_message=f"Conversion timed out after {timeout} seconds",
            duration_seconds=duration,
        )

    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        error_msg = f"wevtutil failed with return code {e.returncode}"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"

        return ConversionResult(
            status=ConversionStatus.FAILED,
            input_file=input_path,
            output_file=output_path,
            error_message=error_msg,
            duration_seconds=duration,
        )

    except Exception as e:
        duration = time.time() - start_time
        return ConversionResult(
            status=ConversionStatus.FAILED,
            input_file=input_path,
            output_file=output_path,
            error_message=f"Unexpected error: {str(e)}",
            duration_seconds=duration,
        )

    finally:
        # Clean up temporary file
        if temp_file is not None and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass  # Best effort cleanup


def batch_convert(
    source_dir: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    recursive: bool = False,
    overwrite: bool = False,
    timeout: int = 60,
    continue_on_error: bool = True,
    progress_callback: Optional[Callable[[int, int, Path], None]] = None,
    auto_repair: bool = True,
) -> BatchConversionSummary:
    """Convert multiple .evt files in a directory to .evtx format.

    Scans the source directory for .evt files and converts each one using wevtutil.
    Optionally searches subdirectories recursively and preserves directory structure.

    Args:
        source_dir: Path to the directory containing .evt files.
        output_dir: Path to the output directory. If None, converted files are placed
                   in the same directory as their source files. If specified, the
                   directory structure is preserved relative to source_dir in recursive mode.
        recursive: If True, search subdirectories for .evt files recursively.
                  If False, only process files in the immediate directory.
        overwrite: If True, overwrite existing .evtx files. If False, skip files
                  that would overwrite existing outputs.
        timeout: Maximum time in seconds for each individual file conversion.
        continue_on_error: If True, continue processing remaining files after errors.
                         If False, stop on the first error and raise ConversionError.
        progress_callback: Optional callback function called after each file is processed.
                          Signature: callback(current: int, total: int, file: Path)
                          where current is the number of files processed so far,
                          total is the total number of files to process,
                          and file is the current file being processed.

    Returns:
        BatchConversionSummary object with statistics and individual results.

    Raises:
        PlatformNotSupportedError: If not running on Windows.
        WevtutilNotFoundError: If wevtutil is not available.
        FileValidationError: If the source directory doesn't exist or is invalid.
        ConversionError: If continue_on_error is False and a conversion fails.

    Example:
        >>> summary = batch_convert("C:/Logs", recursive=True)
        >>> print(f"Converted {summary.successful}/{summary.total} files")
        >>> print(f"Success rate: {summary.success_rate:.1f}%")
        >>>
        >>> def progress(current, total, file):
        ...     print(f"[{current}/{total}] Processing {file.name}")
        >>> summary = batch_convert("C:/Logs", progress_callback=progress)
    """
    import time

    # Convert to Path objects
    source_path = Path(source_dir)
    output_path = Path(output_dir) if output_dir else None

    # Perform platform and tool checks
    check_platform()
    check_wevtutil_available()

    # Find all .evt files
    evt_files = find_evt_files(source_path, recursive=recursive)

    # Initialize counters and results
    results: List[ConversionResult] = []
    successful = 0
    failed = 0
    skipped = 0
    total = len(evt_files)

    start_time = time.time()

    # Process each file
    for index, evt_file in enumerate(evt_files, start=1):
        # Call progress callback if provided
        if progress_callback:
            progress_callback(index, total, evt_file)

        # Determine output file path
        if output_path:
            # Preserve directory structure in output
            if recursive:
                # Calculate relative path from source_dir
                relative_path = evt_file.relative_to(source_path)
                file_output_dir = output_path / relative_path.parent
                # Create output subdirectory if needed
                file_output_dir.mkdir(parents=True, exist_ok=True)
                file_output_path = generate_output_path(evt_file, file_output_dir)
            else:
                # All files go to output_dir root
                output_path.mkdir(parents=True, exist_ok=True)
                file_output_path = generate_output_path(evt_file, output_path)
        else:
            # Output to same directory as input
            file_output_path = None

        # Convert the file
        result = convert_evt_to_evtx(
            evt_file,
            file_output_path,
            overwrite=overwrite,
            timeout=timeout,
            auto_repair=auto_repair,
        )

        # Update counters
        if result.status == ConversionStatus.SUCCESS:
            successful += 1
        elif result.status == ConversionStatus.FAILED:
            failed += 1
            # Stop on first error if continue_on_error is False
            if not continue_on_error:
                raise ConversionError(
                    f"Conversion failed for {evt_file}: {result.error_message}"
                )
        elif result.status == ConversionStatus.SKIPPED:
            skipped += 1

        results.append(result)

    total_duration = time.time() - start_time

    # Create summary
    summary = BatchConversionSummary(
        total=total,
        successful=successful,
        failed=failed,
        skipped=skipped,
        results=results,
        total_duration_seconds=total_duration,
    )

    return summary
