"""Deterministic document/reference-level evidence linkage."""

from .models import (
    EvidenceLinkGraph, EvidenceNodeKind, EvidenceNodeRef, ExplicitEvidenceLink,
    ExplicitLinkKind, LinkCompleteness, LinkCoverage, LinkCoverageState,
    LinkPreparationItem, LinkPreparationPlan, SourceLocator,
)
from .rules import (
    EXPLICIT_LINK_RULESET_VERSION, EXPLICIT_LINK_SCHEMA_VERSION,
    LINK_GRAPH_SCHEMA_VERSION, LINK_PREPARATION_SCHEMA_VERSION,
)
from .service import ExplicitLinkService

__all__ = [
    "EvidenceLinkGraph", "EvidenceNodeKind", "EvidenceNodeRef", "ExplicitEvidenceLink",
    "ExplicitLinkKind", "LinkCompleteness", "LinkCoverage", "LinkCoverageState",
    "LinkPreparationItem", "LinkPreparationPlan", "SourceLocator", "ExplicitLinkService",
    "EXPLICIT_LINK_RULESET_VERSION", "EXPLICIT_LINK_SCHEMA_VERSION",
    "LINK_GRAPH_SCHEMA_VERSION", "LINK_PREPARATION_SCHEMA_VERSION",
]
