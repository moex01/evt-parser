"""EVT to EVTX Converter - A Python library for Windows Event Log processing.

This library provides functionality to:
- Convert legacy Windows Event Log (.evt) files to modern (.evtx) format
- Parse EVT files natively (cross-platform, no wevtutil required)
- Export parsed events to JSON, XML, or CSV formats

The library offers:
- Single file conversion with automatic output path generation
- Batch conversion with recursive directory scanning
- Native EVT parsing without Windows dependencies
- Multiple output formats (JSON, XML, CSV)
- Comprehensive error handling and validation
- Progress tracking for batch operations
- Zero external dependencies (Python standard library only)

Basic Usage:
    Single file conversion (Windows only):
        >>> from evt_parser import convert_evt_to_evtx
        >>> result = convert_evt_to_evtx("System.evt")
        >>> if result.success:
        ...     print(f"Converted to {result.output_file}")

    Native EVT parsing (cross-platform):
        >>> from evt_parser import parse_evt_file, JsonFormatter
        >>> result = parse_evt_file("Security.evt")
        >>> print(f"Parsed {result.valid_records} events")
        >>> formatter = JsonFormatter()
        >>> json_output = formatter.format(result)

    Batch conversion:
        >>> from evt_parser import batch_convert
        >>> summary = batch_convert("C:/Logs", recursive=True)
        >>> print(f"Converted {summary.successful}/{summary.total} files")

Platform Requirements:
    - EVTX conversion: Windows Vista or later (uses native wevtutil tool)
    - EVT parsing: Cross-platform (Python 3.8+)

For more information, see the documentation for individual functions and classes.
"""

from .converter import (
    ConversionStatus,
    ConversionResult,
    BatchConversionSummary,
    convert_evt_to_evtx,
    batch_convert,
)

from .exceptions import (
    EvtConverterError,
    PlatformNotSupportedError,
    WevtutilNotFoundError,
    FileValidationError,
    EvtDirtyFlagError,
    ConversionError,
    ParserError,
    CorruptedEvtError,
    OutputFormatError,
)

from .parser import (
    EvtHeader,
    EventRecord,
    ParseResult,
    parse_evt_file,
    iter_evt_records,
)

from .formatters import (
    Formatter,
    JsonFormatter,
    XmlFormatter,
    CsvFormatter,
    get_formatter,
)

from .utils import (
    check_platform,
    check_wevtutil_available,
    validate_legacy_evt_signature,
    validate_evt_file,
    generate_output_path,
    find_evt_files,
    is_evt_dirty,
    repair_dirty_evt,
)

__version__ = "1.0.0"
__author__ = "moex01"
__license__ = "MIT"

__all__ = [
    # Main conversion functions
    "convert_evt_to_evtx",
    "batch_convert",
    # Native EVT parser
    "EvtHeader",
    "EventRecord",
    "ParseResult",
    "parse_evt_file",
    "iter_evt_records",
    # Output formatters
    "Formatter",
    "JsonFormatter",
    "XmlFormatter",
    "CsvFormatter",
    "get_formatter",
    # Data classes and enums
    "ConversionStatus",
    "ConversionResult",
    "BatchConversionSummary",
    # Exceptions
    "EvtConverterError",
    "PlatformNotSupportedError",
    "WevtutilNotFoundError",
    "FileValidationError",
    "EvtDirtyFlagError",
    "ConversionError",
    "ParserError",
    "CorruptedEvtError",
    "OutputFormatError",
    # Utility functions
    "check_platform",
    "check_wevtutil_available",
    "validate_legacy_evt_signature",
    "validate_evt_file",
    "generate_output_path",
    "find_evt_files",
    "is_evt_dirty",
    "repair_dirty_evt",
    # Metadata
    "__version__",
    "__author__",
    "__license__",
]
