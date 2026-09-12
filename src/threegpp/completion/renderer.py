from __future__ import annotations

from .models import TDocEvidenceCompletionResult


def render_completion_result(result: TDocEvidenceCompletionResult) -> str:
    stages = (
        ("Metadata", result.metadata),
        ("Contribution body", result.body),
        ("Normalization", result.normalization),
        ("Index", result.index),
        ("Semantic extraction", result.semantic_extraction),
        ("Link/status refresh", result.link_status),
    )
    lines = [result.request.tdoc_id, ""]
    for label, stage in stages:
        lines.append(f"{label:<26}{stage.state.value.upper()}")
        lines.append(f"  {stage.detail}")
    lines.extend([
        f"Retention                 {(result.retention.value.upper() if result.retention else 'N/A')}",
        "TDoc content inspected    " + ("Yes" if result.content_inspected else "No"),
    ])
    if result.evidence_count is not None:
        lines.append(f"Contribution evidence     {result.evidence_count}")
        if result.content_inspected and result.evidence_count == 0:
            lines.append(
                "No qualifying contribution statements were extracted under the current evidence rules."
            )
    if result.failure is not None:
        lines.append(f"Failure                    {result.failure.value.upper()}")
    lines.append(f"Completion result ID       {result.result_id}")
    if result.study_view_id:
        lines.append(f"Study view ID              {result.study_view_id}")
    return "\n".join(lines) + "\n"
