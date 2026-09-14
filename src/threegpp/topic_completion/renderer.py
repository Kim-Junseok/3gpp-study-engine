from __future__ import annotations

from .models import TopicCompletionExecutionState, TopicCompletionItemState


def render_topic_completion_plan(plan, *, provenance=False):
    lines = ["TOPIC CORPUS COMPLETION PLAN", "", "Topic", f"- {plan.topic_label}",
             f"- Profile: {plan.profile_id}",
             f"- Range: {plan.working_group.value}#{plan.from_meeting}–#{plan.to_meeting}",
             "", "Direct corpus",
             f"- TDocs: {plan.summary['total_direct_tdocs']}",
             f"- Content inspected: {plan.summary['already_inspected']}",
             f"- Selected for bounded completion: {plan.summary['selected_completion_candidates']}",
             f"- Deferred: {plan.summary['deferred']}",
             f"- Ineligible: {plan.summary['ineligible']}", ""]
    for item in plan.items:
        companies = ", ".join(item.organizations) or "Organization unavailable"
        lines.extend([companies, f"  {item.tdoc_id} ({item.metadata_meeting or 'meeting unresolved'}): {item.title or 'Title unavailable'}",
            "  Discussion: " + ("Referenced in selected Chair Note"
                if item.discussion_confirmed else "Not observed in selected Chair Note"),
            "  Contribution: TDoc content inspected: " + ("Yes" if item.content_inspected else "No"),
            "  Meeting outcome: Explicit TDoc reference found: "
                + ("Yes" if item.explicit_meeting_outcome_reference else "No"),
            f"  Completion: {item.state.value.replace('_', ' ')} — {item.reason}"])
        if provenance:
            lines.extend([f"  Item: {item.item_id}",
                "  Matched terms: " + ", ".join(sorted({a.query_term for a in item.associations})),
                f"  Metadata source: {item.metadata_source_identity or 'unresolved'}"])
    lines.extend(["", *plan.limitations, "", f"Plan: {plan.plan_id}"])
    return "\n".join(lines) + "\n"


def render_topic_completion_result(result, *, provenance=False):
    lines = ["TOPIC CORPUS COMPLETION RESULT", "",
        f"Requested: {result.summary['requested']}",
        f"Completed: {result.summary['completed']}",
        f"Reused: {result.summary['reused']}",
        f"Failed: {result.summary['failed']}",
        f"Not run: {result.summary['not_run']}", ""]
    for item in result.items:
        lines.append(f"- {item.tdoc_id}: {item.state.value}")
        if item.failure: lines.append(f"  Failure: {item.failure}")
        if item.warning: lines.append(f"  Note: {item.warning}")
        if provenance and item.completion_result:
            lines.append(f"  V0.9 result: {item.completion_result.result_id}")
    if result.systemic_failure:
        lines.extend(["", f"Systemic failure: {result.systemic_failure}"])
    lines.extend(["", *result.limitations, "", f"Result: {result.result_id}"])
    return "\n".join(lines) + "\n"
