from __future__ import annotations

import io
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from threegpp.completion import TDocEvidenceCompletionService
from threegpp.db import MetadataRepository
from threegpp.documents.models import RetentionState
from threegpp.ingest.downloader import DownloadResult
from threegpp.models import TDocMetadata
from threegpp.topic_completion import (
    MAX_OPERATION_BOUND, PlanStaleError, TopicCompletionExecutionState,
    TopicCompletionItemState, TopicCorpusCompletionPlanRequest,
    TopicCorpusCompletionService,
)
from threegpp.topics.models import (
    TopicCompanyInventory, TopicInventoryAssociation, TopicInventoryTDoc,
    TopicProfileInventory, TopicQueryGroup, TopicTerminologyProfile,
)


PROFILE_ID = "topic-profile-" + "1" * 64


def metadata(tdoc_id, meeting="126", *, organization="Example Org", url=True,
             title="Fast-ARQ contribution"):
    return TDocMetadata(tdoc_id=tdoc_id, working_group="RAN1", meeting=meeting,
        title=title, source_organization_raw=organization, organizations=[organization],
        official_list_present=True, metadata_source_kind="tdoc_list",
        metadata_source_url=f"https://example.test/{meeting}/list.xlsx",
        metadata_source_checksum="a" * 64,
        source_url=(f"https://example.test/{meeting}/{tdoc_id}.zip" if url else None))


def association(tdoc_id, meeting="126", *, chair=True):
    return TopicInventoryAssociation(query_group=TopicQueryGroup.USER_SEED,
        query_term="Fast-ARQ", literal_source_phrase="Fast ARQ", meeting=meeting,
        association_basis=("chair_note_topic_tdoc" if chair else "metadata_title_relevance"),
        source_locator={"block_id": "b000001", "row_index": 0,
                        "cell_index": 0, "char_start": int(tdoc_id[-2:])})


def inventory_item(tdoc_id, meeting="126", *, organization="Example Org",
                   chair=True, inspected=False, outcome=False):
    return TopicInventoryTDoc(tdoc_id=tdoc_id, meeting=meeting,
        title="Fast-ARQ contribution", organizations=[organization],
        official_url=f"https://example.test/{meeting}/{tdoc_id}.zip",
        chair_note_confirmed=chair, metadata_relevant_only=not chair,
        content_inspected=inspected,
        explicit_meeting_outcome_reference=outcome,
        associations=[association(tdoc_id, meeting or "126", chair=chair)])


class ProfileFixture:
    def __init__(self, items, repository=None):
        self.items = items
        self.repository = repository
        self.profile = TopicTerminologyProfile(profile_id=PROFILE_ID,
            profile_checksum="2" * 64, working_group="RAN1", topic_label="Fast ARQ",
            from_meeting="126", to_meeting="126", user_terms=["Fast-ARQ"], terms=[],
            source_bootstrap_id="topic-bootstrap-" + "3" * 64,
            source_identities=["source-" + "4" * 64], versions={})

    def load(self, profile_id):
        assert profile_id == PROFILE_ID
        return self.profile

    def inventory(self, profile, *, from_meeting=None, to_meeting=None,
                  chair_note_snapshots=None, limit=100):
        items = []
        for item in self.items:
            inspected = item.content_inspected
            if self.repository is not None:
                receipt = self.repository.get_document_receipt(
                    item.tdoc_id, "RAN1", item.meeting)
                inspected = inspected or bool(receipt and receipt.normalized_checksum)
            items.append(item.model_copy(update={"content_inspected": inspected}))
        logical = [(item.tdoc_id, item.content_inspected) for item in items]
        suffix = hashlib.sha256(json.dumps(logical).encode()).hexdigest()
        companies = {}
        for item in items:
            companies.setdefault(item.organizations[0], []).append(item)
        return TopicProfileInventory(inventory_id="topic-inventory-" + suffix,
            profile_id=profile.profile_id, working_group="RAN1",
            topic_label=profile.topic_label, from_meeting=from_meeting or "126",
            to_meeting=to_meeting or "126", direct_terms=["Fast-ARQ"],
            related_diagnostic_terms=["HARQ"],
            companies=[TopicCompanyInventory(organization=key, tdocs=value)
                       for key, value in sorted(companies.items())],
            unassigned_tdocs=[], new_source_candidates=[], new_related_candidates=[],
            accepted_terms_found=[], accepted_terms_not_found=[],
            source_completeness="complete_for_selected_sources",
            limitations=[], versions={})


class Downloader:
    def __init__(self, fail_tdocs=()):
        self.calls = 0
        self.fail_tdocs = set(fail_tdocs)
        target = io.BytesIO()
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("contribution.txt", "Proposal: Study Fast ARQ.")
        self.data = target.getvalue()

    def download(self, url, destination):
        self.calls += 1
        if any(tdoc_id in str(url) for tdoc_id in self.fail_tdocs):
            raise RuntimeError("synthetic network failure")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.data)
        checksum = hashlib.sha256(self.data).hexdigest()
        return DownloadResult(destination, checksum, True)


def service(tmp_path, repository, items, downloader=None, completion=None):
    profiles = ProfileFixture(items, repository)
    return TopicCorpusCompletionService(repository, tmp_path, downloader,
        profile_service=profiles, completion_service=completion), profiles


def test_plan_is_deterministic_bounded_direct_only_and_read_only(tmp_path):
    items = [inventory_item(f"R1-2601{index:03d}", organization=(
        "Samsung" if index % 2 else "Nokia"), chair=index % 3 != 0)
        for index in range(35)]
    downloader = Downloader()
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        for item in items:
            repository.upsert_tdoc(metadata(item.tdoc_id,
                organization=item.organizations[0]))
        planner, _ = service(tmp_path, repository, items, downloader)
        request = TopicCorpusCompletionPlanRequest(profile_id=PROFILE_ID)
        first = planner.plan(request)
        second = planner.plan(request)
        loaded = planner.load_plan(first.plan_id)
    assert first == second == loaded and downloader.calls == 0
    assert first.summary == {"total_direct_tdocs": 35, "already_inspected": 0,
        "selected_completion_candidates": 20, "ineligible": 0,
        "deferred": 15, "explicitly_excluded": 0}
    assert len(first.batches) == 2 and len(first.batches[0]) == 20
    assert len(first.batches[1]) == 15 and MAX_OPERATION_BOUND == 50
    assert first.request.retention is RetentionState.CACHE
    assert first.items[0].associations[0].query_group is TopicQueryGroup.USER_SEED
    assert any(item.discussion_confirmed for item in first.items)
    assert (tmp_path / "derived/topic-completion/ran1" / first.plan_id / "plan.json").is_file()


def test_filters_preserve_full_corpus_and_select_only_explicit_scope(tmp_path):
    items = [inventory_item("R1-2601001", organization="Samsung", chair=True),
             inventory_item("R1-2601002", organization="Nokia", chair=True),
             inventory_item("R1-2601003", organization="Samsung", chair=False)]
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        for item in items:
            repository.upsert_tdoc(metadata(item.tdoc_id,
                organization=item.organizations[0]))
        planner, _ = service(tmp_path, repository, items)
        plan = planner.plan(TopicCorpusCompletionPlanRequest(profile_id=PROFILE_ID,
            companies=["Samsung"], discussion_only=True, retention="pinned"))
    states = {item.tdoc_id: item.state for item in plan.items}
    assert states == {"R1-2601001": TopicCompletionItemState.ELIGIBLE_FOR_COMPLETION,
        "R1-2601002": TopicCompletionItemState.EXPLICITLY_EXCLUDED,
        "R1-2601003": TopicCompletionItemState.EXPLICITLY_EXCLUDED}
    assert plan.request.retention is RetentionState.PINNED
    assert len(plan.items) == 3  # metadata-only direct membership is retained

    with MetadataRepository(tmp_path / "second.duckdb") as repository:
        older = inventory_item("R1-2500001", meeting="125", organization="Samsung")
        scoped_items = items + [older]
        for item in scoped_items:
            repository.upsert_tdoc(metadata(item.tdoc_id, item.meeting,
                organization=item.organizations[0]))
        planner, _ = service(tmp_path / "scoped", repository, scoped_items)
        scoped = planner.plan(TopicCorpusCompletionPlanRequest(profile_id=PROFILE_ID,
            meetings=["125"], tdoc_ids=["R1-2500001"]))
    assert [item.tdoc_id for item in scoped.items
            if item.state is TopicCompletionItemState.ELIGIBLE_FOR_COMPLETION] == ["R1-2500001"]


def test_plan_reports_inspected_listed_unknown_unresolved_and_ambiguous(tmp_path):
    items = [inventory_item("R1-2601001", inspected=True),
             inventory_item("R1-2601002"), inventory_item("R1-2601003"),
             inventory_item("R1-2601004", meeting="125"),
             inventory_item("R1-2601005", meeting=None).model_copy(update={
                 "associations": [], "chair_note_confirmed": False})]
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(metadata("R1-2601001"))
        repository.upsert_tdoc(metadata("R1-2601002", url=False))
        repository.upsert_tdoc(TDocMetadata(tdoc_id="R1-2601003",
            working_group="RAN1", meeting="126", title="Fast-ARQ contribution",
            organizations=["Example Org"]))
        repository.upsert_tdoc(metadata("R1-2601005", "125"))
        repository.upsert_tdoc(metadata("R1-2601005", "126"))
        planner, _ = service(tmp_path, repository, items)
        plan = planner.plan(TopicCorpusCompletionPlanRequest(profile_id=PROFILE_ID))
    states = {item.tdoc_id: item.state for item in plan.items}
    assert states["R1-2601001"] is TopicCompletionItemState.ALREADY_INSPECTED
    assert states["R1-2601002"] is TopicCompletionItemState.NOT_DOWNLOADABLE
    assert states["R1-2601003"] is TopicCompletionItemState.NOT_DOWNLOADABLE
    assert states["R1-2601004"] is TopicCompletionItemState.METADATA_UNRESOLVED
    assert states["R1-2601005"] is TopicCompletionItemState.METADATA_AMBIGUOUS
    assert plan.summary["ineligible"] == 4


def test_execution_reuses_v09_is_bounded_and_refreshes_inventory(tmp_path):
    item = inventory_item("R1-2601001", outcome=True)
    downloader = Downloader()
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(metadata(item.tdoc_id))
        profiles = ProfileFixture([item], repository)
        v09 = TDocEvidenceCompletionService(repository, tmp_path, downloader)
        orchestrator = TopicCorpusCompletionService(repository, tmp_path, downloader,
            profile_service=profiles, completion_service=v09)
        plan = orchestrator.plan(TopicCorpusCompletionPlanRequest(profile_id=PROFILE_ID))
        first = orchestrator.execute(plan.plan_id, tdoc_ids=[item.tdoc_id])
        second = orchestrator.execute(plan.plan_id, tdoc_ids=[item.tdoc_id])
        replanned = orchestrator.plan(TopicCorpusCompletionPlanRequest(profile_id=PROFILE_ID))
        inspected = orchestrator.execute(replanned.plan_id, tdoc_ids=[item.tdoc_id])
    assert first.summary["completed"] == 1 and first.summary["failed"] == 0
    assert first.items[0].completion_result is not None
    assert first.items[0].completion_result.request.retention is RetentionState.CACHE
    assert first.items[0].completion_result.semantic_extraction.values["document_role"] == "contribution"
    assert second.items[0].state is TopicCompletionExecutionState.REUSED
    assert downloader.calls == 1
    assert replanned.items[0].state is TopicCompletionItemState.ALREADY_INSPECTED
    assert replanned.items[0].discussion_confirmed is True
    assert replanned.items[0].explicit_meeting_outcome_reference is True
    assert first.updated_inventory_id != plan.inventory_id
    assert inspected.items[0].state is TopicCompletionExecutionState.REUSED


def test_offline_failure_is_item_local_and_systemic_exception_stops(tmp_path):
    items = [inventory_item(f"R1-260100{index}") for index in range(1, 4)]
    downloader = Downloader()
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        for item in items:
            repository.upsert_tdoc(metadata(item.tdoc_id))
        profiles = ProfileFixture(items, repository)
        actual = TDocEvidenceCompletionService(repository, tmp_path, downloader)
        orchestrator = TopicCorpusCompletionService(repository, tmp_path, downloader,
            profile_service=profiles, completion_service=actual)
        plan = orchestrator.plan(TopicCorpusCompletionPlanRequest(
            profile_id=PROFILE_ID, limit=3))
        local = orchestrator.execute(plan.plan_id, batch=1, offline=True)
        assert local.summary["failed"] == 3 and local.summary["not_run"] == 0
        assert downloader.calls == 0

        class Broken:
            def complete(self, request):
                raise RuntimeError("repository unavailable")

        broken = TopicCorpusCompletionService(repository, tmp_path,
            profile_service=profiles, completion_service=Broken())
        stopped = broken.execute(plan.plan_id, batch=1)
    assert stopped.systemic_failure == "RuntimeError: repository unavailable"
    assert stopped.summary["failed"] == 1 and stopped.summary["not_run"] == 2
    assert [item.state for item in stopped.items] == [
        TopicCompletionExecutionState.FAILED,
        TopicCompletionExecutionState.NOT_RUN,
        TopicCompletionExecutionState.NOT_RUN]


def test_one_download_failure_does_not_rollback_independent_items(tmp_path):
    items = [inventory_item(f"R1-260100{index}") for index in range(1, 4)]
    downloader = Downloader(fail_tdocs={"R1-2601002"})
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        for item in items:
            repository.upsert_tdoc(metadata(item.tdoc_id))
        profiles = ProfileFixture(items, repository)
        orchestrator = TopicCorpusCompletionService(repository, tmp_path, downloader,
            profile_service=profiles,
            completion_service=TDocEvidenceCompletionService(
                repository, tmp_path, downloader))
        plan = orchestrator.plan(TopicCorpusCompletionPlanRequest(
            profile_id=PROFILE_ID, limit=3))
        result = orchestrator.execute(plan.plan_id, batch=1)
    assert result.systemic_failure is None
    assert result.summary["completed"] == 2 and result.summary["failed"] == 1
    assert [item.tdoc_id for item in result.items
            if item.state is TopicCompletionExecutionState.FAILED] == ["R1-2601002"]
    assert downloader.calls == 3


def test_profile_revision_invalidates_plan_before_execution(tmp_path):
    item = inventory_item("R1-2601001")
    downloader = Downloader()
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(metadata(item.tdoc_id))
        planner, _ = service(tmp_path, repository, [item], downloader)
        plan = planner.plan(TopicCorpusCompletionPlanRequest(profile_id=PROFILE_ID))
        revision = tmp_path / "derived/topics/ran1" / ("topic-profile-" + "9" * 64)
        revision.mkdir(parents=True)
        (revision / "topic-profile.json").write_text(json.dumps({
            "profile_id": "topic-profile-" + "9" * 64,
            "parent_profile_id": PROFILE_ID}))
        with pytest.raises(PlanStaleError, match="PLAN_STALE"):
            planner.execute(plan.plan_id, batch=1)
    assert downloader.calls == 0


def test_plan_validation_and_runtime_artifact_are_git_ignored(tmp_path):
    with pytest.raises(ValueError):
        TopicCorpusCompletionPlanRequest(profile_id=PROFILE_ID, limit=51)
    with pytest.raises(ValueError):
        TopicCorpusCompletionPlanRequest(profile_id=PROFILE_ID, from_meeting="125")
    ignore = (Path(__file__).parents[1] / ".gitignore").read_text()
    assert "data/derived/" in ignore
