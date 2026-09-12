from __future__ import annotations

import re

import pytest

from threegpp.db import MetadataRepository
from threegpp.links import ExplicitLinkService
from threegpp.models import EvidenceKind, EvidenceScope
from threegpp.study_view import TDocStudyService, render_tdoc_study

from test_links import discussion, evidence, metadata
from test_evidence import _block, _document


def make_view(tmp_path, monkeypatch, *, contribution=True, meeting=True, discussed=True,
              tdoc_id="R1-2601985", metadata_meeting="124bis", discussion_meeting="125"):
    repository = MetadataRepository(tmp_path / "metadata.duckdb")
    record = metadata(tdoc_id, meeting=metadata_meeting)
    repository.upsert_tdoc(record)
    contribution_item = evidence("Proposal: Use explicit DCI.", evidence_id="contribution",
        tdoc_id=tdoc_id, meeting=metadata_meeting, kind=EvidenceKind.PROPOSAL,
        scope=EvidenceScope.CONTRIBUTION)
    meeting_item = evidence(f"Agreement: The draft CR {tdoc_id} is endorsed.",
        evidence_id="meeting")
    semantic = ([contribution_item] if contribution else []) + ([meeting_item] if meeting else [])
    discussions = [discussion(tdoc_id, meeting=discussion_meeting)] if discussed else []
    graph = ExplicitLinkService(repository, tmp_path).resolve_links(
        working_group="RAN1", semantic_evidence=semantic,
        discussion_records=discussions, metadata_records=[record])
    service = TDocStudyService(repository, tmp_path)
    monkeypatch.setattr(service.links, "build_for_tdoc", lambda *args: graph)
    monkeypatch.setattr(service, "_relevant_graphs", lambda *args: [graph])
    monkeypatch.setattr(service, "_content_inspected", lambda *args: contribution)
    monkeypatch.setattr(service.evidence, "list_evidence",
                        lambda *args, **kwargs: [contribution_item] if contribution else [])
    monkeypatch.setattr(service.evidence, "get_evidence", lambda evidence_id: meeting_item)
    return repository, service.build("RAN1", tdoc_id)


def headings(output):
    return [line for line in output.splitlines()
            if line in {"DISCUSSION", "CONTRIBUTION", "MEETING OUTCOME", "EVIDENCE STATUS"}]


def test_case_a_renders_three_independent_positive_sections(tmp_path, monkeypatch):
    repository, view = make_view(tmp_path, monkeypatch)
    try:
        output = render_tdoc_study(view)
    finally:
        repository.close()
    assert headings(output) == ["DISCUSSION", "CONTRIBUTION", "MEETING OUTCOME"]
    assert "Referenced in selected Chair Note: Yes" in output
    assert "TDoc content inspected: Yes" in output
    assert "Proposal\n- Proposal: Use explicit DCI." in output
    assert "Explicit TDoc reference found: Yes" in output
    assert "Outcome: Agreement" in output and "Disposition: ENDORSE" in output


def test_case_b_keeps_uninspected_contribution_separate_from_outcome(tmp_path, monkeypatch):
    repository, view = make_view(tmp_path, monkeypatch, contribution=False)
    try:
        output = render_tdoc_study(view)
    finally:
        repository.close()
    assert "Referenced in selected Chair Note: Yes" in output
    assert "TDoc content inspected: No" in output
    assert "Explicit TDoc reference found: Yes" in output
    assert "Disposition: ENDORSE" in output
    assert "official document unavailable" not in output.casefold()


def test_case_c_missing_outcome_is_source_scoped_and_non_negative(tmp_path, monkeypatch):
    repository, view = make_view(tmp_path, monkeypatch, meeting=False)
    try:
        output = render_tdoc_study(view)
    finally:
        repository.close()
    assert "Referenced in selected Chair Note: Yes" in output
    assert "TDoc content inspected: Yes" in output
    assert "Explicit TDoc reference found: No" in output
    assert "not evidence of rejection" in output
    assert not re.search(r"^No meeting outcome$", output, re.MULTILINE)


def test_discussion_absence_renders_not_observed_never_not_discussed(tmp_path, monkeypatch):
    repository, view = make_view(tmp_path, monkeypatch, discussed=False, meeting=False)
    try:
        output = render_tdoc_study(view)
    finally:
        repository.close()
    assert "Referenced in selected Chair Note: Not observed" in output
    assert not re.search(r"^Not discussed$", output, re.MULTILINE)
    assert "does not establish that the TDoc was not discussed" in output


def test_default_output_hides_internal_implementation_terms(tmp_path, monkeypatch):
    repository, view = make_view(tmp_path, monkeypatch, contribution=False, meeting=False)
    try:
        output = render_tdoc_study(view)
    finally:
        repository.close()
    for value in ("BODY_NOT_LOCAL", "NO_EXPLICIT_LINK", "DISCUSSION_REFERENCE",
                  "SAME_TDOC", "ExplicitEvidenceLink", "coverage axis", "graph node"):
        assert value not in output
    assert "EVIDENCE STATUS" not in output


def test_provenance_mode_may_expose_backend_details(tmp_path, monkeypatch):
    repository, view = make_view(tmp_path, monkeypatch)
    try:
        output = render_tdoc_study(view, provenance=True)
    finally:
        repository.close()
    assert "Graph ID:" in output and "Link ID:" in output
    assert "Backend link kind: discussion_reference" in output
    assert "ChairNoteRef:" in output and "EvidenceRefs:" in output
    assert "Backend statuses:" in output
    assert headings(output) == ["DISCUSSION", "CONTRIBUTION", "MEETING OUTCOME"]


def test_r1_2603427_style_view_uses_discussion_meeting_not_metadata_meeting(
        tmp_path, monkeypatch):
    repository, view = make_view(tmp_path, monkeypatch, tdoc_id="R1-2603427",
        metadata_meeting="124bis", discussion_meeting="125", contribution=False,
        meeting=False)
    try:
        output = render_tdoc_study(view)
    finally:
        repository.close()
    assert view.metadata_meeting == "124bis"
    assert "Meeting: RAN1#125" in output
    assert "cross_meeting" not in output


def test_contribution_evidence_renders_only_actual_kinds(tmp_path, monkeypatch):
    repository, view = make_view(tmp_path, monkeypatch, meeting=False)
    base = view.contribution.evidence[0]
    view.contribution.evidence = [base.model_copy(update={"kind": kind,
        "statement_text": f"{kind.value}: literal"}) for kind in (
            EvidenceKind.OBSERVATION, EvidenceKind.CONCLUSION, EvidenceKind.FFS)]
    try:
        output = render_tdoc_study(view)
    finally:
        repository.close()
    assert "Proposal\n" not in output
    assert "Observation\n- observation: literal" in output
    assert "Conclusion\n- conclusion: literal" in output
    assert "FFS\n- ffs: literal" in output


def test_fresh_zero_evidence_extraction_still_counts_as_content_inspected(
        tmp_path, monkeypatch):
    repository = MetadataRepository(tmp_path / "metadata.duckdb")
    receipt = _document(repository, tmp_path, "R1-2604000", [
        _block("b000001", "Background material without an explicit evidence label."),
    ])
    from threegpp.evidence import EvidenceExtractionService
    outcome = EvidenceExtractionService(repository, tmp_path).extract_document(receipt)
    assert outcome.status == "EXTRACTED" and outcome.evidence_extracted == 0

    service = TDocStudyService(repository, tmp_path)
    targeted = service.links.build_for_tdoc("RAN1", "R1-2604000")
    monkeypatch.setattr(service, "_relevant_graphs", lambda *args: [targeted])
    try:
        view = service.build("RAN1", "R1-2604000")
        output = render_tdoc_study(view)
    finally:
        repository.close()
    assert view.contribution.content_inspected is True
    assert view.contribution.evidence == []
    assert "TDoc content inspected: Yes" in output


def test_view_identity_is_deterministic_and_view_is_not_persisted(tmp_path, monkeypatch):
    repository, first = make_view(tmp_path, monkeypatch)
    service = TDocStudyService(repository, tmp_path)
    graph = ExplicitLinkService(repository, tmp_path).resolve_links(
        working_group="RAN1", metadata_records=[metadata()])
    monkeypatch.setattr(service.links, "build_for_tdoc", lambda *args: graph)
    monkeypatch.setattr(service, "_relevant_graphs", lambda *args: [graph])
    monkeypatch.setattr(service, "_content_inspected", lambda *args: False)
    monkeypatch.setattr(service.evidence, "list_evidence", lambda *args, **kwargs: [])
    try:
        second = service.build("RAN1", "R1-2601985")
        third = service.build("RAN1", "R1-2601985")
    finally:
        repository.close()
    assert second.view_id == third.view_id
    assert not list(tmp_path.rglob("*study-view*"))
    assert first.view_id != second.view_id


def test_study_view_never_invokes_source_acquisition(tmp_path, monkeypatch):
    from threegpp.chair_notes import ChairNoteService
    from threegpp.documents import DocumentService
    monkeypatch.setattr(DocumentService, "execute", lambda *a, **k: pytest.fail("TDoc fetched"))
    monkeypatch.setattr(ChairNoteService, "fetch", lambda *a, **k: pytest.fail("Chair Note fetched"))
    repository, view = make_view(tmp_path, monkeypatch)
    repository.close()
    assert view.tdoc_id == "R1-2601985"


def test_show_tdoc_study_cli_help():
    from threegpp.cli import build_parser
    with pytest.raises(SystemExit) as stopped:
        build_parser().parse_args(["show-tdoc-study", "--help"])
    assert stopped.value.code == 0
