"""
DedupAgent — two modes:

  1. DEDUP mode (default): identifies true duplicate clusters within the existing
     dataset using LLM judgement.

  2. INGEST mode: triggered when upstream["incoming_records"] (or
     state["context"]["incoming_records"]) is present.  Compares each incoming
     record against the existing dataset and decides:
       - insert   : new facility, not in existing data
       - update   : matches an existing record, incoming data is fresher
       - duplicate: exact or near-exact match, skip
       - review   : ambiguous, needs human check

Input : full facilities DataFrame + optional upstream context
Output: cluster decisions (dedup mode) OR ingestion decisions (ingest mode)
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..json_fields import normalize_jsonish_dataframe
from .base import BaseAgent

# ── DEDUP prompt ──────────────────────────────────────────────────────────────

DEDUP_SYSTEM = """You are a healthcare data quality expert.
You will receive a JSON array of facility records that share a cluster_id,
meaning they were flagged as potential duplicates by a blocking algorithm.

For each cluster decide:
  - "merge"  : records represent the same real-world facility
  - "split"  : records are distinct facilities that happen to look similar
  - "review" : uncertain — human review needed

Return ONLY valid JSON in this exact shape (no prose, no markdown fences):
{
  "clusters": [
    {
      "cluster_id": "...",
      "decision": "merge|split|review",
      "confidence": "high|medium|low",
      "reason": "one sentence",
      "canonical_name": "preferred facility name if merge, else null"
    }
  ],
  "summary": {
    "total_clusters": 0,
    "merge_count": 0,
    "split_count": 0,
    "review_count": 0
  }
}"""


# ── INGEST prompt ─────────────────────────────────────────────────────────────

INGEST_SYSTEM = """You are a healthcare data ingestion expert.

You will receive two JSON arrays:
  - incoming: new records that a user wants to add to the master dataset
  - existing_sample: a sample of records already in the master dataset

For each incoming record decide:
  - "insert"    : genuinely new facility, not present in existing data
  - "update"    : matches an existing record by name/location; incoming data
                  is fresher or fills missing fields — apply as an update
  - "duplicate" : already present with equal or better data — skip
  - "review"    : ambiguous match that needs human inspection

Return ONLY valid JSON in this exact shape (no prose, no markdown fences):
{
  "ingestion_decisions": [
    {
      "incoming_index": 0,
      "incoming_name": "...",
      "decision": "insert|update|duplicate|review",
      "confidence": "high|medium|low",
      "matched_existing_name": "null or name of matched existing record",
      "reason": "one sentence",
      "fields_to_update": ["field1", "field2"]
    }
  ],
  "summary": {
    "total_incoming": 0,
    "insert_count": 0,
    "update_count": 0,
    "duplicate_count": 0,
    "review_count": 0
  }
}"""


class DedupAgent(BaseAgent):
    name = "dedup"
    workflow_ref = "docs/facilities_data_quality.md#3-deduplication-rules"
    rule_families = [
        "exact duplicate",
        "same name/location",
        "enriched update",
        "data removal review",
        "location moved",
    ]

    def _execute(self, df: pd.DataFrame, upstream: dict[str, Any]) -> dict:
        # Ingestion mode: compare incoming records against existing dataset
        incoming = upstream.get("incoming_records")
        if incoming:
            return self._run_ingest(df, incoming)
        return self._run_dedup(df)

    # ── ingest mode ───────────────────────────────────────────────────────────

    def _run_ingest(self, existing_df: pd.DataFrame, incoming: list[dict]) -> dict:
        incoming_df = normalize_jsonish_dataframe(pd.DataFrame(incoming))
        if not self.llm_enabled():
            decisions = []
            existing_names = set(existing_df.get("name", pd.Series(dtype=str)).fillna("").astype(str).str.lower())
            for index, row in incoming_df.head(100).fillna("").iterrows():
                name = str(row.get("name", "")).lower()
                decision = "duplicate" if name and name in existing_names else "insert"
                decisions.append(
                    {
                        "incoming_index": int(index),
                        "incoming_name": row.get("name", ""),
                        "decision": decision,
                        "confidence": "medium",
                        "matched_existing_name": row.get("name", "") if decision == "duplicate" else None,
                        "reason": "Deterministic skeleton match on facility name.",
                        "fields_to_update": [],
                    }
                )
            summary = {
                "total_incoming": len(incoming),
                "insert_count": sum(1 for item in decisions if item["decision"] == "insert"),
                "update_count": 0,
                "duplicate_count": sum(1 for item in decisions if item["decision"] == "duplicate"),
                "review_count": 0,
            }
            return {
                "ingestion_decisions": decisions,
                "summary": summary,
                "mode": "ingest",
                "incoming_count": len(incoming),
                "existing_count": len(existing_df),
                "skeleton": True,
            }

        # Sample existing to stay within token budget
        existing_sample = self._sample(existing_df, n=40)

        # Compact incoming (up to 30 records)
        inc_cols = [c for c in [
            "name", "address_city", "address_stateOrRegion", "address_zipOrPostcode",
            "organization_type", "specialties",
        ] if c in incoming_df.columns]
        inc_sample = incoming_df[inc_cols].head(30).fillna("").to_dict(orient="records")

        user_msg = (
            f"Ingestion request: {len(incoming)} incoming records vs "
            f"{len(existing_df):,} existing records.\n\n"
            f"=== INCOMING RECORDS ===\n{inc_sample}\n\n"
            f"=== EXISTING DATASET SAMPLE ===\n{existing_sample}"
        )

        result = self._ask(INGEST_SYSTEM, user_msg)
        result["mode"] = "ingest"
        result["incoming_count"] = len(incoming)
        result["existing_count"] = len(existing_df)
        return result

    # ── dedup mode ────────────────────────────────────────────────────────────

    def _run_dedup(self, df: pd.DataFrame) -> dict:
        cluster_col = "cluster_id"
        if cluster_col not in df.columns:
            return {
                "clusters": [],
                "summary": {"total_clusters": 0, "merge_count": 0, "split_count": 0, "review_count": 0},
                "skipped": "no cluster_id column",
                "mode": "dedup",
            }

        cluster_counts = df[cluster_col].fillna("").astype(str).value_counts()
        dup_clusters = cluster_counts[cluster_counts > 1].index.tolist()
        dup_clusters = [c for c in dup_clusters if c and c != ""]

        if not dup_clusters:
            return {
                "clusters": [],
                "summary": {"total_clusters": 0, "merge_count": 0, "split_count": 0, "review_count": 0},
                "mode": "dedup",
            }

        if not self.llm_enabled():
            clusters = [
                {
                    "cluster_id": cluster_id,
                    "decision": "review",
                    "confidence": "medium",
                    "reason": "Deterministic skeleton flagged this duplicate cluster for review.",
                    "canonical_name": None,
                }
                for cluster_id in dup_clusters[:20]
            ]
            return {
                "clusters": clusters,
                "summary": {
                    "total_clusters": len(clusters),
                    "merge_count": 0,
                    "split_count": 0,
                    "review_count": len(clusters),
                },
                "total_dup_clusters": len(dup_clusters),
                "evaluated_clusters": len(clusters),
                "mode": "dedup",
                "skeleton": True,
            }

        sample_clusters = dup_clusters[:20]
        cluster_records = (
            df[df[cluster_col].isin(sample_clusters)]
            .fillna("")
            .to_dict(orient="records")
        )
        cols = [c for c in [
            "name", "address_city", "address_stateOrRegion", "cluster_id",
            "description", "specialties",
        ] if c in pd.DataFrame(cluster_records).columns]

        user_msg = (
            f"Evaluate {len(sample_clusters)} duplicate clusters "
            f"(out of {len(dup_clusters)} total) from a healthcare facility dataset.\n\n"
            f"Records:\n{pd.DataFrame(cluster_records)[cols].to_json(orient='records')}"
        )

        result = self._ask(DEDUP_SYSTEM, user_msg)
        result["total_dup_clusters"] = len(dup_clusters)
        result["evaluated_clusters"] = len(sample_clusters)
        result["mode"] = "dedup"
        return result
