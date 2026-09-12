from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from threegpp.chair_notes.models import DiscussionRecord
from threegpp.db import MetadataRepository
from threegpp.documents.models import DocumentReceipt
from threegpp.evidence import EvidenceExtractionService, classify_document_role
from threegpp.historical import HistoricalCoverageRequest, HistoricalCoverageService
from threegpp.historical import rules as historical_rules
from threegpp.models import (
    DocumentRole, EvidenceExtractionRequest, EvidenceKind, EvidenceScope, SemanticEvidence,
    TDocMetadata, TDocQuery, WorkingGroup,
)
from threegpp.topic import classify_agreement_disposition, resolve_authority_meeting

from . import rules
from .models import (
    ContributionSemanticEvidenceState, EvidenceLinkGraph, EvidenceNodeKind,
    EvidenceNodeRef, ExplicitEvidenceLink, ExplicitLinkKind, ExplicitLinkPresenceState,
    LinkCompleteness, LinkCoverage, LinkCoverageState, LinkPreparationItem,
    LinkPreparationPlan, SourceLocator, TDocExplicitLinkStatus, TDocStatusProvenance,
)


_MEETING_LINK_KINDS = {
    EvidenceKind.AGREEMENT, EvidenceKind.DECISION, EvidenceKind.CONCLUSION, EvidenceKind.FFS,
}


class ExplicitLinkService:
    """Build deterministic explicit-reference graphs from already-local evidence."""

    def __init__(self, repository: MetadataRepository, data_root: Path | str):
        self.repository = repository
        self.connection = repository.connection
        self.data_root = Path(data_root)

    def resolve_links(
        self,
        *,
        working_group: WorkingGroup | str,
        semantic_evidence: Sequence[SemanticEvidence] = (),
        discussion_records: Sequence[DiscussionRecord] = (),
        metadata_records: Sequence[TDocMetadata] = (),
        preferred_metadata: dict[str, TDocMetadata] | None = None,
        scope: dict[str, Any] | None = None,
    ) -> EvidenceLinkGraph:
        group = WorkingGroup.parse(working_group)
        metadata = sorted(metadata_records, key=lambda item: (
            item.meeting, item.tdoc_id, rules.identity(item.model_dump(mode="json"))))
        preferred = {key.upper(): value for key, value in (preferred_metadata or {}).items()}
        scope_value = scope or {}
        nodes: dict[str, EvidenceNodeRef] = {}
        links: dict[str, ExplicitEvidenceLink] = {}
        coverage: dict[str, LinkCoverage] = {}

        def add_link(link: ExplicitEvidenceLink) -> None:
            nodes[link.source_node.node_id] = link.source_node
            nodes[link.target_node.node_id] = link.target_node
            for candidate in link.resolution_candidates:
                nodes[candidate.node_id] = candidate
            links[link.link_id] = link

        for item in semantic_evidence:
            if item.working_group is not group:
                continue
            source = self._semantic_node(item)
            nodes[source.node_id] = source
            if item.scope is EvidenceScope.CONTRIBUTION:
                target, state, candidates = self._resolve_tdoc_node(
                    group, item.tdoc_id, metadata, preferred, expected_meeting=item.meeting)
                metadata_missing = state is LinkCoverageState.UNRESOLVED_REFERENCE
                if metadata_missing:
                    # The evidence contract itself establishes its parent document identity.
                    # Missing metadata is a coverage gap, not an ambiguous parent relation.
                    target = self._source_tdoc_node(item)
                    state, candidates = LinkCoverageState.LINKED, []
                add_link(self._link(
                    ExplicitLinkKind.SAME_TDOC, source, target, item.tdoc_id,
                    source.locators, state, candidates, source_meeting=item.meeting,
                    metadata_meeting=target.meeting,
                ))
                self._cover(
                    coverage, item.tdoc_id,
                    LinkCoverageState.SOURCE_MISSING if metadata_missing else state,
                    target.meeting,
                    "contribution SemanticEvidence has a structural parent-TDoc link; "
                    + ("metadata is missing" if metadata_missing else "metadata is resolved"))
            if item.scope is EvidenceScope.MEETING and item.kind not in _MEETING_LINK_KINDS:
                continue
            for match in rules.TDOC_REFERENCE_PATTERN.finditer(item.statement_text):
                tdoc_id = match.group(0).upper()
                target, state, candidates = self._resolve_tdoc_node(
                    self._tdoc_group(tdoc_id), tdoc_id, metadata, preferred)
                relation = ExplicitLinkKind(
                    rules.relation_for_reference(item.statement_text, match.start(), match.end()))
                disposition = classify_agreement_disposition(item)
                locator = self._literal_evidence_locator(source, item, match.start(), match.end())
                discovery_meeting, authority_meeting = self._evidence_meetings(item, metadata)
                add_link(self._link(
                    relation, source, target, match.group(0), [locator],
                    state, candidates, source_meeting=item.meeting,
                    discovery_meeting=discovery_meeting,
                    authority_meeting=authority_meeting,
                    metadata_meeting=target.meeting,
                    disposition=disposition.disposition if disposition else None,
                ))
                self._cover(coverage, tdoc_id, state, target.meeting,
                            "SemanticEvidence contains a literal TDoc reference")
            for match in rules.MEETING_REFERENCE_PATTERN.finditer(item.statement_text):
                raw = match.group("meeting")
                target_group = WorkingGroup.RAN1 if raw.upper().startswith("RAN1") else WorkingGroup.RAN2
                try:
                    meeting, _ = historical_rules.normalize_historical_meeting(raw, target_group)
                except ValueError:
                    continue
                target = self._meeting_node(target_group, meeting, raw)
                locator = self._literal_evidence_locator(source, item, match.start(), match.end())
                add_link(self._link(
                    ExplicitLinkKind.EXPLICIT_MEETING_REFERENCE, source, target, match.group(0),
                    [locator], LinkCoverageState.LINKED, [],
                    source_meeting=item.meeting, discovery_meeting=item.meeting,
                    authority_meeting=self._evidence_meetings(item, metadata)[1],
                    metadata_meeting=meeting,
                ))

        for record in discussion_records:
            ref = record.reference.source_ref
            if ref.working_group is not group:
                continue
            source = self._discussion_node(record)
            target, state, candidates = self._resolve_tdoc_node(
                self._tdoc_group(record.reference.tdoc_id), record.reference.tdoc_id,
                metadata, preferred)
            add_link(self._link(
                ExplicitLinkKind.DISCUSSION_REFERENCE, source, target,
                record.reference.raw_reference, source.locators, state, candidates,
                discussion_meeting=ref.meeting, source_meeting=ref.meeting,
                metadata_meeting=target.meeting,
            ))
            self._cover(coverage, record.reference.tdoc_id, state, target.meeting,
                        "selected Chair Note discussion context contains a literal TDoc reference")

        # Structured metadata relationships and literal title/abstract references are explicit,
        # but relation semantics stronger than reference require literal cue words.
        for item in metadata:
            if item.working_group is not group:
                continue
            source = self._metadata_node(item)
            nodes[source.node_id] = source
            fields = [("title", item.title or ""), ("abstract", item.abstract or "")]
            if item.related_tdoc_ids:
                fields.extend(("related_tdoc_ids", value) for value in item.related_tdoc_ids)
            for field, text in fields:
                for match in rules.TDOC_REFERENCE_PATTERN.finditer(text):
                    target_id = match.group(0).upper()
                    if target_id == item.tdoc_id.upper():
                        continue
                    target_group = self._tdoc_group(target_id)
                    target, state, candidates = self._resolve_tdoc_node(
                        target_group, target_id, metadata, preferred)
                    kind = ExplicitLinkKind(rules.relation_for_reference(text, match.start(), match.end()))
                    locator = self._metadata_locator(item, field, match.start(), match.end())
                    add_link(self._link(
                        kind, source, target, match.group(0), [locator], state, candidates,
                        source_meeting=item.meeting, metadata_meeting=target.meeting,
                    ))
                    self._cover(coverage, target_id, state, target.meeting,
                                f"TDoc metadata {field} contains a literal reference")

        for item in metadata:
            if item.working_group is group and item.tdoc_id.upper() not in coverage:
                self._cover(coverage, item.tdoc_id, LinkCoverageState.NO_EXPLICIT_LINK,
                            item.meeting, "metadata is available but no explicit link was found")

        if scope_value.get("kind") == "tdoc" and scope_value["tdoc_id"].upper() not in coverage:
            self._cover(coverage, scope_value["tdoc_id"], LinkCoverageState.SOURCE_MISSING,
                        None, "no local metadata, discussion record, or SemanticEvidence was found")

        graph = self._graph(group, scope_value, nodes.values(), links.values(), coverage.values())
        return graph

    def build_for_tdoc(self, working_group: WorkingGroup | str, tdoc_id: str) -> EvidenceLinkGraph:
        group = WorkingGroup.parse(working_group)
        wanted = tdoc_id.upper()
        current = self.repository.query_tdocs(TDocQuery(
            working_groups=[group], tdoc_id=wanted))
        preferred = {wanted: current[0]} if len(current) == 1 else {}
        all_evidence = EvidenceExtractionService(self.repository, self.data_root).list_evidence(
            EvidenceExtractionRequest(working_groups=[group], limit=5000))
        evidence = [item for item in all_evidence if item.tdoc_id.upper() == wanted
                    or any(match.group(0).upper() == wanted
                           for match in rules.TDOC_REFERENCE_PATTERN.finditer(item.statement_text))]
        source_ids = {item.tdoc_id.upper() for item in evidence}
        all_metadata = self._all_metadata(group)
        metadata = [item for item in all_metadata if item.tdoc_id.upper() in source_ids | {wanted}
                    or wanted in {value.upper() for value in item.related_tdoc_ids}
                    or any(match.group(0).upper() == wanted
                           for field in (item.title or "", item.abstract or "")
                           for match in rules.TDOC_REFERENCE_PATTERN.finditer(field))]
        return self.resolve_links(working_group=group, semantic_evidence=evidence,
                                  metadata_records=metadata, preferred_metadata=preferred,
                                  scope={"kind": "tdoc", "tdoc_id": tdoc_id.upper()})

    def build_for_meeting(self, working_group: WorkingGroup | str, meeting: str) -> EvidenceLinkGraph:
        group = WorkingGroup.parse(working_group)
        meeting_raw = str(meeting)
        meeting, source_alias = historical_rules.normalize_historical_meeting(meeting, group)
        all_metadata = self._all_metadata(group)
        all_evidence = EvidenceExtractionService(self.repository, self.data_root).list_evidence(
            EvidenceExtractionRequest(working_groups=[group], limit=5000))
        evidence = [item for item in all_evidence if item.meeting == meeting
                    or (item.scope is EvidenceScope.MEETING
                        and self._evidence_meetings(item, all_metadata)[1] == meeting)]
        relevant_ids = {item.tdoc_id.upper() for item in evidence}
        relevant_ids.update(match.group(0).upper() for item in evidence
                            for match in rules.TDOC_REFERENCE_PATTERN.finditer(item.statement_text))
        metadata = [item for item in all_metadata
                    if item.meeting == meeting or item.tdoc_id.upper() in relevant_ids]
        return self.resolve_links(working_group=group, semantic_evidence=evidence,
                                  metadata_records=metadata,
                                  scope={"kind": "meeting", "meeting": meeting,
                                         "meeting_raw": meeting_raw,
                                         "source_alias": source_alias})

    def build_for_range(self, coverage) -> EvidenceLinkGraph:
        if isinstance(coverage, HistoricalCoverageRequest):
            coverage = HistoricalCoverageService(
                self.repository, self.data_root).build_coverage(coverage)
        group = coverage.request.working_group
        records: list[DiscussionRecord] = []
        preferred_candidates: dict[str, list[TDocMetadata]] = {}
        tdoc_ids: set[str] = set()
        meetings: list[str] = []
        meeting_aliases: list[dict[str, Any]] = []
        for meeting in coverage.meetings:
            meetings.append(meeting.meeting.meeting)
            meeting_aliases.append(meeting.meeting.model_dump(mode="json"))
            for candidate in (meeting.coverage.chair_note_confirmed
                              + meeting.coverage.unresolved_references
                              + meeting.coverage.metadata_relevant_only):
                tdoc_ids.add(candidate.tdoc_id.upper())
                records.extend(candidate.associations)
                if candidate.metadata is not None:
                    preferred_candidates.setdefault(candidate.tdoc_id.upper(), []).append(candidate.metadata)
        preferred = {}
        for tdoc_id, candidates in preferred_candidates.items():
            unique = {self._metadata_resolution_identity(item): item for item in candidates}
            if len(unique) == 1:
                preferred[tdoc_id] = next(iter(unique.values()))
        metadata = self._all_metadata(group, tdoc_ids=sorted(tdoc_ids))
        metadata.extend(value for value in preferred.values()
                        if value.model_dump(mode="json") not in [x.model_dump(mode="json") for x in metadata])
        all_evidence = EvidenceExtractionService(self.repository, self.data_root).list_evidence(
            EvidenceExtractionRequest(working_groups=[group], limit=5000))
        evidence = [item for item in all_evidence if item.tdoc_id.upper() in tdoc_ids
                    or (item.scope is EvidenceScope.MEETING and any(
                        match.group(0).upper() in tdoc_ids
                        for match in rules.TDOC_REFERENCE_PATTERN.finditer(item.statement_text)))]
        source_metadata = self._all_metadata(group,
            tdoc_ids=sorted({item.tdoc_id.upper() for item in evidence}))
        known_metadata = {rules.identity(item.model_dump(mode="json")) for item in metadata}
        metadata.extend(item for item in source_metadata
                        if rules.identity(item.model_dump(mode="json")) not in known_metadata)
        return self.resolve_links(
            working_group=group, semantic_evidence=evidence, discussion_records=records,
            metadata_records=metadata, preferred_metadata=preferred,
            scope={"kind": "historical_topic", "from_meeting": coverage.request.from_meeting,
                   "to_meeting": coverage.request.to_meeting, "query": coverage.request.query,
                   "coverage_id": coverage.coverage_id, "meetings": meetings,
                   "from_meeting_raw": coverage.request.from_meeting_raw,
                   "to_meeting_raw": coverage.request.to_meeting_raw,
                   "meeting_aliases": meeting_aliases},
        )

    def build_for_topic(self, request: HistoricalCoverageRequest) -> EvidenceLinkGraph:
        coverage = HistoricalCoverageService(self.repository, self.data_root).build_coverage(request)
        return self.build_for_range(coverage)

    def persist(self, graph: EvidenceLinkGraph) -> Path:
        """Persist one compact graph, per-TDoc status, and DuckDB locator indexes."""
        scope_id = rules.identity(graph.scope)[:20]
        relative = Path("derived/links") / graph.working_group.value.casefold() / scope_id / "graph.json.gz"
        path = self.data_root / relative
        statuses = self.build_tdoc_statuses(graph)
        status_relative = self.tdoc_status_relative_path(graph)
        status_path = self.data_root / status_relative
        path.parent.mkdir(parents=True, exist_ok=True)
        status_path.parent.mkdir(parents=True, exist_ok=True)
        payload = gzip.compress(
            json.dumps(graph.model_dump(mode="json"), sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False).encode("utf-8"), mtime=0)
        status_jsonl = b"".join(
            (json.dumps(item.model_dump(mode="json"), sort_keys=True,
                        separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
            for item in statuses)
        status_payload = gzip.compress(status_jsonl, mtime=0)
        path.write_bytes(payload)
        status_path.write_bytes(status_payload)
        scope_json = json.dumps(graph.scope, sort_keys=True)
        self.connection.execute("BEGIN")
        try:
            previous = [row[0] for row in self.connection.execute(
                "SELECT graph_id FROM explicit_link_graph_state WHERE working_group=? AND scope_json=?",
                [graph.working_group.value, scope_json]).fetchall()]
            for graph_id in previous:
                self.connection.execute(
                    "DELETE FROM explicit_link_tdoc_status_state WHERE graph_id=?", [graph_id])
                self.connection.execute("DELETE FROM explicit_link_nodes WHERE graph_id=?", [graph_id])
                self.connection.execute("DELETE FROM explicit_evidence_links WHERE graph_id=?", [graph_id])
                self.connection.execute("DELETE FROM explicit_link_graph_state WHERE graph_id=?", [graph_id])
            self.connection.execute(
                "INSERT INTO explicit_link_graph_state VALUES (?,?,?,?,?,?,?,?,?)",
                [graph.graph_id, graph.working_group.value, scope_json,
                 graph.schema_version, graph.graph_schema_version, rules.EXPLICIT_LINK_RULESET_VERSION,
                 str(relative), graph.graph_checksum, hashlib.sha256(payload).hexdigest()])
            preparation_identities = sorted({identity for item in statuses
                for identity in item.provenance_identities.preparation_source_identities})
            self.connection.execute(
                "INSERT INTO explicit_link_tdoc_status_state VALUES (?,?,?,?,?,?,?)",
                [graph.graph_id, rules.TDOC_EXPLICIT_LINK_STATUS_SCHEMA_VERSION,
                 str(status_relative), hashlib.sha256(status_jsonl).hexdigest(),
                 hashlib.sha256(status_payload).hexdigest(), len(statuses),
                 rules.identity({"graph_sources": graph.source_identities,
                                 "preparation_sources": preparation_identities})])
            if graph.nodes:
                self.connection.executemany(
                    "INSERT INTO explicit_link_nodes VALUES (?,?,?,?,?,?,?)",
                    [[graph.graph_id, n.node_id, n.kind.value, n.working_group.value,
                      n.meeting, n.tdoc_id, n.source_identity] for n in graph.nodes])
            if graph.links:
                self.connection.executemany(
                    "INSERT INTO explicit_evidence_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [[graph.graph_id, link.link_id, link.kind.value, link.source_node.node_id,
                      link.target_node.node_id, link.literal_basis, link.discussion_meeting,
                      link.source_meeting, link.discovery_meeting, link.authority_meeting,
                      link.metadata_meeting, link.resolution_state.value,
                      link.ruleset_version] for link in graph.links])
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        self.connection.execute("COMMIT")
        for graph_id in previous:
            if graph_id == graph.graph_id:
                continue
            stale = (self.data_root / "derived" / "links"
                     / graph.working_group.value.casefold() / graph_id / "tdoc-status.jsonl.gz")
            stale.unlink(missing_ok=True)
            try:
                stale.parent.rmdir()
            except OSError:
                pass
        return path

    @staticmethod
    def tdoc_status_relative_path(graph: EvidenceLinkGraph) -> Path:
        return (Path("derived/links") / graph.working_group.value.casefold()
                / graph.graph_id / "tdoc-status.jsonl.gz")

    def build_tdoc_statuses(self, graph: EvidenceLinkGraph) -> list[TDocExplicitLinkStatus]:
        """Build one independent-axis status record for each canonical TDoc node."""
        candidates = {candidate.node_id for link in graph.links
                      for candidate in link.resolution_candidates}
        definitive = {node.node_id for link in graph.links
                      if link.resolution_state is LinkCoverageState.LINKED
                      for node in (link.source_node, link.target_node)}
        grouped: dict[tuple[str, str, str], list[EvidenceNodeRef]] = {}
        for node in graph.nodes:
            if (node.kind is not EvidenceNodeKind.TDOC or node.meeting is None
                    or (node.node_id in candidates and node.node_id not in definitive)):
                continue
            key = (node.working_group.value, node.meeting, (node.tdoc_id or "").upper())
            grouped.setdefault(key, []).append(node)
        statuses = []
        for nodes in grouped.values():
            nodes.sort(key=lambda item: (item.node_id not in definitive, item.node_id))
            statuses.append(self._tdoc_status(graph, nodes[0], nodes))
        return sorted(statuses, key=lambda item: (
            item.working_group.value, self._meeting_key(item.metadata_meeting),
            item.tdoc_id, item.node_id))

    def plan_preparation(self, graph: EvidenceLinkGraph) -> LinkPreparationPlan:
        items: list[LinkPreparationItem] = []
        for entry in graph.coverage:
            metadata = self._find_preferred_metadata(entry.working_group, entry.tdoc_id,
                                                     entry.metadata_meeting)
            receipt = self.repository.get_document_receipt(
                entry.tdoc_id, entry.working_group, entry.metadata_meeting) if entry.metadata_meeting else None
            semantic = self.connection.execute(
                "SELECT status FROM semantic_evidence_state WHERE upper(tdoc_id)=upper(?) "
                "AND working_group=?" + (" AND meeting_number=?" if entry.metadata_meeting else ""),
                [entry.tdoc_id, entry.working_group.value]
                + ([entry.metadata_meeting] if entry.metadata_meeting else []),
            ).fetchone()
            if metadata is None:
                state, fetch, reason = LinkCoverageState.SOURCE_MISSING, None, "metadata source is unresolved"
            elif receipt is None:
                state = LinkCoverageState.BODY_NOT_LOCAL
                fetch = metadata.availability.value == "downloadable"
                reason = "contribution body is not local; any acquisition remains an explicit separate action"
            elif semantic is None or semantic[0] != "EXTRACTED":
                state, fetch = LinkCoverageState.SEMANTIC_EVIDENCE_NOT_EXTRACTED, False
                reason = "local body has no fresh SemanticEvidence extraction"
            else:
                state, fetch, reason = entry.state, False, "available local evidence was inspected"
            items.append(LinkPreparationItem(
                tdoc_id=entry.tdoc_id, meeting=entry.metadata_meeting, coverage_state=state,
                body_fetch_needed=fetch, normalization_needed=bool(receipt and not receipt.normalized_path),
                index_needed=self._index_needed(receipt),
                semantic_extraction_needed=bool(receipt and (semantic is None or semantic[0] != "EXTRACTED")),
                meeting_evidence_missing=not any(
                    link.target_node.tdoc_id == entry.tdoc_id
                    and link.source_node.kind is EvidenceNodeKind.SEMANTIC_EVIDENCE
                    and link.source_node.evidence_scope is EvidenceScope.MEETING
                    and link.kind is not ExplicitLinkKind.SAME_TDOC for link in graph.links),
                reason=reason,
            ))
        items.sort(key=lambda item: (item.tdoc_id, item.meeting or ""))
        payload = {"schema": rules.LINK_PREPARATION_SCHEMA_VERSION,
                   "graph_id": graph.graph_id,
                   "items": [item.model_dump(mode="json") for item in items]}
        return LinkPreparationPlan(schema_version=rules.LINK_PREPARATION_SCHEMA_VERSION,
                                   plan_id="link-plan-" + rules.identity(payload),
                                   graph_id=graph.graph_id, items=items)

    def _tdoc_status(self, graph: EvidenceLinkGraph, node: EvidenceNodeRef,
                     canonical_nodes: Sequence[EvidenceNodeRef]) -> TDocExplicitLinkStatus:
        assert node.tdoc_id is not None
        canonical_node_ids = {item.node_id for item in canonical_nodes}
        incident = [link for link in graph.links
                    if link.source_node.node_id in canonical_node_ids
                    or link.target_node.node_id in canonical_node_ids]
        chair_links = [link for link in incident
                       if link.kind is ExplicitLinkKind.DISCUSSION_REFERENCE
                       and link.target_node.node_id in canonical_node_ids
                       and link.resolution_state is LinkCoverageState.LINKED]
        contribution_links = [link for link in incident
                              if link.kind is ExplicitLinkKind.SAME_TDOC
                              and link.target_node.node_id in canonical_node_ids
                              and link.source_node.evidence_scope is EvidenceScope.CONTRIBUTION
                              and link.resolution_state is LinkCoverageState.LINKED]
        meeting_links = [link for link in incident
                         if link.kind is not ExplicitLinkKind.SAME_TDOC
                         and link.target_node.node_id in canonical_node_ids
                         and link.source_node.kind is EvidenceNodeKind.SEMANTIC_EVIDENCE
                         and link.source_node.evidence_scope is EvidenceScope.MEETING
                         and link.resolution_state is LinkCoverageState.LINKED]
        cross_links = [link for link in graph.links
                       if link.resolution_state is LinkCoverageState.LINKED
                       and any(self._is_cross_meeting_reference(link, candidate)
                               for candidate in canonical_nodes)]
        coverage = next((item for item in graph.coverage
                         if item.tdoc_id.upper() == node.tdoc_id.upper()
                         and item.metadata_meeting == node.meeting), None)
        if coverage is None:
            coverage = next((item for item in graph.coverage
                             if item.tdoc_id.upper() == node.tdoc_id.upper()), None)
        base_state = coverage.state if coverage else LinkCoverageState.NO_EXPLICIT_LINK
        preparation = self._preparation_item(
            graph, node.tdoc_id, node.working_group, node.meeting, base_state,
            metadata_resolved=any(locator.locator_type == "metadata"
                                  for locator in node.locators))
        contribution_state = self._contribution_evidence_state(
            node, contribution_links, preparation)
        provenance = TDocStatusProvenance(
            canonical_tdoc_source_identity=node.source_identity,
            canonical_tdoc_source_identities=sorted(
                {item.source_identity for item in canonical_nodes}),
            chair_note_source_identities=self._link_identities(chair_links),
            contribution_evidence_source_identities=self._link_identities(contribution_links),
            meeting_evidence_source_identities=self._link_identities(meeting_links),
            cross_meeting_source_identities=self._link_identities(cross_links),
            preparation_source_identities=self._preparation_identities(
                node.working_group, node.tdoc_id, node.meeting),
        )
        versions = dict(graph.versions)
        versions["tdoc_explicit_link_status_schema"] = (
            rules.TDOC_EXPLICIT_LINK_STATUS_SCHEMA_VERSION)
        logical = {
            "schema_version": rules.TDOC_EXPLICIT_LINK_STATUS_SCHEMA_VERSION,
            "graph_id": graph.graph_id,
            "graph_checksum": graph.graph_checksum,
            "node_id": node.node_id,
            "tdoc_id": node.tdoc_id.upper(),
            "working_group": node.working_group.value,
            "metadata_meeting": node.meeting,
            "document_role": node.document_role.value if node.document_role else None,
            "chair_note_discussion_link_state": self._presence(chair_links).value,
            "contribution_semantic_evidence_state": contribution_state.value,
            "meeting_explicit_link_state": self._presence(meeting_links).value,
            "cross_meeting_reference_state": self._presence(cross_links).value,
            "preparation_state": preparation.model_dump(mode="json"),
            "provenance_identities": provenance.model_dump(mode="json"),
            "versions": versions,
            "limitations": [
                "NO_EXPLICIT_LINK records only the absence of a qualifying explicit link "
                "in the available inspected sources; it is not negative evidence.",
                "Each coverage axis is independent and does not overwrite another axis.",
            ],
        }
        return TDocExplicitLinkStatus(
            **logical, record_checksum=rules.identity(logical))

    def _preparation_item(self, graph, tdoc_id, group, meeting,
                          base_state, *, metadata_resolved=False) -> LinkPreparationItem:
        metadata = self._find_preferred_metadata(group, tdoc_id, meeting)
        receipt = self.repository.get_document_receipt(
            tdoc_id, group, meeting) if meeting else None
        parameters = [tdoc_id, group.value] + ([meeting] if meeting else [])
        semantic = self.connection.execute(
            "SELECT status FROM semantic_evidence_state WHERE upper(tdoc_id)=upper(?) "
            "AND working_group=?" + (" AND meeting_number=?" if meeting else ""),
            parameters).fetchone()
        if metadata is None and not metadata_resolved:
            state, fetch, reason = (
                LinkCoverageState.SOURCE_MISSING, None, "metadata source is unresolved")
        elif receipt is None:
            state = LinkCoverageState.BODY_NOT_LOCAL
            fetch = (metadata.availability.value == "downloadable"
                     if metadata is not None else None)
            reason = ("contribution body is not local; any acquisition remains an "
                      "explicit separate action")
        elif semantic is None or semantic[0] != "EXTRACTED":
            state, fetch = LinkCoverageState.SEMANTIC_EVIDENCE_NOT_EXTRACTED, False
            reason = "local body has no fresh SemanticEvidence extraction"
        else:
            state, fetch, reason = base_state, False, "available local evidence was inspected"
        return LinkPreparationItem(
            tdoc_id=tdoc_id.upper(), meeting=meeting, coverage_state=state,
            body_fetch_needed=fetch,
            normalization_needed=bool(receipt and not receipt.normalized_path),
            index_needed=self._index_needed(receipt),
            semantic_extraction_needed=bool(
                receipt and (semantic is None or semantic[0] != "EXTRACTED")),
            meeting_evidence_missing=not any(
                link.target_node.tdoc_id
                and link.target_node.tdoc_id.upper() == tdoc_id.upper()
                and link.target_node.meeting == meeting
                and link.source_node.kind is EvidenceNodeKind.SEMANTIC_EVIDENCE
                and link.source_node.evidence_scope is EvidenceScope.MEETING
                and link.kind is not ExplicitLinkKind.SAME_TDOC for link in graph.links),
            reason=reason,
        )

    @staticmethod
    def _presence(links) -> ExplicitLinkPresenceState:
        return (ExplicitLinkPresenceState.EXPLICIT_LINK_PRESENT if links
                else ExplicitLinkPresenceState.NO_EXPLICIT_LINK)

    @staticmethod
    def _contribution_evidence_state(node, links, preparation):
        if links:
            return ContributionSemanticEvidenceState.SEMANTIC_EVIDENCE_AVAILABLE
        if node.document_role is not DocumentRole.CONTRIBUTION:
            return ContributionSemanticEvidenceState.NOT_APPLICABLE
        if preparation.coverage_state is LinkCoverageState.SOURCE_MISSING:
            return ContributionSemanticEvidenceState.SOURCE_MISSING
        if preparation.coverage_state is LinkCoverageState.BODY_NOT_LOCAL:
            return ContributionSemanticEvidenceState.BODY_NOT_LOCAL
        if preparation.semantic_extraction_needed:
            return ContributionSemanticEvidenceState.SEMANTIC_EVIDENCE_NOT_EXTRACTED
        return ContributionSemanticEvidenceState.NO_SEMANTIC_EVIDENCE

    @staticmethod
    def _link_identities(links) -> list[str]:
        return sorted({identity for link in links for identity in (
            link.source_node.source_identity, link.target_node.source_identity,
            *(locator.source_identity for locator in link.locators))})

    def _preparation_identities(self, group, tdoc_id, meeting) -> list[str]:
        identities: list[str] = []
        filters = [tdoc_id, group.value] + ([meeting] if meeting else [])
        suffix = " AND meeting_number=?" if meeting else ""
        queries = [
            ("document", "SELECT raw_checksum,normalized_checksum,normalization_identity_json "
             "FROM tdoc_documents WHERE upper(tdoc_id)=upper(?) AND working_group=?" + suffix),
            ("index", "SELECT normalized_checksum,index_schema_version,tokenizer_version,status "
             "FROM search_index_state WHERE upper(tdoc_id)=upper(?) AND working_group=?" + suffix),
            ("semantic", "SELECT normalization_identity_json,normalized_checksum,"
             "evidence_schema_version,ruleset_version,evidence_checksum,status "
             "FROM semantic_evidence_state WHERE upper(tdoc_id)=upper(?) AND working_group=?"
             + suffix),
        ]
        for layer, query in queries:
            for row in self.connection.execute(query, filters).fetchall():
                identities.append(f"{layer}:" + rules.identity(list(row)))
        return sorted(set(identities))

    @staticmethod
    def _is_cross_meeting_reference(link, node) -> bool:
        node_is_endpoint = (link.source_node.node_id == node.node_id
                            or link.target_node.node_id == node.node_id)
        semantic_belongs_to_node = (
            link.source_node.kind is EvidenceNodeKind.SEMANTIC_EVIDENCE
            and link.source_node.tdoc_id
            and node.tdoc_id
            and link.source_node.tdoc_id.upper() == node.tdoc_id.upper()
            and link.source_node.meeting == node.meeting)
        if not node_is_endpoint and not semantic_belongs_to_node:
            return False
        if link.kind is ExplicitLinkKind.SAME_TDOC:
            return False
        if link.kind is ExplicitLinkKind.DISCUSSION_REFERENCE:
            source_meeting = link.discussion_meeting
        elif (link.source_node.kind is EvidenceNodeKind.SEMANTIC_EVIDENCE
              and link.source_node.evidence_scope is EvidenceScope.MEETING):
            source_meeting = link.authority_meeting or link.source_meeting
        else:
            source_meeting = link.source_meeting or link.source_node.meeting
        target_meeting = link.metadata_meeting or link.target_node.meeting
        return bool(source_meeting and target_meeting and source_meeting != target_meeting)

    def _all_metadata(self, group: WorkingGroup, *, tdoc_ids: Sequence[str] = (),
                      meetings: Sequence[str] = ()) -> list[TDocMetadata]:
        result: list[TDocMetadata] = []
        if tdoc_ids:
            for tdoc_id in tdoc_ids:
                target_group = self._tdoc_group(tdoc_id)
                result.extend(self.repository.query_tdocs(TDocQuery(
                    working_groups=[target_group], tdoc_id=tdoc_id)))
                result.extend(item for _, item in self.repository.find_tdoc_snapshot_candidates(
                    target_group, tdoc_id))
        elif meetings:
            for meeting in meetings:
                result.extend(self.repository.list_tdocs(group, meeting))
                for snapshot in self.repository.list_tdoc_list_snapshots(group, meeting):
                    result.extend(snapshot.tdocs)
        else:
            result.extend(self.repository.query_tdocs(TDocQuery(working_groups=[group])))
            for meeting in self.repository.list_known_meetings(group):
                for snapshot in self.repository.list_tdoc_list_snapshots(group, meeting):
                    result.extend(snapshot.tdocs)
        unique = {rules.identity(item.model_dump(mode="json")): item for item in result}
        return sorted(unique.values(), key=lambda item: (item.meeting, item.tdoc_id, item.title or ""))

    def _resolve_tdoc_node(self, group, tdoc_id, metadata, preferred, expected_meeting=None):
        tdoc_id = tdoc_id.upper()
        if tdoc_id in preferred and preferred[tdoc_id].working_group is group:
            node = self._metadata_node(preferred[tdoc_id])
            return node, LinkCoverageState.LINKED, []
        candidates = [item for item in metadata
                      if item.working_group is group and item.tdoc_id.upper() == tdoc_id]
        if expected_meeting:
            expected, _ = historical_rules.normalize_historical_meeting(expected_meeting, group)
            exact = [item for item in candidates if item.meeting == expected]
            if exact:
                candidates = exact
        logical: dict[str, TDocMetadata] = {}
        for item in candidates:
            key = self._metadata_resolution_identity(item)
            logical[key] = item
        candidate_nodes = sorted((self._metadata_node(item) for item in logical.values()),
                                 key=lambda node: node.node_id)
        if len(candidate_nodes) == 1:
            return candidate_nodes[0], LinkCoverageState.LINKED, []
        unresolved = self._unresolved_tdoc_node(group, tdoc_id)
        if not candidate_nodes:
            return unresolved, LinkCoverageState.UNRESOLVED_REFERENCE, []
        return unresolved, LinkCoverageState.AMBIGUOUS_REFERENCE, candidate_nodes

    def _semantic_node(self, item: SemanticEvidence) -> EvidenceNodeRef:
        source = item.model_dump(mode="json")
        source.pop("extracted_at", None)
        identity = rules.identity(source)
        locators = [SourceLocator(locator_type="EvidenceRef", source_artifact=item.tdoc_id,
            source_identity=identity, reference=span.model_dump(mode="json"))
            for span in item.evidence_refs]
        payload = {"kind": "semantic_evidence", "evidence_id": item.evidence_id,
                   "source_identity": identity}
        return EvidenceNodeRef(node_id="node-" + rules.identity(payload),
            kind=EvidenceNodeKind.SEMANTIC_EVIDENCE, working_group=item.working_group,
            meeting=item.meeting, tdoc_id=item.tdoc_id, source_artifact=item.evidence_id,
            evidence_kind=item.kind, evidence_scope=item.scope,
            document_role=item.document_role,
            source_organizations=item.source_organizations,
            source_identity=identity, locators=locators)

    def _discussion_node(self, item: DiscussionRecord) -> EvidenceNodeRef:
        ref = item.reference.source_ref
        identity = rules.identity(item.model_dump(mode="json"))
        locator = SourceLocator(locator_type="ChairNoteRef", source_artifact=ref.snapshot_id,
                                source_identity=identity, reference=ref.model_dump(mode="json"))
        payload = {"kind": "discussion_record", "record_id": item.record_id,
                   "source_identity": identity}
        return EvidenceNodeRef(node_id="node-" + rules.identity(payload),
            kind=EvidenceNodeKind.DISCUSSION_RECORD, working_group=ref.working_group,
            meeting=ref.meeting, tdoc_id=item.reference.tdoc_id,
            source_artifact=ref.snapshot_id, source_identity=identity, locators=[locator])

    def _source_tdoc_node(self, item: SemanticEvidence) -> EvidenceNodeRef:
        payload = {"kind": "tdoc", "working_group": item.working_group.value,
                   "meeting": item.meeting, "tdoc_id": item.tdoc_id.upper(),
                   "parent_evidence": item.evidence_id,
                   "normalization_identity": item.normalization_identity}
        identity = rules.identity(payload)
        locator = SourceLocator(locator_type="SemanticEvidenceParent",
            source_artifact=item.evidence_id, source_identity=identity,
            reference={"evidence_id": item.evidence_id, "tdoc_id": item.tdoc_id,
                       "meeting": item.meeting,
                       "normalization_identity": item.normalization_identity})
        return EvidenceNodeRef(node_id="node-" + identity, kind=EvidenceNodeKind.TDOC,
            working_group=item.working_group, meeting=item.meeting, tdoc_id=item.tdoc_id,
            document_role=item.document_role,
            source_organizations=item.source_organizations,
            source_artifact=item.evidence_id, source_identity=identity, locators=[locator])

    def _metadata_node(self, item: TDocMetadata) -> EvidenceNodeRef:
        identity = rules.identity(item.model_dump(mode="json"))
        locator = self._metadata_locator(item, "record")
        role = classify_document_role(item).role
        payload = {"kind": "tdoc", "working_group": item.working_group.value,
                   "meeting": item.meeting, "tdoc_id": item.tdoc_id.upper(),
                   "source_identity": identity}
        return EvidenceNodeRef(node_id="node-" + rules.identity(payload), kind=EvidenceNodeKind.TDOC,
            working_group=item.working_group, meeting=item.meeting, tdoc_id=item.tdoc_id.upper(),
            document_role=role,
            source_organizations=(item.organizations if role is DocumentRole.CONTRIBUTION else []),
            source_artifact=locator.source_artifact, source_identity=identity, locators=[locator])

    def _metadata_locator(self, item: TDocMetadata, field: str,
                          char_start: int | None = None,
                          char_end: int | None = None) -> SourceLocator:
        identity = rules.identity(item.model_dump(mode="json"))
        artifact = str(item.metadata_source_url or item.source_url
                       or f"metadata:{item.working_group.value}:{item.meeting}:{item.tdoc_id}")
        return SourceLocator(locator_type="metadata", source_artifact=artifact,
            source_identity=identity, reference={"tdoc_id": item.tdoc_id,
                "working_group": item.working_group.value, "meeting": item.meeting,
                "field": field, "char_start": char_start, "char_end": char_end,
                "metadata_source_checksum": item.metadata_source_checksum})

    def _literal_evidence_locator(self, source, item, char_start, char_end):
        span = self._source_span(item, char_start, char_end)
        return SourceLocator(locator_type="EvidenceRef", source_artifact=item.evidence_id,
            source_identity=source.source_identity, reference={
                "evidence_id": item.evidence_id, "char_start": char_start,
                "char_end": char_end, "evidence_span": span})

    @staticmethod
    def _source_span(item, char_start, char_end):
        offset = 0
        for span in sorted(item.evidence_refs, key=lambda value: value.sequence):
            if span.row_index is not None:
                return span.model_dump(mode="json")
            length = (span.char_end - (span.char_start or 0)
                      if span.char_end is not None else len(item.statement_text))
            if offset <= char_start and char_end <= offset + length:
                start = (span.char_start or 0) + char_start - offset
                return span.model_copy(update={"char_start": start,
                    "char_end": start + char_end - char_start}).model_dump(mode="json")
            offset += length + 1
        raise ValueError("literal reference cannot be mapped to its SemanticEvidence span")

    def _unresolved_tdoc_node(self, group, tdoc_id):
        payload = {"kind": "tdoc", "working_group": group.value,
                   "meeting": None, "tdoc_id": tdoc_id.upper(), "unresolved": True}
        identity = rules.identity(payload)
        locator = SourceLocator(locator_type="unresolved_tdoc_reference",
            source_artifact=f"unresolved:{tdoc_id.upper()}", source_identity=identity,
            reference={"tdoc_id": tdoc_id.upper()})
        return EvidenceNodeRef(node_id="node-" + identity, kind=EvidenceNodeKind.TDOC,
            working_group=group, tdoc_id=tdoc_id.upper(),
            source_artifact=locator.source_artifact, source_identity=identity, locators=[locator])

    def _meeting_node(self, group, meeting, raw):
        payload = {"kind": "meeting", "working_group": group.value,
                   "meeting": meeting, "raw": raw,
                   "alias_ruleset": historical_rules.MEETING_ALIAS_RULESET_VERSION}
        identity = rules.identity(payload)
        locator = SourceLocator(locator_type="literal_meeting_reference",
            source_artifact=f"meeting:{group.value}:{meeting}", source_identity=identity,
            reference={"meeting": meeting, "raw_text": raw})
        return EvidenceNodeRef(node_id="node-" + identity, kind=EvidenceNodeKind.MEETING,
            working_group=group, meeting=meeting, meeting_raw=raw,
            source_artifact=locator.source_artifact, source_identity=identity, locators=[locator])

    def _link(self, kind, source, target, literal, locators, state, candidates,
              discussion_meeting=None, source_meeting=None, discovery_meeting=None,
              authority_meeting=None, metadata_meeting=None,
              disposition=None):
        payload = {"kind": kind.value, "source": source.node_id, "target": target.node_id,
                   "literal": literal, "locators": [x.model_dump(mode="json") for x in locators],
                   "discussion_meeting": discussion_meeting, "source_meeting": source_meeting,
                   "discovery_meeting": discovery_meeting,
                   "authority_meeting": authority_meeting,
                   "metadata_meeting": metadata_meeting, "state": state.value,
                   "candidates": [x.node_id for x in candidates], "disposition": disposition,
                   "ruleset": rules.EXPLICIT_LINK_RULESET_VERSION,
                   "alias_ruleset": historical_rules.MEETING_ALIAS_RULESET_VERSION}
        return ExplicitEvidenceLink(link_id="link-" + rules.identity(payload), kind=kind,
            source_node=source, target_node=target, literal_basis=literal,
            locators=list(locators), discussion_meeting=discussion_meeting,
            source_meeting=source_meeting, discovery_meeting=discovery_meeting,
            authority_meeting=authority_meeting, metadata_meeting=metadata_meeting,
            resolution_state=state, resolution_candidates=list(candidates),
            disposition=disposition, ruleset_version=rules.EXPLICIT_LINK_RULESET_VERSION)

    def _graph(self, group, scope, nodes, links, coverage):
        nodes = sorted(nodes, key=lambda item: (self._meeting_key(item.meeting),
                                                item.kind.value, item.node_id))
        links = sorted(links, key=lambda item: (
            self._meeting_key(item.discussion_meeting or item.source_meeting
                              or item.metadata_meeting),
            item.kind.value, item.source_node.node_id, item.target_node.node_id, item.link_id))
        coverage = sorted(coverage, key=lambda item: (item.tdoc_id, item.metadata_meeting or ""))
        states = {item.state for item in coverage}
        if (not nodes and scope) or states & {LinkCoverageState.SOURCE_MISSING, LinkCoverageState.BODY_NOT_LOCAL,
                     LinkCoverageState.SEMANTIC_EVIDENCE_NOT_EXTRACTED}:
            completeness = LinkCompleteness.SOURCE_PREPARATION_REQUIRED
        elif states & {LinkCoverageState.AMBIGUOUS_REFERENCE,
                       LinkCoverageState.UNRESOLVED_REFERENCE}:
            completeness = LinkCompleteness.PARTIAL_EVIDENCE_COVERAGE
        else:
            completeness = LinkCompleteness.COMPLETE_FOR_AVAILABLE_EVIDENCE
        versions = {"explicit_link_schema": rules.EXPLICIT_LINK_SCHEMA_VERSION,
            "link_graph_schema": rules.LINK_GRAPH_SCHEMA_VERSION,
            "explicit_link_ruleset": rules.EXPLICIT_LINK_RULESET_VERSION,
            "meeting_alias_ruleset": historical_rules.MEETING_ALIAS_RULESET_VERSION}
        logical = {"working_group": group.value, "scope": scope,
            "nodes": [item.model_dump(mode="json") for item in nodes],
            "links": [item.model_dump(mode="json") for item in links],
            "coverage": [item.model_dump(mode="json") for item in coverage],
            "completeness": completeness.value, "versions": versions}
        checksum = rules.identity(logical)
        diagnostics = {"nodes": len(nodes), "links": len(links),
            "linked": sum(x.resolution_state is LinkCoverageState.LINKED for x in links),
            "unresolved": sum(x.resolution_state is LinkCoverageState.UNRESOLVED_REFERENCE for x in links),
            "ambiguous": sum(x.resolution_state is LinkCoverageState.AMBIGUOUS_REFERENCE for x in links)}
        return EvidenceLinkGraph(schema_version=rules.EXPLICIT_LINK_SCHEMA_VERSION,
            graph_schema_version=rules.LINK_GRAPH_SCHEMA_VERSION,
            graph_id="link-graph-" + checksum, graph_checksum=checksum,
            working_group=group, scope=scope, nodes=nodes, links=links,
            coverage=coverage, completeness=completeness,
            source_identities=sorted({item.source_identity for item in nodes}),
            versions=versions, diagnostics=diagnostics,
            limitations=[
                "Explicit links are document/reference-level unless literal source text states more.",
                "A TDoc reference does not project a meeting disposition onto every contribution statement.",
                "Missing explicit links are not evidence that no relationship exists.",
                "Chair Note discussion references are positive discussion context, not meeting outcomes.",
            ])

    @staticmethod
    def _cover(values, tdoc_id, state, meeting, detail):
        key = tdoc_id.upper()
        existing = values.get(key)
        priority = {LinkCoverageState.AMBIGUOUS_REFERENCE: 3,
                    LinkCoverageState.UNRESOLVED_REFERENCE: 2,
                    LinkCoverageState.SOURCE_MISSING: 2,
                    LinkCoverageState.BODY_NOT_LOCAL: 2,
                    LinkCoverageState.SEMANTIC_EVIDENCE_NOT_EXTRACTED: 2,
                    LinkCoverageState.LINKED: 1,
                    LinkCoverageState.NO_EXPLICIT_LINK: 0}
        if existing is None or priority.get(state, 0) > priority.get(existing.state, 0):
            values[key] = LinkCoverage(tdoc_id=key, state=state,
                working_group=(WorkingGroup.RAN1 if key.startswith("R1-") else WorkingGroup.RAN2),
                metadata_meeting=meeting, detail=detail)

    def _find_preferred_metadata(self, group, tdoc_id, meeting):
        if meeting:
            found = self.repository.get_tdoc(group, meeting, tdoc_id)
            if found:
                return found
            matches = [item for _, item in self.repository.find_tdoc_snapshot_candidates(group, tdoc_id)
                       if item.meeting == meeting]
            if len(matches) == 1:
                return matches[0]
        matches = self._all_metadata(group, tdoc_ids=[tdoc_id])
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _metadata_resolution_identity(item):
        return rules.identity({
            "working_group": item.working_group.value, "meeting": item.meeting,
            "tdoc_id": item.tdoc_id, "title": item.title,
            "organizations": item.organizations, "source_url": str(item.source_url or ""),
            "metadata_checksum": item.metadata_source_checksum,
        })

    def _index_needed(self, receipt: DocumentReceipt | None) -> bool:
        if receipt is None or receipt.normalized_path is None:
            return False
        row = self.connection.execute(
            "SELECT status,normalized_checksum FROM search_index_state WHERE tdoc_id=? "
            "AND working_group=? AND meeting_number=?",
            [receipt.tdoc_id, receipt.working_group.value, receipt.meeting]).fetchone()
        return not bool(row and row[0] == "INDEXED" and row[1] == receipt.normalized_checksum)

    @staticmethod
    def _evidence_meetings(item, metadata):
        discovery = item.meeting
        if item.scope is not EvidenceScope.MEETING:
            return discovery, None
        sources = [record for record in metadata
                   if record.working_group is item.working_group
                   and record.meeting == item.meeting
                   and record.tdoc_id.upper() == item.tdoc_id.upper()]
        if len(sources) != 1:
            return discovery, None
        authority = resolve_authority_meeting(sources[0], DocumentRole.MEETING_REPORT)
        return discovery, (authority.authority_meeting.meeting_id
                           if authority.authority_meeting else None)

    @staticmethod
    def _meeting_key(meeting):
        if meeting is None:
            return (10**9, 9, "")
        try:
            return (*historical_rules.meeting_order_key(meeting), "")
        except ValueError:
            return (10**9, 8, str(meeting))

    @staticmethod
    def _tdoc_group(tdoc_id):
        return WorkingGroup.RAN1 if tdoc_id.upper().startswith("R1-") else WorkingGroup.RAN2
