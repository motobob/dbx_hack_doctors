#!/usr/bin/env python3
"""Inspect locally downloaded raw Databricks CSV files."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
from typing import Any


DEFAULT_CATALOG = "databricks_virtue_foundation_dataset_dais_2026"
DEFAULT_SCHEMA = "virtue_foundation_dataset"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=f"data/raw/{DEFAULT_CATALOG}/{DEFAULT_SCHEMA}")
    parser.add_argument("--sample-rows", type=int, default=3)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def inspect_csv(path: Path, sample_rows: int) -> tuple[list[str], list[list[str]]]:
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        rows = []
        for _ in range(sample_rows):
            try:
                rows.append(next(reader))
            except StopIteration:
                break
    return header, rows


def shorten(value: str, max_length: int = 140) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def main() -> int:
    args = parse_args()
    data_dir = (PROJECT_ROOT / args.data_dir).resolve()
    manifest_path = data_dir / "manifest.json"

    if not manifest_path.exists():
        print(f"Missing manifest: {manifest_path}")
        print("Run: uv run python scripts/download_catalog.py --overwrite")
        return 1

    manifest = load_json(manifest_path)
    print(f"Local raw data: {data_dir}")
    print(f"Tables: {len(manifest)}")

    for entry in manifest:
        csv_path = PROJECT_ROOT / entry["csv"]
        schema_path = PROJECT_ROOT / entry["schema"]
        header, rows = inspect_csv(csv_path, args.sample_rows)
        schema = load_json(schema_path)
        columns = schema.get("table_info", {}).get("columns", [])

        print(f"\n{entry['table']}")
        print("-" * len(entry["table"]))
        print(f"Rows: {entry['rows']:,}")
        print(f"CSV: {csv_path}")
        print(f"Columns: {len(header)}")
        if columns:
            typed_columns = [
                f"{column.get('name')}: {column.get('type_text') or column.get('type_name')}"
                for column in columns[:8]
            ]
            print("First typed columns: " + ", ".join(typed_columns))
        if rows:
            preview = dict(zip(header, rows[0], strict=False))
            print("First row preview:")
            for key, value in list(preview.items())[:8]:
                print(f"  {key}: {shorten(value)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
