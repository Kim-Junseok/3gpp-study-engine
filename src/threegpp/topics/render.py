from __future__ import annotations

from .models import TopicTermState


def render_bootstrap(result, profile=None, *, provenance=False):
    lines = ["TOPIC BOOTSTRAP", "", "Topic", f"- {result.request.topic_label or result.request.user_terms[0]}",
             "", "User terms"]
    for term in result.request.user_terms:
        observed = next((item.source_occurrence_count for item in result.terms
                         if item.literal_text == term and item.state is TopicTermState.USER_SEED), 0)
        lines.append(f"- {term}: {'observed' if observed else 'not observed in selected sources'}")
    variants = [item for item in result.terms if item.state is TopicTermState.EXACT_VARIANT]
    lines.extend(["", "Exact lexical variants"])
    lines.extend([f"- {item.literal_text}: "
                  f"{'observed' if item.source_occurrence_count else 'not observed'}"
                  for item in variants] or ["- None"])
    candidates = [item for item in result.terms if item.state is TopicTermState.SOURCE_CANDIDATE]
    lines.extend(["", "Source terminology"])
    if not candidates:
        lines.append("- No source terminology candidates were found in the selected prepared official sources.")
    for item in candidates:
        lines.append(f"- {item.literal_text}: {item.source_occurrence_count} occurrence(s), "
                     f"{len(item.meetings)} meeting(s), {len(item.candidate_tdoc_ids)} TDoc(s)")
        if item.occurrences:
            locator = item.occurrences[0].locator
            source = {"chair_note": "selected Chair Note",
                      "metadata_title": "official metadata title",
                      "contribution_content": "local contribution content",
                      "meeting_outcome": "local meeting record"}[locator.source_type.value]
            suffix = f", {locator.associated_tdoc_id}" if locator.associated_tdoc_id else ""
            lines.append(f"  source example: {locator.working_group.value}#{locator.meeting} "
                         f"{source}{suffix}")
        if provenance:
            lines.append(f"  state={item.state.value}; support={item.retrieval_support_score}; id={item.term_id}")
            for occurrence in item.occurrences:
                loc = occurrence.locator
                lines.append(f"  source={loc.source_type.value} {loc.working_group.value}#{loc.meeting} "
                             f"{loc.source_identity} {loc.member or loc.source_file or ''} "
                             f"{loc.block_id or ''}:{loc.row_index}:{loc.cell_index}:{loc.char_start}-{loc.char_end}")
    related = [item for item in result.terms if item.state is TopicTermState.RELATED_ONLY]
    lines.extend(["", "Related observations"])
    lines.extend([f"- {item.literal_text} (diagnostic only)" for item in related] or ["- None"])
    coverage = ("Complete for the selected prepared sources"
                if result.source_coverage.completeness == "complete_for_selected_sources"
                else "Partial prepared-source coverage")
    lines.extend(["", "Source coverage", f"- {coverage}"])
    if profile:
        lines.append(f"- Saved profile: {profile.profile_id}")
    if provenance:
        lines.extend([f"- bootstrap identity: {result.bootstrap_id}",
                      f"- profile: {profile.profile_id if profile else 'not persisted'}"])
    lines.append("")
    return "\n".join(lines)


def render_profile(profile, inventory=None, *, provenance=False):
    accepted = [item.literal_text for item in profile.terms
                if item.state is TopicTermState.ACCEPTED_SOURCE_TERM]
    variants = [item.literal_text for item in profile.terms
                if item.state is TopicTermState.EXACT_VARIANT]
    candidates = [item.literal_text for item in profile.terms
                  if item.state is TopicTermState.SOURCE_CANDIDATE]
    related = [item.literal_text for item in profile.terms
               if item.state is TopicTermState.RELATED_ONLY]
    lines = ["TOPIC PROFILE", f"Profile: {profile.profile_id}", "", "Topic",
             f"- {profile.topic_label}", "", "User terms"]
    lines.extend(f"- {item}" for item in profile.user_terms)
    lines.extend(["", "Exact lexical variants"])
    lines.extend([f"- {item}" for item in variants] or ["- None"])
    lines.extend(["", "Accepted source terminology"])
    lines.extend([f"- {item}" for item in accepted] or ["- None"])
    lines.extend(["", "Candidate source terminology"])
    lines.extend([f"- {item}" for item in candidates] or ["- None"])
    lines.extend(["", "Related terminology"])
    lines.extend([f"- {item} (diagnostic only)" for item in related] or ["- None"])
    if inventory:
        lines.extend(["", "Source terminology in this range"])
        lines.extend([f"- Observed accepted term: {item}"
                      for item in inventory.accepted_terms_found])
        lines.extend([f"- Accepted term not observed: {item}"
                      for item in inventory.accepted_terms_not_found])
        if not inventory.accepted_terms_found and not inventory.accepted_terms_not_found:
            lines.append("- No accepted source terms are configured.")
        lines.extend(["", "TDocs and organizations",
            (f"- Within {profile.working_group.value}#{inventory.from_meeting}–#{inventory.to_meeting}, "
             "the selected source snapshots and direct topic terminology found:")])
        for company in inventory.companies:
            lines.append(f"- {company.organization}")
            for item in company.tdocs:
                discussion = "Yes" if item.chair_note_confirmed else "No explicit selected-source reference"
                lines.append(f"  - {item.tdoc_id} ({item.meeting or 'unknown'}): {item.title or 'title unavailable'}")
                lines.append(f"    Discussion: {discussion}; Contribution inspected: "
                             f"{'Yes' if item.content_inspected else 'No'}; Meeting outcome explicit ref: "
                             f"{'Yes' if item.explicit_meeting_outcome_reference else 'No'}")
        if inventory.unassigned_tdocs:
            lines.append("- Organization unresolved")
            lines.extend(f"  - {item.tdoc_id}" for item in inventory.unassigned_tdocs)
        if inventory.new_source_candidates:
            lines.extend(["", "New source terminology candidates"])
            lines.extend(f"- {item.literal_text}" for item in inventory.new_source_candidates)
        if inventory.new_related_candidates:
            lines.extend(["", "New related terminology observations"])
            lines.extend(f"- {item.literal_text} (diagnostic only)"
                         for item in inventory.new_related_candidates)
        coverage = ("Complete for the selected prepared sources"
                    if inventory.source_completeness == "complete_for_selected_sources"
                    else "Partial prepared-source coverage")
        lines.extend(["", "Coverage", f"- {coverage}"])
    if provenance:
        rejected = [item.literal_text for item in profile.terms
                    if item.state is TopicTermState.REJECTED]
        lines.extend(["", "Provenance", f"- profile identity: {profile.profile_id}",
                      f"- profile checksum: {profile.profile_checksum}",
                      f"- source bootstrap: {profile.source_bootstrap_id}"])
        lines.extend(f"- rejected term: {item}" for item in rejected)
        if inventory:
            lines.append(f"- inventory identity: {inventory.inventory_id}")
    lines.append("")
    return "\n".join(lines)
