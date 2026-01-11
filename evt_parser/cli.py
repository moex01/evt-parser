"""Command-line interface for the EVT converter and parser.

This module provides a user-friendly CLI tool for:
- Converting legacy Windows Event Log (.evt) files to .evtx format (Windows only)
- Parsing EVT files and exporting to JSON, XML, or CSV (cross-platform)
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional, Sequence

from .converter import convert_evt_to_evtx, batch_convert, ConversionStatus
from .parser import parse_evt_file
from .formatters import get_formatter
from .exceptions import (
    EvtConverterError,
    PlatformNotSupportedError,
    WevtutilNotFoundError,
    FileValidationError,
    ParserError,
    OutputFormatError,
)
from . import __version__


# Progress symbols
SYMBOL_SUCCESS = "[+]"
SYMBOL_FAILURE = "[X]"
SYMBOL_SKIPPED = "[-]"


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging based on verbosity level.

    Args:
        verbose: If True, enable DEBUG level logging.
        quiet: If True, suppress all logging except errors.
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level, format="%(levelname)s: %(message)s", stream=sys.stderr
    )


def progress_bar(current: int, total: int, file_path: Path, width: int = 40) -> None:
    """Display a simple progress bar for batch operations.

    Args:
        current: Current file number (1-indexed).
        total: Total number of files.
        file_path: Path of the current file being processed.
        width: Width of the progress bar in characters.
    """
    percent = (current / total) * 100 if total > 0 else 0
    filled = int(width * current / total) if total > 0 else 0
    bar = "=" * filled + "-" * (width - filled)

    # Print progress on same line using carriage return
    sys.stderr.write(f"\r[{bar}] {percent:.1f}% ({current}/{total}) {file_path.name}")
    sys.stderr.flush()

    # Print newline when complete
    if current == total:
        sys.stderr.write("\n")
        sys.stderr.flush()


def convert_single(
    input_file: str,
    output_file: Optional[str],
    force: bool,
    timeout: int,
    verbose: bool,
    auto_repair: bool = True,
) -> int:
    """Handle conversion of a single file.

    Args:
        input_file: Path to input .evt file.
        output_file: Path to output .evtx file (optional).
        force: Whether to overwrite existing files.
        timeout: Timeout in seconds for the conversion.
        verbose: Whether to show verbose output.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Converting {input_file}...")

        result = convert_evt_to_evtx(
            input_file=input_file,
            output_file=output_file,
            overwrite=force,
            timeout=timeout,
            auto_repair=auto_repair,
        )

        if result.success:
            duration_str = (
                f" ({result.duration_seconds:.2f}s)" if result.duration_seconds else ""
            )
            print(
                f"{SYMBOL_SUCCESS} Successfully converted to {result.output_file}{duration_str}"
            )
            if verbose:
                logger.debug(f"Input: {result.input_file}")
                logger.debug(f"Output: {result.output_file}")
            return 0
        elif result.status == ConversionStatus.SKIPPED:
            print(f"{SYMBOL_SKIPPED} Skipped: {result.error_message}")
            logger.warning(f"File skipped: {result.input_file}")
            return 0
        else:
            print(
                f"{SYMBOL_FAILURE} Conversion failed: {result.error_message}",
                file=sys.stderr,
            )
            logger.error(
                f"Failed to convert {result.input_file}: {result.error_message}"
            )
            return 1

    except PlatformNotSupportedError as e:
        print(f"{SYMBOL_FAILURE} Error: {e}", file=sys.stderr)
        logger.error("Platform not supported")
        return 1
    except WevtutilNotFoundError as e:
        print(f"{SYMBOL_FAILURE} Error: {e}", file=sys.stderr)
        logger.error("wevtutil not found")
        return 1
    except FileValidationError as e:
        print(f"{SYMBOL_FAILURE} Error: {e}", file=sys.stderr)
        logger.error(f"File validation failed: {e}")
        return 1
    except EvtConverterError as e:
        print(f"{SYMBOL_FAILURE} Error: {e}", file=sys.stderr)
        logger.error(f"Conversion error: {e}")
        return 1
    except Exception as e:
        print(f"{SYMBOL_FAILURE} Unexpected error: {e}", file=sys.stderr)
        logger.exception("Unexpected error during conversion")
        return 1


def convert_batch(
    batch_dir: str,
    output_dir: Optional[str],
    recursive: bool,
    force: bool,
    timeout: int,
    stop_on_error: bool,
    verbose: bool,
    quiet: bool,
    auto_repair: bool = True,
) -> int:
    """Handle batch conversion of multiple files.

    Args:
        batch_dir: Directory containing .evt files.
        output_dir: Output directory for .evtx files (optional).
        recursive: Whether to search subdirectories.
        force: Whether to overwrite existing files.
        timeout: Timeout in seconds per file.
        stop_on_error: Whether to stop on first error.
        verbose: Whether to show verbose output.
        quiet: Whether to suppress progress output.

    Returns:
        Exit code: 0 for complete success, 1 for complete failure, 2 for partial success.
    """
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Starting batch conversion from {batch_dir}")
        if recursive:
            logger.info("Recursive mode enabled")

        # Create progress callback unless in quiet mode
        progress_callback = None if quiet else progress_bar

        summary = batch_convert(
            source_dir=batch_dir,
            output_dir=output_dir,
            recursive=recursive,
            overwrite=force,
            timeout=timeout,
            continue_on_error=not stop_on_error,
            progress_callback=progress_callback,
            auto_repair=auto_repair,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("CONVERSION SUMMARY")
        print("=" * 60)
        print(f"Total files found:       {summary.total}")
        print(f"{SYMBOL_SUCCESS} Successfully converted: {summary.successful}")
        print(f"{SYMBOL_FAILURE} Failed:                 {summary.failed}")
        print(f"{SYMBOL_SKIPPED} Skipped:                {summary.skipped}")
        print(f"Success rate:            {summary.success_rate:.1f}%")
        print(f"Total duration:          {summary.total_duration_seconds:.2f}s")
        print("=" * 60)

        # Show details of failed conversions if any
        if summary.failed > 0 and verbose:
            print("\nFailed conversions:")
            for result in summary.results:
                if result.status == ConversionStatus.FAILED:
                    print(
                        f"  {SYMBOL_FAILURE} {result.input_file}: {result.error_message}"
                    )

        # Show details of skipped conversions if any
        if summary.skipped > 0 and verbose:
            print("\nSkipped conversions:")
            for result in summary.results:
                if result.status == ConversionStatus.SKIPPED:
                    print(
                        f"  {SYMBOL_SKIPPED} {result.input_file}: {result.error_message}"
                    )

        # Determine exit code
        if summary.total == 0:
            print("\nNo .evt files found in the specified directory.")
            return 1
        elif summary.failed == 0 and summary.skipped == 0:
            # Complete success
            return 0
        elif summary.successful == 0:
            # Complete failure
            return 1
        else:
            # Partial success
            return 2

    except PlatformNotSupportedError as e:
        print(f"{SYMBOL_FAILURE} Error: {e}", file=sys.stderr)
        logger.error("Platform not supported")
        return 1
    except WevtutilNotFoundError as e:
        print(f"{SYMBOL_FAILURE} Error: {e}", file=sys.stderr)
        logger.error("wevtutil not found")
        return 1
    except FileValidationError as e:
        print(f"{SYMBOL_FAILURE} Error: {e}", file=sys.stderr)
        logger.error(f"Directory validation failed: {e}")
        return 1
    except EvtConverterError as e:
        print(f"{SYMBOL_FAILURE} Error: {e}", file=sys.stderr)
        logger.error(f"Batch conversion error: {e}")
        return 1
    except Exception as e:
        print(f"{SYMBOL_FAILURE} Unexpected error: {e}", file=sys.stderr)
        logger.exception("Unexpected error during batch conversion")
        return 1


def parse_single(
    input_file: str,
    output_file: Optional[str],
    format_name: str,
    include_metadata: bool,
    verbose: bool,
) -> int:
    """Handle parsing of a single EVT file.

    Args:
        input_file: Path to input .evt file.
        output_file: Path to output file (optional, defaults to stdout).
        format_name: Output format (json, xml, csv).
        include_metadata: Whether to include file metadata in output.
        verbose: Whether to show verbose output.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    logger = logging.getLogger(__name__)

    try:
        input_path = Path(input_file)
        logger.info(f"Parsing {input_file}...")

        # Parse the EVT file
        result = parse_evt_file(input_path)

        if not result.success and result.valid_records == 0:
            print(
                f"{SYMBOL_FAILURE} No valid records found in {input_file}",
                file=sys.stderr,
            )
            return 1

        # Format output
        formatter = get_formatter(format_name)
        output = formatter.format(result, include_metadata=include_metadata)

        # Write output
        if output_file:
            output_path = Path(output_file)
            output_path.write_text(output, encoding="utf-8")
            print(
                f"{SYMBOL_SUCCESS} Parsed {result.valid_records} records to {output_path}"
            )
        else:
            print(output)

        if verbose:
            logger.info(f"Total records: {result.total_records}")
            logger.info(f"Valid records: {result.valid_records}")
            logger.info(f"Parse errors: {result.parse_errors}")
            logger.info(f"Duration: {result.parse_duration_seconds:.3f}s")

        return 0

    except FileValidationError as e:
        print(f"{SYMBOL_FAILURE} Error: {e}", file=sys.stderr)
        logger.error(f"File validation failed: {e}")
        return 1
    except ParserError as e:
        print(f"{SYMBOL_FAILURE} Parse error: {e}", file=sys.stderr)
        logger.error(f"Parser error: {e}")
        return 1
    except OutputFormatError as e:
        print(f"{SYMBOL_FAILURE} Format error: {e}", file=sys.stderr)
        logger.error(f"Output format error: {e}")
        return 1
    except Exception as e:
        print(f"{SYMBOL_FAILURE} Unexpected error: {e}", file=sys.stderr)
        logger.exception("Unexpected error during parsing")
        return 1


def parse_batch(
    batch_dir: str,
    output_dir: Optional[str],
    format_name: str,
    recursive: bool,
    include_metadata: bool,
    verbose: bool,
    quiet: bool,
) -> int:
    """Handle batch parsing of multiple EVT files.

    Args:
        batch_dir: Directory containing .evt files.
        output_dir: Output directory for formatted files.
        format_name: Output format (json, xml, csv).
        recursive: Whether to search subdirectories.
        include_metadata: Whether to include file metadata.
        verbose: Whether to show verbose output.
        quiet: Whether to suppress progress output.

    Returns:
        Exit code: 0 for complete success, 1 for failure, 2 for partial success.
    """
    logger = logging.getLogger(__name__)

    try:
        from .utils import find_evt_files

        logger.info(f"Starting batch parse from {batch_dir}")
        source_path = Path(batch_dir)

        if not source_path.is_dir():
            print(
                f"{SYMBOL_FAILURE} Error: {batch_dir} is not a directory",
                file=sys.stderr,
            )
            return 1

        evt_files = list(find_evt_files(source_path, recursive=recursive))
        total = len(evt_files)

        if total == 0:
            print(f"{SYMBOL_FAILURE} No .evt files found in {batch_dir}")
            return 1

        # Create output directory if specified
        out_path = Path(output_dir) if output_dir else None
        if out_path:
            out_path.mkdir(parents=True, exist_ok=True)

        formatter = get_formatter(format_name)
        ext = format_name.lower()

        successful = 0
        failed = 0

        for i, evt_file in enumerate(evt_files, 1):
            if not quiet:
                progress_bar(i, total, evt_file)

            try:
                result = parse_evt_file(evt_file)

                if result.valid_records > 0:
                    output = formatter.format(result, include_metadata=include_metadata)

                    # Determine output file path
                    if out_path:
                        out_file = out_path / f"{evt_file.stem}.{ext}"
                    else:
                        out_file = evt_file.with_suffix(f".{ext}")

                    out_file.write_text(output, encoding="utf-8")
                    successful += 1
                else:
                    failed += 1
                    if verbose:
                        logger.warning(f"No valid records in {evt_file}")

            except Exception as e:
                failed += 1
                if verbose:
                    logger.error(f"Failed to parse {evt_file}: {e}")

        # Print summary
        print("\n" + "=" * 60)
        print("PARSE SUMMARY")
        print("=" * 60)
        print(f"Total files found:       {total}")
        print(f"{SYMBOL_SUCCESS} Successfully parsed:    {successful}")
        print(f"{SYMBOL_FAILURE} Failed:                 {failed}")
        print(f"Output format:           {format_name.upper()}")
        print("=" * 60)

        if failed == 0:
            return 0
        elif successful == 0:
            return 1
        else:
            return 2

    except Exception as e:
        print(f"{SYMBOL_FAILURE} Unexpected error: {e}", file=sys.stderr)
        logger.exception("Unexpected error during batch parsing")
        return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main entry point for the CLI tool.

    Args:
        argv: Optional argument list to parse instead of sys.argv.

    Returns:
        Exit code: 0 for success, 1 for failure, 2 for partial success.
    """
    parser = argparse.ArgumentParser(
        prog="evt-parser",
        description="Convert and parse legacy Windows Event Log (.evt) files",
        epilog="""
Commands:
  parse     Parse EVT files to JSON/XML/CSV (cross-platform)
  convert   Convert EVT to EVTX format (Windows only)

Examples:
  # Parse EVT to JSON (cross-platform)
  %(prog)s parse Security.evt -o events.json
  %(prog)s parse Security.evt --format xml -o events.xml
  %(prog)s parse --batch C:\\Logs --format csv -O C:\\Output

  # Convert to EVTX (Windows only)
  %(prog)s convert System.evt
  %(prog)s convert System.evt -o Output.evtx
  %(prog)s convert --batch C:\\Logs -r -O C:\\Output
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ========== PARSE SUBCOMMAND ==========
    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse EVT files to JSON/XML/CSV (cross-platform)",
        description="Parse legacy Windows Event Log (.evt) files and export to various formats.",
        epilog="""
Examples:
  %(prog)s Security.evt                     # Parse to stdout as JSON
  %(prog)s Security.evt -o events.json      # Parse to file
  %(prog)s Security.evt --format xml        # Output as XML
  %(prog)s Security.evt --format csv        # Output as CSV
  %(prog)s --batch C:\\Logs -O C:\\Output    # Batch parse directory
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parse_parser.add_argument("input_file", nargs="?", help="Input .evt file to parse")

    parse_parser.add_argument(
        "-o", "--output", metavar="FILE", help="Output file path (default: stdout)"
    )

    parse_parser.add_argument(
        "-O", "--output-dir", metavar="DIR", help="Output directory for batch mode"
    )

    parse_parser.add_argument(
        "--format",
        "-F",
        choices=["json", "xml", "csv"],
        default="json",
        help="Output format (default: json)",
    )

    parse_parser.add_argument(
        "-b",
        "--batch",
        metavar="DIR",
        help="Batch mode: parse all .evt files in directory",
    )

    parse_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively search subdirectories in batch mode",
    )

    parse_parser.add_argument(
        "--no-metadata", action="store_true", help="Exclude file metadata from output"
    )

    parse_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    parse_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress output"
    )

    # ========== CONVERT SUBCOMMAND ==========
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert EVT to EVTX format (Windows only)",
        description="Convert legacy .evt files to modern .evtx format using wevtutil.",
        epilog="""
Examples:
  %(prog)s System.evt                       # Convert single file
  %(prog)s System.evt -o Output.evtx        # Custom output path
  %(prog)s --batch C:\\Logs -r              # Batch convert recursively
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    convert_parser.add_argument(
        "input_file", nargs="?", help="Input .evt file to convert"
    )

    convert_parser.add_argument(
        "-o", "--output", metavar="FILE", help="Output .evtx file path"
    )

    convert_parser.add_argument(
        "-O", "--output-dir", metavar="DIR", help="Output directory for batch mode"
    )

    convert_parser.add_argument(
        "-b",
        "--batch",
        metavar="DIR",
        help="Batch mode: convert all .evt files in directory",
    )

    convert_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively search subdirectories in batch mode",
    )

    convert_parser.add_argument(
        "-f", "--force", action="store_true", help="Overwrite existing output files"
    )

    convert_parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=60,
        metavar="SECONDS",
        help="Timeout per file (default: 60)",
    )

    convert_parser.add_argument(
        "--stop-on-error", action="store_true", help="Stop on first error in batch mode"
    )

    convert_parser.add_argument(
        "--no-auto-repair",
        action="store_true",
        help="Disable automatic repair of dirty EVT files",
    )

    convert_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    convert_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress output"
    )

    args = parser.parse_args(argv)

    # Setup logging
    verbose = getattr(args, "verbose", False)
    quiet = getattr(args, "quiet", False)
    setup_logging(verbose=verbose, quiet=quiet)

    if verbose and quiet:
        print("Error: Cannot use --verbose and --quiet together", file=sys.stderr)
        return 1

    # ========== PARSE COMMAND ==========
    if args.command == "parse":
        batch_dir = getattr(args, "batch", None)
        input_file = getattr(args, "input_file", None)

        if batch_dir and input_file:
            print("Error: Cannot specify both input file and --batch", file=sys.stderr)
            return 1

        if not batch_dir and not input_file:
            print("Error: Must specify input file or --batch", file=sys.stderr)
            parse_parser.print_help()
            return 1

        if args.output and batch_dir:
            print("Error: Use -O/--output-dir with --batch, not -o", file=sys.stderr)
            return 1

        if batch_dir:
            return parse_batch(
                batch_dir=batch_dir,
                output_dir=args.output_dir,
                format_name=args.format,
                recursive=args.recursive,
                include_metadata=not args.no_metadata,
                verbose=args.verbose,
                quiet=args.quiet,
            )
        else:
            assert isinstance(input_file, str)
            return parse_single(
                input_file=input_file,
                output_file=args.output,
                format_name=args.format,
                include_metadata=not args.no_metadata,
                verbose=args.verbose,
            )

    # ========== CONVERT COMMAND ==========
    batch_dir = getattr(args, "batch", None)
    input_file = getattr(args, "input_file", None)
    output_file = getattr(args, "output", None)
    output_dir = getattr(args, "output_dir", None)
    recursive = getattr(args, "recursive", False)
    force = getattr(args, "force", False)
    timeout = getattr(args, "timeout", 60)
    stop_on_error = getattr(args, "stop_on_error", False)
    no_auto_repair = getattr(args, "no_auto_repair", False)

    if batch_dir and input_file:
        print("Error: Cannot specify both input file and --batch", file=sys.stderr)
        return 1

    if not batch_dir and not input_file:
        # No command and no input - show help
        parser.print_help()
        return 1

    if output_file and batch_dir:
        print("Error: Use -O/--output-dir with --batch, not -o", file=sys.stderr)
        return 1

    if output_dir and not batch_dir:
        print("Error: -O/--output-dir requires --batch", file=sys.stderr)
        return 1

    if recursive and not batch_dir:
        print("Error: -r/--recursive requires --batch", file=sys.stderr)
        return 1

    if stop_on_error and not batch_dir:
        print("Error: --stop-on-error requires --batch", file=sys.stderr)
        return 1

    if timeout <= 0:
        print("Error: Timeout must be positive", file=sys.stderr)
        return 1

    if batch_dir:
        return convert_batch(
            batch_dir=batch_dir,
            output_dir=output_dir,
            recursive=recursive,
            force=force,
            timeout=timeout,
            stop_on_error=stop_on_error,
            verbose=verbose,
            quiet=quiet,
            auto_repair=not no_auto_repair,
        )
    else:
        assert isinstance(input_file, str)
        return convert_single(
            input_file=input_file,
            output_file=output_file,
            force=force,
            timeout=timeout,
            verbose=verbose,
            auto_repair=not no_auto_repair,
        )


if __name__ == "__main__":
    sys.exit(main())
