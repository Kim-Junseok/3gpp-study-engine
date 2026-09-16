from __future__ import annotations


def render_proposition_relations(corpus, *, offset=0, limit=20, provenance=False):
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    manifest = corpus.manifest
    propositions = {value.proposition_id: value for value in corpus.source_propositions}
    reviews = {}
    for review in corpus.reviews:
        if review.pair_id not in reviews or review.sequence > reviews[review.pair_id].sequence:
            reviews[review.pair_id] = review
    lines = ["Proposition relations", f"Corpus: {manifest.relation_corpus_id}",
        f"Source proposition corpus: {manifest.source_proposition_corpus_id}",
        f"Eligible pairs: {manifest.eligible_pair_count}",
        f"Reviewed: {corpus.reviewed_count}", f"Deferred: {corpus.deferred_count}",
        "Authority warning: relation decisions are researcher annotations, not source evidence, meeting outcomes, or complete organization positions.", ""]
    selected = corpus.pair_candidates[offset:offset + limit]
    for pair in selected:
        left, right = propositions[pair.left_proposition_id], propositions[pair.right_proposition_id]
        lines += [f"PAIR {pair.pair_id} [{pair.review_state.value}]",
            "LEFT PROPOSITION", f"  {left.proposition_id}",
            f"  Organization metadata: {', '.join(left.source_organizations)}",
            f"  TDoc: {left.tdoc_id}; meeting: {left.meeting}; kind: {left.evidence_kind.value}",
            f"  {' | '.join(left.exact_text_segments)}",
            "RIGHT PROPOSITION", f"  {right.proposition_id}",
            f"  Organization metadata: {', '.join(right.source_organizations)}",
            f"  TDoc: {right.tdoc_id}; meeting: {right.meeting}; kind: {right.evidence_kind.value}",
            f"  {' | '.join(right.exact_text_segments)}", "RELATION REVIEW"]
        review = reviews.get(pair.pair_id)
        if review:
            lines.append(f"  {review.decision.value} ({review.review_id})")
            for label, basis in (("Left basis", review.left_basis),
                                 ("Right basis", review.right_basis)):
                for span in basis:
                    lines.append(f"  {label} [{span.segment_index}:{span.char_start}:{span.char_end}]: {span.exact_text}")
            if review.rationale:
                lines.append(f"  Rationale annotation: {review.rationale}")
        else:
            lines.append("  UNREVIEWED")
        if provenance:
            left_refs = ", ".join(f"{value.evidence_ref.member}/{value.evidence_ref.block_id}"
                                  for value in left.evidence_refs)
            right_refs = ", ".join(f"{value.evidence_ref.member}/{value.evidence_ref.block_id}"
                                   for value in right.evidence_refs)
            lines += [f"  left source review={left.review_id}; EvidenceRefs={left_refs}",
                      f"  right source review={right.review_id}; EvidenceRefs={right_refs}"]
        lines.append("")
    if offset + len(selected) < len(corpus.pair_candidates):
        lines.append(f"More pairs remain; request offset {offset + len(selected)} explicitly.")
    return "\n".join(lines).rstrip() + "\n"
