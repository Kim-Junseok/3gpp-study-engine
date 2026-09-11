import httpx

from threegpp.models import ArtifactType
from threegpp.sources import RAN1Source


def test_source_directory_b_alias_preserves_raw_url() -> None:
    base = "https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == base:
            return httpx.Response(
                200,
                text='<a href="TSGR1_124/">TSGR1_124</a><a href="TSGR1_124b/">TSGR1_124b</a>',
                request=request,
            )
        if str(request.url) == base + "TSGR1_124b/":
            return httpx.Response(200, text="", request=request)
        return httpx.Response(404, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = RAN1Source(client=client, backoff=0)
        historical = next(item for item in source.list_meetings() if item.meeting_number == "124bis")
        assert historical.meeting_name == "RAN1#124b"
        assert str(historical.source_url).endswith("TSGR1_124b/")
        assert source.meeting_url("124bis").endswith("TSGR1_124b/")
        metadata = source.get_meeting_metadata("124bis")
        assert metadata.meeting_number == "124bis"
        assert metadata.meeting_name == "RAN1#124b"


def test_list_meetings_keeps_suffixes_and_skips_unknown_layouts(ran2_source) -> None:
    meetings = ran2_source.list_meetings()
    assert [item.meeting_number for item in meetings] == ["129", "131", "131bis"]
    assert str(meetings[-1].source_url).endswith("TSGR2_131bis/")


def test_parse_meeting_resources_and_tdocs(ran2_source) -> None:
    meeting = ran2_source.get_meeting_metadata("131")
    assert meeting.meeting_name == "RAN2#131"
    assert meeting.start_date is None

    agenda = ran2_source.get_agenda("131")
    report = ran2_source.get_meeting_report("131")
    tdoc_lists = ran2_source.get_tdoc_list("131")
    tdocs = ran2_source.list_tdocs("131")

    assert agenda[0].artifact_type is ArtifactType.AGENDA
    assert report[0].artifact_type is ArtifactType.MEETING_REPORT
    assert {item.original_filename for item in tdoc_lists} == {
        "TDoc_List_Meeting_RAN2#131.xlsx",
        "R2-131-final-tdoc-list.xlsx",
        "tdocList_2025-09-02_14h28.xlsx",
    }
    assert [item.tdoc_id for item in tdocs] == ["R2-2505001", "R2-2505002"]
    assert all(item.title is None for item in tdocs)
    assert all(item.directory_present for item in tdocs)
    assert all(not item.official_list_present for item in tdocs)


def test_get_one_tdoc(ran2_source) -> None:
    tdoc = ran2_source.get_tdoc("131", "r2-2505002")
    assert tdoc.tdoc_id == "R2-2505002"
