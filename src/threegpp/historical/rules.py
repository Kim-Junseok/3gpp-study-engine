"""Versioned rules for bounded historical meeting coverage."""
from __future__ import annotations

import re

from threegpp.chair_notes.rules import identity
from threegpp.models import WorkingGroup, normalize_meeting_identifier

MEETING_ALIAS_RULESET_VERSION = "meeting-alias-v1"
HISTORICAL_METADATA_RESOLVER_VERSION = "historical-metadata-v1"
HISTORICAL_COVERAGE_SCHEMA_VERSION = "1"
HISTORICAL_CORPUS_PLAN_SCHEMA_VERSION = "1"
DEFAULT_MAX_MEETINGS = 24

_SCOPED = re.compile(
    r"^(?:(?P<wg>RAN[12])#|TSG(?P<tsg>R[12])[_-])?"
    r"(?P<number>[0-9]+)(?P<suffix>bis|b|-e)?$",
    re.IGNORECASE,
)


def normalize_historical_meeting(value: str | int, working_group: WorkingGroup | str) -> tuple[str, str | None]:
    """Normalize explicit historical notation and return its source alias.

    ``b`` is a versioned identifier alias for ``bis`` only in this adapter.
    It does not assert that any two source artifacts are equivalent.
    """
    group = WorkingGroup.parse(working_group)
    raw = str(value).strip()
    match = _SCOPED.fullmatch(raw)
    if not match:
        raise ValueError(f"invalid historical meeting identifier {value!r}")
    prefix = match.group("wg") or match.group("tsg")
    if prefix:
        prefixed_group = "RAN" + prefix[-1]
        if prefixed_group != group.value:
            raise ValueError(f"meeting identifier {value!r} belongs to {prefixed_group}, not {group.value}")
    suffix = (match.group("suffix") or "").lower()
    alias = raw if suffix == "b" else None
    if suffix == "b":
        suffix = "bis"
    return normalize_meeting_identifier(match.group("number") + suffix), alias


def meeting_order_key(meeting: str) -> tuple[int, int, str]:
    normalized = normalize_meeting_identifier(meeting)
    match = re.fullmatch(r"([0-9]+)(bis|-e)?", normalized)
    suffix = match.group(2) or ""
    return int(match.group(1)), {"": 0, "bis": 1, "-e": 2}[suffix], suffix


def expand_numeric_range(start: str, end: str, known: list[str] | None = None) -> list[str]:
    """Expand a bounded range, inserting locally known suffixed meetings."""
    start_key, end_key = meeting_order_key(start), meeting_order_key(end)
    if start_key > end_key:
        raise ValueError("from-meeting must not follow to-meeting")
    values = {start, end}
    for number in range(start_key[0], end_key[0] + 1):
        candidate = str(number)
        key = meeting_order_key(candidate)
        if start_key <= key <= end_key:
            values.add(candidate)
    for candidate in known or []:
        try:
            key = meeting_order_key(candidate)
        except ValueError:
            continue
        if start_key <= key <= end_key:
            values.add(normalize_meeting_identifier(candidate))
    return sorted(values, key=meeting_order_key)
