from __future__ import annotations

from datetime import UTC, datetime

import pytest

from threegpp.chair_notes.models import (
    AssociationBasis, ChairNoteRef, DiscussionRecord, TDocReference, TopicAnchor,
)
from threegpp.db import MetadataRepository
from threegpp.links import (
    EvidenceNodeKind, ExplicitLinkKind, ExplicitLinkService, LinkCoverageState,
)
from threegpp.models import (
    AgreementDisposition, DetectionBasis, DocumentRole, EvidenceKind, EvidenceRef,
    EvidenceScope, EvidenceSpan, SemanticEvidence, TDocMetadata,
)


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def metadata(tdoc_id="R1-2601985", meeting="124bis", *, title="Fast ARQ contribution",
             organization="Example Corp", checksum="a" * 64, group="RAN1"):
    return TDocMetadata(tdoc_id=tdoc_id, working_group=group, meeting=meeting,
        title=title, source_organization_raw=organization, organizations=[organization],
        official_list_present=True, metadata_source_kind="tdoc_list",
        metadata_source_url=f"https://example.test/{meeting}/list.xlsx",
        metadata_source_checksum=checksum)


def evidence(text, *, evidence_id="e1", tdoc_id="R1-2603481", meeting="125",
             kind=EvidenceKind.AGREEMENT, scope=EvidenceScope.MEETING):
    role = DocumentRole.MEETING_REPORT if scope is EvidenceScope.MEETING else DocumentRole.CONTRIBUTION
    ref = EvidenceRef(tdoc_id=tdoc_id, working_group="RAN1", meeting=meeting,
        member="source.docx", block_id="b000001", block_type="paragraph",
        heading_path=["Evidence"])
    return SemanticEvidence(evidence_id=evidence_id, kind=kind, scope=scope,
        working_group="RAN1", meeting=meeting, tdoc_id=tdoc_id,
        document_role=role, document_role_basis=["fixture"],
        source_organizations=[] if scope is EvidenceScope.MEETING else ["Example Corp"],
        evidence_refs=[EvidenceSpan(evidence_ref=ref, sequence=0)], statement_text=text,
        label=kind.value, detection_basis=DetectionBasis.EXPLICIT_LABEL,
        matched_cue=kind.value, rule_id="fixture", rule_version="1", extracted_at=NOW,
        normalization_identity={"raw_sha256": "b" * 64}, evidence_schema_version="1")


def discussion(tdoc_id="R1-2601985", *, record_id="d1", block="b000002", meeting="125"):
    ref = ChairNoteRef(working_group="RAN1", meeting=meeting, snapshot_id="chair-1",
        normalization_id="n1", normalized_checksum="c" * 64, member="chair.docx",
        block_id=block, block_type="paragraph", heading_path=["HARQ"])
    anchor = TopicAnchor(source_ref=ref, literal_text="HARQ Fast-ARQ", matched_terms=["harq"])
    return DiscussionRecord(record_id=record_id, section_id="s1", topic_anchor=anchor,
        reference=TDocReference(tdoc_id=tdoc_id, raw_reference=tdoc_id,
            source_ref=ref, rule_id="literal-tdoc-id", ruleset_version="v1"),
        association_basis=AssociationBasis.SAME_BLOCK, rule_id="same-block",
        ruleset_version="v1")


@pytest.fixture
def service(tmp_path):
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        yield ExplicitLinkService(repository, tmp_path)


def test_contribution_evidence_has_structural_parent_tdoc_link(service):
    item = evidence("Proposal: use explicit DCI.", tdoc_id="R1-2601985",
                    scope=EvidenceScope.CONTRIBUTION, kind=EvidenceKind.PROPOSAL)
    graph = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                  metadata_records=[metadata()])
    assert len(graph.links) == 1
    link = graph.links[0]
    assert link.kind is ExplicitLinkKind.SAME_TDOC
    assert link.source_node.kind is EvidenceNodeKind.SEMANTIC_EVIDENCE
    assert link.target_node.kind is EvidenceNodeKind.TDOC
    assert link.literal_basis == "R1-2601985"
    assert link.target_node.source_organizations == ["Example Corp"]


def test_parent_tdoc_link_is_structurally_resolved_when_metadata_is_missing(service):
    item = evidence("Proposal: use explicit DCI.", tdoc_id="R1-2601985",
                    scope=EvidenceScope.CONTRIBUTION, kind=EvidenceKind.PROPOSAL)
    graph = service.resolve_links(working_group="RAN1", semantic_evidence=[item])
    assert graph.links[0].resolution_state is LinkCoverageState.LINKED
    assert graph.links[0].target_node.meeting == "125"
    assert graph.coverage[0].state is LinkCoverageState.SOURCE_MISSING


def test_missing_tdoc_query_reports_source_preparation_gap(service):
    graph = service.build_for_tdoc("RAN1", "R1-2699999")
    assert graph.coverage[0].state is LinkCoverageState.SOURCE_MISSING
    assert graph.completeness.value == "source_preparation_required"
    plan = service.plan_preparation(graph)
    assert plan.items[0].coverage_state is LinkCoverageState.SOURCE_MISSING
    assert plan.executes_actions is False


def test_chair_note_cross_meeting_link_preserves_roles(service):
    records = [discussion(record_id="d1", block="b1"), discussion(record_id="d2", block="b2")]
    graph = service.resolve_links(working_group="RAN1", discussion_records=records,
                                  metadata_records=[metadata()])
    assert len(graph.links) == 2
    assert len([node for node in graph.nodes if node.kind is EvidenceNodeKind.TDOC]) == 1
    assert {link.kind for link in graph.links} == {ExplicitLinkKind.DISCUSSION_REFERENCE}
    assert {link.discussion_meeting for link in graph.links} == {"125"}
    assert {link.metadata_meeting for link in graph.links} == {"124bis"}


def test_same_chair_note_section_does_not_link_referenced_tdocs_to_each_other(service):
    records = [discussion("R1-2601001", record_id="d1", block="b1"),
               discussion("R1-2601002", record_id="d2", block="b1")]
    graph = service.resolve_links(working_group="RAN1", discussion_records=records,
        metadata_records=[metadata("R1-2601001"), metadata("R1-2601002")])
    assert len(graph.links) == 2
    assert all(link.source_node.kind is EvidenceNodeKind.DISCUSSION_RECORD
               and link.target_node.kind is EvidenceNodeKind.TDOC for link in graph.links)
    assert not any(link.source_node.kind is EvidenceNodeKind.TDOC
                   and link.target_node.kind is EvidenceNodeKind.TDOC for link in graph.links)


def test_link_order_uses_historical_meeting_chronology(service):
    records = [discussion("R1-2602001", record_id="later", meeting="125"),
               discussion("R1-2601001", record_id="earlier", meeting="124bis")]
    graph = service.resolve_links(working_group="RAN1", discussion_records=records,
        metadata_records=[metadata("R1-2601001", meeting="124bis"),
                          metadata("R1-2602001", meeting="125")])
    assert [link.discussion_meeting for link in graph.links] == ["124bis", "125"]


@pytest.mark.parametrize("kind", [EvidenceKind.AGREEMENT, EvidenceKind.DECISION,
                                  EvidenceKind.CONCLUSION, EvidenceKind.FFS])
def test_meeting_evidence_literal_tdoc_reference_only(kind, service):
    item = evidence("Decision: Refer to CR R1-2601985.", kind=kind)
    graph = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                  metadata_records=[metadata()])
    assert [(link.kind, link.literal_basis) for link in graph.links] == [
        (ExplicitLinkKind.EXPLICIT_TDOC_REFERENCE, "R1-2601985")]


def test_meeting_link_preserves_disposition_as_separate_field(service):
    item = evidence("Agreement: The draft CR R1-2601985 is endorsed.")
    graph = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                  metadata_records=[metadata()])
    assert graph.links[0].kind is ExplicitLinkKind.EXPLICIT_TDOC_REFERENCE
    assert graph.links[0].disposition is AgreementDisposition.ENDORSE
    assert graph.links[0].source_node.evidence_scope is EvidenceScope.MEETING
    assert graph.links[0].source_node.source_organizations == []


def test_meeting_link_preserves_discovery_authority_and_target_metadata_meetings(service):
    report = metadata("R1-2603481", meeting="125",
        title="Report of RAN1#124b meeting", organization="ETSI MCC")
    item = evidence("Agreement: Refer to R1-2601985.")
    graph = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                  metadata_records=[report, metadata()])
    link = graph.links[0]
    assert link.discovery_meeting == "125"
    assert link.authority_meeting == "124bis"
    assert link.metadata_meeting == "124bis"


def test_no_literal_reference_produces_no_meeting_link(service):
    graph = service.resolve_links(working_group="RAN1",
        semantic_evidence=[evidence("Agreement: Study explicit indication.")],
        metadata_records=[metadata()])
    assert graph.links == []


def test_unresolved_reference_later_resolves_deterministically(service):
    item = evidence("Agreement: Refer to R1-2601985.")
    missing = service.resolve_links(working_group="RAN1", semantic_evidence=[item])
    assert missing.links[0].resolution_state is LinkCoverageState.UNRESOLVED_REFERENCE
    resolved = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                     metadata_records=[metadata()])
    assert resolved.links[0].resolution_state is LinkCoverageState.LINKED
    assert resolved.graph_id != missing.graph_id
    assert resolved == service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                             metadata_records=[metadata()])


def test_incompatible_metadata_is_ambiguous_without_definitive_target(service):
    item = evidence("Decision: Refer to R1-2601985.", kind=EvidenceKind.DECISION)
    graph = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
        metadata_records=[metadata(meeting="124bis"), metadata(meeting="125", title="Other")])
    link = graph.links[0]
    assert link.resolution_state is LinkCoverageState.AMBIGUOUS_REFERENCE
    assert link.target_node.meeting is None
    assert len(link.resolution_candidates) == 2


def test_similar_wording_same_topic_and_company_do_not_link_tdocs(service):
    first = evidence("Proposal: fast HARQ recovery with explicit indication.", evidence_id="e1",
        tdoc_id="R1-2601001", scope=EvidenceScope.CONTRIBUTION, kind=EvidenceKind.PROPOSAL)
    second = evidence("Proposal: explicit indication for faster HARQ recovery.", evidence_id="e2",
        tdoc_id="R1-2601002", scope=EvidenceScope.CONTRIBUTION, kind=EvidenceKind.PROPOSAL)
    records = [metadata("R1-2601001"), metadata("R1-2601002")]
    graph = service.resolve_links(working_group="RAN1", semantic_evidence=[first, second],
                                  metadata_records=records)
    assert {link.kind for link in graph.links} == {ExplicitLinkKind.SAME_TDOC}
    assert all(link.source_node.tdoc_id == link.target_node.tdoc_id for link in graph.links)


@pytest.mark.parametrize("title,expected", [
    ("Reply LS to R1-2601001", ExplicitLinkKind.EXPLICIT_REPLY_REFERENCE),
    ("Revision of R1-2601001", ExplicitLinkKind.EXPLICIT_REVISION_REFERENCE),
    ("Supersedes R1-2601001", ExplicitLinkKind.EXPLICIT_SUPERSESSION_REFERENCE),
])
def test_literal_metadata_relationships_only(title, expected, service):
    source = metadata("R1-2602001", title=title)
    target = metadata("R1-2601001")
    graph = service.resolve_links(working_group="RAN1", metadata_records=[source, target])
    assert any(link.kind is expected and link.source_node.tdoc_id == "R1-2602001"
               for link in graph.links)


def test_explicit_reply_ls_preserves_cross_working_group_target(service):
    source = metadata("R1-2602001", title="Reply LS to R2-2601001")
    target = metadata("R2-2601001", group="RAN2")
    graph = service.resolve_links(working_group="RAN1", metadata_records=[source, target])
    link = next(item for item in graph.links
                if item.kind is ExplicitLinkKind.EXPLICIT_REPLY_REFERENCE)
    assert link.source_node.working_group.value == "RAN1"
    assert link.target_node.working_group.value == "RAN2"


def test_literal_cross_working_group_meeting_reference_preserves_raw_alias(service):
    item = evidence("Conclusion: Follow-up to RAN2#134b is recorded.",
        scope=EvidenceScope.CONTRIBUTION, kind=EvidenceKind.CONCLUSION)
    graph = service.resolve_links(working_group="RAN1", semantic_evidence=[item])
    link = next(value for value in graph.links
                if value.kind is ExplicitLinkKind.EXPLICIT_MEETING_REFERENCE)
    assert link.target_node.working_group.value == "RAN2"
    assert link.target_node.meeting == "134bis"
    assert link.target_node.meeting_raw == "RAN2#134b"


def test_title_similarity_alone_builds_no_relation(service):
    graph = service.resolve_links(working_group="RAN1", metadata_records=[
        metadata("R1-2601001", title="HARQ reply study"),
        metadata("R1-2601002", title="HARQ reply study revised")])
    assert graph.links == []


def test_ruleset_and_source_identity_change_graph_identity(service, monkeypatch):
    from threegpp.links import rules
    item = evidence("Agreement: Refer to R1-2601985.")
    first = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                  metadata_records=[metadata()])
    changed_source = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                           metadata_records=[metadata(checksum="f" * 64)])
    assert first.graph_id != changed_source.graph_id
    monkeypatch.setattr(rules, "EXPLICIT_LINK_RULESET_VERSION", "explicit-link-changed")
    changed_rule = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                         metadata_records=[metadata()])
    assert first.graph_id != changed_rule.graph_id


def test_meeting_alias_ruleset_change_invalidates_graph_identity(service, monkeypatch):
    from threegpp.historical import rules as historical_rules
    first = service.resolve_links(working_group="RAN1", discussion_records=[discussion()],
                                  metadata_records=[metadata()])
    monkeypatch.setattr(historical_rules, "MEETING_ALIAS_RULESET_VERSION", "meeting-alias-changed")
    second = service.resolve_links(working_group="RAN1", discussion_records=[discussion()],
                                   metadata_records=[metadata()])
    assert first.graph_id != second.graph_id


def test_extraction_timestamp_is_not_a_source_semantic_change(service):
    item = evidence("Agreement: Refer to R1-2601985.")
    later = item.model_copy(update={"extracted_at": datetime(2026, 2, 1, tzinfo=UTC)})
    first = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                  metadata_records=[metadata()])
    second = service.resolve_links(working_group="RAN1", semantic_evidence=[later],
                                   metadata_records=[metadata()])
    assert first.graph_id == second.graph_id


def test_repeated_literal_occurrences_keep_separate_exact_locators(service):
    item = evidence("Decision: R1-2601985 and R1-2601985 require separate references.",
                    kind=EvidenceKind.DECISION)
    graph = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
                                  metadata_records=[metadata()])
    assert len(graph.links) == 2
    assert len({link.link_id for link in graph.links}) == 2
    assert {link.target_node.node_id for link in graph.links} == {graph.links[0].target_node.node_id}
    starts = [link.locators[0].reference["char_start"] for link in graph.links]
    assert len(set(starts)) == 2


def test_input_order_does_not_change_graph_identity(service):
    items = [evidence("Decision: Refer to R1-2601985.", evidence_id="e2",
                      kind=EvidenceKind.DECISION),
             evidence("Conclusion: Refer to R1-2601001.", evidence_id="e1",
                      kind=EvidenceKind.CONCLUSION)]
    records = [metadata("R1-2601985"), metadata("R1-2601001")]
    first = service.resolve_links(working_group="RAN1", semantic_evidence=items,
                                  metadata_records=records)
    second = service.resolve_links(working_group="RAN1", semantic_evidence=list(reversed(items)),
                                   metadata_records=list(reversed(records)))
    assert first.graph_id == second.graph_id
    assert first.links == second.links


def test_v07_historical_coverage_feeds_cross_meeting_link_graph(tmp_path):
    from test_historical import add_snapshot, install_chair, metadata as historical_metadata
    from threegpp.historical import HistoricalCoverageRequest
    install_chair(tmp_path, "RAN1", "125", "HARQ Fast-ARQ R1-2603427")
    with MetadataRepository(tmp_path / "db.duckdb") as repository:
        add_snapshot(repository, "124bis", [historical_metadata("R1-2603427", "124bis")])
        graph = ExplicitLinkService(repository, tmp_path).build_for_topic(
            HistoricalCoverageRequest(working_group="RAN1", from_meeting="124b",
                to_meeting="125", query="HARQ Fast-ARQ"))
        link = next(item for item in graph.links
                    if item.kind is ExplicitLinkKind.DISCUSSION_REFERENCE)
        assert graph.scope["meetings"] == ["124bis", "125"]
        assert link.discussion_meeting == "125"
        assert link.metadata_meeting == "124bis"


def test_persistence_indexes_only_compact_link_fields(service, tmp_path):
    graph = service.resolve_links(working_group="RAN1",
        semantic_evidence=[evidence("Agreement: Refer to R1-2601985.")],
        metadata_records=[metadata()])
    path = service.persist(graph)
    assert path.is_file() and path.is_relative_to(tmp_path)
    assert service.connection.execute("select count(*) from explicit_link_nodes").fetchone()[0] == 2
    assert service.connection.execute("select count(*) from explicit_evidence_links").fetchone()[0] == 1
    state = service.connection.execute(
        "select graph_checksum,artifact_checksum from explicit_link_graph_state").fetchone()
    assert state[0] == graph.graph_checksum and len(state[1]) == 64
    columns = {row[1] for row in service.connection.execute(
        "pragma table_info('explicit_evidence_links')").fetchall()}
    assert "statement_text" not in columns and "body_text" not in columns


def test_persist_replaces_stale_graph_for_the_same_scope(service):
    item = evidence("Agreement: Refer to R1-2601985.")
    first = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
        metadata_records=[metadata()], scope={"kind": "tdoc", "tdoc_id": "R1-2601985"})
    service.persist(first)
    second = service.resolve_links(working_group="RAN1", semantic_evidence=[item],
        metadata_records=[metadata(checksum="f" * 64)],
        scope={"kind": "tdoc", "tdoc_id": "R1-2601985"})
    service.persist(second)
    assert first.graph_id != second.graph_id
    assert service.connection.execute(
        "select graph_id from explicit_link_graph_state").fetchall() == [(second.graph_id,)]
    assert service.connection.execute(
        "select distinct graph_id from explicit_evidence_links").fetchall() == [(second.graph_id,)]


def test_link_build_never_invokes_document_or_chair_acquisition(service, monkeypatch):
    from threegpp.documents import DocumentService
    from threegpp.chair_notes import ChairNoteService
    monkeypatch.setattr(DocumentService, "execute", lambda *a, **k: pytest.fail("downloaded TDoc"))
    monkeypatch.setattr(ChairNoteService, "fetch", lambda *a, **k: pytest.fail("downloaded Chair Note"))
    graph = service.resolve_links(working_group="RAN1",
        discussion_records=[discussion()], metadata_records=[metadata()])
    assert graph.diagnostics["links"] == 1


def test_preparation_reports_local_normalized_body_without_semantic_extraction(tmp_path):
    from test_evidence import _block, _document
    with MetadataRepository(tmp_path / "db.duckdb") as repository:
        _document(repository, tmp_path, "R1-2601985", [_block("b000001", "Proposal: Fast ARQ")])
        service = ExplicitLinkService(repository, tmp_path)
        graph = service.build_for_tdoc("RAN1", "R1-2601985")
        plan = service.plan_preparation(graph)
        assert plan.items[0].coverage_state is LinkCoverageState.SEMANTIC_EVIDENCE_NOT_EXTRACTED
        assert plan.items[0].body_fetch_needed is False
        assert plan.items[0].normalization_needed is False
        assert plan.items[0].index_needed is True
        assert plan.items[0].semantic_extraction_needed is True


def test_models_expose_no_stance_or_semantic_cluster_fields():
    from threegpp.links import ExplicitEvidenceLink
    fields = set(ExplicitEvidenceLink.model_fields)
    assert not fields & {"supports", "opposes", "stance", "score", "semantic_cluster"}


@pytest.mark.parametrize("command", [
    "build-explicit-links", "show-tdoc-links", "show-meeting-links",
    "show-topic-links", "plan-link-preparation",
])
def test_link_cli_help(command):
    from threegpp.cli import build_parser
    with pytest.raises(SystemExit) as stopped:
        build_parser().parse_args([command, "--help"])
    assert stopped.value.code == 0


def test_tdoc_link_cli_uses_local_state_only(tmp_path, capsys, monkeypatch):
    from threegpp.chair_notes import ChairNoteService
    from threegpp.cli import main
    from threegpp.documents import DocumentService
    monkeypatch.setattr(DocumentService, "execute", lambda *a, **k: pytest.fail("downloaded TDoc"))
    monkeypatch.setattr(ChairNoteService, "fetch", lambda *a, **k: pytest.fail("downloaded Chair Note"))
    result = main(["--db", str(tmp_path / "db.duckdb"), "--data-dir", str(tmp_path),
                   "show-tdoc-links", "--wg", "RAN1", "--tdoc", "R1-2699999"])
    assert result == 0
    output = capsys.readouterr().out
    assert '"source_missing"' in output and '"links": []' in output


def test_build_cli_persists_only_under_runtime_root(tmp_path, capsys):
    from threegpp.cli import main
    result = main(["--db", str(tmp_path / "db.duckdb"), "--data-dir", str(tmp_path),
                   "build-explicit-links", "--wg", "RAN1", "--tdoc", "R1-2699999"])
    assert result == 0
    output = capsys.readouterr().out
    assert '"downloads_performed": 0' in output
    assert len(list((tmp_path / "derived" / "links").rglob("graph.json.gz"))) == 1
