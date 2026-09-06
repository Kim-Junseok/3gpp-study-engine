from __future__ import annotations

import re
from collections import Counter

from threegpp.db import MetadataRepository
from threegpp.models import (
    CandidateInventory,
    CandidateTDoc,
    CandidateView,
    CandidateViewKind,
    MatchLevel,
    SnapshotCoverage,
    SnapshotRole,
    StudyRequest,
    TDocAvailability,
    TDocMetadata,
    TDocQuery,
    TopicMatchEvidence,
)


FIELD_WEIGHTS = {
    "title": 3,
    "abstract": 3,
    "agenda_item_description": 2,
    "related_work_item": 2,
    "document_type": 1,
    "status": 0,
    "release": 1,
    "specification": 1,
    "intended_for": 1,
}
ANCHOR_FIELDS = ("title", "abstract", "agenda_item_description")
SUPPORTING_FIELDS = tuple(field for field in FIELD_WEIGHTS if field not in ANCHOR_FIELDS)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "of", "on", "or", "the", "to", "with",
}
GENERIC_TOKENS = {
    "3gpp", "access", "change", "discussion", "document", "radio", "system", "study",
    "mode", "update",
}
_LEVEL_RANK = {MatchLevel.LOW: 1, MatchLevel.MEDIUM: 2, MatchLevel.HIGH: 3}


class StudyService:
    def __init__(self, repository: MetadataRepository) -> None:
        self.repository = repository

    def candidate_inventory(
        self, request: StudyRequest, *, snapshot_url: str | None = None
    ) -> CandidateInventory:
        if snapshot_url is None:
            query = TDocQuery(working_groups=request.working_groups, meetings=request.meetings)
            records = self.repository.query_tdocs(query)
            view = CandidateView()
        else:
            snapshot = self.repository.get_tdoc_list_snapshot(snapshot_url)
            if snapshot is None:
                raise ValueError(f"snapshot is not stored: {snapshot_url}")
            if (
                snapshot.working_group not in request.working_groups
                or snapshot.meeting not in request.meetings.get(snapshot.working_group, [])
            ):
                raise ValueError("snapshot is outside the StudyRequest meeting scope")
            records = snapshot.tdocs
            if SnapshotRole.MEETING_CLOSE in snapshot.roles:
                kind = CandidateViewKind.MEETING_CLOSE
            elif SnapshotRole.HISTORICAL in snapshot.roles:
                kind = CandidateViewKind.HISTORICAL_SNAPSHOT
            else:
                kind = CandidateViewKind.SNAPSHOT
            view = CandidateView(
                kind=kind,
                snapshot_url=str(snapshot.source_url),
                snapshot_checksum=snapshot.checksum,
                snapshot_roles=snapshot.roles,
                snapshot_timestamp=(
                    snapshot.snapshot_timestamp.isoformat()
                    if snapshot.snapshot_timestamp
                    else None
                ),
                request_selected=True,
                canonical_current_modified=False,
            )
        candidates: list[CandidateTDoc] = []
        for record in records:
            evidence = [
                match
                for topic in request.topics
                if (match := _topic_match(record, topic)) is not None
            ]
            if (not request.topics or evidence) and _matches_organizations(
                record, request.organizations
            ):
                if evidence:
                    best = _best_match(evidence)
                else:
                    best = None
                candidates.append(
                    CandidateTDoc(
                        tdoc=record,
                        matched_topic=best.topic if best else None,
                        match_level=best.match_level if best else None,
                        matched_fields=best.matched_fields if best else {},
                        anchor_fields_matched=best.anchor_fields_matched if best else {},
                        supporting_fields_matched=(
                            best.supporting_fields_matched if best else {}
                        ),
                        covered_topic_tokens=best.covered_topic_tokens if best else [],
                        topic_matches=evidence,
                        availability=record.availability,
                    )
                )
        missing: dict[str, list[str]] = {}
        for group, meetings in request.meetings.items():
            absent = [
                meeting
                for meeting in meetings
                if self.repository.get_meeting(group, meeting) is None
            ]
            if absent:
                missing[group.value] = absent

        by_organization: Counter[str] = Counter()
        by_meeting: Counter[str] = Counter()
        by_agenda: Counter[str] = Counter()
        for candidate in candidates:
            record = candidate.tdoc
            for organization in record.organizations or ["(unknown)"]:
                by_organization[organization] += 1
            by_meeting[f"{record.working_group.value}#{record.meeting}"] += 1
            by_agenda[record.agenda_item or "(unknown)"] += 1

        snapshot_coverage: dict[str, SnapshotCoverage] = {}
        for group, meetings in request.meetings.items():
            for meeting in meetings:
                snapshots = self.repository.list_tdoc_list_snapshots(
                    group, meeting, include_records=False
                )
                key = f"{group.value}#{meeting}"
                snapshot_coverage[key] = SnapshotCoverage(
                    total=len(snapshots),
                    parsed=sum(item.parse_summary is not None for item in snapshots),
                    current_consolidated=sum(
                        SnapshotRole.CURRENT_CONSOLIDATED in item.roles for item in snapshots
                    ),
                    meeting_close=sum(
                        SnapshotRole.MEETING_CLOSE in item.roles for item in snapshots
                    ),
                    historical=sum(SnapshotRole.HISTORICAL in item.roles for item in snapshots),
                    explicit_user_selected=sum(
                        SnapshotRole.EXPLICIT_USER_SELECTED in item.roles for item in snapshots
                    ),
                    unknown=sum(SnapshotRole.UNKNOWN in item.roles for item in snapshots),
                )

        return CandidateInventory(
            study_name=request.name,
            view=view,
            meetings_inspected={group.value: values for group, values in request.meetings.items()},
            missing_meetings=missing,
            candidate_count=len(candidates),
            downloadable_count=sum(
                item.availability is TDocAvailability.DOWNLOADABLE for item in candidates
            ),
            listed_only_count=sum(
                item.availability is TDocAvailability.LISTED_ONLY for item in candidates
            ),
            unknown_availability_count=sum(
                item.availability is TDocAvailability.UNKNOWN for item in candidates
            ),
            high_match_count=sum(item.match_level is MatchLevel.HIGH for item in candidates),
            medium_match_count=sum(item.match_level is MatchLevel.MEDIUM for item in candidates),
            low_match_count=sum(item.match_level is MatchLevel.LOW for item in candidates),
            snapshot_coverage=snapshot_coverage,
            by_organization=dict(by_organization.most_common()),
            by_meeting=dict(by_meeting.most_common()),
            by_agenda_item=dict(by_agenda.most_common()),
            candidate_tdocs=candidates,
        )


def _topic_match(record: TDocMetadata, topic: str) -> TopicMatchEvidence | None:
    topic_tokens = _meaningful_tokens(topic)
    if not topic_tokens:
        return None
    fields = {
        "title": record.title,
        "abstract": record.abstract,
        "agenda_item_description": record.agenda_item_description,
        "related_work_item": record.related_work_item,
        "document_type": record.document_type,
        "status": record.status,
        "release": record.release,
        "specification": record.specification,
        "intended_for": record.intended_for,
    }
    matched_fields: dict[str, list[str]] = {}
    for field, value in fields.items():
        if not value:
            continue
        available = set(_normalize_text(value).split())
        matched = [token for token in topic_tokens if token in available]
        if matched:
            matched_fields[field] = matched

    anchor_matches = {
        field: matched_fields[field] for field in ANCHOR_FIELDS if field in matched_fields
    }
    supporting_matches = {
        field: matched_fields[field]
        for field in SUPPORTING_FIELDS
        if field in matched_fields
    }
    anchor_covered = _ordered_union(
        topic_tokens,
        *anchor_matches.values(),
    )
    all_covered = _ordered_union(topic_tokens, *matched_fields.values())
    has_specific_anchor = any(token not in GENERIC_TOKENS for token in anchor_covered)
    if not has_specific_anchor:
        return None

    if any(
        set(topic_tokens).issubset(set(matched_fields.get(field, [])))
        for field in ANCHOR_FIELDS
    ):
        level = MatchLevel.HIGH
    elif (
        set(topic_tokens).issubset(set(all_covered))
        and len(matched_fields) >= 2
    ):
        level = MatchLevel.MEDIUM
    elif (
        len(anchor_covered) >= 2
        and len(anchor_covered) / len(topic_tokens) >= 0.5
    ):
        level = MatchLevel.LOW
    else:
        return None

    return TopicMatchEvidence(
        topic=topic,
        match_level=level,
        topic_tokens=topic_tokens,
        matched_fields=matched_fields,
        anchor_fields_matched=anchor_matches,
        supporting_fields_matched=supporting_matches,
        covered_topic_tokens=all_covered,
    )


def _best_match(evidence: list[TopicMatchEvidence]) -> TopicMatchEvidence:
    indexed = list(enumerate(evidence))
    return max(
        indexed,
        key=lambda item: (
            _LEVEL_RANK[item[1].match_level],
            len(item[1].covered_topic_tokens) / len(item[1].topic_tokens),
            max((FIELD_WEIGHTS[field] for field in item[1].matched_fields), default=0),
            -item[0],
        ),
    )[1]


def _meaningful_tokens(value: str) -> list[str]:
    return list(dict.fromkeys(
        token for token in _normalize_text(value).split() if token not in STOPWORDS
    ))


def _ordered_union(order: list[str], *groups: list[str]) -> list[str]:
    present = {token for group in groups for token in group}
    return [token for token in order if token in present]


def _matches_organizations(record: TDocMetadata, organizations: list[str]) -> bool:
    if not organizations:
        return True
    available = {value.casefold() for value in record.organizations}
    return any(value.casefold() in available for value in organizations)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
