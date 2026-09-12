from __future__ import annotations

import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from threegpp.documents.archive import inspect_package
from threegpp.documents.models import ContentBlock, ExtractionStatus, NormalizationIdentity
from threegpp.documents.parsers import parser_for
from threegpp.documents.service import _atomic, _gzip, _overall, _sha
from threegpp.ingest.downloader import DownloadConflictError, HTTPDownloader
from threegpp.models import WorkingGroup, normalize_meeting_identifier

from . import rules
from .models import ChairNoteRef, ChairNoteSnapshot, ChairNoteSnapshotRole, SnapshotSelection


class ChairNoteService:
    """Snapshot receipts and parser reuse, independent of all TDoc evidence tables."""

    def __init__(self, root: Path, downloader: HTTPDownloader | None = None):
        self.root = Path(root)
        self.downloader = downloader

    def discover(self, source, meeting: str) -> list[ChairNoteSnapshot]:
        for snapshot in source.discover_chair_notes(meeting):
            path = self._receipt_path(snapshot.artifact.working_group, snapshot.artifact.meeting,
                                      snapshot.snapshot_id)
            if path.exists():
                old = ChairNoteSnapshot.model_validate_json(path.read_text())
                if old.artifact.official_url != snapshot.artifact.official_url:
                    raise DownloadConflictError('Chair Note discovery identity conflicts with receipt')
                # Preserve original discovery time and downloaded provenance on rediscovery.
                snapshot = old.model_copy(update={
                    'artifact': snapshot.artifact.model_copy(update={
                        'discovered_at': old.artifact.discovered_at,
                    }),
                    'role': snapshot.role, 'role_basis': snapshot.role_basis,
                    'snapshot_label_raw': snapshot.snapshot_label_raw,
                    'snapshot_ruleset': snapshot.snapshot_ruleset})
            self._write(snapshot)
        return self.list_snapshots(source.working_group, meeting)

    def list_snapshots(self, working_group, meeting) -> list[ChairNoteSnapshot]:
        base = self._scope('manifests', working_group, meeting)
        snapshots = [
            ChairNoteSnapshot.model_validate_json(path.read_text())
            for path in base.glob('cn-*/receipt.json')
        ]
        if any(
            snapshot.snapshot_ruleset != rules.CHAIR_NOTE_SNAPSHOT_RULESET_VERSION
            or snapshot.artifact.discovery_ruleset
            != rules.CHAIR_NOTE_DISCOVERY_RULESET_VERSION
            for snapshot in snapshots
        ):
            raise ValueError(
                'stale Chair Note discovery/snapshot rules; rediscover the meeting inventory'
            )
        return sorted(
            snapshots,
            key=lambda item: (str(item.artifact.official_url), item.snapshot_id),
        )

    def select(self, working_group, meeting, snapshot_id: str | None = None) -> SnapshotSelection:
        snapshots = self.list_snapshots(working_group, meeting)
        selected = None
        basis = 'no discovered Chair Note snapshot'
        if snapshot_id is not None:
            selected = next((s for s in snapshots if s.snapshot_id == snapshot_id), None)
            if selected is None:
                raise ValueError('requested Chair Note snapshot is not in the discovered inventory')
            basis = 'explicit request'
        elif snapshots:
            finals = [s for s in snapshots if s.role is ChairNoteSnapshotRole.EXPLICIT_FINAL]
            if len(finals) == 1:
                selected, basis = finals[0], 'unique explicitly final snapshot'
            elif len(snapshots) == 1:
                selected, basis = snapshots[0], 'only discovered snapshot; no finality inferred'
            else:
                basis = 'ambiguous snapshots; specify a snapshot ID'
        return SnapshotSelection(selected_snapshot=selected, selection_basis=basis,
                                 available_snapshots=snapshots)

    def fetch(self, working_group, meeting, snapshot_id: str, *, refresh: bool = False) -> ChairNoteSnapshot:
        """Explicit Chair Note acquisition; never calls contribution-body acquisition."""
        snapshot = self.select(working_group, meeting, snapshot_id).selected_snapshot
        raw_path = self._scope('raw', working_group, meeting) / snapshot_id / snapshot.raw_filename
        if snapshot.raw_sha256 and raw_path.exists() and _sha(raw_path) != snapshot.raw_sha256:
            raise DownloadConflictError('cached Chair Note raw checksum conflicts with receipt')
        if not raw_path.exists() or refresh:
            if self.downloader is None:
                with HTTPDownloader() as downloader:
                    downloader.download(str(snapshot.artifact.official_url), raw_path)
            else:
                self.downloader.download(str(snapshot.artifact.official_url), raw_path)
        digest = _sha(raw_path)
        if snapshot.raw_sha256 is not None and snapshot.raw_sha256 != digest:
            raise DownloadConflictError('retrieved Chair Note raw checksum conflicts with receipt')
        snapshot = snapshot.model_copy(update={
            'raw_path': str(raw_path.relative_to(self.root)), 'raw_sha256': digest,
            'retrieved_at': snapshot.retrieved_at or datetime.fromtimestamp(raw_path.stat().st_mtime, timezone.utc),
            'extraction_status': snapshot.extraction_status if snapshot.normalized_path else ExtractionStatus.FETCHED,
        })
        # Persist byte provenance even if package inspection or parsing fails.
        self._write(snapshot)
        try:
            return self._normalize(snapshot, raw_path)
        except Exception as exc:
            snapshot = snapshot.model_copy(update={
                'extraction_status': ExtractionStatus.FAILED, 'warnings': [str(exc)[:500]],
                'normalized_path': None, 'normalized_checksum': None,
                'normalization_identity': None, 'normalization_id': None,
                'block_count': 0, 'tdoc_reference_count': 0})
            self._write(snapshot)
            raise

    def _normalize(self, snapshot, raw_path):
        members = inspect_package(raw_path.read_bytes(), snapshot.raw_filename)
        names = [m.metadata.filename for m in members]
        if len(set(names)) != len(names):
            raise ValueError('duplicate package member names cannot have unambiguous ChairNoteRefs')
        normalization = self._identity(snapshot.raw_sha256, names)
        if snapshot.normalization_identity == normalization and snapshot.normalized_path:
            path = self.root / snapshot.normalized_path
            if path.is_file() and _sha(path) == snapshot.normalized_checksum:
                self._write(snapshot)
                return snapshot
        blocks, statuses, warnings = [], [], []
        for member in members:
            parser = parser_for(member.metadata.filename)
            if parser is None:
                statuses.append(ExtractionStatus.UNSUPPORTED_FORMAT)
                warnings.append(f'{member.metadata.filename}: unsupported member format')
                continue
            parsed, status, messages = parser.parse(member.data, member.metadata.filename)
            statuses.append(status)
            warnings.extend(f'{member.metadata.filename}: {message}' for message in messages)
            for block in parsed:
                number = len(blocks) + 1
                blocks.append(block.model_copy(update={'block_id': f'b{number:06d}', 'order': number}))
        normalization_id = rules.identity(normalization.model_dump(mode='json'))
        base = self._scope('normalized', snapshot.artifact.working_group, snapshot.artifact.meeting)
        path = base / snapshot.snapshot_id / normalization_id / 'blocks.jsonl.gz'
        payload = _gzip(''.join(json.dumps(b.model_dump(mode='json'), sort_keys=True,
                                         ensure_ascii=False) + '\n' for b in blocks).encode())
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic(path, payload)
        snapshot = snapshot.model_copy(update={
            'schema_version': rules.CHAIR_NOTE_SCHEMA_VERSION,
            'normalization_identity': normalization, 'normalization_id': normalization_id,
            'normalized_path': str(path.relative_to(self.root)), 'normalized_checksum': _sha(path),
            'extraction_status': _overall(statuses), 'block_count': len(blocks),
            'tdoc_reference_count': sum(len(list(rules.TDOC_REFERENCE.finditer(text)))
                                        for block in blocks for text in block_texts(block)),
            'warnings': warnings})
        self._write(snapshot)
        return snapshot

    def inspect(self, working_group, meeting, snapshot_id: str):
        snapshot = self.select(working_group, meeting, snapshot_id).selected_snapshot
        if snapshot.normalized_path is None:
            return {'snapshot': snapshot.model_dump(mode='json'), 'blocks': []}
        snapshot, blocks = self.load_blocks(working_group, meeting, snapshot_id)
        return {'snapshot': snapshot.model_dump(mode='json'),
                'blocks': [block.model_dump(mode='json') for block in blocks]}

    def load_blocks(self, working_group, meeting, snapshot_id):
        snapshot = self.select(working_group, meeting, snapshot_id).selected_snapshot
        if snapshot.normalization_identity is None or not snapshot.normalized_path:
            raise ValueError('Chair Note is not normalized; explicitly fetch the selected snapshot first')
        expected = self._identity(snapshot.raw_sha256, snapshot.normalization_identity.parser_members)
        if (snapshot.schema_version != rules.CHAIR_NOTE_SCHEMA_VERSION
                or expected != snapshot.normalization_identity
                or snapshot.normalization_id != rules.identity(expected.model_dump(mode='json'))):
            raise ValueError('stale Chair Note normalization identity; explicitly normalize cached snapshot')
        raw = self.root / snapshot.raw_path
        path = self.root / snapshot.normalized_path
        if not raw.is_file() or _sha(raw) != snapshot.raw_sha256:
            raise DownloadConflictError('Chair Note raw evidence missing or checksum-conflicting')
        if not path.is_file() or _sha(path) != snapshot.normalized_checksum:
            raise ValueError('stale Chair Note normalized checksum')
        blocks = [ContentBlock.model_validate_json(line) for line in gzip.decompress(path.read_bytes()).decode().splitlines()]
        if len(blocks) != snapshot.block_count or len({(b.member_filename, b.block_id) for b in blocks}) != len(blocks):
            raise ValueError('Chair Note block identity/count mismatch')
        return snapshot, blocks

    def resolve_ref(self, ref: ChairNoteRef) -> dict:
        snapshot, blocks = self.load_blocks(ref.working_group, ref.meeting, ref.snapshot_id)
        if (ref.normalization_id, ref.normalized_checksum) != (snapshot.normalization_id, snapshot.normalized_checksum):
            raise ValueError('stale ChairNoteRef')
        block = next((b for b in blocks if (b.member_filename, b.block_id) == (ref.member, ref.block_id)), None)
        if block is None:
            raise ValueError('ChairNoteRef block is missing')
        expected = make_ref(snapshot, block, row=ref.row_index, cell=ref.cell_index,
                            start=ref.char_start, end=ref.char_end)
        if ref != expected:
            raise ValueError('ChairNoteRef structure does not match source')
        if ref.row_index is not None:
            if ref.cell_index is None or not block.rows or ref.row_index >= len(block.rows) or ref.cell_index >= len(block.rows[ref.row_index]):
                raise ValueError('ChairNoteRef table locator is invalid')
            text = cell_text(block.rows[ref.row_index][ref.cell_index])
        else:
            if ref.cell_index is not None:
                raise ValueError('cell requires a row')
            text = block.text or ''
        if ref.char_start is not None or ref.char_end is not None:
            if ref.char_start is None or ref.char_end is None or not 0 <= ref.char_start <= ref.char_end <= len(text):
                raise ValueError('ChairNoteRef character span is invalid')
            text = text[ref.char_start:ref.char_end]
        return {'snapshot': snapshot.model_dump(mode='json'), 'block': block.model_dump(mode='json'),
                'literal_text': text}

    def _identity(self, raw_sha, member_names):
        return NormalizationIdentity(raw_sha256=raw_sha,
            parser_members={name: f'{p.name}@{p.version}' if (p := parser_for(name)) else 'unsupported'
                            for name in member_names},
            normalized_schema_version=rules.CHAIR_NOTE_SCHEMA_VERSION)

    def _scope(self, layer, group, meeting):
        return self.root / layer / 'chair-notes' / WorkingGroup.parse(group).value.lower() / normalize_meeting_identifier(meeting)

    def _receipt_path(self, group, meeting, snapshot_id):
        if not re.fullmatch(r'cn-[0-9a-f]{64}', snapshot_id):
            raise ValueError('invalid Chair Note snapshot ID')
        return self._scope('manifests', group, meeting) / snapshot_id / 'receipt.json'

    def _write(self, snapshot):
        path = self._receipt_path(snapshot.artifact.working_group, snapshot.artifact.meeting, snapshot.snapshot_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic(path, (snapshot.model_dump_json(indent=2) + '\n').encode())


def cell_text(value):
    return '' if value is None else str(value)


def block_texts(block):
    return [cell_text(cell) for row in block.rows for cell in row] if block.rows is not None else [block.text or '']


def make_ref(snapshot, block, *, row=None, cell=None, start=None, end=None):
    return ChairNoteRef(working_group=snapshot.artifact.working_group, meeting=snapshot.artifact.meeting,
        snapshot_id=snapshot.snapshot_id, normalization_id=snapshot.normalization_id,
        normalized_checksum=snapshot.normalized_checksum, member=block.member_filename,
        block_id=block.block_id, block_type=block.type, heading_path=block.heading_path,
        page=block.page_number, sheet=block.sheet_name, row_index=row, cell_index=cell,
        char_start=start, char_end=end)
