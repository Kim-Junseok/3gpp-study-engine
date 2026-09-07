from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.cli import main
from threegpp.documents.models import (
    DocumentReceipt,
    ExtractionStatus,
    NormalizationIdentity,
    PackageMember,
    RawArtifact,
    RetentionState,
)
from threegpp.evidence import EvidenceExtractionService, classify_document_role
from threegpp.models import (
    DetectionBasis,
    DocumentRole,
    EvidenceExtractionRequest,
    EvidenceKind,
    EvidenceScope,
    TDocMetadata,
)


def _block(block_id, text, *, kind="paragraph", heading=None, level=None, rows=None):
    return {
        "block_id": block_id, "type": kind, "text": text,
        "member_filename": "paper.docx", "order": int(block_id[1:]),
        "page_number": 3, "heading_level": level,
        "heading_path": heading or [], "rows": rows,
        "sheet_name": "Evidence" if kind == "table" else None,
    }


def _document(repo, root, tdoc_id, blocks, *, title="HARQ contribution",
              organizations=None, identity="raw-1", status=ExtractionStatus.PARSED):
    organizations = ["Nokia"] if organizations is None else organizations
    relative = Path("normalized/documents/ran1/125") / tdoc_id / "document.jsonl.gz"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = gzip.compress(
        "".join(json.dumps(block) + "\n" for block in blocks).encode(), mtime=0
    )
    path.write_bytes(payload)
    raw_path = root / "raw" / f"{tdoc_id}.zip"
    raw_path.parent.mkdir(exist_ok=True)
    raw_path.write_bytes(b"raw")
    raw = RawArtifact(
        source_url=f"https://example.test/{tdoc_id}.zip", local_path=raw_path,
        filename=f"{tdoc_id}.zip", retrieved_at=datetime.now(timezone.utc),
        media_type="application/zip", byte_size=3, sha256=identity,
        retention=RetentionState.CACHE,
    )
    receipt = DocumentReceipt(
        tdoc_id=tdoc_id, working_group="RAN1", meeting="125", raw=raw,
        members=[PackageMember(
            filename="paper.docx", media_type="application/docx", byte_size=1,
            sha256="member", extraction_status=status,
        )],
        primary_member="paper.docx", extraction_status=status,
        parser_versions={"docx": "1"},
        normalization_identity=NormalizationIdentity(
            raw_sha256=identity, parser_members={"paper.docx": "docx@1"},
            normalized_schema_version="1",
        ),
        normalized_path=relative, text_path=Path("unused"),
        normalized_checksum=hashlib.sha256(payload).hexdigest(),
        text_checksum="unused", block_count=len(blocks), text_length=100,
    )
    repo.upsert_tdoc(TDocMetadata(
        tdoc_id=tdoc_id, working_group="RAN1", meeting="125",
        title=title, organizations=organizations,
        source_organization_raw="; ".join(organizations),
    ))
    repo.upsert_document_receipt(receipt)
    return receipt


def test_document_roles_are_conservative_and_explainable():
    contribution = TDocMetadata(
        tdoc_id="R1-1", working_group="RAN1", meeting="125",
        title="HARQ options", organizations=["Nokia"],
    )
    report = contribution.model_copy(update={
        "title": "Report of RAN1#125 meeting", "organizations": ["ETSI MCC"],
    })
    agenda = report.model_copy(update={"title": "Agenda for RAN1#125"})
    chair = report.model_copy(update={"title": "Chair material for RAN1#125"})
    unknown = report.model_copy(update={"title": "Administrative document"})

    assert classify_document_role(contribution).role is DocumentRole.CONTRIBUTION
    assert classify_document_role(report).role is DocumentRole.MEETING_REPORT
    assert classify_document_role(agenda).role is DocumentRole.AGENDA
    assert classify_document_role(chair).role is DocumentRole.CHAIR_MATERIAL
    assert classify_document_role(unknown).role is DocumentRole.UNKNOWN
    assert classify_document_role(report).basis


def test_contribution_extraction_multiblock_context_and_hard_agreement_guard(tmp_path):
    blocks = [
        _block("b000001", "Proposal 1: Reduce HARQ retransmission delay."),
        _block("b000002", "Proposal 2"),
        _block("b000003", "Use immediate RLC recovery."),
        _block("b000004", "Observation 1: Timer expiry adds delay."),
        _block("b000005", "Conclusion: Option A performs better."),
        _block("b000006", "We agree that option 2 should be selected."),
        _block("b000007", "Agreement: Option 2"),
        _block("b000008", "This is left for further study."),
        _block("b000009", "Proposals", kind="heading", level=1, heading=["Proposals"]),
        _block("b000010", "Apply a bounded timer.", heading=["Proposals"]),
        _block("b000011", "Use one retransmission.", heading=["Proposals"]),
        _block("b000012", "Other", kind="heading", level=1, heading=["Other"]),
        _block("b000013", "This unmarked paragraph is outside the section.", heading=["Other"]),
    ]
    with MetadataRepository(tmp_path / "db.duckdb") as repo:
        receipt = _document(repo, tmp_path, "R1-1000", blocks)
        service = EvidenceExtractionService(repo, tmp_path)
        first = service.extract_document(receipt)
        items = service.list_evidence(EvidenceExtractionRequest(tdoc_ids=["R1-1000"]))
        first_dump = [item.model_dump(mode="json") for item in items]
        second = service.extract_document(receipt)

        assert first.evidence_extracted == 7
        assert first.candidates_rejected_by_authority == 2
        assert second.reused
        assert first_dump == [item.model_dump(mode="json") for item in service.list_evidence()]
        assert {(item.kind, item.scope) for item in items} == {
            (EvidenceKind.PROPOSAL, EvidenceScope.CONTRIBUTION),
            (EvidenceKind.OBSERVATION, EvidenceScope.CONTRIBUTION),
            (EvidenceKind.CONCLUSION, EvidenceScope.CONTRIBUTION),
            (EvidenceKind.FFS, EvidenceScope.CONTRIBUTION),
        }
        assert all(item.kind is not EvidenceKind.AGREEMENT for item in items)
        assert all(item.source_organizations == ["Nokia"] for item in items)
        proposal_two = next(item for item in items if item.ordinal == 2)
        assert proposal_two.statement_text == "Proposal 2\nUse immediate RLC recovery."
        assert [span.evidence_ref.block_id for span in proposal_two.evidence_refs] == [
            "b000002", "b000003",
        ]
        assert all(item.evidence_refs[0].evidence_ref.block_id != "b000013" for item in items)
        evidence, sources = service.get_evidence_sources(proposal_two.evidence_id)
        assert evidence == proposal_two
        assert [block["block_id"] for block in sources] == ["b000002", "b000003"]

        repo.upsert_tdoc(TDocMetadata(
            tdoc_id="R1-1000", working_group="RAN1", meeting="125",
            title="HARQ contribution", organizations=["Samsung"],
            source_organization_raw="Samsung",
        ))
        metadata_changed = service.extract_document(receipt)
        assert not metadata_changed.reused
        assert all(item.source_organizations == ["Samsung"] for item in service.list_evidence())
        filtered = service.list_evidence(EvidenceExtractionRequest(
            organizations=["Samsung"], evidence_kinds=[EvidenceKind.PROPOSAL],
            scopes=[EvidenceScope.CONTRIBUTION],
            document_roles=[DocumentRole.CONTRIBUTION],
        ))
        assert len(filtered) == 4
        assert not service.list_evidence(EvidenceExtractionRequest(organizations=["Nokia"]))


def test_meeting_report_heading_inline_conclusion_ffs_and_decision(tmp_path):
    blocks = [
        _block("b000001", "Agreements", kind="heading", level=1, heading=["Agreements"]),
        _block("b000002", "1. The UE shall use a bounded timer.", heading=["Agreements"]),
        _block("b000003", "2. FFS whether a second timer is needed.", heading=["Agreements"]),
        _block("b000004", "Other", kind="heading", level=1, heading=["Other"]),
        _block("b000005", "An unmarked informational paragraph.", heading=["Other"]),
        _block("b000006", "Conclusion: The meeting concluded to retain Option A."),
        _block("b000007", "It was agreed that the timer is configurable."),
        _block("b000008", "The meeting decided to document the issue."),
    ]
    with MetadataRepository(tmp_path / "db.duckdb") as repo:
        receipt = _document(
            repo, tmp_path, "R1-1001", blocks,
            title="Report of RAN1#125 meeting", organizations=["ETSI MCC"],
        )
        service = EvidenceExtractionService(repo, tmp_path)
        outcome = service.extract_document(receipt)
        items = service.list_evidence()

        assert outcome.document_role is DocumentRole.MEETING_REPORT
        assert {(item.kind, item.scope) for item in items} == {
            (EvidenceKind.AGREEMENT, EvidenceScope.MEETING),
            (EvidenceKind.CONCLUSION, EvidenceScope.MEETING),
            (EvidenceKind.FFS, EvidenceScope.MEETING),
            (EvidenceKind.DECISION, EvidenceScope.MEETING),
        }
        assert all(not item.source_organizations for item in items)
        agreement = next(item for item in items if item.evidence_refs[0].evidence_ref.block_id == "b000002")
        assert agreement.detection_basis is DetectionBasis.HEADING_CONTEXT
        assert not any(item.evidence_refs[0].evidence_ref.block_id == "b000005" for item in items)


def test_table_evidence_preserves_row_cell_and_authority(tmp_path):
    contribution_table = _block(
        "b000001", None, kind="table",
        rows=[["Proposal 3", "Use compact feedback."], ["Agreement", "Not authoritative."]],
    )
    report_table = _block(
        "b000001", None, kind="table",
        rows=[
            ["Agreement", "Use bounded feedback."],
            ["FFS", "Timer value."],
            ["Proposal 1", "Not a meeting-record evidence kind."],
        ],
    )
    with MetadataRepository(tmp_path / "db.duckdb") as repo:
        contribution = _document(repo, tmp_path, "R1-1002", [contribution_table])
        report = _document(
            repo, tmp_path, "R1-1003", [report_table],
            title="Report of RAN1#125 meeting", organizations=["ETSI MCC"],
        )
        service = EvidenceExtractionService(repo, tmp_path)
        assert service.extract_document(contribution).candidates_rejected_by_authority == 1
        assert service.extract_document(report).candidates_rejected_by_authority == 1
        items = service.list_evidence()

        proposal = next(item for item in items if item.tdoc_id == "R1-1002")
        assert proposal.kind is EvidenceKind.PROPOSAL
        assert proposal.statement_text == "Proposal 3\tUse compact feedback."
        assert proposal.evidence_refs[0].row_index == 0
        assert proposal.evidence_refs[0].cell_index == 0
        report_items = [item for item in items if item.tdoc_id == "R1-1003"]
        assert {item.kind for item in report_items} == {EvidenceKind.AGREEMENT, EvidenceKind.FFS}
        assert all(item.detection_basis is DetectionBasis.TABLE_LABEL for item in items)


def test_incremental_ruleset_and_stale_source_safety(tmp_path, monkeypatch):
    with MetadataRepository(tmp_path / "db.duckdb") as repo:
        receipt = _document(repo, tmp_path, "R1-1004", [
            _block("b000001", "Proposal 1: Use Option A."),
        ])
        service = EvidenceExtractionService(repo, tmp_path)
        service.extract_document(receipt)
        original = service.list_evidence()[0]

        changed = _document(repo, tmp_path, "R1-1004", [
            _block("b000001", "Proposal 1: Use Option B."),
        ], identity="raw-2")
        assert not service.list_evidence()
        assert repo.connection.execute(
            "SELECT status FROM semantic_evidence_state WHERE tdoc_id='R1-1004'"
        ).fetchone()[0] == "STALE"
        service.extract_document(changed)
        changed_item = service.list_evidence()[0]
        assert changed_item.evidence_id == original.evidence_id
        assert changed_item.statement_text != original.statement_text

        monkeypatch.setattr(
            "threegpp.evidence.service.EXTRACTION_RULESET_VERSION", "explicit-structural-v2"
        )
        outcome = service.extract_document(changed)
        rules_changed_item = service.list_evidence()[0]
        assert not outcome.reused
        assert rules_changed_item.evidence_id != changed_item.evidence_id

        state = repo.connection.execute(
            "SELECT evidence_path FROM semantic_evidence_state WHERE tdoc_id='R1-1004'"
        ).fetchone()[0]
        path = tmp_path / state
        payload = json.loads(gzip.decompress(path.read_bytes()).decode().strip())
        payload["evidence_refs"][0]["evidence_ref"]["block_id"] = "b999999"
        changed_payload = gzip.compress(
            (json.dumps(payload, sort_keys=True) + "\n").encode(), mtime=0
        )
        path.write_bytes(changed_payload)
        repo.connection.execute(
            "UPDATE semantic_evidence_state SET evidence_checksum=? WHERE tdoc_id='R1-1004'",
            [hashlib.sha256(changed_payload).hexdigest()],
        )
        assert not service.list_evidence()
        assert repo.connection.execute(
            "SELECT status FROM semantic_evidence_state WHERE tdoc_id='R1-1004'"
        ).fetchone()[0] == "STALE"


def test_evidence_cli_extract_list_and_inspect(tmp_path, capsys):
    database = tmp_path / "db.duckdb"
    with MetadataRepository(database) as repo:
        _document(repo, tmp_path, "R1-1005", [
            _block("b000001", "Proposal 1: Use deterministic recovery."),
        ])
    common = ["--db", str(database), "--data-dir", str(tmp_path)]
    assert main(common + [
        "extract-evidence", "--wg", "RAN1", "--meeting", "125", "--tdoc", "R1-1005",
    ]) == 0
    extraction = json.loads(capsys.readouterr().out)
    assert extraction[0]["evidence_extracted"] == 1

    assert main(common + [
        "list-evidence", "--wg", "RAN1", "--meeting", "125", "--kind", "proposal",
    ]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert len(listed) == 1

    assert main(common + [
        "inspect-evidence", "--evidence-id", listed[0]["evidence_id"],
    ]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["evidence"]["statement_text"] == listed[0]["statement_text"]
    assert inspected["source_blocks"][0]["block_id"] == "b000001"
