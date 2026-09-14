from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from threegpp.chair_notes.service import ChairNoteService, cell_text, make_ref
from threegpp.chair_notes import rules as chair_rules
from threegpp.documents.service import _atomic, _sha
from threegpp.evidence import classify_document_role
from threegpp.historical import HistoricalCoverageRequest, HistoricalCoverageService
from threegpp.historical import rules as historical_rules
from threegpp.models import DocumentRole, TDocQuery, WorkingGroup
from threegpp.study_view import TDocStudyService

from . import rules
from .models import (
    TopicBootstrapRequest, TopicBootstrapResult, TopicCompanyInventory,
    TopicInventoryAssociation, TopicInventoryTDoc, TopicProfileDecision,
    TopicProfileInventory, TopicQueryGroup, TopicSourceCoverage,
    TopicSourceType, TopicTerm, TopicTermLocator, TopicTermOccurrence,
    TopicTerminologyProfile, TopicTermState,
)


LIMITATIONS = [
    "Source-term co-occurrence is retrieval evidence, not semantic equivalence.",
    "Metadata-title relevance is terminology evidence and does not establish Chair Note discussion.",
    "Absence from selected prepared sources is not evidence that a topic or term does not exist.",
    "Topic bootstrap reads local prepared sources only and performs zero contribution-body downloads.",
]


@dataclass(frozen=True)
class _Passage:
    text: str
    source_type: TopicSourceType
    working_group: WorkingGroup
    meeting: str
    source_identity: str
    source_file: str | None = None
    member: str | None = None
    block_id: str | None = None
    row_index: int | None = None
    cell_index: int | None = None
    associated_tdoc_id: str | None = None
    associated_tdoc_ids: tuple[str, ...] = ()
    organizations: tuple[str, ...] = ()
    source_ref: dict | None = None


class TopicBootstrapService:
    """Discover literal source terminology from already-prepared official material."""

    def __init__(self, repository, data_root: Path | str):
        self.repository = repository
        self.data_root = Path(data_root)
        self.chairs = ChairNoteService(self.data_root)

    def bootstrap(self, request: TopicBootstrapRequest) -> TopicBootstrapResult:
        known = self.repository.list_known_meetings(request.working_group)
        meetings = historical_rules.expand_numeric_range(
            request.from_meeting, request.to_meeting, known)
        if len(meetings) > request.max_meetings:
            raise ValueError(f"meeting range contains {len(meetings)} meetings; maximum is {request.max_meetings}")
        passages, coverage = self._passages(request, meetings)
        terms = self._terms(request, passages)
        result = TopicBootstrapResult(
            bootstrap_id="", request=request, terms=terms, source_coverage=coverage,
            limitations=LIMITATIONS + ([
                "PARTIAL_SOURCE_COVERAGE: one or more requested source classes were missing or unusable."
            ] if coverage.completeness != "complete_for_selected_sources" else []),
            versions={
                "bootstrap_schema": rules.TOPIC_BOOTSTRAP_SCHEMA_VERSION,
                "terminology_ruleset": rules.TOPIC_TERMINOLOGY_RULESET_VERSION,
                "tokenizer": __import__("threegpp.search", fromlist=["TOKENIZER_VERSION"]).TOKENIZER_VERSION,
            },
        )
        result.bootstrap_id = rules.identity(
            rules.logical(result.model_dump(mode="json")), "topic-bootstrap-")
        return result

    def _passages(self, request, meetings):
        passages = []
        chair_available, chair_missing, chair_unusable = [], [], []
        metadata_available, metadata_missing = [], []
        local_count = 0
        local_seen = set()
        for meeting in meetings:
            if request.source_policy.selected_chair_notes:
                selection = self.chairs.select(
                    request.working_group, meeting,
                    request.source_policy.chair_note_snapshots.get(meeting))
                selected = selection.selected_snapshot
                if selected is None:
                    (chair_unusable if selection.available_snapshots else chair_missing).append(meeting)
                elif not selected.normalized_path:
                    chair_unusable.append(meeting)
                else:
                    try:
                        snapshot, blocks = self.chairs.load_blocks(
                            request.working_group, meeting, selected.snapshot_id)
                    except (ValueError, OSError):
                        chair_unusable.append(meeting)
                    else:
                        chair_available.append(meeting)
                        for block in blocks:
                            cells = ([(row, cell, cell_text(value))
                                      for row, values in enumerate(block.rows)
                                      for cell, value in enumerate(values)]
                                     if block.rows is not None else [(None, None, block.text or "")])
                            for row, cell, text in cells:
                                if not text:
                                    continue
                                ref = make_ref(snapshot, block, row=row, cell=cell,
                                               start=0, end=len(text))
                                references = sorted({match.group(0).upper()
                                    for match in chair_rules.TDOC_REFERENCE.finditer(text)})
                                organizations = set()
                                for tdoc_id in references:
                                    candidates = self.repository.query_tdocs(TDocQuery(tdoc_id=tdoc_id))
                                    if len(candidates) == 1:
                                        organizations.update(candidates[0].organizations)
                                passages.append(_Passage(text=text,
                                    source_type=TopicSourceType.CHAIR_NOTE,
                                    working_group=request.working_group, meeting=meeting,
                                    source_identity=snapshot.snapshot_id,
                                    source_file=snapshot.raw_filename,
                                    member=block.member_filename, block_id=block.block_id,
                                    row_index=row, cell_index=cell,
                                    associated_tdoc_id=references[0] if len(references) == 1 else None,
                                    associated_tdoc_ids=tuple(references),
                                    organizations=tuple(sorted(
                                        organizations, key=lambda value: (value.casefold(), value))),
                                    source_ref=ref.model_dump(mode="json")))
            metadata = self._meeting_metadata(request.working_group, meeting)
            if request.source_policy.metadata_titles:
                if metadata:
                    metadata_available.append(meeting)
                else:
                    metadata_missing.append(meeting)
                for item, source_identity in metadata:
                    if item.title:
                        passages.append(_Passage(text=item.title,
                            source_type=TopicSourceType.METADATA_TITLE,
                            working_group=request.working_group, meeting=meeting,
                            source_identity=source_identity,
                            source_file=str(item.metadata_source_url) if item.metadata_source_url else None,
                            associated_tdoc_id=item.tdoc_id,
                            associated_tdoc_ids=(item.tdoc_id,),
                            organizations=tuple(item.organizations),
                            source_ref={"tdoc_id": item.tdoc_id,
                                "metadata_source_kind": item.metadata_source_kind.value,
                                "metadata_source_url": str(item.metadata_source_url) if item.metadata_source_url else None,
                                "metadata_source_checksum": item.metadata_source_checksum,
                                "field": "title"}))
            if request.source_policy.local_documents:
                for item, _ in metadata:
                    receipt = self.repository.get_document_receipt(
                        item.tdoc_id, item.working_group, item.meeting)
                    if not receipt or not receipt.normalized_path or not receipt.normalized_checksum:
                        continue
                    path = self.data_root / receipt.normalized_path
                    if not path.is_file() or _sha(path) != receipt.normalized_checksum:
                        continue
                    role = classify_document_role(item).role
                    if role not in {DocumentRole.CONTRIBUTION, DocumentRole.MEETING_REPORT}:
                        continue
                    local_key = (item.working_group.value, item.meeting, item.tdoc_id,
                                 receipt.normalized_checksum)
                    if local_key in local_seen:
                        continue
                    local_seen.add(local_key)
                    local_count += 1
                    source_type = (TopicSourceType.CONTRIBUTION_CONTENT
                                   if role is DocumentRole.CONTRIBUTION
                                   else TopicSourceType.MEETING_OUTCOME)
                    for line in gzip.decompress(path.read_bytes()).decode().splitlines():
                        block = json.loads(line)
                        cells = ([(row, cell, cell_text(value))
                                  for row, values in enumerate(block.get("rows") or [])
                                  for cell, value in enumerate(values)]
                                 if block.get("rows") is not None
                                 else [(None, None, block.get("text") or "")])
                        for row, cell, text in cells:
                            if text:
                                passages.append(_Passage(text=text, source_type=source_type,
                                    working_group=request.working_group, meeting=meeting,
                                    source_identity=receipt.normalized_checksum,
                                    source_file=str(receipt.normalized_path),
                                    member=block.get("member_filename"),
                                    block_id=block.get("block_id"), row_index=row, cell_index=cell,
                                    associated_tdoc_id=item.tdoc_id,
                                    associated_tdoc_ids=(item.tdoc_id,),
                                    organizations=tuple(item.organizations),
                                    source_ref={"normalization_identity": (
                                        receipt.normalization_identity.model_dump(mode="json")
                                        if receipt.normalization_identity else None),
                                        "normalized_checksum": receipt.normalized_checksum,
                                        "member": block.get("member_filename"),
                                        "block_id": block.get("block_id"),
                                        "row_index": row, "cell_index": cell}))
        completeness = ("complete_for_selected_sources"
                        if not chair_missing and not chair_unusable and not metadata_missing
                        else "partial_source_coverage")
        coverage = TopicSourceCoverage(meetings_requested=meetings,
            chair_note_meetings_available=chair_available,
            chair_note_meetings_missing=chair_missing,
            chair_note_meetings_unusable=chair_unusable,
            metadata_meetings_available=metadata_available,
            metadata_meetings_missing=metadata_missing,
            local_documents_inspected=local_count, completeness=completeness)
        source_rank = {TopicSourceType.CHAIR_NOTE: 0, TopicSourceType.METADATA_TITLE: 1,
                       TopicSourceType.CONTRIBUTION_CONTENT: 2,
                       TopicSourceType.MEETING_OUTCOME: 3}
        passages.sort(key=lambda p: (historical_rules.meeting_order_key(p.meeting),
            source_rank[p.source_type], p.source_identity, p.member or "", p.block_id or "",
            p.row_index if p.row_index is not None else -1,
            p.cell_index if p.cell_index is not None else -1, p.text))
        return passages, coverage

    def _meeting_metadata(self, group, meeting):
        values = {}
        for item in self.repository.list_tdocs(group, meeting):
            source = item.metadata_source_checksum or rules.identity(
                item.model_dump(mode="json"), "metadata-")
            values[(item.tdoc_id, item.title or "", source)] = (item, source)
        for snapshot in self.repository.list_tdoc_list_snapshots(group, meeting):
            source = snapshot.checksum or rules.identity(str(snapshot.source_url), "metadata-")
            for item in snapshot.tdocs:
                values[(item.tdoc_id, item.title or "", source)] = (item, source)
        return [values[key] for key in sorted(values)]

    def _terms(self, request, passages):
        records: dict[tuple[str, TopicTermState], dict] = {}
        all_seeds = list(request.user_terms)
        for literal in request.user_terms:
            self._record(records, literal, TopicTermState.USER_SEED, [literal],
                         "wording supplied by the researcher")
            for variant in rules.exact_variants(literal):
                if variant != literal:
                    self._record(records, variant, TopicTermState.EXACT_VARIANT, [literal],
                                 "deterministic case/hyphen/space formatting variant")
        for literal in request.accepted_source_terms:
            self._record(records, literal, TopicTermState.ACCEPTED_SOURCE_TERM, [],
                         "explicitly accepted in the bootstrap request")
        for literal in request.related_terms:
            self._record(records, literal, TopicTermState.RELATED_ONLY, [],
                         "explicitly supplied as diagnostic-only terminology")

        atoms = rules.seed_atoms(all_seeds)
        exact_keys = {rules.decision_key(value) for seed in all_seeds
                      for value in rules.exact_variants(seed)}
        for passage in passages:
            passage_atoms = {part for token in rules.word_spans(passage.text)
                             for part in rules.normalized_term(token[0]).split()}
            if not atoms & passage_atoms:
                continue
            for seed in all_seeds:
                for literal, start, end in self._exact_occurrences(passage.text, seed):
                    key = rules.decision_key(literal)
                    eligible = [value for value in records.values()
                                if value["state"] in {TopicTermState.USER_SEED, TopicTermState.EXACT_VARIANT}
                                and rules.decision_key(value["literal_text"]) == key]
                    target = next((value for value in eligible
                                   if value["literal_text"].casefold() == literal.casefold()),
                                  eligible[0] if eligible else None)
                    if target is not None:
                        target["occurrences"].append(self._occurrence(passage, literal, start, end))
            for segment_match in rules.SEGMENT.finditer(passage.text):
                raw_segment = segment_match.group(0)
                leading = len(raw_segment) - len(raw_segment.lstrip())
                segment = raw_segment.strip()
                segment_base = segment_match.start() + leading
                if not segment:
                    continue
                spans = rules.word_spans(segment)
                matched = [index for index, (word, _, _) in enumerate(spans)
                           if atoms & set(rules.normalized_term(word).split())]
                if matched:
                    start_i, end_i = min(matched), min(len(spans), max(matched) + 2)
                    if end_i - start_i < 2 and end_i < len(spans):
                        end_i += 1
                    if end_i - start_i > rules.MAX_CANDIDATE_TOKENS:
                        end_i = start_i + rules.MAX_CANDIDATE_TOKENS
                    if end_i > start_i:
                        start = segment_base + spans[start_i][1]
                        end = segment_base + spans[end_i - 1][2]
                        literal = passage.text[start:end]
                        cleaned = rules.strip_joined_organization_suffix(
                            literal, passage.organizations)
                        end -= len(literal) - len(cleaned)
                        literal = cleaned
                        if len(rules.normalized_term(literal).split()) >= 2 and rules.decision_key(literal) not in exact_keys:
                            target = self._record(records, literal, TopicTermState.SOURCE_CANDIDATE,
                                all_seeds, "observed token window around a seed-token match")
                            target["occurrences"].append(self._occurrence(passage, literal, start, end))
                else:
                    clean_spans = [(word, start, end) for word, start, end in spans
                                   if not re.fullmatch(r"R[12]-\d+", word, re.I)]
                    if 2 <= len(clean_spans) <= rules.MAX_CANDIDATE_TOKENS:
                        start = segment_base + clean_spans[0][1]
                        end = segment_base + clean_spans[-1][2]
                        literal = passage.text[start:end]
                        target = self._record(records, literal, TopicTermState.RELATED_ONLY,
                            all_seeds, "adjacent bounded source segment; diagnostic only")
                        target["occurrences"].append(self._occurrence(passage, literal, start, end))

        finalized = [self._finalize(value) for value in records.values()]
        state_rank = {TopicTermState.USER_SEED: 0, TopicTermState.EXACT_VARIANT: 1,
                      TopicTermState.ACCEPTED_SOURCE_TERM: 2,
                      TopicTermState.SOURCE_CANDIDATE: 3,
                      TopicTermState.RELATED_ONLY: 4, TopicTermState.REJECTED: 5}
        finalized.sort(key=lambda item: (state_rank[item.state],
            -item.retrieval_support_score, item.normalized_term, item.literal_text))
        candidates = [item for item in finalized if item.state in {
            TopicTermState.SOURCE_CANDIDATE, TopicTermState.RELATED_ONLY}]
        keep = set(item.term_id for item in candidates[:request.candidate_limit])
        return [item for item in finalized if item.state not in {
            TopicTermState.SOURCE_CANDIDATE, TopicTermState.RELATED_ONLY} or item.term_id in keep]

    @staticmethod
    def _record(records, literal, state, seeds, basis):
        key = (rules.decision_key(literal), state)
        if key not in records:
            records[key] = {"literal_text": literal, "state": state,
                            "seed_terms": sorted(
                                set(seeds), key=lambda value: (value.casefold(), value)),
                            "occurrences": [], "decision_basis": basis}
        return records[key]

    @staticmethod
    def _exact_occurrences(text, seed):
        words = [re.escape(value) for value in re.findall(r"[A-Za-z0-9]+", seed)]
        if not words:
            return []
        pattern = re.compile(r"(?<![A-Za-z0-9])" + r"[-\s]+".join(words)
                             + r"(?![A-Za-z0-9])", re.I)
        return [(match.group(0), match.start(), match.end()) for match in pattern.finditer(text)]

    @staticmethod
    def _occurrence(passage, literal, start, end):
        source_ref = dict(passage.source_ref) if passage.source_ref else None
        if source_ref is not None:
            source_ref["char_start"] = start
            source_ref["char_end"] = end
        locator = TopicTermLocator(source_type=passage.source_type,
            working_group=passage.working_group, meeting=passage.meeting,
            source_identity=passage.source_identity, source_file=passage.source_file,
            member=passage.member, block_id=passage.block_id,
            row_index=passage.row_index, cell_index=passage.cell_index,
            char_start=start, char_end=end, associated_tdoc_id=passage.associated_tdoc_id,
            associated_tdoc_ids=list(passage.associated_tdoc_ids),
            associated_organizations=list(passage.organizations),
            source_ref=source_ref)
        return TopicTermOccurrence(literal_text=literal, locator=locator)

    @staticmethod
    def _finalize(value):
        unique = {}
        for occurrence in value["occurrences"]:
            key = json.dumps(occurrence.model_dump(mode="json"), sort_keys=True,
                             separators=(",", ":"), ensure_ascii=False)
            unique[key] = occurrence
        occurrences = [unique[key] for key in sorted(unique)]
        meetings = sorted({item.locator.meeting for item in occurrences},
                          key=historical_rules.meeting_order_key)
        tdocs = sorted({tdoc_id for item in occurrences
                        for tdoc_id in item.locator.associated_tdoc_ids}
                       | {item.locator.associated_tdoc_id for item in occurrences
                          if item.locator.associated_tdoc_id})
        organizations = sorted({organization for item in occurrences
            for organization in item.locator.associated_organizations},
            key=lambda value: (value.casefold(), value))
        chair = sum(item.locator.source_type is TopicSourceType.CHAIR_NOTE for item in occurrences)
        titles = sum(item.locator.source_type is TopicSourceType.METADATA_TITLE for item in occurrences)
        score = len(occurrences) + 3 * len(meetings) + 2 * len(tdocs) + 2 * chair + titles
        term_id = rules.identity({"literal": rules.decision_key(value["literal_text"]),
                                  "state": value["state"].value,
                                  "occurrences": [item.model_dump(mode="json") for item in occurrences]},
                                 "topic-term-")
        return TopicTerm(term_id=term_id, literal_text=value["literal_text"],
            normalized_term=rules.normalized_term(value["literal_text"]), state=value["state"],
            seed_terms=value["seed_terms"], occurrences=occurrences,
            source_occurrence_count=len(occurrences), meetings=meetings,
            meeting_occurrence_counts={meeting: sum(
                item.locator.meeting == meeting for item in occurrences) for meeting in meetings},
            source_type_occurrence_counts={source_type.value: sum(
                item.locator.source_type is source_type for item in occurrences)
                for source_type in TopicSourceType
                if any(item.locator.source_type is source_type for item in occurrences)},
            candidate_tdoc_ids=tdocs, candidate_organizations=organizations,
            earliest_observed_meeting=meetings[0] if meetings else None,
            latest_observed_meeting=meetings[-1] if meetings else None,
            retrieval_support_score=score, decision_basis=value["decision_basis"])


class TopicProfileService:
    """Persist deterministic terminology decisions and build offline inventories."""

    def __init__(self, repository, data_root: Path | str):
        self.repository = repository
        self.data_root = Path(data_root)
        self.bootstrapper = TopicBootstrapService(repository, data_root)

    def create(self, result: TopicBootstrapResult) -> TopicTerminologyProfile:
        return self._profile(result, result.terms, None)

    def bootstrap_and_persist(self, request: TopicBootstrapRequest):
        result = self.bootstrapper.bootstrap(request)
        profile = self.create(result)
        self.persist(profile)
        return result, profile

    def update(self, decision: TopicProfileDecision) -> TopicTerminologyProfile:
        old = self.load(decision.profile_id)
        decisions = {}
        for state, values in ((TopicTermState.ACCEPTED_SOURCE_TERM, decision.accept),
                              (TopicTermState.RELATED_ONLY, decision.related),
                              (TopicTermState.REJECTED, decision.reject)):
            for value in values:
                decisions[rules.decision_key(value)] = (state, value)
        terms = []
        found = set()
        for term in old.terms:
            value = decisions.get(rules.decision_key(term.literal_text))
            if value:
                state, literal = value
                payload = term.model_dump(mode="json")
                payload.update({"state": state, "literal_text": literal,
                    "normalized_term": rules.normalized_term(literal),
                    "decision_basis": "explicit researcher profile decision"})
                payload["term_id"] = rules.identity({
                    "literal": rules.decision_key(literal), "state": state.value,
                    "occurrences": payload["occurrences"]}, "topic-term-")
                term = TopicTerm.model_validate(payload)
                found.add(rules.decision_key(literal))
            terms.append(term)
        missing = set(decisions) - found
        if missing:
            raise ValueError("profile decision term is not present in the source-derived profile: "
                             + ", ".join(sorted(missing)))
        result = TopicBootstrapResult(bootstrap_id=old.source_bootstrap_id,
            request=TopicBootstrapRequest(working_group=old.working_group,
                from_meeting=old.from_meeting, to_meeting=old.to_meeting,
                user_terms=old.user_terms, topic_label=old.topic_label),
            terms=terms, source_coverage=TopicSourceCoverage(
                meetings_requested=[], completeness="profile_revision"),
            limitations=[], versions=old.versions)
        profile = self._profile(result, terms, old.profile_id)
        self.persist(profile)
        return profile

    def _profile(self, result, terms, parent):
        source_ids = sorted({occurrence.locator.source_identity for term in terms
                             for occurrence in term.occurrences})
        logical = {"schema_version": rules.TOPIC_PROFILE_SCHEMA_VERSION,
            "working_group": result.request.working_group.value,
            "topic_label": result.request.topic_label or result.request.user_terms[0],
            "from_meeting": result.request.from_meeting,
            "to_meeting": result.request.to_meeting,
            "user_terms": result.request.user_terms,
            "terms": [term.model_dump(mode="json") for term in terms],
            "source_bootstrap_id": result.bootstrap_id,
            "source_identities": source_ids, "parent_profile_id": parent,
            "versions": {"profile_schema": rules.TOPIC_PROFILE_SCHEMA_VERSION,
                         "terminology_ruleset": rules.TOPIC_TERMINOLOGY_RULESET_VERSION}}
        checksum = hashlib.sha256(json.dumps(logical, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        return TopicTerminologyProfile(**logical, profile_checksum=checksum,
            profile_id="topic-profile-" + checksum)

    def persist(self, profile):
        path = self.profile_path(profile)
        payload = (json.dumps(profile.model_dump(mode="json"), sort_keys=True,
                    indent=2, ensure_ascii=False) + "\n").encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic(path, payload)
        return path

    def profile_path(self, profile):
        return (self.data_root / "derived" / "topics" / profile.working_group.value.lower()
                / profile.profile_id / "topic-profile.json")

    def load(self, profile_id):
        if not re.fullmatch(r"topic-profile-[0-9a-f]{64}", profile_id):
            raise ValueError("invalid topic profile ID")
        paths = sorted((self.data_root / "derived" / "topics").glob(
            f"*/{profile_id}/topic-profile.json"))
        if len(paths) != 1:
            raise ValueError("topic profile was not found or is ambiguous")
        profile = TopicTerminologyProfile.model_validate_json(paths[0].read_text())
        expected = self._profile(TopicBootstrapResult(bootstrap_id=profile.source_bootstrap_id,
            request=TopicBootstrapRequest(working_group=profile.working_group,
                from_meeting=profile.from_meeting, to_meeting=profile.to_meeting,
                user_terms=profile.user_terms, topic_label=profile.topic_label), terms=profile.terms,
            source_coverage=TopicSourceCoverage(meetings_requested=[], completeness="load"),
            limitations=[], versions=profile.versions), profile.terms, profile.parent_profile_id)
        if (expected.profile_id != profile.profile_id
                or expected.profile_checksum != profile.profile_checksum):
            raise ValueError("stale or checksum-conflicting topic profile")
        return profile

    def inventory(self, profile, *, from_meeting=None, to_meeting=None,
                  chair_note_snapshots=None, limit=100):
        start = historical_rules.normalize_historical_meeting(
            from_meeting or profile.from_meeting, profile.working_group)[0]
        end = historical_rules.normalize_historical_meeting(
            to_meeting or profile.to_meeting, profile.working_group)[0]
        direct = []
        priority = {TopicTermState.USER_SEED: TopicQueryGroup.USER_SEED,
                    TopicTermState.EXACT_VARIANT: TopicQueryGroup.EXACT_VARIANT,
                    TopicTermState.ACCEPTED_SOURCE_TERM: TopicQueryGroup.ACCEPTED_SOURCE_TERM}
        for term in profile.terms:
            if term.state not in priority:
                continue
            direct.append((term.literal_text, priority[term.state]))
        related = sorted({term.literal_text for term in profile.terms
                          if term.state is TopicTermState.RELATED_ONLY},
                         key=lambda value: (value.casefold(), value))
        records = {}
        term_found = set()
        completeness = []
        for query, group in direct:
            coverage = HistoricalCoverageService(self.repository, self.data_root).build_coverage(
                HistoricalCoverageRequest(working_group=profile.working_group,
                    from_meeting=start, to_meeting=end, query=query,
                    chair_note_snapshots=chair_note_snapshots or {}, limit_per_meeting=limit))
            completeness.append(coverage.completeness.value)
            for meeting in coverage.meetings:
                for candidate in meeting.coverage.chair_note_confirmed:
                    candidate = _direct_candidate(candidate, query)
                    if candidate is not None:
                        term_found.add(rules.decision_key(query))
                        self._add_inventory(records, candidate, query, group, True, False)
                for candidate in meeting.coverage.metadata_relevant_only:
                    candidate = _direct_candidate(candidate, query)
                    if candidate is not None:
                        term_found.add(rules.decision_key(query))
                        self._add_inventory(records, candidate, query, group, False, True)
                for candidate in meeting.coverage.unresolved_references:
                    candidate = _direct_candidate(candidate, query)
                    if candidate is not None:
                        term_found.add(rules.decision_key(query))
                        self._add_inventory(records, candidate, query, group, True, False)
        items = []
        study = TDocStudyService(self.repository, self.data_root)
        for key in sorted(records, key=lambda value: (
                historical_rules.meeting_order_key(value[1]) if value[1] else (10**9, 9, ""), value[0])):
            value = records[key]
            metadata = value["metadata"]
            content, outcome = False, False
            if metadata:
                view = study.build(profile.working_group, value["tdoc_id"],
                                   metadata_meeting=metadata.meeting)
                content = view.contribution.content_inspected
                outcome = view.meeting_outcome.explicit_tdoc_reference_found
            items.append(TopicInventoryTDoc(tdoc_id=value["tdoc_id"],
                meeting=metadata.meeting if metadata else key[1],
                title=metadata.title if metadata else None,
                organizations=metadata.organizations if metadata else [],
                official_url=str(metadata.source_url) if metadata and metadata.source_url else None,
                chair_note_confirmed=value["chair"],
                metadata_relevant_only=value["metadata_only"] and not value["chair"],
                content_inspected=content,
                explicit_meeting_outcome_reference=outcome,
                associations=sorted(value["associations"], key=lambda item: (
                    item.query_group.value, item.query_term.casefold(), item.meeting,
                    json.dumps(item.source_locator, sort_keys=True)))))
        by_company = defaultdict(list)
        unassigned = []
        for item in items:
            if item.organizations:
                for organization in item.organizations:
                    by_company[organization].append(item)
            else:
                unassigned.append(item)
        companies = [TopicCompanyInventory(organization=organization,
            tdocs=sorted(values, key=lambda item: (item.meeting or "", item.tdoc_id)))
            for organization, values in sorted(
                by_company.items(), key=lambda item: (item[0].casefold(), item[0]))]
        extension = self.bootstrapper.bootstrap(TopicBootstrapRequest(
            working_group=profile.working_group, from_meeting=start, to_meeting=end,
            user_terms=profile.user_terms + [term.literal_text for term in profile.terms
                if term.state is TopicTermState.ACCEPTED_SOURCE_TERM],
            topic_label=profile.topic_label,
            source_policy={"chair_note_snapshots": chair_note_snapshots or {}},
            candidate_limit=rules.DEFAULT_CANDIDATE_LIMIT))
        existing = {rules.decision_key(term.literal_text) for term in profile.terms}
        new_candidates = [term for term in extension.terms
                          if term.state is TopicTermState.SOURCE_CANDIDATE
                          and rules.decision_key(term.literal_text) not in existing]
        new_related = [term for term in extension.terms
                       if term.state is TopicTermState.RELATED_ONLY
                       and rules.decision_key(term.literal_text) not in existing]
        accepted = [query for query, group in direct
                    if group is TopicQueryGroup.ACCEPTED_SOURCE_TERM]
        logical = {"schema_version": rules.TOPIC_INVENTORY_SCHEMA_VERSION,
            "profile_id": profile.profile_id, "working_group": profile.working_group,
            "topic_label": profile.topic_label, "from_meeting": start, "to_meeting": end,
            "direct_terms": [query for query, _ in direct],
            "related_diagnostic_terms": related, "companies": companies,
            "unassigned_tdocs": unassigned, "new_source_candidates": new_candidates,
            "new_related_candidates": new_related,
            "accepted_terms_found": [value for value in accepted
                if rules.decision_key(value) in term_found],
            "accepted_terms_not_found": [value for value in accepted
                if rules.decision_key(value) not in term_found],
            "source_completeness": ("complete_for_selected_sources"
                if completeness and set(completeness) == {"complete_for_selected_sources"}
                else "partial_source_coverage"),
            "limitations": LIMITATIONS + [
                "Company grouping reports official metadata authorship only; it does not infer company stance."],
            "versions": {"inventory_schema": rules.TOPIC_INVENTORY_SCHEMA_VERSION,
                         "profile_schema": rules.TOPIC_PROFILE_SCHEMA_VERSION,
                         "terminology_ruleset": rules.TOPIC_TERMINOLOGY_RULESET_VERSION}}
        inventory_id = rules.identity(rules.logical(_jsonable(logical)), "topic-inventory-")
        return TopicProfileInventory(**logical, inventory_id=inventory_id)

    @staticmethod
    def _add_inventory(records, candidate, query, group, chair, metadata_only):
        metadata = candidate.metadata
        meeting = metadata.meeting if metadata else None
        key = (candidate.tdoc_id, meeting)
        value = records.setdefault(key, {"tdoc_id": candidate.tdoc_id,
            "metadata": metadata, "chair": False, "metadata_only": False, "associations": []})
        value["chair"] |= chair
        value["metadata_only"] |= metadata_only
        if candidate.associations:
            for association in candidate.associations:
                value["associations"].append(TopicInventoryAssociation(
                    query_group=group, query_term=query,
                    literal_source_phrase=association.topic_anchor.literal_text,
                    meeting=association.topic_anchor.source_ref.meeting,
                    association_basis=association.association_basis.value,
                    source_locator=association.topic_anchor.source_ref.model_dump(mode="json")))
        elif metadata:
            matched_field, matched_text = next(((name, value) for name, value in (
                ("title", metadata.title), ("abstract", metadata.abstract),
                ("agenda_item_description", metadata.agenda_item_description))
                if value and _contains_phrase(value, query)), ("title", metadata.title or ""))
            value["associations"].append(TopicInventoryAssociation(
                query_group=group, query_term=query,
                literal_source_phrase=matched_text,
                meeting=metadata.meeting,
                association_basis=f"metadata_{matched_field}_relevance",
                source_locator={"tdoc_id": metadata.tdoc_id, "field": matched_field,
                    "metadata_source_url": str(metadata.metadata_source_url)
                    if metadata.metadata_source_url else None,
                    "metadata_source_checksum": metadata.metadata_source_checksum}))


def _jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, WorkingGroup):
        return value.value
    return value


def _direct_candidate(candidate, query):
    """Keep only literal formatting-equivalent direct-term matches."""
    associations = [association for association in candidate.associations
                    if _contains_phrase(association.topic_anchor.literal_text, query)]
    if candidate.associations:
        if associations:
            return candidate.model_copy(update={"associations": associations})
        metadata = candidate.metadata
        fields = ([metadata.title, metadata.abstract, metadata.agenda_item_description]
                  if metadata else [])
        # A normalized Chair Note cell can join a trailing organization to a title.
        # Retain an independently exact metadata match without treating that joined
        # Chair Note spelling as the direct-term locator.
        if any(_contains_phrase(value or "", query) for value in fields):
            return candidate.model_copy(update={"associations": []})
        return None
    metadata = candidate.metadata
    fields = ([metadata.title, metadata.abstract, metadata.agenda_item_description]
              if metadata else [])
    return candidate if any(_contains_phrase(value or "", query) for value in fields) else None


def _contains_phrase(text, query):
    words = [re.escape(value) for value in re.findall(r"[A-Za-z0-9]+", query)]
    if not words:
        return False
    return bool(re.search(r"(?<![A-Za-z0-9])" + r"[-\s]+".join(words)
                          + r"(?![A-Za-z0-9])", text, re.I))
