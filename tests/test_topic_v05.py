from datetime import datetime, timezone

from threegpp.models import (
    AgreementDisposition, DetectionBasis, DocumentRole, EvidenceKind, EvidenceRef,
    EvidenceScope, EvidenceSpan, SemanticEvidence, TDocMetadata, TopicEvidenceItem,
)
from threegpp.topic import (
    classify_agreement_disposition, extract_explicit_links, get_evidence_context,
    get_topic_timeline, resolve_authority_meeting,
)


def _evidence(text, *, block="b000001", kind=EvidenceKind.AGREEMENT,
              scope=EvidenceScope.MEETING, role=DocumentRole.MEETING_REPORT):
    ref = EvidenceRef(tdoc_id="R1-2603481", working_group="RAN1", meeting="125",
                      member="report.docx", block_id=block, block_type="paragraph",
                      heading_path=["Agreements"], page=1)
    return SemanticEvidence(evidence_id="e-" + block, kind=kind, scope=scope,
        working_group="RAN1", meeting="125", tdoc_id="R1-2603481",
        document_role=role, document_role_basis=["fixture"], source_organizations=[],
        evidence_refs=[EvidenceSpan(evidence_ref=ref, sequence=0)], statement_text=text,
        detection_basis=DetectionBasis.EXPLICIT_LABEL, matched_cue="Agreement:",
        rule_id="fixture", rule_version="1", extracted_at=datetime.now(timezone.utc),
        normalization_identity={"fixture": "1"}, evidence_schema_version="1")


def test_report_authority_preserves_discovery_raw_alias_and_provenance():
    metadata = TDocMetadata(tdoc_id="R1-2603481", working_group="RAN1", meeting="125",
        title="Report of RAN1#124b meeting", organizations=["ETSI MCC"])
    authority = resolve_authority_meeting(metadata, DocumentRole.MEETING_REPORT)
    assert authority.discovery_meeting.meeting_id == "125"
    assert authority.authority_meeting.meeting_id == "124bis"
    assert authority.authority_meeting.raw_text == "RAN1#124b"
    assert authority.rule_id == "meeting-report-title-v1"
    assert resolve_authority_meeting(metadata, DocumentRole.CONTRIBUTION).authority_meeting is None


def test_explicit_dispositions_and_study_never_becomes_adoption():
    fixtures = {
        "Agreement: Study whether and how to support mechanism X.": AgreementDisposition.STUDY,
        "Agreement: Option 2 is selected.": AgreementDisposition.SELECT,
        "Agreement: The draft CR R1-2601985 is endorsed.": AgreementDisposition.ENDORSE,
        "Agreement: The exact mechanism remains open.": AgreementDisposition.UNCLASSIFIED,
    }
    for statement, expected in fixtures.items():
        result = classify_agreement_disposition(_evidence(statement))
        assert result.disposition is expected
    study = classify_agreement_disposition(_evidence(next(iter(fixtures))))
    assert study.disposition not in {AgreementDisposition.ADOPT, AgreementDisposition.SELECT,
                                     AgreementDisposition.ENDORSE}


def test_bounded_context_stops_at_heading_and_is_literal_not_semantic_evidence():
    evidence = _evidence("Agreement: The upper limit is 1706 bits.")
    blocks = [
        {"block_id": "b000001", "type": "paragraph", "text": evidence.statement_text,
         "member_filename": "report.docx", "heading_path": ["Agreements"]},
        {"block_id": "b000002", "type": "paragraph", "text": "Note1: This does not imply the final maximum is 1706.",
         "member_filename": "report.docx", "heading_path": ["Agreements"]},
        {"block_id": "b000003", "type": "paragraph", "text": "Note2: The exact maximum may be determined later.",
         "member_filename": "report.docx", "heading_path": ["Agreements"]},
        {"block_id": "b000004", "type": "heading", "text": "Next Heading",
         "member_filename": "report.docx", "heading_path": ["Next Heading"]},
    ]
    context = get_evidence_context(evidence, blocks)
    assert [item.evidence_ref.block_id for item in context] == ["b000002", "b000003"]
    assert all(not isinstance(item, SemanticEvidence) for item in context)


def test_explicit_endorsement_link_and_authority_timeline():
    evidence = _evidence("Agreement: The draft CR R1-2601985 is endorsed.")
    links = extract_explicit_links(evidence)
    assert [(item.relationship.value, item.target_tdoc_id) for item in links] == [
        ("endorses_tdoc", "R1-2601985")]
    metadata = TDocMetadata(tdoc_id=evidence.tdoc_id, working_group="RAN1", meeting="125",
        title="Report of RAN1#124b meeting", organizations=["ETSI MCC"])
    item = TopicEvidenceItem(evidence=evidence,
        meeting_authority=resolve_authority_meeting(metadata, DocumentRole.MEETING_REPORT),
        disposition=classify_agreement_disposition(evidence), explicit_links=links)
    timeline = get_topic_timeline([item])
    assert timeline[0].authority_meeting.meeting_id == "124bis"
    assert timeline[0].events[0].meeting_authority.discovery_meeting.meeting_id == "125"


def test_multiblock_disposition_and_link_point_to_literal_body():
    text = 'The draft CR R1-1234567 is endorsed.'
    e = _evidence('Agreement:\n' + text)
    label = e.evidence_refs[0].model_copy(update={'char_start': 0, 'char_end': 10})
    body = label.model_copy(update={
        'evidence_ref': label.evidence_ref.model_copy(update={'block_id': 'b000002'}),
        'sequence': 1, 'char_end': len(text)})
    e = e.model_copy(update={'evidence_refs': [label, body]})
    disposition = classify_agreement_disposition(e)
    link = extract_explicit_links(e)[0]
    for span, literal in [(disposition.evidence_span, disposition.matched_cue),
                          (link.evidence_span, link.matched_literal)]:
        assert span.evidence_ref.block_id == 'b000002'
        assert text[span.char_start:span.char_end] == literal


def test_pending_selection_does_not_claim_completed_selection():
    for text in [
        'Agreement: Repetition numbers are to be selected from candidate values.',
        'Agreement: Down select one from the following options in RAN1#125:',
        'Agreement: RAN1 further select from the following candidate coding schemes:',
        'Agreement: Down-select between the following options:',
    ]:
        assert classify_agreement_disposition(_evidence(text)).disposition is AgreementDisposition.UNCLASSIFIED
    assert classify_agreement_disposition(_evidence(
        'Agreement: One of the following options is down-selected:')).disposition is AgreementDisposition.SELECT


import gzip
import hashlib
import json
import pytest
from threegpp.db import MetadataRepository
from threegpp.evidence import EvidenceExtractionService
from threegpp.models import TopicStudyRequest, normalize_report_meeting_identifier
from threegpp.topic import TopicStudyService
from test_evidence import _document, _block


@pytest.fixture
def topic_corpus(tmp_path):
    from threegpp.search import EvidenceSearchService
    from threegpp.documents.models import ExtractionStatus
    with MetadataRepository(tmp_path / 'db.duckdb') as repo:
        report = _document(repo, tmp_path, 'R1-1000001', [
            _block('b000001', 'Agreement:'),
            _block('b000002', 'Study HARQ failure indication.'),
            _block('b000003', 'Note1: This does not select a mechanism.'),
            _block('b000004', 'Agreement: The HARQ draft CR R1-1000009 is endorsed.'),
        ], title='Report of RAN1#124b meeting', organizations=['ETSI MCC'])
        contribution = _document(repo, tmp_path, 'R1-1000002', [
            _block('b000001', 'Conclusion: HARQ explicit DCI indication.'),
            _block('b000002', 'Proposal: HARQ failure indication.'),
        ], organizations=['Example Company'])
        _document(repo, tmp_path, 'R1-1000003', [_block('b000001', 'HARQ background')])
        _document(repo, tmp_path, 'R1-1000004', [_block('b000001', '')], status=ExtractionStatus.UNSUPPORTED_FORMAT)
        repo.upsert_tdoc(TDocMetadata(tdoc_id='R2-1000001',working_group='RAN2',meeting='133'))
        for receipt in [report, contribution]:
            EvidenceExtractionService(repo, tmp_path).extract_document(receipt)
            EvidenceSearchService(repo, tmp_path).index_document(receipt)
        yield TopicStudyService(repo, tmp_path), report


def test_bundle_layers_coverage_limits_and_unrelated_link(topic_corpus):
    service, _ = topic_corpus
    request = TopicStudyRequest(query='HARQ', working_groups=['RAN1'])
    first = service.build_topic_study(request)
    assert first == service.build_topic_study(request)
    assert first.lexical_candidates
    assert len(first.meeting_evidence) == 2
    assert len(first.contribution_evidence['Example Company']) == 2
    assert first.meeting_timeline[0].authority_meeting.meeting_id == '124bis'
    assert first.meeting_evidence[0].disposition.disposition is AgreementDisposition.STUDY
    assert first.meeting_evidence[0].context[0].role.value == 'note'
    assert any(i.explicit_links for i in first.meeting_evidence)
    assert any('R1-1000002' in message for message in first.unresolved)
    assert first.coverage.documents_available == 4
    assert first.coverage.documents_normalized == 4
    assert first.coverage.documents_indexable == 2
    assert first.coverage.documents_semantically_extracted == 2
    assert first.coverage.unsupported_documents == 1
    assert first.coverage.meeting_reports_available == 1
    limited = service.build_topic_study(request.model_copy(update={'limit_per_group': 1}))
    assert len(limited.meeting_evidence) == 1
    assert len(limited.contribution_evidence['Example Company']) == 1
    assert any('truncated' in x for x in limited.coverage.limitations)


@pytest.mark.parametrize('version', [
    'TOPIC_STUDY_SCHEMA_VERSION', 'MEETING_AUTHORITY_RULESET_VERSION',
    'AGREEMENT_DISPOSITION_RULESET_VERSION', 'EVIDENCE_CONTEXT_RULESET_VERSION',
])
def test_on_demand_identity_depends_on_versions(topic_corpus, monkeypatch, version):
    import threegpp.topic as topic
    service, _ = topic_corpus
    request = TopicStudyRequest(query='HARQ', working_groups=['RAN1'])
    first = service.build_topic_study(request)
    monkeypatch.setattr(topic, version, 'changed-for-fixture')
    assert service.build_topic_study(request).study_id != first.study_id


def test_identity_changes_with_fresh_same_id_evidence_and_rejects_stale_checksum(topic_corpus):
    service, receipt = topic_corpus
    request = TopicStudyRequest(query='HARQ', working_groups=['RAN1'])
    first = service.build_topic_study(request)
    # Change only a literal body, maintaining the V0.4 span lengths/IDs.
    path = service.data_root / receipt.normalized_path
    payload = gzip.decompress(path.read_bytes()).replace(b'Study HARQ failure', b'Study HARQ process')
    packed = gzip.compress(payload, mtime=0)
    path.write_bytes(packed)
    receipt = receipt.model_copy(update={'normalized_checksum': hashlib.sha256(packed).hexdigest()})
    service.repository.upsert_document_receipt(receipt)
    service.evidence.extract_document(receipt)
    second = service.build_topic_study(request)
    assert first.meeting_evidence[0].evidence.evidence_id == second.meeting_evidence[0].evidence.evidence_id
    assert first.study_id != second.study_id
    service.repository.connection.execute(
        "UPDATE semantic_evidence_state SET evidence_checksum='corrupt' WHERE tdoc_id='R1-1000001'")
    third = service.build_topic_study(request)
    assert not third.meeting_evidence
    assert third.study_id != second.study_id


def test_timeline_order_and_report_aliases():
    items = []
    for meeting in ['125', '124b', '124', '119-e', '99']:
        metadata = TDocMetadata(tdoc_id='R1-1234567', working_group='RAN1', meeting='125',
                               title=f'Report of RAN1#{meeting} meeting')
        items.append(TopicEvidenceItem(evidence=_evidence('Agreement: Study HARQ.'),
            meeting_authority=resolve_authority_meeting(metadata, DocumentRole.MEETING_REPORT)))
    assert [i.authority_meeting.meeting_id for i in get_topic_timeline(items)] == [
        '99', '119-e', '124', '124bis', '125']
    assert normalize_report_meeting_identifier('124bis') == '124bis'


@pytest.mark.parametrize('boundary', ['heading', 'member', 'section', 'unlabelled'])
def test_context_boundaries(boundary):
    e = _evidence('Agreement: A bound.')
    blocks = [dict(block_id='b000001', type='paragraph', text=e.statement_text,
                   member_filename='report.docx', heading_path=['Agreements'])]
    next_block = dict(blocks[0], block_id='b000002', text='Note1: A qualification.')
    if boundary == 'heading': next_block['type'] = 'heading'
    if boundary == 'member': next_block['member_filename'] = 'other.docx'
    if boundary == 'section': next_block['heading_path'] = ['Other']
    if boundary == 'unlabelled': next_block['text'] = 'Unlabelled paragraph.'
    assert get_evidence_context(e, blocks + [next_block]) == []
