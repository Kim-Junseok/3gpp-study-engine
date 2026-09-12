"""First-class Chair Note artifacts and positive discussion coverage."""

from .coverage import DiscussionCoverageService
from .models import (
    AssociationBasis, ChairNoteArtifact, ChairNoteRef, ChairNoteSnapshot,
    ChairNoteSnapshotRole, DiscussionCoverageRequest, DiscussionCoverageState,
    DiscussionRecord, DiscussionSection, ReferenceResolutionState,
    TopicCorpusExpansionPlan, TopicDiscussionCoverage,
)
from .service import ChairNoteService

__all__ = [
    'ChairNoteService', 'DiscussionCoverageService', 'ChairNoteArtifact', 'ChairNoteSnapshot',
    'ChairNoteSnapshotRole', 'ChairNoteRef', 'DiscussionCoverageRequest', 'DiscussionCoverageState',
    'DiscussionRecord', 'DiscussionSection', 'AssociationBasis', 'ReferenceResolutionState',
    'TopicDiscussionCoverage', 'TopicCorpusExpansionPlan',
]
