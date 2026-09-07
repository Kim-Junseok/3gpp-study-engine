from __future__ import annotations

import re
from dataclasses import dataclass

from threegpp.models.evidence import DetectionBasis, DocumentRole, EvidenceKind


EVIDENCE_SCHEMA_VERSION = "1"
EXTRACTION_RULESET_VERSION = "explicit-structural-v1"
RULE_VERSION = "1"


@dataclass(frozen=True)
class EvidenceRule:
    rule_id: str
    kind: EvidenceKind
    basis: DetectionBasis
    pattern: re.Pattern[str]
    allowed_roles: frozenset[DocumentRole] | None = None


def _label(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"^\s*(?P<label>{name})(?=\s|:|$)(?:\s+(?P<ordinal>\d+))?\s*:?[ \t]*(?P<body>.*)$",
        re.IGNORECASE,
    )


LABEL_RULES = (
    EvidenceRule("proposal-label", EvidenceKind.PROPOSAL, DetectionBasis.EXPLICIT_LABEL, _label("Proposal")),
    EvidenceRule("observation-label", EvidenceKind.OBSERVATION, DetectionBasis.EXPLICIT_LABEL, _label("Observation")),
    EvidenceRule("conclusion-label", EvidenceKind.CONCLUSION, DetectionBasis.EXPLICIT_LABEL, _label("Conclusion")),
    EvidenceRule("agreement-label", EvidenceKind.AGREEMENT, DetectionBasis.EXPLICIT_LABEL, _label("Agreements?")),
    EvidenceRule("decision-label", EvidenceKind.DECISION, DetectionBasis.EXPLICIT_LABEL, _label("Decision")),
    EvidenceRule("ffs-label", EvidenceKind.FFS, DetectionBasis.EXPLICIT_LABEL, _label("FFS")),
    EvidenceRule("further-study-label", EvidenceKind.FFS, DetectionBasis.EXPLICIT_LABEL, _label("For further study")),
)

INLINE_RULES = (
    EvidenceRule("proposal-we-propose", EvidenceKind.PROPOSAL, DetectionBasis.EXPLICIT_SENTENCE_CUE,
                 re.compile(r"\bwe propose that\b|\bthe source proposes\b", re.IGNORECASE),
                 frozenset({DocumentRole.CONTRIBUTION})),
    EvidenceRule("agreement-meeting-cue", EvidenceKind.AGREEMENT, DetectionBasis.EXPLICIT_SENTENCE_CUE,
                 re.compile(r"\bit was agreed that\b|\bthe meeting agreed\b", re.IGNORECASE),
                 frozenset({DocumentRole.MEETING_REPORT})),
    EvidenceRule("agreement-company-cue", EvidenceKind.AGREEMENT, DetectionBasis.EXPLICIT_SENTENCE_CUE,
                 re.compile(r"\bwe agree that\b|\bit is agreed in our view\b", re.IGNORECASE),
                 frozenset()),
    EvidenceRule("conclusion-meeting-cue", EvidenceKind.CONCLUSION, DetectionBasis.EXPLICIT_SENTENCE_CUE,
                 re.compile(r"\bit was concluded that\b|\bthe meeting concluded\b", re.IGNORECASE),
                 frozenset({DocumentRole.MEETING_REPORT})),
    EvidenceRule("decision-meeting-cue", EvidenceKind.DECISION, DetectionBasis.EXPLICIT_SENTENCE_CUE,
                 re.compile(r"\bthe meeting decided\b", re.IGNORECASE),
                 frozenset({DocumentRole.MEETING_REPORT})),
    EvidenceRule("ffs-explicit-cue", EvidenceKind.FFS, DetectionBasis.EXPLICIT_SENTENCE_CUE,
                 re.compile(r"\bFFS\b|\bleft for further study\b", re.IGNORECASE)),
)

HEADING_KINDS = {
    "proposal": EvidenceKind.PROPOSAL,
    "proposals": EvidenceKind.PROPOSAL,
    "observation": EvidenceKind.OBSERVATION,
    "observations": EvidenceKind.OBSERVATION,
    "conclusion": EvidenceKind.CONCLUSION,
    "conclusions": EvidenceKind.CONCLUSION,
    "agreement": EvidenceKind.AGREEMENT,
    "agreements": EvidenceKind.AGREEMENT,
    "decision": EvidenceKind.DECISION,
    "decisions": EvidenceKind.DECISION,
    "open issues": EvidenceKind.FFS,
    "issues for further study": EvidenceKind.FFS,
    "for further study": EvidenceKind.FFS,
}


AUTHORITY_KINDS = {
    DocumentRole.CONTRIBUTION: frozenset({
        EvidenceKind.PROPOSAL, EvidenceKind.OBSERVATION,
        EvidenceKind.CONCLUSION, EvidenceKind.FFS,
    }),
    DocumentRole.MEETING_REPORT: frozenset({
        EvidenceKind.AGREEMENT, EvidenceKind.CONCLUSION,
        EvidenceKind.FFS, EvidenceKind.DECISION,
    }),
    DocumentRole.CHAIR_MATERIAL: frozenset(),
    DocumentRole.AGENDA: frozenset(),
    DocumentRole.UNKNOWN: frozenset(),
}


def rule_allows(rule: EvidenceRule, role: DocumentRole) -> bool:
    if rule.allowed_roles is not None and role not in rule.allowed_roles:
        return False
    return rule.kind in AUTHORITY_KINDS[role]


def kind_allowed(kind: EvidenceKind, role: DocumentRole) -> bool:
    return kind in AUTHORITY_KINDS[role]


def heading_kind(text: str) -> EvidenceKind | None:
    key = re.sub(r"\s+", " ", text.strip().rstrip(":")).casefold()
    return HEADING_KINDS.get(key)
