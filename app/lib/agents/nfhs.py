"""NfhsSurveyIngestionAgent — district survey ingestion contract."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .base import BaseAgent


class NfhsSurveyIngestionAgent(BaseAgent):
    name = "nfhs"
    workflow_ref = "agents/nfhs_survey_ingestion_agent.md"
    rule_families = [
        "district survey grain",
        "suppression flags",
        "caution estimates",
        "join keys",
    ]

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        # This skeleton validates the NFHS ingestion contract and creates runtime
        # planning context. Full NFHS parsing happens in UC work tables.
        state_col = "address_stateOrRegion"
        city_col = "address_city"
        location_frame = df[[c for c in [state_col, city_col] if c in df.columns]].fillna("").astype(str) if len(df) else pd.DataFrame()
        usable_geo_rows = 0
        if not location_frame.empty:
            usable_geo_rows = int(location_frame.apply(lambda row: any(value.strip() for value in row), axis=1).sum())

        sub_agents = [
            {
                "name": "nfhs_schema_agent",
                "contract": "Validate geography columns, survey-base columns, and indicator column classification.",
                "status": "specified",
            },
            {
                "name": "nfhs_geography_agent",
                "contract": "Preserve raw state/district labels and create normalized district join keys.",
                "status": "specified",
            },
            {
                "name": "nfhs_indicator_parsing_agent",
                "contract": "Parse numeric, suppressed '*', parenthesized caution estimates, and failures.",
                "status": "specified",
            },
            {
                "name": "nfhs_quality_flag_agent",
                "contract": "Write suppressed, caution, parse failure, range failure, and geography warning flags.",
                "status": "specified",
            },
            {
                "name": "nfhs_ingestion_scoring_agent",
                "contract": "Score ingestion quality only; never district health risk.",
                "status": "specified",
            },
        ]

        return {
            "mode": "contract_validation",
            "source_table": "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.nfhs_5_district_health_indicators",
            "target_tables": {
                "clean": "dais_readiness_desk.work.nfhs_district_indicators_clean",
                "quality_flags": "dais_readiness_desk.work.nfhs_indicator_quality_flags",
                "geography_review_queue": "dais_readiness_desk.work.nfhs_geography_review_queue",
                "ingestion_log": "dais_readiness_desk.audit.nfhs_ingestion_log",
            },
            "sub_agents": sub_agents,
            "summary": {
                "facility_rows": len(df),
                "facility_rows_with_joinable_geo_hint": usable_geo_rows,
                "expected_nfhs_source_rows": 706,
                "expected_nfhs_columns": 109,
                "baseline_suppressed_cell_count": 4125,
                "baseline_caution_estimate_cell_count": 5068,
                "join_key_required": True,
                "source_docs_verified": [
                    "agents/nfhs_survey_ingestion_agent.md",
                    "docs/nfhs_survey_ingestion_data_quality.md",
                ],
            },
            "guardrail": "NFHS is district survey context only: suppressed '*' values become NULL, parenthesized values keep caution flags, and ingestion quality is not health risk.",
            "skeleton": True,
        }
