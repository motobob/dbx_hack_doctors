"""
ShortageAgent — identifies healthcare service shortages by geography.

Input : full facilities DataFrame + dedup results (upstream)
Output: shortage analysis by state/district with care-type breakdown
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .base import BaseAgent

SYSTEM = """You are a healthcare access analyst specialising in shortage area identification.

You will receive aggregate statistics and a sample of healthcare facility records.
Identify:
1. States / districts with critical shortages (emergency, ICU, NICU, maternity)
2. States that appear data-poor vs. genuinely underserved
3. Capability gaps — common care types missing from certain regions
4. Priority areas for intervention based on facility density and capability evidence

Return ONLY valid JSON in this exact shape:
{
  "shortage_areas": [
    {
      "state": "...",
      "district_or_city": "...",
      "care_types_missing": ["ICU", "NICU", "Emergency"],
      "severity": "critical|high|medium|low",
      "facility_count": 0,
      "evidence": "one sentence",
      "data_confidence": "high|medium|low"
    }
  ],
  "capability_gaps": [
    {
      "care_type": "ICU|NICU|Emergency|Maternity|Oncology|Dialysis|Surgery",
      "affected_states": ["..."],
      "gap_severity": "high|medium|low"
    }
  ],
  "summary": {
    "critical_shortage_states": 0,
    "total_shortage_areas": 0,
    "most_underserved_state": "...",
    "top_missing_care_type": "..."
  }
}"""


class ShortageAgent(BaseAgent):
    name = "shortage"
    workflow_ref = "app/lib/agents/SPEC.md#shortageagent-operating-contract"
    rule_families = [
        "trust-weighted coverage",
        "capability gaps",
        "data-poor regions",
        "planning impact",
    ]

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        state_col = "address_stateOrRegion"
        cap_col = "capability"
        spec_col = "specialties"

        # Build per-state capability summary
        state_summary: list[dict] = []
        if state_col in df.columns:
            for state, grp in df.groupby(state_col):
                has_cap = grp[cap_col].fillna("").astype(str).str.len().gt(4).sum() if cap_col in grp else 0
                has_spec = grp[spec_col].fillna("").astype(str).str.len().gt(4).sum() if spec_col in grp else 0
                state_summary.append({
                    "state": state,
                    "facility_count": len(grp),
                    "has_capability_data": int(has_cap),
                    "has_specialty_data": int(has_spec),
                })

        dedup_summary = upstream.get("dedup", {}).get("summary", {})
        if not self.llm_enabled():
            shortage_areas = []
            for item in state_summary:
                capability_ratio = (item["has_capability_data"] + item["has_specialty_data"]) / max(item["facility_count"] * 2, 1)
                if capability_ratio < 0.35:
                    shortage_areas.append(
                        {
                            "state": item["state"],
                            "district_or_city": "",
                            "care_types_missing": ["ICU", "NICU", "Emergency"],
                            "severity": "high" if capability_ratio < 0.15 else "medium",
                            "facility_count": item["facility_count"],
                            "evidence": "Sparse capability/specialty evidence in skeleton shortage scan.",
                            "data_confidence": "low" if capability_ratio < 0.15 else "medium",
                        }
                    )
            top = shortage_areas[0]["state"] if shortage_areas else ""
            return {
                "shortage_areas": shortage_areas[:25],
                "capability_gaps": [
                    {
                        "care_type": "Emergency",
                        "affected_states": [area["state"] for area in shortage_areas[:10]],
                        "gap_severity": "medium",
                    }
                ] if shortage_areas else [],
                "summary": {
                    "critical_shortage_states": sum(1 for area in shortage_areas if area["severity"] == "critical"),
                    "total_shortage_areas": len(shortage_areas),
                    "most_underserved_state": top,
                    "top_missing_care_type": "Emergency" if shortage_areas else "",
                    "dedup_review_count": dedup_summary.get("review_count", 0),
                },
                "skeleton": True,
            }

        user_msg = (
            f"Analyse healthcare shortages across {len(df):,} facilities "
            f"in {len(state_summary)} states.\n\n"
            f"Dedup context: {dedup_summary}\n\n"
            f"State capability summary:\n{pd.DataFrame(state_summary).to_json(orient='records')}\n\n"
            f"Sample records:\n{self._sample(df)}"
        )

        return self._ask(SYSTEM, user_msg)
