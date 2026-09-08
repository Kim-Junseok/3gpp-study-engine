from datetime import datetime, timezone

import httpx
import pytest

from threegpp.chair_notes.models import ChairNoteSnapshotRole
from threegpp.chair_notes.rules import discovered_snapshot
from threegpp.sources import RAN1Source, RAN2Source

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def snapshot(filename='chair_notes_final.docx', group='RAN1', meeting='126'):
    directory = f'https://www.3gpp.org/ftp/fixture/{group}/{meeting}/Inbox/Chair_notes/'
    return discovered_snapshot(group, meeting, directory + filename, directory, NOW)


@pytest.mark.parametrize('source_type,folder', [(RAN1Source, 'Chair_notes'), (RAN2Source, 'Chair_Notes')])
def test_discovery_preserves_directory_case_and_never_fetches_files(source_type, folder):
    calls = []
    def handler(request):
        calls.append(str(request.url))
        path = request.url.path
        if path.endswith('/TSGR1_126/') or path.endswith('/TSGR2_126/'):
            html = '<a href="Inbox/">Inbox</a><a href="Docs/">Docs</a>'
        elif path.endswith('/Inbox/'):
            html = f'<a href="{folder}/">{folder}</a><a href="Other/">Other</a>'
        elif path.endswith('/' + folder + '/'):
            html = '<a href="chair_notes_eom1.docx">chair_notes_eom1.docx</a>'
        else:
            raise AssertionError(f'unexpected acquisition: {path}')
        return httpx.Response(200, text=html)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = source_type(client=client)
        items = source.discover_chair_notes('126')
        assert len(items) == 1
        assert str(items[0].artifact.source_directory).endswith('/' + folder + '/')
        assert str(items[0].artifact.official_url).endswith('/' + folder + '/chair_notes_eom1.docx')
        assert items[0].raw_sha256 is None and items[0].retrieved_at is None
        assert len(calls) == 3


@pytest.mark.parametrize('filename,label,role', [
    ('chair_notes_eom1.docx','eom1',ChairNoteSnapshotRole.EOM),
    ('chair_notes_eom2.docx','eom2',ChairNoteSnapshotRole.EOM),
    ('chair_notes_final.docx','final',ChairNoteSnapshotRole.EXPLICIT_FINAL),
    ('chair_notes_revision.docx','revision',ChairNoteSnapshotRole.INTERMEDIATE),
    ('chair_notes.docx',None,ChairNoteSnapshotRole.UNKNOWN),
    ('chair_notes_final_eom2.docx','final eom2',ChairNoteSnapshotRole.UNKNOWN),
])
def test_filename_roles_do_not_infer_finality(filename, label, role):
    first = snapshot(filename)
    assert first.snapshot_label_raw == label and first.role is role
    assert first == snapshot(filename)


import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook
from threegpp.chair_notes.service import ChairNoteService, make_ref
from threegpp.documents.models import ExtractionStatus
from threegpp.ingest.downloader import HTTPDownloader, DownloadConflictError


def docx_bytes():
    out = io.BytesIO()
    xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>HARQ related aspects</w:t></w:r></w:p>
    <w:p><w:r><w:t>Fast ARQ discussion. R1-2601001 R1-2601002</w:t></w:r></w:p>
    <w:p><w:r><w:t>Agreement: Study Option A.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>CSI feedback</w:t></w:r></w:p>
    <w:p><w:r><w:t>R1-2602001</w:t></w:r></w:p>
    </w:body></w:document>'''
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    return out.getvalue()


def register(service, snapshots):
    source = SimpleNamespace(working_group='RAN1', discover_chair_notes=lambda meeting: snapshots)
    return service.discover(source, '126')


@pytest.fixture
def chair_store(tmp_path):
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=docx_bytes())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        service = ChairNoteService(tmp_path, HTTPDownloader(client=client))
        register(service, [snapshot()])
        yield service, calls


def test_snapshot_selection_coexistence_and_cached_parser_reuse(chair_store, monkeypatch):
    service, calls = chair_store
    eom1, eom2, final = snapshot('chair_notes_eom1.docx'), snapshot('chair_notes_eom2.docx'), snapshot()
    register(service, [eom1, eom2])
    assert service.select('RAN1', '126').selected_snapshot.snapshot_id == final.snapshot_id
    for item in [eom1, eom2, final]:
        service.fetch('RAN1', '126', item.snapshot_id)
    assert len(calls) == 3
    receipts = service.list_snapshots('RAN1', '126')
    assert len({s.raw_path for s in receipts}) == 3
    assert len({s.normalized_path for s in receipts}) == 3
    assert all(s.normalized_checksum for s in receipts)
    first = service.select('RAN1','126',final.snapshot_id).selected_snapshot
    from threegpp.documents.parsers import parser_for
    monkeypatch.setattr(parser_for('a.docx'), 'parse', lambda *args: pytest.fail('cache should reuse normalization'))
    assert service.fetch('RAN1','126',final.snapshot_id) == first
    assert len(calls) == 3
    assert 'blocks' not in json.loads(service._receipt_path('RAN1','126',final.snapshot_id).read_text())


def test_ambiguous_snapshots_require_explicit_selection(tmp_path):
    service = ChairNoteService(tmp_path)
    a,b = snapshot('chair_notes_eom1.docx'),snapshot('chair_notes_eom2.docx')
    register(service,[a,b])
    result=service.select('RAN1','126')
    assert result.selected_snapshot is None and 'ambiguous' in result.selection_basis
    assert service.select('RAN1','126',a.snapshot_id).selected_snapshot == a


def test_ref_resolution_and_checksum_safety(chair_store):
    service, calls=chair_store
    s=service.fetch('RAN1','126',snapshot().snapshot_id)
    s,blocks=service.load_blocks('RAN1','126',s.snapshot_id)
    ref=make_ref(s,blocks[1],start=21,end=31)
    assert service.resolve_ref(ref)['literal_text'] == 'R1-2601001'
    with pytest.raises(ValueError,match='missing'):
        service.resolve_ref(ref.model_copy(update={'block_id':'b999999'}))
    (service.root/s.normalized_path).write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):
        service.resolve_ref(ref)
    rebuilt=service.fetch('RAN1','126',s.snapshot_id)
    assert rebuilt.normalized_checksum == s.normalized_checksum
    assert len(calls)==1
    (service.root/s.raw_path).write_bytes(b'corrupt')
    with pytest.raises(DownloadConflictError):
        service.fetch('RAN1','126',s.snapshot_id)


@pytest.mark.parametrize('extension',['xlsx','xls'])
def test_spreadsheet_parser_reuse_and_row_cell_locators(tmp_path,extension):
    out=io.BytesIO()
    if extension=='xlsx':
        book=Workbook(); sheet=book.active;sheet.title='Notes'
        sheet.append(['Topic','TDoc']);sheet.append(['HARQ','R1-2601001']);book.save(out)
    else:
        import xlwt
        book=xlwt.Workbook();sheet=book.add_sheet('Notes')
        for r,row in enumerate([['Topic','TDoc'],['HARQ','R1-2601001']]):
            for c,value in enumerate(row):sheet.write(r,c,value)
        book.save(out)
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=out.getvalue()))) as client:
        service=ChairNoteService(tmp_path,HTTPDownloader(client=client))
        item=snapshot('chair_notes_final.'+extension);register(service,[item])
        s=service.fetch('RAN1','126',item.snapshot_id)
        s,blocks=service.load_blocks('RAN1','126',item.snapshot_id)
        assert s.normalization_identity.parser_members[item.raw_filename]=='spreadsheet@1'
        ref=make_ref(s,blocks[0],row=1,cell=1,start=0,end=10)
        assert ref.sheet=='Notes' and service.resolve_ref(ref)['literal_text']=='R1-2601001'


def test_unsupported_chair_format_stays_explicit(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'unsupported'))) as client:
        service=ChairNoteService(tmp_path,HTTPDownloader(client=client));item=snapshot('chair_notes_final.pptx')
        register(service,[item]);result=service.fetch('RAN1','126',item.snapshot_id)
        assert result.extraction_status is ExtractionStatus.UNSUPPORTED_FORMAT
        assert result.block_count==0


from threegpp.chair_notes.coverage import DiscussionCoverageService, discussion_sections
from threegpp.chair_notes.models import (
    AssociationBasis, DiscussionCoverageRequest, DiscussionCoverageState, ReferenceResolutionState,
)
from threegpp.db import MetadataRepository
from threegpp.documents.models import ContentBlock
from threegpp.models import TDocMetadata


def test_sections_positive_only_metadata_join_and_no_meeting_semantics(chair_store):
    service,calls=chair_store
    s=service.fetch('RAN1','126',snapshot().snapshot_id)
    with MetadataRepository(service.root/'metadata.duckdb') as repo:
        repo.upsert_tdoc(TDocMetadata(tdoc_id='R1-2601001',working_group='RAN1',meeting='126',
            title='Official HARQ title',organizations=['Example Inc.'],status='available',
            source_url='https://www.3gpp.org/ftp/Docs/R1-2601001.zip'))
        repo.upsert_tdoc(TDocMetadata(tdoc_id='R1-2601002',working_group='RAN1',meeting='125',
            title='Earlier HARQ contribution',organizations=['Other Inc.'],official_list_present=True))
        repo.upsert_tdoc(TDocMetadata(tdoc_id='R1-2601003',working_group='RAN1',meeting='126',
            title='HARQ metadata only'))
        coverage=DiscussionCoverageService(repo,service.root)
        req=DiscussionCoverageRequest(working_group='RAN1',meeting='126',query='HARQ Fast-ARQ')
        result=coverage.build_coverage(req)
        assert result==coverage.build_coverage(req)
        assert [c.tdoc_id for c in result.chair_note_confirmed]==['R1-2601001','R1-2601002']
        assert [c.tdoc_id for c in result.metadata_relevant_only]==['R1-2601003']
        a,b=result.chair_note_confirmed
        assert a.metadata.title=='Official HARQ title' and a.metadata.organizations==['Example Inc.']
        assert a.resolution_state is ReferenceResolutionState.CURRENT_MEETING_METADATA
        assert b.resolution_state is ReferenceResolutionState.OTHER_KNOWN_METADATA
        assert b.metadata.meeting=='125' and b.availability.value=='listed_only'
        assert result.metadata_relevant_only[0].coverage_state is DiscussionCoverageState.METADATA_RELEVANT_ONLY
        assert 'not_discussed' not in result.model_dump_json()
        assert repo.connection.execute('select count(*) from semantic_evidence').fetchone()[0]==0
        assert repo.connection.execute('select count(*) from tdoc_documents').fetchone()[0]==0
        assert len(calls)==1
        for c in result.chair_note_confirmed:
            for record in c.associations:
                assert service.resolve_ref(record.reference.source_ref)['literal_text']==record.reference.raw_reference
        assert 'R1-2602001' not in {c.tdoc_id for c in result.chair_note_confirmed}
        plan=coverage.plan_topic_corpus(req)
        assert len(calls)==1
        assert [i.candidate.tdoc_id for i in plan.items if i.fetch_eligible]==['R1-2601001']
        fetch=coverage.compile_fetch_plan(plan,['R1-2601001'])
        assert len(fetch.items)==1 and fetch.items[0].source_url==a.metadata.source_url
        with pytest.raises(ValueError,match='not fetch eligible'):
            coverage.compile_fetch_plan(plan,['R1-2601002'])
        assert len(calls)==1


def test_unresolved_unknown_and_ambiguous_references(chair_store):
    service,_=chair_store;service.fetch('RAN1','126',snapshot().snapshot_id)
    with MetadataRepository(service.root/'metadata.duckdb') as repo:
        coverage=DiscussionCoverageService(repo,service.root)
        req=DiscussionCoverageRequest(working_group='RAN1',meeting='126',query='HARQ')
        result=coverage.build_coverage(req)
        assert len(result.unresolved_references)==2
        assert all(x.metadata is None and x.availability is None for x in result.unresolved_references)
        before=result.coverage_id
        repo.upsert_tdoc(TDocMetadata(tdoc_id='R1-2601001',working_group='RAN1',meeting='126'))
        changed=coverage.build_coverage(req)
        assert changed.coverage_id!=before and changed.chair_note_confirmed[0].availability.value=='unknown'
        plan=coverage.plan_topic_corpus(req)
        assert not any(i.fetch_eligible for i in plan.items)
        repo.upsert_tdoc(TDocMetadata(tdoc_id='R1-2601001',working_group='RAN1',meeting='125'))
        ambiguous=coverage.build_coverage(req).unresolved_references[0]
        assert ambiguous.resolution_state is ReferenceResolutionState.AMBIGUOUS
        assert ambiguous.metadata is None and len(ambiguous.metadata_candidates)==2


def test_explicit_unresolved_reference_preserves_literal_without_fabrication(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b'HARQ R1-2699999'))) as client:
        chairs = ChairNoteService(tmp_path, HTTPDownloader(client=client))
        item = snapshot('chair_notes_final.txt')
        register(chairs, [item])
        chairs.fetch('RAN1', '126', item.snapshot_id)
        with MetadataRepository(tmp_path / 'metadata.duckdb') as repo:
            result = DiscussionCoverageService(repo, tmp_path).build_coverage(
                DiscussionCoverageRequest(
                    working_group='RAN1', meeting='126', query='HARQ'))
            assert len(result.unresolved_references) == 1
            unresolved = result.unresolved_references[0]
            assert unresolved.tdoc_id == 'R1-2699999'
            assert unresolved.resolution_state is ReferenceResolutionState.UNRESOLVED
            assert unresolved.metadata is None
            assert unresolved.metadata_candidates == []
            assert unresolved.availability is None
            reference = unresolved.associations[0].reference
            assert reference.raw_reference == 'R1-2699999'
            assert chairs.resolve_ref(reference.source_ref)['literal_text'] == 'R1-2699999'


def test_table_association_stays_in_row(chair_store):
    service,_=chair_store;s=service.fetch('RAN1','126',snapshot().snapshot_id)
    blocks=[ContentBlock(block_id='b000001',type='table',member_filename='fixture.docx',order=1,
        rows=[['HARQ','R1-2601001'],['CSI','R1-2602001']])]
    sections,records,_=discussion_sections(s,blocks,'HARQ')
    assert len(sections)==len(records)==1
    r=records[0]
    assert r.association_basis is AssociationBasis.SAME_TABLE_ROW
    assert r.topic_anchor.source_ref.row_index==0 and r.topic_anchor.source_ref.cell_index==0
    assert r.reference.source_ref.row_index==0 and r.reference.source_ref.cell_index==1
    assert r.reference.source_ref.char_start==0 and r.reference.source_ref.char_end==10
    assert r.reference.tdoc_id=='R1-2601001'


@pytest.mark.parametrize('boundary',['heading','member','table'])
def test_section_leakage_boundaries(chair_store,boundary):
    service,_=chair_store;s=service.fetch('RAN1','126',snapshot().snapshot_id)
    blocks=[ContentBlock(block_id='b000001',type='heading',text='HARQ',member_filename='a.docx',order=1,
                         heading_path=['HARQ'],heading_level=1)]
    if boundary=='heading':
        blocks.append(ContentBlock(block_id='b000002',type='heading',text='CSI',member_filename='a.docx',order=2,
                                   heading_path=['CSI'],heading_level=1))
    if boundary=='table':
        blocks.append(ContentBlock(block_id='b000002',type='table',rows=[['CSI']],member_filename='a.docx',order=2))
    blocks.append(ContentBlock(block_id='b000003',type='paragraph',text='R1-2602001',
        member_filename='b.docx' if boundary=='member' else 'a.docx',order=3))
    _,records,_=discussion_sections(s,blocks,'HARQ')
    assert records==[]


@pytest.mark.parametrize('version',['DISCUSSION_SECTION_RULESET_VERSION','TDOC_REFERENCE_RULESET_VERSION'])
def test_coverage_rebuilds_on_rule_change(chair_store,monkeypatch,version):
    from threegpp.chair_notes import rules
    service,_=chair_store;service.fetch('RAN1','126',snapshot().snapshot_id)
    with MetadataRepository(service.root/'metadata.duckdb') as repo:
        coverage=DiscussionCoverageService(repo,service.root)
        req=DiscussionCoverageRequest(working_group='RAN1',meeting='126',query='HARQ')
        first=coverage.build_coverage(req)
        monkeypatch.setattr(rules,version,'changed-for-test')
        assert coverage.build_coverage(req).coverage_id!=first.coverage_id


def test_parser_and_schema_changes_invalidate_refs(chair_store,monkeypatch):
    from threegpp.chair_notes import rules
    from threegpp.documents.parsers import parser_for
    service,calls=chair_store;s=service.fetch('RAN1','126',snapshot().snapshot_id)
    s,blocks=service.load_blocks('RAN1','126',s.snapshot_id);ref=make_ref(s,blocks[1])
    monkeypatch.setattr(parser_for('a.docx'),'version','2')
    with pytest.raises(ValueError,match='stale'):
        service.resolve_ref(ref)
    second=service.fetch('RAN1','126',s.snapshot_id)
    assert second.normalization_id!=s.normalization_id and second.raw_sha256==s.raw_sha256
    assert (service.root/s.normalized_path).exists()
    with pytest.raises(ValueError,match='stale'):
        service.resolve_ref(ref)
    monkeypatch.setattr(rules,'CHAIR_NOTE_SCHEMA_VERSION','2')
    with pytest.raises(ValueError,match='stale'):
        service.load_blocks('RAN1','126',s.snapshot_id)
    third=service.fetch('RAN1','126',s.snapshot_id)
    assert third.normalization_id!=second.normalization_id and len(calls)==1


@pytest.mark.parametrize(
    'version',
    ['CHAIR_NOTE_DISCOVERY_RULESET_VERSION', 'CHAIR_NOTE_SNAPSHOT_RULESET_VERSION'],
)
def test_changed_inventory_rules_require_rediscovery(chair_store, monkeypatch, version):
    from threegpp.chair_notes import rules

    service, _ = chair_store
    monkeypatch.setattr(rules, version, 'changed-for-test')
    with pytest.raises(ValueError, match='rediscover'):
        service.list_snapshots('RAN1', '126')
    refreshed = service.discover(
        SimpleNamespace(
            working_group='RAN1',
            discover_chair_notes=lambda meeting: [snapshot()],
        ),
        '126',
    )
    assert len(refreshed) == 1


def test_already_local_plan_reuses_existing_fetch_pipeline(chair_store,monkeypatch):
    from threegpp.documents import DocumentService, FetchPlanner
    from threegpp.search import EvidenceSearchService
    from threegpp.evidence import EvidenceExtractionService
    service,calls=chair_store;service.fetch('RAN1','126',snapshot().snapshot_id)
    with MetadataRepository(service.root/'metadata.duckdb') as repo:
        repo.upsert_tdoc(TDocMetadata(tdoc_id='R1-2601001',working_group='RAN1',meeting='126',
            title='HARQ contribution',organizations=['Example Inc.'],
            source_url='https://www.3gpp.org/ftp/Docs/R1-2601001.txt'))
        with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'Proposal: Study HARQ.'))) as client:
            docs=DocumentService(repo,service.root,HTTPDownloader(client=client))
            fetch_plan=FetchPlanner(repo).explicit([('RAN1','126','R1-2601001')])
            receipt=docs.execute(fetch_plan)[0].receipt
        EvidenceSearchService(repo,service.root).index_document(receipt)
        EvidenceExtractionService(repo,service.root).extract_document(receipt)
        monkeypatch.setattr(HTTPDownloader,'download',lambda *args:pytest.fail('coverage must not download'))
        monkeypatch.setattr(DocumentService,'execute',lambda *args:pytest.fail('coverage must not execute fetch'))
        coverage=DiscussionCoverageService(repo,service.root)
        plan=coverage.plan_topic_corpus(DiscussionCoverageRequest(working_group='RAN1',meeting='126',query='HARQ'))
        item=next(i for i in plan.items if i.candidate.tdoc_id=='R1-2601001')
        assert item.fetch_needed is False and not item.fetch_eligible
        assert item.candidate.local_state.raw_verified and item.candidate.local_state.normalized
        assert item.candidate.local_state.indexed_status=='INDEXED'
        assert item.candidate.local_state.semantic_status=='EXTRACTED'
        assert len(calls)==1


def test_refreshed_raw_conflict_is_loud_and_preserves_bytes(chair_store,monkeypatch):
    service,_=chair_store;item=service.fetch('RAN1','126',snapshot().snapshot_id)
    raw=service.root/item.raw_path;original=raw.read_bytes()
    monkeypatch.setattr(service.downloader,'_get_bytes',lambda url:b'changed official bytes')
    with pytest.raises(DownloadConflictError):
        service.fetch('RAN1','126',item.snapshot_id,refresh=True)
    assert raw.read_bytes()==original


def test_unsafe_archive_is_rejected_and_receipt_retains_raw_provenance(tmp_path):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as archive:archive.writestr('../outside.txt','unsafe')
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=out.getvalue()))) as client:
        service=ChairNoteService(tmp_path,HTTPDownloader(client=client));item=snapshot('chair_notes_final.zip')
        register(service,[item])
        with pytest.raises(ValueError,match='unsafe archive'):
            service.fetch('RAN1','126',item.snapshot_id)
        receipt=service.select('RAN1','126',item.snapshot_id).selected_snapshot
        assert receipt.raw_sha256 and receipt.retrieved_at and receipt.normalized_path is None
        assert receipt.extraction_status is ExtractionStatus.FAILED
        assert not (tmp_path/'outside.txt').exists()


def test_cli_coverage_and_fetch_plan_handoff(chair_store,capsys,monkeypatch):
    from threegpp.cli import main
    from threegpp.documents.models import TDocFetchPlan
    service,_=chair_store;item=service.fetch('RAN1','126',snapshot().snapshot_id)
    db=service.root/'metadata.duckdb'
    with MetadataRepository(db) as repo:
        repo.upsert_tdoc(TDocMetadata(tdoc_id='R1-2601001',working_group='RAN1',meeting='126',
            source_url='https://www.3gpp.org/ftp/Docs/R1-2601001.zip'))
    monkeypatch.setattr(HTTPDownloader,'download',lambda *args:pytest.fail('offline command downloaded'))
    common=['--db',str(db),'--data-dir',str(service.root)]
    args=['--wg','RAN1','--meeting','126','--query','HARQ']
    assert main(common+['discussion-coverage']+args)==0
    coverage=json.loads(capsys.readouterr().out)
    assert coverage['chair_note_confirmed'][0]['tdoc_id']=='R1-2601001'
    output=service.root/'selected.yaml'
    assert main(common+['plan-topic-corpus']+args+['--tdoc','R1-2601001','--fetch-plan',str(output)])==0
    plan=json.loads(capsys.readouterr().out)
    assert TDocFetchPlan.from_yaml(output).items[0].tdoc_id=='R1-2601001'
    assert plan['items'][0]['candidate']['associations']
    assert main(common+['inspect-chair-note','--wg','RAN1','--meeting','126','--snapshot',item.snapshot_id])==0
    assert json.loads(capsys.readouterr().out)['snapshot']['raw_sha256']==item.raw_sha256


def test_stale_plan_cannot_compile_after_metadata_change(chair_store):
    service,_=chair_store;service.fetch('RAN1','126',snapshot().snapshot_id)
    with MetadataRepository(service.root/'metadata.duckdb') as repo:
        record=TDocMetadata(tdoc_id='R1-2601001',working_group='RAN1',meeting='126',
                           source_url='https://www.3gpp.org/ftp/Docs/R1-2601001.zip')
        repo.upsert_tdoc(record)
        coverage=DiscussionCoverageService(repo,service.root)
        request=DiscussionCoverageRequest(working_group='RAN1',meeting='126',query='HARQ')
        plan=coverage.plan_topic_corpus(request)
        repo.upsert_tdoc(record.model_copy(update={'title':'changed official title'}))
        with pytest.raises(ValueError,match='stale'):
            coverage.compile_fetch_plan(plan,['R1-2601001'])


def test_missing_raw_does_not_claim_normalized_reuse(chair_store):
    from threegpp.documents import DocumentService, FetchPlanner
    service, _ = chair_store
    service.fetch('RAN1', '126', snapshot().snapshot_id)
    with MetadataRepository(service.root / 'metadata.duckdb') as repo:
        metadata = TDocMetadata(
            tdoc_id='R1-2601001', working_group='RAN1', meeting='126',
            source_url='https://www.3gpp.org/ftp/Docs/R1-2601001.txt')
        repo.upsert_tdoc(metadata)
        with httpx.Client(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b'HARQ body'))) as client:
            outcome = DocumentService(repo, service.root, HTTPDownloader(client=client)).execute(
                FetchPlanner(repo).explicit([('RAN1', '126', 'R1-2601001')]))[0]
        Path(outcome.receipt.raw.local_path).unlink()
        plan = DiscussionCoverageService(repo, service.root).plan_topic_corpus(
            DiscussionCoverageRequest(working_group='RAN1', meeting='126', query='HARQ'))
        item = next(value for value in plan.items if value.candidate.tdoc_id == 'R1-2601001')
        assert not item.candidate.local_state.raw_verified
        assert not item.candidate.local_state.normalized
        assert item.fetch_needed and item.fetch_eligible


def test_section_window_and_batch_limits_are_explicit(chair_store):
    from threegpp.chair_notes import rules
    service,_=chair_store;s=service.fetch('RAN1','126',snapshot().snapshot_id)
    blocks=[ContentBlock(block_id='b000001',type='heading',text='HARQ',member_filename='a.docx',order=1)]
    blocks.extend(ContentBlock(block_id=f'b{i:06d}',type='paragraph',text='context',member_filename='a.docx',order=i)
                  for i in range(2,rules.MAX_SECTION_BLOCKS+1))
    blocks.append(ContentBlock(block_id='b000201',type='paragraph',text='R1-2699999',member_filename='a.docx',order=201))
    sections,records,truncated=discussion_sections(s,blocks,'HARQ')
    assert sections[0].block_count==rules.MAX_SECTION_BLOCKS and not records and truncated==1
    with MetadataRepository(service.root/'metadata.duckdb') as repo:
        coverage=DiscussionCoverageService(repo,service.root)
        plan=coverage.plan_topic_corpus(DiscussionCoverageRequest(working_group='RAN1',meeting='126',query='HARQ'))
        with pytest.raises(ValueError,match='1..50'):
            coverage.compile_fetch_plan(plan,[f'R1-{i:07d}' for i in range(51)])


def test_coverage_output_caps_reference_associations(chair_store):
    service, _ = chair_store
    selected = service.fetch('RAN1', '126', snapshot().snapshot_id)
    selected, blocks = service.load_blocks('RAN1', '126', selected.snapshot_id)
    path = service.root / selected.normalized_path
    block = blocks[1].model_copy(update={
        'text': 'HARQ ' + ' '.join(f'R1-{2601000 + index}' for index in range(20))})
    from threegpp.documents.service import _gzip, _sha
    payload = _gzip((block.model_dump_json() + '\n').encode())
    path.write_bytes(payload)
    selected = selected.model_copy(update={
        'normalized_checksum': _sha(path), 'block_count': 1, 'tdoc_reference_count': 20})
    service._write(selected)
    with MetadataRepository(service.root / 'metadata.duckdb') as repo:
        result = DiscussionCoverageService(repo, service.root).build_coverage(
            DiscussionCoverageRequest(
                working_group='RAN1', meeting='126', query='HARQ', limit=3))
        assert result.diagnostics['explicit_reference_occurrences'] == 20
        assert result.diagnostics['explicit_reference_occurrences_output'] == 3
        assert len(result.unresolved_references) == 3
        assert sum(len(item.associations) for item in result.unresolved_references) == 3
        assert any('truncated discussion associations' in item for item in result.limitations)


def test_partial_package_cache_keeps_status_and_member_boundaries(tmp_path):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as archive:
        archive.writestr('one.txt','HARQ discussion R1-2601001')
        archive.writestr('empty.txt','')
        archive.writestr('two.txt','R1-2602001')
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=out.getvalue()))) as client:
        service=ChairNoteService(tmp_path,HTTPDownloader(client=client));item=snapshot('chair_notes_final.zip')
        register(service,[item]);first=service.fetch('RAN1','126',item.snapshot_id)
        assert first.extraction_status is ExtractionStatus.PARTIALLY_PARSED
        assert service.fetch('RAN1','126',item.snapshot_id)==first
        s,blocks=service.load_blocks('RAN1','126',item.snapshot_id)
        _,records,_=discussion_sections(s,blocks,'HARQ')
        assert [r.reference.tdoc_id for r in records]==['R1-2601001']


def test_snapshot_specific_coverage_is_not_silently_unioned(tmp_path):
    def handler(request):
        target='R1-2601001' if 'eom1' in request.url.path else 'R1-2601002'
        return httpx.Response(200,content=f'HARQ {target}'.encode())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        service=ChairNoteService(tmp_path,HTTPDownloader(client=client))
        a,b=snapshot('chair_notes_eom1.txt'),snapshot('chair_notes_eom2.txt')
        register(service,[a,b])
        for s in [a,b]:service.fetch('RAN1','126',s.snapshot_id)
        with MetadataRepository(tmp_path/'metadata.duckdb') as repo:
            coverage=DiscussionCoverageService(repo,tmp_path)
            req=DiscussionCoverageRequest(working_group='RAN1',meeting='126',query='HARQ')
            assert not coverage.build_coverage(req).unresolved_references
            for s,target in [(a,'R1-2601001'),(b,'R1-2601002')]:
                result=coverage.build_coverage(req.model_copy(update={'chair_note_snapshot':s.snapshot_id}))
                assert [r.tdoc_id for r in result.unresolved_references]==[target]
                assert result.unresolved_references[0].associations[0].reference.source_ref.snapshot_id==s.snapshot_id


def test_missing_inventory_is_offline_and_metadata_remains_positive_only(tmp_path,monkeypatch):
    monkeypatch.setattr(HTTPDownloader,'download',lambda *args:pytest.fail('must stay offline'))
    with MetadataRepository(tmp_path/'metadata.duckdb') as repo:
        repo.upsert_tdoc(TDocMetadata(tdoc_id='R1-2601234',working_group='RAN1',meeting='126',title='HARQ'))
        result=DiscussionCoverageService(repo,tmp_path).build_coverage(
            DiscussionCoverageRequest(working_group='RAN1',meeting='126',query='HARQ'))
        assert result.selection.selected_snapshot is None
        assert len(result.metadata_relevant_only)==1 and not result.chair_note_confirmed
        assert result.metadata_relevant_only[0].coverage_state is DiscussionCoverageState.METADATA_RELEVANT_ONLY


def test_cli_discovery_and_explicit_chair_fetch(tmp_path,monkeypatch,capsys):
    import threegpp.cli as cli
    item=snapshot('chair_notes_final.txt')
    source=SimpleNamespace(working_group='RAN1',discover_chair_notes=lambda meeting:[item],close=lambda:None)
    monkeypatch.setattr(cli,'source_for',lambda wg:source)
    calls=[]
    def bytes_for(self,url):
        calls.append(url)
        return b'HARQ R1-2601001'
    monkeypatch.setattr(HTTPDownloader,'_get_bytes',bytes_for)
    common=['--data-dir',str(tmp_path)]
    scope=['--wg','RAN1','--meeting','126']
    assert cli.main(common+['discover-chair-notes']+scope)==0
    assert not calls and json.loads(capsys.readouterr().out)[0]['raw_sha256'] is None
    assert cli.main(common+['inspect-chair-note']+scope+['--snapshot',item.snapshot_id])==0
    assert not calls and not json.loads(capsys.readouterr().out)['blocks']
    assert cli.main(common+['fetch-chair-note']+scope+['--snapshot',item.snapshot_id])==0
    assert calls==[str(item.artifact.official_url)]
    assert json.loads(capsys.readouterr().out)['block_count']==1
