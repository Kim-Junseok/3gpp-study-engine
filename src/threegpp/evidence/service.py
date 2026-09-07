from __future__ import annotations

import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.documents.models import DocumentReceipt, ExtractionStatus
from threegpp.models import TDocMetadata
from threegpp.models.evidence import (
    DetectionBasis,
    DocumentRole,
    DocumentRoleClassification,
    EvidenceExtractionOutcome,
    EvidenceExtractionRequest,
    EvidenceKind,
    EvidenceScope,
    EvidenceSpan,
    SemanticEvidence,
)
from threegpp.models.search import EvidenceRef

from .rules import (
    EVIDENCE_SCHEMA_VERSION,
    EXTRACTION_RULESET_VERSION,
    INLINE_RULES,
    LABEL_RULES,
    RULE_VERSION,
    EvidenceRule,
    heading_kind,
    kind_allowed,
    rule_allows,
)


_INDEXABLE = {ExtractionStatus.PARSED, ExtractionStatus.PARTIALLY_PARSED}
_SEMANTIC_WORD = re.compile(r"\b(proposal|observation|agreement|conclusion|decision|ffs)\b", re.I)


def classify_document_role(metadata: TDocMetadata | None) -> DocumentRoleClassification:
    if metadata is None:
        return DocumentRoleClassification(role=DocumentRole.UNKNOWN, basis=["TDoc metadata unavailable"])
    title = (metadata.title or "").casefold()
    descriptor = " ".join(filter(None, [metadata.document_type, metadata.document_category])).casefold()
    organizations = metadata.organizations
    is_mcc = any(item.casefold() == "etsi mcc" for item in organizations)
    if "agenda" in title or "agenda" in descriptor:
        return DocumentRoleClassification(
            role=DocumentRole.AGENDA,
            basis=["title or authoritative document metadata identifies an agenda"],
        )
    if ("chairman" in title or "chair material" in title or "chair material" in descriptor) and is_mcc:
        return DocumentRoleClassification(
            role=DocumentRole.CHAIR_MATERIAL,
            basis=["title identifies chair material", "source organization is ETSI MCC"],
        )
    if is_mcc and (re.search(r"\breport of ran[12]#", title) or "meeting report" in title):
        return DocumentRoleClassification(
            role=DocumentRole.MEETING_REPORT,
            basis=["title identifies a RAN meeting report", "source organization is ETSI MCC"],
        )
    if organizations and any(item.casefold() != "etsi mcc" for item in organizations):
        return DocumentRoleClassification(
            role=DocumentRole.CONTRIBUTION,
            basis=["authoritative source organizations identify contribution submitter(s)"],
        )
    return DocumentRoleClassification(
        role=DocumentRole.UNKNOWN,
        basis=["metadata does not establish contribution or meeting-record authority"],
    )


class EvidenceExtractionService:
    """Deterministic extraction of explicit semantic evidence from normalized blocks."""

    def __init__(self, repository: MetadataRepository, data_root: Path):
        self.repository = repository
        self.connection = repository.connection
        self.data_root = Path(data_root)

    def extract_document(self, receipt: DocumentReceipt) -> EvidenceExtractionOutcome:
        metadata = self.repository.get_tdoc(receipt.working_group, receipt.meeting, receipt.tdoc_id)
        classification = classify_document_role(metadata)
        identity = _identity_json(receipt)
        key = [receipt.tdoc_id, receipt.working_group.value, receipt.meeting]
        if (receipt.extraction_status not in _INDEXABLE or receipt.normalized_path is None
                or receipt.normalization_identity is None):
            return self._clear_and_state(receipt, classification, "NOT_INDEXABLE")
        normalized_path = self.data_root / receipt.normalized_path
        if not normalized_path.is_file() or _sha(normalized_path) != receipt.normalized_checksum:
            return self._clear_and_state(receipt, classification, "STALE")
        current = self.connection.execute(
            "SELECT status,metadata_identity_json,normalization_identity_json,normalized_checksum,evidence_schema_version,"
            "ruleset_version,evidence_path,evidence_checksum,evidence_count,blocks_scanned,"
            "explicit_labels_detected,candidates_rejected,ambiguous_cues_ignored "
            "FROM semantic_evidence_state WHERE tdoc_id=? AND working_group=? AND meeting_number=?",
            key,
        ).fetchone()
        if current and tuple(current[:6]) == (
            "EXTRACTED", _metadata_identity(metadata), identity, receipt.normalized_checksum,
            EVIDENCE_SCHEMA_VERSION, EXTRACTION_RULESET_VERSION,
        ):
            evidence_path = self.data_root / current[6]
            if evidence_path.is_file() and _sha(evidence_path) == current[7]:
                return EvidenceExtractionOutcome(
                    tdoc_id=receipt.tdoc_id,
                    working_group=receipt.working_group,
                    meeting=receipt.meeting,
                    status="EXTRACTED",
                    document_role=classification.role,
                    document_role_basis=classification.basis,
                    evidence_extracted=current[8],
                    blocks_scanned=current[9],
                    explicit_labels_detected=current[10],
                    candidates_rejected_by_authority=current[11],
                    ambiguous_cues_ignored=current[12],
                    reused=True,
                )
        try:
            blocks = _read_blocks(normalized_path)
            evidence, diagnostics = self._extract_blocks(receipt, metadata, classification, blocks)
            evidence.sort(key=_evidence_order)
            relative_path = (
                Path("derived/evidence") / receipt.working_group.value.casefold()
                / receipt.meeting / receipt.tdoc_id / "evidence.jsonl.gz"
            )
            output_path = self.data_root / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            payload = gzip.compress(
                "".join(
                    json.dumps(item.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
                    + "\n" for item in evidence
                ).encode("utf-8"),
                mtime=0,
            )
            output_path.write_bytes(payload)
        except Exception as exc:
            return self._clear_and_state(receipt, classification, "FAILED", error=str(exc)[:500])
        self.connection.execute("BEGIN")
        try:
            self._delete_items(key)
            for sequence, item in enumerate(evidence):
                self.connection.execute(
                    "INSERT INTO semantic_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [
                        item.evidence_id, item.tdoc_id, item.working_group.value, item.meeting,
                        item.kind.value, item.scope.value, item.document_role.value,
                        json.dumps(item.source_organizations, ensure_ascii=False), item.label,
                        item.ordinal, item.detection_basis.value, item.rule_id,
                        item.rule_version, sequence, item.statement_text,
                        item.model_dump_json(),
                    ],
                )
            self._write_state(
                receipt, classification, "EXTRACTED", relative_path, _sha(output_path),
                len(evidence), len(blocks), diagnostics, identity=identity,
            )
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        self.connection.execute("COMMIT")
        return EvidenceExtractionOutcome(
            tdoc_id=receipt.tdoc_id,
            working_group=receipt.working_group,
            meeting=receipt.meeting,
            status="EXTRACTED",
            document_role=classification.role,
            document_role_basis=classification.basis,
            blocks_scanned=len(blocks),
            explicit_labels_detected=diagnostics["labels"],
            evidence_extracted=len(evidence),
            candidates_rejected_by_authority=diagnostics["rejected"],
            ambiguous_cues_ignored=diagnostics["ambiguous"],
        )

    def extract_documents(
        self, request: EvidenceExtractionRequest | None = None
    ) -> list[EvidenceExtractionOutcome]:
        request = request or EvidenceExtractionRequest()
        clauses, values = ["1=1"], []
        for column, wanted in (
            ("working_group", request.working_groups),
            ("meeting_number", request.meetings),
            ("tdoc_id", request.tdoc_ids),
        ):
            if wanted:
                clauses.append(column + " IN (" + ",".join("?" for _ in wanted) + ")")
                values.extend(item.value if hasattr(item, "value") else item for item in wanted)
        rows = self.connection.execute(
            "SELECT receipt_json FROM tdoc_documents WHERE " + " AND ".join(clauses)
            + " ORDER BY working_group,meeting_number,tdoc_id",
            values,
        ).fetchall()
        outcomes = []
        for row in rows:
            receipt = DocumentReceipt.model_validate_json(row[0])
            role = classify_document_role(
                self.repository.get_tdoc(receipt.working_group, receipt.meeting, receipt.tdoc_id)
            ).role
            if request.document_roles and role not in request.document_roles:
                continue
            outcomes.append(self.extract_document(receipt))
        return outcomes

    def list_evidence(
        self, request: EvidenceExtractionRequest | None = None
    ) -> list[SemanticEvidence]:
        request = request or EvidenceExtractionRequest()
        clauses = ["s.status='EXTRACTED'"]
        values: list[object] = []
        for column, wanted in (
            ("e.working_group", request.working_groups),
            ("e.meeting_number", request.meetings),
            ("e.tdoc_id", request.tdoc_ids),
            ("e.kind", request.evidence_kinds),
            ("e.scope", request.scopes),
            ("e.document_role", request.document_roles),
        ):
            if wanted:
                clauses.append(column + " IN (" + ",".join("?" for _ in wanted) + ")")
                values.extend(item.value if hasattr(item, "value") else item for item in wanted)
        rows = self.connection.execute(
            "SELECT e.evidence_id,e.tdoc_id,e.working_group,e.meeting_number "
            "FROM semantic_evidence e JOIN semantic_evidence_state s "
            "USING(tdoc_id,working_group,meeting_number) WHERE " + " AND ".join(clauses)
            + " ORDER BY e.working_group,e.meeting_number,e.tdoc_id,e.sequence_number,e.evidence_id",
            values,
        ).fetchall()
        validated: dict[tuple[str, str, str], dict[str, SemanticEvidence] | None] = {}
        result = []
        for evidence_id, tdoc_id, group, meeting in rows:
            key = (tdoc_id, group, meeting)
            if key not in validated:
                validated[key] = self._validated_document_evidence(key)
            document = validated[key]
            if document is None or evidence_id not in document:
                continue
            item = document[evidence_id]
            if request.organizations and not all(
                any(actual.casefold() == wanted.casefold() for actual in item.source_organizations)
                for wanted in request.organizations
            ):
                continue
            result.append(item)
            if len(result) >= request.limit:
                break
        return result

    def get_evidence(self, evidence_id: str) -> SemanticEvidence:
        row = self.connection.execute(
            "SELECT tdoc_id,working_group,meeting_number FROM semantic_evidence WHERE evidence_id=?",
            [evidence_id],
        ).fetchone()
        if row is None:
            raise ValueError("semantic evidence is missing")
        document = self._validated_document_evidence(tuple(row))
        if document is None or evidence_id not in document:
            raise ValueError("semantic evidence is stale")
        return document[evidence_id]

    def get_evidence_sources(self, evidence_id: str) -> tuple[SemanticEvidence, list[dict]]:
        item = self.get_evidence(evidence_id)
        receipt = self.repository.get_document_receipt(
            item.tdoc_id, item.working_group, item.meeting
        )
        blocks = _read_blocks(self.data_root / receipt.normalized_path)
        by_ref = {(block["member_filename"], block["block_id"]): block for block in blocks}
        return item, [
            by_ref[(span.evidence_ref.member, span.evidence_ref.block_id)]
            for span in sorted(item.evidence_refs, key=lambda value: value.sequence)
        ]

    def inspect_extraction(self) -> list[dict]:
        names = [
            "tdoc_id", "working_group", "meeting", "status", "document_role",
            "document_role_basis", "metadata_identity", "normalization_identity", "normalized_checksum",
            "evidence_schema_version", "ruleset_version", "evidence_path",
            "evidence_checksum", "evidence_count", "blocks_scanned",
            "explicit_labels_detected", "candidates_rejected", "ambiguous_cues_ignored",
            "extracted_at", "error",
        ]
        rows = self.connection.execute(
            "SELECT tdoc_id,working_group,meeting_number,status,document_role,document_role_basis_json,metadata_identity_json,"
            "normalization_identity_json,normalized_checksum,evidence_schema_version,ruleset_version,"
            "evidence_path,evidence_checksum,evidence_count,blocks_scanned,explicit_labels_detected,"
            "candidates_rejected,ambiguous_cues_ignored,extracted_at,error "
            "FROM semantic_evidence_state ORDER BY working_group,meeting_number,tdoc_id"
        ).fetchall()
        return [dict(zip(names, row, strict=True)) for row in rows]

    def _extract_blocks(self, receipt, metadata, classification, blocks):
        evidence: list[SemanticEvidence] = []
        diagnostics = {"labels": 0, "rejected": 0, "ambiguous": 0}
        consumed: set[int] = set()
        active_heading: tuple[EvidenceKind, str] | None = None
        active_member: str | None = None
        extracted_at = datetime.now(timezone.utc)
        for index, block in enumerate(blocks):
            if block["member_filename"] != active_member:
                active_heading = None
                active_member = block["member_filename"]
            text = _block_text(block)
            if block["type"] == "heading":
                kind = heading_kind(text)
                active_heading = (kind, text) if kind and kind_allowed(kind, classification.role) else None
                continue
            if index in consumed or not text.strip():
                continue
            if block["type"] == "table" and block.get("rows"):
                table_items, table_diagnostics = self._extract_table(
                    receipt, metadata, classification, block, extracted_at
                )
                evidence.extend(table_items)
                diagnostics["labels"] += table_diagnostics["labels"]
                diagnostics["rejected"] += table_diagnostics["rejected"]
                continue
            matched = _match_label(text)
            if matched:
                rule, match = matched
                diagnostics["labels"] += 1
                if not rule_allows(rule, classification.role):
                    diagnostics["rejected"] += 1
                    continue
                source_blocks = [block]
                if not match.group("body").strip() and index + 1 < len(blocks):
                    following = blocks[index + 1]
                    if following["member_filename"] == block["member_filename"] and following["type"] != "heading" and _block_text(following).strip():
                        source_blocks.append(following)
                        consumed.add(index + 1)
                evidence.append(self._make_evidence(
                    receipt, metadata, classification, rule.kind, rule.basis,
                    rule.rule_id, match.group("label"), match.group("ordinal"),
                    match.group(0)[:len(match.group("label"))], source_blocks,
                    extracted_at,
                ))
                continue
            inline = _match_inline(text)
            if inline:
                rule, match = inline
                if not rule_allows(rule, classification.role):
                    diagnostics["rejected"] += 1
                    continue
                evidence.append(self._make_evidence(
                    receipt, metadata, classification, rule.kind, rule.basis,
                    rule.rule_id, None, None, match.group(0), [block], extracted_at,
                ))
                continue
            if active_heading:
                kind, cue = active_heading
                evidence.append(self._make_evidence(
                    receipt, metadata, classification, kind, DetectionBasis.HEADING_CONTEXT,
                    f"{kind.value}-heading-context", None, None, cue, [block], extracted_at,
                ))
            elif _SEMANTIC_WORD.search(text):
                diagnostics["ambiguous"] += 1
        return evidence, diagnostics

    def _extract_table(self, receipt, metadata, classification, block, extracted_at):
        result = []
        diagnostics = {"labels": 0, "rejected": 0}
        for row_index, row in enumerate(block["rows"]):
            for cell_index, value in enumerate(row):
                text = "" if value is None else str(value)
                matched = _match_label(text)
                if not matched:
                    continue
                rule, match = matched
                diagnostics["labels"] += 1
                if not rule_allows(rule, classification.role):
                    diagnostics["rejected"] += 1
                    break
                row_text = "\t".join("" if cell is None else str(cell) for cell in row)
                span = EvidenceSpan(
                    evidence_ref=_evidence_ref(receipt, block), sequence=0,
                    row_index=row_index, cell_index=cell_index,
                )
                result.append(self._build_evidence(
                    receipt, metadata, classification, rule.kind, DetectionBasis.TABLE_LABEL,
                    rule.rule_id, match.group("label"), match.group("ordinal"),
                    text, [span], row_text, extracted_at,
                ))
                break
        return result, diagnostics

    def _make_evidence(self, receipt, metadata, classification, kind, basis, rule_id,
                       label, ordinal, cue, blocks, extracted_at):
        spans = []
        texts = []
        for sequence, block in enumerate(blocks):
            text = _block_text(block)
            texts.append(text)
            spans.append(EvidenceSpan(
                evidence_ref=_evidence_ref(receipt, block), sequence=sequence,
                char_start=0, char_end=len(text),
            ))
        return self._build_evidence(
            receipt, metadata, classification, kind, basis, rule_id,
            label, ordinal, cue, spans, "\n".join(texts), extracted_at,
        )

    def _build_evidence(self, receipt, metadata, classification, kind, basis, rule_id,
                        label, ordinal, cue, spans, statement, extracted_at):
        scope = (
            EvidenceScope.MEETING if classification.role is DocumentRole.MEETING_REPORT
            else EvidenceScope.CONTRIBUTION
        )
        organizations = list(metadata.organizations) if metadata and scope is EvidenceScope.CONTRIBUTION else []
        identity = receipt.normalization_identity.model_dump(mode="json")
        identity_input = {
            "schema": EVIDENCE_SCHEMA_VERSION,
            "ruleset": EXTRACTION_RULESET_VERSION,
            "tdoc_id": receipt.tdoc_id,
            "working_group": receipt.working_group.value,
            "meeting": receipt.meeting,
            "kind": kind.value,
            "scope": scope.value,
            "spans": [span.model_dump(mode="json") for span in spans],
            "label": label,
            "ordinal": int(ordinal) if ordinal else None,
            "rule_id": rule_id,
            "rule_version": RULE_VERSION,
        }
        evidence_id = "ev-" + hashlib.sha256(
            json.dumps(identity_input, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]
        return SemanticEvidence(
            evidence_id=evidence_id, kind=kind, scope=scope,
            working_group=receipt.working_group, meeting=receipt.meeting,
            tdoc_id=receipt.tdoc_id, document_role=classification.role,
            document_role_basis=classification.basis,
            source_organizations=organizations, evidence_refs=spans,
            statement_text=statement, label=label,
            ordinal=int(ordinal) if ordinal else None,
            detection_basis=basis, matched_cue=cue, rule_id=rule_id,
            rule_version=RULE_VERSION, extracted_at=extracted_at,
            normalization_identity=identity,
            evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
        )

    def _validated_document_evidence(self, key):
        row = self.connection.execute(
            "SELECT d.receipt_json,s.metadata_identity_json,s.normalization_identity_json,s.normalized_checksum,"
            "s.evidence_schema_version,s.ruleset_version,s.evidence_path,s.evidence_checksum "
            "FROM tdoc_documents d JOIN semantic_evidence_state s "
            "USING(tdoc_id,working_group,meeting_number) "
            "WHERE d.tdoc_id=? AND d.working_group=? AND d.meeting_number=? AND s.status='EXTRACTED'",
            key,
        ).fetchone()
        if row is None:
            return None
        receipt = DocumentReceipt.model_validate_json(row[0])
        metadata = self.repository.get_tdoc(receipt.working_group, receipt.meeting, receipt.tdoc_id)
        expected = (
            _metadata_identity(metadata), _identity_json(receipt), receipt.normalized_checksum,
            EVIDENCE_SCHEMA_VERSION, EXTRACTION_RULESET_VERSION,
        )
        if tuple(row[1:6]) != expected or receipt.normalized_path is None:
            self._mark_stale(key)
            return None
        normalized_path = self.data_root / receipt.normalized_path
        evidence_path = self.data_root / row[6]
        if (not normalized_path.is_file() or _sha(normalized_path) != receipt.normalized_checksum
                or not evidence_path.is_file() or _sha(evidence_path) != row[7]):
            self._mark_stale(key)
            return None
        try:
            blocks = _read_blocks(normalized_path)
            by_ref = {(block["member_filename"], block["block_id"]): block for block in blocks}
            items = [SemanticEvidence.model_validate_json(line) for line in _read_gzip_lines(evidence_path)]
            for item in items:
                if (item.normalization_identity != receipt.normalization_identity.model_dump(mode="json")
                        or item.evidence_schema_version != EVIDENCE_SCHEMA_VERSION
                        or not kind_allowed(item.kind, item.document_role)):
                    raise ValueError("semantic evidence policy or identity mismatch")
                for span in item.evidence_refs:
                    block = by_ref.get((span.evidence_ref.member, span.evidence_ref.block_id))
                    if block is None or not _ref_matches_block(span.evidence_ref, block):
                        raise ValueError("semantic evidence source block is missing")
                    if span.char_end is not None and span.char_end > len(_block_text(block)):
                        raise ValueError("semantic evidence character span is invalid")
                    if span.row_index is not None:
                        rows = block.get("rows") or []
                        if span.row_index >= len(rows) or span.cell_index is None or span.cell_index >= len(rows[span.row_index]):
                            raise ValueError("semantic evidence table span is invalid")
        except Exception:
            self._mark_stale(key)
            return None
        return {item.evidence_id: item for item in items}

    def _delete_items(self, key):
        self.connection.execute(
            "DELETE FROM semantic_evidence WHERE tdoc_id=? AND working_group=? AND meeting_number=?",
            key,
        )

    def _mark_stale(self, key):
        self._delete_items(key)
        self.connection.execute(
            "UPDATE semantic_evidence_state SET status='STALE',evidence_count=0 "
            "WHERE tdoc_id=? AND working_group=? AND meeting_number=?",
            key,
        )

    def _clear_and_state(self, receipt, classification, status, error=None):
        key = [receipt.tdoc_id, receipt.working_group.value, receipt.meeting]
        self._delete_items(key)
        self._write_state(
            receipt, classification, status, None, None, 0, 0,
            {"labels": 0, "rejected": 0, "ambiguous": 0}, error=error,
        )
        return EvidenceExtractionOutcome(
            tdoc_id=receipt.tdoc_id, working_group=receipt.working_group,
            meeting=receipt.meeting, status=status,
            document_role=classification.role,
            document_role_basis=classification.basis,
        )

    def _write_state(self, receipt, classification, status, evidence_path, evidence_checksum,
                     count, blocks, diagnostics, identity=None, error=None):
        self.connection.execute(
            "INSERT OR REPLACE INTO semantic_evidence_state VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                receipt.tdoc_id, receipt.working_group.value, receipt.meeting, status,
                classification.role.value, json.dumps(classification.basis),
                _metadata_identity(self.repository.get_tdoc(
                    receipt.working_group, receipt.meeting, receipt.tdoc_id
                )),
                identity if identity is not None else _identity_json(receipt),
                receipt.normalized_checksum, EVIDENCE_SCHEMA_VERSION,
                EXTRACTION_RULESET_VERSION, str(evidence_path) if evidence_path else None,
                evidence_checksum, count, blocks, diagnostics["labels"],
                diagnostics["rejected"], diagnostics["ambiguous"],
                datetime.now(timezone.utc), error,
            ],
        )


def _match_label(text: str):
    for rule in LABEL_RULES:
        match = rule.pattern.match(text)
        if match:
            return rule, match
    return None


def _match_inline(text: str):
    for rule in INLINE_RULES:
        match = rule.pattern.search(text)
        if match:
            return rule, match
    return None


def _identity_json(receipt: DocumentReceipt) -> str | None:
    return receipt.normalization_identity.model_dump_json() if receipt.normalization_identity else None


def _metadata_identity(metadata: TDocMetadata | None) -> str:
    value = {
        "title": metadata.title if metadata else None,
        "organizations": metadata.organizations if metadata else [],
        "document_type": metadata.document_type if metadata else None,
        "document_category": metadata.document_category if metadata else None,
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _read_gzip_lines(path: Path) -> list[str]:
    return [line for line in gzip.decompress(path.read_bytes()).decode("utf-8").splitlines() if line]


def _read_blocks(path: Path) -> list[dict]:
    return [json.loads(line) for line in _read_gzip_lines(path)]


def _block_text(block: dict) -> str:
    if block.get("rows"):
        return "\n".join(
            "\t".join("" if cell is None else str(cell) for cell in row)
            for row in block["rows"]
        )
    return block.get("text") or ""


def _evidence_ref(receipt: DocumentReceipt, block: dict) -> EvidenceRef:
    return EvidenceRef(
        tdoc_id=receipt.tdoc_id, working_group=receipt.working_group,
        meeting=receipt.meeting, member=block["member_filename"],
        block_id=block["block_id"], block_type=block["type"],
        heading_path=block.get("heading_path", []), page=block.get("page_number"),
        sheet=block.get("sheet_name"),
    )


def _ref_matches_block(ref: EvidenceRef, block: dict) -> bool:
    return (
        ref.member, ref.block_id, ref.block_type, ref.heading_path, ref.page, ref.sheet,
    ) == (
        block["member_filename"], block["block_id"], block["type"],
        block.get("heading_path", []), block.get("page_number"), block.get("sheet_name"),
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence_order(item: SemanticEvidence):
    first = min(item.evidence_refs, key=lambda span: span.sequence)
    return (
        first.evidence_ref.member, first.evidence_ref.block_id,
        first.row_index if first.row_index is not None else -1,
        item.kind.value, item.evidence_id,
    )
