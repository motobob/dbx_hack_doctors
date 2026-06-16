"""HumanReviewGateAgent — turns agent uncertainty into review queue signals."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .base import BaseAgent


class HumanReviewGateAgent(BaseAgent):
    name = "review"
    workflow_ref = "agents/ingestion_agent.md#5-sub-agent-c--review-surface-agent"
    rule_families = [
        "proof/reject queue",
        "material changes",
        "human ownership",
        "audit notes",
    ]

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        items: list[dict[str, Any]] = []
        ingestion = upstream.get("ingestion", {})
        qa = upstream.get("qa", {})
        pincode = upstream.get("pincode", {})
        dedup = upstream.get("dedup", {})
        evidence = upstream.get("evidence", {})
        geo = upstream.get("geo", {})

        if ingestion.get("review_required"):
            items.append(
                {
                    "reason": "ingestion_schema_or_column_alignment",
                    "severity": "high",
                    "detail": "Uploaded data needs mapping review before merge.",
                }
            )
        for flag in ingestion.get("row_quality_flags", [])[:20]:
            items.append(
                {
                    "reason": flag.get("issue", "incoming_row_quality"),
                    "severity": flag.get("severity", "medium"),
                    "detail": str(flag),
                    "incoming_index": flag.get("incoming_index"),
                }
            )
        for flag in qa.get("flags", [])[:20]:
            if flag.get("severity") in {"high", "medium"}:
                items.append({"reason": flag.get("issue"), "severity": flag.get("severity"), "detail": str(flag)})

        for item in pincode.get("review_items", [])[:20]:
            items.append(
                {
                    "reason": item.get("issue", "pincode_enrichment_review"),
                    "severity": item.get("severity", "medium"),
                    "detail": item.get("recommendation", str(item)),
                    "pincode": item.get("pin_value"),
                }
            )

        for cluster in dedup.get("clusters", [])[:20]:
            if cluster.get("decision") == "review" or cluster.get("confidence") in {"low", "medium"}:
                items.append(
                    {
                        "reason": "ambiguous_duplicate_cluster",
                        "severity": "high" if cluster.get("confidence") == "low" else "medium",
                        "detail": cluster.get("reason", ""),
                        "cluster_id": cluster.get("cluster_id"),
                    }
                )

        for decision in dedup.get("ingestion_decisions", [])[:50]:
            if decision.get("decision") in {"duplicate", "review"}:
                items.append(
                    {
                        "reason": "incoming_duplicate_or_ambiguous_match",
                        "severity": "high" if decision.get("decision") == "review" else "medium",
                        "detail": decision.get("reason", ""),
                        "incoming_index": decision.get("incoming_index"),
                        "incoming_name": decision.get("incoming_name"),
                        "matched_existing_name": decision.get("matched_existing_name"),
                    }
                )

        for contradiction in evidence.get("contradictions", [])[:20]:
            items.append(
                {
                    "reason": "weak_or_contradictory_capability_evidence",
                    "severity": "medium",
                    "detail": str(contradiction),
                }
            )

        for record in geo.get("flagged_records", [])[:20]:
            items.append(
                {
                    "reason": "borderline_or_suspicious_geocode",
                    "severity": "medium",
                    "detail": record.get("detail", str(record)),
                }
            )

        material_threshold = 70
        review_count = len(items)
        planning_impact = min(100, review_count * 8)
        if planning_impact >= material_threshold:
            items.insert(
                0,
                {
                    "reason": "material_planning_impact",
                    "severity": "high",
                    "detail": f"Review queue impact score {planning_impact} crosses threshold {material_threshold}.",
                },
            )

        return {
            "review_items": items[:100],
            "summary": {
                "review_count": len(items),
                "high_severity": sum(1 for item in items if item.get("severity") == "high"),
                "material_planning_impact_score": planning_impact,
                "material_threshold": material_threshold,
            },
            "review_required": bool(items),
        }
