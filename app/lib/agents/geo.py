"""
GeoAgent — validates geographic data quality and identifies anomalies.

Input : full facilities DataFrame + dedup results (upstream)
Output: geo quality report with flagged records and coverage gaps
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .base import BaseAgent

SYSTEM = """You are a geographic data quality analyst specialising in healthcare facility data for India.

You will receive a JSON sample of facility records with location fields.
Identify:
1. Suspicious or mismatched state/city/PIN combinations
2. Records with likely incorrect or swapped coordinates
3. States with suspiciously low facility density relative to population size
4. Geographic coverage gaps (states/districts with no facilities)

Return ONLY valid JSON in this exact shape:
{
  "flagged_records": [
    {
      "name": "...",
      "issue": "mismatched state/city|bad coordinates|duplicate location|other",
      "detail": "one sentence",
      "state": "...",
      "city": "..."
    }
  ],
  "coverage_gaps": [
    {
      "state": "...",
      "issue": "no facilities|very low density|missing districts",
      "severity": "high|medium|low"
    }
  ],
  "summary": {
    "flagged_count": 0,
    "gap_states": 0,
    "overall_geo_quality_score": 0
  }
}"""


class GeoAgent(BaseAgent):
    name = "geo"

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        state_col = "address_stateOrRegion"
        city_col = "address_city"
        pin_col = "address_zipOrPostcode"
        if not self.llm_enabled():
            missing_location = df[
                [
                    column
                    for column in [state_col, city_col, pin_col]
                    if column in df.columns
                ]
            ].fillna("").astype(str).apply(lambda row: any(not value.strip() for value in row), axis=1) if len(df) else pd.Series(dtype=bool)
            flagged_count = int(missing_location.sum()) if len(df) else 0
            coverage_gaps = []
            if state_col in df.columns:
                counts = df[state_col].fillna("Unknown").astype(str).value_counts()
                coverage_gaps = [
                    {"state": state, "issue": "very low density", "severity": "medium"}
                    for state, count in counts.tail(min(5, len(counts))).items()
                    if count < max(3, len(df) * 0.002)
                ]
            return {
                "flagged_records": [
                    {
                        "name": str(row.get("name", "")),
                        "issue": "missing location fields",
                        "detail": "Record is missing at least one state/city/PIN value.",
                        "state": str(row.get(state_col, "")),
                        "city": str(row.get(city_col, "")),
                    }
                    for _, row in df[missing_location].head(20).fillna("").iterrows()
                ] if len(df) else [],
                "coverage_gaps": coverage_gaps,
                "summary": {
                    "flagged_count": flagged_count,
                    "gap_states": len(coverage_gaps),
                    "overall_geo_quality_score": max(0, round(100 - flagged_count / max(len(df), 1) * 100)),
                },
                "skeleton": True,
            }

        state_dist = (
            df[state_col].fillna("Unknown").value_counts().head(20).to_dict()
            if state_col in df.columns else {}
        )

        user_msg = (
            f"Analyse geo quality for {len(df):,} healthcare facility records.\n\n"
            f"State distribution (top 20):\n{pd.Series(state_dist).to_json()}\n\n"
            f"Sample records (up to 60):\n{self._sample(df)}"
        )

        return self._ask(SYSTEM, user_msg)
