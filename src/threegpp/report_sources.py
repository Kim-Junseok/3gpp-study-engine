"""Bounded, read-only source access for human research reports.

Passages are literal source material, not newly classified evidence or reviews.
The report writer must inspect context before making a claim from a passage.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from threegpp.chair_notes.service import ChairNoteService, make_ref
from threegpp.chair_notes.coverage import discussion_sections
from threegpp.chair_notes.rules import TDOC_REFERENCE
from threegpp.documents import DocumentService
from threegpp.evidence import classify_document_role
from threegpp.evidence.rules import LABEL_RULES
from threegpp.evidence.service import _authoritative_blocks
from threegpp.historical import HistoricalMetadataResolver
from threegpp.historical.rules import expand_numeric_range, meeting_order_key
from threegpp.models import DocumentRole, EvidenceRef, WorkingGroup
from threegpp.topic import resolve_authority_meeting
from threegpp.topics import TopicProfileService, TopicTermState
from threegpp.topics import rules as topic_rules
from threegpp.topics.service import _contains_phrase


REPORT_SOURCE_SCHEMA_VERSION = "1"
REPORT_SOURCE_RULESET_VERSION = "report-source-reading-v1"


class ReportSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str
    chair_note_snapshots: dict[str, str] = Field(default_factory=dict)
    max_passages_per_source: int = Field(default=80, ge=1, le=500)
    context_blocks: int = Field(default=3, ge=0, le=10)
    max_passage_chars: int = Field(default=12000, ge=100, le=100000)


class ReportSourceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: dict[str, Any]
    coverage: dict[str, Any]
    contribution_sources: list[dict[str, Any]]
    discussion_sources: list[dict[str, Any]]
    meeting_outcome_sources: list[dict[str, Any]]
    evidence_gaps: list[dict[str, Any]]
    # Never used to choose sources. No annotation workflow is invoked here.
    annotations_optional: list[dict[str, Any]] = Field(default_factory=list)
    audit: dict[str, Any]

    def presentation(self, *, audit: bool = False) -> dict[str, Any]:
        """Expose human locators by default; exact identities only on request."""
        value = self.model_dump(mode="json")
        if audit:
            return value

        def clean(item):
            if isinstance(item, dict):
                result = {key: clean(child) for key, child in item.items()
                          if key not in {"audit", "annotations_optional"}}
                if "reason" in result:
                    reason = result["reason"]
                    if any(word in reason.lower() for word in
                           ("checksum", "identity", "schema", "rules", "stale")):
                        result["reason"] = "source validation failed; inspect the source provenance before using it"
                    elif "unsupported_format" in reason:
                        result["reason"] = "source format is unsupported; content was not read"
                return result
            if isinstance(item, list):
                return [clean(child) for child in item]
            return item
        return clean(value)


def _text(block):
    if block.rows is not None:
        return "\n".join(" | ".join("" if c is None else str(c) for c in row)
                         for row in block.rows)
    return block.text or ""


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def _matches(text, term):
    # Reuse Chair Note's deterministic TDoc/title boundary repair; this does
    # not add a topic synonym or alter the stored literal passage.
    return _contains_phrase(TDOC_REFERENCE.sub(lambda m: m.group(0) + " ", text), term)


def _label(text):
    for rule in LABEL_RULES:
        match = rule.pattern.match(text)
        if match:
            return match.group("label") + (" " + match.group("ordinal")
                    if match.group("ordinal") else "")
    return None


def _locator(block):
    parts = [block.member_filename]
    if block.heading_path:
        parts.append(" / ".join(block.heading_path))
    if block.page_number is not None:
        parts.append(f"page {block.page_number}")
    if block.sheet_name:
        parts.append(f"sheet {block.sheet_name}")
    label = _label(_text(block))
    if label:
        parts.append(label)
    # This is the normalized reading order, never a fabricated DOCX paragraph/page.
    parts.append(f"normalized reading order {block.order}")
    return "; ".join(parts)


class ReportSourceService:
    """Build three independent channels without preparation or state writes."""

    def __init__(self, repository, data_root: Path | str):
        self.repository = repository
        self.root = Path(data_root)
        self.documents = DocumentService(repository, self.root)
        self.chairs = ChairNoteService(self.root)

    def build(self, request: ReportSourceRequest) -> ReportSourceBundle:
        profile = TopicProfileService(self.repository, self.root).load(request.profile_id)
        if profile.versions.get("terminology_ruleset") != topic_rules.TOPIC_TERMINOLOGY_RULESET_VERSION:
            raise ValueError("topic terminology definition is stale; explicit profile refresh required")
        terms = sorted({term.literal_text for term in profile.terms if term.state in {
            TopicTermState.USER_SEED, TopicTermState.EXACT_VARIANT,
            TopicTermState.ACCEPTED_SOURCE_TERM}}, key=lambda t: (t.casefold(), t))
        if not terms:
            raise ValueError("report requires accepted direct terminology")
        meetings = expand_numeric_range(profile.from_meeting, profile.to_meeting,
                                       self.repository.list_known_meetings(profile.working_group))
        snapshots = self._snapshot_selection(profile, request)
        gaps, records, discussions = [], {}, []
        provenance = {"profile_id": profile.profile_id,
                      "profile_checksum": profile.profile_checksum,
                      "request": request.model_dump(mode="json"),
                      "schema_version": REPORT_SOURCE_SCHEMA_VERSION,
                      "ruleset": REPORT_SOURCE_RULESET_VERSION,
                      "discussion_associations": []}
        # Reuse structural association rules; filter exact accepted phrases BEFORE
        # expensive historical joins. Do not inspect unrelated lexical-token hits.
        resolver = HistoricalMetadataResolver(self.repository)
        for meeting in meetings:
            selected = None
            for term in terms:
                self._metadata_inventory(profile.working_group, meeting, term, records)
            try:
                selection = self.chairs.select(profile.working_group, meeting, snapshots.get(meeting))
                selected = selection.selected_snapshot
                if selected is None or selected.normalized_path is None:
                    gaps.append({"source": f"{profile.working_group.value}#{meeting} discussion",
                                 "reason": selection.selection_basis if selected is None
                                 else "selected Chair Note has no readable normalized source"})
                    continue
                selected, blocks = self.chairs.load_blocks(profile.working_group, meeting, selected.snapshot_id)
                associations = {}
                for term in terms:
                    _, found, truncated = discussion_sections(selected, blocks, term)
                    for association in found:
                        if _matches(association.topic_anchor.literal_text, term):
                            associations[association.record_id] = association
                    if truncated:
                        gaps.append({"source": f"{meeting} discussion inventory",
                                     "reason": "bounded discussion sections were truncated",
                                     "sections_truncated": truncated})
                resolutions = {}
                for association in associations.values():
                    tdoc = association.reference.tdoc_id
                    if tdoc not in resolutions:
                        resolutions[tdoc] = resolver.resolve(profile.working_group, tdoc,
                                                           discussion_meeting=meeting)
                    resolution = resolutions[tdoc]
                    metadata = resolution.selected.metadata if resolution.selected else None
                    if metadata is None:
                        gaps.append({"source": tdoc,
                                     "reason": "discussion reference has unresolved or ambiguous metadata"})
                        continue
                    key = (metadata.meeting, metadata.tdoc_id)
                    item = records.setdefault(key, {"metadata": metadata, "associations": []})
                    item["associations"].append(association.model_dump(mode="json"))
                provenance["discussion_associations"].extend(
                    associations[key].model_dump(mode="json") for key in sorted(associations))
                passages, omitted = self._passages(blocks, terms, request,
                    lambda block: make_ref(selected, block).model_dump(mode="json"),
                    referenced_tdocs={key[1] for key in records})
                discussions.append({"meeting": meeting, "selected_chair_note": selected.raw_filename,
                    "snapshot_label": selected.snapshot_label_raw, "passages": passages,
                    "associated_tdocs": sorted(resolutions),
                    "context_referenced_tdocs": sorted({match.group(0).upper()
                        for p in passages for q in [p] + p["surrounding_context"]
                        for match in TDOC_REFERENCE.finditer(q["literal_text"])}),
                    "association_note": "Associated TDocs use exact-term structural matches; other literal references in surrounding context do not establish topic association.",
                    "source": self._source_paths(selected.raw_path, selected.normalized_path,
                                                 str(selected.artifact.official_url)),
                    "audit": {"snapshot_id": selected.snapshot_id,
                              "normalized_checksum": selected.normalized_checksum,
                              "normalization_id": selected.normalization_id}})
                self._omission_gap(gaps, f"{meeting} Chair Note", omitted)
            except (ValueError, OSError) as exc:
                gaps.append({"source": f"{meeting} Chair Note", "reason": str(exc)})
        contributions = []
        inventory = []
        for key in sorted(records, key=lambda k: (meeting_order_key(k[0]), k[1])):
            item = records[key]
            metadata = item["metadata"]
            inventory.append({"tdoc": metadata.tdoc_id, "organizations": metadata.organizations,
                              "meeting": metadata.meeting, "title": metadata.title})
            classification = classify_document_role(metadata)
            if classification.role is not DocumentRole.CONTRIBUTION:
                gaps.append({"source": metadata.tdoc_id,
                             "reason": "direct inventory item is not a company contribution source"})
                continue
            try:
                _, receipt, blocks = self.documents.read_source(metadata.tdoc_id,
                    metadata.working_group, metadata.meeting)
                source = self._document_source(metadata, receipt, blocks, terms, request,
                    all_passages=any(_contains_phrase(metadata.title or "", t) for t in terms))
                source["audit"]["discussion_associations"] = sorted(
                    {json.dumps(a, sort_keys=True) for a in item["associations"]})
                contributions.append(source)
                self._omission_gap(gaps, metadata.tdoc_id, source["passages_omitted"])
                self._receipt_gaps(gaps, receipt)
                if not source["passages"]:
                    gaps.append({"source": metadata.tdoc_id,
                                 "reason": "readable source has no exact direct-term passage in bounded scope"})
            except (ValueError, OSError) as exc:
                gaps.append({"source": metadata.tdoc_id, "reason": str(exc)})
        outcomes, examined = self._outcomes(profile.working_group, meetings, terms, request, gaps)
        for meeting in meetings:
            if not any(s["authority_meeting"] == meeting for s in outcomes):
                gaps.append({"source": f"{profile.working_group.value}#{meeting} meeting outcome",
                    "reason": "no readable explicitly labelled topic outcome found in available authoritative reports; absence is not a negative finding"})
        for source in contributions + discussions + outcomes:
            for passage in source["passages"]:
                for part in [passage] + passage["surrounding_context"]:
                    if part["characters_omitted"]:
                        gaps.append({"source": source.get("tdoc", source.get("selected_chair_note")),
                                     "locator": part["locator"], "reason": "source passage text was truncated",
                                     "characters_omitted": part["characters_omitted"]})
        gaps = [json.loads(s) for s in sorted({json.dumps(g, sort_keys=True, ensure_ascii=False) for g in gaps})]
        bundle = ReportSourceBundle(topic={"name": profile.topic_label,
            "working_group": profile.working_group.value, "meetings": meetings,
            "direct_terms": terms}, coverage={"direct_documents": len(records),
                "readable_contribution_documents": len(contributions),
                "selected_readable_chair_notes": len(discussions),
                "authoritative_reports_examined": examined,
                "documents": inventory,
                "limits": {"max_passages_per_source": request.max_passages_per_source,
                           "context_blocks": request.context_blocks,
                           "max_passage_chars": request.max_passage_chars},
                "limitations": ["Local prepared sources only; source completeness is not assumed.",
                    "Chair Note absence does not prove non-discussion.",
                    "No explicit outcome reference does not establish rejection.",
                    "Passages and context must be read before writing a technical claim."]},
            contribution_sources=contributions, discussion_sources=discussions,
            meeting_outcome_sources=outcomes, evidence_gaps=gaps, audit=provenance)
        bundle.audit["bundle_identity"] = _digest(bundle.model_dump(mode="json"))
        return bundle

    def _snapshot_selection(self, profile, request):
        choices = {}
        for term in profile.terms:
            for occurrence in term.occurrences:
                locator = occurrence.locator
                ref = locator.source_ref or {}
                if locator.source_type.value == "chair_note" and ref.get("snapshot_id"):
                    choices.setdefault(locator.meeting, set()).add(ref["snapshot_id"])
        result = dict(request.chair_note_snapshots)
        for meeting, values in choices.items():
            if meeting in result:
                continue
            if len(values) != 1:
                raise ValueError(f"profile contains ambiguous Chair Note snapshots for {meeting}; select explicitly")
            result[meeting] = next(iter(values))
        return result

    def _metadata_inventory(self, group, meeting, term, records):
        for metadata in self.repository.list_tdocs(group, meeting):
            if any(_contains_phrase(value or "", term) for value in
                   [metadata.title, metadata.abstract, metadata.agenda_item_description]):
                records.setdefault((metadata.meeting, metadata.tdoc_id),
                                   {"metadata": metadata, "associations": []})

    def _source_paths(self, raw, normalized, official):
        def resolve(value):
            if value is None:
                return None
            path = Path(value)
            if not path.is_absolute():
                path = (path if path.is_file() else self.root / path)
            return str(path.resolve()) if path.is_file() else None
        return {"raw_local": resolve(raw), "normalized_local": resolve(normalized),
                "official_url": official}

    def _passages(self, blocks, terms, request, make_reference, *, all_passages=False,
                  referenced_tdocs=frozenset()):
        eligible = [i for i, b in enumerate(blocks) if _text(b).strip() and
            (all_passages or any(_matches(" ".join(b.heading_path) + "\n" + _text(b), t)
                                 for t in terms)
             or any(m.group(0).upper() in referenced_tdocs for m in TDOC_REFERENCE.finditer(_text(b))))]
        passages = []
        for i in eligible[:request.max_passages_per_source]:
            block = blocks[i]
            context = []
            for j in range(max(0, i-request.context_blocks), min(len(blocks), i+request.context_blocks+1)):
                other = blocks[j]
                if (j != i and other.member_filename == block.member_filename
                        and other.heading_path == block.heading_path and _text(other).strip()):
                    context.append(self._passage(other, request, make_reference, relative=j-i))
            passage = self._passage(block, request, make_reference)
            passage["selection_basis"] = ("direct topic document" if all_passages else
                "accepted phrase" if any(_matches(" ".join(block.heading_path) + "\n" + _text(block), t)
                                         for t in terms) else "literal reference to a direct-inventory TDoc")
            passage["surrounding_context"] = context
            passage["context_window_blocks"] = request.context_blocks
            passages.append(passage)
        return passages, len(eligible) - len(passages)

    @staticmethod
    def _passage(block, request, make_reference, **extra):
        text = _text(block)
        return {"literal_text": text[:request.max_passage_chars],
                "source_native_label": _label(text), "locator": _locator(block),
                "member": block.member_filename, "heading": block.heading_path,
                "characters_omitted": max(0, len(text)-request.max_passage_chars),
                "audit": {"source_ref": make_reference(block)}, **extra}

    def _document_source(self, metadata, receipt, blocks, terms, request, *, all_passages=False):
        def reference(block):
            return EvidenceRef(tdoc_id=metadata.tdoc_id, working_group=metadata.working_group,
                meeting=metadata.meeting, member=block.member_filename, block_id=block.block_id,
                block_type=block.type, heading_path=block.heading_path,
                page=block.page_number, sheet=block.sheet_name).model_dump(mode="json")
        passages, omitted = self._passages(blocks, terms, request, reference, all_passages=all_passages)
        return {"tdoc": metadata.tdoc_id, "organizations": metadata.organizations,
                "meeting": metadata.meeting, "title": metadata.title,
                "passages": passages, "passages_omitted": omitted,
                "source": self._source_paths(receipt.raw.local_path, receipt.normalized_path,
                                             str(receipt.raw.source_url)),
                "audit": {"normalization_identity": receipt.normalization_identity.model_dump(mode="json"),
                          "normalized_checksum": receipt.normalized_checksum,
                          "raw_checksum": receipt.raw.sha256,
                          "metadata": metadata.model_dump(mode="json")}}

    def _outcomes(self, group, meetings, terms, request, gaps):
        result, examined = [], []
        rows = self.repository.connection.execute(
            "SELECT tdoc_id,meeting_number FROM tdoc_documents WHERE working_group=? ORDER BY meeting_number,tdoc_id",
            [group.value]).fetchall()
        for tdoc, discovery in rows:
            metadata = self.repository.get_tdoc(group, discovery, tdoc)
            if metadata is None:
                continue
            classification = classify_document_role(metadata)
            if classification.role is not DocumentRole.MEETING_REPORT:
                continue
            authority = resolve_authority_meeting(metadata, classification.role)
            if authority.authority_meeting is None:
                gaps.append({"source": tdoc, "reason": "authoritative report meeting is unresolved"})
                continue
            meeting = authority.authority_meeting.meeting_id
            if meeting not in meetings:
                continue
            examined.append({"tdoc": tdoc, "authority_meeting": meeting,
                             "discovery_meeting": discovery})
            try:
                _, receipt, blocks = self.documents.read_source(tdoc, group, discovery)
                allowed = _authoritative_blocks(receipt, classification,
                    [b.model_dump(mode="json") for b in blocks])
                allowed_ids = {(b["member_filename"], b["block_id"]) for b in allowed}
                blocks = [b for b in blocks if (b.member_filename, b.block_id) in allowed_ids]
                source = self._document_source(metadata, receipt, [], terms, request)
                outcome_passages = []
                for i, block in enumerate(blocks):
                    native_label = (_label(_text(block)) or "").casefold()
                    label = native_label.split(" ")[0]
                    if (label not in {"agreement", "agreements", "decision", "conclusion", "ffs"}
                            and native_label != "for further study"):
                        continue
                    statement_blocks = [block]
                    for other in blocks[i+1:i+1+request.context_blocks]:
                        if (other.member_filename != block.member_filename
                                or other.heading_path != block.heading_path
                                or other.type == "heading" or _label(_text(other))):
                            break
                        statement_blocks.append(other)
                    topic_text = " ".join(block.heading_path) + "\n" + "\n".join(map(_text, statement_blocks))
                    if not any(_contains_phrase(topic_text, t) for t in terms):
                        continue
                    # Anchor at the actual labelled outcome, never at a neighboring
                    # proposal merely because an Agreement occurs in its context.
                    packet = self._document_source(metadata, receipt, statement_blocks,
                                                   terms, request, all_passages=True)
                    outcome_passages.append(packet["passages"][0])
                source["passages"] = outcome_passages[:request.max_passages_per_source]
                source["passages_omitted"] = len(outcome_passages) - len(source["passages"])
                self._omission_gap(gaps, tdoc, source["passages_omitted"])
                self._receipt_gaps(gaps, receipt)
                if source["passages"]:
                    source.pop("organizations")
                    source["authority_meeting"] = meeting
                    source["discovery_meeting"] = discovery
                    source["audit"]["authority"] = authority.model_dump(mode="json")
                    result.append(source)
            except (ValueError, OSError) as exc:
                gaps.append({"source": tdoc, "reason": str(exc)})
        result.sort(key=lambda s: (meeting_order_key(s["authority_meeting"]), s["tdoc"]))
        return result, examined

    @staticmethod
    def _omission_gap(gaps, source, omitted):
        if omitted:
            gaps.append({"source": source, "reason": "passage output truncated", "passages_omitted": omitted})

    @staticmethod
    def _receipt_gaps(gaps, receipt):
        for member in receipt.members:
            if member.extraction_status.value not in {"parsed"}:
                gaps.append({"source": receipt.tdoc_id, "member": member.filename,
                             "reason": f"member content incomplete: {member.extraction_status.value}",
                             "details": member.warnings})
