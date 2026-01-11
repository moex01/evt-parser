#!/usr/bin/env python3
"""
Comprehensive Test Script for EVT to EVTX Converter

This script tests all functionality of the converter to ensure it works correctly.
Run this on a Windows system with wevtutil available.

Usage:
    python scripts/windows_smoketest.py [path_to_evt_file]

If no path is provided, tests will be limited to validation checks only.
"""

import sys
import platform
from pathlib import Path

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text):
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_success(text):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text):
    """Print warning message."""
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_info(text):
    """Print info message."""
    print(f"{BLUE}ℹ {text}{RESET}")


def test_platform():
    """Test 1: Verify we're on Windows."""
    print_header("Test 1: Platform Check")

    current_platform = platform.system()
    print_info(f"Detected platform: {current_platform}")

    if current_platform == "Windows":
        print_success("Platform check passed - running on Windows")
        return True
    else:
        print_error(
            f"Platform check failed - this tool requires Windows, found {current_platform}"
        )
        print_warning("The converter will not work on non-Windows systems")
        return False


def test_imports():
    """Test 2: Verify package can be imported."""
    print_header("Test 2: Package Import Test")

    try:
        print_info("Attempting to import evt_parser package...")
        import evt_parser

        print_success(f"Successfully imported evt_parser v{evt_parser.__version__}")

        print_info("Checking exported functions...")
        for name in ("convert_evt_to_evtx", "batch_convert", "parse_evt_file"):
            if hasattr(evt_parser, name):
                print_success(f"Found evt_parser.{name}()")
            else:
                print_error(f"Missing evt_parser.{name}()")
                return False

        print_info("Checking exception classes...")
        import evt_parser.exceptions as exc

        for name in (
            "EvtConverterError",
            "PlatformNotSupportedError",
            "WevtutilNotFoundError",
            "FileValidationError",
            "ConversionError",
        ):
            if hasattr(exc, name):
                print_success(f"Found exceptions.{name}")
            else:
                print_error(f"Missing exceptions.{name}")
                return False

        return True

    except ImportError as e:
        print_error(f"Import failed: {e}")
        print_warning("Make sure the package is installed:")
        print_warning("  pip install -e .")
        return False


def test_wevtutil():
    """Test 3: Check if wevtutil is available."""
    print_header("Test 3: Wevtutil Availability Check")

    try:
        from evt_parser.utils import check_wevtutil_available

        print_info("Checking if wevtutil command is available...")
        check_wevtutil_available()
        print_success("wevtutil command found and available")
        return True

    except Exception as e:
        print_error(f"wevtutil check failed: {e}")
        print_warning("wevtutil is required and comes with Windows Vista or later")
        return False


def test_file_validation():
    """Test 4: Test file validation logic."""
    print_header("Test 4: File Validation Tests")

    try:
        from evt_parser.utils import validate_evt_file
        from evt_parser.exceptions import FileValidationError

        # Test 1: Non-existent file
        print_info("Test 4.1: Validating non-existent file (should fail)...")
        try:
            validate_evt_file(Path("nonexistent.evt"))
            print_error("Validation should have failed for non-existent file")
            return False
        except FileValidationError:
            print_success("Correctly rejected non-existent file")

        # Test 2: Wrong extension
        print_info("Test 4.2: Validating file with wrong extension (should fail)...")
        # Create a temporary file
        temp_file = Path("temp_test.txt")
        temp_file.write_text("test")
        try:
            validate_evt_file(temp_file)
            print_error("Validation should have failed for wrong extension")
            temp_file.unlink()
            return False
        except FileValidationError:
            print_success("Correctly rejected file with wrong extension")
        finally:
            if temp_file.exists():
                temp_file.unlink()

        print_success("File validation logic works correctly")
        return True

    except Exception as e:
        print_error(f"File validation test failed: {e}")
        return False


def test_path_generation():
    """Test 5: Test output path generation."""
    print_header("Test 5: Output Path Generation Tests")

    try:
        from evt_parser.utils import generate_output_path

        # Test auto-generation
        print_info("Test 5.1: Auto-generate output path...")
        input_path = Path("C:/Logs/System.evt")
        output_path = generate_output_path(input_path)

        expected = Path("C:/Logs/System.evtx")
        if output_path == expected:
            print_success(f"Correctly generated: {output_path}")
        else:
            print_error(f"Expected {expected}, got {output_path}")
            return False

        # Test with custom output directory
        print_info("Test 5.2: Generate path with custom output directory...")
        output_path = generate_output_path(input_path, Path("C:/Output"))

        expected = Path("C:/Output/System.evtx")
        if output_path == expected:
            print_success(f"Correctly generated: {output_path}")
        else:
            print_error(f"Expected {expected}, got {output_path}")
            return False

        print_success("Path generation logic works correctly")
        return True

    except Exception as e:
        print_error(f"Path generation test failed: {e}")
        return False


def test_single_conversion(evt_file):
    """Test 6: Test actual single file conversion."""
    print_header("Test 6: Single File Conversion Test")

    try:
        from evt_parser import convert_evt_to_evtx

        input_path = Path(evt_file)

        if not input_path.exists():
            print_warning(f"Test file not found: {input_path}")
            print_info(
                "Skipping conversion test - provide a valid .evt file as argument"
            )
            return None

        print_info(f"Converting: {input_path}")
        print_info(f"File size: {input_path.stat().st_size:,} bytes")

        result = convert_evt_to_evtx(input_path, timeout=120)

        if result.success:
            print_success("Conversion succeeded!")
            print_success(f"  Output file: {result.output_file}")
            print_success(f"  Duration: {result.duration_seconds:.2f} seconds")

            if result.output_file and result.output_file.exists():
                output_size = result.output_file.stat().st_size
                print_success(f"  Output size: {output_size:,} bytes")

                input_size = input_path.stat().st_size
                ratio = output_size / input_size if input_size > 0 else 0
                print_info(f"  Size ratio: {ratio:.2f}x")

            return True
        else:
            print_error(f"Conversion failed: {result.error_message}")
            if result.duration_seconds:
                print_info(f"  Failed after: {result.duration_seconds:.2f} seconds")
            return False

    except Exception as e:
        print_error(f"Conversion test failed with exception: {e}")
        import traceback

        print_error(traceback.format_exc())
        return False


def test_batch_find():
    """Test 7: Test finding .evt files in directory."""
    print_header("Test 7: Batch File Discovery Test")

    try:
        from evt_parser.utils import find_evt_files

        test_dir = Path("test_files")

        if not test_dir.exists():
            print_warning(f"Test directory not found: {test_dir}")
            print_info("Skipping batch discovery test")
            return None

        print_info(f"Scanning directory: {test_dir}")
        evt_files = find_evt_files(test_dir, recursive=False)

        print_info(f"Found {len(evt_files)} .evt file(s):")
        for f in evt_files:
            print_info(f"  - {f.name} ({f.stat().st_size:,} bytes)")

        if len(evt_files) > 0:
            print_success("File discovery works correctly")
            return True
        else:
            print_warning("No .evt files found in test directory")
            return None

    except Exception as e:
        print_error(f"Batch discovery test failed: {e}")
        return False


def test_cli():
    """Test 8: Test CLI interface."""
    print_header("Test 8: CLI Interface Test")

    try:
        from evt_parser.cli import main
        import sys
        from io import StringIO

        print_info("Testing CLI --help flag...")

        # Capture stdout
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()

        try:
            # Test --help (should exit with 0)
            try:
                main(["--help"])
            except SystemExit as e:
                if e.code == 0:
                    print_success("CLI --help works correctly")
                else:
                    print_error(f"CLI --help exited with code {e.code}")
                    return False
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        print_info("Testing CLI --version flag...")
        sys.stdout = StringIO()
        sys.stderr = StringIO()

        try:
            try:
                main(["--version"])
            except SystemExit as e:
                if e.code == 0:
                    print_success("CLI --version works correctly")
                else:
                    print_error(f"CLI --version exited with code {e.code}")
                    return False
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        print_success("CLI interface works correctly")
        return True

    except Exception as e:
        print_error(f"CLI test failed: {e}")
        return False


def main():
    """Run all tests."""
    print(f"\n{BOLD}EVT to EVTX Converter - Comprehensive Test Suite{RESET}")
    print(
        f"{BOLD}Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}{RESET}"
    )

    # Get test file from command line if provided
    evt_test_file = sys.argv[1] if len(sys.argv) > 1 else "test_files/test.evt"

    results = {}

    # Run all tests
    results["platform"] = test_platform()
    results["imports"] = test_imports()
    results["wevtutil"] = test_wevtutil()
    results["validation"] = test_file_validation()
    results["path_generation"] = test_path_generation()
    results["conversion"] = test_single_conversion(evt_test_file)
    results["batch_discovery"] = test_batch_find()
    results["cli"] = test_cli()

    # Summary
    print_header("Test Summary")

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    total = len(results)

    print(f"\n{BOLD}Results:{RESET}")
    print(f"  {GREEN}Passed:  {passed}/{total}{RESET}")
    print(f"  {RED}Failed:  {failed}/{total}{RESET}")
    print(f"  {YELLOW}Skipped: {skipped}/{total}{RESET}")

    if failed == 0:
        print(f"\n{GREEN}{BOLD}All tests passed! ✓{RESET}")
        print("\nThe converter is ready for use in your incident response workflow.")

        if skipped > 0:
            print(f"\n{YELLOW}Note: {skipped} test(s) were skipped.{RESET}")
            print("To run complete tests, provide a .evt file:")
            print("  python scripts/windows_smoketest.py path/to/file.evt")

        return 0
    else:
        print(f"\n{RED}{BOLD}{failed} test(s) failed! ✗{RESET}")
        print("\nPlease review the failed tests above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
