#!/usr/bin/env python3
"""
clean_assets.py

Validate + normalize an asset CSV for migration/import workflows.

Outputs:
- assets_clean.csv
- validation_report.csv

Exit codes:
- 0: no critical issues
- 2: critical issues found
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


REQUIRED_COLUMNS = ["asset_id", "manufacturer", "model", "status"]
OPTIONAL_COLUMNS = ["serial_number", "install_date", "notes"]

ALLOWED_STATUS = {"active", "inactive", "retired"}

MANUFACTURER_ALIASES = {
    "nest": "Nest",
    "google nest": "Nest",
    "tesla": "Tesla",
    "generac": "Generac",
}

DATE_INPUT_FORMATS = [
    "%Y-%m-%d",   # 2024-02-01
    "%m/%d/%Y",   # 02/01/2024
    "%m/%d/%y",   # 2/1/24
]


@dataclass
class Issue:
    row_number: int
    asset_id: str
    field: str
    issue: str
    severity: str  # "critical" | "warning"


def normalize_whitespace(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_manufacturer(value: str) -> str:
    v = normalize_whitespace(value).lower()
    if v in MANUFACTURER_ALIASES:
        return MANUFACTURER_ALIASES[v]
    return v.title()


def normalize_status(value: str) -> str:
    return normalize_whitespace(value).lower()


def normalize_date(value: str) -> Tuple[str, Optional[str]]:
    raw = normalize_whitespace(value)
    if not raw:
        return "", None

    for fmt in DATE_INPUT_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d"), None
        except ValueError:
            continue

    return "", f"Invalid date format: '{value}'"


def validate_required(row: Dict[str, str], issues: List[Issue], row_number: int) -> None:
    asset_id = row.get("asset_id", "").strip()
    for col in REQUIRED_COLUMNS:
        if not normalize_whitespace(row.get(col, "")):
            issues.append(Issue(row_number, asset_id, col, "Missing required value", "critical"))


def find_duplicates(rows: List[Dict[str, str]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in rows:
        aid = normalize_whitespace(r.get("asset_id", ""))
        if aid:
            counts[aid] = counts.get(aid, 0) + 1
    return {aid: c for aid, c in counts.items() if c > 1}


def normalize_row(row: Dict[str, str], issues: List[Issue], row_number: int) -> Dict[str, str]:
    out = dict(row)
    asset_id = normalize_whitespace(row.get("asset_id", ""))
    out["asset_id"] = asset_id

    out["manufacturer"] = normalize_manufacturer(row.get("manufacturer", ""))
    out["model"] = normalize_whitespace(row.get("model", ""))

    if "serial_number" in row:
        out["serial_number"] = normalize_whitespace(row.get("serial_number", ""))

    status = normalize_status(row.get("status", ""))
    out["status"] = status
    if status and status not in ALLOWED_STATUS:
        issues.append(Issue(row_number, asset_id, "status", f"Invalid status '{status}'", "critical"))

    if "install_date" in row:
        normalized, err = normalize_date(row.get("install_date", ""))
        out["install_date"] = normalized
        if err:
            issues.append(Issue(row_number, asset_id, "install_date", err, "warning"))

    if "notes" in row:
        out["notes"] = normalize_whitespace(row.get("notes", ""))

    return out


def read_csv(path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")

        fieldnames = [fn.strip() for fn in reader.fieldnames]
        rows: List[Dict[str, str]] = []
        for r in reader:
            rows.append({k.strip(): (v or "") for k, v in r.items()})
        return fieldnames, rows


def write_csv(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def write_issues(path: str, issues: List[Issue]) -> None:
    fieldnames = ["row_number", "asset_id", "field", "issue", "severity"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i in issues:
            writer.writerow(
                {
                    "row_number": i.row_number,
                    "asset_id": i.asset_id,
                    "field": i.field,
                    "issue": i.issue,
                    "severity": i.severity,
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate + normalize asset CSV for migration/import workflows.")
    parser.add_argument("--input", "-i", required=True, help="Path to input CSV")
    parser.add_argument("--outdir", "-o", default="output", help="Output directory (default: output)")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    fieldnames, rows = read_csv(args.input)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing_cols:
        print(f"ERROR: Missing required columns in header: {', '.join(missing_cols)}", file=sys.stderr)
        return 2

    issues: List[Issue] = []
    normalized_rows: List[Dict[str, str]] = []

    for idx, row in enumerate(rows, start=2):  # header = row 1
        validate_required(row, issues, idx)
        normalized_rows.append(normalize_row(row, issues, idx))

    duplicates = find_duplicates(normalized_rows)
    for aid, count in duplicates.items():
        issues.append(Issue(0, aid, "asset_id", f"Duplicate asset_id appears {count} times", "critical"))

    clean_path = os.path.join(args.outdir, "assets_clean.csv")
    report_path = os.path.join(args.outdir, "validation_report.csv")

    ordered: List[str] = []
    for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
        if c in fieldnames and c not in ordered:
            ordered.append(c)
    for c in fieldnames:
        if c not in ordered:
            ordered.append(c)

    write_csv(clean_path, ordered, normalized_rows)
    write_issues(report_path, issues)

    critical = sum(1 for i in issues if i.severity == "critical")
    warning = sum(1 for i in issues if i.severity == "warning")

    print(f"Wrote: {clean_path}")
    print(f"Wrote: {report_path}")
    print(f"Issues: {critical} critical, {warning} warning")

    return 2 if critical > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())