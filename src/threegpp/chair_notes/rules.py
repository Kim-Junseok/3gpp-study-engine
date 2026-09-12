"""Versioned, literal-only Chair Note discovery and interpretation rules."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from .models import ChairNoteArtifact, ChairNoteSnapshot, ChairNoteSnapshotRole

CHAIR_NOTE_SCHEMA_VERSION = "2"
CHAIR_NOTE_DISCOVERY_RULESET_VERSION = "chair-note-discovery-v1"
CHAIR_NOTE_SNAPSHOT_RULESET_VERSION = "chair-note-snapshot-v1"
DISCUSSION_SECTION_RULESET_VERSION = "discussion-section-v3"
TDOC_REFERENCE_RULESET_VERSION = "tdoc-reference-v2"
CORPUS_EXPANSION_SCHEMA_VERSION = "1"
CHAIR_NOTE_DIRECTORY_NAMES = frozenset({"chair_notes"})
# Real Chair Notes commonly concatenate a TDoc number and its title in a table
# cell (for example ``R1-2605236HARQ related aspects``).  A following letter is
# therefore a valid title boundary.  Still reject another digit or a hyphen so
# a prefix of a longer/malformed identifier cannot be accepted.
TDOC_REFERENCE = re.compile(r"(?<![\w-])R[12]-[0-9]{6,8}(?![0-9-])", re.I)
SNAPSHOT_LABEL = re.compile(r"(?<![a-z0-9])(?:final|eom\d*|rev(?:ision)?\d*)(?![a-z0-9])", re.I)
MAX_SECTION_BLOCKS = 200
COMPLETENESS_LIMITATION = (
    "Chair-note-confirmed references are positive evidence that the selected Chair Note "
    "associates a TDoc with the recorded discussion context. Absence from the selected "
    "Chair Note snapshot is not proof that the TDoc was not discussed."
)


def identity(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def discovered_snapshot(group, meeting, url, directory, discovered_at: datetime):
    filename = unquote(PurePosixPath(urlparse(url).path).name)
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise ValueError("unsafe Chair Note filename")
    labels = [m.group(0) for m in SNAPSHOT_LABEL.finditer(PurePosixPath(filename).stem)]
    roles = {ChairNoteSnapshotRole.EXPLICIT_FINAL if label.casefold() == "final"
             else ChairNoteSnapshotRole.EOM if label.casefold().startswith("eom")
             else ChairNoteSnapshotRole.INTERMEDIATE for label in labels}
    role = next(iter(roles)) if len(roles) == 1 else ChairNoteSnapshotRole.UNKNOWN
    artifact_id = "chair-" + identity([str(group), meeting, url])
    return ChairNoteSnapshot(
        schema_version=CHAIR_NOTE_SCHEMA_VERSION,
        artifact=ChairNoteArtifact(artifact_id=artifact_id, working_group=group, meeting=meeting,
            official_url=url, official_filename=filename, source_directory=directory,
            discovered_at=discovered_at, discovery_ruleset=CHAIR_NOTE_DISCOVERY_RULESET_VERSION),
        snapshot_id="cn-" + identity([artifact_id, filename]),
        snapshot_label_raw=" ".join(labels) if labels else None, role=role,
        role_basis="explicit filename label" if len(roles) == 1 else "missing or conflicting filename labels",
        snapshot_ruleset=CHAIR_NOTE_SNAPSHOT_RULESET_VERSION, raw_filename=filename)
