"""EvidenceSpecialtyAgent — capability evidence and specialty normalization skeleton."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .base import BaseAgent


CAPABILITY_TERMS = {
    "ICU": ["icu", "intensive care", "ventilator"],
    "NICU": ["nicu", "neonatal", "newborn"],
    "Emergency": ["emergency", "casualty", "trauma", "accident"],
    "Maternity": ["maternity", "obstetric", "gynaecology", "gynecology", "labour"],
    "Oncology": ["oncology", "cancer", "chemotherapy"],
    "Dialysis": ["dialysis", "hemodialysis"],
    "Surgery": ["surgery", "operating theatre", "operation theatre"],
}


class EvidenceSpecialtyAgent(BaseAgent):
    name = "evidence"

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        rows: list[dict[str, Any]] = []
        claim_counts = {"strong": 0, "partial": 0, "weak": 0, "suspicious": 0, "none": 0}
        text_columns = [column for column in ["description", "specialties", "procedure", "equipment", "capability"] if column in df.columns]

        for index, row in df.head(250).fillna("").iterrows():
            blob = " ".join(str(row.get(column, "")) for column in text_columns).lower()
            facility = str(row.get("name", f"row-{index}"))
            for capability, terms in CAPABILITY_TERMS.items():
                matches = [term for term in terms if term in blob]
                if not matches:
                    continue
                has_description = bool(str(row.get("description", "")).strip())
                has_structured = bool(str(row.get("capability", "") or row.get("specialties", "")).strip())
                status = "strong" if has_description and has_structured else "partial" if has_description else "weak"
                claim_counts[status] += 1
                rows.append(
                    {
                        "facility": facility,
                        "capability": capability,
                        "claim_status": status,
                        "matched_terms": matches[:4],
                        "confidence": "high" if status == "strong" else "medium" if status == "partial" else "low",
                        "review_required": status in {"weak", "suspicious"},
                    }
                )

        if not rows:
            claim_counts["none"] = len(df)

        contradictions = []
        for item in rows:
            if item["claim_status"] == "weak":
                contradictions.append(
                    {
                        "facility": item["facility"],
                        "issue": "capability_claim_without_structured_support",
                        "capability": item["capability"],
                    }
                )

        return {
            "claims": rows[:100],
            "contradictions": contradictions[:50],
            "summary": {
                "evaluated_rows": min(len(df), 250),
                "claim_counts": claim_counts,
                "review_claims": sum(1 for row in rows if row["review_required"]),
            },
            "review_required": bool(contradictions),
        }
