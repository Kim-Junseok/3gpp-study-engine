from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import httpx

from threegpp.chair_notes.rules import discovered_snapshot
from threegpp.chair_notes.service import ChairNoteService
from threegpp.db import MetadataRepository
from threegpp.ingest.downloader import HTTPDownloader
from threegpp.models import TDocMetadata
from threegpp.topics import (
    TopicBootstrapRequest, TopicBootstrapService, TopicProfileDecision,
    TopicProfileService, TopicTermState, render_bootstrap, render_profile,
)
from threegpp.topics.rules import exact_variants


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def install_chair(root, meeting, text, filename="chair_notes_final.txt"):
    directory = f"https://www.3gpp.org/ftp/fixture/RAN1/{meeting}/Inbox/Chair_notes/"
    snapshot = discovered_snapshot("RAN1", meeting, directory + filename, directory, NOW)
    with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=text.encode()))) as client:
        service = ChairNoteService(root, HTTPDownloader(client=client))
        source = SimpleNamespace(working_group="RAN1",
            discover_chair_notes=lambda value: [snapshot])
        service.discover(source, meeting)
        service.fetch("RAN1", meeting, snapshot.snapshot_id)
    return snapshot


def metadata(tdoc_id, meeting, title, organization="Example Org"):
    return TDocMetadata(tdoc_id=tdoc_id, working_group="RAN1", meeting=meeting,
        title=title, source_organization_raw=organization, organizations=[organization],
        official_list_present=True, metadata_source_kind="tdoc_list",
        metadata_source_url=f"https://www.3gpp.org/RAN1/{meeting}/list.xlsx",
        metadata_source_checksum=("a" if meeting == "125" else "b") * 64)


def request(**updates):
    values = dict(working_group="RAN1", from_meeting="125", to_meeting="126",
                  user_terms=["CBUL", "contention-based uplink"],
                  topic_label="Contention-based uplink")
    values.update(updates)
    return TopicBootstrapRequest(**values)


def term(result, literal, state=None):
    values = [item for item in result.terms
              if item.literal_text.casefold() == literal.casefold()
              and (state is None or item.state is state)]
    assert values, [(item.literal_text, item.state) for item in result.terms]
    return values[0]


def test_exact_variants_are_formatting_only():
    variants = exact_variants("Fast-ARQ")
    assert "Fast ARQ" in variants and "fast arq" in variants
    assert not any("HARQ" in value for value in variants)


def test_cbul_bootstrap_separates_seed_candidate_and_related_terms(tmp_path):
    install_chair(tmp_path, "126",
        "contention based PUSCH, configured grant, random access R1-2601001")
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(metadata("R1-2601001", "126",
            "Discussion on contention-based PUSCH transmission", "Samsung"))
        service = TopicBootstrapService(repository, tmp_path)
        first = service.bootstrap(request())
        second = service.bootstrap(request())
    assert first == second
    assert term(first, "CBUL", TopicTermState.USER_SEED).source_occurrence_count == 0
    candidate = term(first, "contention based PUSCH", TopicTermState.SOURCE_CANDIDATE)
    assert candidate.source_occurrence_count >= 1
    assert candidate.state is not TopicTermState.ACCEPTED_SOURCE_TERM
    assert candidate.occurrences[0].locator.char_end > candidate.occurrences[0].locator.char_start
    assert term(first, "configured grant", TopicTermState.RELATED_ONLY)
    assert term(first, "random access", TopicTermState.RELATED_ONLY)
    assert "Samsung" in {org for item in first.terms for org in item.candidate_organizations}


def test_candidate_organization_order_has_literal_tiebreaker(tmp_path):
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(metadata("R1-2601001", "126",
            "contention based PUSCH", "Wisig Networks"))
        repository.upsert_tdoc(metadata("R1-2601002", "126",
            "contention based PUSCH", "WiSig Networks"))
        result = TopicBootstrapService(repository, tmp_path).bootstrap(request())
    candidate = term(result, "contention based PUSCH", TopicTermState.SOURCE_CANDIDATE)
    assert candidate.candidate_organizations == ["WiSig Networks", "Wisig Networks"]


def test_candidate_strips_organization_joined_to_source_term(tmp_path):
    install_chair(tmp_path, "126",
                  "less than threshold, R1-2601001 GNSS resilienceAmazon")
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(metadata("R1-2601001", "126",
            "Unrelated title", "Amazon Web Services"))
        result = TopicBootstrapService(repository, tmp_path).bootstrap(request(
            from_meeting="126", user_terms=["GNSS-less"],
            topic_label="GNSS-less NTN"))
    candidate = term(result, "GNSS resilience", TopicTermState.SOURCE_CANDIDATE)
    assert candidate.source_occurrence_count == 1
    assert not any(item.literal_text == "GNSS resilienceAmazon"
                   for item in result.terms)
    assert not any(item.literal_text == "less than"
                   and item.state is TopicTermState.SOURCE_CANDIDATE
                   for item in result.terms)


def test_fast_arq_source_format_is_exact_variant_not_synonym(tmp_path):
    install_chair(tmp_path, "126", "Fast ARQ R1-2601001")
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        result = TopicBootstrapService(repository, tmp_path).bootstrap(request(
            from_meeting="126", user_terms=["Fast-ARQ"], topic_label="Fast ARQ"))
    assert term(result, "Fast ARQ", TopicTermState.EXACT_VARIANT).source_occurrence_count == 1
    assert not any(item.literal_text.casefold() == "harq" for item in result.terms)


def test_zero_candidate_and_partial_sources_are_explicit(tmp_path):
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        result = TopicBootstrapService(repository, tmp_path).bootstrap(request(
            from_meeting="125", to_meeting="125", user_terms=["unseen phrase"]))
    assert not any(item.state is TopicTermState.SOURCE_CANDIDATE for item in result.terms)
    assert result.source_coverage.completeness == "partial_source_coverage"
    assert "No source terminology candidates" in render_bootstrap(result)


def test_profile_decisions_are_explicit_deterministic_and_stale_safe(tmp_path):
    install_chair(tmp_path, "126",
        "contention based PUSCH, configured grant, random access R1-2601001")
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        service = TopicProfileService(repository, tmp_path)
        result, profile = service.bootstrap_and_persist(request())
        accepted = term(result, "contention based PUSCH", TopicTermState.SOURCE_CANDIDATE)
        revised = service.update(TopicProfileDecision(profile_id=profile.profile_id,
            accept=[accepted.literal_text], related=["configured grant"], reject=["random access"]))
        loaded = service.load(revised.profile_id)
        again = service.update(TopicProfileDecision(profile_id=profile.profile_id,
            accept=[accepted.literal_text], related=["configured grant"], reject=["random access"]))
    assert loaded == revised == again
    assert term(loaded, accepted.literal_text, TopicTermState.ACCEPTED_SOURCE_TERM)
    assert term(loaded, "configured grant", TopicTermState.RELATED_ONLY)
    assert term(loaded, "random access", TopicTermState.REJECTED)
    assert profile.profile_id != revised.profile_id
    assert (tmp_path / "derived" / "topics" / "ran1" / revised.profile_id
            / "topic-profile.json").is_file()


def test_related_term_stays_out_of_direct_inventory_and_company_is_metadata_authorship(tmp_path):
    install_chair(tmp_path, "126",
        "contention based PUSCH, configured grant, random access R1-2601001")
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(metadata("R1-2601001", "126",
            "contention based PUSCH design", "Samsung"))
        service = TopicProfileService(repository, tmp_path)
        result, profile = service.bootstrap_and_persist(request())
        candidate = term(result, "contention based PUSCH", TopicTermState.SOURCE_CANDIDATE)
        initial_inventory = service.inventory(profile)
        revised = service.update(TopicProfileDecision(profile_id=profile.profile_id,
            accept=[candidate.literal_text], related=["configured grant"]))
        first = service.inventory(revised)
        second = service.inventory(revised)
    assert initial_inventory.companies == []
    assert first == second
    assert "configured grant" not in first.direct_terms
    assert "configured grant" in first.related_diagnostic_terms
    samsung = next(item for item in first.companies if item.organization == "Samsung")
    assert [item.tdoc_id for item in samsung.tdocs] == ["R1-2601001"]
    assert samsung.tdocs[0].chair_note_confirmed
    assert not samsung.tdocs[0].content_inspected
    assert not samsung.tdocs[0].explicit_meeting_outcome_reference
    assert any(association.query_term == candidate.literal_text
               for association in samsung.tdocs[0].associations)


def test_direct_inventory_falls_back_to_exact_metadata_after_joined_chair_text(tmp_path):
    install_chair(tmp_path, "126",
                  "R1-2601001contention based PUSCHSamsung")
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(metadata("R1-2601001", "126",
            "contention based PUSCH", "Samsung"))
        service = TopicProfileService(repository, tmp_path)
        _, profile = service.bootstrap_and_persist(request(
            from_meeting="126", to_meeting="126",
            accepted_source_terms=["contention based PUSCH"]))
        inventory = service.inventory(profile)
    samsung = next(item for item in inventory.companies if item.organization == "Samsung")
    assert samsung.tdocs[0].chair_note_confirmed is True
    assert samsung.tdocs[0].associations[0].association_basis == "metadata_title_relevance"


def test_profile_reuse_extends_range_and_keeps_new_candidates_unaccepted(tmp_path):
    install_chair(tmp_path, "126", "contention based PUSCH R1-2601001")
    install_chair(tmp_path, "127", "contention based PUSCH, sidelink relay R1-2601002")
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(metadata("R1-2601001", "126", "contention based PUSCH", "A"))
        repository.upsert_tdoc(metadata("R1-2601002", "127", "contention based PUSCH relay", "B"))
        service = TopicProfileService(repository, tmp_path)
        result, profile = service.bootstrap_and_persist(request(
            from_meeting="126", to_meeting="126"))
        candidate = term(result, "contention based PUSCH", TopicTermState.SOURCE_CANDIDATE)
        revised = service.update(TopicProfileDecision(profile_id=profile.profile_id,
                                                       accept=[candidate.literal_text]))
        inventory = service.inventory(revised, from_meeting="127", to_meeting="127")
    assert {item.organization for item in inventory.companies} == {"B"}
    assert any(item.literal_text.casefold() == "contention based pusch relay"
               and item.state is TopicTermState.SOURCE_CANDIDATE
               for item in inventory.new_source_candidates)
    assert any(item.literal_text.casefold() == "sidelink relay"
               for item in inventory.new_related_candidates)


def test_default_renderer_hides_backend_state_and_scores(tmp_path):
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        result, profile = TopicProfileService(repository, tmp_path).bootstrap_and_persist(
            request(from_meeting="125", to_meeting="125", user_terms=["CBUL"]))
    output = render_bootstrap(result, profile)
    profile_output = render_profile(profile)
    assert "SOURCE_CANDIDATE" not in output + profile_output
    assert "retrieval_support_score" not in output + profile_output
    assert f"Profile: {profile.profile_id}" in profile_output
    assert profile.profile_id in render_profile(profile, provenance=True)


def test_bootstrap_does_not_instantiate_completion_or_download_contributions(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("topic bootstrap must not download")
    monkeypatch.setattr(HTTPDownloader, "download", fail)
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        result = TopicBootstrapService(repository, tmp_path).bootstrap(request(
            from_meeting="125", to_meeting="125", user_terms=["CBUL"]))
    assert result.bootstrap_id.startswith("topic-bootstrap-")


def test_topic_profile_cli_round_trip_is_research_facing(tmp_path, capsys, monkeypatch):
    from threegpp.cli import main

    install_chair(tmp_path, "126", "contention based PUSCH R1-2601001")
    database = tmp_path / "metadata.duckdb"
    with MetadataRepository(database) as repository:
        repository.upsert_tdoc(metadata("R1-2601001", "126",
            "contention based PUSCH", "Samsung"))
    monkeypatch.setattr(HTTPDownloader, "download",
                        lambda *args, **kwargs: (_ for _ in ()).throw(
                            AssertionError("profile CLI downloaded")))
    common = ["--db", str(database), "--data-dir", str(tmp_path)]
    assert main(common + ["bootstrap-topic", "--wg", "RAN1",
        "--from-meeting", "126", "--to-meeting", "126",
        "--term", "contention-based uplink"]) == 0
    assert "TOPIC BOOTSTRAP" in capsys.readouterr().out
    profiles = sorted((tmp_path / "derived" / "topics" / "ran1").glob(
        "topic-profile-*/topic-profile.json"))
    initial = profiles[0].parent.name
    assert main(common + ["update-topic-profile", "--profile", initial,
        "--accept", "contention based PUSCH"]) == 0
    assert "Accepted source terminology" in capsys.readouterr().out
    profiles = sorted((tmp_path / "derived" / "topics" / "ran1").glob(
        "topic-profile-*/topic-profile.json"))
    revised = next(path.parent.name for path in profiles if path.parent.name != initial)
    assert main(common + ["show-topic-profile", "--profile", revised]) == 0
    output = capsys.readouterr().out
    assert "Samsung" in output and "Contribution inspected: No" in output
    assert "SOURCE_CANDIDATE" not in output


def test_inventory_reuses_inspected_content_and_explicit_outcome_state(tmp_path):
    from test_evidence import _block, _document
    from threegpp.evidence import EvidenceExtractionService

    install_chair(tmp_path, "125", "Fast-ARQ R1-2601005")
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        contribution = _document(repository, tmp_path, "R1-2601005", [
            _block("b000001", "Proposal: Use Fast-ARQ recovery."),
        ], title="Fast-ARQ recovery", organizations=["Nokia"], identity="raw-contribution")
        report = _document(repository, tmp_path, "R1-9999", [
            _block("b000001", "Agreement: The draft CR R1-2601005 is endorsed."),
        ], title="Report of RAN1#125 meeting", organizations=["ETSI MCC"],
            identity="raw-report")
        evidence = EvidenceExtractionService(repository, tmp_path)
        evidence.extract_document(contribution)
        evidence.extract_document(report)
        service = TopicProfileService(repository, tmp_path)
        _, profile = service.bootstrap_and_persist(TopicBootstrapRequest(
            working_group="RAN1", from_meeting="125", to_meeting="125",
            user_terms=["Fast-ARQ"], topic_label="Fast ARQ"))
        inventory = service.inventory(profile)
    nokia = next(item for item in inventory.companies if item.organization == "Nokia")
    assert nokia.tdocs[0].content_inspected is True
    assert nokia.tdocs[0].explicit_meeting_outcome_reference is True
