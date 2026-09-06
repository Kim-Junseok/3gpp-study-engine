from __future__ import annotations

import httpx

from threegpp.models import WorkingGroup

from .base import DirectorySource


class RAN2Source(DirectorySource):
    def __init__(self, *, client: httpx.Client | None = None, **kwargs: object) -> None:
        super().__init__(
            WorkingGroup.RAN2,
            "WG2_RL2",
            "TSGR2_",
            "R2",
            client=client,
            **kwargs,
        )
