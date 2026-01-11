#!/usr/bin/env python3
"""
Batch conversion examples for `evt_parser`.

These examples demonstrate converting legacy `.evt` files to `.evtx` using
Windows `wevtutil` via `evt_parser.batch_convert`.

Requirements:
  - Windows Vista or later
  - Python 3.8+
  - `wevtutil` available on PATH
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from evt_parser import batch_convert
from evt_parser.exceptions import (
    FileValidationError,
    PlatformNotSupportedError,
    WevtutilNotFoundError,
)


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "n/a"
    return f"{seconds:.2f}s"


def example_1_simple_batch() -> None:
    """Convert all `.evt` files in a directory."""
    print("=" * 70)
    print("Example 1: Simple Batch Conversion")
    print("=" * 70)

    source_dir = Path(r"C:\EventLogs")

    try:
        summary = batch_convert(source_dir)
        print("\nConversion summary:")
        print(f"  Total:      {summary.total}")
        print(f"  Successful: {summary.successful}")
        print(f"  Failed:     {summary.failed}")
        print(f"  Skipped:    {summary.skipped}")
        print(f"  Duration:   {_format_duration(summary.total_duration_seconds)}")

    except (PlatformNotSupportedError, WevtutilNotFoundError, FileValidationError) as e:
        print(f"Error: {e}")

    print()


def example_2_recursive_to_output_dir() -> None:
    """Convert a directory tree and write outputs under a separate root."""
    print("=" * 70)
    print("Example 2: Recursive Conversion to Output Directory")
    print("=" * 70)

    source_dir = Path(r"C:\AllEventLogs")
    output_dir = Path(r"C:\ConvertedLogs")

    try:
        summary = batch_convert(
            source_dir=source_dir,
            output_dir=output_dir,
            recursive=True,
        )
        print("\nConversion summary:")
        print(f"  Source:    {source_dir}")
        print(f"  Output:    {output_dir}")
        print(f"  Total:     {summary.total}")
        print(f"  Success:   {summary.successful}")
        print(f"  Failed:    {summary.failed}")
        print(f"  Skipped:   {summary.skipped}")
        print(f"  Duration:  {_format_duration(summary.total_duration_seconds)}")

    except (PlatformNotSupportedError, WevtutilNotFoundError, FileValidationError) as e:
        print(f"Error: {e}")

    print()


def example_3_progress_callback() -> None:
    """Show per-file progress while converting."""
    print("=" * 70)
    print("Example 3: Progress Callback")
    print("=" * 70)

    source_dir = Path(r"C:\EventLogs")

    def progress(current: int, total: int, file_path: Path) -> None:
        print(f"[{current}/{total}] {file_path}")

    try:
        summary = batch_convert(
            source_dir=source_dir,
            recursive=True,
            progress_callback=progress,
        )
        print("\nConversion summary:")
        print(f"  Total:      {summary.total}")
        print(f"  Successful: {summary.successful}")
        print(f"  Failed:     {summary.failed}")
        print(f"  Skipped:    {summary.skipped}")
        print(f"  Duration:   {_format_duration(summary.total_duration_seconds)}")

    except (PlatformNotSupportedError, WevtutilNotFoundError, FileValidationError) as e:
        print(f"Error: {e}")

    print()


def example_4_inspect_results() -> None:
    """Inspect per-file results after a batch conversion."""
    print("=" * 70)
    print("Example 4: Inspect Results")
    print("=" * 70)

    source_dir = Path(r"C:\EventLogs")

    try:
        summary = batch_convert(source_dir, continue_on_error=True)
        if summary.failed == 0 and summary.skipped == 0:
            print("No failures or skips.")
            return

        print("\nNon-successful files:")
        for result in summary.results:
            if result.success:
                continue
            print(f"  - {result.status.value}: {result.input_file}")
            if result.error_message:
                print(f"    {result.error_message}")

    except (PlatformNotSupportedError, WevtutilNotFoundError, FileValidationError) as e:
        print(f"Error: {e}")

    print()


def main() -> None:
    """Entry point for running examples manually."""
    # Uncomment the examples you want to run.
    # example_1_simple_batch()
    # example_2_recursive_to_output_dir()
    # example_3_progress_callback()
    # example_4_inspect_results()
    print(
        "Uncomment an example in main() and run: python3 examples/batch_conversion.py"
    )


if __name__ == "__main__":
    main()
