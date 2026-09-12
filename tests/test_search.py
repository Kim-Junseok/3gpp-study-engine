from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.documents.models import (
    DocumentReceipt, ExtractionStatus, NormalizationIdentity, PackageMember,
    RawArtifact, RetentionState,
)
from threegpp.models import EvidenceSearchQuery, TDocMetadata
from threegpp.search import EvidenceSearchService, tokenize


def _document(repo: MetadataRepository, root: Path, tdoc_id: str, blocks: list[dict], *,
              organization: str = "Nokia", title: str = "HARQ study",
              identity: str = "raw-1") -> DocumentReceipt:
    relative = Path("normalized/documents/ran1/125") / tdoc_id / "document.jsonl.gz"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = gzip.compress("".join(json.dumps(block) + "\n" for block in blocks).encode(), mtime=0)
    path.write_bytes(payload)
    raw_path = root / "raw" / f"{tdoc_id}.zip"; raw_path.parent.mkdir(exist_ok=True); raw_path.write_bytes(b"raw")
    raw = RawArtifact(source_url=f"https://example.test/{tdoc_id}.zip", local_path=raw_path,
        filename=f"{tdoc_id}.zip", retrieved_at=datetime.now(timezone.utc), media_type="application/zip",
        byte_size=3, sha256=identity, retention=RetentionState.CACHE)
    member_names = sorted({block["member_filename"] for block in blocks})
    receipt = DocumentReceipt(tdoc_id=tdoc_id, working_group="RAN1", meeting="125", raw=raw,
        members=[PackageMember(filename=name, media_type="application/docx", byte_size=1, sha256="x",
            extraction_status=ExtractionStatus.PARSED) for name in member_names], primary_member=member_names[0],
        extraction_status=ExtractionStatus.PARSED, parser_versions={"docx": "1"},
        normalization_identity=NormalizationIdentity(raw_sha256=identity, parser_members={member_names[0]: "docx@1"}, normalized_schema_version="1"),
        normalized_path=relative, text_path=Path("unused"), normalized_checksum=hashlib.sha256(payload).hexdigest(),
        text_checksum="unused", block_count=len(blocks), text_length=100)
    repo.upsert_tdoc(TDocMetadata(tdoc_id=tdoc_id, working_group="RAN1", meeting="125", title=title,
        organizations=[organization], source_organization_raw=organization))
    repo.upsert_document_receipt(receipt)
    return receipt


def _block(block_id: str, text: str | None, *, kind: str = "paragraph", heading=None, rows=None):
    return {"block_id": block_id, "type": kind, "text": text, "member_filename": "paper.docx",
        "order": int(block_id[1:]), "page_number": 2, "heading_level": None,
        "heading_path": heading or [], "rows": rows, "sheet_name": "Results" if kind == "table" else None}


def test_technical_tokenizer_is_deterministic():
    assert tokenize("HARQ HARQ-ACK GNSS-less multi-TRP 6G NR-NTN RAN1#125 PUSCH/PDCCH") == [
        "harq", "harq-ack", "harq", "ack", "gnss-less", "gnss", "less",
        "multi-trp", "multi", "trp", "6g", "nr-ntn", "nr", "ntn",
        "ran1#125", "ran1", "125", "pusch", "pdcch",
    ]


def test_phrase_filters_table_ranking_aggregation_and_integrity(tmp_path):
    with MetadataRepository(tmp_path / "metadata.duckdb") as repo:
        service = EvidenceSearchService(repo, tmp_path)
        first = _document(repo, tmp_path, "R1-0001", [
            _block("b000001", "HARQ feedback latency is reduced.", heading=["HARQ feedback"]),
            _block("b000002", None, kind="table", rows=[["PUSCH", "contention based uplink"]]),
            _block("b000003", "HARQ appears once in a deliberately much longer block " + "padding " * 30),
        ])
        second = _document(repo, tmp_path, "R1-0002", [
            _block("b000001", "HARQ HARQ HARQ feedback is evaluated.")
        ], organization="Ericsson", title="Other")
        assert service.index_document(first).reused is False
        assert service.index_document(first).reused is True
        service.index_document(second)

        phrase = service.search_evidence(EvidenceSearchQuery(query='"HARQ feedback"'))
        assert phrase[0].evidence.tdoc_id == "R1-0001"
        assert phrase[0].phrase_match and phrase[0].match_kind == "exact_phrase"
        assert phrase[0].score_explanation["phrase_bonus"] == 2.0
        assert service.get_evidence_block(phrase[0].evidence)["block_id"] == "b000001"
        # Phrase matching respects token boundaries: ``arq`` is not a suffix
        # match inside the technical token ``harq``.
        assert not service.search_evidence(EvidenceSearchQuery(query='"ARQ feedback"'))

        table = service.search_evidence(EvidenceSearchQuery(query='"contention based uplink"', block_types=["table"]))
        assert [(hit.evidence.block_id, hit.evidence.sheet) for hit in table] == [("b000002", "Results")]
        assert table[0].snippet == "PUSCH\tcontention based uplink"

        nokia = service.search_evidence(EvidenceSearchQuery(query="HARQ", organizations=["Nokia"], tdoc_ids=["R1-0001"]))
        assert {hit.evidence.tdoc_id for hit in nokia} == {"R1-0001"}
        assert nokia[0].evidence.block_id == "b000001"  # heading and length normalization win
        aggregated = service.search_tdocs(EvidenceSearchQuery(query="HARQ", limit=20))
        assert aggregated[0].matching_block_count >= 1
        assert aggregated[0].best_block.score <= aggregated[0].aggregate_score

        (tmp_path / first.normalized_path).unlink()
        assert service.search_evidence("HARQ")
        # Searching the missing indexed document verifies and evicts its stale rows.
        assert all(hit.evidence.tdoc_id != "R1-0001" for hit in service.search_evidence("HARQ"))
        status = repo.connection.execute("SELECT status FROM search_index_state WHERE tdoc_id='R1-0001'").fetchone()[0]
        assert status == "STALE"


def test_changed_identity_replaces_only_one_document_and_unsupported_is_not_indexed(tmp_path):
    with MetadataRepository(tmp_path / "db.duckdb") as repo:
        service = EvidenceSearchService(repo, tmp_path)
        receipt = _document(repo, tmp_path, "R1-0003", [_block("b000001", "old HARQ")])
        service.index_document(receipt)
        unrelated = _document(repo, tmp_path, "R1-0007", [_block("b000001", "stable NR evidence")])
        service.index_document(unrelated)
        unrelated_before = repo.connection.execute(
            "SELECT term,term_frequency FROM search_postings WHERE tdoc_id='R1-0007' ORDER BY term"
        ).fetchall()
        changed = _document(repo, tmp_path, "R1-0003", [_block("b000001", "new PDCCH")], identity="raw-2")
        assert not service.index_document(changed).reused
        assert not service.search_evidence("old")
        assert service.search_evidence("PDCCH")[0].evidence.block_id == "b000001"
        assert repo.connection.execute(
            "SELECT term,term_frequency FROM search_postings WHERE tdoc_id='R1-0007' ORDER BY term"
        ).fetchall() == unrelated_before
        unsupported = changed.model_copy(update={"tdoc_id": "R1-0004", "extraction_status": ExtractionStatus.UNSUPPORTED_FORMAT,
            "normalized_path": None, "normalized_checksum": None})
        outcome = service.index_document(unsupported)
        assert outcome.status == "NOT_INDEXABLE" and outcome.indexed_blocks == 0


def test_stale_index_cannot_return_a_valid_sibling_block(tmp_path):
    with MetadataRepository(tmp_path / "db.duckdb") as repo:
        service = EvidenceSearchService(repo, tmp_path)
        receipt = _document(repo, tmp_path, "R1-0005", [
            _block("b000001", "HARQ first"),
            _block("b000002", "HARQ second"),
        ])
        service.index_document(receipt)
        repo.connection.execute(
            "INSERT INTO search_blocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ["R1-0005", "RAN1", "125", "paper.docx", "b999999", "paragraph", "[]", None, None, 1],
        )
        repo.connection.execute(
            "INSERT INTO search_postings VALUES (?, ?, ?, ?, ?, ?, ?)",
            ["harq", "R1-0005", "RAN1", "125", "paper.docx", "b999999", 1],
        )

        assert not service.search_evidence("HARQ")
        state = repo.connection.execute(
            "SELECT status,indexed_block_count,posting_count FROM search_index_state "
            "WHERE tdoc_id='R1-0005'"
        ).fetchone()
        assert state == ("STALE", 0, 0)


def test_changed_receipt_checksum_is_stale_until_reindexed(tmp_path):
    with MetadataRepository(tmp_path / "db.duckdb") as repo:
        service = EvidenceSearchService(repo, tmp_path)
        receipt = _document(repo, tmp_path, "R1-0006", [
            _block("b000001", "old HARQ evidence"),
        ])
        service.index_document(receipt)
        _document(repo, tmp_path, "R1-0006", [
            _block("b000001", "new PDCCH evidence"),
        ], identity="raw-2")

        assert not service.search_evidence("HARQ")
        state = repo.connection.execute(
            "SELECT status,indexed_block_count,posting_count FROM search_index_state "
            "WHERE tdoc_id='R1-0006'"
        ).fetchone()
        assert state == ("STALE", 0, 0)
