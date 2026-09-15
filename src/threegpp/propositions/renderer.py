def render_proposition_corpus(corpus, *, provenance=False):
    m=corpus.manifest
    lines=[f"Topic proposition corpus: {m.topic_label}",f"Corpus: {m.corpus_id}",
           f"Scope: {m.working_group.value} {m.from_meeting}..{m.to_meeting}",
           f"Source units: {len(corpus.source_units)}",f"Candidates: {len(corpus.candidates)}",
           f"Accepted: {corpus.accepted_count}",f"Deferred: {corpus.deferred_count}",
           f"Excluded: {corpus.excluded_count}",f"Evidence gaps: {len(m.evidence_gaps)}",""]
    units={unit.source_unit_id:unit for unit in corpus.source_units}
    current=None
    for candidate in corpus.candidates:
        unit=units[candidate.source_unit_id]
        group=(tuple(candidate.source_organizations),candidate.tdoc_id)
        if group != current:
            lines += [f"Organization metadata: {', '.join(group[0]) or 'Unassigned'}",
                      f"TDoc: {candidate.tdoc_id}" + (f" — {unit.title}" if unit.title else "")]
            current=group
        refs=", ".join(f"{span.evidence_ref.member}/{span.evidence_ref.block_id}"
                       for span in candidate.evidence_refs)
        lines += [f"SOURCE EVIDENCE ({candidate.evidence_kind.value}) [{refs}]",
                  f"  {unit.exact_text}","PROPOSITION CANDIDATE",
                  f"  {candidate.candidate_id} [{candidate.review_state.value}]",
                  f"  {candidate.exact_text}"]
        if provenance:
            lines.append(f"  source={candidate.source_unit_id} spans=" + ",".join(
                f"{s.char_start}:{s.char_end}" for s in candidate.source_spans))
            if candidate.context_source_unit_id or candidate.context_candidate_id:
                lines.append("  context=" + ", ".join(value for value in (
                    candidate.context_source_unit_id, candidate.context_candidate_id) if value))
    if corpus.accepted_propositions:
        lines += ["", "Accepted propositions"]
        for item in corpus.accepted_propositions:
            lines.append(f"  {item.proposition_id}: " + " | ".join(item.exact_text_segments))
    if m.evidence_gaps:
        lines += ["", "Evidence gaps"] + [f"  {g.tdoc_id}: {g.reason}" for g in m.evidence_gaps]
    return "\n".join(lines)+"\n"
