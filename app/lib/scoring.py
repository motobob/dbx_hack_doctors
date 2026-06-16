from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

import pandas as pd


INDIA_LAT_MIN = 8
INDIA_LAT_MAX = 37
INDIA_LON_MIN = 68
INDIA_LON_MAX = 98

CAPABILITY_TERMS = {
    "ICU": ["icu", "intensive care", "ventilator"],
    "NICU": ["nicu", "neonatal", "newborn"],
    "Emergency": ["emergency", "casualty", "trauma", "accident"],
    "Maternity": ["maternity", "obstetric", "gynaecology", "gynecology", "labour"],
    "Oncology": ["oncology", "cancer", "chemotherapy"],
    "Dialysis": ["dialysis", "hemodialysis"],
    "Surgery": ["surgery", "operating theatre", "operation theatre"],
}

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if pd.isna(value):
        return ""
    return str(value).strip()


def _present(row: pd.Series, field: str) -> bool:
    return bool(_text(row.get(field)))


def _score_to_tier(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def _try_float(value: Any) -> float | None:
    try:
        text = _text(value).replace("°", "")
        text = re.sub(r"\s*[NSEW]\s*$", "", text, flags=re.IGNORECASE).strip()
        return float(text)
    except Exception:
        return None


def _looks_like_json_junk(value: str) -> bool:
    return value.startswith("[") or value.startswith("{") or value.lower() in {"nan", "none", "null"}


def _arrayish_signal(value: str) -> bool:
    if not value:
        return False
    if value in {"[]", '[""]'}:
        return False
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            return bool(parsed)
        except Exception:
            return True
    return len(value) > 3


def _json_array_items(value: Any) -> list[str] | None:
    text = _text(value)
    if not text:
        return []
    if not text.startswith("["):
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    if not isinstance(parsed, list):
        return None
    return [str(item).strip() for item in parsed if str(item).strip()]


def _array_count(row: pd.Series, field: str) -> int:
    items = _json_array_items(row.get(field))
    if items is None:
        return 0
    return len(items)


def _distinct_array_count(row: pd.Series, field: str) -> int:
    items = _json_array_items(row.get(field))
    if items is None:
        return 0
    return len(set(item.lower() for item in items))


def _sentinel(value: Any) -> bool:
    return _text(value).lower() in {"kie", "nan", "none", "null", "na", "n/a"}


def _cap(score: int, caps: list[int]) -> int:
    if not caps:
        return score
    return min(score, min(caps))


def _component_integrity_v2(row: pd.Series) -> tuple[int, list[str], list[int]]:
    score = 100
    reasons: list[str] = []
    caps: list[int] = []
    unique_id = _text(row.get("unique_id"))
    name = _text(row.get("name"))

    if not unique_id or not UUID_RE.match(unique_id):
        score -= 45
        caps.append(55)
        reasons.append("invalid_or_missing_uuid")
    if not name:
        score -= 80
        caps.append(30)
        reasons.append("missing_name")
    elif _looks_like_json_junk(name):
        score -= 85
        caps.append(25)
        reasons.append("name_looks_like_scraper_payload")
    elif len(name) < 3 or len(name) > 140:
        score -= 25
        reasons.append("suspicious_name_length")

    if _text(row.get("address_city")).lower() == "kie":
        score -= 80
        caps.append(30)
        reasons.append("column_shift_city_sentinel")
    if _text(row.get("source")).lower() == "kie":
        score -= 18
        reasons.append("source_sentinel_kie")

    for field in ["source_types", "source_ids", "phone_numbers", "websites", "source_urls", "specialties", "procedure", "equipment", "capability"]:
        raw = _text(row.get(field))
        if raw and _json_array_items(raw) is None:
            score -= 8
            reasons.append(f"malformed_array_{field}")

    return max(0, _cap(score, caps)), reasons, caps


def _component_location_v2(row: pd.Series) -> tuple[int, list[str], list[int]]:
    score = 100
    reasons: list[str] = []
    caps: list[int] = []
    state = _text(row.get("address_stateOrRegion"))
    city = _text(row.get("address_city"))
    pin = _text(row.get("address_zipOrPostcode"))
    lat = _try_float(row.get("latitude"))
    lon = _try_float(row.get("longitude"))

    if not state or _sentinel(state):
        score -= 35
        reasons.append("missing_or_sentinel_state")
    if not city or _sentinel(city):
        score -= 25
        reasons.append("missing_or_sentinel_city")
    if not re.fullmatch(r"\d{6}", pin):
        score -= 35 if pin else 30
        reasons.append("invalid_pin_format" if pin else "missing_pin")
    if lat is None or lon is None:
        score -= 25
        reasons.append("missing_coordinates")
    elif INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX and INDIA_LON_MIN <= lon <= INDIA_LON_MAX:
        pass
    elif INDIA_LAT_MIN <= lon <= INDIA_LAT_MAX and INDIA_LON_MIN <= lat <= INDIA_LON_MAX:
        score -= 45
        caps.append(65)
        reasons.append("likely_swapped_coordinates")
    else:
        score -= 70
        caps.append(45)
        reasons.append("coordinates_outside_india")
    if lat is not None and lon is not None and abs(lat - lon) < 0.00001:
        score -= 35
        reasons.append("lat_equals_lon")

    return max(0, _cap(score, caps)), reasons, caps


def _component_provenance_v2(row: pd.Series) -> tuple[int, list[str], list[int]]:
    score = 100
    reasons: list[str] = []
    caps: list[int] = []
    source = _text(row.get("source"))
    source_urls_count = _array_count(row, "source_urls")
    websites_count = _array_count(row, "websites")
    source_ids_count = _array_count(row, "source_ids")
    source_types_count = _array_count(row, "source_types")

    if not source:
        score -= 40
        reasons.append("missing_source")
    elif _sentinel(source):
        score -= 45
        caps.append(88)
        reasons.append("source_sentinel_kie")

    if not source_urls_count and not websites_count and not _present(row, "officialWebsite"):
        score -= 40
        reasons.append("missing_source_url")
    if source_urls_count > 20:
        score -= 24
        caps.append(82)
        reasons.append("source_url_bloat")
    if source_ids_count > 20 or source_types_count > 20:
        score -= 18
        caps.append(85)
        reasons.append("source_lineage_bloat")

    return max(0, _cap(score, caps)), reasons, caps


def _component_bloat_v2(row: pd.Series) -> tuple[int, list[str], list[int]]:
    score = 100
    reasons: list[str] = []
    caps: list[int] = []
    counts = {
        "specialties": _array_count(row, "specialties"),
        "phone_numbers": _array_count(row, "phone_numbers"),
        "websites": _array_count(row, "websites"),
        "source_urls": _array_count(row, "source_urls"),
        "source_ids": _array_count(row, "source_ids"),
        "capability": _array_count(row, "capability"),
        "procedure": _array_count(row, "procedure"),
        "equipment": _array_count(row, "equipment"),
    }
    if counts["specialties"] > 20:
        score -= 30
        caps.append(82)
        reasons.append("specialty_bloat")
    if counts["phone_numbers"] > 10:
        score -= 18
        caps.append(85)
        reasons.append("phone_bloat")
    if counts["source_urls"] > 20 or counts["source_ids"] > 20:
        score -= 24
        caps.append(82)
        reasons.append("source_bloat")
    if counts["capability"] > 30 or counts["procedure"] > 40 or counts["equipment"] > 40:
        score -= 16
        caps.append(86)
        reasons.append("claim_bloat")

    specialties = _json_array_items(row.get("specialties")) or []
    if len(specialties) > 10:
        distinct = _distinct_array_count(row, "specialties")
        if distinct / max(len(specialties), 1) < 0.65:
            score -= 18
            reasons.append("repeated_specialty_scrape")

    heavy_fields = sum(1 for value in counts.values() if value > 20)
    if heavy_fields >= 3:
        score -= 26
        caps.append(72)
        reasons.append("possible_merged_mega_record")

    return max(0, _cap(score, caps)), reasons, caps


def _component_capability_v2(row: pd.Series) -> tuple[int, list[str], list[int]]:
    score = 100
    reasons: list[str] = []
    caps: list[int] = []
    description = _text(row.get("description"))
    specialties = _text(row.get("specialties"))
    capability = _text(row.get("capability"))
    procedure = _text(row.get("procedure"))
    equipment = _text(row.get("equipment"))
    blob = " ".join([description, specialties, capability, procedure, equipment]).lower()
    has_structured = bool(_json_array_items(specialties)) or bool(_json_array_items(capability))
    has_support = bool(_json_array_items(procedure)) or bool(_json_array_items(equipment))
    matched = [name for name, terms in CAPABILITY_TERMS.items() if any(term in blob for term in terms)]

    if not has_structured:
        score -= 35
        reasons.append("missing_structured_capability")
    if not description:
        score -= 25
        reasons.append("sparse_description")
    if matched and not has_support and not description:
        score -= 35
        caps.append(60)
        reasons.append("claim_without_evidence")
    elif matched and not has_support:
        score -= 15
        reasons.append("claim_lacks_procedure_or_equipment_support")
    if not matched and not has_structured:
        score -= 20
        reasons.append("no_capability_signal")

    return max(0, _cap(score, caps)), reasons, caps


def _component_metadata_v2(row: pd.Series) -> tuple[int, list[str], list[int]]:
    score = 100
    reasons: list[str] = []
    caps: list[int] = []
    year = _try_float(row.get("yearEstablished") or row.get("year_established"))
    doctors = _try_float(row.get("numberDoctors") or row.get("doctors"))
    capacity = _try_float(row.get("capacity"))

    if year is not None and not (1800 <= year <= 2026):
        score -= 35
        reasons.append("invalid_year_established")
    for field_name, value in [("numberDoctors", doctors), ("capacity", capacity)]:
        raw = _text(row.get(field_name))
        if raw and value is None:
            score -= 22
            reasons.append(f"invalid_{field_name}")
    if doctors is not None and doctors > 5000:
        score -= 18
        reasons.append("implausible_numberDoctors")
    if capacity is not None and capacity > 10000:
        score -= 18
        reasons.append("implausible_capacity")

    return max(0, _cap(score, caps)), reasons, caps


def row_scorer_v2(row: pd.Series, cluster_counts: Counter[str] | None = None) -> dict[str, Any]:
    cluster_counts = cluster_counts or Counter()
    dedupe_score, dedupe_reasons = _component_dedupe(row, cluster_counts)
    components_v2 = {
        "integrity": _component_integrity_v2(row),
        "location_coherence": _component_location_v2(row),
        "provenance_trust": _component_provenance_v2(row),
        "bloat_contamination": _component_bloat_v2(row),
        "capability_evidence": _component_capability_v2(row),
        "dedupe": (dedupe_score, dedupe_reasons, []),
        "metadata_validity": _component_metadata_v2(row),
    }
    component_scores = {key: value[0] for key, value in components_v2.items()}
    reason_codes = sorted({reason for _, reasons, _ in components_v2.values() for reason in reasons})
    caps = [cap for _, _, component_caps in components_v2.values() for cap in component_caps]
    score = round(
        0.20 * component_scores["integrity"]
        + 0.20 * component_scores["location_coherence"]
        + 0.17 * component_scores["provenance_trust"]
        + 0.15 * component_scores["bloat_contamination"]
        + 0.15 * component_scores["capability_evidence"]
        + 0.08 * component_scores["dedupe"]
        + 0.05 * component_scores["metadata_validity"]
    )
    severe_reasons = {
        "missing_name",
        "name_looks_like_scraper_payload",
        "column_shift_city_sentinel",
        "coordinates_outside_india",
        "invalid_or_missing_uuid",
        "possible_merged_mega_record",
    }
    if "source_sentinel_kie" in reason_codes and ("source_bloat" in reason_codes or "specialty_bloat" in reason_codes):
        caps.append(78)
        reason_codes.append("sentinel_plus_bloat")
    score = _cap(max(0, score), caps)
    tier = _score_to_tier(score)
    review_required = tier in {"C", "D"} or bool(severe_reasons.intersection(reason_codes))
    return {
        "row_readiness_score": score,
        "row_uncertainty_tier": tier,
        "row_review_required": review_required,
        "row_reason_codes": sorted(set(reason_codes)),
        "component_scores": component_scores,
        "scorer_version": "row_scorer_v2",
    }


def score_facilities_v2(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "row_readiness_score",
                "row_uncertainty_tier",
                "row_review_required",
                "row_reason_codes",
                "component_scores",
                "scorer_version",
            ]
        )
    cluster_counts = Counter(df.get("cluster_id", pd.Series(index=df.index)).fillna("").astype(str))
    rows = [row_scorer_v2(row, cluster_counts) for _, row in df.iterrows()]
    return pd.DataFrame(rows, index=df.index)


def _component_identity(row: pd.Series) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    name = _text(row.get("name"))
    if name:
        score += 60
        if 3 <= len(name) <= 120 and not _looks_like_json_junk(name):
            score += 20
        else:
            reasons.append("suspicious_name")
    else:
        reasons.append("missing_name")
    if _present(row, "organization_type") or _present(row, "facilityTypeId"):
        score += 20
    else:
        reasons.append("missing_facility_type")
    return min(score, 100), reasons


def _component_location(row: pd.Series) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    state = _text(row.get("address_stateOrRegion"))
    city = _text(row.get("address_city"))
    pin = _text(row.get("address_zipOrPostcode"))
    lat = _try_float(row.get("latitude"))
    lon = _try_float(row.get("longitude"))

    if state:
        score += 20
    else:
        reasons.append("missing_state")
    if city:
        score += 15
    else:
        reasons.append("missing_city")
    if re.fullmatch(r"\d{6}", pin):
        score += 20
    elif pin:
        score += 8
        reasons.append("invalid_pin_format")
    else:
        reasons.append("missing_pin")

    if lat is not None and lon is not None:
        score += 20
        if INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX and INDIA_LON_MIN <= lon <= INDIA_LON_MAX:
            score += 25
        elif INDIA_LAT_MIN <= lon <= INDIA_LAT_MAX and INDIA_LON_MIN <= lat <= INDIA_LON_MAX:
            score += 10
            reasons.append("likely_swapped_coordinates")
        else:
            reasons.append("coordinates_outside_india")
    else:
        reasons.append("missing_coordinates")

    return min(score, 100), reasons


def _component_capability(row: pd.Series) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    description = _text(row.get("description"))
    specialties = _text(row.get("specialties"))
    capability = _text(row.get("capability"))
    procedure = _text(row.get("procedure"))
    equipment = _text(row.get("equipment"))
    blob = " ".join([description, specialties, capability, procedure, equipment]).lower()

    has_description = bool(description)
    has_structured = _arrayish_signal(specialties) or _arrayish_signal(capability)
    has_support = _arrayish_signal(procedure) or _arrayish_signal(equipment)
    matched = [name for name, terms in CAPABILITY_TERMS.items() if any(term in blob for term in terms)]

    if has_structured:
        score += 35
    else:
        reasons.append("missing_structured_capability")
    if has_description:
        score += 25
    else:
        reasons.append("sparse_description")
    if has_support:
        score += 20
    if matched:
        score += 20
        if has_description and not has_structured and not has_support:
            reasons.append("text_claim_without_support")
    elif not has_structured:
        reasons.append("no_capability_signal")

    return min(score, 100), reasons


def _component_dedupe(row: pd.Series, cluster_counts: Counter[str]) -> tuple[int, list[str]]:
    cluster_id = _text(row.get("cluster_id"))
    if not cluster_id:
        return 100, []
    cluster_size = cluster_counts.get(cluster_id, 1)
    if cluster_size <= 1:
        return 95, []
    if cluster_size <= 3:
        return 70, ["duplicate_cluster"]
    return 45, ["large_duplicate_cluster"]


def _component_provenance(row: pd.Series) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if _present(row, "source"):
        score += 35
    else:
        reasons.append("missing_source")
    if _present(row, "source_urls") or _present(row, "websites") or _present(row, "officialWebsite"):
        score += 35
    else:
        reasons.append("missing_source_url")
    if _present(row, "source_types") or _present(row, "source_ids"):
        score += 20
    if _present(row, "recency_of_page_update") or _present(row, "post_metrics_most_recent_social_media_post_date"):
        score += 10
    return min(score, 100), reasons


def _component_metadata(row: pd.Series) -> tuple[int, list[str]]:
    score = 100
    reasons: list[str] = []
    year = _try_float(row.get("yearEstablished") or row.get("year_established"))
    doctors = _try_float(row.get("numberDoctors") or row.get("doctors"))
    capacity = _try_float(row.get("capacity"))

    if year is not None and not (1800 <= year <= 2026):
        score -= 20
        reasons.append("invalid_year_established")
    for field_name, value in [("numberDoctors", doctors), ("capacity", capacity)]:
        raw = _text(row.get(field_name))
        if raw and value is None:
            score -= 15
            reasons.append(f"invalid_{field_name}")

    for field_name in ["procedure", "equipment", "capability", "specialties"]:
        raw = _text(row.get(field_name))
        if raw and not raw.startswith("["):
            score -= 10
            reasons.append(f"non_array_{field_name}")

    return max(score, 0), reasons


def score_facility_row(row: pd.Series, cluster_counts: Counter[str] | None = None) -> dict[str, Any]:
    cluster_counts = cluster_counts or Counter()
    components = {
        "identity": _component_identity(row),
        "location": _component_location(row),
        "capability_evidence": _component_capability(row),
        "dedupe": _component_dedupe(row, cluster_counts),
        "provenance": _component_provenance(row),
        "metadata": _component_metadata(row),
    }
    component_scores = {key: value[0] for key, value in components.items()}
    reason_codes = sorted({reason for _, reasons in components.values() for reason in reasons})
    score = round(
        0.20 * component_scores["identity"]
        + 0.25 * component_scores["location"]
        + 0.20 * component_scores["capability_evidence"]
        + 0.15 * component_scores["dedupe"]
        + 0.10 * component_scores["provenance"]
        + 0.10 * component_scores["metadata"]
    )
    tier = _score_to_tier(score)
    blocking_reasons = {
        "missing_name",
        "coordinates_outside_india",
        "likely_swapped_coordinates",
        "large_duplicate_cluster",
        "text_claim_without_support",
    }
    review_required = tier in {"C", "D"} or bool(blocking_reasons.intersection(reason_codes))
    return {
        "row_readiness_score": score,
        "row_uncertainty_tier": tier,
        "row_review_required": review_required,
        "row_reason_codes": reason_codes,
        "component_scores": component_scores,
    }


def score_facilities(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "row_readiness_score",
                "row_uncertainty_tier",
                "row_review_required",
                "row_reason_codes",
                "component_scores",
            ]
        )
    cluster_counts = Counter(df.get("cluster_id", pd.Series(index=df.index)).fillna("").astype(str))
    rows = [score_facility_row(row, cluster_counts) for _, row in df.iterrows()]
    return pd.DataFrame(rows, index=df.index)


def score_summary(scores: pd.DataFrame) -> dict[str, Any]:
    if scores.empty:
        return {
            "row_readiness_avg": 0,
            "row_review_required": 0,
            "tier_counts": {"A": 0, "B": 0, "C": 0, "D": 0},
            "score_distribution": [],
            "top_reason_codes": [],
        }
    tier_counts = {tier: int((scores["row_uncertainty_tier"] == tier).sum()) for tier in ["A", "B", "C", "D"]}
    bins = [(0, 49), (50, 69), (70, 84), (85, 100)]
    distribution = []
    for low, high in bins:
        count = int(scores["row_readiness_score"].between(low, high, inclusive="both").sum())
        distribution.append({"label": f"{low}-{high}", "min": low, "max": high, "count": count})
    reasons = Counter(reason for reasons in scores["row_reason_codes"] for reason in reasons)
    return {
        "row_readiness_avg": round(float(scores["row_readiness_score"].mean())),
        "row_review_required": int(scores["row_review_required"].sum()),
        "tier_counts": tier_counts,
        "score_distribution": distribution,
        "top_reason_codes": [{"reason": key, "count": value} for key, value in reasons.most_common(8)],
    }
