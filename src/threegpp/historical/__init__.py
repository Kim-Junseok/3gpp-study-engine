"""Historical metadata resolution and bounded meeting-range coverage."""

from .models import (
    HistoricalCorpusExpansionPlan, HistoricalCoverageRequest, HistoricalMetadataResolution,
    HistoricalResolutionState, HistoricalTopicCoverage, MeetingAlias,
)
from .resolver import HistoricalMetadataResolver
from .service import HistoricalCoverageService

__all__ = [
    "HistoricalCorpusExpansionPlan", "HistoricalCoverageRequest", "HistoricalMetadataResolution",
    "HistoricalResolutionState", "HistoricalTopicCoverage", "MeetingAlias",
    "HistoricalMetadataResolver", "HistoricalCoverageService",
]
