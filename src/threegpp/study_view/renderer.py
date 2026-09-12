from __future__ import annotations

import json

from .models import TDocStudyView


def render_tdoc_study(view: TDocStudyView, *, provenance: bool = False) -> str:
    organization = ", ".join(view.organizations)
    lines = [view.tdoc_id + (f" — {organization}" if organization else "")]
    if view.title:
        lines.append(view.title)

    lines.extend(["", "DISCUSSION", "",
                  "Referenced in selected Chair Note: "
                  + ("Yes" if view.discussion.referenced_in_selected_chair_note
                     else "Not observed")])
    for item in view.discussion.references:
        lines.append(f"Meeting: {view.working_group.value}#{item.meeting}")
        if item.context:
            lines.append(f"Context: {item.context}")
        lines.append(f"Chair Note source: {item.chair_note_source}")
        if item.literal_source_context:
            lines.append(f"Literal source context: {item.literal_source_context}")
        if provenance:
            lines.extend([f"Graph ID: {item.graph_id}", f"Link ID: {item.link_id}",
                          f"Backend link kind: {item.backend_link_kind}",
                          "ChairNoteRef: " + _compact(item.chair_note_ref)])
    if view.discussion.limitation:
        lines.extend(["", "Note: " + view.discussion.limitation])

    lines.extend(["", "CONTRIBUTION", "",
                  "TDoc content inspected: " + ("Yes" if view.contribution.content_inspected
                                                  else "No")])
    groups = {}
    for item in view.contribution.evidence:
        groups.setdefault(item.kind.value, []).append(item)
    labels = {"proposal": "Proposal", "observation": "Observation",
              "conclusion": "Conclusion", "ffs": "FFS", "decision": "Decision"}
    for kind in ("proposal", "observation", "conclusion", "ffs", "decision"):
        if kind not in groups:
            continue
        lines.extend(["", labels[kind]])
        for item in groups[kind]:
            lines.append("- " + item.statement_text)
            if provenance:
                lines.append(f"  Evidence ID: {item.evidence_id}")
                lines.append("  EvidenceRefs: " + _compact(item.evidence_refs))
    if view.contribution.limitation:
        lines.extend(["", "Note: " + view.contribution.limitation])

    lines.extend(["", "MEETING OUTCOME", "",
                  "Explicit TDoc reference found: "
                  + ("Yes" if view.meeting_outcome.explicit_tdoc_reference_found else "No")])
    for item in view.meeting_outcome.outcomes:
        lines.append(f"Outcome: {item.outcome_type.value.title()}")
        if item.disposition is not None:
            lines.append(f"Disposition: {item.disposition.value.upper()}")
        if item.meeting:
            lines.append(f"Meeting: {view.working_group.value}#{item.meeting}")
        lines.append(f'Evidence: "{item.statement_text}"')
        lines.append(f"Evidence source: {item.evidence_id}")
        if provenance:
            lines.extend([f"Graph ID: {item.graph_id}", f"Link ID: {item.link_id}",
                          f"Backend link kind: {item.backend_link_kind}",
                          f"Literal reference: {item.literal_reference}",
                          "EvidenceRefs: " + _compact(item.evidence_refs)])
    if view.meeting_outcome.limitation:
        lines.extend(["", "Note: " + view.meeting_outcome.limitation])
    if provenance:
        lines.extend(["", "Provenance:", f"Study view ID: {view.view_id}",
                      "Backend statuses: " + _compact(view.backend_statuses)])
    return "\n".join(lines) + "\n"


def _compact(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
