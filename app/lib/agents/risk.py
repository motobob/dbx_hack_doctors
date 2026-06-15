"""
RiskAgent — synthesizes dedup + geo + shortage into a risk matrix.

Input : full facilities DataFrame + all upstream agent results
Output: prioritised risk matrix + planning recommendations
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .base import BaseAgent

SYSTEM = """You are a strategic healthcare planning analyst.

You have received outputs from three prior analysis agents:
  - dedup: duplicate facility analysis
  - geo:   geographic quality and coverage gaps
  - shortage: care shortage areas by state

Synthesise these into a final risk assessment and planning recommendations.

Return ONLY valid JSON in this exact shape:
{
  "risks": [
    {
      "risk_id": "R01",
      "priority": "P0|P1|P2",
      "category": "data_quality|coverage_gap|shortage|planning",
      "title": "Short title",
      "description": "2-3 sentences",
      "affected_states": ["..."],
      "affected_care_types": ["..."],
      "root_cause": "dedup|geo|shortage|combined",
      "recommended_action": "...",
      "owner": "Data team|Field team|Planning team|AI agent",
      "confidence": "high|medium|low",
      "estimated_impact_score": 0
    }
  ],
  "executive_summary": "3-5 sentence narrative for planners",
  "top_3_priorities": ["...", "...", "..."],
  "data_readiness_score": 0,
  "planning_readiness_score": 0
}"""


class RiskAgent(BaseAgent):
    name = "risk"

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        dedup_result = upstream.get("dedup", {})
        geo_result = upstream.get("geo", {})
        shortage_result = upstream.get("shortage", {})
        evidence_result = upstream.get("evidence", {})
        review_result = upstream.get("review", {})

        if not self.llm_enabled():
            review_count = review_result.get("summary", {}).get("review_count", 0)
            geo_score = geo_result.get("summary", {}).get("overall_geo_quality_score", 70)
            shortage_count = shortage_result.get("summary", {}).get("total_shortage_areas", 0)
            evidence_reviews = evidence_result.get("summary", {}).get("review_claims", 0)
            data_readiness = max(35, min(95, round((geo_score * 0.4) + (70 * 0.3) + max(0, 100 - review_count * 3) * 0.3)))
            planning_readiness = max(25, min(90, data_readiness - min(25, shortage_count + evidence_reviews // 2)))
            risks = []
            if review_count:
                risks.append(
                    {
                        "risk_id": "R01",
                        "priority": "P0",
                        "category": "data_quality",
                        "title": "Human review queue can change planning counts",
                        "description": f"{review_count} records or clusters need review before final planning counts.",
                        "affected_states": [],
                        "affected_care_types": [],
                        "root_cause": "combined",
                        "recommended_action": "Resolve high-severity review items before using the data for allocation decisions.",
                        "owner": "Data team",
                        "confidence": "medium",
                        "estimated_impact_score": min(100, review_count * 8),
                    }
                )
            if shortage_count:
                risks.append(
                    {
                        "risk_id": "R02",
                        "priority": "P1",
                        "category": "shortage",
                        "title": "Potential care gaps require trust-weighted validation",
                        "description": f"{shortage_count} shortage areas were flagged by the skeleton shortage scan.",
                        "affected_states": [area.get("state", "") for area in shortage_result.get("shortage_areas", [])[:5]],
                        "affected_care_types": ["Emergency", "ICU", "NICU"],
                        "root_cause": "shortage",
                        "recommended_action": "Review sparse regions and validate capability evidence before outreach planning.",
                        "owner": "Planning team",
                        "confidence": "medium",
                        "estimated_impact_score": min(100, shortage_count * 10),
                    }
                )
            return {
                "risks": risks,
                "executive_summary": "Skeleton risk synthesis combines ingestion, QA, dedupe, evidence, geo, shortage, and review-gate signals into a planning readiness view.",
                "top_3_priorities": [risk["title"] for risk in risks[:3]],
                "data_readiness_score": data_readiness,
                "planning_readiness_score": planning_readiness,
                "skeleton": True,
            }

        user_msg = (
            f"Synthesise risk assessment for a healthcare facility dataset "
            f"with {len(df):,} records.\n\n"
            f"=== DEDUP AGENT OUTPUT ===\n"
            f"Summary: {dedup_result.get('summary', {})}\n"
            f"Sample cluster decisions (first 5): {dedup_result.get('clusters', [])[:5]}\n\n"
            f"=== GEO AGENT OUTPUT ===\n"
            f"Summary: {geo_result.get('summary', {})}\n"
            f"Coverage gaps: {geo_result.get('coverage_gaps', [])[:5]}\n\n"
            f"=== SHORTAGE AGENT OUTPUT ===\n"
            f"Summary: {shortage_result.get('summary', {})}\n"
            f"Critical shortage areas: {[a for a in shortage_result.get('shortage_areas', []) if a.get('severity') == 'critical'][:5]}\n\n"
            f"Produce a risk matrix and executive summary for the planning team."
        )

        return self._ask(SYSTEM, user_msg, max_tokens=3000)
