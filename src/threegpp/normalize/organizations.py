from __future__ import annotations

import re


_LEGAL_SUFFIXES = re.compile(
    r",\s*(?=(?:inc\.?|ltd\.?|limited|corp\.?|corporation|co\.?|llc)\b)",
    re.IGNORECASE,
)


def normalize_organizations(raw: str | None) -> list[str]:
    """Split only official-list delimiters, never ordinary name punctuation/words."""
    if not raw or not raw.strip():
        return []
    protected = _LEGAL_SUFFIXES.sub("\u0000", raw)
    # Commas, semicolons, and line breaks are list delimiters in observed 3GPP
    # source cells. Words/symbols such as "and", "&", slash, and plus can be
    # part of a legal organization name and are deliberately not separators.
    parts = re.split(r"\s*(?:;|\r?\n|,)\s*", protected)
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = re.sub(r"\s+", " ", part.replace("\u0000", ", ")).strip(" ,;")
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result
