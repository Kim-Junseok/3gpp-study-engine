from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from .models import ExactSourceSpan, SegmentationReason


_LIST = re.compile(r"(?m)^(?P<indent>\s*)(?P<mark>[-•*]|\d+[.)]|Option\s+\d+\s*[:.)])\s+")
_SENTENCE = re.compile(r"(?<=[.!?])(?=\s+(?:[\"'“‘(]*[A-Z0-9]))")


def canonical(value) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def surface(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split()).casefold()


def segment(text: str):
    """Return literal source spans; never rewrite or merge source wording."""
    matches = list(_LIST.finditer(text))
    if len(matches) >= 2:
        result = []
        if text[:matches[0].start()].strip():
            start = next(i for i, char in enumerate(text[:matches[0].start()]) if not char.isspace())
            end = matches[0].start()
            while end > start and text[end - 1].isspace(): end -= 1
            result.append((ExactSourceSpan(char_start=start, char_end=end,
                                            exact_text=text[start:end]),
                           SegmentationReason.WHOLE_SOURCE_UNIT, None))
        parent = 0 if result else None
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            while end > start and text[end - 1].isspace(): end -= 1
            mark = match.group("mark").casefold()
            reason = (SegmentationReason.OPTION_ITEM if mark.startswith("option") else
                      SegmentationReason.NUMBERED_ITEM if mark[0].isdigit() else
                      SegmentationReason.LIST_ITEM)
            result.append((ExactSourceSpan(char_start=start, char_end=end,
                                            exact_text=text[start:end]), reason, parent))
        return result
    boundaries = [0] + [m.end() for m in _SENTENCE.finditer(text)] + [len(text)]
    spans = []
    for start, end in zip(boundaries, boundaries[1:]):
        while start < end and text[start].isspace(): start += 1
        while end > start and text[end - 1].isspace(): end -= 1
        if start < end:
            spans.append(ExactSourceSpan(char_start=start, char_end=end,
                                         exact_text=text[start:end]))
    if len(spans) >= 2:
        return [(span, SegmentationReason.SENTENCE_BOUNDARY, None) for span in spans]
    start, end = 0, len(text)
    while start < end and text[start].isspace(): start += 1
    while end > start and text[end - 1].isspace(): end -= 1
    return [(ExactSourceSpan(char_start=start, char_end=end, exact_text=text[start:end]),
             SegmentationReason.WHOLE_SOURCE_UNIT, None)] if start < end else []
