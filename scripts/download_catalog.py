#!/usr/bin/env python3
"""Download Databricks Unity Catalog tables to local CSV files."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


DEFAULT_HOST = "https://dbc-46f0fbb0-0c1c.cloud.databricks.com"
DEFAULT_CATALOG = "databricks_virtue_foundation_dataset_dais_2026"
DEFAULT_SCHEMA = "virtue_foundation_dataset"
DEFAULT_WAREHOUSE_ID = "e428febecc2419c5"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("DATABRICKS_HOST", DEFAULT_HOST))
    parser.add_argument("--catalog", default=os.getenv("DATABRICKS_CATALOG", DEFAULT_CATALOG))
    parser.add_argument("--schema", default=os.getenv("DATABRICKS_SCHEMA", DEFAULT_SCHEMA))
    parser.add_argument("--warehouse-id", default=os.getenv("DATABRICKS_WAREHOUSE_ID", DEFAULT_WAREHOUSE_ID))
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--batch-size", type=int, default=10_000)
    parser.add_argument("--limit", type=int, help="Optional row limit per table for test downloads.")
    parser.add_argument("--tables", nargs="*", help="Optional table names. Defaults to every visible table.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing CSV files.")
    return parser.parse_args()


def quote_identifier(identifier: str) -> str:
    return "`" + identifier.replace("`", "``") + "`"


def full_table_name(catalog: str, schema: str, table: str) -> str:
    return ".".join(quote_identifier(part) for part in (catalog, schema, table))


def safe_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    return safe or "table"


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if hasattr(value, "__dict__"):
        return {key: val for key, val in vars(value).items() if not key.startswith("_")}
    return str(value)


def cell_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def make_workspace(host: str):
    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        print("Missing dependency: databricks-sdk")
        print("Install with: uv sync")
        raise SystemExit(1)

    if not os.getenv("DATABRICKS_TOKEN"):
        print("Missing DATABRICKS_TOKEN in .env.")
        raise SystemExit(1)
    return WorkspaceClient(host=host)


def list_tables(workspace: Any, catalog: str, schema: str, requested: list[str] | None) -> list[str]:
    if requested:
        return requested

    tables = workspace.tables.list(catalog_name=catalog, schema_name=schema)
    names = sorted(table.name for table in tables if getattr(table, "name", None))
    if not names:
        raise RuntimeError(f"No visible tables found in {catalog}.{schema}")
    return names


def write_schema(workspace: Any, catalog: str, schema: str, table: str, metadata_path: Path) -> None:
    table_info = workspace.tables.get(full_name=f"{catalog}.{schema}.{table}")
    payload = {
        "catalog": catalog,
        "schema": schema,
        "table": table,
        "full_name": f"{catalog}.{schema}.{table}",
        "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "table_info": table_info,
    }
    metadata_path.write_text(json.dumps(payload, indent=2, default=json_default) + "\n")


def connect_sql(host: str, warehouse_id: str):
    try:
        from databricks import sql
    except ImportError:
        print("Missing dependency: databricks-sql-connector")
        print("Install with: uv sync")
        raise SystemExit(1)

    server_hostname = host.removeprefix("https://").removeprefix("http://").rstrip("/")
    return sql.connect(
        server_hostname=server_hostname,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def download_table(
    connection: Any,
    catalog: str,
    schema: str,
    table: str,
    csv_path: Path,
    batch_size: int,
    limit: int | None,
) -> int:
    query = f"SELECT * FROM {full_table_name(catalog, schema, table)}"
    if limit is not None:
        query += f" LIMIT {limit}"

    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]

        with gzip.open(csv_path, "wt", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)

            row_count = 0
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                writer.writerows([cell_value(value) for value in row] for row in rows)
                row_count += len(rows)
                print(f"  wrote {row_count:,} rows", flush=True)

    return row_count


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()

    output_root = (PROJECT_ROOT / args.output_dir / args.catalog / args.schema).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    workspace = make_workspace(args.host)
    table_names = list_tables(workspace, args.catalog, args.schema, args.tables)

    print(f"Downloading {len(table_names)} table(s) from {args.catalog}.{args.schema}")
    print(f"Warehouse: {args.warehouse_id}")
    print(f"Output: {output_root}")

    with connect_sql(args.host, args.warehouse_id) as connection:
        manifest: list[dict[str, Any]] = []
        for table in table_names:
            table_dir = output_root / safe_name(table)
            table_dir.mkdir(parents=True, exist_ok=True)
            csv_path = table_dir / f"{safe_name(table)}.csv.gz"
            metadata_path = table_dir / "schema.json"

            if csv_path.exists() and not args.overwrite:
                print(f"\nSkipping {table}: {csv_path} already exists. Use --overwrite to replace it.")
                continue

            print(f"\n{table}")
            print("-" * len(table))
            write_schema(workspace, args.catalog, args.schema, table, metadata_path)
            row_count = download_table(
                connection=connection,
                catalog=args.catalog,
                schema=args.schema,
                table=table,
                csv_path=csv_path,
                batch_size=args.batch_size,
                limit=args.limit,
            )
            manifest.append(
                {
                    "table": table,
                    "rows": row_count,
                    "csv": str(csv_path.relative_to(PROJECT_ROOT)),
                    "schema": str(metadata_path.relative_to(PROJECT_ROOT)),
                }
            )
            print(f"Saved {row_count:,} rows to {csv_path}")

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nManifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
