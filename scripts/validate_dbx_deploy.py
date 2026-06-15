#!/usr/bin/env python
"""Validate the deployed Databricks App and eight-agent Databricks Job."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from databricks.sdk import WorkspaceClient


REPO_DIR = Path(__file__).resolve().parents[1]
APP_DIR = REPO_DIR / "app"
EXPECTED_AGENTS = ["ingestion", "qa", "dedup", "evidence", "geo", "shortage", "review", "risk"]


def load_env() -> None:
    env_file = REPO_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def new_pipeline_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"dbx-smoke-{stamp}"


def task_summary(run) -> list[dict]:
    rows = []
    for task in run.tasks or []:
        state = task.state
        rows.append(
            {
                "task_key": task.task_key,
                "run_id": task.run_id,
                "life_cycle_state": str(state.life_cycle_state) if state else None,
                "result_state": str(state.result_state) if state else None,
                "state_message": state.state_message if state else None,
            }
        )
    return rows


def main() -> int:
    load_env()
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))

    app_name = os.getenv("DATABRICKS_APP_NAME", "dbx-hack-doctors")
    job_id = os.getenv("DATABRICKS_PIPELINE_JOB_ID")
    if not job_id:
        raise RuntimeError("DATABRICKS_PIPELINE_JOB_ID is missing. Run scripts/setup_dbx_job.py first.")

    w = WorkspaceClient()

    app = w.apps.get(app_name)
    app_status = {
        "name": app.name,
        "url": app.url,
        "compute_status": app.compute_status.as_dict() if app.compute_status else None,
    }
    print("APP_STATUS")
    print(json.dumps(app_status, indent=2))

    pipeline_id = new_pipeline_id()
    print(f"STARTING_JOB job_id={job_id} pipeline_id={pipeline_id}")
    run = w.jobs.run_now(job_id=int(job_id), job_parameters={"pipeline_id": pipeline_id})
    run_id = int(run.run_id)
    print(f"JOB_RUN_ID {run_id}")

    timeout_seconds = int(os.getenv("DBX_VALIDATE_TIMEOUT_SECONDS", "900"))
    deadline = time.time() + timeout_seconds
    last_state = ""
    final_run = None
    while time.time() < deadline:
        current = w.jobs.get_run(run_id=run_id)
        life_cycle = str(current.state.life_cycle_state) if current.state else "UNKNOWN"
        result_state = str(current.state.result_state) if current.state else "UNKNOWN"
        marker = f"{life_cycle}/{result_state}"
        if marker != last_state:
            print(f"JOB_STATE {marker}")
            last_state = marker
        if "TERMINATED" in life_cycle or "SKIPPED" in life_cycle or "INTERNAL_ERROR" in life_cycle:
            final_run = current
            break
        time.sleep(15)

    if final_run is None:
        raise TimeoutError(f"Job run {run_id} did not finish within {timeout_seconds} seconds.")

    print("TASKS")
    print(json.dumps(task_summary(final_run), indent=2))

    result_state = str(final_run.state.result_state) if final_run.state else ""
    if "SUCCESS" not in result_state:
        raise RuntimeError(f"Databricks Job run did not succeed: {result_state}")

    from lib import pipeline_state as ps  # noqa: PLC0415

    state = ps.workspace_load(pipeline_id)
    if not state:
        raise RuntimeError(f"Could not load workspace pipeline state for {pipeline_id}.")
    agent_statuses = {name: state.get("agents", {}).get(name, {}).get("status") for name in EXPECTED_AGENTS}
    print("WORKSPACE_PIPELINE_STATE")
    print(json.dumps({"pipeline_id": pipeline_id, "status": state.get("status"), "agents": agent_statuses}, indent=2))

    incomplete = {name: status for name, status in agent_statuses.items() if status != "completed"}
    if incomplete:
        raise RuntimeError(f"Not all agents completed: {incomplete}")

    print("DBX_DEPLOY_VALIDATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
