#!/usr/bin/env python3
"""Print a small, permission-aware snapshot of a Databricks workspace."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


DEFAULT_HOST = "https://dbc-46f0fbb0-0c1c.cloud.databricks.com"
DEFAULT_PROFILE = "dbx_hack_doctors"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def item_name(item: Any, *attrs: str) -> str:
    for attr in attrs:
        value = getattr(item, attr, None)
        if value:
            return str(value)
    return str(item)


def show_section(title: str, loader: Callable[[], Iterable[Any]], formatter: Callable[[Any], str]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    try:
        items = list(loader())
    except Exception as exc:  # Databricks APIs often vary by permissions.
        print(f"Unable to load: {exc}")
        return

    if not items:
        print("No items visible.")
        return

    for item in items[:20]:
        print(formatter(item))
    if len(items) > 20:
        print(f"... {len(items) - 20} more")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default=os.getenv("DATABRICKS_CONFIG_PROFILE", DEFAULT_PROFILE),
        help="Databricks CLI/SDK profile name to use.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("DATABRICKS_HOST", DEFAULT_HOST),
        help="Databricks workspace host URL.",
    )
    parser.add_argument(
        "--use-env-auth",
        action="store_true",
        help="Use DATABRICKS_HOST plus env credentials instead of a named config profile.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()

    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        print("Missing dependency: databricks-sdk")
        print("Install with: uv sync")
        return 1

    if args.use_env_auth or os.getenv("DATABRICKS_TOKEN"):
        if not os.getenv("DATABRICKS_TOKEN"):
            print("Missing DATABRICKS_TOKEN for --use-env-auth.")
            print("Add it to .env, or use OAuth/profile auth instead:")
            print(f"  databricks auth login --host {args.host} --profile {args.profile}")
            return 1
        workspace = WorkspaceClient(host=args.host)
        auth_source = f"env auth at {args.host}"
    else:
        workspace = WorkspaceClient(profile=args.profile)
        auth_source = f"profile {args.profile}"

    print(f"Databricks workspace explorer ({auth_source})")

    try:
        me = workspace.current_user.me()
        print(f"Signed in as: {me.user_name}")
    except Exception as exc:
        print(f"Unable to authenticate: {exc}")
        print("\nTry one of these:")
        print(f"  databricks auth login --host {args.host} --profile {args.profile}")
        print("  cp .env.example .env  # then add DATABRICKS_TOKEN for PAT auth")
        return 1

    show_section(
        "Clusters",
        workspace.clusters.list,
        lambda c: f"- {item_name(c, 'cluster_name')} ({item_name(c, 'cluster_id')})",
    )
    show_section(
        "SQL Warehouses",
        workspace.warehouses.list,
        lambda w: f"- {item_name(w, 'name')} ({item_name(w, 'id')})",
    )
    show_section(
        "Jobs",
        workspace.jobs.list,
        lambda j: f"- {item_name(j.settings, 'name') if getattr(j, 'settings', None) else item_name(j, 'job_id')} ({item_name(j, 'job_id')})",
    )
    show_section(
        "Unity Catalog Catalogs",
        workspace.catalogs.list,
        lambda c: f"- {item_name(c, 'name')} ({item_name(c, 'catalog_type')})",
    )
    show_section(
        "Workspace Root",
        lambda: workspace.workspace.list("/"),
        lambda o: f"- {item_name(o, 'path')} [{item_name(o, 'object_type')}]",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
