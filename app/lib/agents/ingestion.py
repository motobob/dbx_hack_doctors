"""IngestionManagerAgent — upload/schema routing skeleton."""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..json_fields import normalize_jsonish_dataframe
from .base import BaseAgent


class IngestionManagerAgent(BaseAgent):
    name = "ingestion"
    workflow_ref = "agents/ingestion_agent.md#3-sub-agent-a--alignment--cleaning-agent"
    rule_families = [
        "scraper corruption",
        "field typing",
        "state mapping",
        "coordinate repair",
    ]

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        incoming = upstream.get("incoming_records") or []
        incoming_df = normalize_jsonish_dataframe(pd.DataFrame(incoming))
        required = ["name", "address_city", "address_stateOrRegion", "address_zipOrPostcode"]
        source_columns = list(incoming_df.columns if incoming else df.columns)
        present = [column for column in required if column in source_columns]
        missing = [column for column in required if column not in source_columns]
        shifted_columns_suspected = False
        blank_required_cells = 0
        row_quality_flags: list[dict[str, Any]] = []
        if incoming:
            for column in present:
                blanks = incoming_df[column].fillna("").astype(str).str.strip().eq("")
                blank_required_cells += int(blanks.sum())
                for row_index in incoming_df.index[blanks].tolist()[:20]:
                    row_quality_flags.append(
                        {
                            "incoming_index": int(row_index),
                            "issue": "blank_required_field",
                            "field": column,
                            "severity": "medium",
                        }
                    )
            shifted_columns_suspected = blank_required_cells > max(3, len(incoming_df) * max(len(present), 1) * 0.45)

        route = "qa_ready"
        if missing or shifted_columns_suspected or row_quality_flags:
            route = "needs_mapping_review"

        return {
            "mode": "ingest" if incoming else "analysis",
            "incoming_count": len(incoming),
            "existing_count": len(df),
            "required_fields_present": present,
            "required_fields_missing": missing,
            "shifted_columns_suspected": shifted_columns_suspected,
            "blank_required_cells": blank_required_cells,
            "row_quality_flags": row_quality_flags[:50],
            "route": route,
            "review_required": route != "qa_ready",
            "summary": {
                "source_columns": len(source_columns),
                "present_required": len(present),
                "missing_required": len(missing),
                "row_quality_flag_count": len(row_quality_flags),
            },
        }
