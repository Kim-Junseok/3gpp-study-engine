from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from threegpp.completion import (
    COMPLETION_SCHEMA_VERSION, TDocEvidenceCompletionRequest,
    TDocEvidenceCompletionService,
)
from threegpp.documents.models import RetentionState
from threegpp.evidence import classify_document_role
from threegpp.historical import HistoricalMetadataResolver
from threegpp.historical import rules as historical_rules
from threegpp.historical.models import HistoricalResolutionState
from threegpp.models import DocumentRole, TDocAvailability
from threegpp.topics import TopicProfileService
from threegpp.topics import rules as topic_rules
from threegpp.topics.models import TopicInventoryAssociation

from .models import (
    MAX_OPERATION_BOUND, TOPIC_COMPLETION_PLAN_SCHEMA_VERSION,
    TOPIC_COMPLETION_RESULT_SCHEMA_VERSION, TOPIC_COMPLETION_RULESET_VERSION,
    TopicCompletionExecutionState, TopicCompletionItemState,
    TopicCorpusCompletionItemResult, TopicCorpusCompletionPlan,
    TopicCorpusCompletionPlanItem, TopicCorpusCompletionPlanRequest,
    TopicCorpusCompletionResult,
)


LIMITATIONS = [
    "The corpus is defined by the selected meetings, prepared official sources, and accepted topic terminology profile.",
    "Completing this corpus does not establish completeness beyond that scope.",
    "Corpus completion does not establish proposition equivalence, company stance, consensus, or meeting agreement.",
]


class PlanStaleError(ValueError):
    pass


class TopicCorpusCompletionService:
    """Plan and explicitly execute bounded V0.9 completion over a V0.10 corpus."""

    def __init__(self, repository, data_root: Path | str, downloader=None, *,
                 profile_service=None, completion_service=None):
        self.repository = repository
        self.data_root = Path(data_root)
        self.profiles = profile_service or TopicProfileService(repository, self.data_root)
        self.completion = completion_service or TDocEvidenceCompletionService(
            repository, self.data_root, downloader)
        self.resolver = HistoricalMetadataResolver(repository)

    def plan(self, request: TopicCorpusCompletionPlanRequest, *, persist=True):
        profile = self.profiles.load(request.profile_id)
        start = request.from_meeting or profile.from_meeting
        end = request.to_meeting or profile.to_meeting
        inventory = self.profiles.inventory(
            profile, from_meeting=start, to_meeting=end,
            chair_note_snapshots=request.chair_note_snapshots)
        records = self._corpus_records(inventory)
        items = [self._plan_item(profile.working_group, value)
                 for value in records]
        eligible = []
        filtered = []
        for item in items:
            if item.state is not TopicCompletionItemState.ELIGIBLE_FOR_COMPLETION:
                filtered.append(item)
                continue
            if not self._matches_filters(item, request):
                filtered.append(item.model_copy(update={
                    "state": TopicCompletionItemState.EXPLICITLY_EXCLUDED,
                    "reason": "excluded by explicit plan filter"}))
                continue
            eligible.append(item)
        batches = [[item.tdoc_id for item in eligible[index:index + request.limit]]
                   for index in range(0, len(eligible), request.limit)]
        selected = set(batches[0] if batches else [])
        final = filtered + [item if item.tdoc_id in selected else item.model_copy(update={
            "state": TopicCompletionItemState.DEFERRED_BY_BOUND,
            "reason": f"deferred after the first {request.limit} eligible TDocs"})
            for item in eligible]
        final.sort(key=self._item_order_key)
        scope = self._scope_payload(profile, inventory, final)
        scope_checksum = _digest(scope)
        revisions = self._profile_revisions(profile.profile_id)
        summary = self._summary(final)
        logical = {
            "schema_version": TOPIC_COMPLETION_PLAN_SCHEMA_VERSION,
            "request": request.model_dump(mode="json"),
            "profile_id": profile.profile_id,
            "profile_checksum": profile.profile_checksum,
            "inventory_id": inventory.inventory_id,
            "corpus_scope_checksum": scope_checksum,
            "working_group": profile.working_group.value,
            "topic_label": profile.topic_label,
            "from_meeting": start,
            "to_meeting": end,
            "source_identities": profile.source_identities,
            "profile_revision_ids": revisions,
            "items": [item.model_dump(mode="json") for item in final],
            "batches": batches,
            "summary": summary,
            "limitations": LIMITATIONS,
            "versions": self._versions(),
        }
        checksum = _digest(logical)
        plan = TopicCorpusCompletionPlan(
            **logical, plan_checksum=checksum, plan_id="topic-completion-plan-" + checksum)
        if persist:
            self._persist_plan(plan)
        return plan

    def execute(self, plan_id: str, *, tdoc_ids=None, batch=None, offline=False):
        plan = self.load_plan(plan_id)
        if bool(tdoc_ids) == bool(batch):
            raise ValueError("select explicit --tdoc values or exactly one --batch")
        if self._profile_revisions(plan.profile_id) != plan.profile_revision_ids:
            raise PlanStaleError("PLAN_STALE: topic profile revisions changed")
        current = self.plan(plan.request, persist=False)
        if current.corpus_scope_checksum != plan.corpus_scope_checksum:
            raise PlanStaleError("PLAN_STALE: direct corpus or source provenance changed")
        old_states = {item.tdoc_id: item for item in plan.items}
        changed = [item.tdoc_id for item in current.items
                   if item.tdoc_id in old_states
                   and item.state_identity != old_states[item.tdoc_id].state_identity
                   and not self._compatible_completed_progress(old_states[item.tdoc_id], item)]
        if changed:
            raise PlanStaleError("PLAN_STALE: completion state changed for "
                                 + ", ".join(changed))
        if batch:
            if batch < 1 or batch > len(plan.batches):
                raise ValueError("batch is outside the persisted plan")
            requested = list(plan.batches[batch - 1])
        else:
            requested = sorted({self._tdoc_id(value) for value in tdoc_ids})
        if not requested or len(requested) > plan.request.limit or len(requested) > MAX_OPERATION_BOUND:
            raise ValueError(f"select 1..{plan.request.limit} TDocs from one plan operation")
        eligible = {item.tdoc_id for item in plan.items if item.state in {
            TopicCompletionItemState.ALREADY_INSPECTED,
            TopicCompletionItemState.ELIGIBLE_FOR_COMPLETION,
            TopicCompletionItemState.DEFERRED_BY_BOUND}}
        unknown = set(requested) - eligible
        if unknown:
            raise ValueError("selected TDocs are not eligible in this plan: "
                             + ", ".join(sorted(unknown)))
        current_items = {item.tdoc_id: item for item in current.items}
        planned_items = {item.tdoc_id: item for item in plan.items}
        results = []
        systemic = None
        for position, tdoc_id in enumerate(requested):
            old, now = planned_items[tdoc_id], current_items[tdoc_id]
            if now.content_inspected:
                warning = ("completed after planning; reused compatible inspected state"
                           if not old.content_inspected else
                           "content was already inspected when the plan was created")
                results.append(TopicCorpusCompletionItemResult(
                    tdoc_id=tdoc_id, state=TopicCompletionExecutionState.REUSED,
                    content_inspected=True,
                    warning=warning))
                continue
            try:
                completion = self.completion.complete(TDocEvidenceCompletionRequest(
                    working_group=plan.working_group, tdoc_id=tdoc_id,
                    retention=plan.request.retention, offline=offline,
                    expected_metadata_meeting=old.metadata_meeting,
                    discussion_meeting=(old.discussion_meetings[0]
                                        if old.discussion_meetings else None)))
            except Exception as exc:
                systemic = f"{type(exc).__name__}: {str(exc)[:500]}"
                results.append(TopicCorpusCompletionItemResult(
                    tdoc_id=tdoc_id, state=TopicCompletionExecutionState.FAILED,
                    content_inspected=now.content_inspected,
                    failure="systemic failure: " + systemic))
                results.extend(TopicCorpusCompletionItemResult(
                    tdoc_id=value, state=TopicCompletionExecutionState.NOT_RUN,
                    content_inspected=current_items[value].content_inspected,
                    warning="not run after systemic failure")
                    for value in requested[position + 1:])
                break
            if completion.failure is None:
                state = (TopicCompletionExecutionState.REUSED
                         if completion.body.state.value == "reused"
                         else TopicCompletionExecutionState.COMPLETED)
            else:
                state = TopicCompletionExecutionState.FAILED
            results.append(TopicCorpusCompletionItemResult(
                tdoc_id=tdoc_id, state=state, completion_result=completion,
                content_inspected=completion.content_inspected,
                failure=completion.failure.value if completion.failure else None))
        updated_inventory_id = None
        try:
            profile = self.profiles.load(plan.profile_id)
            updated_inventory_id = self.profiles.inventory(
                profile, from_meeting=plan.from_meeting, to_meeting=plan.to_meeting,
                chair_note_snapshots=plan.request.chair_note_snapshots).inventory_id
        except Exception as exc:
            if systemic is None:
                systemic = f"inventory refresh failed: {type(exc).__name__}: {str(exc)[:500]}"
        summary = {
            "requested": len(requested),
            "selected": len(requested),
            "completed": sum(item.state is TopicCompletionExecutionState.COMPLETED for item in results),
            "reused": sum(item.state is TopicCompletionExecutionState.REUSED for item in results),
            "failed": sum(item.state is TopicCompletionExecutionState.FAILED for item in results),
            "ineligible": plan.summary["ineligible"],
            "deferred": plan.summary["deferred"],
            "not_run": sum(item.state is TopicCompletionExecutionState.NOT_RUN for item in results),
        }
        logical = {
            "schema_version": TOPIC_COMPLETION_RESULT_SCHEMA_VERSION,
            "plan_id": plan.plan_id,
            "requested_tdoc_ids": requested,
            "selected_tdoc_ids": requested,
            "items": [item.model_dump(mode="json") for item in results],
            "summary": summary,
            "updated_inventory_id": updated_inventory_id,
            "systemic_failure": systemic,
            "limitations": LIMITATIONS,
            "provenance": {"profile_id": plan.profile_id,
                           "initial_inventory_id": plan.inventory_id,
                           "corpus_scope_checksum": plan.corpus_scope_checksum},
            "versions": self._versions(),
        }
        checksum = _digest(logical)
        result = TopicCorpusCompletionResult(
            **logical, result_checksum=checksum,
            result_id="topic-completion-result-" + checksum)
        self._persist_result(plan, result)
        return result

    def load_plan(self, plan_id):
        if not re.fullmatch(r"topic-completion-plan-[0-9a-f]{64}", plan_id):
            raise ValueError("invalid topic completion plan ID")
        paths = sorted((self.data_root / "derived" / "topic-completion").glob(
            f"*/{plan_id}/plan.json"))
        if len(paths) != 1:
            raise ValueError("topic completion plan was not found or is ambiguous")
        plan = TopicCorpusCompletionPlan.model_validate_json(paths[0].read_text())
        logical = plan.model_dump(mode="json", exclude={"plan_id", "plan_checksum"})
        checksum = _digest(logical)
        if checksum != plan.plan_checksum or plan.plan_id != "topic-completion-plan-" + checksum:
            raise ValueError("topic completion plan checksum is stale or conflicting")
        return plan

    def _plan_item(self, group, record):
        base = record["item"]
        discussion_meetings = sorted({association.meeting for association in base.associations},
            key=historical_rules.meeting_order_key)
        resolution = self.resolver.resolve(
            group, base.tdoc_id,
            discussion_meeting=discussion_meetings[0] if discussion_meetings else None,
            expected_meeting=base.meeting)
        if resolution.state is HistoricalResolutionState.AMBIGUOUS:
            state, reason, metadata = (TopicCompletionItemState.METADATA_AMBIGUOUS,
                "official metadata resolution is ambiguous", None)
        elif resolution.selected is None:
            state, reason, metadata = (TopicCompletionItemState.METADATA_UNRESOLVED,
                "official metadata could not be resolved", None)
        else:
            metadata = resolution.selected.metadata
            if classify_document_role(metadata).role is not DocumentRole.CONTRIBUTION:
                state, reason = (TopicCompletionItemState.NOT_A_CONTRIBUTION,
                                 "resolved TDoc is not a contribution")
            elif base.content_inspected:
                state, reason = (TopicCompletionItemState.ALREADY_INSPECTED,
                                 "contribution content is already inspected")
            elif metadata.availability is not TDocAvailability.DOWNLOADABLE:
                state, reason = (TopicCompletionItemState.NOT_DOWNLOADABLE,
                                 f"body availability is {metadata.availability.value}")
            else:
                state, reason = (TopicCompletionItemState.ELIGIBLE_FOR_COMPLETION,
                                 "missing inspected contribution content and body is downloadable")
        meeting = metadata.meeting if metadata else base.meeting
        status = self._local_status(group.value, base.tdoc_id, meeting)
        required = self._required_stages(status, base.content_inspected)
        logical = {
            "tdoc_id": base.tdoc_id,
            "metadata_meeting": meeting,
            "organizations": sorted(set(base.organizations), key=lambda value: (value.casefold(), value)),
            "associations": [item.model_dump(mode="json") for item in base.associations],
            "metadata_candidate_id": resolution.selected.candidate_id if resolution.selected else None,
            "state_status": status,
        }
        return TopicCorpusCompletionPlanItem(
            item_id="topic-completion-item-" + _digest(logical),
            tdoc_id=base.tdoc_id, organizations=logical["organizations"],
            metadata_meeting=meeting, discussion_meetings=discussion_meetings,
            title=metadata.title if metadata else base.title,
            official_url=str(metadata.source_url) if metadata and metadata.source_url else base.official_url,
            availability=metadata.availability if metadata else TDocAvailability.UNKNOWN,
            associations=base.associations,
            discussion_confirmed=base.chair_note_confirmed,
            content_inspected=base.content_inspected,
            explicit_meeting_outcome_reference=base.explicit_meeting_outcome_reference,
            metadata_resolution_state=resolution.state.value,
            metadata_candidate_id=resolution.selected.candidate_id if resolution.selected else None,
            metadata_source_identity=((resolution.selected.snapshot_checksum
                or metadata.metadata_source_checksum)
                if resolution.selected and metadata else None),
            raw_local_state=status["raw"], retention_state=(RetentionState(status["retention"])
                if status["retention"] else None), normalization_state=status["normalization"],
            index_state=status["index"], semantic_evidence_state=status["semantic"],
            semantic_evidence_count=status["evidence_count"], state=state,
            required_stages=required, reason=reason,
            state_identity=_digest(status))

    def _local_status(self, group, tdoc_id, meeting):
        if not meeting:
            return {"raw": "missing", "retention": None, "normalization": "missing",
                    "index": "missing", "semantic": "missing", "evidence_count": None,
                    "raw_checksum": None, "normalization_identity": None,
                    "normalized_checksum": None}
        receipt = self.repository.get_document_receipt(tdoc_id, group, meeting)
        raw_state = "missing"
        if receipt:
            path = Path(receipt.raw.local_path)
            raw_state = ("available" if path.is_file() and _sha(path) == receipt.raw.sha256
                         else "checksum_mismatch" if path.is_file() else "missing")
        key = [tdoc_id, group, meeting]
        index = self.repository.connection.execute(
            "SELECT status, normalization_identity_json, normalized_checksum, index_schema_version, tokenizer_version FROM search_index_state WHERE tdoc_id=? AND working_group=? AND meeting_number=?",
            key).fetchone()
        semantic = self.repository.connection.execute(
            "SELECT status, normalization_identity_json, normalized_checksum, evidence_schema_version, ruleset_version, evidence_count FROM semantic_evidence_state WHERE tdoc_id=? AND working_group=? AND meeting_number=?",
            key).fetchone()
        return {
            "raw": raw_state,
            "retention": receipt.raw.retention.value if receipt else None,
            "raw_checksum": receipt.raw.sha256 if receipt else None,
            "normalization": receipt.extraction_status.value if receipt else "missing",
            "normalization_identity": (receipt.normalization_identity.model_dump(mode="json")
                if receipt and receipt.normalization_identity else None),
            "normalized_checksum": receipt.normalized_checksum if receipt else None,
            "index": index[0] if index else "missing",
            "index_identity": list(index[1:]) if index else None,
            "semantic": semantic[0] if semantic else "missing",
            "semantic_identity": list(semantic[1:5]) if semantic else None,
            "evidence_count": semantic[5] if semantic else None,
        }

    @staticmethod
    def _required_stages(status, inspected):
        if inspected:
            return []
        stages = []
        if status["raw"] != "available": stages.append("body")
        if status["normalization"] not in {"parsed", "partially_parsed"}: stages.append("normalization")
        if status["index"] != "INDEXED": stages.append("index")
        if status["semantic"] != "EXTRACTED": stages.append("semantic_extraction")
        stages.extend(["link_status_refresh", "study_view_refresh"])
        return stages

    @staticmethod
    def _corpus_records(inventory):
        records = {}
        values = [item for company in inventory.companies for item in company.tdocs]
        values.extend(inventory.unassigned_tdocs)
        for item in values:
            key = item.tdoc_id
            if key not in records:
                records[key] = {"item": item.model_copy(deep=True)}
                continue
            target = records[key]["item"]
            organizations = sorted(set(target.organizations) | set(item.organizations),
                                   key=lambda value: (value.casefold(), value))
            associations = {json.dumps(value.model_dump(mode="json"), sort_keys=True): value
                            for value in target.associations + item.associations}
            records[key]["item"] = target.model_copy(update={
                "meeting": target.meeting if target.meeting == item.meeting else None,
                "organizations": organizations,
                "associations": [associations[key] for key in sorted(associations)],
                "chair_note_confirmed": target.chair_note_confirmed or item.chair_note_confirmed,
                "metadata_relevant_only": target.metadata_relevant_only or item.metadata_relevant_only,
                "content_inspected": target.content_inspected or item.content_inspected,
                "explicit_meeting_outcome_reference": (
                    target.explicit_meeting_outcome_reference
                    or item.explicit_meeting_outcome_reference),
            })
        result = [value for _, value in sorted(records.items(), key=lambda pair: (
            historical_rules.meeting_order_key(pair[1]["item"].meeting)
                if pair[1]["item"].meeting else (10**9, 9, ""),
            _tdoc_number(pair[0])))]
        return result

    @staticmethod
    def _matches_filters(item, request):
        if request.companies and not ({value.casefold() for value in item.organizations}
                & {value.casefold() for value in request.companies}): return False
        if request.meetings and item.metadata_meeting not in request.meetings: return False
        if request.tdoc_ids and item.tdoc_id not in request.tdoc_ids: return False
        if request.discussion_only and not item.discussion_confirmed: return False
        return True

    @staticmethod
    def _compatible_completed_progress(old, current):
        return (not old.content_inspected and current.content_inspected
                and old.metadata_candidate_id == current.metadata_candidate_id
                and old.metadata_source_identity == current.metadata_source_identity)

    @staticmethod
    def _item_order_key(item):
        association = min((TopicCorpusCompletionService._association_key(value)
                           for value in item.associations), default=(10**9, "", -1, -1, -1))
        return (historical_rules.meeting_order_key(item.metadata_meeting)
                if item.metadata_meeting else (10**9, 9, ""), association,
                _tdoc_number(item.tdoc_id))

    @staticmethod
    def _association_key(value: TopicInventoryAssociation):
        loc = value.source_locator
        return (historical_rules.meeting_order_key(value.meeting),
                loc.get("block_id") or "", _none_as(loc.get("row_index"), -1),
                _none_as(loc.get("cell_index"), -1),
                _none_as(loc.get("char_start"), -1))

    @staticmethod
    def _scope_payload(profile, inventory, items):
        return {"profile_id": profile.profile_id, "profile_checksum": profile.profile_checksum,
            "working_group": profile.working_group.value, "topic_label": profile.topic_label,
            "from_meeting": inventory.from_meeting, "to_meeting": inventory.to_meeting,
            "direct_terms": inventory.direct_terms,
            "source_identities": profile.source_identities,
            "items": [{"tdoc_id": item.tdoc_id, "organizations": item.organizations,
                "metadata_meeting": item.metadata_meeting, "title": item.title,
                "official_url": item.official_url, "availability": item.availability.value,
                "associations": [value.model_dump(mode="json") for value in item.associations],
                "discussion_confirmed": item.discussion_confirmed,
                "meeting_outcome": item.explicit_meeting_outcome_reference,
                "metadata_candidate_id": item.metadata_candidate_id,
                "metadata_source_identity": item.metadata_source_identity}
                for item in items]}

    def _profile_revisions(self, profile_id):
        values = []
        for path in sorted((self.data_root / "derived" / "topics").glob(
                "*/topic-profile-*/topic-profile.json")):
            try:
                payload = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            if payload.get("parent_profile_id") == profile_id:
                values.append(payload.get("profile_id"))
        return sorted(value for value in values if value)

    @staticmethod
    def _summary(items):
        return {"total_direct_tdocs": len(items),
            "already_inspected": sum(item.state is TopicCompletionItemState.ALREADY_INSPECTED for item in items),
            "selected_completion_candidates": sum(item.state is TopicCompletionItemState.ELIGIBLE_FOR_COMPLETION for item in items),
            "ineligible": sum(item.state in {TopicCompletionItemState.NOT_DOWNLOADABLE,
                TopicCompletionItemState.METADATA_UNRESOLVED,
                TopicCompletionItemState.METADATA_AMBIGUOUS,
                TopicCompletionItemState.NOT_A_CONTRIBUTION} for item in items),
            "deferred": sum(item.state is TopicCompletionItemState.DEFERRED_BY_BOUND for item in items),
            "explicitly_excluded": sum(item.state is TopicCompletionItemState.EXPLICITLY_EXCLUDED for item in items)}

    @staticmethod
    def _versions():
        return {"plan_schema": TOPIC_COMPLETION_PLAN_SCHEMA_VERSION,
                "result_schema": TOPIC_COMPLETION_RESULT_SCHEMA_VERSION,
                "ruleset": TOPIC_COMPLETION_RULESET_VERSION,
                "completion_schema": COMPLETION_SCHEMA_VERSION,
                "topic_profile_schema": topic_rules.TOPIC_PROFILE_SCHEMA_VERSION,
                "topic_inventory_schema": topic_rules.TOPIC_INVENTORY_SCHEMA_VERSION}

    def _persist_plan(self, plan):
        path = (self.data_root / "derived" / "topic-completion"
                / plan.working_group.value.lower() / plan.plan_id / "plan.json")
        _atomic(path, plan.model_dump(mode="json"))
        return path

    def _persist_result(self, plan, result):
        path = (self.data_root / "derived" / "topic-completion"
                / plan.working_group.value.lower() / plan.plan_id / "results"
                / f"{result.result_id}.json")
        _atomic(path, result.model_dump(mode="json"))
        return path

    @staticmethod
    def _tdoc_id(value):
        return "".join(value.split()).replace("_", "-").upper()


def _tdoc_number(value):
    match = re.search(r"(\d+)$", value)
    return (int(match.group(1)) if match else 10**20, value)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _none_as(value, fallback):
    return fallback if value is None else value
