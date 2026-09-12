from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.documents.models import (
    NORMALIZED_DOCUMENT_SCHEMA_VERSION, ExtractionStatus, NormalizationIdentity, TDocFetchPlan,
)
from threegpp.documents.parsers import parser_for
from threegpp.documents.service import FetchPlanner, _sha
from threegpp.models import TDocAvailability, TDocQuery
from threegpp.search import SEARCH_INDEX_SCHEMA_VERSION, TOKENIZER_VERSION, tokenize
from threegpp.evidence.rules import EVIDENCE_SCHEMA_VERSION, EXTRACTION_RULESET_VERSION
from threegpp.evidence.service import _metadata_identity

from . import rules
from .models import (
    AssociationBasis, CorpusExpansionItem, CoverageTDoc, DiscussionCoverageRequest,
    DiscussionCoverageState, DiscussionRecord, DiscussionSection, LocalBodyState,
    ReferenceResolutionState, TDocReference, TopicAnchor, TopicCorpusExpansionPlan,
    TopicDiscussionCoverage,
)
from .service import ChairNoteService, cell_text, make_ref


def _anchor(snapshot, block, text, tokens, row=None, cell=None):
    # Word-table extraction can concatenate the TDoc identifier and title.
    # Insert a lexical boundary for matching while retaining the exact source
    # text and character locator in the TopicAnchor.
    lexical_text = rules.TDOC_REFERENCE.sub(lambda match: match.group(0) + ' ', text)
    matched = tokens & set(tokenize(lexical_text))
    # The same extraction can concatenate an acronym at the end of a title
    # with an uppercase organization abbreviation (``HARQKT``).  Recover only
    # an explicit uppercase acronym at a non-word start; do not apply general
    # substring matching.
    for token in tokens - matched:
        acronym = token.upper()
        if len(acronym) >= 3 and re.search(
            rf'(?<![A-Za-z0-9]){re.escape(acronym)}(?=[A-Z])', lexical_text
        ):
            matched.add(token)
    terms = sorted(matched)
    if not terms:
        return None
    return TopicAnchor(source_ref=make_ref(snapshot, block, row=row, cell=cell, start=0, end=len(text)),
                       literal_text=text, matched_terms=terms)


def _regions(blocks):
    """Leaf heading runs; tables are separate rows; unheaded text is block-local."""
    run = []
    for block in blocks:
        boundary = (block.type == 'heading' or block.rows is not None
                    or run and block.member_filename != run[0].member_filename)
        if boundary and run:
            yield run, None
            run = []
        if block.rows is not None:
            for row in range(len(block.rows)):
                yield [block], row
        elif block.type == 'heading' or run:
            run.append(block)
        else:
            yield [block], None
    if run:
        yield run, None


def discussion_sections(snapshot, blocks, query):
    tokens = set(tokenize(query))
    sections, records, truncated_regions = [], [], 0
    for region, row_index in _regions(blocks):
        if len(region) > rules.MAX_SECTION_BLOCKS:
            truncated_regions += 1
        region = region[:rules.MAX_SECTION_BLOCKS]
        anchors, references = [], []
        for block in region:
            cells = ([(c, cell_text(v)) for c, v in enumerate(block.rows[row_index])]
                     if row_index is not None else [(None, block.text or '')])
            for cell, text in cells:
                anchor = _anchor(snapshot, block, text, tokens, row_index, cell)
                if anchor is not None:
                    anchors.append(anchor)
                for match in rules.TDOC_REFERENCE.finditer(text):
                    references.append(TDocReference(tdoc_id=match.group(0).upper(),
                        raw_reference=match.group(0), source_ref=make_ref(snapshot, block,
                            row=row_index, cell=cell, start=match.start(), end=match.end()),
                        rule_id='literal-tdoc-id', ruleset_version=rules.TDOC_REFERENCE_RULESET_VERSION))
        if not anchors:
            continue
        start = make_ref(snapshot, region[0], row=row_index, cell=0 if row_index is not None else None)
        end = make_ref(snapshot, region[-1], row=row_index,
                       cell=len(region[-1].rows[row_index])-1 if row_index is not None else None)
        section_id = 'section-' + rules.identity([start.model_dump(mode='json'), end.model_dump(mode='json'),
                                                 rules.DISCUSSION_SECTION_RULESET_VERSION])
        section = DiscussionSection(working_group=snapshot.artifact.working_group,
            meeting=snapshot.artifact.meeting, snapshot_id=snapshot.snapshot_id, section_id=section_id,
            heading_path=region[0].heading_path, topic_anchors=anchors, start_ref=start, end_ref=end,
            block_count=len(region), referenced_tdoc_ids=sorted({r.tdoc_id for r in references}))
        sections.append(section)
        for reference in references:
            anchor = next((a for a in anchors if a.source_ref.block_id == reference.source_ref.block_id), anchors[0])
            basis = (AssociationBasis.SAME_TABLE_ROW if row_index is not None else
                     AssociationBasis.SAME_BLOCK if anchor.source_ref.block_id == reference.source_ref.block_id
                     else AssociationBasis.SAME_DISCUSSION_SECTION)
            payload = [section_id, anchor.model_dump(mode='json'), reference.model_dump(mode='json'), basis.value]
            records.append(DiscussionRecord(record_id='discussion-' + rules.identity(payload),
                section_id=section_id, topic_anchor=anchor, reference=reference,
                association_basis=basis, rule_id='bounded-structural-association',
                ruleset_version=rules.DISCUSSION_SECTION_RULESET_VERSION))
    return sections, records, truncated_regions


class DiscussionCoverageService:
    """Offline positive coverage and plans; no acquisition dependency is instantiated."""

    def __init__(self, repository: MetadataRepository, root: Path):
        self.repository = repository
        self.root = Path(root)
        self.chair_notes = ChairNoteService(root)

    def build_coverage(self, request: DiscussionCoverageRequest) -> TopicDiscussionCoverage:
        selection = self.chair_notes.select(request.working_group, request.meeting, request.chair_note_snapshot)
        sections, records, truncated = [], [], 0
        limitations = [rules.COMPLETENESS_LIMITATION,
            'Matching uses lexical tokens and bounded structure, not semantic similarity. '
            'Every heading and table ends a prose region; tables associate only within the same row. '
            'Unheaded text/PDF pages associate only within one block.',
            f'Each prose section is capped at {rules.MAX_SECTION_BLOCKS} blocks. '
            'Results are limited per collection; diagnostics report totals before output limits.',
            'Metadata joins use known canonical-current records across meetings; archived-only metadata may remain unresolved.',
            'Chair Note text, including Agreement labels, is discussion context only and is not meeting SemanticEvidence.']
        selected = selection.selected_snapshot
        if selected is None:
            limitations.append(selection.selection_basis)
        elif selected.normalized_path is None:
            limitations.append('Selected snapshot is not normalized; explicit Chair Note fetch is required.')
        else:
            selected, blocks = self.chair_notes.load_blocks(request.working_group, request.meeting, selected.snapshot_id)
            sections, records, truncated = discussion_sections(selected, blocks, request.query)
            if selected.extraction_status not in {ExtractionStatus.PARSED, ExtractionStatus.PARTIALLY_PARSED}:
                limitations.append(f'Selected snapshot extraction status: {selected.extraction_status.value}.')
        all_referenced_tdocs = {record.reference.tdoc_id for record in records}
        output_records = records[:request.limit]
        if len(records) > request.limit:
            limitations.append(
                'Output limit truncated discussion associations; diagnostics retain the full occurrence and unique-ID counts.'
            )
        by_tdoc = defaultdict(list)
        for record in output_records:
            by_tdoc[record.reference.tdoc_id].append(record)
        confirmed, unresolved = [], []
        for tdoc_id in sorted(by_tdoc):
            candidate = self._resolve(tdoc_id, request, by_tdoc[tdoc_id])
            (confirmed if candidate.metadata is not None else unresolved).append(candidate)
        metadata = self.repository.list_tdocs(request.working_group, request.meeting)
        tokens = set(tokenize(request.query))
        relevant = []
        if request.include_metadata_candidates:
            for item in metadata:
                text = ' '.join(filter(None, [item.title, item.abstract, item.agenda_item_description]))
                if item.tdoc_id not in by_tdoc and tokens & set(tokenize(text)):
                    relevant.append(CoverageTDoc(tdoc_id=item.tdoc_id,
                        coverage_state=DiscussionCoverageState.METADATA_RELEVANT_ONLY,
                        resolution_state=ReferenceResolutionState.CURRENT_MEETING_METADATA,
                        metadata=item, availability=item.availability, local_state=self._local_state(item)))
        diagnostics = {
            'snapshots_available': len(selection.available_snapshots),
            'meeting_metadata_documents': len(metadata), 'matched_sections': len(sections),
            'explicit_reference_occurrences': len(records),
            'explicit_reference_occurrences_output': len(output_records),
            'explicit_unique_tdoc_ids': len(all_referenced_tdocs),
            'explicit_unique_tdoc_ids_output': len(by_tdoc),
            'chair_note_confirmed_resolved_tdocs': len(confirmed),
            'metadata_relevant_only_tdocs': len(relevant), 'unresolved_tdocs': len(unresolved),
            'confirmed_already_normalized': sum(c.local_state.normalized for c in confirmed),
            'confirmed_fetch_eligible': sum(c.availability is TDocAvailability.DOWNLOADABLE
                                          and not c.local_state.raw_verified for c in confirmed),
            'section_windows_truncated': truncated,
        }
        if any(len(items) > request.limit for items in [sections, confirmed, relevant, unresolved]):
            limitations.append('Output limit truncated one or more collections; absence is not negative evidence.')
        # Keep every section cited by a retained association, even beyond the display-only section cap.
        kept_ids = {a.section_id for c in (confirmed[:request.limit] + unresolved[:request.limit]) for a in c.associations}
        kept_sections = [s for i,s in enumerate(sections) if i < request.limit or s.section_id in kept_ids]
        coverage = TopicDiscussionCoverage(coverage_id='', request=request, selection=selection,
            matched_sections=kept_sections, chair_note_confirmed=confirmed[:request.limit],
            metadata_relevant_only=relevant[:request.limit], unresolved_references=unresolved[:request.limit],
            diagnostics=diagnostics, versions={
                'schema': rules.CHAIR_NOTE_SCHEMA_VERSION,
                'discovery': rules.CHAIR_NOTE_DISCOVERY_RULESET_VERSION,
                'snapshot': rules.CHAIR_NOTE_SNAPSHOT_RULESET_VERSION,
                'discussion': rules.DISCUSSION_SECTION_RULESET_VERSION,
                'tdoc_reference': rules.TDOC_REFERENCE_RULESET_VERSION,
                'tokenizer': TOKENIZER_VERSION}, limitations=limitations)
        coverage.coverage_id = rules.identity(_logical(coverage.model_dump(mode='json')))
        return coverage

    def _resolve(self, tdoc_id, request, associations):
        candidates = self.repository.query_tdocs(TDocQuery(tdoc_id=tdoc_id))
        # A duplicate identity is ambiguous even if one candidate is in the Chair Note meeting.
        metadata = candidates[0] if len(candidates) == 1 else None
        state = ReferenceResolutionState.UNRESOLVED
        if len(candidates) > 1:
            state = ReferenceResolutionState.AMBIGUOUS
        elif metadata is not None:
            current = (metadata.working_group, metadata.meeting) == (request.working_group, request.meeting)
            state = (ReferenceResolutionState.CURRENT_MEETING_METADATA if current
                     else ReferenceResolutionState.OTHER_KNOWN_METADATA)
        return CoverageTDoc(tdoc_id=tdoc_id, coverage_state=DiscussionCoverageState.CHAIR_NOTE_CONFIRMED,
            resolution_state=state, metadata=metadata, metadata_candidates=candidates if len(candidates)>1 else [],
            availability=metadata.availability if metadata else None,
            local_state=self._local_state(metadata) if metadata else LocalBodyState(), associations=associations)

    def _local_state(self, metadata):
        receipt = self.repository.get_document_receipt(metadata.tdoc_id, metadata.working_group, metadata.meeting)
        if receipt is None:
            return LocalBodyState()
        raw = _runtime_path(self.root, receipt.raw.local_path)
        raw_present = raw.is_file()
        source_matches = metadata.source_url is None or receipt.raw.source_url == metadata.source_url
        raw_verified = raw_present and source_matches and _sha(raw) == receipt.raw.sha256
        identity = NormalizationIdentity(raw_sha256=receipt.raw.sha256,
            parser_members={m.filename: f'{p.name}@{p.version}' if (p := parser_for(m.filename)) else 'unsupported'
                            for m in receipt.members},
            normalized_schema_version=NORMALIZED_DOCUMENT_SCHEMA_VERSION)
        normalized = bool(receipt.normalized_path and (self.root/receipt.normalized_path).is_file()
                          and _sha(self.root/receipt.normalized_path) == receipt.normalized_checksum
                          and raw_verified and receipt.normalization_identity == identity
                          and receipt.extraction_status in {ExtractionStatus.PARSED, ExtractionStatus.PARTIALLY_PARSED})
        key = [metadata.tdoc_id, metadata.working_group.value, metadata.meeting]
        statuses = {}
        for table, field in [('search_index_state','indexed_status'), ('semantic_evidence_state','semantic_status')]:
            extra = ('index_schema_version,tokenizer_version' if field == 'indexed_status' else
                     'evidence_schema_version,ruleset_version,metadata_identity_json,evidence_path,evidence_checksum')
            row = self.repository.connection.execute(
                f'SELECT status,normalized_checksum,{extra} FROM {table} '
                'WHERE tdoc_id=? AND working_group=? AND meeting_number=?',key).fetchone()
            valid = bool(row and normalized and row[1] == receipt.normalized_checksum)
            if row and field == 'indexed_status':
                valid &= tuple(row[2:4]) == (SEARCH_INDEX_SCHEMA_VERSION, TOKENIZER_VERSION)
            elif row:
                valid &= tuple(row[2:5]) == (EVIDENCE_SCHEMA_VERSION, EXTRACTION_RULESET_VERSION, _metadata_identity(metadata))
                valid &= bool(row[5] and (self.root/row[5]).is_file() and _sha(self.root/row[5]) == row[6])
            statuses[field] = row[0] if valid else ('STALE' if row else None)
        return LocalBodyState(raw_present=raw_present, raw_verified=raw_verified, normalized=normalized,
                              extraction_status=receipt.extraction_status.value, **statuses)

    def plan_topic_corpus(self, request: DiscussionCoverageRequest) -> TopicCorpusExpansionPlan:
        coverage = self.build_coverage(request)
        items = []
        for candidate in coverage.chair_note_confirmed + coverage.unresolved_references + coverage.metadata_relevant_only:
            local = candidate.local_state
            eligible = False
            needed = None
            if candidate.metadata is None:
                reason = 'unresolved or ambiguous metadata; no URL or meeting assumed'
            elif candidate.coverage_state is DiscussionCoverageState.METADATA_RELEVANT_ONLY:
                reason = 'metadata relevance only; not selected for Chair-note-confirmed expansion'
            elif local.raw_present and not local.raw_verified:
                needed, reason = False, 'raw checksum conflict; repair provenance explicitly before any acquisition'
            elif local.raw_verified:
                needed = False
                reason = 'reuse local normalized body' if local.normalized else 'reuse local raw body; normalization may be needed'
            elif candidate.availability is TDocAvailability.DOWNLOADABLE:
                needed, eligible, reason = True, True, 'Chair-note-confirmed and officially downloadable; explicit fetch required'
            elif candidate.availability is TDocAvailability.LISTED_ONLY:
                reason = 'listed-only metadata; no body URL is known'
            else:
                reason = 'unknown body availability; no automatic fetch'
            items.append(CorpusExpansionItem(candidate=candidate, fetch_needed=needed,
                                            fetch_eligible=eligible, fetch_reason=reason))
        items.sort(key=lambda i: (i.candidate.tdoc_id,i.candidate.coverage_state.value))
        plan = TopicCorpusExpansionPlan(schema_version=rules.CORPUS_EXPANSION_SCHEMA_VERSION,
            plan_id='', coverage=coverage, items=items,
            automatic_batch_limit=FetchPlanner(self.repository).batch_limit)
        plan.plan_id = rules.identity(_logical(plan.model_dump(mode='json')))
        return plan

    def compile_fetch_plan(self, plan: TopicCorpusExpansionPlan, tdoc_ids: list[str]) -> TDocFetchPlan:
        """Compile an explicit bounded selection, without downloading any TDoc."""
        current = self.plan_topic_corpus(plan.coverage.request)
        if current.plan_id != plan.plan_id:
            raise ValueError('stale corpus expansion plan; rebuild before selecting TDocs')
        selected = set(tdoc_ids)
        if not selected or len(selected) > current.automatic_batch_limit:
            raise ValueError(f'select 1..{current.automatic_batch_limit} TDocs per fetch plan')
        by_id = {item.candidate.tdoc_id: item for item in current.items}
        identities = []
        for tdoc_id in sorted(selected):
            item = by_id.get(tdoc_id)
            if item is None or not item.fetch_eligible:
                raise ValueError(f'{tdoc_id} is not fetch eligible in this expansion plan')
            metadata = item.candidate.metadata
            identities.append((metadata.working_group, metadata.meeting, metadata.tdoc_id))
        return FetchPlanner(self.repository).explicit(identities,
            reason=f'Chair Note coverage {current.coverage.coverage_id}; expansion plan {current.plan_id}')


def _logical(value):
    if isinstance(value, dict):
        return {k:_logical(v) for k,v in value.items() if k not in {'discovered_at','retrieved_at'}}
    if isinstance(value, list):
        return [_logical(v) for v in value]
    return value


def _runtime_path(root: Path, stored_path) -> Path:
    path = Path(stored_path)
    if path.is_absolute():
        return path
    candidates = (path, root / path, root.parent / path)
    return next((candidate for candidate in candidates if candidate.is_file()), path)
