"""PincodeIngestionAgent — join-safe PIN directory enrichment contract."""
from __future__ import annotations

from typing import Any
import re

import pandas as pd

from .base import BaseAgent


PIN_PATTERN = re.compile(r"^[0-9]{6}$")


class PincodeIngestionAgent(BaseAgent):
    name = "pincode"
    workflow_ref = "agents/pincode_ingestion_agent.md"
    rule_families = [
        "post-office grain",
        "one-row PIN lookup",
        "ambiguity flags",
        "confidence tiers",
    ]

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        pin_col = "address_zipOrPostcode"
        pins = df[pin_col] if pin_col in df.columns else pd.Series(index=df.index, dtype=str)
        pin_text = pins.fillna("").astype(str).str.strip()
        normalized = pin_text.str.replace(r"\D", "", regex=True).str.zfill(6)
        has_pin = pin_text.ne("")
        valid_pin = has_pin & normalized.str.match(PIN_PATTERN)
        invalid_pin = has_pin & ~valid_pin

        valid_pin_values = normalized[valid_pin]
        duplicate_pin_facility_rows = int(valid_pin_values.duplicated(keep=False).sum())
        unique_pin_count = int(valid_pin_values.nunique())

        review_items: list[dict[str, Any]] = []
        for idx in df.index[invalid_pin].tolist()[:20]:
            review_items.append(
                {
                    "row_index": int(idx),
                    "issue": "invalid_facility_pin",
                    "pin_value": str(pin_text.loc[idx]),
                    "severity": "medium",
                    "recommendation": "Review facility PIN before postal enrichment.",
                }
            )

        if duplicate_pin_facility_rows:
            review_items.append(
                {
                    "issue": "pin_join_requires_lookup",
                    "severity": "high",
                    "affected_facility_rows": duplicate_pin_facility_rows,
                    "recommendation": "Join facilities only to pincode_lookup_clean, never to raw post-office grain.",
                }
            )

        sub_agents = [
            {
                "name": "pincode_cleaning_agent",
                "contract": "Trim/sentinel handling, six-digit PIN validation, post-office grain preservation.",
                "status": "specified",
            },
            {
                "name": "pincode_coordinate_agent",
                "contract": "Parse coordinates, validate India bounds, swap likely reversed coordinates, flag equal lat/lon.",
                "status": "specified",
            },
            {
                "name": "pincode_aggregation_agent",
                "contract": "Build one-row-per-PIN lookup with counts, centroid, confidence, and flags.",
                "status": "specified",
            },
            {
                "name": "pincode_ambiguity_agent",
                "contract": "Flag multi-state, weak multi-district, missing geography, and coordinate dispersion.",
                "status": "specified",
            },
            {
                "name": "pincode_scoring_agent",
                "contract": "Assign PIN confidence tiers A-D and run-level quality summary.",
                "status": "specified",
            },
        ]

        return {
            "mode": "contract_validation",
            "source_table": "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.india_post_pincode_directory",
            "target_tables": {
                "post_office_clean": "dais_readiness_desk.work.pincode_post_offices_clean",
                "lookup_clean": "dais_readiness_desk.work.pincode_lookup_clean",
                "ambiguity_flags": "dais_readiness_desk.work.pincode_ambiguity_flags",
                "review_queue": "dais_readiness_desk.work.pincode_review_queue",
                "ingestion_log": "dais_readiness_desk.audit.pincode_ingestion_log",
            },
            "sub_agents": sub_agents,
            "review_items": review_items[:50],
            "summary": {
                "facility_rows": len(df),
                "facility_rows_with_pin": int(has_pin.sum()),
                "valid_facility_pin_rows": int(valid_pin.sum()),
                "invalid_facility_pin_rows": int(invalid_pin.sum()),
                "missing_facility_pin_rows": int((~has_pin).sum()),
                "unique_facility_pins": unique_pin_count,
                "duplicate_pin_facility_rows": duplicate_pin_facility_rows,
                "review_item_count": len(review_items),
                "join_safe_lookup_required": True,
                "source_docs_verified": [
                    "agents/pincode_ingestion_agent.md",
                    "docs/pincode_data_quality.md",
                ],
            },
            "guardrail": "A PIN code is not a district key; facility enrichment must use one-row-per-PIN lookup with ambiguity flags.",
            "skeleton": True,
        }
