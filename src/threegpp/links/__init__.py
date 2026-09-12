"""Deterministic document/reference-level evidence linkage."""

from .models import (
    ContributionSemanticEvidenceState, EvidenceLinkGraph, EvidenceNodeKind,
    EvidenceNodeRef, ExplicitEvidenceLink, ExplicitLinkKind, ExplicitLinkPresenceState,
    LinkCompleteness, LinkCoverage, LinkCoverageState, LinkPreparationItem,
    LinkPreparationPlan, SourceLocator, TDocExplicitLinkStatus, TDocStatusProvenance,
)
from .rules import (
    EXPLICIT_LINK_RULESET_VERSION, EXPLICIT_LINK_SCHEMA_VERSION,
    LINK_GRAPH_SCHEMA_VERSION, LINK_PREPARATION_SCHEMA_VERSION,
    TDOC_EXPLICIT_LINK_STATUS_SCHEMA_VERSION,
)
from .service import ExplicitLinkService

__all__ = [
    "ContributionSemanticEvidenceState", "EvidenceLinkGraph", "EvidenceNodeKind",
    "EvidenceNodeRef", "ExplicitEvidenceLink", "ExplicitLinkKind",
    "ExplicitLinkPresenceState", "LinkCompleteness", "LinkCoverage", "LinkCoverageState",
    "LinkPreparationItem", "LinkPreparationPlan", "SourceLocator", "ExplicitLinkService",
    "TDocExplicitLinkStatus", "TDocStatusProvenance",
    "EXPLICIT_LINK_RULESET_VERSION", "EXPLICIT_LINK_SCHEMA_VERSION",
    "LINK_GRAPH_SCHEMA_VERSION", "LINK_PREPARATION_SCHEMA_VERSION",
    "TDOC_EXPLICIT_LINK_STATUS_SCHEMA_VERSION",
]
