from __future__ import annotations

import io
import json
import re
import zipfile
from xml.etree import ElementTree as ET

import pytest
from openpyxl import Workbook

from threegpp.chair_notes import ChairNoteService
from threegpp.cli import main
from threegpp.db import MetadataRepository
from threegpp.documents import DocumentService, FetchPlanner
from threegpp.evidence import EvidenceExtractionService
from threegpp.ingest.downloader import HTTPDownloader
from threegpp.models import TDocMetadata
from threegpp.proposition_relations import PropositionRelationService
from threegpp.propositions import PropositionCorpusService
from threegpp.report_sources import ReportSourceRequest, ReportSourceService
from threegpp.search import EvidenceSearchService
from threegpp.study_view import TDocStudyService
from threegpp.topics import TopicBootstrapRequest, TopicBootstrapService, TopicProfileService

from test_report_source_read import LocalFixtureDownloader, stored_bytes
from test_topics_v010 import install_chair


def docx_bytes(paragraphs):
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    document = ET.Element(namespace + "document")
    body = ET.SubElement(document, namespace + "body")
    for item in paragraphs:
        level, text = item if isinstance(item, tuple) else (None, item)
        paragraph = ET.SubElement(body, namespace + "p")
        if level:
            properties = ET.SubElement(paragraph, namespace + "pPr")
            ET.SubElement(properties, namespace + "pStyle", {namespace + "val": f"Heading{level}"})
        run = ET.SubElement(paragraph, namespace + "r")
        ET.SubElement(run, namespace + "t").text = text
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", ET.tostring(document))
    return output.getvalue()


def add_document(repository, root, tdoc, paragraphs, *, meeting="125",
                 title="Fast ARQ contribution", organizations=None, extra_members=None):
    repository.upsert_tdoc(TDocMetadata(
        tdoc_id=tdoc, working_group="RAN1", meeting=meeting, title=title,
        organizations=organizations or ["Example Company"],
        official_list_present=True, directory_present=True,
        source_url=f"https://example.test/{tdoc}.zip",
    ))
    members = {f"{tdoc}.docx": docx_bytes(paragraphs), **(extra_members or {})}
    plan = FetchPlanner(repository).explicit([("RAN1", meeting, tdoc)])
    outcome = DocumentService(repository, root, LocalFixtureDownloader(members)).execute(plan)[0]
    assert outcome.receipt is not None
    return outcome.receipt


def save_profile(repository, root, *, start="125", end="125", snapshots=None):
    _, profile = TopicProfileService(repository, root).bootstrap_and_persist(
        TopicBootstrapRequest(working_group="RAN1", from_meeting=start, to_meeting=end,
            user_terms=["Fast ARQ"], topic_label="Fast ARQ",
            source_policy={"chair_note_snapshots": snapshots or {}}))
    return profile


def deny_preparation_and_annotation_reads(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("report attempted preparation or annotation-dependent source reading")

    for owner, methods in (
        (HTTPDownloader, ["download"]),
        (DocumentService, ["execute", "_fetch_and_normalize"]),
        (ChairNoteService, ["fetch", "discover"]),
        (EvidenceExtractionService, ["__init__"]),
        (EvidenceSearchService, ["__init__"]),
        (PropositionCorpusService, ["__init__"]),
        (PropositionRelationService, ["__init__"]),
        (TDocStudyService, ["__init__"]),
        (TopicProfileService, ["inventory", "persist"]),
        (TopicBootstrapService, ["bootstrap"]),
    ):
        for method in methods:
            monkeypatch.setattr(owner, method, fail)


def build_read_only(db, root, profile, **options):
    with MetadataRepository(db, read_only=True) as repository:
        return ReportSourceService(repository, root).build(ReportSourceRequest(
            profile_id=profile.profile_id, **options))


def test_sources_ignore_absent_zero_and_stale_extractions_and_reviews(tmp_path, monkeypatch):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    with MetadataRepository(db) as repository:
        add_document(repository, root, "R1-2601001", [
            "Proposal: Fast ARQ uses the first scheduling opportunity."])
        zero = add_document(repository, root, "R1-2601002", [
            "Fast ARQ recovery remains conditional on timer expiry."])
        stale = add_document(repository, root, "R1-2601003", [
            "Proposal: Fast ARQ requires an explicit negative acknowledgement."],
            organizations=["ZTE", "Sanechips"])
        extraction = EvidenceExtractionService(repository, root)
        zero_result = extraction.extract_document(zero)
        assert zero_result.evidence_extracted == 0 and zero_result.status == "EXTRACTED"
        assert extraction.extract_document(stale).evidence_extracted > 0
        repository.connection.execute(
            "UPDATE semantic_evidence_state SET evidence_checksum='stale-fixture' WHERE tdoc_id=?",
            [stale.tdoc_id])
        profile = save_profile(repository, root)
    before = stored_bytes(root)
    deny_preparation_and_annotation_reads(monkeypatch)
    first = build_read_only(db, root, profile)
    second = build_read_only(db, root, profile)
    assert first == second
    assert first.audit["bundle_identity"] == second.audit["bundle_identity"]
    assert [source["tdoc"] for source in first.contribution_sources] == [
        "R1-2601001", "R1-2601002", "R1-2601003"]
    assert all(source["passages"] for source in first.contribution_sources)
    assert first.contribution_sources[2]["organizations"] == ["ZTE", "Sanechips"]
    assert first.annotations_optional == []
    assert stored_bytes(root) == before


def test_selected_chair_snapshot_is_never_unioned_and_never_an_outcome(tmp_path, monkeypatch):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    first = install_chair(root, "125", "Agreement: Fast ARQ R1-2601001 first snapshot.",
                          filename="chair_notes_eom1.txt")
    second = install_chair(root, "125", "Agreement: Fast ARQ R1-2601002 second snapshot.",
                           filename="chair_notes_eom2.txt")
    with MetadataRepository(db) as repository:
        for tdoc in ("R1-2601001", "R1-2601002"):
            add_document(repository, root, tdoc, ["Fast ARQ source content."],
                         title="An independently identified contribution")
        profile = save_profile(repository, root, snapshots={"125": first.snapshot_id})
    before = stored_bytes(root)
    deny_preparation_and_annotation_reads(monkeypatch)
    a = build_read_only(db, root, profile)
    b = build_read_only(db, root, profile, chair_note_snapshots={"125": second.snapshot_id})
    assert [source["tdoc"] for source in a.contribution_sources] == ["R1-2601001"]
    assert [source["tdoc"] for source in b.contribution_sources] == ["R1-2601002"]
    assert a.discussion_sources[0]["associated_tdocs"] == ["R1-2601001"]
    assert b.discussion_sources[0]["associated_tdocs"] == ["R1-2601002"]
    assert "second snapshot" not in json.dumps(a.discussion_sources)
    assert "first snapshot" not in json.dumps(b.discussion_sources)
    assert not a.meeting_outcome_sources and not b.meeting_outcome_sources
    assert stored_bytes(root) == before


def test_topic_outcome_uses_authority_meeting_without_a_tdoc_reference(tmp_path, monkeypatch):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    statement = "Agreement: Study Fast ARQ failure indication."
    qualifier = "Note: This does not select a signalling mechanism."
    with MetadataRepository(db) as repository:
        add_document(repository, root, "R1-2609000", [statement, qualifier],
            meeting="126", title="Report of RAN1#125 meeting", organizations=["ETSI MCC"])
        add_document(repository, root, "R1-2601001", [
            "Agreement: Fast ARQ is preferred in our company view."])
        profile = save_profile(repository, root)
    before = stored_bytes(root)
    deny_preparation_and_annotation_reads(monkeypatch)
    bundle = build_read_only(db, root, profile)
    assert len(bundle.meeting_outcome_sources) == 1
    outcome = bundle.meeting_outcome_sources[0]
    assert outcome["tdoc"] == "R1-2609000"
    assert outcome["authority_meeting"] == "125" and outcome["discovery_meeting"] == "126"
    assert "organizations" not in outcome
    passage = next(p for p in outcome["passages"] if p["literal_text"] == statement)
    assert passage["source_native_label"] == "Agreement"
    assert qualifier in [p["literal_text"] for p in passage["surrounding_context"]]
    assert not re.search(r"R[12]-\d+", statement)
    assert bundle.contribution_sources[0]["tdoc"] == "R1-2601001"
    assert stored_bytes(root) == before


def test_report_attachments_do_not_inherit_meeting_authority(tmp_path):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    workbook = Workbook()
    workbook.active.append(["Agreement: Fast ARQ attachment must not become an outcome."])
    spreadsheet = io.BytesIO()
    workbook.save(spreadsheet)
    with MetadataRepository(db) as repository:
        add_document(repository, root, "R1-2609000", ["Administrative report contents."],
            title="Report of RAN1#125 meeting", organizations=["ETSI MCC"],
            extra_members={"tdoc_list.xlsx": spreadsheet.getvalue()})
        profile = save_profile(repository, root)
    bundle = build_read_only(db, root, profile)
    assert bundle.meeting_outcome_sources == []


def test_passage_context_stops_at_heading_and_reports_omitted_passages(tmp_path):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    with MetadataRepository(db) as repository:
        add_document(repository, root, "R1-2601001", [
            (1, "Fast ARQ"), "Proposal: Use the scheduling DCI.",
            "Condition: Apply only after timer expiry.",
            (1, "Different subject"), "Unrelated material must stay in its own section."])
        profile = save_profile(repository, root)
    bundle = build_read_only(db, root, profile, max_passages_per_source=2, context_blocks=3)
    source = bundle.contribution_sources[0]
    proposal = next(p for p in source["passages"] if p["source_native_label"] == "Proposal")
    context = [p["literal_text"] for p in proposal["surrounding_context"]]
    assert "Condition: Apply only after timer expiry." in context
    assert not any("Unrelated" in value or value == "Different subject" for value in context)
    assert source["passages_omitted"] == 3
    assert any(gap["source"] == "R1-2601001" and "truncated" in gap["reason"]
               for gap in bundle.evidence_gaps)


def test_character_truncation_has_an_explicit_gap(tmp_path):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    with MetadataRepository(db) as repository:
        add_document(repository, root, "R1-2601001", [
            "Proposal: Fast ARQ " + "long literal source description " * 10 + "only under this condition."])
        profile = save_profile(repository, root)
    bundle = build_read_only(db, root, profile, max_passage_chars=100)
    passage = bundle.contribution_sources[0]["passages"][0]
    assert len(passage["literal_text"]) == 100 and passage["characters_omitted"] > 0
    assert any(gap["source"] == "R1-2601001" and "truncat" in gap["reason"]
               for gap in bundle.evidence_gaps)


def test_unrelated_adjacent_agreement_does_not_promote_a_topic_proposal(tmp_path):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    with MetadataRepository(db) as repository:
        add_document(repository, root, "R1-2609000", [
            "Proposal: Fast ARQ may use a company timer.",
            "Agreement: Retain the unrelated beam management procedure."],
            title="Report of RAN1#125 meeting", organizations=["ETSI MCC"])
        profile = save_profile(repository, root)
    bundle = build_read_only(db, root, profile)
    assert not bundle.meeting_outcome_sources


def test_default_cli_hides_audit_details_even_for_invalid_sources(tmp_path, capsys, monkeypatch):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    with MetadataRepository(db) as repository:
        receipt = add_document(repository, root, "R1-2601001", ["Fast ARQ literal source."])
        profile = save_profile(repository, root)
    (root / receipt.normalized_path).write_bytes(b"corrupted source")
    before = stored_bytes(root)
    deny_preparation_and_annotation_reads(monkeypatch)
    arguments = ["--db", str(db), "--data-dir", str(root), "report-sources",
                 "--profile", profile.profile_id]
    assert main(arguments) == 0
    output = capsys.readouterr().out
    presentation = json.loads(output)
    assert presentation["evidence_gaps"] and not presentation["contribution_sources"]
    for forbidden in ("SemanticEvidence", "AcceptedProposition", "PropositionCandidate",
                      "PropositionRelation", "TopicProfile", "SourceUnit", "ruleset",
                      "checksum", "profile_id", "profile_checksum", "bundle_identity"):
        assert forbidden.casefold() not in output.casefold()
    assert main(arguments + ["--audit"]) == 0
    audit_output = json.loads(capsys.readouterr().out)
    assert audit_output["audit"]["profile_id"] == profile.profile_id
    assert audit_output["audit"]["bundle_identity"]
    assert stored_bytes(root) == before


def test_concatenated_chair_reference_retains_an_older_direct_contribution(tmp_path):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    install_chair(root, "125", "R1-2601001Fast ARQ recovery options")
    with MetadataRepository(db) as repository:
        add_document(repository, root, "R1-2601001", ["Proposal: Fast ARQ uses a bounded timer."],
                     meeting="124bis")
        profile = save_profile(repository, root)
    bundle = build_read_only(db, root, profile)
    assert [source["tdoc"] for source in bundle.contribution_sources] == ["R1-2601001"]
    assert bundle.contribution_sources[0]["meeting"] == "124bis"
    assert bundle.discussion_sources[0]["associated_tdocs"] == ["R1-2601001"]


@pytest.mark.parametrize("paragraphs,label", [
    (["Agreement:", "Study Fast ARQ failure indication.",
      "Note: No particular mechanism is selected."], "Agreement"),
    (["For further study: Fast ARQ failure indication."], "For further study"),
])
def test_outcome_retains_explicit_label_continuations_and_long_ffs_label(tmp_path, paragraphs, label):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    with MetadataRepository(db) as repository:
        add_document(repository, root, "R1-2609000", paragraphs,
            title="Report of RAN1#125 meeting", organizations=["ETSI MCC"])
        profile = save_profile(repository, root)
    bundle = build_read_only(db, root, profile)
    assert len(bundle.meeting_outcome_sources) == 1
    anchor = bundle.meeting_outcome_sources[0]["passages"][0]
    assert anchor["source_native_label"] == label
    available_texts = [p["literal_text"] for p in [anchor] + anchor["surrounding_context"]]
    assert all(text in available_texts for text in paragraphs)


def test_source_link_identifies_the_bytes_read_after_metadata_url_changes(tmp_path):
    root, db = tmp_path / "data", tmp_path / "data" / "metadata.duckdb"
    with MetadataRepository(db) as repository:
        receipt = add_document(repository, root, "R1-2601001", ["Fast ARQ source content."])
        metadata = repository.get_tdoc("RAN1", "125", "R1-2601001")
        repository.upsert_tdoc(metadata.model_copy(update={
            "source_url": "https://example.test/alternate/R1-2601001.zip"}))
        profile = save_profile(repository, root)
    before = stored_bytes(root)
    bundle = build_read_only(db, root, profile)
    assert len(bundle.contribution_sources) == 1
    source = bundle.contribution_sources[0]
    assert source["source"]["official_url"] == str(receipt.raw.source_url)
    assert stored_bytes(root) == before
