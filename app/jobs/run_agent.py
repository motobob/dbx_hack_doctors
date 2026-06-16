#!/usr/bin/env python
"""
Databricks Job task entrypoint.

Each task in the multi-task Job runs:
    python jobs/run_agent.py <agent_name> <pipeline_id>

The pipeline_id is passed as a Databricks Job parameter. For local/manual task
testing, PIPELINE_ID env var is also accepted.

State is written back via the Workspace API so the FastAPI app can read it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_JOB_ENV = {
    "APP_DATA_MODE": "unity_catalog",
    "APP_SOURCE_MODE": "unity_catalog",
    "APP_STATE_MODE": "local",
    "DATABRICKS_HOST": "https://dbc-46f0fbb0-0c1c.cloud.databricks.com",
    "DATABRICKS_WORKSPACE_PATH": "/Workspace/Users/ebob@qbocoherence.ai/dbx-hack-doctors",
    "APP_SOURCE_CATALOG": "databricks_virtue_foundation_dataset_dais_2026",
    "APP_SOURCE_SCHEMA": "virtue_foundation_dataset",
    "APP_SOURCE_TABLE": "facilities",
    "APP_RESULT_CATALOG": "dais_readiness_desk",
    "DATABRICKS_WAREHOUSE_ID": "e428febecc2419c5",
    "APP_SOURCE_ROW_LIMIT": "10000",
    "APP_STATE_FALLBACK_ON_ERROR": "true",
    "AGENT_LLM_ENABLED": "false",
    "DATABRICKS_SQL_USE_CLOUD_FETCH": "false",
    "DATABRICKS_JOB_USE_SPARK_SOURCE": "true",
}


def _app_dir() -> Path:
    """Resolve app/ when Databricks Spark Python task does not define __file__."""
    if "__file__" in globals():
        return Path(__file__).resolve().parent.parent
    workspace_path = os.getenv("DATABRICKS_WORKSPACE_PATH") or DEFAULT_JOB_ENV["DATABRICKS_WORKSPACE_PATH"]
    if workspace_path:
        return Path(workspace_path)
    return Path.cwd()


# Ensure app/ is on sys.path regardless of CWD.
APP_DIR = _app_dir()
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pandas as pd

from lib import pipeline_state as ps
from lib.store import read_facilities


def configure_job_env() -> None:
    for key, value in DEFAULT_JOB_ENV.items():
        os.environ.setdefault(key, value)


def _spark_source_table() -> str:
    catalog = os.getenv("APP_SOURCE_CATALOG") or os.getenv("DATABRICKS_CATALOG")
    schema = os.getenv("APP_SOURCE_SCHEMA") or os.getenv("DATABRICKS_SCHEMA")
    table = os.getenv("APP_SOURCE_TABLE", "facilities")
    if not catalog or not schema or not table:
        raise RuntimeError("Missing APP_SOURCE_CATALOG, APP_SOURCE_SCHEMA, or APP_SOURCE_TABLE.")
    return f"`{catalog}`.`{schema}`.`{table}`"


def read_facilities_for_job() -> pd.DataFrame:
    if os.getenv("DATABRICKS_JOB_USE_SPARK_SOURCE", "true").strip().lower() in {"0", "false", "no", "off"}:
        return read_facilities()

    try:
        from pyspark.sql import SparkSession

        spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        limit = int(os.getenv("APP_SOURCE_ROW_LIMIT", "10000"))
        rows = spark.table(_spark_source_table()).limit(limit).collect()
        return pd.DataFrame([row.asDict(recursive=True) for row in rows])
    except Exception as exc:
        print(f"[job] Spark source read failed, falling back to SQL connector: {type(exc).__name__}: {exc}")
        return read_facilities()


def main() -> None:
    configure_job_env()

    if len(sys.argv) < 2:
        print("Usage: python run_agent.py <agent_name>", file=sys.stderr)
        sys.exit(1)

    agent_name = sys.argv[1].lower()
    pipeline_id = os.environ.get("PIPELINE_ID") or (sys.argv[2] if len(sys.argv) > 2 else None)
    if not pipeline_id:
        print("ERROR: PIPELINE_ID env var or second CLI arg required", file=sys.stderr)
        sys.exit(1)

    print(f"[{agent_name}] pipeline={pipeline_id}")

    # Load state from workspace (written by FastAPI when job was triggered)
    state = ps.workspace_load(pipeline_id) or ps.new_pipeline(pipeline_id)
    df = read_facilities_for_job()

    # Collect upstream results from already-completed agents
    upstream: dict = {}
    for name, agent_state in state.get("agents", {}).items():
        if agent_state.get("status") == "completed" and agent_state.get("result"):
            upstream[name] = agent_state["result"]

    # Instantiate and run the requested agent
    agent = _get_agent(agent_name)
    agent.run(df, state, upstream)

    # Write updated state back to workspace
    ps.workspace_save(state)
    print(f"[{agent_name}] done — status: {state['agents'][agent_name]['status']}")


def _get_agent(name: str):
    from lib.agents import (
        DedupAgent,
        EvidenceSpecialtyAgent,
        GeoAgent,
        HumanReviewGateAgent,
        IngestionManagerAgent,
        NfhsSurveyIngestionAgent,
        PincodeIngestionAgent,
        QAProfileAgent,
        RiskAgent,
        ShortageAgent,
    )

    agents = {
        "ingestion": IngestionManagerAgent,
        "qa": QAProfileAgent,
        "pincode": PincodeIngestionAgent,
        "nfhs": NfhsSurveyIngestionAgent,
        "dedup": DedupAgent,
        "evidence": EvidenceSpecialtyAgent,
        "geo": GeoAgent,
        "shortage": ShortageAgent,
        "review": HumanReviewGateAgent,
        "risk": RiskAgent,
    }
    cls = agents.get(name)
    if cls is None:
        raise ValueError(f"Unknown agent: {name!r}. Choose from: {list(agents)}")
    return cls()


if __name__ == "__main__":
    main()
