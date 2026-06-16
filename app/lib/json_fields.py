from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd


JSON_CONTAINER_STARTS = ("[", "{")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, Mapping) or (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    ):
        return False
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(missing, bool):
        return missing
    return False


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_container(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized = {
            str(key).strip(): _normalize_container(item)
            for key, item in value.items()
            if str(key).strip() and not _is_missing(item)
        }
        return {key: value for key, value in normalized.items() if value not in ("", [], {})}

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        normalized_items = [_normalize_container(item) for item in value if not _is_missing(item)]
        compact_items = [item for item in normalized_items if item not in ("", [], {})]
        seen: set[str] = set()
        distinct_items = []
        for item in compact_items:
            fingerprint = _canonical_json(item)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            distinct_items.append(item)
        return distinct_items

    if isinstance(value, str):
        return value.strip()

    return value


def normalize_jsonish_value(value: Any) -> str:
    """Return stable scalar text, parsing JSON array/object cells when present."""
    if _is_missing(value):
        return ""

    parsed: Any
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            return ""
        if not text.startswith(JSON_CONTAINER_STARTS):
            return text
        try:
            parsed = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return text
    elif isinstance(value, Mapping) or (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    ):
        parsed = value
    else:
        return str(value).strip()

    normalized = _normalize_container(parsed)
    if normalized in ([], {}):
        return ""
    if isinstance(normalized, (Mapping, list)):
        return _canonical_json(normalized)
    return str(normalized).strip()


def normalize_jsonish_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    normalized = df.copy()
    for column in normalized.columns:
        normalized[column] = normalized[column].map(normalize_jsonish_value)
    return normalized


def normalize_jsonish_records(records: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    if not records:
        return []
    return [
        {str(key): normalize_jsonish_value(value) for key, value in record.items()}
        for record in records
    ]
