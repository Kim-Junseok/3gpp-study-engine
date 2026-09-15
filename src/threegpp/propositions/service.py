from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

from threegpp.evidence import EvidenceExtractionService, EXTRACTION_RULESET_VERSION
from threegpp.historical import rules as historical_rules
from threegpp.models import EvidenceExtractionRequest, EvidenceScope
from threegpp.topics import TopicProfileService

from .models import (
    PROPOSITION_CORPUS_SCHEMA_VERSION, PROPOSITION_REVIEW_SCHEMA_VERSION,
    PROPOSITION_SEGMENTATION_RULESET_VERSION, PROPOSITION_SOURCE_UNIT_SCHEMA_VERSION,
    AcceptedProposition,
    AtomicPropositionCandidate, CandidateReviewState, ExactSourceSpan,
    PropositionCorpusBuildRequest, PropositionCorpusManifest,
    PropositionEvidenceGap, PropositionReview, PropositionReviewDecision,
    PropositionTDocAccounting,
    PropositionSourceUnit, TopicPropositionCorpus,
)
from .rules import digest, option_context_source_units, segment, surface


LIMITATIONS = [
    "The corpus contains contribution-scoped SemanticEvidence only.",
    "Segmentation preserves source wording and does not establish proposition equivalence or company stance.",
    "Absence of proposition evidence is not negative evidence.",
]


class PropositionCorpusStaleError(ValueError):
    pass


class PropositionCorpusService:
    def __init__(self, repository, data_root: Path | str, *, profile_service=None,
                 evidence_service=None):
        self.repository = repository
        self.data_root = Path(data_root)
        self.profiles = profile_service or TopicProfileService(repository, self.data_root)
        self.evidence = evidence_service or EvidenceExtractionService(repository, self.data_root)

    def build(self, request: PropositionCorpusBuildRequest, *, persist=True):
        profile = self.profiles.load(request.profile_id)
        start = request.from_meeting or profile.from_meeting
        end = request.to_meeting or profile.to_meeting
        inventory = self.profiles.inventory(profile, from_meeting=start, to_meeting=end,
            chair_note_snapshots=request.chair_note_snapshots, limit=request.limit)
        items = self._inventory_items(inventory)
        inspected = {(item.meeting, item.tdoc_id): item for item in items if item.content_inspected}
        gaps = [PropositionEvidenceGap(tdoc_id=item.tdoc_id, meeting=item.meeting,
                    reason="contribution body is not inspected")
                for item in items if not item.content_inspected]
        evidence = self.evidence.list_evidence(EvidenceExtractionRequest(
            working_groups=[profile.working_group], tdoc_ids=sorted({key[1] for key in inspected}),
            scopes=[EvidenceScope.CONTRIBUTION], limit=5000)) if inspected else []
        states = {(row["working_group"], row["meeting"], row["tdoc_id"]): row
                  for row in self.evidence.inspect_extraction()}
        units = []
        for item in evidence:
            if item.scope is not EvidenceScope.CONTRIBUTION:
                continue
            if (item.meeting, item.tdoc_id) not in inspected:
                continue
            receipt = self.repository.get_document_receipt(
                item.tdoc_id, item.working_group, item.meeting)
            if receipt is None:
                gaps.append(PropositionEvidenceGap(tdoc_id=item.tdoc_id,
                    meeting=item.meeting, reason="normalized receipt is missing"))
                continue
            state = states.get((item.working_group.value, item.meeting, item.tdoc_id), {})
            logical = {"source_unit_schema": PROPOSITION_SOURCE_UNIT_SCHEMA_VERSION,
                "source_unit_ruleset": PROPOSITION_SEGMENTATION_RULESET_VERSION,
                "profile_id": profile.profile_id, "inventory_id": inventory.inventory_id,
                "evidence_id": item.evidence_id, "exact_text": item.statement_text,
                "refs": [v.model_dump(mode="json") for v in item.evidence_refs],
                "normalization_identity": item.normalization_identity,
                "normalized_checksum": receipt.normalized_checksum,
                "evidence_artifact_checksum": state.get("evidence_checksum")}
            sid = "proposition-source-" + digest(logical)
            units.append(PropositionSourceUnit(source_unit_id=sid,
                source_checksum=digest(logical), topic_profile_id=profile.profile_id,
                topic_inventory_id=inventory.inventory_id, working_group=item.working_group,
                meeting=item.meeting, tdoc_id=item.tdoc_id,
                title=inspected[(item.meeting, item.tdoc_id)].title,
                source_organizations=item.source_organizations,
                document_members=sorted({span.evidence_ref.member for span in item.evidence_refs}),
                semantic_evidence_id=item.evidence_id, evidence_kind=item.kind,
                evidence_scope=item.scope, exact_text=item.statement_text,
                surface_normalized=surface(item.statement_text),
                evidence_refs=item.evidence_refs,
                normalization_identity=item.normalization_identity,
                document_identity={"raw_sha256": getattr(getattr(receipt, "raw", None), "sha256", None),
                    "normalization_identity": item.normalization_identity,
                    "normalized_checksum": receipt.normalized_checksum},
                normalized_checksum=receipt.normalized_checksum,
                evidence_artifact_checksum=state.get("evidence_checksum")))
        units.sort(key=self._unit_key)
        groups = {}
        for unit in units:
            key = (unit.tdoc_id, unit.evidence_kind.value, surface(unit.exact_text))
            groups.setdefault(key, []).append(unit)
        for values in groups.values():
            if len(values) > 1:
                first=values[0]
                group_id = "surface-duplicate-" + digest({"tdoc_id":first.tdoc_id,
                    "evidence_kind":first.evidence_kind.value,
                    "surface_normalized":first.surface_normalized})
                for value in values: value.surface_duplicate_group_id = group_id
        candidates = []
        source_contexts = option_context_source_units(units)
        for unit in units:
            staged = segment(unit.exact_text)
            ids = []
            for ordinal, (span, reason, parent) in enumerate(staged, 1):
                logical = {"source_unit_id": unit.source_unit_id, "ordinal": ordinal,
                           "span": span.model_dump(mode="json"), "reason": reason.value,
                           "context_source_unit_id": source_contexts.get(unit.source_unit_id),
                           "ruleset": PROPOSITION_SEGMENTATION_RULESET_VERSION}
                checksum = digest(logical); cid = "proposition-candidate-" + checksum
                ids.append(cid)
                candidates.append(AtomicPropositionCandidate(candidate_id=cid,
                    candidate_checksum=checksum, source_unit_id=unit.source_unit_id,
                    ordinal=ordinal, exact_text=span.exact_text, source_spans=[span],
                    evidence_refs=unit.evidence_refs, working_group=unit.working_group,
                    meeting=unit.meeting, tdoc_id=unit.tdoc_id,
                    source_organizations=unit.source_organizations,
                    evidence_kind=unit.evidence_kind, segmentation_reason=reason,
                    context_candidate_id=(ids[parent] if parent is not None else None),
                    context_source_unit_id=(unit.source_unit_id if parent is not None
                        else source_contexts.get(unit.source_unit_id))))
        source_checksum = digest([u.model_dump(mode="json") for u in units])
        candidate_checksum = digest([c.model_dump(mode="json") for c in candidates])
        unit_counts, candidate_counts = {}, {}
        for unit in units:
            key=(unit.meeting,unit.tdoc_id); unit_counts[key]=unit_counts.get(key,0)+1
        for candidate in candidates:
            key=(candidate.meeting,candidate.tdoc_id); candidate_counts[key]=candidate_counts.get(key,0)+1
        accounting=[PropositionTDocAccounting(tdoc_id=item.tdoc_id,meeting=item.meeting,
            organizations=item.organizations,content_inspected=item.content_inspected,
            source_unit_count=unit_counts.get((item.meeting,item.tdoc_id),0),
            candidate_count=candidate_counts.get((item.meeting,item.tdoc_id),0)) for item in items]
        organization_groups={}
        for item in items:
            for organization in item.organizations:
                organization_groups.setdefault(organization,[]).append(item.tdoc_id)
        organization_groups={name:sorted(set(ids)) for name,ids in sorted(
            organization_groups.items(),key=lambda pair:(pair[0].casefold(),pair[0]))}
        logical = {"schema_version": PROPOSITION_CORPUS_SCHEMA_VERSION,
            "request": request.model_dump(mode="json"), "profile_id": profile.profile_id,
            "profile_checksum": profile.profile_checksum, "inventory_id": inventory.inventory_id,
            "working_group": profile.working_group.value, "topic_label": profile.topic_label,
            "from_meeting": start, "to_meeting": end,
            "source_unit_count": len(units), "candidate_count": len(candidates),
            "evidence_gaps": [g.model_dump(mode="json") for g in sorted(gaps, key=lambda x:(x.meeting or "",x.tdoc_id,x.reason))],
            "tdoc_accounting": [value.model_dump(mode="json") for value in accounting],
            "organization_groups": organization_groups,
            "source_identities": [unit.source_unit_id for unit in units],
            "evidence_identities": [unit.semantic_evidence_id for unit in units],
            "source_artifact_checksum": source_checksum,
            "candidate_artifact_checksum": candidate_checksum,
            "versions": self._versions(), "limitations": LIMITATIONS}
        checksum = digest(logical)
        manifest = PropositionCorpusManifest(**logical, corpus_checksum=checksum,
            corpus_id="topic-proposition-corpus-" + checksum)
        corpus = TopicPropositionCorpus(manifest=manifest, source_units=units,
            candidates=candidates, reviews=[], accepted_propositions=[])
        if persist: self._persist_new(corpus)
        return corpus

    def load(self, corpus_id: str, *, validate_current=True):
        path = self._find(corpus_id); manifest = PropositionCorpusManifest.model_validate_json(
            (path / "corpus.json").read_text())
        logical = manifest.model_dump(mode="json", exclude={"corpus_id", "corpus_checksum"})
        if digest(logical) != manifest.corpus_checksum or manifest.corpus_id != "topic-proposition-corpus-" + manifest.corpus_checksum:
            raise PropositionCorpusStaleError("PROPOSITION_CORPUS_STALE: manifest checksum conflict")
        units = [PropositionSourceUnit.model_validate(v) for v in self._read_gzip(path / "source-units.jsonl.gz")]
        candidates = [AtomicPropositionCandidate.model_validate(v) for v in self._read_gzip(path / "candidates.jsonl.gz")]
        if digest([u.model_dump(mode="json") for u in units]) != manifest.source_artifact_checksum:
            raise PropositionCorpusStaleError("PROPOSITION_CORPUS_STALE: source artifact changed")
        if digest([c.model_dump(mode="json") for c in candidates]) != manifest.candidate_artifact_checksum:
            raise PropositionCorpusStaleError("PROPOSITION_CORPUS_STALE: candidate artifact changed")
        reviews = self._read_reviews(path)
        for review in reviews:
            authority = review.model_dump(mode="json", exclude={"review_id", "researcher_note"})
            if review.review_id != "proposition-review-" + digest(authority):
                raise PropositionCorpusStaleError("PROPOSITION_CORPUS_STALE: review identity conflict")
        known = {c.candidate_id for c in candidates}; stale = [r.review_id for r in reviews if r.candidate_id not in known]
        active = [r for r in reviews if r.candidate_id in known]
        accepted = self._accepted(manifest.corpus_id, units, candidates, active)
        accepted_path=path / "accepted-propositions.jsonl.gz"
        if accepted_path.exists():
            persisted=[AcceptedProposition.model_validate(value) for value in self._read_gzip(accepted_path)]
            if [value.model_dump(mode="json") for value in persisted] != [value.model_dump(mode="json") for value in accepted]:
                raise PropositionCorpusStaleError("PROPOSITION_CORPUS_STALE: accepted proposition artifact changed")
        if validate_current:
            profile = self.profiles.load(manifest.profile_id)
            current = self.build(manifest.request, persist=False)
            if (profile.profile_checksum != manifest.profile_checksum or
                    current.manifest.corpus_id != manifest.corpus_id):
                raise PropositionCorpusStaleError("PROPOSITION_CORPUS_STALE: upstream evidence or inventory changed")
        return TopicPropositionCorpus(manifest=manifest, source_units=units,
            candidates=self._with_states(candidates, active), reviews=reviews,
            accepted_propositions=accepted, stale_review_ids=stale,
            **self._review_summary(active))

    def review(self, corpus_id, candidate_id, decision, *, spans=None, researcher_note=None):
        corpus = self.load(corpus_id)
        candidate = next((c for c in corpus.candidates if c.candidate_id == candidate_id), None)
        if candidate is None: raise ValueError("candidate is not in this corpus")
        decision = PropositionReviewDecision(decision)
        spans = [ExactSourceSpan.model_validate(v) for v in (spans or [])]
        unit = next(u for u in corpus.source_units if u.source_unit_id == candidate.source_unit_id)
        if decision is PropositionReviewDecision.REPLACE_WITH_EXACT_SPANS:
            if not spans: raise ValueError("replacement requires exact source spans")
            last = -1
            for span in sorted(spans, key=lambda v:(v.char_start,v.char_end)):
                if span.char_start < last or span.char_end > len(unit.exact_text) or unit.exact_text[span.char_start:span.char_end] != span.exact_text:
                    raise ValueError("replacement spans must be exact, ordered, non-overlapping source-unit slices")
                last = span.char_end
        elif spans:
            raise ValueError("replacement spans are allowed only for replace_with_exact_spans")
        authority = {"corpus_id": corpus_id, "candidate_id": candidate_id,
                     "source_unit_id": candidate.source_unit_id, "decision": decision.value,
                     "replacement_spans": [v.model_dump(mode="json") for v in spans],
                     "review_schema_version": PROPOSITION_REVIEW_SCHEMA_VERSION}
        review = PropositionReview(**authority, review_id="proposition-review-" + digest(authority),
                                   researcher_note=researcher_note)
        reviews = [r for r in corpus.reviews if r.candidate_id != candidate_id] + [review]
        reviews.sort(key=lambda r:(r.candidate_id,r.review_id)); path = self._find(corpus_id)
        self._write_jsonl(path / "reviews.jsonl", reviews)
        accepted = self._accepted(corpus_id, corpus.source_units, corpus.candidates, reviews)
        self._write_gzip(path / "accepted-propositions.jsonl.gz", accepted)
        return self.load(corpus_id)

    @staticmethod
    def _inventory_items(inventory):
        values = {}
        for company in inventory.companies:
            for item in company.tdocs: values[(item.meeting, item.tdoc_id)] = item
        for item in inventory.unassigned_tdocs: values[(item.meeting, item.tdoc_id)] = item
        return [values[k] for k in sorted(values, key=lambda x:(historical_rules.meeting_order_key(x[0]) if x[0] else (10**9,9,""),x[1]))]

    @staticmethod
    def _unit_key(unit):
        ref = min((s.evidence_ref.member, s.evidence_ref.block_id, s.sequence) for s in unit.evidence_refs)
        return (historical_rules.meeting_order_key(unit.meeting), unit.tdoc_id, ref, unit.semantic_evidence_id)

    @staticmethod
    def _versions():
        return {"proposition_corpus_schema": PROPOSITION_CORPUS_SCHEMA_VERSION,
                "source_unit_schema": PROPOSITION_SOURCE_UNIT_SCHEMA_VERSION,
                "segmentation_ruleset": PROPOSITION_SEGMENTATION_RULESET_VERSION,
                "review_schema": PROPOSITION_REVIEW_SCHEMA_VERSION,
                "semantic_evidence_ruleset": EXTRACTION_RULESET_VERSION}

    def _dir(self, manifest): return self.data_root / "derived" / "propositions" / manifest.working_group.value / manifest.corpus_id
    def _find(self, corpus_id):
        paths = list((self.data_root / "derived" / "propositions").glob(f"*/{corpus_id}"))
        if len(paths) != 1: raise ValueError("proposition corpus was not found or is ambiguous")
        return paths[0]

    def _persist_new(self, corpus):
        path = self._dir(corpus.manifest); path.mkdir(parents=True, exist_ok=True)
        self._atomic(path / "corpus.json", corpus.manifest.model_dump_json(indent=2) + "\n")
        self._write_gzip(path / "source-units.jsonl.gz", corpus.source_units)
        self._write_gzip(path / "candidates.jsonl.gz", corpus.candidates)
        if not (path / "reviews.jsonl").exists():
            self._write_jsonl(path / "reviews.jsonl", [])
            reviews=[]
        else:
            reviews=self._read_reviews(path)
        known={candidate.candidate_id for candidate in corpus.candidates}
        self._write_gzip(path / "accepted-propositions.jsonl.gz",
            self._accepted(corpus.manifest.corpus_id,corpus.source_units,corpus.candidates,
                           [review for review in reviews if review.candidate_id in known]))

    @staticmethod
    def _atomic(path, text):
        tmp = path.with_suffix(path.suffix + ".tmp"); tmp.write_text(text); os.replace(tmp, path)

    def _write_jsonl(self, path, values):
        text = "".join(json.dumps(v.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",",":")) + "\n" for v in values)
        self._atomic(path, text)

    def _write_gzip(self, path, values):
        raw = "".join(json.dumps(v.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",",":")) + "\n" for v in values).encode()
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as zipped: zipped.write(raw)
        os.replace(tmp, path)

    @staticmethod
    def _read_gzip(path):
        with gzip.open(path, "rt", encoding="utf-8") as stream: return [json.loads(x) for x in stream if x.strip()]
    @staticmethod
    def _read_reviews(path):
        p=path/"reviews.jsonl"
        return [PropositionReview.model_validate_json(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []

    @staticmethod
    def _with_states(candidates, reviews):
        decisions={r.candidate_id:r.decision for r in reviews}
        mapping={PropositionReviewDecision.ACCEPT:CandidateReviewState.ACCEPTED,
                 PropositionReviewDecision.DEFER:CandidateReviewState.DEFERRED,
                 PropositionReviewDecision.EXCLUDE_NON_PROPOSITION:CandidateReviewState.EXCLUDED,
                 PropositionReviewDecision.REPLACE_WITH_EXACT_SPANS:CandidateReviewState.REPLACED}
        return [c.model_copy(update={"review_state":mapping[decisions[c.candidate_id]]}) if c.candidate_id in decisions else c for c in candidates]

    @staticmethod
    def _review_summary(reviews):
        return {"accepted_count":sum(r.decision in {PropositionReviewDecision.ACCEPT,
                    PropositionReviewDecision.REPLACE_WITH_EXACT_SPANS} for r in reviews),
                "deferred_count":sum(r.decision is PropositionReviewDecision.DEFER for r in reviews),
                "excluded_count":sum(r.decision is PropositionReviewDecision.EXCLUDE_NON_PROPOSITION for r in reviews)}

    @staticmethod
    def _accepted(corpus_id, units, candidates, reviews):
        by_candidate={c.candidate_id:c for c in candidates}; by_unit={u.source_unit_id:u for u in units}; result=[]
        for review in reviews:
            if review.decision not in {PropositionReviewDecision.ACCEPT, PropositionReviewDecision.REPLACE_WITH_EXACT_SPANS}: continue
            candidate=by_candidate.get(review.candidate_id)
            if candidate is None: continue
            spans = review.replacement_spans or candidate.source_spans
            segments=[s.exact_text for s in spans]
            authority={"corpus_id":corpus_id,"review_id":review.review_id,"candidate_id":candidate.candidate_id,
                       "source_unit_id":candidate.source_unit_id,"source_spans":[s.model_dump(mode="json") for s in spans]}
            result.append(AcceptedProposition(proposition_id="accepted-proposition-"+digest(authority),
                corpus_id=corpus_id,review_id=review.review_id,candidate_id=candidate.candidate_id,
                source_unit_id=candidate.source_unit_id,exact_text_segments=segments,source_spans=spans,
                evidence_refs=by_unit[candidate.source_unit_id].evidence_refs,working_group=candidate.working_group,
                meeting=candidate.meeting,tdoc_id=candidate.tdoc_id,source_organizations=candidate.source_organizations,
                evidence_kind=candidate.evidence_kind))
        return sorted(result,key=lambda p:(historical_rules.meeting_order_key(p.meeting),p.tdoc_id,p.candidate_id))
