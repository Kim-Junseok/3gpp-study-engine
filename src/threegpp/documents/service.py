from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.ingest.downloader import HTTPDownloader, safe_filename
from threegpp.models import CandidateInventory, MatchLevel, TDocAvailability, WorkingGroup

from .archive import inspect_package
from .models import (
    NORMALIZED_DOCUMENT_SCHEMA_VERSION, DocumentReceipt, ExtractionStatus, FetchOutcome,
    FetchPlanItem, NormalizationIdentity, NormalizedMember, NormalizedTDoc, RawArtifact,
    RetentionState, TDocFetchPlan,
)
from .parsers import media_type, parser_for


class FetchPlanner:
    def __init__(self, repository: MetadataRepository, *, batch_limit: int = 50):
        self.repository, self.batch_limit = repository, batch_limit

    def from_inventory(self, inventory: CandidateInventory, *, minimum_match: MatchLevel = MatchLevel.HIGH, organizations: list[str] | None = None) -> TDocFetchPlan:
        rank = {MatchLevel.LOW: 1, MatchLevel.MEDIUM: 2, MatchLevel.HIGH: 3}
        items = []
        for candidate in inventory.candidate_tdocs:
            if candidate.match_level is None or rank[candidate.match_level] < rank[minimum_match]: continue
            if candidate.availability is not TDocAvailability.DOWNLOADABLE: continue
            if organizations and not any(org.casefold() in {x.casefold() for x in candidate.tdoc.organizations} for org in organizations): continue
            reasons = [f"metadata candidate {candidate.match_level.value.upper()}"]
            items.append(FetchPlanItem(tdoc_id=candidate.tdoc.tdoc_id, working_group=candidate.tdoc.working_group, meeting=candidate.tdoc.meeting, source_url=candidate.tdoc.source_url, availability=candidate.availability, selection_reasons=reasons))
        if len(items) > self.batch_limit:
            raise ValueError(f"selection contains {len(items)} TDocs; automatic batch limit is {self.batch_limit}; use explicit TDoc IDs")
        return TDocFetchPlan(study=inventory.study_name, items=items, automatic_batch_limit=self.batch_limit)

    def explicit(self, identities: list[tuple[WorkingGroup | str, str, str]], *, reason: str | None = None) -> TDocFetchPlan:
        items = []
        for group, meeting, tdoc_id in identities:
            record = self.repository.get_tdoc(group, meeting, tdoc_id)
            if record is None: raise ValueError(f"TDoc metadata not found: {group}#{meeting}/{tdoc_id}")
            items.append(FetchPlanItem(tdoc_id=record.tdoc_id, working_group=record.working_group, meeting=record.meeting, source_url=record.source_url, availability=record.availability, selection_reasons=[reason] if reason else []))
        return TDocFetchPlan(items=items, automatic_batch_limit=self.batch_limit)


class DocumentService:
    def __init__(
        self,
        repository: MetadataRepository,
        root: Path,
        downloader: HTTPDownloader | None = None,
        *,
        normalized_schema_version: str = NORMALIZED_DOCUMENT_SCHEMA_VERSION,
    ):
        self.repository, self.root = repository, Path(root)
        self.downloader = downloader or HTTPDownloader()
        self.normalized_schema_version = normalized_schema_version

    def preflight(self, plan: TDocFetchPlan) -> dict[str, int]:
        cached = sum(self._raw_path(item).exists() for item in plan.items if item.source_url)
        return {"selected": len(plan.items), "already_cached": cached, "to_download": sum(item.availability is TDocAvailability.DOWNLOADABLE and not self._raw_path(item).exists() for item in plan.items), "listed_only_skipped": sum(item.availability is TDocAvailability.LISTED_ONLY for item in plan.items), "unknown": sum(item.availability is TDocAvailability.UNKNOWN for item in plan.items)}

    def execute(self, plan: TDocFetchPlan) -> list[FetchOutcome]:
        outcomes = []
        for item in plan.items:
            if item.availability is TDocAvailability.LISTED_ONLY:
                outcomes.append(FetchOutcome(item=item, status=ExtractionStatus.NOT_FETCHED, message="body unavailable from discovered official source")); continue
            if item.availability is not TDocAvailability.DOWNLOADABLE or item.source_url is None:
                outcomes.append(FetchOutcome(item=item, status=ExtractionStatus.NOT_FETCHED, message="body availability is unknown; explicit handling required")); continue
            try: outcomes.append(self._fetch_and_normalize(item))
            except Exception as exc:
                from threegpp.ingest.downloader import DownloadConflictError
                if isinstance(exc, DownloadConflictError): raise
                outcomes.append(FetchOutcome(item=item, status=ExtractionStatus.FAILED, message=str(exc)[:500]))
        return outcomes

    def _fetch_and_normalize(self, item: FetchPlanItem) -> FetchOutcome:
        raw_path = self._raw_path(item)
        if raw_path.exists():
            digest = _sha(raw_path); downloaded = False
        else:
            result = self.downloader.download(str(item.source_url), raw_path); digest, downloaded = result.sha256, result.downloaded
        raw = RawArtifact(source_url=item.source_url, local_path=raw_path, filename=raw_path.name, retrieved_at=datetime.fromtimestamp(raw_path.stat().st_mtime, timezone.utc), media_type=media_type(raw_path.name), byte_size=raw_path.stat().st_size, sha256=digest, retention=item.retention)
        existing = self._read_receipt(item)
        if existing and (
            str(existing.raw.source_url) != str(item.source_url)
            or existing.raw.sha256 != digest
        ):
            from threegpp.ingest.downloader import DownloadConflictError
            raise DownloadConflictError(
                "cached raw artifact provenance conflicts with fetch plan or receipt"
            )
        inspected = inspect_package(raw_path.read_bytes(), raw_path.name)
        identity = NormalizationIdentity(
            raw_sha256=digest,
            parser_members={
                member.metadata.filename: (
                    f"{parser.name}@{parser.version}" if (parser := parser_for(member.metadata.filename)) else "unsupported"
                )
                for member in inspected
            },
            normalized_schema_version=self.normalized_schema_version,
        )
        if existing and existing.normalization_identity == identity and self._normalized_outputs_valid(existing):
            effective_retention = (
                RetentionState.PINNED
                if RetentionState.PINNED in {existing.raw.retention, item.retention}
                else RetentionState.CACHE
            )
            if existing.raw.retention is not effective_retention:
                existing = existing.model_copy(
                    update={"raw": existing.raw.model_copy(update={"retention": effective_retention})}
                )
                self._write_receipt(existing)
            self.repository.upsert_document_receipt(existing)
            return FetchOutcome(item=item, status=existing.extraction_status, message="reused cached raw and normalized artifacts", receipt=existing)
        normalized_members, warnings, statuses, counter = [], [], [], 0
        for inspected_member in inspected:
            parser = parser_for(inspected_member.metadata.filename)
            if parser is None:
                status, blocks, member_warnings = ExtractionStatus.UNSUPPORTED_FORMAT, [], ["unsupported member format"]
                parser_name = parser_version = None
            else:
                blocks, status, member_warnings = parser.parse(inspected_member.data, inspected_member.metadata.filename)
                parser_name, parser_version = parser.name, parser.version
                renumbered = []
                for block in blocks:
                    counter += 1; renumbered.append(block.model_copy(update={"block_id": f"b{counter:06d}", "order": counter}))
                blocks = renumbered
            statuses.append(status); warnings.extend(f"{inspected_member.metadata.filename}: {w}" for w in member_warnings)
            normalized_members.append(NormalizedMember(member=inspected_member.metadata.model_copy(update={"extraction_status": status, "warnings": member_warnings}), parser=parser_name, parser_version=parser_version, extraction_status=status, warnings=member_warnings, blocks=blocks))
        overall = _overall(statuses)
        primary = next((m.metadata.filename for m in inspected if m.metadata.role == "probable_primary"), inspected[0].metadata.filename if len(inspected) == 1 else None)
        text = _flatten(normalized_members)
        normalized = NormalizedTDoc(schema_version=self.normalized_schema_version, tdoc_id=item.tdoc_id, working_group=item.working_group, meeting=item.meeting, raw=raw, members=normalized_members, primary_member=primary, extraction_status=overall, warnings=warnings, normalized_text=text, normalized_at=raw.retrieved_at)
        receipt = self._store(normalized, identity)
        self.repository.upsert_document_receipt(receipt)
        return FetchOutcome(item=item, status=overall, message="downloaded and normalized" if downloaded else "normalized cached raw artifact", receipt=receipt)

    def retrieve(self, tdoc_id: str, working_group: WorkingGroup | str | None = None, meeting: str | None = None) -> tuple[object, DocumentReceipt, list, str]:
        receipt = self.repository.get_document_receipt(tdoc_id, working_group, meeting)
        if receipt is None: raise ValueError(f"normalized document not found: {tdoc_id}")
        metadata = self.repository.get_tdoc(receipt.working_group, receipt.meeting, receipt.tdoc_id)
        lines = gzip.decompress((self.root / receipt.normalized_path).read_bytes()).decode().splitlines()
        blocks = [json.loads(line) for line in lines]
        text = gzip.decompress((self.root / receipt.text_path).read_bytes()).decode()
        return metadata, receipt, blocks, text

    def _raw_path(self, item):
        filename = safe_filename(str(item.source_url), f"{item.tdoc_id}.bin") if item.source_url else f"{item.tdoc_id}.bin"
        return self.root / "raw" / "tdocs" / item.working_group.value.lower() / item.meeting / item.tdoc_id / filename

    def _receipt_path(self, item): return self.root / "manifests" / "documents" / item.working_group.value.lower() / item.meeting / item.tdoc_id / "receipt.json"
    def _read_receipt(self, item):
        path = self._receipt_path(item)
        return DocumentReceipt.model_validate_json(path.read_text()) if path.exists() else None

    def _normalized_outputs_valid(self, receipt: DocumentReceipt) -> bool:
        outputs = (
            (receipt.normalized_path, receipt.normalized_checksum),
            (receipt.text_path, receipt.text_checksum),
        )
        return all(
            relative_path is not None
            and checksum is not None
            and (self.root / relative_path).is_file()
            and _sha(self.root / relative_path) == checksum
            for relative_path, checksum in outputs
        )

    def _store(self, document: NormalizedTDoc, identity: NormalizationIdentity) -> DocumentReceipt:
        base = self.root / "normalized" / "documents" / document.working_group.value.lower() / document.meeting / document.tdoc_id
        blocks = [block for member in document.members for block in member.blocks]
        block_bytes = _gzip("".join(json.dumps(block.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for block in blocks).encode())
        text_bytes = _gzip(document.normalized_text.encode())
        base.mkdir(parents=True, exist_ok=True)
        _atomic(base / "document.jsonl.gz", block_bytes); _atomic(base / "text.txt.gz", text_bytes)
        receipt = DocumentReceipt(tdoc_id=document.tdoc_id, working_group=document.working_group, meeting=document.meeting, raw=document.raw, members=[m.member for m in document.members], primary_member=document.primary_member, extraction_status=document.extraction_status, parser_versions={m.parser: m.parser_version for m in document.members if m.parser and m.parser_version}, normalization_identity=identity, normalized_path=(base / "document.jsonl.gz").relative_to(self.root), text_path=(base / "text.txt.gz").relative_to(self.root), normalized_checksum=hashlib.sha256(block_bytes).hexdigest(), text_checksum=hashlib.sha256(text_bytes).hexdigest(), block_count=len(blocks), text_length=len(document.normalized_text), warnings=document.warnings)
        self._write_receipt(receipt)
        return receipt

    def _write_receipt(self, receipt: DocumentReceipt) -> None:
        receipt_path = self._receipt_path(receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic(receipt_path, (json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode())


def _gzip(data: bytes) -> bytes:
    import io
    target = io.BytesIO()
    with gzip.GzipFile(fileobj=target, mode="wb", mtime=0, filename="") as stream: stream.write(data)
    return target.getvalue()
def _atomic(path: Path, data: bytes):
    temp = path.with_name(f".{path.name}.part"); temp.write_bytes(data); temp.replace(path)
def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def _flatten(members):
    parts=[]
    for member in members:
        parts.append(f"=== FILE: {member.member.filename} ===")
        for block in member.blocks:
            if block.text: parts.append(block.text)
            if block.rows is not None: parts.extend("\t".join("" if cell is None else str(cell) for cell in row) for row in block.rows)
    return "\n\n".join(parts) + ("\n" if parts else "")
def _overall(statuses):
    if not statuses: return ExtractionStatus.FAILED
    parsed = sum(s is ExtractionStatus.PARSED for s in statuses)
    if parsed == len(statuses): return ExtractionStatus.PARSED
    if parsed: return ExtractionStatus.PARTIALLY_PARSED
    if any(s is ExtractionStatus.TEXT_UNAVAILABLE for s in statuses): return ExtractionStatus.TEXT_UNAVAILABLE
    if all(s is ExtractionStatus.UNSUPPORTED_FORMAT for s in statuses): return ExtractionStatus.UNSUPPORTED_FORMAT
    return ExtractionStatus.FAILED
