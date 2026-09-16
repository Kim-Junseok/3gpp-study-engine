from __future__ import annotations

import gzip
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from threegpp.models import EvidenceKind, EvidenceRef, EvidenceScope, EvidenceSpan, WorkingGroup
from threegpp.propositions import AcceptedProposition, ExactSourceSpan
from threegpp.proposition_relations import (
    MAX_ELIGIBLE_PAIRS,
    PairReviewState,
    PairScopeTooLargeError,
    PropositionRelationBuildRequest,
    PropositionRelationCorpusStaleError,
    PropositionRelationDecision,
    PropositionRelationReviewConflict,
    PropositionRelationService,
    RelationAuthority,
    RelationBasisSpan,
    render_proposition_relations,
)
from threegpp.proposition_relations.rules import pair_identity


def _evidence_span(tdoc: str, block: str = "b1"):
    return EvidenceSpan(evidence_ref=EvidenceRef(tdoc_id=tdoc, working_group="RAN1",
        meeting="126", member="source.docx", block_id=block, block_type="paragraph"),
        sequence=0, char_start=0, char_end=12)


def _proposition(suffix: str, organization: str | None, *, text=None, tdoc=None,
                 meeting="126", kind=EvidenceKind.PROPOSAL, organizations=None):
    text = text or f"Proposal {suffix}"
    tdoc = tdoc or f"R1-26000{suffix}"
    orgs = organizations if organizations is not None else ([organization] if organization else [])
    span = ExactSourceSpan(char_start=0, char_end=len(text), exact_text=text)
    return AcceptedProposition(proposition_id=f"accepted-proposition-{suffix}",
        corpus_id="topic-proposition-corpus-source", review_id=f"source-review-{suffix}",
        candidate_id=f"candidate-{suffix}", source_unit_id=f"unit-{suffix}",
        exact_text_segments=[text], source_spans=[span], evidence_refs=[_evidence_span(tdoc)],
        working_group=WorkingGroup.RAN1, meeting=meeting, tdoc_id=tdoc,
        source_organizations=orgs, evidence_kind=kind,
        evidence_scope=EvidenceScope.CONTRIBUTION)


class SourceService:
    def __init__(self, accepted):
        self.accepted = accepted
        self.calls = []
        self.checksum = "c" * 64

    def load(self, corpus_id, *, validate_current=True):
        self.calls.append((corpus_id, validate_current))
        manifest = SimpleNamespace(corpus_id="topic-proposition-corpus-source",
            corpus_checksum=self.checksum, profile_id="topic-profile-source",
            profile_checksum="p" * 64, inventory_id="topic-inventory-source",
            working_group=WorkingGroup.RAN1)
        return SimpleNamespace(manifest=manifest, accepted_propositions=self.accepted)


def _service(tmp_path, accepted=None):
    source = SourceService(accepted or [_proposition("1", "One Corp."),
                                        _proposition("2", "Two Corp.")])
    return PropositionRelationService(SimpleNamespace(), tmp_path,
        proposition_service=source), source


def _request(**changes):
    return PropositionRelationBuildRequest(
        proposition_corpus_id="topic-proposition-corpus-source", **changes)


def _built(tmp_path, accepted=None):
    service, source = _service(tmp_path, accepted)
    return service, source, service.build(_request())


def test_decision_taxonomy_is_exact():
    assert {value.value for value in PropositionRelationDecision} == {
        "EQUIVALENT", "OVERLAPPING", "DISTINCT", "CONFLICTING",
        "NOT_COMPARABLE", "DEFER"}


def test_authority_is_researcher_analysis():
    assert list(RelationAuthority) == [RelationAuthority.RESEARCHER_ANALYSIS]


def test_build_creates_disjoint_organization_pair(tmp_path):
    _, _, corpus = _built(tmp_path)
    assert corpus.manifest.eligible_pair_count == 1
    assert corpus.pair_candidates[0].review_state is PairReviewState.UNREVIEWED


def test_single_accepted_proposition_never_self_pairs(tmp_path):
    service, _ = _service(tmp_path, [_proposition("1", "One Corp.")])
    assert service.build(_request(), persist=False).pair_candidates == []


def test_identical_cross_organization_text_remains_unreviewed(tmp_path):
    accepted = [_proposition("1", "One", text="Use the exact same method."),
                _proposition("2", "Two", text="Use the exact same method.")]
    service, _ = _service(tmp_path, accepted)
    corpus = service.build(_request(), persist=False)
    assert corpus.pair_candidates[0].review_state is PairReviewState.UNREVIEWED
    assert corpus.accepted_relations == []


@pytest.mark.parametrize("accepted", [
    [_proposition("1", "One Corp."), _proposition("2", "One Corp.")],
    [_proposition("1", None), _proposition("2", "Two Corp.")],
    [_proposition("1", None), _proposition("2", None)],
    [_proposition("1", None, organizations=["One Corp.", "Shared"]),
     _proposition("2", None, organizations=["Two Corp.", "shared"])],
])
def test_ineligible_pairs_are_excluded(tmp_path, accepted):
    service, _ = _service(tmp_path, accepted)
    assert service.build(_request(), persist=False).pair_candidates == []


def test_multi_organization_disjoint_pair_is_eligible(tmp_path):
    accepted = [_proposition("1", None, organizations=["One", "Partner"]),
                _proposition("2", None, organizations=["Two", "Other"])]
    service, _ = _service(tmp_path, accepted)
    assert len(service.build(_request(), persist=False).pair_candidates) == 1


def test_pair_preserves_each_evidence_kind(tmp_path):
    accepted = [_proposition("1", "One", kind=EvidenceKind.OBSERVATION),
                _proposition("2", "Two", kind=EvidenceKind.CONCLUSION)]
    service, _ = _service(tmp_path, accepted)
    pair = service.build(_request(), persist=False).pair_candidates[0]
    assert pair.left_evidence_kind is EvidenceKind.OBSERVATION
    assert pair.right_evidence_kind is EvidenceKind.CONCLUSION


def test_pair_identity_is_symmetric():
    assert pair_identity("accepted-b", "accepted-a") == pair_identity("accepted-a", "accepted-b")


def test_pair_endpoints_use_canonical_proposition_ids(tmp_path):
    accepted = [_proposition("z", "One"), _proposition("a", "Two")]
    service, _ = _service(tmp_path, accepted)
    pair = service.build(_request(), persist=False).pair_candidates[0]
    assert pair.left_proposition_id == "accepted-proposition-a"
    assert pair.right_proposition_id == "accepted-proposition-z"


def test_repeated_build_is_deterministic(tmp_path):
    service, _ = _service(tmp_path)
    first = service.build(_request())
    path = tmp_path / "derived/proposition-relations/RAN1" / first.manifest.relation_corpus_id
    before = (path / "pair-candidates.jsonl.gz").read_bytes()
    second = service.build(_request())
    assert first.manifest == second.manifest
    assert before == (path / "pair-candidates.jsonl.gz").read_bytes()


def test_filter_order_does_not_change_corpus_identity(tmp_path):
    accepted = [_proposition("1", "One"), _proposition("2", "Two"),
                _proposition("3", "Three")]
    service, _ = _service(tmp_path, accepted)
    first = service.build(_request(organizations=["Two", "One"]), persist=False)
    second = service.build(_request(organizations=["One", "Two"]), persist=False)
    assert first.manifest.relation_corpus_id == second.manifest.relation_corpus_id


def test_persisted_artifact_set_is_bounded(tmp_path):
    _, _, corpus = _built(tmp_path)
    path = tmp_path / "derived/proposition-relations/RAN1" / corpus.manifest.relation_corpus_id
    assert {item.name for item in path.iterdir()} == {"corpus.json",
        "pair-candidates.jsonl.gz", "reviews.jsonl", "accepted-relations.jsonl.gz"}


@pytest.mark.parametrize(("field", "value"), [
    ("organizations", ["One Corp."]),
    ("tdoc_ids", ["R1-260001"]),
    ("meetings", ["125"]),
    ("evidence_kinds", [EvidenceKind.OBSERVATION]),
    ("proposition_ids", ["accepted-proposition-1"]),
])
def test_general_filters_narrow_source_set(tmp_path, field, value):
    accepted = [_proposition("1", "One Corp."), _proposition("2", "Two Corp."),
                _proposition("3", "Three Corp.")]
    service, _ = _service(tmp_path, accepted)
    corpus = service.build(_request(**{field: value}), persist=False)
    assert corpus.manifest.accepted_proposition_count < 3


def test_left_right_filters_apply_to_canonical_endpoints(tmp_path):
    service, _ = _service(tmp_path)
    yes = service.build(_request(left_organizations=["One Corp."],
        right_organizations=["Two Corp."]), persist=False)
    no = service.build(_request(left_organizations=["Two Corp."]), persist=False)
    assert len(yes.pair_candidates) == 1 and no.pair_candidates == []


def test_pair_scope_guard_fails_without_truncation(tmp_path, monkeypatch):
    import threegpp.proposition_relations.service as module
    service, _ = _service(tmp_path)
    monkeypatch.setattr(module, "MAX_ELIGIBLE_PAIRS", 0)
    with pytest.raises(PairScopeTooLargeError, match="PAIR_SCOPE_TOO_LARGE"):
        service.build(_request(), persist=False)
    assert MAX_ELIGIBLE_PAIRS == 5000


@pytest.mark.parametrize("decision", [
    "EQUIVALENT", "OVERLAPPING", "DISTINCT", "CONFLICTING", "NOT_COMPARABLE"])
def test_non_defer_review_creates_accepted_relation(tmp_path, decision):
    service, _, corpus = _built(tmp_path)
    result = service.review(corpus.manifest.relation_corpus_id,
                            corpus.pair_candidates[0].pair_id, decision)
    assert result.accepted_relations[0].decision.value == decision
    assert result.accepted_relations[0].authority is RelationAuthority.RESEARCHER_ANALYSIS


def test_defer_persists_review_without_accepted_relation(tmp_path):
    service, _, corpus = _built(tmp_path)
    result = service.review(corpus.manifest.relation_corpus_id,
                            corpus.pair_candidates[0].pair_id, "DEFER")
    assert result.deferred_count == 1 and result.accepted_relations == []


def test_default_basis_uses_complete_segments(tmp_path):
    accepted = [_proposition("1", "One", text="left literal"),
                _proposition("2", "Two", text="right literal")]
    service, _, corpus = _built(tmp_path, accepted)
    result = service.review(corpus.manifest.relation_corpus_id,
                            corpus.pair_candidates[0].pair_id, "DISTINCT")
    relation = result.accepted_relations[0]
    assert relation.left_basis[0].exact_text == "left literal"
    assert relation.right_basis[0].exact_text == "right literal"


def test_exact_subspan_basis_is_preserved(tmp_path):
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    result = service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "OVERLAPPING",
        left_basis=[{"segment_index": 0, "char_start": 0, "char_end": 8,
                     "exact_text": "Proposal"}],
        right_basis=[{"segment_index": 0, "char_start": 9, "char_end": 10,
                      "exact_text": "2"}])
    assert result.accepted_relations[0].right_basis[0].exact_text == "2"


@pytest.mark.parametrize("basis", [
    [],
    [{"segment_index": 9, "char_start": 0, "char_end": 1, "exact_text": "P"}],
    [{"segment_index": 0, "char_start": 0, "char_end": 3, "exact_text": "bad"}],
    [{"segment_index": 0, "char_start": 0, "char_end": 8, "exact_text": "Proposal"},
     {"segment_index": 0, "char_start": 2, "char_end": 5, "exact_text": "opo"}],
])
def test_invalid_basis_is_rejected(tmp_path, basis):
    service, _, corpus = _built(tmp_path)
    with pytest.raises(ValueError):
        service.review(corpus.manifest.relation_corpus_id,
            corpus.pair_candidates[0].pair_id, "DISTINCT", left_basis=basis)


def test_unknown_pair_is_rejected(tmp_path):
    service, _, corpus = _built(tmp_path)
    with pytest.raises(ValueError, match="pair is not in"):
        service.review(corpus.manifest.relation_corpus_id, "missing", "DISTINCT")


def test_review_api_rejects_relation_paraphrase(tmp_path):
    service, _, corpus = _built(tmp_path)
    with pytest.raises(TypeError):
        service.review(corpus.manifest.relation_corpus_id,
            corpus.pair_candidates[0].pair_id, "DISTINCT",
            relation_text="The companies disagree")


def test_conflicting_review_requires_explicit_update(tmp_path):
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "DISTINCT")
    with pytest.raises(PropositionRelationReviewConflict):
        service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "CONFLICTING")


def test_identical_review_replay_is_idempotent(tmp_path):
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    first = service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "DISTINCT",
                           rationale="literal comparison")
    second = service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "DISTINCT",
                            rationale="literal comparison")
    assert first.reviews == second.reviews and len(second.reviews) == 1


def test_review_artifacts_are_stable_across_pair_review_order(tmp_path):
    accepted = [_proposition("1", "One"), _proposition("2", "Two"),
                _proposition("3", "Three")]
    outputs = []
    for name, reverse in (("forward", False), ("reverse", True)):
        service, _, corpus = _built(tmp_path / name, accepted)
        pairs = list(reversed(corpus.pair_candidates)) if reverse else corpus.pair_candidates
        for pair in pairs:
            service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "DISTINCT")
        path = (tmp_path / name / "derived/proposition-relations/RAN1" /
                corpus.manifest.relation_corpus_id)
        outputs.append(((path / "reviews.jsonl").read_bytes(),
                        (path / "accepted-relations.jsonl.gz").read_bytes()))
    assert outputs[0] == outputs[1]


def test_explicit_update_preserves_review_history(tmp_path):
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    first = service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "DISTINCT")
    second = service.review(corpus.manifest.relation_corpus_id, pair.pair_id,
                            "CONFLICTING", update=True)
    assert len(second.reviews) == 2
    assert second.reviews[1].supersedes_review_id == first.reviews[0].review_id


def test_rationale_update_does_not_change_logical_relation_identity(tmp_path):
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    first = service.review(corpus.manifest.relation_corpus_id, pair.pair_id,
                           "DISTINCT", rationale="one")
    second = service.review(corpus.manifest.relation_corpus_id, pair.pair_id,
                            "DISTINCT", rationale="two", update=True)
    assert first.accepted_relations[0].relation_id == second.accepted_relations[0].relation_id
    assert first.reviews[-1].review_id != second.reviews[-1].review_id


def test_defer_update_removes_current_accepted_relation(tmp_path):
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "EQUIVALENT")
    result = service.review(corpus.manifest.relation_corpus_id, pair.pair_id,
                            "DEFER", update=True)
    assert result.accepted_relations == [] and result.deferred_count == 1


def test_pair_artifact_tampering_is_stale(tmp_path):
    service, _, corpus = _built(tmp_path)
    path = tmp_path / "derived/proposition-relations/RAN1" / corpus.manifest.relation_corpus_id
    (path / "pair-candidates.jsonl.gz").write_bytes(b"bad")
    with pytest.raises((PropositionRelationCorpusStaleError, OSError)):
        service.load(corpus.manifest.relation_corpus_id)


def test_rechecks_complete_pair_set_when_artifact_and_manifest_are_rehashed(tmp_path):
    from threegpp.propositions.rules import digest
    accepted = [_proposition("1", "One"), _proposition("2", "Two"),
                _proposition("3", "Three")]
    service, _, corpus = _built(tmp_path, accepted)
    path = tmp_path / "derived/proposition-relations/RAN1" / corpus.manifest.relation_corpus_id
    pair_path = path / "pair-candidates.jsonl.gz"
    with gzip.open(pair_path, "rt") as stream:
        records = [json.loads(line) for line in stream]
    records.pop()
    raw = "".join(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
                  for value in records).encode()
    with pair_path.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as zipped:
            zipped.write(raw)
    manifest_path = path / "corpus.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["eligible_pair_count"] = len(records)
    manifest["pair_artifact_checksum"] = digest(records)
    manifest["corpus_checksum"] = digest({key: value for key, value in manifest.items()
                                           if key not in {"relation_corpus_id", "corpus_checksum"}})
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(PropositionRelationCorpusStaleError, match="not regenerable"):
        service.load(corpus.manifest.relation_corpus_id)


def test_review_tampering_is_stale(tmp_path):
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "DISTINCT")
    path = tmp_path / "derived/proposition-relations/RAN1" / corpus.manifest.relation_corpus_id
    record = json.loads((path / "reviews.jsonl").read_text())
    record["decision"] = "CONFLICTING"
    (path / "reviews.jsonl").write_text(json.dumps(record) + "\n")
    with pytest.raises(PropositionRelationCorpusStaleError):
        service.load(corpus.manifest.relation_corpus_id)


def test_review_basis_is_revalidated_against_source_proposition(tmp_path):
    from threegpp.propositions.rules import digest
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "DISTINCT")
    path = tmp_path / "derived/proposition-relations/RAN1" / corpus.manifest.relation_corpus_id
    review_path = path / "reviews.jsonl"
    record = json.loads(review_path.read_text())
    record["left_basis"][0]["exact_text"] = "fabricated"
    record["review_id"] = "proposition-relation-review-" + digest(
        {key: value for key, value in record.items() if key != "review_id"})
    review_path.write_text(json.dumps(record) + "\n")
    with pytest.raises(PropositionRelationCorpusStaleError, match="basis conflict"):
        service.load(corpus.manifest.relation_corpus_id)


def test_manifest_identity_tampering_is_stale_even_with_recomputed_checksum(tmp_path):
    from threegpp.propositions.rules import digest
    service, _, corpus = _built(tmp_path)
    path = tmp_path / "derived/proposition-relations/RAN1" / corpus.manifest.relation_corpus_id
    manifest_path = path / "corpus.json"
    record = json.loads(manifest_path.read_text())
    record["source_profile_id"] = "tampered-profile"
    record["corpus_checksum"] = digest({key: value for key, value in record.items()
                                         if key not in {"relation_corpus_id", "corpus_checksum"}})
    manifest_path.write_text(json.dumps(record))
    with pytest.raises(PropositionRelationCorpusStaleError, match="identity conflict"):
        service.load(corpus.manifest.relation_corpus_id)


def test_accepted_relation_artifact_tampering_is_stale(tmp_path):
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "DISTINCT")
    path = tmp_path / "derived/proposition-relations/RAN1" / corpus.manifest.relation_corpus_id
    with gzip.open(path / "accepted-relations.jsonl.gz", "wt") as stream:
        stream.write("")
    with pytest.raises(PropositionRelationCorpusStaleError, match="accepted relation artifact"):
        service.load(corpus.manifest.relation_corpus_id)


def test_upstream_checksum_change_is_stale(tmp_path):
    service, source, corpus = _built(tmp_path)
    source.checksum = "d" * 64
    with pytest.raises(PropositionRelationCorpusStaleError):
        service.load(corpus.manifest.relation_corpus_id)


def test_new_upstream_accepted_proposition_makes_relation_corpus_stale(tmp_path):
    service, source, corpus = _built(tmp_path)
    source.accepted = source.accepted + [_proposition("3", "Three Corp.")]
    with pytest.raises(PropositionRelationCorpusStaleError, match="source changed"):
        service.load(corpus.manifest.relation_corpus_id)


def test_changed_upstream_accepted_identity_makes_relation_corpus_stale(tmp_path):
    service, source, corpus = _built(tmp_path)
    source.accepted[0] = source.accepted[0].model_copy(
        update={"proposition_id": "accepted-proposition-changed"})
    with pytest.raises(PropositionRelationCorpusStaleError, match="source changed"):
        service.load(corpus.manifest.relation_corpus_id)


def test_renderer_uses_required_labels_and_warning(tmp_path):
    _, _, corpus = _built(tmp_path)
    rendered = render_proposition_relations(corpus, provenance=True)
    for label in ("PAIR", "LEFT PROPOSITION", "RIGHT PROPOSITION", "RELATION REVIEW"):
        assert label in rendered
    assert "researcher annotations" in rendered and "meeting outcomes" in rendered


def test_renderer_shows_exact_bilateral_bases_after_review(tmp_path):
    service, _, corpus = _built(tmp_path)
    pair = corpus.pair_candidates[0]
    reviewed = service.review(corpus.manifest.relation_corpus_id, pair.pair_id, "DISTINCT")
    rendered = render_proposition_relations(reviewed)
    assert "Left basis [0:0:" in rendered and "Right basis [0:0:" in rendered


@pytest.mark.parametrize(("offset", "limit"), [(-1, 20), (0, 0), (0, 101)])
def test_renderer_enforces_bounded_batch(offset, limit, tmp_path):
    _, _, corpus = _built(tmp_path)
    with pytest.raises(ValueError):
        render_proposition_relations(corpus, offset=offset, limit=limit)


def test_runtime_artifacts_are_git_ignored():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["git", "check-ignore",
        "data/derived/proposition-relations/RAN1/example/corpus.json"],
        cwd=root, text=True, capture_output=True)
    assert result.returncode == 0


def test_service_has_no_acquisition_dependency(tmp_path):
    service, _ = _service(tmp_path)
    assert not hasattr(service, "downloader")


def test_pair_model_has_no_inferred_score_or_stance(tmp_path):
    service, _ = _service(tmp_path)
    pair = service.build(_request(), persist=False).pair_candidates[0]
    assert not set(type(pair).model_fields) & {
        "score", "similarity", "stance", "consensus", "adoption", "embedding"}


def test_basis_model_rejects_reverse_range():
    with pytest.raises(ValueError):
        RelationBasisSpan(segment_index=0, char_start=3, char_end=2, exact_text="")


def test_relation_provenance_keeps_both_evidence_refs(tmp_path):
    service, _, corpus = _built(tmp_path)
    result = service.review(corpus.manifest.relation_corpus_id,
                            corpus.pair_candidates[0].pair_id, "NOT_COMPARABLE")
    relation = result.accepted_relations[0]
    assert relation.left_evidence_refs and relation.right_evidence_refs
    assert relation.left_source_review_id and relation.right_source_review_id


def test_topic_agnostic_non_wireless_fixture(tmp_path):
    accepted = [_proposition("1", "Farm Lab", text="Irrigate when soil is dry."),
                _proposition("2", "Crop Institute", text="Measure moisture before watering.")]
    service, _, corpus = _built(tmp_path, accepted)
    reviewed = service.review(corpus.manifest.relation_corpus_id,
        corpus.pair_candidates[0].pair_id, "OVERLAPPING")
    assert reviewed.accepted_relations[0].decision is PropositionRelationDecision.OVERLAPPING


def test_cli_parses_all_relation_commands():
    from threegpp.cli import build_parser
    parser = build_parser()
    build = parser.parse_args(["build-proposition-relations", "--proposition-corpus", "source"])
    show = parser.parse_args(["show-proposition-relations", "--corpus", "relations"])
    review = parser.parse_args(["review-proposition-relation", "--corpus", "relations",
                                "--pair", "pair", "--decision", "EQUIVALENT"])
    assert build.command == "build-proposition-relations"
    assert show.limit == 20 and show.offset == 0
    assert review.decision == "EQUIVALENT" and review.update is False
