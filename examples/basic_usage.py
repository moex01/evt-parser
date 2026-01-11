#!/usr/bin/env python3
"""
Basic Usage Examples for EVT to EVTX Converter

This file demonstrates simple, common usage patterns for converting
Windows Event Log files from .evt to .evtx format.

Requirements:
    - Windows Vista or later
    - Python 3.8+
    - evt_parser package installed
"""

from pathlib import Path
from typing import Optional

from evt_parser import ConversionStatus, batch_convert, convert_evt_to_evtx
from evt_parser.exceptions import (
    PlatformNotSupportedError,
    WevtutilNotFoundError,
)


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "n/a"
    return f"{seconds:.2f}s"


def example_1_simple_conversion() -> None:
    """
    Example 1: Simple single file conversion with auto-generated output name.

    The output file will be created in the same directory as the input file
    with .evtx extension.
    """
    print("=" * 70)
    print("Example 1: Simple Conversion")
    print("=" * 70)

    input_file = "System.evt"

    try:
        result = convert_evt_to_evtx(input_file)

        if result.success:
            print(f"Success! Converted to: {result.output_file}")
            print(f"Conversion took: {_format_duration(result.duration_seconds)}")
        else:
            print(f"Conversion failed: {result.error_message or 'Unknown error'}")

    except PlatformNotSupportedError as e:
        print(f"Error: {e}")
    except WevtutilNotFoundError as e:
        print(f"Error: {e}")

    print()


def example_2_custom_output() -> None:
    """
    Example 2: Convert with custom output file name and location.

    Specify exactly where you want the output file to be created.
    """
    print("=" * 70)
    print("Example 2: Custom Output Location")
    print("=" * 70)

    input_file = "C:\\Windows\\System32\\winevt\\Logs\\Archive-System.evt"
    output_file = "C:\\ConvertedLogs\\System.evtx"

    try:
        result = convert_evt_to_evtx(input_file=input_file, output_file=output_file)

        if result.success:
            print(f"Input:  {result.input_file}")
            print(f"Output: {result.output_file}")
            print(f"Time:   {_format_duration(result.duration_seconds)}")
        else:
            print(f"Failed: {result.error_message or 'Unknown error'}")

    except PlatformNotSupportedError as e:
        print(f"Error: {e}")
    except WevtutilNotFoundError as e:
        print(f"Error: {e}")

    print()


def example_3_overwrite_existing() -> None:
    """
    Example 3: Overwrite existing output file.

    By default, the converter will not overwrite existing files.
    Use overwrite=True to force overwriting.
    """
    print("=" * 70)
    print("Example 3: Overwrite Existing File")
    print("=" * 70)

    input_file = "Application.evt"
    output_file = "Application.evtx"

    # First conversion
    print("First conversion...")
    result1 = convert_evt_to_evtx(input_file, output_file)

    if result1.success:
        print(f"Created: {result1.output_file}")

    # Try to convert again (will skip because file exists)
    print("\nSecond conversion (without overwrite)...")
    result2 = convert_evt_to_evtx(input_file, output_file, overwrite=False)

    if not result2.success:
        print(f"Skipped: {result2.error_message}")

    # Force overwrite
    print("\nThird conversion (with overwrite)...")
    result3 = convert_evt_to_evtx(input_file, output_file, overwrite=True)

    if result3.success:
        print(f"Overwritten: {result3.output_file}")

    print()


def example_4_timeout_handling() -> None:
    """
    Example 4: Handle large files with custom timeout.

    Large .evt files may take a long time to convert. Use the timeout
    parameter to specify how long to wait (in seconds).
    """
    print("=" * 70)
    print("Example 4: Custom Timeout for Large Files")
    print("=" * 70)

    large_file = "LargeEventLog.evt"

    try:
        # Set timeout to 5 minutes (300 seconds)
        result = convert_evt_to_evtx(input_file=large_file, timeout=300)

        if result.success:
            print("Large file converted successfully!")
            if result.output_file is not None and result.output_file.exists():
                print(
                    f"Size: {result.output_file.stat().st_size / (1024 * 1024):.2f} MB"
                )
            print(f"Time: {_format_duration(result.duration_seconds)}")
        else:
            print(
                f"Conversion failed or timed out: {result.error_message or 'Unknown error'}"
            )

    except PlatformNotSupportedError as e:
        print(f"Error: {e}")
    except WevtutilNotFoundError as e:
        print(f"Error: {e}")

    print()


def example_5_path_objects() -> None:
    """
    Example 5: Using pathlib.Path objects instead of strings.

    The converter accepts both strings and Path objects for file paths.
    """
    print("=" * 70)
    print("Example 5: Using pathlib.Path Objects")
    print("=" * 70)

    input_path = Path("C:/EventLogs/Security.evt")
    output_path = Path("C:/Converted/Security.evtx")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = convert_evt_to_evtx(input_file=input_path, output_file=output_path)

        if result.success:
            print(f"Input:  {result.input_file.absolute()}")
            print(f"Output: {result.output_file.absolute()}")
            print(f"Output exists: {result.output_file.exists()}")

    except Exception as e:
        print(f"Error: {e}")

    print()


def example_6_error_handling() -> None:
    """
    Example 6: Comprehensive error handling.

    Demonstrates how to catch and handle different types of errors
    that may occur during conversion.
    """
    print("=" * 70)
    print("Example 6: Error Handling")
    print("=" * 70)

    files_to_convert = [
        "System.evt",
        "Application.evt",
        "Security.evt",
        "NonExistent.evt",
    ]

    for evt_file in files_to_convert:
        print(f"\nProcessing: {evt_file}")

        try:
            result = convert_evt_to_evtx(evt_file)

            if result.success:
                print(f"  [SUCCESS] -> {result.output_file}")
            elif result.status == ConversionStatus.SKIPPED:
                print(f"  [SKIPPED] {result.error_message}")
            else:
                print(f"  [FAILED] {result.error_message}")

        except PlatformNotSupportedError:
            print("  [ERROR] This tool only works on Windows")
            break  # No point trying other files

        except WevtutilNotFoundError:
            print("  [ERROR] wevtutil command not found")
            break  # No point trying other files

        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            continue  # Try next file

    print()


def example_7_check_result_details() -> None:
    """
    Example 7: Examining conversion result details.

    The ConversionResult object contains useful information about
    the conversion process.
    """
    print("=" * 70)
    print("Example 7: Examining Result Details")
    print("=" * 70)

    input_file = "System.evt"

    result = convert_evt_to_evtx(input_file)

    # Check success status
    print(f"Conversion successful: {result.success}")

    # Get file paths
    print(f"Input file:  {result.input_file}")
    print(f"Output file: {result.output_file}")

    # Check timing
    print(
        f"Duration: {result.duration_seconds if result.duration_seconds is not None else 'n/a'} seconds"
    )

    # Check for errors
    if result.error_message:
        print(f"Error message: {result.error_message}")
    else:
        print("No errors occurred")

    # File size comparison (if successful)
    if result.success and result.output_file:
        input_size = result.input_file.stat().st_size
        output_size = result.output_file.stat().st_size

        print("\nFile Sizes:")
        print(f"  Input:  {input_size:,} bytes ({input_size / 1024:.2f} KB)")
        print(f"  Output: {output_size:,} bytes ({output_size / 1024:.2f} KB)")
        print(f"  Ratio:  {output_size / input_size:.2f}x")

    print()


def example_8_multiple_files() -> None:
    """
    Example 8: Converting multiple files sequentially.

    Simple loop to convert multiple files one by one.
    For more advanced batch processing, see batch_conversion.py
    """
    print("=" * 70)
    print("Example 8: Multiple Files Sequential")
    print("=" * 70)

    files = ["System.evt", "Application.evt", "Security.evt"]

    successful = 0
    failed = 0

    for i, evt_file in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Converting {evt_file}...")

        try:
            result = convert_evt_to_evtx(evt_file)

            if result.success:
                print(f"     SUCCESS - {_format_duration(result.duration_seconds)}")
                successful += 1
            else:
                print(f"     FAILED - {result.error_message}")
                failed += 1

        except Exception as e:
            print(f"     ERROR - {e}")
            failed += 1

    print(f"\n{'='*70}")
    print(f"Summary: {successful} succeeded, {failed} failed out of {len(files)} total")
    print()


def example_9_batch_conversion() -> None:
    """Example 9: Batch convert a directory of `.evt` files."""
    print("=" * 70)
    print("Example 9: Batch Conversion")
    print("=" * 70)

    source_dir = Path("C:/EventLogs")
    output_dir = Path("C:/ConvertedLogs")

    def progress(current: int, total: int, file_path: Path) -> None:
        print(f"[{current}/{total}] {file_path}")

    try:
        summary = batch_convert(
            source_dir=source_dir,
            output_dir=output_dir,
            recursive=True,
            progress_callback=progress,
        )

        print("\nBatch summary:")
        print(f"  Total:      {summary.total}")
        print(f"  Successful: {summary.successful}")
        print(f"  Failed:     {summary.failed}")
        print(f"  Skipped:    {summary.skipped}")
        print(f"  Duration:   {_format_duration(summary.total_duration_seconds)}")

    except PlatformNotSupportedError as e:
        print(f"Error: {e}")
    except WevtutilNotFoundError as e:
        print(f"Error: {e}")

    print()


def main() -> None:
    """Run all examples."""
    print("\n")
    print("*" * 70)
    print("EVT to EVTX Converter - Basic Usage Examples")
    print("*" * 70)
    print()

    # Note: These examples assume you have .evt files available
    # Uncomment the examples you want to run

    # example_1_simple_conversion()
    # example_2_custom_output()
    # example_3_overwrite_existing()
    # example_4_timeout_handling()
    # example_5_path_objects()
    # example_6_error_handling()
    # example_7_check_result_details()
    # example_8_multiple_files()
    # example_9_batch_conversion()

    print("\nTo run these examples:")
    print("1. Ensure you have .evt files available")
    print("2. Uncomment the example functions you want to run")
    print("3. Adjust file paths to match your system")
    print("4. Run this script: python3 basic_usage.py")
    print()


if __name__ == "__main__":
    main()
