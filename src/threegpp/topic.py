from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.evidence import EvidenceExtractionService
from threegpp.models import (
    AgreementDisposition, ContextRole, DispositionEvidence, DocumentRole,
    EvidenceContext, EvidenceExtractionRequest, EvidenceKind, EvidenceLink,
    EvidenceLinkType, EvidenceRef, EvidenceScope, MeetingAuthority,
    MeetingAuthorityBasis, MeetingIdentity, MeetingTimelineEntry, SemanticEvidence,
    TDocMetadata, TopicCoverage, TopicEvidenceBundle, TopicEvidenceItem,
    TopicStudyRequest, normalize_report_meeting_identifier,
)
from threegpp.models.search import EvidenceSearchQuery
from threegpp.search import EvidenceSearchService, tokenize

TOPIC_STUDY_SCHEMA_VERSION = "2"
MEETING_AUTHORITY_RULESET_VERSION = "meeting-authority-v1"
AGREEMENT_DISPOSITION_RULESET_VERSION = "agreement-disposition-v2"
EVIDENCE_CONTEXT_RULESET_VERSION = "evidence-context-v1"
CONTEXT_ADJACENCY_LIMIT = 3

_REPORT_TITLE = re.compile(
    r"\b(?:report(?:\s+of)?|final\s+minutes(?:\s+of)?)\s+(?P<raw>RAN[12]\s*#\s*(?P<id>[0-9]+(?:bis|b|-e)?))(?:\s+meeting)?\b",
    re.IGNORECASE,
)
_DISPOSITION_RULES = (
    (AgreementDisposition.STUDY, "study-explicit-v1", re.compile(r"\bstud(?:y|ies|ied|ying)\b", re.I)),
    (AgreementDisposition.SELECT, "select-explicit-v1", re.compile(r"\b(?:select(?:ed)?|is\s+selected)\b", re.I)),
    (AgreementDisposition.ENDORSE, "endorse-explicit-v1", re.compile(r"\bendorse(?:d|ment)?\b", re.I)),
    (AgreementDisposition.ADOPT, "adopt-explicit-v1", re.compile(r"\badopt(?:ed|ion)?\b", re.I)),
    (AgreementDisposition.REUSE, "reuse-explicit-v1", re.compile(r"\b(?:reuse|reused|can\s+be\s+reused)\b", re.I)),
    (AgreementDisposition.DEFER, "defer-explicit-v1", re.compile(r"\b(?:defer(?:red)?|left\s+for\s+later)\b", re.I)),
)
_CONTEXT_LABEL = re.compile(r"^\s*(?P<label>note\s*\d*|remark|condition|exception|ffs)\s*:\s*", re.I)
_TDOC = re.compile(r"\bR[12]-[0-9]{6,8}\b", re.I)
_PENDING_SELECTION = re.compile(
    r"\b(?:to\s+be\s+(?:down-)?selected|(?:down[ -]select|(?:further\s+)?select)\s+"
    r"(?:one\s+)?(?:from|between)|select\s+one\s+of)\b", re.I)


def _matched_span(evidence, match):
    """Map a literal match back through V0.4's newline-joined source spans."""
    offset = 0
    spans = sorted(evidence.evidence_refs, key=lambda span: span.sequence)
    for span in spans:
        if span.row_index is not None:
            # Table statements retain their source row; offsets are not cell offsets.
            return span
        length = (span.char_end - (span.char_start or 0)
                  if span.char_end is not None else len(evidence.statement_text))
        if offset <= match.start() and match.end() <= offset + length:
            start = (span.char_start or 0) + match.start() - offset
            return span.model_copy(update={"char_start": start,
                                           "char_end": start + len(match.group(0))})
        offset += length + 1
    raise ValueError("literal cue cannot be mapped to its source span")


def resolve_authority_meeting(metadata: TDocMetadata, role: DocumentRole) -> MeetingAuthority:
    discovery = MeetingIdentity(working_group=metadata.working_group, meeting_id=metadata.meeting)
    base = dict(discovery_meeting=discovery, ruleset_version=MEETING_AUTHORITY_RULESET_VERSION,
                source_tdoc_id=metadata.tdoc_id)
    if role is not DocumentRole.MEETING_REPORT:
        return MeetingAuthority(**base, unresolved_reason="document is not an authoritative meeting report")
    match = _REPORT_TITLE.search(metadata.title or "")
    if not match:
        return MeetingAuthority(**base, unresolved_reason="report title has no recognized meeting identifier")
    raw = re.sub(r"\s+", "", match.group("raw"))
    raw_group = raw.split("#", 1)[0].upper()
    if raw_group != metadata.working_group.value:
        return MeetingAuthority(**base, unresolved_reason="report title working group conflicts with metadata")
    try:
        normalized = normalize_report_meeting_identifier(match.group("id"))
    except ValueError:
        return MeetingAuthority(**base, unresolved_reason="report title meeting identifier is not confidently normalized")
    return MeetingAuthority(**base,
        authority_meeting=MeetingIdentity(working_group=metadata.working_group,
                                          meeting_id=normalized, raw_text=raw),
        basis=MeetingAuthorityBasis.REPORT_TITLE, rule_id="meeting-report-title-v1")


def classify_agreement_disposition(evidence: SemanticEvidence) -> DispositionEvidence | None:
    if evidence.kind is not EvidenceKind.AGREEMENT or evidence.scope is not EvidenceScope.MEETING:
        return None
    for disposition, rule_id, pattern in _DISPOSITION_RULES:
        match = pattern.search(evidence.statement_text)
        if disposition is AgreementDisposition.SELECT and _PENDING_SELECTION.search(evidence.statement_text):
            continue
        if match:
            return DispositionEvidence(disposition=disposition, matched_cue=match.group(0),
                rule_id=rule_id, rule_version=AGREEMENT_DISPOSITION_RULESET_VERSION,
                evidence_span=_matched_span(evidence, match))
    return DispositionEvidence(disposition=AgreementDisposition.UNCLASSIFIED,
        rule_version=AGREEMENT_DISPOSITION_RULESET_VERSION,
        evidence_span=evidence.evidence_refs[0])


def get_evidence_context(evidence: SemanticEvidence, blocks: list[dict], *, limit: int = CONTEXT_ADJACENCY_LIMIT) -> list[EvidenceContext]:
    """Return only explicitly labelled, same-member/same-section following context."""
    last = evidence.evidence_refs[-1].evidence_ref
    positions = {(b["member_filename"], b["block_id"]): i for i, b in enumerate(blocks)}
    start = positions.get((last.member, last.block_id))
    if start is None:
        return []
    source_heading = blocks[start].get("heading_path", [])
    result = []
    for offset, block in enumerate(blocks[start + 1:start + 1 + limit], 1):
        if block["member_filename"] != last.member or block.get("type") == "heading":
            break
        if block.get("heading_path", []) != source_heading:
            break
        text = _block_text(block)
        match = _CONTEXT_LABEL.match(text)
        if not match:
            break
        label = re.sub(r"\s+|\d+", "", match.group("label").casefold())
        role = {"note": ContextRole.NOTE, "remark": ContextRole.QUALIFICATION,
                "condition": ContextRole.CONDITION, "exception": ContextRole.EXCEPTION,
                "ffs": ContextRole.FFS_CONTEXT}[label]
        result.append(EvidenceContext(evidence_ref=_ref(evidence, block), role=role,
            detection_basis="explicit_context_label", rule_id="explicit-context-label-v1",
            rule_version=EVIDENCE_CONTEXT_RULESET_VERSION, literal_text=text,
            relative_order=offset))
    return result


def extract_explicit_links(evidence: SemanticEvidence) -> list[EvidenceLink]:
    relationship = (EvidenceLinkType.ENDORSES_TDOC
                    if classify_agreement_disposition(evidence) and
                    classify_agreement_disposition(evidence).disposition is AgreementDisposition.ENDORSE
                    else EvidenceLinkType.REFERENCES_TDOC)
    return [EvidenceLink(relationship=relationship, target_tdoc_id=m.group(0).upper(),
                         matched_literal=m.group(0), evidence_span=_matched_span(evidence, m))
            for m in _TDOC.finditer(evidence.statement_text)]


class TopicStudyService:
    """Build deterministic, offline bundles; this service performs no retrieval."""
    def __init__(self, repository: MetadataRepository, data_root: Path):
        self.repository = repository
        self.data_root = Path(data_root)
        self.evidence = EvidenceExtractionService(repository, data_root)
        self.search = EvidenceSearchService(repository, data_root)

    def inspect_meeting_authority(self, tdoc_id: str) -> MeetingAuthority:
        rows = self.repository.connection.execute(
            "SELECT working_group,meeting_number FROM tdoc_metadata WHERE upper(tdoc_id)=upper(?)", [tdoc_id]).fetchall()
        if not rows:
            raise ValueError("TDoc metadata is missing")
        if len(rows) != 1:
            raise ValueError("TDoc ID is ambiguous")
        metadata = self.repository.get_tdoc(rows[0][0], rows[0][1], tdoc_id)
        from threegpp.evidence import classify_document_role
        return resolve_authority_meeting(metadata, classify_document_role(metadata).role)

    def build_topic_study(self, request: TopicStudyRequest) -> TopicEvidenceBundle:
        lexical = self.search.search_evidence(EvidenceSearchQuery(
            query=request.query, working_groups=request.working_groups,
            meetings=request.discovery_meetings, organizations=request.organizations,
            limit=request.limit_per_group * max(1, len(request.working_groups)))) if request.include_lexical_candidates else []
        semantic = self.evidence.list_evidence(EvidenceExtractionRequest(
            working_groups=request.working_groups, meetings=request.discovery_meetings,
            evidence_kinds=request.evidence_kinds, limit=5000))
        query_tokens = set(tokenize(request.query))
        semantic = [e for e in semantic if query_tokens & set(tokenize(e.statement_text))]
        contributions: dict[str, list[TopicEvidenceItem]] = defaultdict(list)
        meetings = []
        block_cache = {}
        for evidence in semantic:
            metadata = self.repository.get_tdoc(evidence.working_group, evidence.meeting, evidence.tdoc_id)
            authority = resolve_authority_meeting(metadata, evidence.document_role)
            if evidence.scope is EvidenceScope.CONTRIBUTION:
                authority = authority.model_copy(update={"authority_meeting": authority.discovery_meeting,
                    "unresolved_reason": None})
            if request.authority_meetings and (not authority.authority_meeting or
                    authority.authority_meeting.meeting_id not in request.authority_meetings):
                continue
            key = (evidence.tdoc_id, evidence.working_group, evidence.meeting)
            if request.include_context and key not in block_cache:
                block_cache[key] = self._blocks(evidence)
            blocks = block_cache.get(key, [])
            item = TopicEvidenceItem(evidence=evidence, meeting_authority=authority,
                disposition=classify_agreement_disposition(evidence),
                context=get_evidence_context(evidence, blocks) if request.include_context else [],
                explicit_links=extract_explicit_links(evidence))
            if evidence.scope is EvidenceScope.CONTRIBUTION and request.include_contribution_evidence:
                for organization in evidence.source_organizations or ["(unknown)"]:
                    if not request.organizations or organization.casefold() in {o.casefold() for o in request.organizations}:
                        contributions[organization].append(item)
            elif evidence.scope is EvidenceScope.MEETING and request.include_meeting_evidence:
                meetings.append(item)
        truncated = False
        for values in contributions.values():
            values.sort(key=_item_key)
            truncated |= len(values) > request.limit_per_group
            del values[request.limit_per_group:]
        meetings.sort(key=_item_key)
        counts = defaultdict(int)
        retained = []
        for item in meetings:
            authority = item.meeting_authority.authority_meeting
            key = (authority.working_group, authority.meeting_id) if authority else None
            counts[key] += 1
            if counts[key] <= request.limit_per_group:
                retained.append(item)
            else:
                truncated = True
        meetings = retained
        timeline = get_topic_timeline(meetings)
        coverage = self._coverage(request, timeline)
        if truncated:
            coverage.limitations.append("Semantic results were truncated by limit_per_group.")
        unresolved = []
        targets = {link.target_tdoc_id for i in meetings for link in i.explicit_links}
        contribution_ids = {i.evidence.tdoc_id for values in contributions.values() for i in values}
        if contributions and meetings:
            for tdoc_id in sorted(contribution_ids - targets):
                unresolved.append(f"no explicit adoption or linkage between contribution {tdoc_id} and meeting evidence is established")
            if contribution_ids & targets:
                unresolved.append("Literal TDoc references do not by themselves establish adoption of a contribution design.")
        bundle = TopicEvidenceBundle(schema_version=TOPIC_STUDY_SCHEMA_VERSION, study_id="",
            topic_query=request.query, coverage=coverage, lexical_candidates=lexical,
            contribution_evidence=dict(sorted(contributions.items())), meeting_evidence=meetings,
            meeting_timeline=timeline, unresolved=unresolved)
        identity_payload = {"request": request.model_dump(mode="json"),
            "bundle": _logical_value(bundle.model_dump(mode="json")),
            "dependencies": self._dependencies(request),
            "versions": [TOPIC_STUDY_SCHEMA_VERSION, MEETING_AUTHORITY_RULESET_VERSION,
                         AGREEMENT_DISPOSITION_RULESET_VERSION, EVIDENCE_CONTEXT_RULESET_VERSION]}
        bundle.study_id = hashlib.sha256(json.dumps(identity_payload, sort_keys=True).encode()).hexdigest()
        return bundle

    def _dependencies(self, request):
        clause, values = _corpus_filter(request)
        return self.repository.connection.execute(
            "SELECT tdoc_id,working_group,meeting_number,metadata_identity_json,"
            "normalization_identity_json,normalized_checksum,evidence_checksum,status "
            "FROM semantic_evidence_state WHERE " + clause +
            " ORDER BY working_group,meeting_number,tdoc_id", values).fetchall()

    def _blocks(self, evidence):
        receipt = self.repository.get_document_receipt(evidence.tdoc_id, evidence.working_group, evidence.meeting)
        if not receipt or not receipt.normalized_path: return []
        return [json.loads(line) for line in gzip.decompress((self.data_root / receipt.normalized_path).read_bytes()).decode().splitlines()]

    def _coverage(self, request, timeline):
        c = self.repository.connection
        clause, values = _corpus_filter(request)
        def count(table, condition):
            return c.execute(f"SELECT count(*) FROM {table} WHERE {condition} AND {clause}", values).fetchone()[0]
        available = count("tdoc_metadata", "current_view_present")
        normalized = count("tdoc_documents", "normalized")
        indexed = count("search_index_state", "status='INDEXED'")
        semantic = count("semantic_evidence_state", "status='EXTRACTED'")
        reports = count("semantic_evidence_state", "document_role='meeting_report'")
        unsupported = count("tdoc_documents", "extraction_status='unsupported_format'")
        authorities = [f"{e.authority_meeting.working_group.value}#{e.authority_meeting.meeting_id}" for e in timeline]
        limitations = ["Coverage is limited to currently local metadata, normalized documents, indexes, and fresh SemanticEvidence."]
        limitations.append("Corpus counts apply to working-group/discovery-meeting filters, before topic, authority, organization, kind, and result limits; indexable counts mean stored INDEXED status, and report counts mean role-classified extraction states.")
        limitations.append("Semantic candidates are bounded to the first 5000 fresh records; lexical candidates use the lexical result limit. Neither layer implies complete topic coverage.")
        if normalized < available: limitations.append("Some available documents are not normalized.")
        if semantic < normalized: limitations.append("Some normalized documents have no current semantic extraction.")
        return TopicCoverage(documents_available=available, documents_normalized=normalized,
            documents_indexable=indexed, documents_semantically_extracted=semantic,
            meeting_reports_available=reports, authority_meetings=authorities,
            unsupported_documents=unsupported, filters_applied={
                "working_groups": [x.value for x in request.working_groups],
                "authority_meetings": request.authority_meetings,
                "discovery_meetings": request.discovery_meetings,
                "organizations": request.organizations,
                "evidence_kinds": [x.value for x in request.evidence_kinds]}, limitations=limitations)


def get_topic_timeline(items: list[TopicEvidenceItem]) -> list[MeetingTimelineEntry]:
    grouped = defaultdict(list)
    identities = {}
    for item in items:
        identity = item.meeting_authority.authority_meeting
        if identity is None: continue
        key = (identity.working_group.value, identity.meeting_id)
        identities[key] = identity; grouped[key].append(item)
    return [MeetingTimelineEntry(authority_meeting=identities[key], events=sorted(grouped[key], key=_item_key))
            for key in sorted(grouped, key=lambda x: (x[0], _meeting_key(x[1])))]


def _meeting_key(value):
    match = re.fullmatch(r"(\d+)(bis|-e)?", value)
    return (int(match.group(1)), {None: 0, "bis": 1, "-e": 2}[match.group(2)])


def _item_key(item):
    ref = item.evidence.evidence_refs[0].evidence_ref
    return (item.evidence.tdoc_id, ref.member, ref.block_id, item.evidence.evidence_id)


def _ref(evidence, block):
    return EvidenceRef(tdoc_id=evidence.tdoc_id, working_group=evidence.working_group,
        meeting=evidence.meeting, member=block["member_filename"], block_id=block["block_id"],
        block_type=block["type"], heading_path=block.get("heading_path", []),
        page=block.get("page_number"), sheet=block.get("sheet_name"))


def _block_text(block):
    if block.get("text") is not None: return block["text"]
    return "\n".join("\t".join(str(cell or "") for cell in row) for row in block.get("rows") or [])


def _corpus_filter(request):
    clauses, values = ["1=1"], []
    for column, wanted in (("working_group", request.working_groups),
                           ("meeting_number", request.discovery_meetings)):
        if wanted:
            clauses.append(column + " IN (" + ",".join("?" for _ in wanted) + ")")
            values.extend(str(item) for item in wanted)
    return " AND ".join(clauses), values


def _logical_value(value):
    if isinstance(value, dict):
        return {k: _logical_value(v) for k, v in value.items() if k != "extracted_at"}
    if isinstance(value, list):
        return [_logical_value(v) for v in value]
    return value
