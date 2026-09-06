from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from threegpp.models import SnapshotRole, SourceArtifact


@dataclass(frozen=True)
class SnapshotSelection:
    artifact: SourceArtifact
    reason: str


@dataclass(frozen=True)
class SnapshotViews:
    current: SnapshotSelection
    meeting_close: SnapshotSelection | None
    request_selected: SnapshotSelection | None
    roles_by_url: dict[str, list[SnapshotRole]]


# Compatibility name for V0.2a.1 callers.
SnapshotType = SnapshotRole


def classify_tdoc_list_snapshot(artifact: SourceArtifact) -> SnapshotRole:
    filename = (artifact.original_filename or "").casefold()
    if re.search(r"(?:^|[_\-.])(eom|final)(?:[_\-.]|$)", filename):
        return SnapshotRole.MEETING_CLOSE
    if "tdoc_list_meeting" in filename or "tdoc list meeting" in filename:
        return SnapshotRole.CURRENT_CONSOLIDATED
    if infer_snapshot_timestamp(artifact) is not None:
        return SnapshotRole.HISTORICAL
    return SnapshotRole.UNKNOWN


def infer_snapshot_timestamp(artifact: SourceArtifact) -> datetime | None:
    filename = (artifact.original_filename or "").casefold()
    match = re.search(
        r"(?P<year>20\d{2})[-_]?\s*(?P<month>\d{1,2})[-_]?\s*(?P<day>\d{1,2})"
        r"(?:[-_T ]+(?P<hour>\d{1,2})h?(?P<minute>\d{2})?)?",
        filename,
    )
    if not match:
        return None
    return datetime(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
        int(match.group("hour") or 0),
        int(match.group("minute") or 0),
    )


def select_snapshot_views(
    artifacts: list[SourceArtifact], *, explicit_url: str | None = None
) -> SnapshotViews:
    if not artifacts:
        raise ValueError("no TDoc-list artifacts were discovered")

    roles_by_url = {
        str(item.source_url): [classify_tdoc_list_snapshot(item)] for item in artifacts
    }
    explicit: SourceArtifact | None = None
    if explicit_url:
        explicit = next(
            (item for item in artifacts if str(item.source_url) == explicit_url), None
        )
        if explicit is None:
            raise ValueError(f"requested TDoc-list URL was not discovered: {explicit_url}")

    meeting_close_candidates = [
        item
        for item in artifacts
        if classify_tdoc_list_snapshot(item) is SnapshotRole.MEETING_CLOSE
    ]
    meeting_close = (
        SnapshotSelection(
            max(meeting_close_candidates, key=_recency_key),
            "latest filename timestamp among meeting-close snapshots; URL breaks ties",
        )
        if meeting_close_candidates
        else None
    )

    consolidated = [
        item
        for item in artifacts
        if classify_tdoc_list_snapshot(item) is SnapshotRole.CURRENT_CONSOLIDATED
    ]
    historical = [
        item
        for item in artifacts
        if classify_tdoc_list_snapshot(item) is SnapshotRole.HISTORICAL
    ]
    if consolidated:
        current = SnapshotSelection(
            max(consolidated, key=_recency_key),
            "current consolidated official meeting list is the canonical research view",
        )
    elif meeting_close is not None:
        current = SnapshotSelection(
            meeting_close.artifact,
            "meeting-close snapshot used because no consolidated list was discovered",
        )
    elif historical:
        current = SnapshotSelection(
            max(historical, key=_recency_key),
            "latest timestamped snapshot used because no consolidated or meeting-close list was discovered",
        )
    else:
        current = SnapshotSelection(
            max(artifacts, key=lambda item: str(item.source_url)),
            "deterministic URL fallback; snapshot role is unknown",
        )
    request_selected = (
        SnapshotSelection(explicit, "explicitly selected for this request; canonical current unchanged")
        if explicit is not None
        else None
    )
    return SnapshotViews(current, meeting_close, request_selected, roles_by_url)


def select_preferred_tdoc_list(
    artifacts: list[SourceArtifact], *, explicit_url: str | None = None
) -> SnapshotSelection:
    """V0.2a.1 compatibility wrapper; new code should use role-specific views."""
    views = select_snapshot_views(artifacts, explicit_url=explicit_url)
    return views.request_selected or views.current


def _recency_key(artifact: SourceArtifact) -> tuple[datetime, str]:
    return (infer_snapshot_timestamp(artifact) or datetime.min, str(artifact.source_url))
