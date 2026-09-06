from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from threegpp.sources import RAN2Source


FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://www.3gpp.org/ftp/tsg_ran/WG2_RL2/"


@pytest.fixture
def ran2_source() -> RAN2Source:
    pages = {
        BASE: "group_listing.html",
        BASE + "TSGR2_131/": "meeting_listing.html",
        BASE + "TSGR2_131/Docs/": "docs_listing.html",
        BASE + "TSGR2_131/Agenda/": "agenda_listing.html",
        BASE + "TSGR2_131/Report/": "report_listing.html",
        BASE + "TSGR2_131/Tdoclists/": "tdoclists_listing.html",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        filename = pages.get(str(request.url))
        if filename is None:
            return httpx.Response(404, request=request)
        return httpx.Response(200, text=(FIXTURES / filename).read_text(), request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = RAN2Source(client=client, backoff=0)
    yield source
    client.close()
