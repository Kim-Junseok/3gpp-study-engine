import hashlib

import pytest

from threegpp.ingest import NormalizedConflictError, NormalizedIntegrityError, NormalizedStore
from threegpp.models import TDocMetadata


def records() -> list[TDocMetadata]:
    return [
        TDocMetadata(tdoc_id="R2-2505002", working_group="RAN2", meeting="131"),
        TDocMetadata(
            tdoc_id="R2-2505001", working_group="RAN2", meeting="131",
            title="Portable metadata", official_list_present=True,
            metadata_source_kind="tdoc_list",
            metadata_source_url="https://www.3gpp.org/list.xlsx",
        ),
    ]


def test_normalized_jsonl_gzip_is_deterministic_and_validated(tmp_path) -> None:
    store = NormalizedStore(tmp_path / "data" / "normalized")

    first = store.write_current("RAN2", "131", records())
    second = store.write_current("RAN2", "131", list(reversed(records())))

    assert first == second
    assert first.rows == 2
    assert first.path.suffixes == [".jsonl", ".gz"]
    path = store.resolve(first.path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == first.sha256
    assert [item.tdoc_id for item in store.read(first)] == ["R2-2505001", "R2-2505002"]

    path.write_bytes(path.read_bytes() + b"corrupt")
    with pytest.raises(NormalizedIntegrityError):
        store.read(first)
    with pytest.raises(NormalizedConflictError):
        store.write_current("RAN2", "131", records())
