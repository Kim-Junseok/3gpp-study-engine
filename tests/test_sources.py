from threegpp.models import ArtifactType


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
