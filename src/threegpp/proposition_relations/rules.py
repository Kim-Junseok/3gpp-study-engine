from __future__ import annotations

from threegpp.propositions.rules import digest

from .models import RelationBasisSpan


def organization_key(value: str) -> str:
    return " ".join(value.split()).casefold()


def organization_keys(values: list[str]) -> frozenset[str]:
    return frozenset(organization_key(value) for value in values if value.strip())


def full_basis(proposition) -> list[RelationBasisSpan]:
    return [RelationBasisSpan(segment_index=index, char_start=0,
                              char_end=len(text), exact_text=text)
            for index, text in enumerate(proposition.exact_text_segments) if text]


def pair_identity(left_proposition_id: str, right_proposition_id: str) -> tuple[str, str, str]:
    left, right = sorted((left_proposition_id, right_proposition_id))
    return left, right, "proposition-pair-" + digest({"left": left, "right": right})
