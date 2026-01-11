"""Output formatters for parsed EVT event records.

Supports JSON, XML, and CSV output formats with configurable options.
"""

import csv
import io
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TextIO, Union
from xml.etree import ElementTree as ET
from xml.dom import minidom

from .parser import EventRecord, ParseResult


class Formatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format(self, result: ParseResult, include_metadata: bool = True) -> str:
        """Format parse result to string."""
        pass

    @abstractmethod
    def format_records(self, records: List[EventRecord]) -> str:
        """Format records only (no metadata)."""
        pass

    def write(
        self,
        result: ParseResult,
        output: Union[Path, TextIO],
        include_metadata: bool = True,
    ) -> None:
        """Write formatted output to file or stream."""
        content = self.format(result, include_metadata)
        if isinstance(output, Path):
            output.write_text(content, encoding="utf-8")
        else:
            output.write(content)


class JsonFormatter(Formatter):
    """JSON output formatter."""

    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
        """Initialize JSON formatter.

        Args:
            indent: Indentation level (0 for compact).
            ensure_ascii: If True, escape non-ASCII characters.
        """
        self.indent = indent if indent > 0 else None
        self.ensure_ascii = ensure_ascii

    def format(self, result: ParseResult, include_metadata: bool = True) -> str:
        """Format parse result as JSON."""
        output: Dict[str, Any] = {}

        if include_metadata:
            output["metadata"] = {
                "source_file": str(result.source_file),
                "total_records": result.total_records,
                "valid_records": result.valid_records,
                "parse_errors": result.parse_errors,
                "parse_duration_seconds": round(result.parse_duration_seconds, 3),
                "header": {
                    "major_version": result.header.major_version,
                    "minor_version": result.header.minor_version,
                    "is_dirty": result.header.is_dirty,
                    "is_wrapped": result.header.is_wrapped,
                    "max_size": result.header.max_size,
                },
            }
            if result.errors:
                output["metadata"]["errors"] = result.errors

        output["records"] = [r.to_dict() for r in result.records]

        return json.dumps(
            output,
            indent=self.indent,
            ensure_ascii=self.ensure_ascii,
            default=self._json_default,
        )

    def format_records(self, records: List[EventRecord]) -> str:
        """Format records only as JSON array."""
        return json.dumps(
            [r.to_dict() for r in records],
            indent=self.indent,
            ensure_ascii=self.ensure_ascii,
            default=self._json_default,
        )

    @staticmethod
    def _json_default(obj: Any) -> Any:
        """Handle non-serializable types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.hex()
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class XmlFormatter(Formatter):
    """XML output formatter."""

    def __init__(self, pretty: bool = True, encoding: str = "utf-8"):
        """Initialize XML formatter.

        Args:
            pretty: If True, output pretty-printed XML.
            encoding: XML encoding declaration.
        """
        self.pretty = pretty
        self.encoding = encoding

    def format(self, result: ParseResult, include_metadata: bool = True) -> str:
        """Format parse result as XML."""
        root = ET.Element("EventLog")

        if include_metadata:
            meta = ET.SubElement(root, "Metadata")
            ET.SubElement(meta, "SourceFile").text = str(result.source_file)
            ET.SubElement(meta, "TotalRecords").text = str(result.total_records)
            ET.SubElement(meta, "ValidRecords").text = str(result.valid_records)
            ET.SubElement(meta, "ParseErrors").text = str(result.parse_errors)
            ET.SubElement(meta, "ParseDuration").text = (
                f"{result.parse_duration_seconds:.3f}"
            )

            header = ET.SubElement(meta, "Header")
            ET.SubElement(header, "MajorVersion").text = str(
                result.header.major_version
            )
            ET.SubElement(header, "MinorVersion").text = str(
                result.header.minor_version
            )
            ET.SubElement(header, "IsDirty").text = str(result.header.is_dirty).lower()
            ET.SubElement(header, "IsWrapped").text = str(
                result.header.is_wrapped
            ).lower()

            if result.errors:
                errors = ET.SubElement(meta, "Errors")
                for error in result.errors:
                    ET.SubElement(errors, "Error").text = error

        events = ET.SubElement(root, "Events")
        for record in result.records:
            self._add_event_element(events, record)

        return self._to_string(root)

    def format_records(self, records: List[EventRecord]) -> str:
        """Format records only as XML."""
        root = ET.Element("Events")
        for record in records:
            self._add_event_element(root, record)
        return self._to_string(root)

    def _add_event_element(self, parent: ET.Element, record: EventRecord) -> None:
        """Add an event record as XML element."""
        event = ET.SubElement(parent, "Event")
        event.set("RecordNumber", str(record.record_number))

        ET.SubElement(event, "TimeGenerated").text = (
            record.time_generated.isoformat() if record.time_generated else ""
        )
        ET.SubElement(event, "TimeWritten").text = (
            record.time_written.isoformat() if record.time_written else ""
        )
        ET.SubElement(event, "EventID").text = str(record.event_id)
        ET.SubElement(event, "EventType").text = record.event_type
        ET.SubElement(event, "EventCategory").text = str(record.event_category)
        ET.SubElement(event, "Source").text = record.source
        ET.SubElement(event, "ComputerName").text = record.computer_name

        if record.user_sid:
            ET.SubElement(event, "UserSID").text = record.user_sid

        if record.strings:
            strings = ET.SubElement(event, "Strings")
            for i, s in enumerate(record.strings):
                string_elem = ET.SubElement(strings, "String")
                string_elem.set("Index", str(i))
                string_elem.text = s

        if record.data:
            ET.SubElement(event, "Data").text = record.data.hex()

    def _to_string(self, root: ET.Element) -> str:
        """Convert XML element to string."""
        if self.pretty:
            xml_str = ET.tostring(root, encoding="unicode")
            parsed = minidom.parseString(xml_str)
            pretty_xml = parsed.toprettyxml(indent="  ")
            # Remove extra blank lines
            lines = [line for line in pretty_xml.split("\n") if line.strip()]
            return "\n".join(lines)
        else:
            return ET.tostring(root, encoding="unicode")


class CsvFormatter(Formatter):
    """CSV output formatter."""

    DEFAULT_COLUMNS = [
        "record_number",
        "time_generated",
        "time_written",
        "event_id",
        "event_type",
        "event_category",
        "source",
        "computer_name",
        "user_sid",
        "strings",
        "data",
    ]

    def __init__(
        self,
        delimiter: str = ",",
        columns: Optional[List[str]] = None,
        include_header: bool = True,
    ):
        """Initialize CSV formatter.

        Args:
            delimiter: Field delimiter character.
            columns: List of columns to include (default: all).
            include_header: If True, include header row.
        """
        self.delimiter = delimiter
        self.columns = columns or self.DEFAULT_COLUMNS
        self.include_header = include_header

    def format(self, result: ParseResult, include_metadata: bool = True) -> str:
        """Format parse result as CSV.

        Note: For maximum compatibility with CSV consumers (including spreadsheet
        imports), this output intentionally avoids comment-style metadata headers and
        ensures that fields do not contain literal newlines.
        """
        output = io.StringIO()

        self._write_records(output, result.records)
        return output.getvalue()

    def format_records(self, records: List[EventRecord]) -> str:
        """Format records only as CSV."""
        output = io.StringIO()
        self._write_records(output, records)
        return output.getvalue()

    def _write_records(self, output: TextIO, records: List[EventRecord]) -> None:
        """Write records to CSV output."""
        writer = csv.writer(output, delimiter=self.delimiter)

        if self.include_header:
            writer.writerow(self.columns)

        for record in records:
            row = []
            record_dict = record.to_dict()
            for col in self.columns:
                value = record_dict.get(col, "")
                if col == "strings" and isinstance(value, list):
                    value = json.dumps(value, ensure_ascii=False)
                elif value is None:
                    value = ""
                elif isinstance(value, str):
                    value = self._sanitize_csv_cell(value)
                row.append(value)
            writer.writerow(row)

    @staticmethod
    def _sanitize_csv_cell(value: str) -> str:
        """Make a value safe for strict CSV consumers.

        - Avoid literal newlines/tabs within cells (some importers mis-handle them).
        - Preserve meaning by using escape sequences.
        """
        if not value:
            return value

        value = value.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
        value = value.replace("\t", "\\t")

        sanitized: list[str] = []
        for ch in value:
            code = ord(ch)
            if code < 0x20:
                sanitized.append(f"\\x{code:02x}")
            else:
                sanitized.append(ch)
        return "".join(sanitized)


def get_formatter(format_name: str, **kwargs: Any) -> Formatter:
    """Get a formatter instance by name.

    Args:
        format_name: One of 'json', 'xml', 'csv'.
        **kwargs: Formatter-specific options.

    Returns:
        Formatter instance.

    Raises:
        ValueError: If format_name is not recognized.
    """
    formatters: Dict[str, Callable[..., Formatter]] = {
        "json": JsonFormatter,
        "xml": XmlFormatter,
        "csv": CsvFormatter,
    }

    format_lower = format_name.lower()
    if format_lower not in formatters:
        raise ValueError(
            f"Unknown format: {format_name}. Available: {list(formatters.keys())}"
        )

    return formatters[format_lower](**kwargs)
