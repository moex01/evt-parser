from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from evt_parser import CsvFormatter, parse_evt_file


def test_csv_output_has_no_metadata_header_lines() -> None:
    result = parse_evt_file(Path("test_files/Security.evt"))
    csv_text = CsvFormatter().format(result, include_metadata=True)
    assert not csv_text.startswith("#")


def test_csv_rows_match_valid_records_and_are_single_line_cells() -> None:
    result = parse_evt_file(Path("test_files/Security.evt"))
    csv_text = CsvFormatter().format(result)
    reader = csv.reader(StringIO(csv_text))
    header = next(reader)
    rows = list(reader)

    assert header[0] == "record_number"
    assert len(rows) == result.valid_records
    assert all(len(r) == len(header) for r in rows)

    for row in rows:
        for cell in row:
            assert "\n" not in cell
            assert "\r" not in cell
