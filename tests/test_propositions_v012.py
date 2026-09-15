from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from threegpp.models import (DetectionBasis, DocumentRole, EvidenceKind,
    EvidenceRef, EvidenceScope, EvidenceSpan, SemanticEvidence, WorkingGroup)
from threegpp.propositions import (CandidateReviewState, ExactSourceSpan,
    PropositionCorpusBuildRequest, PropositionCorpusService,
    PropositionCorpusStaleError, PropositionReviewDecision)
from threegpp.propositions.models import SegmentationReason
from threegpp.propositions.rules import segment, surface


def _span(text="Proposal: Study X.", block_id="b1"):
    return EvidenceSpan(evidence_ref=EvidenceRef(tdoc_id="R1-2600001",
        working_group="RAN1", meeting="126", member="a.docx", block_id=block_id,
        block_type="paragraph"), sequence=0, char_start=0, char_end=len(text))


def _evidence(text="Proposal: Study X.", *, eid="ev-1", scope=EvidenceScope.CONTRIBUTION,
              kind=EvidenceKind.PROPOSAL, tdoc="R1-2600001", organization="Example Corp."):
    role = DocumentRole.CONTRIBUTION if scope is EvidenceScope.CONTRIBUTION else DocumentRole.MEETING_REPORT
    orgs = [organization] if scope is EvidenceScope.CONTRIBUTION else []
    span = _span(text)
    span.evidence_ref.tdoc_id = tdoc
    return SemanticEvidence(evidence_id=eid, kind=kind, scope=scope,
        working_group="RAN1", meeting="126", tdoc_id=tdoc, document_role=role,
        document_role_basis=["fixture"], source_organizations=orgs,
        evidence_refs=[span], statement_text=text, detection_basis=DetectionBasis.EXPLICIT_LABEL,
        matched_cue="Proposal", rule_id="fixture", rule_version="1",
        extracted_at=datetime.now(timezone.utc), normalization_identity={"id":"norm-1"},
        evidence_schema_version="1")


def _evidence_at(text, eid, block_id, kind=EvidenceKind.PROPOSAL):
    value=_evidence(text,eid=eid,kind=kind)
    value.evidence_refs=[_span(text,block_id)]
    return value


class Profiles:
    def __init__(self, inspected=True): self.inspected=inspected
    def load(self, _):
        return SimpleNamespace(profile_id="topic-profile-"+"a"*64,
            profile_checksum="a"*64, working_group=WorkingGroup.RAN1,
            topic_label="Fixture", from_meeting="126", to_meeting="126")
    def inventory(self, profile, **kwargs):
        item=SimpleNamespace(tdoc_id="R1-2600001",meeting="126",title="Fixture",
            organizations=["Example Corp."],content_inspected=self.inspected)
        return SimpleNamespace(inventory_id="topic-inventory-"+"b"*64,
            companies=[SimpleNamespace(organization="Example Corp.",tdocs=[item])],
            unassigned_tdocs=[])


class ProfilesMultiple(Profiles):
    def inventory(self, profile, **kwargs):
        items=[SimpleNamespace(tdoc_id="R1-2600001",meeting="126",title="One",
                    organizations=["One Corp."],content_inspected=True),
               SimpleNamespace(tdoc_id="R1-2600002",meeting="126",title="Two",
                    organizations=["Two Corp."],content_inspected=True)]
        return SimpleNamespace(inventory_id="topic-inventory-"+"b"*64,
            companies=[SimpleNamespace(organization="One Corp.",tdocs=[items[0]]),
                       SimpleNamespace(organization="Two Corp.",tdocs=[items[1]])],
            unassigned_tdocs=[])


class Evidence:
    def __init__(self, values): self.values=values; self.last_request=None
    def list_evidence(self, request): self.last_request=request; return self.values
    def inspect_extraction(self):
        return [{"working_group":"RAN1","meeting":"126","tdoc_id":"R1-2600001",
                 "evidence_checksum":"e"*64}]


class Repo:
    def get_document_receipt(self, *args):
        return SimpleNamespace(normalized_checksum="n"*64,
            normalization_identity=SimpleNamespace(model_dump=lambda **_: {"id":"norm-1"}))


def _service(tmp_path, evidence=None, inspected=True):
    ev=Evidence(evidence if evidence is not None else [_evidence()])
    return PropositionCorpusService(Repo(), tmp_path, profile_service=Profiles(inspected),
                                    evidence_service=ev), ev


def _request(): return PropositionCorpusBuildRequest(profile_id="topic-profile-"+"a"*64)


@pytest.mark.parametrize(("text","reason","count"), [
    ("One proposition", SegmentationReason.WHOLE_SOURCE_UNIT, 1),
    ("First claim. Second claim.", SegmentationReason.SENTENCE_BOUNDARY, 2),
    ("Proposal:\n- first\n- second", SegmentationReason.WHOLE_SOURCE_UNIT, 3),
    ("1. first\n2. second", SegmentationReason.NUMBERED_ITEM, 2),
    ("Option 1: first\nOption 2: second", SegmentationReason.OPTION_ITEM, 2),
])
def test_structural_segmentation(text, reason, count):
    result=segment(text)
    assert len(result)==count
    assert result[0][1] is reason
    for span, _, _ in result: assert text[span.char_start:span.char_end] == span.exact_text


def test_list_children_keep_explicit_parent_context(tmp_path):
    text="Options are considered:\n- alpha\n- beta"
    service,_=_service(tmp_path,[_evidence(text)])
    candidates=service.build(_request(),persist=False).candidates
    assert candidates[1].context_candidate_id == candidates[0].candidate_id
    assert candidates[2].context_candidate_id == candidates[0].candidate_id
    assert candidates[1].context_source_unit_id == candidates[0].source_unit_id


def test_adjacent_option_units_reference_parent_source_unit(tmp_path):
    evidence=[_evidence_at("Proposal: The following options can be considered:","ev-parent","b000010"),
              _evidence_at("Option 1: exact first option.","ev-option-1","b000011",EvidenceKind.CONCLUSION),
              _evidence_at("Option 2: exact second option.","ev-option-2","b000012",EvidenceKind.CONCLUSION)]
    service,_=_service(tmp_path,evidence)
    corpus=service.build(_request(),persist=False)
    parent=corpus.source_units[0].source_unit_id
    assert corpus.candidates[1].context_source_unit_id == parent
    assert corpus.candidates[2].context_source_unit_id == parent
    assert corpus.candidates[1].exact_text == "Option 1: exact first option."


def test_ambiguous_compound_falls_back_whole():
    assert len(segment("Support X and Y; details remain open")) == 1


def test_surface_normalization_is_only_textual():
    assert surface("  Option\u00a0X ") == "option x"
    assert surface("adopt") != surface("select")


def test_build_is_deterministic_and_persisted(tmp_path):
    service,_=_service(tmp_path)
    a=service.build(_request()); b=service.build(_request())
    assert a.manifest.corpus_id == b.manifest.corpus_id
    assert [x.candidate_id for x in a.candidates] == [x.candidate_id for x in b.candidates]
    root=tmp_path/"derived/propositions/RAN1"/a.manifest.corpus_id
    assert {p.name for p in root.iterdir()} == {"corpus.json","source-units.jsonl.gz",
        "candidates.jsonl.gz","reviews.jsonl","accepted-propositions.jsonl.gz"}


def test_build_requests_contribution_scope_only(tmp_path):
    service,ev=_service(tmp_path); service.build(_request())
    assert ev.last_request.scopes == [EvidenceScope.CONTRIBUTION]


def test_meeting_evidence_cannot_enter_corpus(tmp_path):
    service,_=_service(tmp_path, [_evidence(scope=EvidenceScope.MEETING)])
    corpus=service.build(_request(), persist=False)
    assert corpus.source_units == []


def test_source_unit_preserves_literal_and_provenance(tmp_path):
    text="Proposal: X only if condition Y."
    service,_=_service(tmp_path, [_evidence(text)])
    unit=service.build(_request(),persist=False).source_units[0]
    assert unit.exact_text == text and unit.evidence_refs[0].evidence_ref.block_id == "b1"
    assert unit.normalized_checksum == "n"*64 and unit.evidence_artifact_checksum == "e"*64


def test_uninspected_tdoc_is_gap_and_not_read(tmp_path):
    service,ev=_service(tmp_path, inspected=False)
    corpus=service.build(_request(),persist=False)
    assert corpus.source_units == [] and corpus.manifest.evidence_gaps[0].tdoc_id == "R1-2600001"
    assert ev.last_request is None


def test_zero_evidence_is_valid_not_negative(tmp_path):
    service,_=_service(tmp_path, [])
    corpus=service.build(_request(),persist=False)
    assert corpus.source_units == [] and corpus.manifest.evidence_gaps == []


def test_candidates_begin_unreviewed(tmp_path):
    service,_=_service(tmp_path)
    assert service.build(_request(),persist=False).candidates[0].review_state is CandidateReviewState.UNREVIEWED


@pytest.mark.parametrize(("decision","state","accepted"), [
    ("accept", CandidateReviewState.ACCEPTED, 1),
    ("defer", CandidateReviewState.DEFERRED, 0),
    ("exclude_non_proposition", CandidateReviewState.EXCLUDED, 0),
])
def test_explicit_review_decisions(tmp_path, decision, state, accepted):
    service,_=_service(tmp_path); corpus=service.build(_request()); candidate=corpus.candidates[0]
    result=service.review(corpus.manifest.corpus_id,candidate.candidate_id,decision)
    assert result.candidates[0].review_state is state
    assert len(result.accepted_propositions)==accepted


def test_replace_requires_exact_spans_and_keeps_segments_separate(tmp_path):
    text="Proposal: alpha and beta"
    service,_=_service(tmp_path,[_evidence(text)]); corpus=service.build(_request()); c=corpus.candidates[0]
    spans=[{"char_start":10,"char_end":15,"exact_text":"alpha"},
           {"char_start":20,"char_end":24,"exact_text":"beta"}]
    result=service.review(corpus.manifest.corpus_id,c.candidate_id,
        PropositionReviewDecision.REPLACE_WITH_EXACT_SPANS,spans=spans)
    assert result.accepted_propositions[0].exact_text_segments == ["alpha","beta"]


@pytest.mark.parametrize("spans", [
    [], [{"char_start":0,"char_end":3,"exact_text":"wrong"}],
    [{"char_start":10,"char_end":15,"exact_text":"alpha"},{"char_start":12,"char_end":15,"exact_text":"pha"}],
])
def test_invalid_replacement_rejected(tmp_path, spans):
    service,_=_service(tmp_path,[_evidence("Proposal: alpha")]); corpus=service.build(_request()); c=corpus.candidates[0]
    with pytest.raises(ValueError):
        service.review(corpus.manifest.corpus_id,c.candidate_id,"replace_with_exact_spans",spans=spans)


def test_note_does_not_change_review_authority_identity(tmp_path):
    service,_=_service(tmp_path); corpus=service.build(_request()); c=corpus.candidates[0]
    a=service.review(corpus.manifest.corpus_id,c.candidate_id,"accept",researcher_note="one")
    first=a.reviews[0].review_id
    b=service.review(corpus.manifest.corpus_id,c.candidate_id,"accept",researcher_note="two")
    assert b.reviews[0].review_id == first and b.reviews[0].researcher_note == "two"


def test_duplicates_are_preserved_and_grouped_only_within_tdoc_kind(tmp_path):
    values=[_evidence(eid="ev-1"),_evidence(eid="ev-2")]
    service,_=_service(tmp_path,values); corpus=service.build(_request(),persist=False)
    assert len(corpus.source_units)==2
    assert corpus.source_units[0].surface_duplicate_group_id == corpus.source_units[1].surface_duplicate_group_id


def test_duplicate_group_identity_uses_surface_contract(tmp_path):
    values=[_evidence(eid="ev-1"),_evidence(eid="ev-2")]
    service,_=_service(tmp_path,values); corpus=service.build(_request(),persist=False)
    group=corpus.source_units[0].surface_duplicate_group_id
    assert group and all(unit.source_unit_id not in group for unit in corpus.source_units)


def test_different_kinds_are_not_duplicate_grouped(tmp_path):
    values=[_evidence(eid="ev-1"),_evidence(eid="ev-2",kind=EvidenceKind.OBSERVATION)]
    service,_=_service(tmp_path,values); corpus=service.build(_request(),persist=False)
    assert all(x.surface_duplicate_group_id is None for x in corpus.source_units)


def test_identical_text_across_tdocs_and_organizations_is_not_grouped(tmp_path):
    values=[_evidence(eid="ev-1",tdoc="R1-2600001",organization="One Corp."),
            _evidence(eid="ev-2",tdoc="R1-2600002",organization="Two Corp.")]
    ev=Evidence(values)
    service=PropositionCorpusService(Repo(),tmp_path,profile_service=ProfilesMultiple(),
                                     evidence_service=ev)
    corpus=service.build(_request(),persist=False)
    assert len(corpus.source_units)==2
    assert all(unit.surface_duplicate_group_id is None for unit in corpus.source_units)
    assert {tuple(unit.source_organizations) for unit in corpus.source_units} == {
        ("One Corp.",),("Two Corp.",)}


def test_tampered_artifact_is_stale(tmp_path):
    service,_=_service(tmp_path); corpus=service.build(_request())
    path=tmp_path/"derived/propositions/RAN1"/corpus.manifest.corpus_id/"candidates.jsonl.gz"
    path.write_bytes(b"bad")
    with pytest.raises((PropositionCorpusStaleError, OSError)):
        service.load(corpus.manifest.corpus_id)


def test_profile_or_upstream_change_is_stale(tmp_path):
    service,_=_service(tmp_path); corpus=service.build(_request())
    service.profiles.load=lambda _: SimpleNamespace(profile_id="topic-profile-"+"a"*64,
        profile_checksum="changed",working_group=WorkingGroup.RAN1,topic_label="Fixture",
        from_meeting="126",to_meeting="126")
    with pytest.raises(PropositionCorpusStaleError): service.load(corpus.manifest.corpus_id)


def test_request_range_must_be_paired():
    with pytest.raises(ValueError): PropositionCorpusBuildRequest(
        profile_id="topic-profile-"+"a"*64,from_meeting="125")


def test_runtime_proposition_artifacts_are_git_ignored():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(["git","check-ignore","data/derived/propositions/RAN1/example/corpus.json"],
                          cwd=root,text=True,capture_output=True)
    assert result.returncode == 0


def test_service_has_no_acquisition_dependency(tmp_path):
    service,_=_service(tmp_path)
    assert not hasattr(service,"downloader")


def test_no_relation_or_score_fields_exist(tmp_path):
    service,_=_service(tmp_path); corpus=service.build(_request(),persist=False)
    fields=set(type(corpus.candidates[0]).model_fields)
    assert not fields & {"relation","equivalence","stance","polarity","modality","score","embedding"}


def test_exact_span_model_rejects_reverse_range():
    with pytest.raises(ValueError): ExactSourceSpan(char_start=3,char_end=2,exact_text="")


def test_review_api_rejects_free_text_authority(tmp_path):
    service,_=_service(tmp_path); corpus=service.build(_request()); candidate=corpus.candidates[0]
    with pytest.raises(TypeError):
        service.review(corpus.manifest.corpus_id,candidate.candidate_id,"accept",
                       replacement_text="rewritten claim")
