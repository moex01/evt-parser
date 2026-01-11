"""Native EVT file parser for legacy Windows Event Log files.

This module provides cross-platform parsing of legacy Windows EVT files
(Windows 2000/XP/2003) without requiring wevtutil or Windows.

The EVT format consists of:
- Header (48 bytes) with file metadata
- Event records (variable length, each starts with size + "LfLe" signature)
- EOF record (40 bytes with 0x11111111... signature)

Based on the EVT format specification from libevt:
https://github.com/libyal/libevt/blob/main/documentation/Windows%20Event%20Log%20(EVT)%20format.asciidoc
"""

from __future__ import annotations

import base64
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
import mmap
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from .exceptions import FileValidationError


# EVT Header constants
EVT_HEADER_SIZE = 48
EVENTLOGRECORD_HEADER_SIZE = 56
EVT_SIGNATURE = b"LfLe"
EVT_SIGNATURE_OFFSET = 0x04
EVT_EOF_SIGNATURE = bytes.fromhex("11111111222222223333333344444444")

# Event type mappings
EVENT_TYPE_MAP = {
    1: "error",
    2: "warning",
    4: "information",
    8: "audit_success",
    16: "audit_failure",
}


@dataclass
class EvtHeader:
    """Parsed EVT file header."""

    header_size: int
    signature: bytes
    major_version: int
    minor_version: int
    start_offset: int
    end_offset: int
    current_record_number: int
    oldest_record_number: int
    max_size: int
    flags: int
    retention: int
    header_size_copy: int

    @property
    def is_dirty(self) -> bool:
        return bool(self.flags & 0x01)

    @property
    def is_wrapped(self) -> bool:
        return bool(self.flags & 0x02)


@dataclass
class EventRecord:
    """Parsed event record from an EVT file."""

    record_number: int
    time_generated: Optional[datetime]
    time_written: Optional[datetime]
    event_id: int
    event_type: str
    event_type_raw: int
    event_category: int
    source: str
    computer_name: str
    user_sid: Optional[str]
    strings: List[str]
    data: Optional[bytes]
    raw_record: bytes = field(repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "record_number": self.record_number,
            "time_generated": (
                self.time_generated.isoformat() if self.time_generated else None
            ),
            "time_written": (
                self.time_written.isoformat() if self.time_written else None
            ),
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_category": self.event_category,
            "source": self.source,
            "computer_name": self.computer_name,
            "user_sid": self.user_sid,
            "strings": self.strings,
            "data": base64.b64encode(self.data).decode("ascii") if self.data else None,
        }


@dataclass
class ParseResult:
    """Result of parsing an EVT file."""

    source_file: Path
    header: EvtHeader
    records: List[EventRecord]
    total_records: int
    valid_records: int
    parse_errors: int
    parse_duration_seconds: float
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.valid_records > 0 or self.total_records == 0


def _parse_header(data: bytes) -> EvtHeader:
    """Parse the EVT file header (48 bytes)."""
    if len(data) < EVT_HEADER_SIZE:
        raise FileValidationError(f"File too small for EVT header: {len(data)} bytes")

    header_size = struct.unpack("<I", data[0:4])[0]
    signature = data[4:8]
    major_version = struct.unpack("<I", data[8:12])[0]
    minor_version = struct.unpack("<I", data[12:16])[0]
    start_offset = struct.unpack("<I", data[16:20])[0]
    end_offset = struct.unpack("<I", data[20:24])[0]
    current_record_number = struct.unpack("<I", data[24:28])[0]
    oldest_record_number = struct.unpack("<I", data[28:32])[0]
    max_size = struct.unpack("<I", data[32:36])[0]
    flags = struct.unpack("<I", data[36:40])[0]
    retention = struct.unpack("<I", data[40:44])[0]
    header_size_copy = struct.unpack("<I", data[44:48])[0]

    if signature != EVT_SIGNATURE:
        raise FileValidationError(
            f"Invalid EVT signature: {signature!r}, expected {EVT_SIGNATURE!r}"
        )

    return EvtHeader(
        header_size=header_size,
        signature=signature,
        major_version=major_version,
        minor_version=minor_version,
        start_offset=start_offset,
        end_offset=end_offset,
        current_record_number=current_record_number,
        oldest_record_number=oldest_record_number,
        max_size=max_size,
        flags=flags,
        retention=retention,
        header_size_copy=header_size_copy,
    )


def _unix_to_datetime(timestamp: int) -> Optional[datetime]:
    """Convert Unix timestamp to datetime, handling edge cases."""
    if timestamp == 0:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def _read_null_terminated_utf16(
    data: bytes, offset: int, max_len: int = 1024
) -> tuple[str, int]:
    """Read a null-terminated UTF-16LE string from data."""
    end = offset
    while end < min(offset + max_len, len(data) - 1):
        if data[end] == 0 and data[end + 1] == 0:
            break
        end += 2

    try:
        string = data[offset:end].decode("utf-16-le")
    except UnicodeDecodeError:
        string = data[offset:end].decode("utf-16-le", errors="replace")

    return string, end + 2


def _parse_sid(data: bytes) -> Optional[str]:
    """Parse a Windows SID from binary data."""
    if not data or len(data) < 8:
        return None

    try:
        revision = data[0]
        sub_auth_count = data[1]

        if len(data) < 8 + sub_auth_count * 4:
            return None

        # 6-byte identifier authority (big-endian)
        id_auth = int.from_bytes(data[2:8], "big")

        # Sub-authorities (little-endian)
        sub_auths = []
        for i in range(sub_auth_count):
            offset = 8 + i * 4
            sub_auth = struct.unpack("<I", data[offset : offset + 4])[0]
            sub_auths.append(str(sub_auth))

        return f"S-{revision}-{id_auth}-" + "-".join(sub_auths)
    except Exception:
        return None


def _parse_event_record(
    data: Union[bytes, mmap.mmap], offset: int
) -> tuple[Optional[EventRecord], int, Optional[str]]:
    """Parse a single event record from the data.

    Returns: (record, next_offset, error_message)
    """
    if offset + 8 > len(data):
        return None, offset, "Insufficient data for record header"

    # Read record size and signature
    record_size = struct.unpack("<I", data[offset : offset + 4])[0]
    signature = data[offset + 4 : offset + 8]

    # Check for EOF record
    if signature == EVT_EOF_SIGNATURE[:4]:
        return None, offset + 40, None  # EOF record is 40 bytes

    # Validate record
    if signature != EVT_SIGNATURE:
        return (
            None,
            offset + 4,
            f"Invalid record signature at offset {offset}: {signature.hex()}",
        )

    if record_size < EVENTLOGRECORD_HEADER_SIZE or record_size > 65536:
        return (
            None,
            offset + 4,
            f"Invalid record size at offset {offset}: {record_size}",
        )

    if offset + record_size > len(data):
        return None, len(data), f"Record extends past end of file at offset {offset}"

    raw_record = data[offset : offset + record_size]

    try:
        record_number = struct.unpack("<I", raw_record[8:12])[0]
        time_generated = struct.unpack("<I", raw_record[12:16])[0]
        time_written = struct.unpack("<I", raw_record[16:20])[0]

        event_id_dword = struct.unpack("<I", raw_record[20:24])[0]
        event_id = event_id_dword & 0xFFFF

        event_type_raw = struct.unpack("<H", raw_record[24:26])[0]
        num_strings = struct.unpack("<H", raw_record[26:28])[0]
        event_category = struct.unpack("<H", raw_record[28:30])[0]
        string_offset = struct.unpack("<I", raw_record[36:40])[0]
        user_sid_length = struct.unpack("<I", raw_record[40:44])[0]
        user_sid_offset = struct.unpack("<I", raw_record[44:48])[0]
        data_length = struct.unpack("<I", raw_record[48:52])[0]
        data_offset = struct.unpack("<I", raw_record[52:56])[0]

        # Parse source name and computer name (immediately after fixed header)
        var_offset = EVENTLOGRECORD_HEADER_SIZE
        source_name, var_offset = _read_null_terminated_utf16(raw_record, var_offset)
        computer_name, var_offset = _read_null_terminated_utf16(raw_record, var_offset)

        # Parse SID if present
        user_sid = None
        if (
            user_sid_length > 0
            and user_sid_offset > 0
            and user_sid_offset + user_sid_length <= record_size
        ):
            sid_data = raw_record[user_sid_offset : user_sid_offset + user_sid_length]
            user_sid = _parse_sid(sid_data)

        # Parse strings
        strings = []
        if num_strings > 0 and string_offset > 0 and string_offset < record_size:
            str_pos = string_offset
            for _ in range(num_strings):
                if str_pos >= record_size:
                    break
                s, str_pos = _read_null_terminated_utf16(
                    raw_record, str_pos, record_size - str_pos
                )
                strings.append(s)

        # Parse data
        event_data = None
        if (
            data_length > 0
            and data_offset > 0
            and data_offset + data_length <= record_size
        ):
            event_data = raw_record[data_offset : data_offset + data_length]

        event_type = EVENT_TYPE_MAP.get(event_type_raw, f"unknown_{event_type_raw}")

        record = EventRecord(
            record_number=record_number,
            time_generated=_unix_to_datetime(time_generated),
            time_written=_unix_to_datetime(time_written),
            event_id=event_id,
            event_type=event_type,
            event_type_raw=event_type_raw,
            event_category=event_category,
            source=source_name,
            computer_name=computer_name,
            user_sid=user_sid,
            strings=strings,
            data=event_data,
            raw_record=raw_record,
        )

        return record, offset + record_size, None

    except Exception as e:
        return (
            None,
            offset + record_size,
            f"Error parsing record at offset {offset}: {e}",
        )


def parse_evt_file(input_file: Union[str, Path]) -> ParseResult:
    """Parse an EVT file and extract all event records.

    Args:
        input_file: Path to the EVT file to parse.

    Returns:
        ParseResult with header, records, and statistics.

    Raises:
        FileValidationError: If the file cannot be read or has invalid format.
    """
    input_path = Path(input_file)

    if not input_path.exists():
        raise FileValidationError(f"File not found: {input_path}")

    start_time = time.time()
    errors = []
    records = []

    with input_path.open("rb") as f:
        data = f.read()

    if len(data) < EVT_HEADER_SIZE:
        raise FileValidationError(f"File too small to be valid EVT: {len(data)} bytes")

    # Parse header
    header = _parse_header(data)

    # Parse records starting from start_offset
    offset = header.start_offset
    record_count = 0

    while offset < len(data) - 8:  # Need at least 8 bytes for record header
        # Check for EOF signature
        if data[offset + 4 : offset + 8] == EVT_EOF_SIGNATURE[:4]:
            break

        # Check for LfLe signature
        if data[offset + 4 : offset + 8] != EVT_SIGNATURE:
            # Try to find next record
            next_lfle = data.find(EVT_SIGNATURE, offset + 4)
            if next_lfle == -1:
                break
            offset = next_lfle - 4
            continue

        record, next_offset, error = _parse_event_record(data, offset)
        record_count += 1

        if error:
            errors.append(error)

        if record:
            records.append(record)

        if next_offset <= offset:
            break
        offset = next_offset

    duration = time.time() - start_time

    return ParseResult(
        source_file=input_path,
        header=header,
        records=records,
        total_records=record_count,
        valid_records=len(records),
        parse_errors=len(errors),
        parse_duration_seconds=duration,
        errors=errors,
    )


def iter_evt_records(input_file: Union[str, Path]) -> Iterator[EventRecord]:
    """Iterate over EVT records without building a full result list.

    This uses a read-only memory map for efficient access to large EVT files while
    avoiding the overhead of reading the entire file into a Python `bytes`.
    """
    input_path = Path(input_file)

    if not input_path.exists():
        raise FileValidationError(f"File not found: {input_path}")

    file_size = input_path.stat().st_size
    if file_size < EVT_HEADER_SIZE:
        raise FileValidationError(f"File too small to be valid EVT: {file_size} bytes")

    with input_path.open("rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            header = _parse_header(mm[:EVT_HEADER_SIZE])
            offset = header.start_offset

            while offset < len(mm) - 8:
                if mm[offset + 4 : offset + 8] == EVT_EOF_SIGNATURE[:4]:
                    break

                if mm[offset + 4 : offset + 8] != EVT_SIGNATURE:
                    next_lfle = mm.find(EVT_SIGNATURE, offset + 4)
                    if next_lfle == -1:
                        break
                    offset = next_lfle - 4
                    continue

                record, next_offset, _error = _parse_event_record(mm, offset)
                if record:
                    yield record

                if next_offset <= offset:
                    break
                offset = next_offset
