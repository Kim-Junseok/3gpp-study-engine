from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from .models import PackageMember
from .parsers import media_type, parser_for


class UnsafeArchiveError(ValueError): pass


@dataclass(frozen=True)
class InspectedMember:
    metadata: PackageMember
    data: bytes


def inspect_package(data: bytes, filename: str, *, max_member_bytes: int = 50_000_000, max_total_bytes: int = 200_000_000) -> list[InspectedMember]:
    if not zipfile.is_zipfile(io.BytesIO(data)) or filename.lower().endswith((".docx", ".xlsx")):
        return [_member(filename, data)]
    result, total = [], 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.is_dir(): continue
            normalized_name = info.filename.replace("\\", "/")
            path = PurePosixPath(normalized_name)
            if path.is_absolute() or re.match(r"^[A-Za-z]:/", normalized_name) or ".." in path.parts:
                raise UnsafeArchiveError(f"unsafe archive member path: {info.filename}")
            total += info.file_size
            if info.file_size > max_member_bytes or total > max_total_bytes:
                raise UnsafeArchiveError("archive expansion exceeds configured safety limit")
            result.append(_member(info.filename, archive.read(info)))
    supported = [item for item in result if parser_for(item.metadata.filename)]
    if len(supported) == 1:
        chosen = supported[0]
        result[result.index(chosen)] = InspectedMember(chosen.metadata.model_copy(update={"role": "probable_primary"}), chosen.data)
    return result


def _member(filename: str, data: bytes) -> InspectedMember:
    return InspectedMember(PackageMember(filename=filename, media_type=media_type(filename), byte_size=len(data), sha256=hashlib.sha256(data).hexdigest()), data)
