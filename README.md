# Python Data Cleanup + Migration Helper

A small CLI tool that validates and cleans asset CSV exports for import/migration workflows.

## Why
Support engineering often needs to update/clean data attributes when no UI is available and produce upload-ready files with clear validation output.

## What it does
- Validates required columns/values (e.g., `asset_id`, `manufacturer`, `model`, `status`)
- Normalizes common fields:
  - trims whitespace
  - normalizes manufacturer names (basic alias mapping)
  - normalizes status values
  - parses dates and outputs `YYYY-MM-DD`
- Detects duplicate `asset_id` values
- Produces two outputs:
  - `assets_clean.csv` (import-ready)
  - `validation_report.csv` (row-level issues)

  ## Expected columns
Required:
- `asset_id`
- `manufacturer`
- `model`
- `status`

Optional:
- `serial_number`
- `install_date`
- `notes`

## Usage
```bash
python clean_assets.py --input sample_data/assets_raw.csv --outdir output
```

## Example output
```text
Wrote: output/assets_clean.csv
Wrote: output/validation_report.csv
Issues: 1 critical, 0 warning
```

Notes:
- If **critical** issues are found, the script exits with code `2` (useful for CI checks).
- Review `output/validation_report.csv` to see row-level details.

## Output
- `output/assets_clean.csv`
- `output/validation_report.csv`

## Requirements
- Python 3.12+
- No external dependencies (standard library only)