#!/usr/bin/env python3
"""Explore the configured Databricks Unity Catalog schema and table metadata."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any


DEFAULT_HOST = "https://dbc-46f0fbb0-0c1c.cloud.databricks.com"
DEFAULT_PROFILE = "dbx_hack_doctors"
DEFAULT_CATALOG = "databricks_virtue_foundation_dataset_dais_2026"
DEFAULT_SCHEMA = "virtue_foundation_dataset"
DEFAULT_TABLE = "nfhs_5_district_health_indicators"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def display(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=os.getenv("DATABRICKS_CONFIG_PROFILE", DEFAULT_PROFILE))
    parser.add_argument("--host", default=os.getenv("DATABRICKS_HOST", DEFAULT_HOST))
    parser.add_argument("--catalog", default=os.getenv("DATABRICKS_CATALOG", DEFAULT_CATALOG))
    parser.add_argument("--schema", default=os.getenv("DATABRICKS_SCHEMA", DEFAULT_SCHEMA))
    parser.add_argument("--table", default=os.getenv("DATABRICKS_TABLE", DEFAULT_TABLE))
    parser.add_argument("--use-env-auth", action="store_true")
    return parser.parse_args()


def make_workspace(args: argparse.Namespace):
    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        print("Missing dependency: databricks-sdk")
        print("Install with: uv sync")
        raise SystemExit(1)

    if args.use_env_auth:
        if not os.getenv("DATABRICKS_TOKEN"):
            print("Missing DATABRICKS_TOKEN for --use-env-auth.")
            print("Add it to .env, or use OAuth/profile auth instead:")
            print(f"  databricks auth login --host {args.host} --profile {args.profile}")
            raise SystemExit(1)
        return WorkspaceClient(host=args.host)

    return WorkspaceClient(profile=args.profile)


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    workspace = make_workspace(args)
    full_schema = f"{args.catalog}.{args.schema}"
    full_table = f"{full_schema}.{args.table}"

    print(f"Catalog explorer: {full_schema}")

    try:
        me = workspace.current_user.me()
        print(f"Signed in as: {me.user_name}")
    except Exception as exc:
        print(f"Unable to authenticate: {exc}")
        print(f"Try: databricks auth login --host {args.host} --profile {args.profile}")
        return 1

    print("\nTables")
    print("------")
    try:
        tables = list(workspace.tables.list(catalog_name=args.catalog, schema_name=args.schema))
    except Exception as exc:
        print(f"Unable to list tables: {exc}")
        return 1

    if not tables:
        print("No tables visible.")
    for table in tables:
        name = display(getattr(table, "name", None))
        table_type = display(getattr(table, "table_type", None))
        comment = display(getattr(table, "comment", None))
        print(f"- {name} [{table_type}]" + (f" - {comment}" if comment else ""))

    print(f"\nColumns: {full_table}")
    print("-" * (9 + len(full_table)))
    try:
        table_info = workspace.tables.get(full_name=full_table)
    except Exception as exc:
        print(f"Unable to describe table: {exc}")
        return 1

    columns = getattr(table_info, "columns", None) or []
    if not columns:
        print("No column metadata visible.")
    for column in columns:
        name = display(getattr(column, "name", None))
        type_text = display(getattr(column, "type_text", None) or getattr(column, "type_name", None))
        comment = display(getattr(column, "comment", None))
        print(f"- {name}: {type_text}" + (f" - {comment}" if comment else ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
