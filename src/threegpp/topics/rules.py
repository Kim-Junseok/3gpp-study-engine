"""Versioned deterministic rules for topic terminology bootstrap."""
from __future__ import annotations

import hashlib
import json
import re

TOPIC_BOOTSTRAP_SCHEMA_VERSION = "1"
TOPIC_TERMINOLOGY_RULESET_VERSION = "lexical-source-terms-v1"
TOPIC_PROFILE_SCHEMA_VERSION = "1"
TOPIC_INVENTORY_SCHEMA_VERSION = "1"
DEFAULT_CANDIDATE_LIMIT = 40
MAX_CANDIDATE_TOKENS = 4

WORD = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
SEGMENT = re.compile(r"[^,;/|\n]+")


def identity(value: object, prefix: str) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return prefix + hashlib.sha256(payload).hexdigest()


def normalized_term(value: str) -> str:
    """Normalize only case, punctuation, whitespace, and hyphen formatting."""
    return " ".join(re.findall(r"[A-Za-z0-9]+", value)).casefold()


def decision_key(value: str) -> str:
    return normalized_term(value)


def exact_variants(value: str) -> list[str]:
    """Return bounded formatting variants without conceptual expansion."""
    clean = " ".join(value.strip().split())
    values = {clean, clean.casefold()}
    if "-" in clean:
        spaced = re.sub(r"(?<=\w)-(?=\w)", " ", clean)
        values.update({spaced, spaced.casefold()})
    elif " " in clean:
        parts = clean.split()
        if len(parts) == 2:
            hyphenated = "-".join(parts)
            values.update({hyphenated, hyphenated.casefold()})
    return sorted(values, key=lambda item: (item.casefold(), item))


def word_spans(text: str) -> list[tuple[str, int, int]]:
    return [(match.group(0), match.start(), match.end()) for match in WORD.finditer(text)]


def seed_atoms(values: list[str]) -> set[str]:
    result = set()
    for value in values:
        result.update(part for part in normalized_term(value).split() if len(part) >= 3)
    return result


def logical(value):
    if isinstance(value, dict):
        return {key: logical(item) for key, item in value.items()
                if key not in {"discovered_at", "retrieved_at"}}
    if isinstance(value, list):
        return [logical(item) for item in value]
    return value
