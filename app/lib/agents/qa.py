"""QAProfileAgent — completeness, sparsity, and metadata checks."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .base import BaseAgent


class QAProfileAgent(BaseAgent):
    name = "qa"

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        fields = {
            "identity": ["name"],
            "location": ["address_city", "address_stateOrRegion", "address_zipOrPostcode"],
            "capability": ["specialties", "capability", "description"],
            "provenance": ["source", "url", "source_url"],
            "metadata": ["year_established", "capacity", "doctors"],
        }
        groups: dict[str, dict[str, Any]] = {}
        flags: list[dict[str, Any]] = []
        for group, columns in fields.items():
            present_columns = [column for column in columns if column in df.columns]
            if not present_columns:
                groups[group] = {"score": 0, "present_columns": [], "missing_columns": columns}
                flags.append({"issue": "missing_field_group", "group": group, "severity": "medium"})
                continue
            row_has_any = pd.Series(False, index=df.index)
            for column in present_columns:
                row_has_any = row_has_any | df[column].fillna("").astype(str).str.strip().ne("")
            score = round(float(row_has_any.mean()) * 100) if len(df) else 0
            groups[group] = {
                "score": score,
                "present_columns": present_columns,
                "missing_columns": [column for column in columns if column not in df.columns],
            }
            if score < 70:
                flags.append({"issue": "sparse_field_group", "group": group, "score": score, "severity": "high"})

        suspicious_years = 0
        if "year_established" in df.columns:
            years = pd.to_numeric(df["year_established"], errors="coerce")
            suspicious_years = int(((years < 1800) | (years > 2026)).fillna(False).sum())
            if suspicious_years:
                flags.append({"issue": "suspicious_year_established", "count": suspicious_years, "severity": "medium"})

        overall = round(sum(group["score"] for group in groups.values()) / max(len(groups), 1))
        return {
            "overall_quality_score": overall,
            "field_groups": groups,
            "flags": flags[:50],
            "review_required": any(flag.get("severity") == "high" for flag in flags),
            "summary": {
                "row_count": len(df),
                "flag_count": len(flags),
                "suspicious_years": suspicious_years,
            },
        }
