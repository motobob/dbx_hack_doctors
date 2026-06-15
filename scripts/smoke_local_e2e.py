#!/usr/bin/env python
"""Local end-to-end smoke test for the Data Readiness Desk demo path.

This intentionally avoids Databricks network dependencies. It validates the
click-through demo skeleton:

1. FastAPI health/state endpoints respond in local checked-in-data mode.
2. Demo XLSX parses through the same upload-preview endpoint used by the UI.
3. The import records run through the full eight-agent local pipeline.
4. Expected demo signals are present: duplicate decisions, row-quality flags,
   and human-review items.
"""
from __future__ import annotations

import os
import sys
import asyncio
import io
from pathlib import Path

from fastapi import UploadFile


REPO_DIR = Path(__file__).resolve().parents[1]
APP_DIR = REPO_DIR / "app"
DEMO_XLSX = REPO_DIR / "demo" / "data_readiness_demo_import.xlsx"
EXPECTED_AGENTS = ["ingestion", "qa", "dedup", "evidence", "geo", "shortage", "review", "risk"]


def configure_local_env() -> None:
    os.environ.update(
        {
            "APP_DATA_MODE": "local",
            "APP_SOURCE_MODE": "checked_in",
            "APP_STATE_MODE": "local",
            "PIPELINE_MODE": "local",
            "AGENT_LLM_ENABLED": "false",
            "APP_BASIC_AUTH_ENABLED": "false",
            "APP_STATE_LOAD_TIMEOUT_SECONDS": "8",
        }
    )


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main_async() -> int:
    configure_local_env()
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))

    if not DEMO_XLSX.exists():
        raise FileNotFoundError(f"Missing demo workbook: {DEMO_XLSX}. Run scripts/create_demo_import.py")

    import server  # noqa: PLC0415

    health = server.health()
    assert_true(health.get("status") == "ok", "/api/health endpoint did not return ok")

    state_json = await server.state()
    assert_true(len(state_json.get("preview", [])) > 0, "/api/state returned no preview rows")

    upload_file = UploadFile(
        filename=DEMO_XLSX.name,
        file=io.BytesIO(DEMO_XLSX.read_bytes()),
    )
    upload_json = await server.import_preview(upload_file)
    assert_true(upload_json["row_count"] == 12, f"expected 12 import rows, got {upload_json['row_count']}")
    assert_true(upload_json["import_readiness"] == 100, f"expected 100 import readiness, got {upload_json['import_readiness']}")

    start = await server.pipeline_start(
        server.PipelineStartPayload(mode="local", incoming_records=upload_json["preview"])
    )
    pipeline_id = start["pipeline_id"]

    final_state = None
    for _ in range(80):
        status_json = server.pipeline_status(pipeline_id)
        if status_json.get("status") in {"completed", "failed"}:
            final_state = status_json
            break
        await asyncio.sleep(0.25)

    assert_true(final_state is not None, "pipeline timed out")
    assert_true(final_state["status"] == "completed", f"pipeline did not complete: {final_state['status']}")

    agents = final_state["agents"]
    agent_statuses = {name: agents[name]["status"] for name in EXPECTED_AGENTS}
    assert_true(all(status == "completed" for status in agent_statuses.values()), f"agent statuses: {agent_statuses}")

    ingestion_summary = agents["ingestion"]["result"]["summary"]
    dedup_summary = agents["dedup"]["result"]["summary"]
    review_summary = agents["review"]["result"]["summary"]

    assert_true(
        ingestion_summary.get("row_quality_flag_count", 0) >= 3,
        f"expected at least 3 row-quality flags, got {ingestion_summary}",
    )
    assert_true(
        dedup_summary.get("duplicate_count", 0) >= 4,
        f"expected at least 4 duplicate decisions, got {dedup_summary}",
    )
    assert_true(
        review_summary.get("review_count", 0) >= 20,
        f"expected at least 20 review items, got {review_summary}",
    )

    print("LOCAL_E2E_SMOKE_OK")
    print(f"pipeline_id={pipeline_id}")
    print(f"agents={agent_statuses}")
    print(f"ingestion={ingestion_summary}")
    print(f"dedup={dedup_summary}")
    print(f"review={review_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
