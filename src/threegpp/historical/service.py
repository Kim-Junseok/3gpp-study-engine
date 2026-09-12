from __future__ import annotations

from pathlib import Path

from threegpp.chair_notes.coverage import DiscussionCoverageService, _logical
from threegpp.chair_notes.models import DiscussionCoverageRequest, ReferenceResolutionState
from threegpp.chair_notes.rules import identity
from threegpp.documents import FetchPlanner
from threegpp.models import TDocAvailability

from . import rules
from .models import (
    HistoricalCompleteness, HistoricalCorpusExpansionPlan, HistoricalCorpusItem,
    HistoricalCoverageRequest, HistoricalDiscussionEdge, HistoricalMeetingCoverage,
    HistoricalResolutionState, HistoricalSourceState, HistoricalTopicCoverage, MeetingAlias,
    MeetingCoverageState,
)
from .resolver import HistoricalMetadataResolver


DISCLAIMER = (
    "This timeline reflects positive evidence found in the selected official Chair Note "
    "snapshots and known official metadata. Absence from a meeting's selected Chair Note "
    "is not evidence that a TDoc or topic was not discussed."
)


class HistoricalCoverageService:
    """Offline range aggregation over V0.6 single-meeting coverage."""

    def __init__(self, repository, root: Path):
        self.repository, self.root = repository, Path(root)
        self.single = DiscussionCoverageService(repository, root)
        self.resolver = HistoricalMetadataResolver(repository)

    def build_coverage(self, request: HistoricalCoverageRequest) -> HistoricalTopicCoverage:
        known = self.repository.list_known_meetings(request.working_group)
        meetings = rules.expand_numeric_range(request.from_meeting, request.to_meeting, known)
        if len(meetings) > request.max_meetings:
            raise ValueError(f"meeting range contains {len(meetings)} meetings; maximum is {request.max_meetings}")
        entries = [self._meeting(request, meeting) for meeting in meetings]
        missing = sum(item.state is MeetingCoverageState.CHAIR_NOTE_UNAVAILABLE for item in entries)
        unusable = sum(item.state is not MeetingCoverageState.AVAILABLE for item in entries)
        metadata_missing = sum(item.metadata_source_state in {
                               HistoricalSourceState.SOURCE_MISSING,
                               HistoricalSourceState.SOURCE_UNAVAILABLE} for item in entries)
        if missing == len(entries) or metadata_missing == len(entries):
            completeness = HistoricalCompleteness.SOURCE_PREPARATION_REQUIRED
        elif unusable or metadata_missing or any(
                item.metadata_source_state is HistoricalSourceState.SNAPSHOT_SELECTION_REQUIRED
                for item in entries):
            completeness = HistoricalCompleteness.PARTIAL_SOURCE_COVERAGE
        else:
            completeness = HistoricalCompleteness.COMPLETE_FOR_SELECTED_SOURCES
        diagnostics = {
            "meetings_requested": len(entries),
            "meetings_with_usable_chair_note": len(entries) - unusable,
            "meetings_with_metadata_source": len(entries) - metadata_missing,
            "metadata_universe": sum(x.diagnostics["metadata_universe"] for x in entries),
            "chair_note_confirmed": sum(x.diagnostics["chair_note_confirmed"] for x in entries),
            "metadata_relevant_only": sum(x.diagnostics["metadata_relevant_only"] for x in entries),
            "historically_resolved": sum(x.diagnostics["historically_resolved"] for x in entries),
            "unresolved": sum(x.diagnostics["unresolved"] for x in entries),
            "ambiguous": sum(x.diagnostics["ambiguous"] for x in entries),
            "local_bodies": sum(x.diagnostics["local_bodies"] for x in entries),
            "fetch_needed": sum(x.diagnostics["fetch_needed"] for x in entries),
        }
        result = HistoricalTopicCoverage(schema_version=rules.HISTORICAL_COVERAGE_SCHEMA_VERSION,
            coverage_id="", request=request, meetings=entries, completeness=completeness,
            diagnostics=diagnostics, versions={
                "meeting_alias": rules.MEETING_ALIAS_RULESET_VERSION,
                "metadata_resolver": rules.HISTORICAL_METADATA_RESOLVER_VERSION,
                "historical_coverage": rules.HISTORICAL_COVERAGE_SCHEMA_VERSION,
            }, limitations=[DISCLAIMER,
                "Meeting aliases express identifier equivalence only; source authority remains snapshot-specific.",
                "A later Chair Note reference to an older TDoc does not establish proposition continuity.",
                "Coverage and planning perform no source preparation, TDoc download, indexing, or semantic extraction."])
        result.coverage_id = identity(_logical(result.model_dump(mode="json")))
        return result

    def _meeting(self, request, meeting):
        single_request = DiscussionCoverageRequest(working_group=request.working_group, meeting=meeting,
            query=request.query, chair_note_snapshot=request.chair_note_snapshots.get(meeting),
            include_metadata_candidates=request.include_metadata_candidates, limit=request.limit_per_meeting)
        coverage = self.single.build_coverage(single_request)
        metadata_snapshots = self.repository.list_tdoc_list_snapshots(
            request.working_group, meeting, include_records=False)
        role_rank = {"meeting_close": 0, "explicit_user_selected": 0,
                     "current_consolidated": 1, "historical": 2, "unknown": 3}
        preferred_url = None
        usable_metadata_snapshots = [snapshot for snapshot in metadata_snapshots
                                     if snapshot.parse_error is None]
        if usable_metadata_snapshots:
            ranked = [(min(role_rank[role.value] for role in snapshot.roles), snapshot)
                      for snapshot in usable_metadata_snapshots]
            best = min(rank for rank, _ in ranked)
            best_snapshots = [snapshot for rank, snapshot in ranked if rank == best]
            if len(best_snapshots) == 1:
                metadata_state = HistoricalSourceState.AVAILABLE
                preferred_url = str(best_snapshots[0].source_url)
            else:
                metadata_state = HistoricalSourceState.SNAPSHOT_SELECTION_REQUIRED
        elif metadata_snapshots:
            metadata_state = HistoricalSourceState.SOURCE_UNAVAILABLE
        elif any(item.official_list_present
                 for item in self.repository.list_tdocs(request.working_group, meeting)):
            metadata_state = HistoricalSourceState.AVAILABLE
        else:
            metadata_state = HistoricalSourceState.SOURCE_MISSING
        selected = coverage.selection.selected_snapshot
        if selected is None:
            state = (MeetingCoverageState.SNAPSHOT_SELECTION_REQUIRED
                     if coverage.selection.available_snapshots else MeetingCoverageState.CHAIR_NOTE_UNAVAILABLE)
        elif selected.normalized_path is None:
            state = MeetingCoverageState.CHAIR_NOTE_NOT_NORMALIZED
        else:
            state = MeetingCoverageState.AVAILABLE
        resolutions = []
        resolved_confirmed, unresolved = [], []
        for item in coverage.chair_note_confirmed + coverage.unresolved_references:
            resolution = self.resolver.resolve(request.working_group, item.tdoc_id,
                                               discussion_meeting=meeting)
            resolutions.append(resolution)
            if resolution.selected is not None and resolution.state is not HistoricalResolutionState.AMBIGUOUS:
                metadata = resolution.selected.metadata
                mapped = (ReferenceResolutionState.CURRENT_MEETING_METADATA
                          if metadata.meeting == meeting else ReferenceResolutionState.OTHER_KNOWN_METADATA)
                item = item.model_copy(update={"metadata": metadata,
                    "metadata_candidates": [c.metadata for c in resolution.candidates
                                             if c.candidate_id != resolution.selected.candidate_id],
                    "resolution_state": mapped, "availability": metadata.availability,
                    "local_state": self.single._local_state(metadata)})
                resolved_confirmed.append(item)
            else:
                item = item.model_copy(update={"metadata": None,
                    "metadata_candidates": [c.metadata for c in resolution.candidates],
                    "resolution_state": (ReferenceResolutionState.AMBIGUOUS
                                         if resolution.state is HistoricalResolutionState.AMBIGUOUS
                                         else ReferenceResolutionState.UNRESOLVED)})
                unresolved.append(item)
        coverage = coverage.model_copy(update={"chair_note_confirmed": resolved_confirmed,
                                                "unresolved_references": unresolved})
        confirmed = coverage.chair_note_confirmed
        current_metadata = self.repository.list_tdocs(request.working_group, meeting)
        snapshot_ids = {item.tdoc_id for snapshot in self.repository.list_tdoc_list_snapshots(
                        request.working_group, meeting) for item in snapshot.tdocs}
        diagnostics = {
            "metadata_universe": len({item.tdoc_id for item in current_metadata} | snapshot_ids),
            "metadata_snapshots_available": len(metadata_snapshots),
            "chair_note_available": int(bool(coverage.selection.available_snapshots)),
            "chair_note_confirmed": len(confirmed),
            "metadata_relevant_only": len(coverage.metadata_relevant_only),
            "historically_resolved": sum(r.state in {HistoricalResolutionState.HISTORICAL_METADATA,
                                                      HistoricalResolutionState.LISTED_ONLY,
                                                      HistoricalResolutionState.UNKNOWN}
                                         and r.selected is not None and r.selected.source_layer == "official_snapshot"
                                         for r in resolutions),
            "unresolved": sum(r.state is HistoricalResolutionState.UNRESOLVED for r in resolutions),
            "ambiguous": sum(r.state is HistoricalResolutionState.AMBIGUOUS for r in resolutions),
            "local_bodies": sum(c.local_state.raw_verified for c in confirmed),
            "fetch_needed": sum(c.availability is TDocAvailability.DOWNLOADABLE and not c.local_state.raw_verified
                                for c in confirmed),
        }
        raw = (request.from_meeting_raw if meeting == request.from_meeting else
               request.to_meeting_raw if meeting == request.to_meeting else
               f"{request.working_group.value}#{meeting}")
        _, source_alias = rules.normalize_historical_meeting(raw, request.working_group)
        alias = MeetingAlias(working_group=request.working_group, meeting=meeting,
            raw_text=raw, source_alias=source_alias,
            ruleset_version=rules.MEETING_ALIAS_RULESET_VERSION)
        return HistoricalMeetingCoverage(meeting=alias, state=state, coverage=coverage,
            metadata_source_state=metadata_state, metadata_snapshots=metadata_snapshots,
            preferred_metadata_snapshot_url=preferred_url,
            historical_resolutions=resolutions, diagnostics=diagnostics,
            limitations=[DISCLAIMER] + ([coverage.selection.selection_basis]
                                        if state is not MeetingCoverageState.AVAILABLE else []))

    def plan_corpus(self, request: HistoricalCoverageRequest) -> HistoricalCorpusExpansionPlan:
        coverage = self.build_coverage(request)
        grouped = {}
        for meeting in coverage.meetings:
            resolutions = {r.tdoc_id: r for r in meeting.historical_resolutions}
            for candidate in meeting.coverage.chair_note_confirmed + meeting.coverage.unresolved_references:
                resolution = resolutions[candidate.tdoc_id]
                metadata = resolution.selected.metadata if resolution.selected else None
                key = (metadata.working_group.value, metadata.meeting, metadata.tdoc_id) if metadata else (
                    request.working_group.value, None, candidate.tdoc_id)
                record = grouped.setdefault(key, {"metadata": metadata, "resolution": resolution,
                                                   "local": candidate.local_state, "edges": []})
                record["edges"].extend(HistoricalDiscussionEdge(discussion_meeting=meeting.meeting.meeting,
                                      association=edge) for edge in candidate.associations)
        items = []
        for key, value in grouped.items():
            metadata, local, resolution = value["metadata"], value["local"], value["resolution"]
            if metadata is None:
                needed, eligible, reason = None, False, "unresolved or ambiguous metadata"
            elif local.raw_verified:
                needed, eligible, reason = False, False, "reuse verified local body"
            elif metadata.availability is TDocAvailability.DOWNLOADABLE:
                needed, eligible, reason = True, True, "Chair-note-confirmed, missing locally, and officially downloadable"
            elif metadata.availability is TDocAvailability.LISTED_ONLY:
                needed, eligible, reason = None, False, "listed-only historical metadata has no body URL"
            else:
                needed, eligible, reason = None, False, "unknown body availability"
            edges = sorted(value["edges"], key=lambda e: (rules.meeting_order_key(e.discussion_meeting),
                          e.association.record_id))
            items.append(HistoricalCorpusItem(tdoc_id=key[2], metadata_meeting=metadata.meeting if metadata else None,
                metadata=metadata, resolution_state=resolution.state,
                availability=metadata.availability if metadata else None, local_state=local,
                associations=edges, fetch_needed=needed, fetch_eligible=eligible, fetch_reason=reason))
        items.sort(key=lambda x: (rules.meeting_order_key(x.metadata_meeting) if x.metadata_meeting else (10**9,9,""),
                                  x.tdoc_id))
        eligible_ids = [item.tdoc_id for item in items if item.fetch_eligible]
        limit = FetchPlanner(self.repository).batch_limit
        batches = [eligible_ids[index:index + limit] for index in range(0, len(eligible_ids), limit)]
        plan = HistoricalCorpusExpansionPlan(schema_version=rules.HISTORICAL_CORPUS_PLAN_SCHEMA_VERSION,
            plan_id="", coverage=coverage, items=items, batches=batches, automatic_batch_limit=limit)
        plan.plan_id = identity(_logical(plan.model_dump(mode="json")))
        return plan

    def compile_fetch_plan(self, plan: HistoricalCorpusExpansionPlan, batch: int):
        current = self.plan_corpus(plan.coverage.request)
        if current.plan_id != plan.plan_id:
            raise ValueError("stale historical corpus plan; rebuild before compiling")
        if batch < 1 or batch > len(current.batches):
            raise ValueError("batch must identify an existing 1-based batch")
        wanted = set(current.batches[batch - 1])
        records = [item.metadata for item in current.items
                   if item.tdoc_id in wanted and item.fetch_eligible]
        return FetchPlanner(self.repository).explicit_records(records,
            reason=f"Historical coverage {current.coverage.coverage_id}; plan {current.plan_id}; batch {batch}")
