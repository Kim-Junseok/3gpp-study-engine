from __future__ import annotations

import httpx

from threegpp.models import WorkingGroup

from .base import DirectorySource


class RAN1Source(DirectorySource):
    def __init__(self, *, client: httpx.Client | None = None, **kwargs: object) -> None:
        super().__init__(
            WorkingGroup.RAN1,
            "WG1_RL1",
            "TSGR1_",
            "R1",
            client=client,
            **kwargs,
        )
