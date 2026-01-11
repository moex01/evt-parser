# EVT Parser

Command-line tool for parsing legacy Windows Event Log (`.evt`) files (e.g., Windows XP/2003).

## Features

- **Parse EVT files** to JSON, XML, or CSV (cross-platform)
- **Convert EVT to EVTX** format (Windows only, uses wevtutil)
- **Batch processing** with recursive directory scanning
- **Auto-repair** dirty EVT files copied from live systems
- Zero external dependencies

## Quickstart

```bash
git clone https://github.com/moex01/evt-parser.git
cd evt-parser
python -m pip install .

# Parse a bundled sample file
evt-parser parse test_files/Security.evt -o Security.json
```

## Usage

### Parse (Cross-Platform)

```bash
# Single file
evt-parser parse Security.evt -o Security.json
evt-parser parse Application.evt --format xml -o Application.xml
evt-parser parse System.evt --format csv -o System.csv

# Batch parse
evt-parser parse --batch /path/to/logs -O /output/dir -r
```

### Convert to EVTX (Windows Only, `wevtutil`)

```bash
evt-parser convert System.evt
evt-parser convert System.evt -o System.evtx
evt-parser convert --batch C:\Logs -r -O C:\Output
```

## Parsed Fields

For each event record, the parser exports:

- `record_number`
- `time_generated`, `time_written` (UTC ISO-8601)
- `event_id` (low 16 bits of the Windows Event ID)
- `event_type`, `event_category`
- `source`, `computer_name`
- `user_sid` (may be `null` if not present)
- `strings` (insertion strings; may be empty)
- `data` (binary payload, base64; may be `null`)

Note: This tool does not “render” Event Viewer message text (that requires the
source message DLLs/registrations present on the target system).

## Test Files

Sample EVT files from Windows Server 2003 are included in `test_files/`:
- `Application.evt` - Application event log
- `Security.evt` - Security event log
- `System.evt` - System event log

```bash
evt-parser parse test_files/Security.evt -o Security.json
```

## Requirements

- Python 3.8+
- Windows Vista+ for EVTX conversion (`wevtutil` must be available on PATH)

## License

MIT
