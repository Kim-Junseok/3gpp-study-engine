from __future__ import annotations

import hashlib
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import duckdb

from threegpp.db import MetadataRepository
from threegpp.ingest.downloader import HTTPDownloader
from threegpp_web.backend import ResearchBackend
from threegpp_web.backend import _human_gap, _human_locator
from threegpp_web.fixtures import FIXTURE_SCOPE, fixture_report_writer, seed_fixture_corpus


@pytest.fixture(autouse=True)
def no_external_connections(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail("web backend attempted an external network connection")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)


@pytest.fixture
def prepared(tmp_path):
    data = tmp_path / "synthetic-fixture"
    seed_fixture_corpus(data)
    return ResearchBackend(data, tmp_path / "app-state", fixture_mode=True)


def approved(backend):
    task = backend.create_task("FixtureTopic의 검증용 원문을 보여줘.")
    backend.save_scope(task["id"], FIXTURE_SCOPE)
    backend.preview_scope(task["id"])
    return backend.approve_scope(task["id"], confirmed=True)


def stored(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def test_missing_data_is_explicit_and_creates_no_research_database(tmp_path):
    backend = ResearchBackend(tmp_path / "missing", tmp_path / "state")
    task = backend.create_task("NTN Release-18 이후의 논의가 궁금해.")
    backend.save_scope(task["id"], FIXTURE_SCOPE)
    preview = backend.preview_scope(task["id"])
    assert preview["status"] == "needs_data"
    assert not (tmp_path / "missing").exists()
    with pytest.raises(ValueError, match="미리보기"):
        backend.approve_scope(task["id"], confirmed=True)
    assert backend.latest_job(task["id"]) is None


def test_scope_needs_meaning_and_separate_time_boundary(prepared):
    task = prepared.create_task("Release-18 이후")
    with pytest.raises(ValueError, match="의미"):
        prepared.save_scope(task["id"], {**FIXTURE_SCOPE, "interpretation": ""})
    with pytest.raises(ValueError, match="릴리스 비교"):
        prepared.save_scope(task["id"], {**FIXTURE_SCOPE, "interpretation": "release_comparison"})
    with pytest.raises(ValueError, match="기준점"):
        prepared.save_scope(task["id"], {**FIXTURE_SCOPE, "interpretation": "time"})
    saved = prepared.save_scope(task["id"], {**FIXTURE_SCOPE, "interpretation": "time",
                                           "time_boundary": "사용자가 정한 테스트 기준점"})
    assert saved["scope"]["time_boundary"] != saved["scope"]["corpus_as_of"]


def test_large_meeting_range_is_rejected_before_unbounded_expansion(prepared):
    task = prepared.create_task("검증용 질문")
    with pytest.raises(ValueError, match="MVP 운영 한도"):
        prepared.save_scope(task["id"], {**FIXTURE_SCOPE, "to_meeting": "999999999"})


def test_stale_page_cannot_overwrite_a_new_scope_or_enqueue_old_approval(prepared):
    task = approved(prepared)
    stale = prepared.get_task(task["id"])
    prepared.save_scope(task["id"], {**FIXTURE_SCOPE, "user_terms": ["different literal term"]})
    with pytest.raises(ValueError, match="변경"):
        prepared.store.save_task(stale)
    with pytest.raises(ValueError, match="변경"):
        prepared.store.create_job(stale)
    assert prepared.latest_job(task["id"]) is None


def test_preview_is_read_only_and_term_decision_rejects_model_synonyms(prepared):
    task = prepared.create_task("검증용 질문")
    prepared.save_scope(task["id"], FIXTURE_SCOPE)
    before = stored(prepared.data_root)
    preview = prepared.preview_scope(task["id"])
    assert preview["status"] == "scope_ready"
    assert stored(prepared.data_root) == before
    assert "profile_id" not in json.dumps(preview)
    with pytest.raises(ValueError, match="표시된 용어"):
        prepared.approve_scope(task["id"], accepted_terms=["model invented synonym"], confirmed=True)
    assert stored(prepared.data_root) == before


def test_running_requires_current_explicit_scope_approval(prepared):
    task = prepared.create_task("검증용 질문")
    prepared.save_scope(task["id"], FIXTURE_SCOPE)
    prepared.preview_scope(task["id"])
    with pytest.raises(ValueError, match="승인"):
        prepared.enqueue(task["id"])
    with pytest.raises(ValueError, match="확인"):
        prepared.approve_scope(task["id"], confirmed=False)
    prepared.approve_scope(task["id"], confirmed=True)
    prepared.save_scope(task["id"], FIXTURE_SCOPE)
    with pytest.raises(ValueError, match="승인"):
        prepared.enqueue(task["id"])


def test_repeated_start_creates_one_job_and_one_attempt(prepared):
    task = approved(prepared)
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = list(pool.map(lambda _: prepared.enqueue(task["id"]), range(10)))
    assert len({job["id"] for job in jobs}) == 1
    assert all(job["attempt"] == 1 for job in jobs)


def test_model_disabled_keeps_sources_and_does_not_fabricate_report(prepared, monkeypatch):
    task = approved(prepared)
    before = stored(prepared.data_root)
    monkeypatch.setattr(HTTPDownloader, "download", lambda *args: pytest.fail("source acquisition"))
    job = prepared.run_job(prepared.enqueue(task["id"])["id"])
    result = prepared.result(job["id"])
    assert job["status"] == "sources_ready"
    assert result["report"] is None and result["model_input"]["model_calls"] == 0
    assert result["validation"]["stage_b_accepted"] is False
    assert stored(prepared.data_root) == before
    assert all(result["bundle"][channel] for channel in (
        "contribution_sources", "discussion_sources", "meeting_outcome_sources"))


def test_fixture_report_stays_labelled_and_citations_resolve(prepared):
    prepared.report_writer = fixture_report_writer
    task = approved(prepared)
    job = prepared.run_job(prepared.enqueue(task["id"])["id"])
    result = prepared.result(job["id"])
    assert job["status"] == "completed"
    report = result["report"]
    assert report["fixture_only"] and report["human_review_pending"]
    assert "실제 연구 보고서가 아닙니다" in report["notice"]
    sources = {source["key"] for channel in (
        "contribution_sources", "discussion_sources", "meeting_outcome_sources")
        for source in result["bundle"][channel]}
    assert all(claim["sources"] and set(claim["sources"]) <= sources for claim in report["claims"])
    assert result["validation"]["content_accuracy_reviewed"] is False


def test_non_fixture_mode_refuses_injected_report_writer(tmp_path):
    with pytest.raises(ValueError, match="fixture"):
        ResearchBackend(tmp_path / "data", tmp_path / "state", report_writer=fixture_report_writer)


@pytest.mark.parametrize("status", ["queued", "running"])
def test_restart_preserves_task_and_marks_pending_job_interrupted(prepared, status):
    task = approved(prepared)
    job = prepared.enqueue(task["id"])
    if status == "running":
        prepared.store.claim_job(job["id"])
    restarted = ResearchBackend(prepared.data_root, prepared.state_root, fixture_mode=True)
    restored = restarted.get_job(job["id"])
    assert restored["status"] == "interrupted"
    assert restarted.get_task(task["id"])["question"] == task["question"]
    assert any(event["stage"] == "interrupted" for event in restored["events"])
    assert restarted.enqueue(task["id"])["id"] == job["id"]
    retry = restarted.enqueue(task["id"], retry=True)
    assert retry["id"] != job["id"] and retry["attempt"] == 2


def test_completed_sources_and_downloads_survive_restart(prepared):
    task = approved(prepared)
    job = prepared.run_job(prepared.enqueue(task["id"])["id"])
    result = prepared.result(job["id"])
    source = result["bundle"]["contribution_sources"][0]
    assert source["source"]["raw_asset"].startswith(f"/sources/{job['id']}/")
    asset_id = source["source"]["raw_asset"].rsplit("/", 1)[1]
    restarted = ResearchBackend(prepared.data_root, prepared.state_root, fixture_mode=True)
    assert restarted.get_job(job["id"])["status"] == "sources_ready"
    assert restarted.result(job["id"]) == result
    path, filename = restarted.resolve_asset(job["id"], asset_id)
    assert path.is_file() and filename == path.name
    text = json.dumps(result, ensure_ascii=False)
    assert str(prepared.data_root) not in text
    assert "normalized reading order" not in text
    assert "profile_id" not in text and "raw_checksum" not in text


def test_download_refuses_changed_or_unregistered_files(prepared):
    task = approved(prepared)
    job = prepared.run_job(prepared.enqueue(task["id"])["id"])
    source = prepared.result(job["id"])["bundle"]["contribution_sources"][0]
    asset_id = source["source"]["raw_asset"].rsplit("/", 1)[1]
    path, _ = prepared.resolve_asset(job["id"], asset_id)
    path.write_bytes(b"changed after source read")
    with pytest.raises(ValueError, match="검증"):
        prepared.resolve_asset(job["id"], asset_id)
    with pytest.raises(KeyError):
        prepared.resolve_asset(job["id"], "../../metadata.duckdb")


def test_configurable_source_limit_preserves_all_sources_and_gaps(prepared):
    prepared.limits["max_sources"] = 1
    task = approved(prepared)
    job = prepared.run_job(prepared.enqueue(task["id"])["id"])
    result = prepared.result(job["id"])
    assert job["status"] == "scope_limit"
    assert len(result["bundle"]["contribution_sources"]) == 2
    assert result["report"] is None and result["model_input"]["model_calls"] == 0


def test_passage_context_budget_is_explicit_and_does_not_silently_trim(prepared):
    prepared.limits["max_input_tokens"] = 1
    task = approved(prepared)
    job = prepared.run_job(prepared.enqueue(task["id"])["id"])
    result = prepared.result(job["id"])
    assert job["status"] == "scope_limit"
    assert result["bundle"]["contribution_sources"][0]["passages"][0]["surrounding_context"]
    assert result["model_input"]["token_upper_bound"] > 1
    assert "exact model token count" in result["model_input"]["count_method"]


def test_scope_preview_does_not_revoke_unchanged_approval(prepared):
    task = approved(prepared)
    prepared.preview_scope(task["id"])
    assert prepared.get_task(task["id"])["status"] == "approved"
    assert prepared.enqueue(task["id"])["status"] == "queued"


def test_new_question_keeps_parent_but_never_inherits_approval(prepared):
    parent = approved(prepared)
    child = prepared.create_task("후속 질문", parent["id"])
    assert child["parent_id"] == parent["id"] and child["scope"] is None and child["approval"] is None
    with pytest.raises(ValueError, match="승인"):
        prepared.enqueue(child["id"])


def test_empty_database_does_not_produce_a_report(tmp_path):
    root = tmp_path / "empty-corpus"
    with MetadataRepository(root / "metadata.duckdb"):
        pass
    backend = ResearchBackend(root, tmp_path / "state")
    task = approved(backend)
    job = backend.run_job(backend.enqueue(task["id"])["id"])
    assert job["status"] == "needs_data" and backend.result(job["id"])["report"] is None


def test_bad_fixture_citation_is_failure_not_fake_success(prepared):
    prepared.report_writer = lambda packet: {"claims": [{"text": "unsupported", "sources": ["imaginary-source"]}]}
    task = approved(prepared)
    job = prepared.run_job(prepared.enqueue(task["id"])["id"])
    assert job["status"] == "failed"
    assert prepared.result(job["id"]) is None


def test_fixture_seed_never_overwrites_existing_research_directory(tmp_path):
    root = tmp_path / "research"
    root.mkdir()
    (root / "valuable-source").write_text("retain exactly")
    with pytest.raises(ValueError, match="empty"):
        seed_fixture_corpus(root)
    assert (root / "valuable-source").read_text() == "retain exactly"


def test_restored_sql_view_is_rejected_before_external_file_evaluation(prepared, tmp_path):
    external = tmp_path / "external-to-corpus.csv"
    external.write_text("value\nnever-read-during-web-query\n")
    escaped = str(external).replace("'", "''")
    with MetadataRepository(prepared.database_path) as repository:
        repository.connection.execute(f"CREATE VIEW malicious AS SELECT * FROM read_csv('{escaped}')")
    external.unlink()
    before = stored(prepared.data_root)
    with pytest.raises(ValueError, match="SQL view"):
        with prepared._repository():
            pytest.fail("user-defined catalog view was exposed to core queries")
    assert stored(prepared.data_root) == before
    task = prepared.create_task("검증용 질문")
    prepared.save_scope(task["id"], FIXTURE_SCOPE)
    with pytest.raises(ValueError, match="확인할 수 없습니다"):
        prepared.preview_scope(task["id"])


def test_read_only_web_connection_disables_network_and_filesystem_table_functions(prepared):
    before = stored(prepared.data_root)
    with prepared._repository() as repository:
        assert repository.connection.execute("SELECT current_setting('enable_external_access')").fetchone() == (False,)
        assert repository.connection.execute("SELECT current_setting('autoload_known_extensions')").fetchone() == (False,)
        with pytest.raises(duckdb.Error, match="(disabled|external access)"):
            repository.connection.execute(
                "SELECT * FROM read_csv('https://fixture.invalid/must-not-be-requested.csv', "
                "columns={'value':'VARCHAR'},auto_detect=false)")
    assert stored(prepared.data_root) == before


def test_changed_term_decision_gets_new_revision_and_cannot_reuse_completed_job(prepared):
    first = approved(prepared)
    first_job = prepared.run_job(prepared.enqueue(first["id"])["id"])
    preview = prepared.preview_scope(first["id"])
    candidate = preview["candidates"][0]["literal_text"]
    changed = prepared.approve_scope(first["id"], accepted_terms=[candidate], confirmed=True,
                                    expected_revision=first["revision"])
    second_job = prepared.enqueue(first["id"])
    assert changed["revision"] == first["revision"] + 1
    assert changed["approval"]["profile_id"] != first["approval"]["profile_id"]
    assert second_job["id"] != first_job["id"]
    assert prepared.get_job(first_job["id"])["approved_scope"] == first["approval"]
    repeated = prepared.approve_scope(first["id"], accepted_terms=[candidate], confirmed=True)
    assert repeated["revision"] == changed["revision"]
    assert prepared.enqueue(first["id"])["id"] == second_job["id"]


def test_changed_bootstrap_after_preview_requires_a_new_approval_revision(prepared):
    first = approved(prepared)
    old_job = prepared.run_job(prepared.enqueue(first["id"])["id"])
    with MetadataRepository(prepared.database_path) as repository:
        metadata = repository.get_tdoc("RAN1", "125", "R1-9900001")
        repository.upsert_tdoc(metadata.model_copy(update={"title": "FixtureTopic changed synthetic wording"}))
    prepared.preview_scope(first["id"])
    assert prepared.get_task(first["id"])["approval"] is None
    changed = prepared.approve_scope(first["id"], confirmed=True)
    assert changed["revision"] > first["revision"]
    assert prepared.enqueue(first["id"])["id"] != old_job["id"]


def test_fixture_marker_cannot_be_used_as_real_research(prepared, tmp_path):
    with pytest.raises(ValueError, match="실제 연구 모드"):
        ResearchBackend(prepared.data_root, tmp_path / "real-state", fixture_mode=False)
    assert not (tmp_path / "real-state").exists()


def test_model_outcome_packet_keeps_authority_and_discovery_meetings_separate():
    bundle = {"contribution_sources": [], "discussion_sources": [], "evidence_gaps": [], "coverage": {},
              "meeting_outcome_sources": [{"key": "source-1", "tdoc": "R1-9900999",
                  "meeting": "126", "authority_meeting": "125", "discovery_meeting": "126", "passages": []}]}
    source = ResearchBackend.model_packet(bundle, "fixture question")["sources"][0]
    assert source["meeting"] == source["authority_meeting"] == "125"
    assert source["discovery_meeting"] == "126"


def test_generic_unnumbered_label_requires_a_distinctive_literal_locator():
    passage = {"locator": "source.docx; Proposal; normalized reading order 4",
               "heading": [], "source_native_label": "Proposal", "literal_text": "Proposal: Preserve this exact condition."}
    locator = _human_locator(passage)
    assert passage["literal_text"] in locator
    assert "normalized reading order" not in locator
    numbered = {**passage, "source_native_label": "Proposal 2", "locator": "source.docx; Proposal 2"}
    assert _human_locator(numbered) == "source.docx; Proposal 2"


def test_error_gaps_hide_server_paths_hashes_and_engine_identifiers():
    gap = _human_gap({"source": "R1-9900001", "reason": "Cannot open /srv/private/raw/source.zip",
                      "details": ["missing /home/researcher/paper.docx", "a" * 64,
                                  "topic-profile-" + "b" * 64],
                      "locator": "actual.docx; Proposal; normalized reading order 8",
                      "passages_omitted": 3})
    text = json.dumps(gap, ensure_ascii=False)
    assert all(value not in text for value in ("/srv", "/home", "a" * 64, "topic-profile", "normalized reading order"))
    assert gap["source"] == "R1-9900001" and gap["passages_omitted"] == 3
    assert gap["locator"] == "actual.docx; Proposal"
