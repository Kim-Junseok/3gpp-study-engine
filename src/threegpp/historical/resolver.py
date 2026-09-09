from __future__ import annotations

from threegpp.chair_notes.rules import identity
from threegpp.db import MetadataRepository
from threegpp.models import TDocAvailability, TDocQuery, WorkingGroup

from . import rules
from .models import (
    HistoricalMetadataCandidate, HistoricalMetadataResolution, HistoricalResolutionState,
)


def _candidate(metadata, layer, snapshot=None):
    payload = [layer, metadata.model_dump(mode="json")]
    if snapshot is not None:
        payload += [str(snapshot.source_url), snapshot.checksum, [role.value for role in snapshot.roles]]
    return HistoricalMetadataCandidate(
        candidate_id="hmc-" + identity(payload), metadata=metadata, source_layer=layer,
        snapshot_id=("tdoc-list-" + identity([str(snapshot.source_url), snapshot.checksum,
                     [role.value for role in snapshot.roles]])) if snapshot else None,
        snapshot_url=str(snapshot.source_url) if snapshot else None,
        snapshot_filename=snapshot.filename if snapshot else None,
        snapshot_checksum=snapshot.checksum if snapshot else None,
        snapshot_roles=snapshot.roles if snapshot else [],
        snapshot_timestamp=snapshot.snapshot_timestamp if snapshot else None,
    )


def _signature(candidate):
    return candidate.metadata.model_dump(mode="json", exclude={"metadata_source_url", "metadata_source_checksum"})


def _snapshot_rank(candidate):
    values = {role.value for role in candidate.snapshot_roles}
    if "meeting_close" in values or "explicit_user_selected" in values:
        return 0
    if "current_consolidated" in values:
        return 1
    if "historical" in values:
        return 2
    return 3


class HistoricalMetadataResolver:
    """Resolve stored official metadata without changing the canonical-current view."""

    def __init__(self, repository: MetadataRepository):
        self.repository = repository

    def resolve(self, working_group, tdoc_id, *, discussion_meeting=None, expected_meeting=None):
        group = WorkingGroup.parse(working_group)
        discussion = rules.normalize_historical_meeting(discussion_meeting, group)[0] if discussion_meeting else None
        expected = rules.normalize_historical_meeting(expected_meeting, group)[0] if expected_meeting else None
        current = [_candidate(item, "canonical_current") for item in self.repository.query_tdocs(
            TDocQuery(working_groups=[group], tdoc_id=tdoc_id))]
        historical = [_candidate(item, "official_snapshot", snapshot)
                      for snapshot, item in self.repository.find_tdoc_snapshot_candidates(group, tdoc_id)]
        all_candidates = sorted(current + historical,
                                key=lambda c: (c.metadata.meeting, c.source_layer, c.snapshot_url or "", c.candidate_id))

        exact_meeting = expected or discussion
        exact_current = [c for c in current if exact_meeting and c.metadata.meeting == exact_meeting]
        if exact_current:
            return self._choose(tdoc_id, group, discussion, expected, exact_current, all_candidates,
                                HistoricalResolutionState.CURRENT_MEETING_METADATA,
                                "exact canonical-current metadata for expected/discussion meeting")
        if current:
            return self._choose(tdoc_id, group, discussion, expected, current, all_candidates,
                                HistoricalResolutionState.OTHER_KNOWN_METADATA,
                                "known canonical-current metadata in another meeting")
        exact_historical = [c for c in historical if expected and c.metadata.meeting == expected]
        pool = exact_historical or historical
        if pool:
            basis = ("exact official historical snapshot metadata for expected meeting" if exact_historical
                     else "official historical snapshot metadata in another known meeting")
            return self._choose(tdoc_id, group, discussion, expected, pool, all_candidates,
                                HistoricalResolutionState.HISTORICAL_METADATA, basis)
        return HistoricalMetadataResolution(tdoc_id=tdoc_id, working_group=group,
            discussion_meeting=discussion, expected_metadata_meeting=expected,
            state=HistoricalResolutionState.UNRESOLVED, candidates=[],
            resolution_basis="no matching canonical-current or stored official snapshot metadata",
            resolver_version=rules.HISTORICAL_METADATA_RESOLVER_VERSION)

    def _choose(self, tdoc_id, group, discussion, expected, pool, all_candidates, state, basis):
        if pool and all(item.source_layer == "official_snapshot" for item in pool):
            best_rank = min(_snapshot_rank(item) for item in pool)
            pool = [item for item in pool if _snapshot_rank(item) == best_rank]
            basis += f"; preferred stored snapshot authority tier {best_rank}"
        signatures = {identity(_signature(item)) for item in pool}
        if len(signatures) != 1:
            return HistoricalMetadataResolution(tdoc_id=tdoc_id, working_group=group,
                discussion_meeting=discussion, expected_metadata_meeting=expected,
                state=HistoricalResolutionState.AMBIGUOUS, candidates=all_candidates,
                resolution_basis=basis + "; incompatible candidates at the same precedence tier",
                resolver_version=rules.HISTORICAL_METADATA_RESOLVER_VERSION)
        selected = sorted(pool, key=lambda c: (c.snapshot_url or "", c.candidate_id))[0]
        if selected.metadata.availability is TDocAvailability.LISTED_ONLY:
            selected_state = HistoricalResolutionState.LISTED_ONLY
        elif selected.metadata.availability is TDocAvailability.UNKNOWN:
            selected_state = HistoricalResolutionState.UNKNOWN
        else:
            selected_state = state
        return HistoricalMetadataResolution(tdoc_id=tdoc_id, working_group=group,
            discussion_meeting=discussion, expected_metadata_meeting=expected,
            state=selected_state, selected=selected, candidates=all_candidates,
            resolution_basis=basis,
            resolver_version=rules.HISTORICAL_METADATA_RESOLVER_VERSION)
