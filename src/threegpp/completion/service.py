from __future__ import annotations

import hashlib
import json
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.documents import DocumentService, FetchPlanner
from threegpp.documents.models import ExtractionStatus, RetentionState
from threegpp.evidence import EvidenceExtractionService, classify_document_role
from threegpp.historical import HistoricalMetadataResolver
from threegpp.historical.models import HistoricalResolutionState
from threegpp.ingest.downloader import DownloadConflictError
from threegpp.links import ExplicitLinkService
from threegpp.models import DocumentRole, TDocAvailability
from threegpp.search import EvidenceSearchService
from threegpp.study_view import TDocStudyService

from .models import (
    COMPLETION_SCHEMA_VERSION, CompletionFailure, CompletionStageResult,
    CompletionStageState,
    TDocEvidenceCompletionRequest, TDocEvidenceCompletionResult,
)


_PARSED = {ExtractionStatus.PARSED, ExtractionStatus.PARTIALLY_PARSED}


class TDocEvidenceCompletionService:
    """Complete the local evidence stages for one explicitly requested TDoc."""

    def __init__(self, repository: MetadataRepository, data_root: Path | str,
                 downloader=None):
        self.repository = repository
        self.data_root = Path(data_root)
        self.documents = DocumentService(repository, self.data_root, downloader)
        self.search = EvidenceSearchService(repository, self.data_root)
        self.evidence = EvidenceExtractionService(repository, self.data_root)
        self.links = ExplicitLinkService(repository, self.data_root)
        self.study = TDocStudyService(repository, self.data_root)
        self.resolver = HistoricalMetadataResolver(repository)

    def complete(self, request: TDocEvidenceCompletionRequest) -> TDocEvidenceCompletionResult:
        resolution = self.resolver.resolve(
            request.working_group, request.tdoc_id,
            discussion_meeting=request.discussion_meeting,
            expected_meeting=request.expected_metadata_meeting,
        )
        empty = self._empty_stages()
        if resolution.state is HistoricalResolutionState.AMBIGUOUS:
            return self._finish(request, resolution, empty,
                                CompletionFailure.METADATA_AMBIGUOUS)
        if resolution.selected is None:
            return self._finish(request, resolution, empty,
                                CompletionFailure.METADATA_UNRESOLVED)
        metadata = resolution.selected.metadata
        empty["metadata"] = self._stage(
            CompletionStageState.COMPLETED, "resolved official metadata",
            resolution.selected.candidate_id,
            source_layer=resolution.selected.source_layer,
            meeting=metadata.meeting, availability=metadata.availability.value,
        )
        if classify_document_role(metadata).role is not DocumentRole.CONTRIBUTION:
            return self._finish(request, resolution, empty,
                                CompletionFailure.NOT_A_CONTRIBUTION)

        receipt = self.repository.get_document_receipt(
            request.tdoc_id, request.working_group, metadata.meeting)
        if receipt is not None and Path(receipt.raw.local_path).is_file():
            actual = _sha(Path(receipt.raw.local_path))
            if actual != receipt.raw.sha256:
                empty["body"] = self._stage(
                    CompletionStageState.FAILED, "local raw checksum does not match receipt",
                    actual, expected_sha256=receipt.raw.sha256)
                return self._finish(request, resolution, empty,
                                    CompletionFailure.RAW_CHECKSUM_INVALID)

        plan = FetchPlanner(self.repository).explicit_records(
            [metadata], reason="explicit single-TDoc evidence completion")
        item = plan.items[0].model_copy(update={"retention": request.retention})
        raw_was_valid = bool(receipt and Path(receipt.raw.local_path).is_file())
        if receipt is not None and raw_was_valid:
            item = item.model_copy(update={
                "source_url": receipt.raw.source_url,
                "availability": TDocAvailability.DOWNLOADABLE,
            })
        plan = plan.model_copy(update={"items": [item]})
        preflight = self.documents.preflight(plan)
        raw_available_before = raw_was_valid or preflight["already_cached"] > 0
        if not raw_was_valid and metadata.availability is not TDocAvailability.DOWNLOADABLE:
            empty["body"] = self._stage(
                CompletionStageState.BLOCKED,
                "official metadata does not provide a downloadable body",
                availability=metadata.availability.value)
            return self._finish(request, resolution, empty,
                                CompletionFailure.BODY_NOT_DOWNLOADABLE)
        if request.offline and not raw_available_before:
            empty["body"] = self._stage(
                CompletionStageState.BLOCKED,
                "offline mode prevents acquisition of the missing body")
            return self._finish(request, resolution, empty,
                                CompletionFailure.OFFLINE_BODY_MISSING)

        normalization_was_valid = bool(receipt and _normalized_valid(self.data_root, receipt))
        try:
            outcome = self.documents.execute(plan)[0]
        except DownloadConflictError as exc:
            empty["body"] = self._stage(CompletionStageState.FAILED, str(exc)[:500])
            return self._finish(request, resolution, empty,
                                CompletionFailure.RAW_CHECKSUM_INVALID,
                                receipt=receipt)
        if outcome.receipt is None or outcome.status not in _PARSED:
            raw_now = self.documents.preflight(plan)["already_cached"] > 0
            failure = (CompletionFailure.NORMALIZATION_FAILED if raw_now
                       else CompletionFailure.DOWNLOAD_FAILED)
            empty["body"] = self._stage(
                CompletionStageState.REUSED if raw_available_before else
                (CompletionStageState.COMPLETED if raw_now else CompletionStageState.FAILED),
                "reused local raw body" if raw_available_before else
                ("acquired raw body" if raw_now else "body acquisition failed"))
            empty["normalization"] = self._stage(
                CompletionStageState.FAILED, outcome.message)
            return self._finish(request, resolution, empty, failure)

        receipt = outcome.receipt
        body_state = (CompletionStageState.REUSED if raw_available_before
                      else CompletionStageState.COMPLETED)
        empty["body"] = self._stage(
            body_state, "reused verified local raw body" if raw_available_before
            else "acquired one body",
            receipt.raw.sha256, byte_size=receipt.raw.byte_size,
            source_url=str(receipt.raw.source_url))
        empty["normalization"] = self._stage(
            CompletionStageState.REUSED if normalization_was_valid else CompletionStageState.COMPLETED,
            "reused current normalization" if normalization_was_valid else
            "completed normalization from verified raw",
            receipt.normalization_identity.model_dump_json()
            if receipt.normalization_identity else None,
            checksum=receipt.normalized_checksum, status=receipt.extraction_status.value)

        indexed = self.search.index_document(receipt)
        if indexed.status != "INDEXED":
            empty["index"] = self._stage(CompletionStageState.FAILED, indexed.status)
            return self._finish(request, resolution, empty, CompletionFailure.INDEX_FAILED,
                                receipt=receipt)
        empty["index"] = self._stage(
            CompletionStageState.REUSED if indexed.reused else CompletionStageState.COMPLETED,
            "reused current lexical index" if indexed.reused else "completed lexical indexing",
            receipt.normalized_checksum, indexed_blocks=indexed.indexed_blocks,
            postings=indexed.postings)

        extracted = self.evidence.extract_document(receipt)
        if (extracted.status != "EXTRACTED"
                or extracted.document_role is not DocumentRole.CONTRIBUTION):
            empty["semantic_extraction"] = self._stage(
                CompletionStageState.FAILED, extracted.status,
                document_role=extracted.document_role.value)
            return self._finish(request, resolution, empty,
                                CompletionFailure.SEMANTIC_EXTRACTION_FAILED,
                                receipt=receipt)
        empty["semantic_extraction"] = self._stage(
            CompletionStageState.REUSED if extracted.reused else CompletionStageState.COMPLETED,
            "reused current contribution SemanticEvidence" if extracted.reused else
            "completed contribution SemanticEvidence extraction",
            receipt.normalized_checksum, evidence_count=extracted.evidence_extracted,
            document_role=extracted.document_role.value)

        try:
            graph = self.links.build_for_tdoc(request.working_group, request.tdoc_id)
            path = self.links.persist(graph)
        except Exception as exc:
            empty["link_status"] = self._stage(
                CompletionStageState.FAILED, str(exc)[:500])
            return self._finish(request, resolution, empty,
                                CompletionFailure.LINK_REFRESH_FAILED,
                                receipt=receipt, content_inspected=True,
                                evidence_count=extracted.evidence_extracted)
        empty["link_status"] = self._stage(
            CompletionStageState.COMPLETED, "refreshed requested-TDoc link/status scope",
            graph.graph_id, path=str(path))
        view = self.study.build(
            request.working_group, request.tdoc_id,
            metadata_meeting=metadata.meeting,
            discussion_meeting=request.discussion_meeting)
        return self._finish(
            request, resolution, empty, receipt=receipt,
            content_inspected=view.contribution.content_inspected,
            study_view_id=view.view_id, evidence_count=extracted.evidence_extracted)

    @staticmethod
    def _empty_stages():
        return {name: CompletionStageResult(
            state=CompletionStageState.NOT_RUN, detail="not run") for name in (
                "metadata", "body", "normalization", "index",
                "semantic_extraction", "link_status")}

    @staticmethod
    def _stage(state, detail, identity=None, **values):
        return CompletionStageResult(
            state=state, detail=detail, identity=identity, values=values)

    def _finish(self, request, resolution, stages, failure=None, *, receipt=None,
                content_inspected=False, study_view_id=None, evidence_count=None):
        retention = receipt.raw.retention if receipt else None
        provenance = {
            "metadata_candidate_id": (resolution.selected.candidate_id
                                      if resolution.selected else None),
            "metadata_source_layer": (resolution.selected.source_layer
                                      if resolution.selected else None),
            "raw_sha256": receipt.raw.sha256 if receipt else None,
            "normalization_identity": (receipt.normalization_identity.model_dump(mode="json")
                                       if receipt and receipt.normalization_identity else None),
            "normalized_checksum": receipt.normalized_checksum if receipt else None,
        }
        logical = {
            "schema_version": COMPLETION_SCHEMA_VERSION,
            "request": request.model_dump(mode="json"),
            "metadata_resolution": resolution.model_dump(mode="json"),
            "retention": retention.value if retention else None,
            "content_inspected": content_inspected,
            "study_view_id": study_view_id, "evidence_count": evidence_count,
            "failure": failure.value if failure else None, "provenance": provenance,
        }
        result_id = "completion-" + hashlib.sha256(json.dumps(
            logical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")).hexdigest()
        return TDocEvidenceCompletionResult(
            result_id=result_id, request=request, metadata_resolution=resolution,
            retention=retention, content_inspected=content_inspected,
            study_view_id=study_view_id, evidence_count=evidence_count,
            failure=failure, provenance=provenance, **stages)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_valid(root: Path, receipt) -> bool:
    return all(path is not None and checksum is not None
               and (root / path).is_file() and _sha(root / path) == checksum
               for path, checksum in (
                   (receipt.normalized_path, receipt.normalized_checksum),
                   (receipt.text_path, receipt.text_checksum)))
