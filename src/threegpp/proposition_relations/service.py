from __future__ import annotations

import gzip
import json
import os
from itertools import combinations
from pathlib import Path

from threegpp.historical import rules as historical_rules
from threegpp.propositions import PropositionCorpusService
from threegpp.propositions.rules import digest

from .models import (
    MAX_ELIGIBLE_PAIRS,
    PROPOSITION_RELATION_CORPUS_SCHEMA_VERSION,
    PROPOSITION_RELATION_PAIR_RULESET_VERSION,
    PROPOSITION_RELATION_REVIEW_SCHEMA_VERSION,
    PROPOSITION_RELATION_SCHEMA_VERSION,
    AcceptedPropositionRelation,
    PairReviewState,
    PropositionPairCandidate,
    PropositionRelationBuildRequest,
    PropositionRelationCorpus,
    PropositionRelationCorpusManifest,
    PropositionRelationDecision,
    PropositionRelationReview,
    RelationAuthority,
    RelationBasisSpan,
)
from .rules import full_basis, organization_keys, pair_identity


LIMITATIONS = [
    "Relations are explicit researcher analysis, not source SemanticEvidence or meeting outcomes.",
    "Organization metadata identifies contribution origin and does not establish company stance.",
    "Unreviewed or absent relations are not negative evidence.",
    "Pair generation uses no semantic similarity, scoring, or automatic relation assignment.",
]


class PropositionRelationCorpusStaleError(ValueError):
    pass


class PairScopeTooLargeError(ValueError):
    pass


class PropositionRelationReviewConflict(ValueError):
    pass


class PropositionRelationService:
    def __init__(self, repository, data_root: Path | str, *, proposition_service=None):
        self.repository = repository
        self.data_root = Path(data_root)
        self.propositions = proposition_service or PropositionCorpusService(repository, self.data_root)

    def build(self, request: PropositionRelationBuildRequest, *, persist=True):
        source = self.propositions.load(request.proposition_corpus_id)
        accepted = self._filtered(source.accepted_propositions, request)
        accepted_checksum = digest([value.model_dump(mode="json") for value in accepted])
        source_manifest = source.manifest
        logical = {
            "schema_version": PROPOSITION_RELATION_CORPUS_SCHEMA_VERSION,
            "request": request.model_dump(mode="json"),
            "working_group": source_manifest.working_group.value,
            "source_proposition_corpus_id": source_manifest.corpus_id,
            "source_proposition_corpus_checksum": source_manifest.corpus_checksum,
            "source_profile_id": source_manifest.profile_id,
            "source_profile_checksum": source_manifest.profile_checksum,
            "source_inventory_id": source_manifest.inventory_id,
            "accepted_proposition_count": len(accepted),
            "accepted_proposition_checksum": accepted_checksum,
            "versions": self._versions(),
            "limitations": LIMITATIONS,
        }
        relation_corpus_id = "proposition-relation-corpus-" + digest(logical)
        pairs = self._candidate_pairs(relation_corpus_id, accepted, request)
        pair_checksum = digest([value.model_dump(mode="json") for value in pairs])
        complete = {**logical, "eligible_pair_count": len(pairs),
                    "pair_artifact_checksum": pair_checksum}
        checksum = digest(complete)
        manifest = PropositionRelationCorpusManifest(
            **complete, corpus_checksum=checksum, relation_corpus_id=relation_corpus_id)
        corpus = PropositionRelationCorpus(manifest=manifest, source_propositions=accepted,
            pair_candidates=pairs, reviews=[], accepted_relations=[])
        if persist:
            self._persist_new(corpus)
            return self.load(relation_corpus_id)
        return corpus

    def load(self, relation_corpus_id: str, *, validate_current=True):
        path = self._find(relation_corpus_id)
        manifest = PropositionRelationCorpusManifest.model_validate_json(
            (path / "corpus.json").read_text())
        logical = manifest.model_dump(mode="json", exclude={
            "relation_corpus_id", "corpus_checksum"})
        if (digest(logical) != manifest.corpus_checksum or
                manifest.relation_corpus_id != relation_corpus_id):
            raise PropositionRelationCorpusStaleError(
                "PROPOSITION_RELATION_CORPUS_STALE: manifest checksum conflict")
        identity_fields = manifest.model_dump(mode="json", exclude={
            "relation_corpus_id", "corpus_checksum", "eligible_pair_count",
            "pair_artifact_checksum"})
        if manifest.relation_corpus_id != "proposition-relation-corpus-" + digest(identity_fields):
            raise PropositionRelationCorpusStaleError(
                "PROPOSITION_RELATION_CORPUS_STALE: corpus identity conflict")
        if manifest.versions != self._versions():
            raise PropositionRelationCorpusStaleError(
                "PROPOSITION_RELATION_CORPUS_STALE: relation rules or schema changed")
        pairs = [PropositionPairCandidate.model_validate(value)
                 for value in self._read_gzip(path / "pair-candidates.jsonl.gz")]
        if digest([value.model_dump(mode="json") for value in pairs]) != manifest.pair_artifact_checksum:
            raise PropositionRelationCorpusStaleError(
                "PROPOSITION_RELATION_CORPUS_STALE: pair artifact changed")
        source = self.propositions.load(manifest.source_proposition_corpus_id,
                                        validate_current=validate_current)
        accepted = self._filtered(source.accepted_propositions, manifest.request)
        if (source.manifest.corpus_checksum != manifest.source_proposition_corpus_checksum or
                source.manifest.profile_checksum != manifest.source_profile_checksum or
                source.manifest.inventory_id != manifest.source_inventory_id or
                len(accepted) != manifest.accepted_proposition_count or
                digest([value.model_dump(mode="json") for value in accepted]) !=
                manifest.accepted_proposition_checksum):
            raise PropositionRelationCorpusStaleError(
                "PROPOSITION_RELATION_CORPUS_STALE: accepted proposition source changed")
        expected_pairs = self._candidate_pairs(relation_corpus_id, accepted, manifest.request)
        if (len(pairs) != manifest.eligible_pair_count or
                [value.model_dump(mode="json") for value in pairs] !=
                [value.model_dump(mode="json") for value in expected_pairs]):
            raise PropositionRelationCorpusStaleError(
                "PROPOSITION_RELATION_CORPUS_STALE: pair set is not regenerable")
        reviews = self._read_reviews(path)
        self._validate_reviews(reviews, pairs, accepted)
        current = self._current_reviews(reviews)
        accepted_relations = self._accepted(manifest.relation_corpus_id, pairs, accepted, current)
        persisted = [AcceptedPropositionRelation.model_validate(value)
                     for value in self._read_gzip(path / "accepted-relations.jsonl.gz")]
        if ([value.model_dump(mode="json") for value in persisted] !=
                [value.model_dump(mode="json") for value in accepted_relations]):
            raise PropositionRelationCorpusStaleError(
                "PROPOSITION_RELATION_CORPUS_STALE: accepted relation artifact changed")
        states = {pair_id: (PairReviewState.DEFERRED if review.decision is
                  PropositionRelationDecision.DEFER else PairReviewState.REVIEWED)
                  for pair_id, review in current.items()}
        visible_pairs = [pair.model_copy(update={"review_state": states[pair.pair_id]})
                         if pair.pair_id in states else pair for pair in pairs]
        return PropositionRelationCorpus(manifest=manifest, source_propositions=accepted,
            pair_candidates=visible_pairs, reviews=reviews,
            accepted_relations=accepted_relations,
            reviewed_count=sum(value is PairReviewState.REVIEWED for value in states.values()),
            deferred_count=sum(value is PairReviewState.DEFERRED for value in states.values()))

    def review(self, relation_corpus_id: str, pair_id: str, decision,
               *, left_basis=None, right_basis=None, rationale=None, update=False):
        corpus = self.load(relation_corpus_id)
        pair = next((value for value in corpus.pair_candidates if value.pair_id == pair_id), None)
        if pair is None:
            raise ValueError("pair is not in this relation corpus")
        propositions = {value.proposition_id: value for value in corpus.source_propositions}
        left = propositions[pair.left_proposition_id]
        right = propositions[pair.right_proposition_id]
        left_basis = self._basis(left, left_basis)
        right_basis = self._basis(right, right_basis)
        decision = PropositionRelationDecision(decision)
        current = self._current_reviews(corpus.reviews).get(pair_id)
        payload = {
            "decision": decision.value,
            "left_basis": [value.model_dump(mode="json") for value in left_basis],
            "right_basis": [value.model_dump(mode="json") for value in right_basis],
            "rationale": rationale,
        }
        if current:
            current_payload = current.model_dump(mode="json", include=set(payload))
            if current_payload == payload:
                return corpus
            if not update:
                raise PropositionRelationReviewConflict(
                    "RELATION_REVIEW_CONFLICT: pass update=True/--update to supersede the current review")
        sequence = current.sequence + 1 if current else 1
        authority = {"relation_corpus_id": relation_corpus_id, "pair_id": pair_id,
            "sequence": sequence, **payload,
            "supersedes_review_id": current.review_id if current else None,
            "review_schema_version": PROPOSITION_RELATION_REVIEW_SCHEMA_VERSION}
        review = PropositionRelationReview(
            **authority, review_id="proposition-relation-review-" + digest(authority))
        reviews = sorted(corpus.reviews + [review],
                         key=lambda value: (value.pair_id, value.sequence, value.review_id))
        path = self._find(relation_corpus_id)
        self._write_jsonl(path / "reviews.jsonl", reviews)
        current_reviews = self._current_reviews(reviews)
        accepted = self._accepted(relation_corpus_id, corpus.pair_candidates,
                                  corpus.source_propositions, current_reviews)
        self._write_gzip(path / "accepted-relations.jsonl.gz", accepted)
        return self.load(relation_corpus_id)

    @staticmethod
    def _filtered(values, request):
        organizations = organization_keys(request.organizations)
        kinds = {value.value for value in request.evidence_kinds}
        result = []
        for value in values:
            if organizations and not organization_keys(value.source_organizations) & organizations:
                continue
            if request.tdoc_ids and value.tdoc_id not in request.tdoc_ids:
                continue
            if request.meetings and value.meeting not in request.meetings:
                continue
            if kinds and value.evidence_kind.value not in kinds:
                continue
            if request.proposition_ids and value.proposition_id not in request.proposition_ids:
                continue
            result.append(value)
        return sorted(result, key=PropositionRelationService._proposition_key)

    @staticmethod
    def _eligible(left, right):
        left_orgs, right_orgs = (organization_keys(left.source_organizations),
                                 organization_keys(right.source_organizations))
        return bool(left_orgs and right_orgs and left_orgs.isdisjoint(right_orgs))

    @staticmethod
    def _pair_filters(left, right, request):
        left_filter = organization_keys(request.left_organizations)
        right_filter = organization_keys(request.right_organizations)
        return ((not left_filter or bool(organization_keys(left.source_organizations) & left_filter))
                and (not right_filter or bool(organization_keys(right.source_organizations) & right_filter)))

    @staticmethod
    def _pair(corpus_id, left, right, pair_id):
        return PropositionPairCandidate(pair_id=pair_id, relation_corpus_id=corpus_id,
            left_proposition_id=left.proposition_id, right_proposition_id=right.proposition_id,
            left_organizations=left.source_organizations,
            right_organizations=right.source_organizations,
            left_tdoc_id=left.tdoc_id, right_tdoc_id=right.tdoc_id,
            left_meeting=left.meeting, right_meeting=right.meeting,
            left_evidence_kind=left.evidence_kind, right_evidence_kind=right.evidence_kind)

    def _candidate_pairs(self, corpus_id, accepted, request):
        provisional = []
        for one, two in combinations(accepted, 2):
            if not self._eligible(one, two):
                continue
            left_id, right_id, pair_id = pair_identity(one.proposition_id, two.proposition_id)
            by_id = {one.proposition_id: one, two.proposition_id: two}
            left, right = by_id[left_id], by_id[right_id]
            if not self._pair_filters(left, right, request):
                continue
            provisional.append((left, right, pair_id))
            if len(provisional) > MAX_ELIGIBLE_PAIRS:
                raise PairScopeTooLargeError(
                    f"PAIR_SCOPE_TOO_LARGE: more than {MAX_ELIGIBLE_PAIRS} eligible pairs")
        pairs = [self._pair(corpus_id, left, right, pair_id)
                 for left, right, pair_id in provisional]
        by_id = {value.proposition_id: value for value in accepted}
        return sorted(pairs, key=lambda pair: self._pair_key(pair, by_id))

    @staticmethod
    def _proposition_key(value):
        return (historical_rules.meeting_order_key(value.meeting), value.tdoc_id,
                value.candidate_id, value.proposition_id)

    @staticmethod
    def _pair_key(pair, by_id):
        return (PropositionRelationService._proposition_key(by_id[pair.left_proposition_id]),
                PropositionRelationService._proposition_key(by_id[pair.right_proposition_id]),
                pair.pair_id)

    @staticmethod
    def _basis(proposition, values):
        spans = full_basis(proposition) if values is None else [
            RelationBasisSpan.model_validate(value) for value in values]
        if not spans:
            raise ValueError("each proposition relation requires a non-empty exact basis")
        previous = (-1, -1)
        for span in spans:
            if span.segment_index >= len(proposition.exact_text_segments):
                raise ValueError("basis segment index is outside the accepted proposition")
            text = proposition.exact_text_segments[span.segment_index]
            if (span.char_end > len(text) or
                    text[span.char_start:span.char_end] != span.exact_text or
                    (span.segment_index, span.char_start) < previous):
                raise ValueError("basis spans must be exact, ordered proposition segment slices")
            if span.segment_index == previous[0] and span.char_start < previous[1]:
                raise ValueError("basis spans must not overlap")
            previous = (span.segment_index, span.char_end)
        return spans

    @staticmethod
    def _current_reviews(reviews):
        current = {}
        for review in reviews:
            if review.pair_id not in current or review.sequence > current[review.pair_id].sequence:
                current[review.pair_id] = review
        return current

    @staticmethod
    def _validate_reviews(reviews, pairs, propositions):
        known = {pair.pair_id for pair in pairs}
        pair_by_id = {pair.pair_id: pair for pair in pairs}
        proposition_by_id = {value.proposition_id: value for value in propositions}
        grouped = {}
        for review in reviews:
            authority = review.model_dump(mode="json", exclude={"review_id"})
            if review.review_id != "proposition-relation-review-" + digest(authority):
                raise PropositionRelationCorpusStaleError(
                    "PROPOSITION_RELATION_CORPUS_STALE: review identity conflict")
            if review.pair_id not in known:
                raise PropositionRelationCorpusStaleError(
                    "PROPOSITION_RELATION_CORPUS_STALE: review pair is missing")
            pair = pair_by_id[review.pair_id]
            try:
                PropositionRelationService._basis(
                    proposition_by_id[pair.left_proposition_id], review.left_basis)
                PropositionRelationService._basis(
                    proposition_by_id[pair.right_proposition_id], review.right_basis)
            except ValueError as exc:
                raise PropositionRelationCorpusStaleError(
                    "PROPOSITION_RELATION_CORPUS_STALE: review basis conflict") from exc
            grouped.setdefault(review.pair_id, []).append(review)
        for values in grouped.values():
            values.sort(key=lambda value: value.sequence)
            for index, value in enumerate(values, 1):
                expected = values[index - 2].review_id if index > 1 else None
                if value.sequence != index or value.supersedes_review_id != expected:
                    raise PropositionRelationCorpusStaleError(
                        "PROPOSITION_RELATION_CORPUS_STALE: review history conflict")

    @staticmethod
    def _accepted(corpus_id, pairs, propositions, current):
        by_pair = {value.pair_id: value for value in pairs}
        by_proposition = {value.proposition_id: value for value in propositions}
        result = []
        for pair_id, review in sorted(current.items()):
            if review.decision is PropositionRelationDecision.DEFER:
                continue
            pair = by_pair[pair_id]
            left = by_proposition[pair.left_proposition_id]
            right = by_proposition[pair.right_proposition_id]
            logical = {"relation_corpus_id": corpus_id, "pair_id": pair_id,
                "left_proposition_id": left.proposition_id,
                "right_proposition_id": right.proposition_id,
                "decision": review.decision.value,
                "left_basis": [value.model_dump(mode="json") for value in review.left_basis],
                "right_basis": [value.model_dump(mode="json") for value in review.right_basis],
                "authority": RelationAuthority.RESEARCHER_ANALYSIS.value,
                "pair_ruleset_version": PROPOSITION_RELATION_PAIR_RULESET_VERSION,
                "relation_schema_version": PROPOSITION_RELATION_SCHEMA_VERSION}
            result.append(AcceptedPropositionRelation(**logical,
                relation_id="accepted-proposition-relation-" + digest(logical),
                review_id=review.review_id,
                left_source_review_id=left.review_id,
                right_source_review_id=right.review_id,
                left_evidence_refs=left.evidence_refs,
                right_evidence_refs=right.evidence_refs))
        return result

    @staticmethod
    def _versions():
        return {"relation_corpus_schema": PROPOSITION_RELATION_CORPUS_SCHEMA_VERSION,
                "pair_ruleset": PROPOSITION_RELATION_PAIR_RULESET_VERSION,
                "relation_review_schema": PROPOSITION_RELATION_REVIEW_SCHEMA_VERSION,
                "accepted_relation_schema": PROPOSITION_RELATION_SCHEMA_VERSION}

    def _dir(self, manifest):
        return (self.data_root / "derived" / "proposition-relations" /
                manifest.working_group.value / manifest.relation_corpus_id)

    def _find(self, corpus_id):
        paths = list((self.data_root / "derived" / "proposition-relations").glob(f"*/{corpus_id}"))
        if len(paths) != 1:
            raise ValueError("proposition relation corpus was not found or is ambiguous")
        return paths[0]

    def _persist_new(self, corpus):
        path = self._dir(corpus.manifest)
        path.mkdir(parents=True, exist_ok=True)
        self._atomic(path / "corpus.json", corpus.manifest.model_dump_json(indent=2) + "\n")
        self._write_gzip(path / "pair-candidates.jsonl.gz", corpus.pair_candidates)
        reviews = self._read_reviews(path) if (path / "reviews.jsonl").exists() else []
        if not (path / "reviews.jsonl").exists():
            self._write_jsonl(path / "reviews.jsonl", [])
        self._validate_reviews(reviews, corpus.pair_candidates, corpus.source_propositions)
        accepted = self._accepted(corpus.manifest.relation_corpus_id,
            corpus.pair_candidates, corpus.source_propositions, self._current_reviews(reviews))
        self._write_gzip(path / "accepted-relations.jsonl.gz", accepted)

    @staticmethod
    def _atomic(path, text):
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text)
        os.replace(tmp, path)

    def _write_jsonl(self, path, values):
        text = "".join(json.dumps(value.model_dump(mode="json"), ensure_ascii=False,
                    sort_keys=True, separators=(",", ":")) + "\n" for value in values)
        self._atomic(path, text)

    def _write_gzip(self, path, values):
        raw = "".join(json.dumps(value.model_dump(mode="json"), ensure_ascii=False,
                    sort_keys=True, separators=(",", ":")) + "\n" for value in values).encode()
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as zipped:
                zipped.write(raw)
        os.replace(tmp, path)

    @staticmethod
    def _read_gzip(path):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return [json.loads(line) for line in stream if line.strip()]

    @staticmethod
    def _read_reviews(path):
        file = path / "reviews.jsonl"
        return [PropositionRelationReview.model_validate_json(line)
                for line in file.read_text().splitlines() if line.strip()] if file.exists() else []
