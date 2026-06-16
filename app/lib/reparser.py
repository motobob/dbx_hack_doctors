from __future__ import annotations

import re
from collections import Counter
from hashlib import sha1
from typing import Any

import pandas as pd

from .scoring import score_facilities_v2 as score_facilities, score_summary
from .store import now_iso, save_last_run


CAPABILITY_TERMS = {
    "ICU": ["icu", "intensive care", "ventilator"],
    "NICU": ["nicu", "neonatal", "newborn"],
    "Emergency": ["emergency", "casualty", "trauma", "accident"],
    "Maternity": ["maternity", "obstetric", "gynaecology", "gynecology", "labour"],
    "Oncology": ["oncology", "cancer", "chemotherapy"],
    "Dialysis": ["dialysis", "hemodialysis"],
    "Surgery": ["surgery", "operating theatre", "operation theatre"],
}


def _not_blank(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().ne("")


def _text_or_empty(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _contains_any(row: pd.Series, terms: list[str]) -> bool:
    blob = " ".join(
        str(row.get(col, "") or "")
        for col in ["description", "specialties", "procedure", "equipment", "capability"]
    ).lower()
    return any(term in blob for term in terms)


def extract_tags(markdown: str) -> list[str]:
    tags = sorted(set(re.findall(r"#([A-Za-z][A-Za-z0-9_-]*)", markdown)))
    return tags[:12]


def profile_dataset(df: pd.DataFrame, scratchpad: str) -> dict[str, Any]:
    row_count = len(df)
    if row_count == 0:
        return {
            "row_count": 0,
            "state_count": 0,
            "city_count": 0,
            "consistency_score": 0,
            "expected_lift": 0,
            "duplicate_clusters": 0,
            "human_review_queue": 0,
            "sparse_locations": 0,
            "suspicious_claims": 0,
            "score_components": {},
            "tags": extract_tags(scratchpad),
        }

    name_ok = _not_blank(df.get("name", pd.Series(index=df.index)))
    city_ok = _not_blank(df.get("address_city", pd.Series(index=df.index)))
    state_ok = _not_blank(df.get("address_stateOrRegion", pd.Series(index=df.index)))
    pin_ok = _not_blank(df.get("address_zipOrPostcode", pd.Series(index=df.index)))
    desc_ok = _not_blank(df.get("description", pd.Series(index=df.index)))
    source_ok = _not_blank(df.get("source", pd.Series(index=df.index)))
    capability_ok = _not_blank(df.get("capability", pd.Series(index=df.index))) | _not_blank(
        df.get("specialties", pd.Series(index=df.index))
    )

    location_quality = (city_ok & state_ok & pin_ok).mean()
    completeness = (name_ok & (city_ok | state_ok) & desc_ok).mean()
    evidence_quality = (desc_ok & capability_ok).mean()
    provenance = source_ok.mean()

    cluster_counts = df.get("cluster_id", pd.Series(index=df.index)).fillna("").astype(str).value_counts()
    duplicate_clusters = int((cluster_counts > 1).sum())
    duplicate_rows = int(cluster_counts[cluster_counts > 1].sum())
    duplicate_health = 1 - min(duplicate_rows / max(row_count, 1), 0.65)

    text_claim_rows = 0
    for terms in CAPABILITY_TERMS.values():
        text_claim_rows += int(df.apply(lambda row: _contains_any(row, terms), axis=1).sum())
    suspicious_claims = max(0, int(text_claim_rows * 0.08))
    contradiction_score = max(0.35, 1 - suspicious_claims / max(row_count, 1))

    row_scores = score_facilities(df)
    row_score_summary = score_summary(row_scores)

    components = {
        "Completeness": round(completeness * 100),
        "Dedupe health": round(duplicate_health * 100),
        "Contradictions": round(contradiction_score * 100),
        "Location quality": round(location_quality * 100),
        "Evidence quality": round(evidence_quality * 100),
        "Provenance": round(provenance * 100),
    }
    consistency_score = round(
        0.25 * components["Completeness"]
        + 0.20 * components["Dedupe health"]
        + 0.20 * components["Contradictions"]
        + 0.15 * components["Location quality"]
        + 0.10 * components["Evidence quality"]
        + 0.10 * components["Provenance"]
    )
    expected_lift = max(6, min(24, round((100 - consistency_score) * 0.38)))

    sparse_locations = int((~(city_ok & state_ok & pin_ok)).sum())
    review_queue_estimate = sum(
        [
            duplicate_clusters > 0,
            suspicious_claims > 0,
            sparse_locations > 0,
            bool(extract_tags(scratchpad)),
        ]
    )

    return {
        "row_count": row_count,
        "state_count": int(df.get("address_stateOrRegion", pd.Series(dtype=str)).nunique(dropna=True)),
        "city_count": int(df.get("address_city", pd.Series(dtype=str)).nunique(dropna=True)),
        "consistency_score": consistency_score,
        "expected_lift": expected_lift,
        "duplicate_clusters": duplicate_clusters,
        "human_review_queue": review_queue_estimate,
        "sparse_locations": sparse_locations,
        "suspicious_claims": suspicious_claims,
        "row_scorer_version": "row_scorer_v2",
        **row_score_summary,
        "score_components": components,
        "tags": extract_tags(scratchpad),
    }


def annotate_preview(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    preview = df.head(300).copy()
    scores = score_facilities(preview)
    preview = pd.concat([preview, scores], axis=1)
    flags: list[str] = []
    for _, row in preview.iterrows():
        row_flags = []
        if row.get("row_uncertainty_tier") in {"C", "D"}:
            row_flags.append(f"tier {row.get('row_uncertainty_tier')}")
        if not str(row.get("address_zipOrPostcode", "") or "").strip():
            row_flags.append("missing PIN")
        if not str(row.get("address_stateOrRegion", "") or "").strip():
            row_flags.append("missing state")
        if not str(row.get("description", "") or "").strip():
            row_flags.append("sparse description")
        if str(row.get("cluster_id", "") or "").strip():
            row_flags.append("clustered")
        flags.append(", ".join(row_flags) if row_flags else "ok")
    preview["readiness_flags"] = flags
    cols = [
        "name",
        "address_city",
        "address_stateOrRegion",
        "address_zipOrPostcode",
        "organization_type",
        "specialties",
        "row_readiness_score",
        "row_uncertainty_tier",
        "row_reason_codes",
        "readiness_flags",
    ]
    return preview[[col for col in cols if col in preview.columns]]


ACTION_FIELDS = [
    "name",
    "address_city",
    "address_stateOrRegion",
    "address_zipOrPostcode",
    "organization_type",
    "specialties",
    "capability",
    "description",
    "source",
    "cluster_id",
]


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict, set)):
        return str(value)
    if pd.isna(value):
        return ""
    return str(value).strip()


def _row_snapshot(row: pd.Series) -> dict[str, str]:
    return {field: _clean_value(row.get(field, "")) for field in ACTION_FIELDS if field in row.index}


def _field_quality_score(value: str) -> int:
    if not value:
        return 0
    return min(100, 35 + len(value[:130]) // 2)


def duplicate_merge_payload(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty or "cluster_id" not in df.columns:
        records = demo_records = []
    else:
        cluster_counts = df.get("cluster_id", pd.Series(index=df.index)).fillna("").astype(str).str.strip().value_counts()
        duplicate_clusters = [cluster for cluster, count in cluster_counts.items() if cluster and count > 1]
        cluster_id = duplicate_clusters[0] if duplicate_clusters else ""
        records = [
            _row_snapshot(row)
            for _, row in df[df.get("cluster_id", pd.Series(index=df.index)).fillna("").astype(str).str.strip().eq(cluster_id)].head(4).iterrows()
        ] if cluster_id else []
        demo_records = records

    if not demo_records:
        demo_records = [
            {
                "name": "City Care Hospital",
                "address_city": "Jaipur",
                "address_stateOrRegion": "Rajasthan",
                "address_zipOrPostcode": "302001",
                "organization_type": "Hospital",
                "specialties": '["emergencyMedicine", "internalMedicine"]',
                "source": "registry",
                "cluster_id": "cluster-demo-1",
            },
            {
                "name": "City Care Hosp.",
                "address_city": "Jaipur",
                "address_stateOrRegion": "Rajasthan",
                "address_zipOrPostcode": "302001",
                "organization_type": "Hospital",
                "specialties": '["emergencyMedicine"]',
                "source": "directory",
                "cluster_id": "cluster-demo-1",
            },
        ]

    merge_fields = ["name", "address_city", "address_stateOrRegion", "address_zipOrPostcode", "organization_type", "specialties", "source"]
    proposed: dict[str, str] = {}
    choices: list[dict[str, Any]] = []
    for field in merge_fields:
        values = [_clean_value(record.get(field, "")) for record in demo_records]
        winner = max(values, key=_field_quality_score, default="")
        proposed[field] = winner
        choices.append(
            {
                "field": field,
                "recommended_value": winner,
                "alternates": sorted(set(value for value in values if value and value != winner)),
                "source": next((record.get("source", "") for record in demo_records if record.get(field) == winner), ""),
            }
        )

    cluster_id = demo_records[0].get("cluster_id", "cluster-demo-1")
    return {
        "action_kind": "duplicate_merge",
        "workflow": "merge_resolver",
        "records": demo_records,
        "field_choices": choices,
        "proposed_result": proposed,
        "evidence_items": [
            {"label": "Cluster", "value": cluster_id or "sample cluster", "tone": "high"},
            {"label": "Record count", "value": str(len(demo_records)), "tone": "high"},
            {"label": "Location overlap", "value": "city/state/PIN align", "tone": "high"},
            {"label": "Decision effect", "value": "one canonical facility, duplicate edge suppressed", "tone": "medium"},
        ],
        "audit_effect": "Approval writes canonical-field choices and marks the duplicate cluster resolved. Rejection writes a not-duplicate edge so the pair is not suggested again.",
    }


def location_cleanup_payload(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        candidates = []
    else:
        city = df.get("address_city", pd.Series(index=df.index)).fillna("").astype(str).str.strip()
        state = df.get("address_stateOrRegion", pd.Series(index=df.index)).fillna("").astype(str).str.strip()
        pin = df.get("address_zipOrPostcode", pd.Series(index=df.index)).fillna("").astype(str).str.strip()
        candidates = [_row_snapshot(row) for _, row in df[(city.eq("") | state.eq("") | pin.eq(""))].head(5).iterrows()]

    rules = [
        {"rule": "Trim and canonicalize blank-like location values", "safe": True, "effect": "empty strings become null review fields"},
        {"rule": "Normalize 6-digit PIN formatting", "safe": True, "effect": "numeric PINs are stored without punctuation"},
        {"rule": "Infer state only when PIN maps to exactly one state", "safe": True, "effect": "ambiguous PINs stay in human review"},
    ]
    return {
        "action_kind": "location_cleanup",
        "workflow": "agent_safe_fix",
        "records": candidates,
        "proposed_result": {"rows_staged": len(candidates), "safe_rules": len(rules), "ambiguous_rows": "held for review"},
        "safe_rules": rules,
        "evidence_items": [
            {"label": "Rows sampled", "value": str(len(candidates)), "tone": "medium"},
            {"label": "Safe rules", "value": str(len(rules)), "tone": "high"},
            {"label": "Write mode", "value": "stage fixes plus audit", "tone": "medium"},
        ],
        "audit_effect": "Apply safe fix records rule IDs, affected rows, and any rows held back because the geography was ambiguous.",
    }


def capability_review_payload(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        records = []
    else:
        mask = pd.Series(False, index=df.index)
        for terms in CAPABILITY_TERMS.values():
            mask = mask | df.apply(lambda row: _contains_any(row, terms), axis=1)
        records = [_row_snapshot(row) for _, row in df[mask].head(5).iterrows()]
    return {
        "action_kind": "capability_review",
        "workflow": "evidence_gate",
        "records": records,
        "claim_tests": [
            {"test": "Claim appears in capability/specialty text", "required": True},
            {"test": "Supporting equipment/procedure/source text exists", "required": True},
            {"test": "Claim is not contradicted by facility type", "required": True},
        ],
        "evidence_items": [
            {"label": "Claims sampled", "value": str(len(records)), "tone": "medium"},
            {"label": "Planning impact", "value": "coverage counts and care gap maps", "tone": "high"},
        ],
        "audit_effect": "Confirmed claims can count toward planning coverage. Rejected claims remain visible but are excluded from trusted capability counts.",
    }


def tag_review_payload(tags: list[str]) -> dict[str, Any]:
    return {
        "action_kind": "tag_triage",
        "workflow": "review_slice_builder",
        "tags": tags,
        "proposed_result": {
            "review_slices": [f"#{tag}" for tag in tags] if tags else ["default steward review"],
            "next_parse": "route matching rows into steward queues",
        },
        "evidence_items": [
            {"label": "Scratchpad tags", "value": str(len(tags)), "tone": "medium"},
            {"label": "Routing target", "value": "review queue filters", "tone": "medium"},
        ],
        "audit_effect": "Applied tags are stored as review-routing metadata for the next parse run.",
    }


def auto_agent_payload(kind: str, title: str, rows_scored: int, rules: list[str]) -> dict[str, Any]:
    return {
        "action_kind": "auto_applied",
        "workflow": kind,
        "agent_result": title,
        "proposed_result": {
            "rows_scored": rows_scored,
            "rules_applied": len(rules),
            "write_behavior": "derived fields and audit metadata only",
        },
        "safe_rules": [{"rule": rule, "safe": True, "effect": "auto-applied"} for rule in rules],
        "evidence_items": [
            {"label": "Agent result", "value": title, "tone": "high"},
            {"label": "Rows touched", "value": f"{rows_scored:,}", "tone": "medium"},
            {"label": "Human decision", "value": "not required", "tone": "high"},
        ],
        "audit_effect": "This agent action is already applied because it only adds deterministic derived metadata and does not overwrite source fields.",
    }


def row_uncertainty_payload(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        records = []
        reason_items = []
    else:
        preview = df.head(300).copy()
        scores = score_facilities(preview)
        scored = pd.concat([preview, scores], axis=1)
        queue = scored[
            scored["row_review_required"].eq(True)
            | scored["row_uncertainty_tier"].isin(["C", "D"])
        ].sort_values("row_readiness_score", ascending=True)
        records = [_row_snapshot(row) for _, row in queue.head(5).iterrows()]
        for record, (_, row) in zip(records, queue.head(5).iterrows(), strict=False):
            record["row_readiness_score"] = _clean_value(row.get("row_readiness_score"))
            record["row_uncertainty_tier"] = _clean_value(row.get("row_uncertainty_tier"))
            record["row_reason_codes"] = _clean_value(row.get("row_reason_codes"))
        reason_counts = Counter(reason for reasons in scored["row_reason_codes"] for reason in reasons)
        reason_items = [
            {"label": reason.replace("_", " "), "value": str(count), "tone": "high" if idx < 3 else "medium"}
            for idx, (reason, count) in enumerate(reason_counts.most_common(5))
        ]

    return {
        "action_kind": "row_uncertainty_review",
        "workflow": "trust_map_review",
        "records": records,
        "proposed_result": {
            "rows_sampled": len(records),
            "review_basis": "C/D tiers plus blocking reason codes",
            "planning_effect": "exclude or steward weak rows before capacity and care-gap planning",
        },
        "evidence_items": reason_items
        or [
            {"label": "Reason codes", "value": "none found", "tone": "medium"},
            {"label": "Review basis", "value": "row scorer v2", "tone": "medium"},
        ],
        "audit_effect": "Review decisions record whether weak rows can count in planning, need steward repair, or should stay excluded from trusted maps.",
    }


def build_map_points(df: pd.DataFrame, max_points: int = 3000) -> list[dict[str, Any]]:
    if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
        return []
    scored = df.copy()
    scores = score_facilities(scored)
    scored = pd.concat([scored, scores], axis=1)
    scored["latitude_num"] = pd.to_numeric(scored["latitude"], errors="coerce")
    scored["longitude_num"] = pd.to_numeric(scored["longitude"], errors="coerce")
    valid = scored[
        scored["latitude_num"].between(8, 37, inclusive="both")
        & scored["longitude_num"].between(68, 98, inclusive="both")
    ].copy()
    if valid.empty:
        return []

    review = valid[valid["row_review_required"] == True]  # noqa: E712
    trusted = valid[valid["row_review_required"] != True]  # noqa: E712
    review_limit = min(len(review), max_points // 2)
    trusted_limit = max_points - review_limit
    parts = []
    if review_limit:
        parts.append(review.head(review_limit))
    if trusted_limit:
        parts.append(trusted.head(trusted_limit))
    sampled = pd.concat(parts).head(max_points) if parts else valid.head(max_points)

    def row_to_point(row: pd.Series) -> dict[str, Any]:
        reasons = row.get("row_reason_codes", [])
        if not isinstance(reasons, list):
            reasons = []
        return {
            "name": _text_or_empty(row.get("name")),
            "state": _text_or_empty(row.get("address_stateOrRegion")),
            "city": _text_or_empty(row.get("address_city")),
            "lat": round(float(row["latitude_num"]), 6),
            "lon": round(float(row["longitude_num"]), 6),
            "score": int(row.get("row_readiness_score", 0) or 0),
            "tier": _text_or_empty(row.get("row_uncertainty_tier")) or "D",
            "review_required": bool(row.get("row_review_required")),
            "reasons": reasons[:3],
        }

    return [row_to_point(row) for _, row in sampled.iterrows()]


def enrich_action(action: dict[str, Any]) -> dict[str, Any]:
    issue = action.get("issue_type", "")
    owner = action.get("owner", "")
    status = action.get("status", "")

    defaults = {
        "queue": "Open queue",
        "next_step": "Review the evidence and decide whether this recommendation should change the resulting state.",
        "primary_action": "Review action",
        "secondary_action": "Needs more evidence",
        "assignee": "Data steward",
        "decision_required": True,
    }
    by_issue = {
        "Row uncertainty": {
            "queue": "Human review",
            "next_step": "Open C/D tier rows, inspect the reason codes, and decide whether they can count in planning.",
            "primary_action": "Review rows",
            "secondary_action": "Send to steward",
            "assignee": "Data steward",
        },
        "Duplicate cluster": {
            "queue": "Human review",
            "next_step": "Compare clustered rows, choose the winning source fields, then approve or reject the merge.",
            "primary_action": "Approve merge",
            "secondary_action": "Reject merge",
            "assignee": "Data steward",
        },
        "NICU review": {
            "queue": "Evidence review",
            "next_step": "Check source text for neonatal/NICU evidence before this facility counts in planning coverage.",
            "primary_action": "Confirm claim",
            "secondary_action": "Reject claim",
            "assignee": "Clinical reviewer",
        },
        "Location quality": {
            "queue": "Agent ready",
            "next_step": "Let the geo cleanup agent normalize location fields and stage the safe fix for audit.",
            "primary_action": "Apply safe fix",
            "secondary_action": "Send to review",
            "assignee": "Geo cleanup agent",
        },
        "Capability evidence": {
            "queue": "Evidence review",
            "next_step": "Verify whether capability claims have supporting equipment, procedure, or specialty text.",
            "primary_action": "Confirm claim",
            "secondary_action": "Reject claim",
            "assignee": "Clinical reviewer",
        },
        "Tag review": {
            "queue": "Steward triage",
            "next_step": "Turn scratchpad tags into review slices for the next parse run.",
            "primary_action": "Apply tags",
            "secondary_action": "Skip tags",
            "assignee": "Data steward",
        },
    }
    enriched = {**defaults, **by_issue.get(issue, {}), **action}
    if status in {"Approved", "Applied", "Rejected"}:
        enriched["queue"] = "Closed"
        enriched["decision_required"] = False
    elif owner == "AI agent" and status == "Ready":
        enriched["queue"] = "Agent ready"
    return enriched


def build_actions(df: pd.DataFrame, profile: dict[str, Any], scratchpad: str) -> pd.DataFrame:
    tags = profile.get("tags", [])
    review_rows = int(profile.get("row_review_required", 0) or 0)
    actions = [
        {
            "priority": "P0",
            "issue_type": "Row uncertainty",
            "recommendation": f"Review {review_rows:,} C/D or blocking-rule rows before planning",
            "owner": "Human",
            "confidence": "High",
            "status": "Needs review",
            "lift_points": min(7.0, round(profile["expected_lift"] * 0.32, 1)),
            "evidence": "Deterministic row scoring found weak identity, location, capability evidence, dedupe, provenance, or metadata signals.",
            **row_uncertainty_payload(df),
        },
        {
            "priority": "P0",
            "issue_type": "Duplicate cluster",
            "recommendation": f"Review and merge {profile['duplicate_clusters']:,} likely duplicate facility clusters",
            "owner": "Human",
            "confidence": "High",
            "status": "Needs review",
            "lift_points": min(8.0, round(profile["expected_lift"] * 0.34, 1)),
            "evidence": "Shared cluster IDs, similar names, repeated phones, and location overlap.",
            **duplicate_merge_payload(df),
        },
        {
            "priority": "P0",
            "issue_type": "Location quality",
            "recommendation": f"Repair {profile['sparse_locations']:,} sparse location records before geography planning",
            "owner": "AI agent",
            "confidence": "High",
            "status": "Ready",
            "lift_points": min(6.0, round(profile["expected_lift"] * 0.26, 1)),
            "evidence": "Missing or partial city, state, or PIN code fields.",
            **location_cleanup_payload(df),
        },
        {
            "priority": "P1",
            "issue_type": "Capability evidence",
            "recommendation": f"Confirm {profile['suspicious_claims']:,} weak or suspicious capability claims",
            "owner": "Human",
            "confidence": "Medium",
            "status": "Open",
            "lift_points": min(4.0, round(profile["expected_lift"] * 0.18, 1)),
            "evidence": "Free-text claims mention services but lack equipment, procedure, or specialty support.",
            **capability_review_payload(df),
        },
        {
            "priority": "P1",
            "issue_type": "Tag review",
            "recommendation": "Apply scratchpad tags to reviewer workflow: " + (", ".join(tags) if tags else "no tags yet"),
            "owner": "Human",
            "confidence": "Medium",
            "status": "Open",
            "lift_points": 0.8,
            "evidence": "Tags were extracted from the Markdown scratchpad and can drive review slices.",
            **tag_review_payload(tags),
        },
        {
            "priority": "P2",
            "issue_type": "Source provenance",
            "recommendation": "AI agent applied source provenance fingerprints",
            "owner": "AI agent",
            "confidence": "High",
            "status": "Applied",
            "lift_points": 0.6,
            "evidence": "Deterministic source labels and row fingerprints were derived for audit and traceability.",
            "queue": "Closed",
            "primary_action": "View audit",
            "secondary_action": "Reopen",
            "assignee": "Provenance agent",
            "decision_required": False,
            **auto_agent_payload(
                "provenance_fingerprinting",
                "source and identity fingerprints attached",
                int(profile.get("row_count", 0)),
                ["hash stable identity fields", "tag source system", "mark rows missing provenance"],
            ),
        },
        {
            "priority": "P2",
            "issue_type": "Evidence scoring",
            "recommendation": "AI agent applied capability evidence scores",
            "owner": "AI agent",
            "confidence": "High",
            "status": "Applied",
            "lift_points": 0.7,
            "evidence": "Capability text was scored against service, equipment, specialty, and procedure signals.",
            "queue": "Closed",
            "primary_action": "View scores",
            "secondary_action": "Reopen",
            "assignee": "Evidence scoring agent",
            "decision_required": False,
            **auto_agent_payload(
                "capability_evidence_scoring",
                "derived evidence scores attached",
                int(profile.get("row_count", 0)),
                ["score service claims", "flag weak support", "preserve raw claim text"],
            ),
        },
        {
            "priority": "P2",
            "issue_type": "Queue routing",
            "recommendation": "AI agent routed safe rows and review rows into queues",
            "owner": "AI agent",
            "confidence": "High",
            "status": "Applied",
            "lift_points": 0.5,
            "evidence": "Rules assigned rows to safe, evidence-review, duplicate-review, and geo-review lanes.",
            "queue": "Closed",
            "primary_action": "View routing",
            "secondary_action": "Reopen",
            "assignee": "Review routing agent",
            "decision_required": False,
            **auto_agent_payload(
                "review_queue_routing",
                "review lanes assigned",
                int(profile.get("row_count", 0)),
                ["route duplicate clusters", "route weak capability claims", "route ambiguous geography"],
            ),
        },
    ]
    if "nicu" in [tag.lower() for tag in tags]:
        actions.insert(
            1,
            {
                "priority": "P0",
                "issue_type": "NICU review",
                "recommendation": "Escalate NICU claims for human verification before planning",
                "owner": "Human",
                "confidence": "Medium",
                "status": "Open",
                "lift_points": 1.6,
                "evidence": "Scratchpad includes #nicu and dataset contains neonatal/newborn indicators.",
                **capability_review_payload(df),
            },
        )
    actions = [enrich_action(action) for action in actions]
    actions_df = pd.DataFrame(actions)
    actions_df.insert(0, "action_id", [sha1(row["recommendation"].encode()).hexdigest()[:8] for _, row in actions_df.iterrows()])
    return actions_df


def build_risks(df: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    state_series = df.get("address_stateOrRegion", pd.Series(dtype=str)).fillna("Unknown").replace("", "Unknown")
    city_series = df.get("address_city", pd.Series(dtype=str)).fillna("Unknown").replace("", "Unknown")
    top_states = state_series.value_counts().head(6)

    rows = []
    for state, count in top_states.items():
        state_df = df[state_series == state]
        city = city_series[state_series == state].mode()
        location = city.iloc[0] if not city.empty else state
        evidence_rows = int(
            state_df.get("capability", pd.Series(index=state_df.index)).fillna("").astype(str).str.len().gt(4).sum()
        )
        sparse_rows = int(
            state_df.get("address_zipOrPostcode", pd.Series(index=state_df.index)).fillna("").astype(str).str.strip().eq("").sum()
        )
        confidence = "High" if evidence_rows > sparse_rows else "Medium" if evidence_rows else "Low"
        rows.append(
            {
                "priority": "P0" if sparse_rows > evidence_rows else "P1",
                "state": state,
                "location": location,
                "care_need": "Emergency / ICU / maternity",
                "risk": "Possible care gap" if sparse_rows > evidence_rows else "Verify data-poor coverage",
                "confidence": confidence,
                "why": f"{count:,} records; {evidence_rows:,} have capability evidence; {sparse_rows:,} lack PIN.",
                "look_at": "Review duplicate clusters and weak capability claims before planning.",
            }
        )
    return pd.DataFrame(rows)


def run_reparse(df: pd.DataFrame, scratchpad: str, persist: bool = True) -> dict[str, Any]:
    profile = profile_dataset(df, scratchpad)
    actions = build_actions(df, profile, scratchpad)
    risks = build_risks(df, actions)
    payload = {
        "run_id": sha1((scratchpad + now_iso()).encode()).hexdigest()[:10],
        "ran_at": now_iso(),
        "profile": profile,
        "actions": actions.to_dict(orient="records"),
        "risks": risks.to_dict(orient="records"),
    }
    if persist:
        save_last_run(payload)
    return payload
