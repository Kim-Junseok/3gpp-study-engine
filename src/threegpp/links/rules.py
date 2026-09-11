from __future__ import annotations

import hashlib
import json
import re
from typing import Any


EXPLICIT_LINK_SCHEMA_VERSION = "1"
LINK_GRAPH_SCHEMA_VERSION = "1"
EXPLICIT_LINK_RULESET_VERSION = "explicit-link-v1"
LINK_PREPARATION_SCHEMA_VERSION = "1"

TDOC_REFERENCE_PATTERN = re.compile(r"\b(?:R[12]-\d{6,8})\b", re.IGNORECASE)
MEETING_REFERENCE_PATTERN = re.compile(
    r"\b(?:previously\s+agreed\s+in|follow(?:-|\s*)up\s+to)\s+"
    r"(?P<meeting>RAN[12]\s*#\s*\d+(?:bis|b|-e)?)\b",
    re.IGNORECASE,
)

_SUPERSESSION = re.compile(r"\b(?:supersedes?|replaces?)\b", re.IGNORECASE)
_REVISION = re.compile(
    r"\b(?:revision\s+of|revised\s+version\s+of|updated\s+version\s+of)\b",
    re.IGNORECASE,
)
_REPLY = re.compile(r"\b(?:reply\s+LS\s+to|reply\s+to|in\s+reply\s+to)\b", re.IGNORECASE)


def relation_for_reference(text: str, start: int, end: int) -> str:
    """Classify only explicit wording close to a literal TDoc reference."""
    context = text[max(0, start - 80):min(len(text), end + 40)]
    if _SUPERSESSION.search(context):
        return "explicit_supersession_reference"
    if _REVISION.search(context):
        return "explicit_revision_reference"
    if _REPLY.search(context):
        return "explicit_reply_reference"
    return "explicit_tdoc_reference"


def identity(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
