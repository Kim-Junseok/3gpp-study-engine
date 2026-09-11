from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.evidence import EvidenceExtractionService
from threegpp.links import (
    EvidenceLinkGraph, EvidenceNodeKind, ExplicitLinkKind, ExplicitLinkService,
    LinkCoverageState,
)
from threegpp.models import EvidenceExtractionRequest, EvidenceScope, TDocQuery, WorkingGroup

from .models import (
    ContributionEvidenceView, ContributionView, DiscussionReferenceView, DiscussionView,
    MeetingOutcomeEvidenceView, MeetingOutcomeView, TDOC_STUDY_VIEW_SCHEMA_VERSION,
    TDocStudyView,
)


DISCUSSION_LIMITATION = (
    "No qualifying reference was found in the selected Chair Note material available to "
    "this local view. This does not establish that the TDoc was not discussed."
)
CONTRIBUTION_LIMITATION = (
    "The TDoc metadata is known, but its document content has not yet been acquired and "
    "processed by the local study corpus."
)
OUTCOME_LIMITATION = (
    "No qualifying explicit TDoc reference was found in the currently prepared "
    "meeting-outcome evidence. This is not evidence of rejection or of the absence of "
    "another meeting outcome."
)


class TDocStudyService:
    """Derive a research-facing TDoc view from existing local evidence."""

    def __init__(self, repository: MetadataRepository, data_root: Path | str):
        self.repository = repository
        self.connection = repository.connection
        self.data_root = Path(data_root)
        self.links = ExplicitLinkService(repository, data_root)
        self.evidence = EvidenceExtractionService(repository, data_root)

    def build(self, working_group: WorkingGroup | str, tdoc_id: str) -> TDocStudyView:
        group = WorkingGroup.parse(working_group)
        wanted = tdoc_id.strip().upper()
        metadata_records = self.repository.query_tdocs(TDocQuery(
            working_groups=[group], tdoc_id=wanted))
        if len(metadata_records) > 1:
            raise ValueError("TDoc ID is ambiguous in canonical-current metadata")
        metadata = metadata_records[0] if metadata_records else None
        meeting = metadata.meeting if metadata else None

        targeted = self.links.build_for_tdoc(group, wanted)
        graphs = self._relevant_graphs(group, wanted, targeted)
        contribution_evidence = self.evidence.list_evidence(EvidenceExtractionRequest(
            working_groups=[group], tdoc_ids=[wanted], scopes=[EvidenceScope.CONTRIBUTION],
            limit=5000))
        discussion = self._discussion(graphs, wanted, meeting)
        contribution = ContributionView(
            content_inspected=self._content_inspected(group, wanted, meeting),
            evidence=[ContributionEvidenceView(
                kind=item.kind, statement_text=item.statement_text,
                evidence_id=item.evidence_id,
                evidence_refs=[span.model_dump(mode="json") for span in item.evidence_refs],
            ) for item in contribution_evidence],
            limitation=None,
        )
        if not contribution.content_inspected:
            contribution.limitation = CONTRIBUTION_LIMITATION
        outcome = self._meeting_outcome(graphs, wanted, meeting)
        statuses = self._statuses(graphs, wanted, meeting)
        logical = {
            "schema_version": TDOC_STUDY_VIEW_SCHEMA_VERSION,
            "tdoc_id": wanted,
            "working_group": group.value,
            "metadata_meeting": meeting,
            "title": metadata.title if metadata else None,
            "organizations": metadata.organizations if metadata else [],
            "official_url": str(metadata.source_url) if metadata and metadata.source_url else None,
            "discussion": discussion.model_dump(mode="json"),
            "contribution": contribution.model_dump(mode="json"),
            "meeting_outcome": outcome.model_dump(mode="json"),
            "backend_statuses": statuses,
        }
        view_id = "tdoc-study-" + hashlib.sha256(json.dumps(
            logical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")).hexdigest()
        return TDocStudyView(**logical, view_id=view_id)

    def _relevant_graphs(self, group, tdoc_id, targeted):
        graphs = {targeted.graph_id: targeted}
        rows = self.connection.execute(
            "SELECT graph_id,graph_path,artifact_checksum FROM explicit_link_graph_state "
            "WHERE working_group=? ORDER BY graph_id", [group.value]).fetchall()
        for graph_id, relative, checksum in rows:
            path = self.data_root / relative
            if not path.is_file():
                continue
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != checksum:
                continue
            graph = EvidenceLinkGraph.model_validate_json(gzip.decompress(payload))
            if graph.graph_id != graph_id or not self._mentions(graph, tdoc_id):
                continue
            graphs[graph.graph_id] = graph
        return [graphs[key] for key in sorted(graphs)]

    @staticmethod
    def _mentions(graph, tdoc_id):
        return any(node.tdoc_id and node.tdoc_id.upper() == tdoc_id for node in graph.nodes)

    def _discussion(self, graphs, tdoc_id, meeting):
        values = {}
        for graph in graphs:
            for link in graph.links:
                if (link.kind is not ExplicitLinkKind.DISCUSSION_REFERENCE
                        or link.resolution_state is not LinkCoverageState.LINKED
                        or not self._target(link, tdoc_id, meeting)):
                    continue
                locator = next((item for item in link.locators
                                if item.locator_type == "ChairNoteRef"), None)
                if locator is None:
                    continue
                ref = locator.reference
                literal = self._chair_context(ref)
                context = (ref.get("heading_path") or [None])[-1] or literal
                item = DiscussionReferenceView(
                    meeting=link.discussion_meeting or link.source_meeting or "unknown",
                    context=context, literal_source_context=literal,
                    chair_note_source=locator.source_artifact,
                    chair_note_ref=ref, graph_id=graph.graph_id, link_id=link.link_id,
                    backend_link_kind=link.kind.value,
                )
                values[(item.meeting, item.link_id)] = item
        references = [values[key] for key in sorted(values)]
        return DiscussionView(referenced_in_selected_chair_note=bool(references),
            references=references, limitation=None if references else DISCUSSION_LIMITATION)

    def _meeting_outcome(self, graphs, tdoc_id, meeting):
        values = {}
        for graph in graphs:
            for link in graph.links:
                if (link.kind is ExplicitLinkKind.SAME_TDOC
                        or link.resolution_state is not LinkCoverageState.LINKED
                        or link.source_node.kind is not EvidenceNodeKind.SEMANTIC_EVIDENCE
                        or link.source_node.evidence_scope is not EvidenceScope.MEETING
                        or not self._target(link, tdoc_id, meeting)):
                    continue
                try:
                    evidence = self.evidence.get_evidence(link.source_node.source_artifact)
                except ValueError:
                    continue
                item = MeetingOutcomeEvidenceView(
                    outcome_type=evidence.kind, disposition=link.disposition,
                    meeting=link.authority_meeting or link.source_meeting,
                    discovery_meeting=link.discovery_meeting,
                    statement_text=evidence.statement_text,
                    literal_reference=link.literal_basis, evidence_id=evidence.evidence_id,
                    evidence_refs=[span.model_dump(mode="json") for span in evidence.evidence_refs],
                    graph_id=graph.graph_id, link_id=link.link_id,
                    backend_link_kind=link.kind.value,
                )
                values[(item.evidence_id, item.link_id)] = item
        outcomes = [values[key] for key in sorted(values)]
        return MeetingOutcomeView(explicit_tdoc_reference_found=bool(outcomes), outcomes=outcomes,
            limitation=None if outcomes else OUTCOME_LIMITATION)

    def _statuses(self, graphs, tdoc_id, meeting):
        values = {}
        for graph in graphs:
            persisted = self.connection.execute(
                "SELECT status_path,artifact_checksum FROM explicit_link_tdoc_status_state "
                "WHERE graph_id=?", [graph.graph_id]).fetchone()
            if persisted is not None:
                path = self.data_root / persisted[0]
                if not path.is_file():
                    continue
                payload = path.read_bytes()
                if hashlib.sha256(payload).hexdigest() != persisted[1]:
                    continue
                candidates = (json.loads(line) for line in gzip.decompress(payload).splitlines())
            else:
                candidates = (item.model_dump(mode="json")
                              for item in self.links.build_tdoc_statuses(graph))
            for status in candidates:
                if (status["tdoc_id"] == tdoc_id
                        and (meeting is None or status["metadata_meeting"] == meeting)):
                    values[(status["graph_id"], status["node_id"])] = status
        return [values[key] for key in sorted(values)]

    def _content_inspected(self, group, tdoc_id, meeting):
        clauses = ["upper(tdoc_id)=upper(?)", "working_group=?", "status='EXTRACTED'",
                   "document_role='contribution'"]
        params = [tdoc_id, group.value]
        if meeting is not None:
            clauses.append("meeting_number=?")
            params.append(meeting)
        return self.connection.execute(
            "SELECT count(*) FROM semantic_evidence_state WHERE " + " AND ".join(clauses),
            params).fetchone()[0] > 0

    @staticmethod
    def _target(link, tdoc_id, meeting):
        return (link.target_node.tdoc_id
                and link.target_node.tdoc_id.upper() == tdoc_id
                and (meeting is None or link.target_node.meeting == meeting))

    def _chair_context(self, ref):
        path = (self.data_root / "normalized" / "chair-notes"
                / ref["working_group"].casefold() / ref["meeting"] / ref["snapshot_id"]
                / ref["normalization_id"] / "blocks.jsonl.gz")
        if not path.is_file():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                block = json.loads(line)
                if (block.get("block_id") != ref["block_id"]
                        or block.get("member_filename") != ref["member"]):
                    continue
                text = block.get("text")
                if text is None and block.get("rows") is not None:
                    row = ref.get("row_index")
                    cell = ref.get("cell_index")
                    if row is not None and cell is not None:
                        text = str(block["rows"][row][cell])
                return _bounded_literal(text, ref.get("char_start"), ref.get("char_end"))
        return None


def _bounded_literal(text: str | None, start: int | None, end: int | None,
                     window: int = 120) -> str | None:
    if not text:
        return None
    if start is None or end is None:
        return text if len(text) <= 2 * window else text[:2 * window].rstrip() + "…"
    left, right = max(0, start - window), min(len(text), end + window)
    value = text[left:right]
    return ("…" if left else "") + value + ("…" if right < len(text) else "")
