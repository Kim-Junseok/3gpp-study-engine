from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.documents.models import DocumentReceipt, ExtractionStatus
from threegpp.models import (
    EvidenceRef, EvidenceSearchHit, EvidenceSearchQuery, IndexOutcome, MatchKind,
    TDocSearchHit,
)

SEARCH_INDEX_SCHEMA_VERSION = "1"
TOKENIZER_VERSION = "1"
SCORING_VERSION = "bm25-block-v1"
BM25_K1 = 1.2
BM25_B = 0.75
PHRASE_BONUS = 2.0
HEADING_BONUS = 0.35
TITLE_BONUS = 0.15
STOPWORDS = frozenset({"a", "an", "and", "for", "of", "the", "to"})
_TOKEN = re.compile(r"[a-z0-9]+(?:[-#][a-z0-9]+)*", re.IGNORECASE)
_INDEXABLE = {ExtractionStatus.PARSED, ExtractionStatus.PARTIALLY_PARSED}


def tokenize(text: str) -> list[str]:
    """Conservative, versioned telecom tokenizer with explainable aliases."""
    result: list[str] = []
    for match in _TOKEN.finditer(text.casefold()):
        token = match.group(0)
        variants = [token]
        if "-" in token:
            variants.extend(part for part in token.split("-") if part)
        if "#" in token:
            variants.extend(part for part in token.split("#") if part)
        for variant in variants:
            if variant not in STOPWORDS:
                result.append(variant)
    return result


def parse_query(query: str) -> tuple[list[str], list[str]]:
    phrases = [match.group(1) for match in re.finditer(r'"([^"\n]+)"', query)]
    unquoted = re.sub(r'"([^"\n]+)"', r"\1", query)
    return tokenize(unquoted), phrases


class EvidenceSearchService:
    """Offline lexical retrieval over derived postings and current normalized blocks."""

    def __init__(self, repository: MetadataRepository, data_root: Path):
        self.repository = repository
        self.connection = repository.connection
        self.data_root = Path(data_root)

    def index_document(self, receipt: DocumentReceipt) -> IndexOutcome:
        key = [receipt.tdoc_id, receipt.working_group.value, receipt.meeting]
        identity = receipt.normalization_identity.model_dump_json() if receipt.normalization_identity else None
        indexable = receipt.extraction_status in _INDEXABLE and receipt.normalized_path is not None
        path = self.data_root / receipt.normalized_path if receipt.normalized_path else None
        if not indexable:
            return self._clear_and_state(receipt, "NOT_INDEXABLE", identity)
        if path is None or not path.is_file() or _sha(path) != receipt.normalized_checksum:
            return self._clear_and_state(receipt, "STALE", identity)
        current = self.connection.execute(
            "SELECT status, normalization_identity_json, normalized_checksum, index_schema_version, tokenizer_version, indexed_block_count, posting_count FROM search_index_state WHERE tdoc_id=? AND working_group=? AND meeting_number=?",
            key,
        ).fetchone()
        if current and tuple(current[:5]) == ("INDEXED", identity, receipt.normalized_checksum, SEARCH_INDEX_SCHEMA_VERSION, TOKENIZER_VERSION):
            return IndexOutcome(tdoc_id=receipt.tdoc_id, working_group=receipt.working_group,
                meeting=receipt.meeting, status="INDEXED", indexed_blocks=current[5],
                postings=current[6], reused=True)
        try:
            blocks = _read_blocks(path)
            block_rows, posting_rows = [], []
            for block in blocks:
                text = _block_text(block)
                counts = Counter(tokenize(text))
                if not counts:
                    continue
                block_rows.append(key + [block["member_filename"], block["block_id"], block["type"],
                    json.dumps(block.get("heading_path", [])), block.get("page_number"),
                    block.get("sheet_name"), sum(counts.values())])
                posting_rows.extend([[term] + key + [block["member_filename"], block["block_id"], frequency]
                                     for term, frequency in sorted(counts.items())])
        except Exception as exc:
            return self._clear_and_state(receipt, "FAILED", identity, str(exc)[:500])
        self.connection.execute("BEGIN")
        try:
            self._delete_rows(key)
            if block_rows:
                self.connection.executemany("INSERT INTO search_blocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", block_rows)
            if posting_rows:
                self.connection.executemany("INSERT INTO search_postings VALUES (?, ?, ?, ?, ?, ?, ?)", posting_rows)
            self._write_state(receipt, "INDEXED", identity, len(block_rows), len(posting_rows))
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        self.connection.execute("COMMIT")
        return IndexOutcome(tdoc_id=receipt.tdoc_id, working_group=receipt.working_group,
            meeting=receipt.meeting, status="INDEXED", indexed_blocks=len(block_rows), postings=len(posting_rows))

    def index_documents(self) -> list[IndexOutcome]:
        rows = self.connection.execute("SELECT receipt_json FROM tdoc_documents ORDER BY working_group, meeting_number, tdoc_id").fetchall()
        outcomes = [self.index_document(DocumentReceipt.model_validate_json(row[0])) for row in rows]
        known = {(item.tdoc_id, item.working_group.value, item.meeting) for item in outcomes}
        stale = self.connection.execute("SELECT tdoc_id, working_group, meeting_number FROM search_index_state").fetchall()
        for key in stale:
            if tuple(key) not in known:
                self._delete_rows(list(key))
                self.connection.execute("UPDATE search_index_state SET status='STALE' WHERE tdoc_id=? AND working_group=? AND meeting_number=?", key)
        return outcomes

    def get_evidence_block(self, evidence: EvidenceRef) -> dict:
        row = self.connection.execute(
            "SELECT receipt_json FROM tdoc_documents WHERE tdoc_id=? AND working_group=? AND meeting_number=?",
            [evidence.tdoc_id, evidence.working_group.value, evidence.meeting],
        ).fetchone()
        if not row:
            raise ValueError("evidence document is missing")
        receipt = DocumentReceipt.model_validate_json(row[0])
        if receipt.normalized_path is None:
            raise ValueError("evidence document is not normalized")
        path = self.data_root / receipt.normalized_path
        if not path.is_file() or _sha(path) != receipt.normalized_checksum:
            self._mark_stale([evidence.tdoc_id, evidence.working_group.value, evidence.meeting])
            raise ValueError("normalized evidence is missing or changed")
        block = next((item for item in _read_blocks(path) if item["member_filename"] == evidence.member and item["block_id"] == evidence.block_id), None)
        if block is None:
            self._mark_stale([evidence.tdoc_id, evidence.working_group.value, evidence.meeting])
            raise ValueError("normalized evidence block is missing")
        return block

    def search_evidence(self, query: EvidenceSearchQuery | str) -> list[EvidenceSearchHit]:
        query = EvidenceSearchQuery(query=query) if isinstance(query, str) else query
        terms, phrases = parse_query(query.query)
        unique_terms = sorted(set(terms))
        if not unique_terms:
            return []
        clauses = ["s.status='INDEXED'", "p.term IN (" + ",".join("?" for _ in unique_terms) + ")"]
        values: list[object] = list(unique_terms)
        filters = [("b.working_group", query.working_groups), ("b.meeting_number", query.meetings),
                   ("b.tdoc_id", query.tdoc_ids), ("b.block_type", query.block_types),
                   ("d.extraction_status", query.extraction_statuses), ("d.retention_state", query.retention_states)]
        for column, wanted in filters:
            if wanted:
                clauses.append(column + " IN (" + ",".join("?" for _ in wanted) + ")")
                values.extend(item.value if hasattr(item, "value") else item for item in wanted)
        for org in query.organizations:
            clauses.append("lower(m.organizations_json) LIKE ?")
            values.append(f'%"{org.casefold()}"%')
        sql = """SELECT b.tdoc_id,b.working_group,b.meeting_number,b.member_filename,b.block_id,
          b.block_type,b.heading_path_json,b.page_number,b.sheet_name,b.token_count,
          m.title,m.organizations_json,p.term,p.term_frequency
          FROM search_postings p JOIN search_blocks b USING(tdoc_id,working_group,meeting_number,member_filename,block_id)
          JOIN search_index_state s USING(tdoc_id,working_group,meeting_number)
          JOIN tdoc_documents d USING(tdoc_id,working_group,meeting_number)
          LEFT JOIN tdoc_metadata m USING(tdoc_id,working_group,meeting_number)
          WHERE """ + " AND ".join(clauses)
        rows = self.connection.execute(sql, values).fetchall()
        grouped: dict[tuple, list] = defaultdict(list)
        for row in rows: grouped[tuple(row[:12])].append(row[12:])
        corpus = self.connection.execute("SELECT count(*), coalesce(avg(token_count),0) FROM search_blocks").fetchone()
        n_blocks, avg_len = corpus[0], float(corpus[1]) or 1.0
        dfs = dict(self.connection.execute("SELECT term,count(*) FROM search_postings WHERE term IN (" + ",".join("?" for _ in unique_terms) + ") GROUP BY term", unique_terms).fetchall())
        hits = []
        verified_documents: dict[tuple[str, str, str], dict[tuple[str, str], dict] | None] = {}
        for key, postings in grouped.items():
            ref = EvidenceRef(tdoc_id=key[0], working_group=key[1], meeting=key[2], member=key[3], block_id=key[4], block_type=key[5], heading_path=json.loads(key[6]), page=key[7], sheet=key[8])
            document_key = tuple(key[:3])
            if document_key not in verified_documents:
                verified_documents[document_key] = self._verified_document_blocks(document_key)
            document_blocks = verified_documents[document_key]
            if document_blocks is None:
                continue
            block = document_blocks.get((ref.member, ref.block_id))
            if block is None:
                self._mark_stale(list(document_key))
                verified_documents[document_key] = None
                continue
            text = _block_text(block); text_tokens = tokenize(text); matched = sorted({p[0] for p in postings})
            contributions = {}
            for term, tf in postings:
                idf = math.log(1 + (n_blocks - dfs[term] + 0.5) / (dfs[term] + 0.5))
                score = idf * (tf * (BM25_K1 + 1)) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * key[9] / avg_len))
                contributions[term] = round(score, 8)
            phrase_results = [_contains_token_phrase(text_tokens, tokenize(phrase)) for phrase in phrases]
            phrase_match = bool(phrase_results) and all(phrase_results)
            # Quotation is a constraint, not a scoring hint that silently falls
            # back to ordinary lexical similarity.
            if phrases and not phrase_match:
                continue
            all_tokens = set(unique_terms).issubset(matched)
            heading_tokens = set(tokenize(" ".join(ref.heading_path)))
            title_tokens = set(tokenize(key[10] or ""))
            phrase_bonus = PHRASE_BONUS if phrase_match else 0.0
            heading_bonus = HEADING_BONUS * len(set(matched) & heading_tokens)
            title_bonus = TITLE_BONUS * len(set(matched) & title_tokens)
            final = sum(contributions.values()) + phrase_bonus + heading_bonus + title_bonus
            hits.append(EvidenceSearchHit(evidence=ref, title=key[10], source_organizations=json.loads(key[11] or "[]"), score=round(final, 8), matched_terms=matched,
                match_kind=MatchKind.EXACT_PHRASE if phrase_match else MatchKind.ALL_TOKENS if all_tokens else MatchKind.PARTIAL_TOKENS,
                phrase_match=phrase_match, score_explanation={"scoring_version": SCORING_VERSION, "bm25": contributions, "phrase_bonus": phrase_bonus, "heading_bonus": heading_bonus, "title_bonus": title_bonus, "k1": BM25_K1, "b": BM25_B}, snippet=_snippet(text, matched)))
        hits.sort(key=lambda hit: (-hit.score, hit.evidence.tdoc_id, hit.evidence.member, hit.evidence.block_id))
        return hits[:query.limit]

    def search_tdocs(self, query: EvidenceSearchQuery | str) -> list[TDocSearchHit]:
        q = EvidenceSearchQuery(query=query, limit=1000) if isinstance(query, str) else query.model_copy(update={"limit": 1000})
        grouped = defaultdict(list)
        for hit in self.search_evidence(q):
            grouped[(hit.evidence.tdoc_id, hit.evidence.working_group, hit.evidence.meeting)].append(hit)
        result = [TDocSearchHit(tdoc_id=k[0], working_group=k[1], meeting=k[2], best_block=v[0], matching_block_count=len(v), aggregate_score=round(sum(h.score for h in v), 8)) for k, v in grouped.items()]
        result.sort(key=lambda item: (-item.aggregate_score, item.tdoc_id))
        return result[:query.limit] if isinstance(query, EvidenceSearchQuery) else result[:20]

    def inspect_index(self) -> list[dict]:
        """Return explicit lifecycle/freshness state without inferring from mtimes."""
        columns = [
            "tdoc_id", "working_group", "meeting", "status",
            "normalization_identity", "normalized_path", "normalized_checksum",
            "index_schema_version", "tokenizer_version", "indexed_block_count",
            "posting_count", "indexed_at", "error",
        ]
        rows = self.connection.execute(
            "SELECT tdoc_id,working_group,meeting_number,status,normalization_identity_json,"
            "normalized_path,normalized_checksum,index_schema_version,tokenizer_version,"
            "indexed_block_count,posting_count,indexed_at,error FROM search_index_state "
            "ORDER BY working_group,meeting_number,tdoc_id"
        ).fetchall()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def _delete_rows(self, key):
        for table in ("search_postings", "search_blocks"):
            self.connection.execute(f"DELETE FROM {table} WHERE tdoc_id=? AND working_group=? AND meeting_number=?", key)

    def _verified_document_blocks(self, key: tuple[str, str, str]) -> dict[tuple[str, str], dict] | None:
        row = self.connection.execute(
            "SELECT d.receipt_json,s.status,s.normalization_identity_json,s.normalized_checksum,"
            "s.index_schema_version,s.tokenizer_version FROM tdoc_documents d "
            "JOIN search_index_state s USING(tdoc_id,working_group,meeting_number) "
            "WHERE d.tdoc_id=? AND d.working_group=? AND d.meeting_number=?",
            key,
        ).fetchone()
        if row is None:
            return None
        receipt = DocumentReceipt.model_validate_json(row[0])
        identity = receipt.normalization_identity.model_dump_json() if receipt.normalization_identity else None
        expected_state = (
            "INDEXED", identity, receipt.normalized_checksum,
            SEARCH_INDEX_SCHEMA_VERSION, TOKENIZER_VERSION,
        )
        if tuple(row[1:]) != expected_state or receipt.normalized_path is None:
            self._mark_stale(list(key))
            return None
        path = self.data_root / receipt.normalized_path
        if not path.is_file() or _sha(path) != receipt.normalized_checksum:
            self._mark_stale(list(key))
            return None
        try:
            blocks = _read_blocks(path)
        except Exception:
            self._mark_stale(list(key))
            return None
        current = {(block["member_filename"], block["block_id"]): block for block in blocks}
        locators = self.connection.execute(
            "SELECT member_filename,block_id,block_type,heading_path_json,page_number,sheet_name "
            "FROM search_blocks WHERE tdoc_id=? AND working_group=? AND meeting_number=?",
            key,
        ).fetchall()
        for member, block_id, block_type, heading_json, page, sheet in locators:
            block = current.get((member, block_id))
            if block is None or (
                block.get("type"), block.get("heading_path", []),
                block.get("page_number"), block.get("sheet_name"),
            ) != (block_type, json.loads(heading_json), page, sheet):
                self._mark_stale(list(key))
                return None
        return current

    def _mark_stale(self, key):
        self._delete_rows(key)
        self.connection.execute("UPDATE search_index_state SET status='STALE', indexed_block_count=0, posting_count=0 WHERE tdoc_id=? AND working_group=? AND meeting_number=?", key)

    def _clear_and_state(self, receipt, status, identity, error=None):
        key = [receipt.tdoc_id, receipt.working_group.value, receipt.meeting]; self._delete_rows(key)
        self._write_state(receipt, status, identity, 0, 0, error)
        return IndexOutcome(tdoc_id=receipt.tdoc_id, working_group=receipt.working_group, meeting=receipt.meeting, status=status)

    def _write_state(self, receipt, status, identity, blocks, postings, error=None):
        self.connection.execute("INSERT OR REPLACE INTO search_index_state VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [receipt.tdoc_id, receipt.working_group.value, receipt.meeting, status, identity, str(receipt.normalized_path) if receipt.normalized_path else None, receipt.normalized_checksum, SEARCH_INDEX_SCHEMA_VERSION, TOKENIZER_VERSION, blocks, postings, datetime.now(timezone.utc), error])


def _read_blocks(path: Path) -> list[dict]:
    return [json.loads(line) for line in gzip.decompress(path.read_bytes()).decode("utf-8").splitlines() if line]

def _block_text(block: dict) -> str:
    pieces = [block.get("text") or ""]
    pieces.extend("\t".join("" if cell is None else str(cell) for cell in row) for row in block.get("rows") or [])
    return "\n".join(piece for piece in pieces if piece)

def _contains_token_phrase(tokens: list[str], phrase: list[str]) -> bool:
    if not phrase or len(phrase) > len(tokens):
        return False
    return any(tokens[index:index + len(phrase)] == phrase for index in range(len(tokens) - len(phrase) + 1))

def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def _snippet(text: str, terms: list[str], limit: int = 240) -> str:
    # A bounded literal view: do not rewrite authoritative normalized whitespace.
    compact = text.strip()
    positions = [compact.casefold().find(term) for term in terms]
    found = [position for position in positions if position >= 0]
    start = max(0, (min(found) if found else 0) - 60)
    snippet = compact[start:start + limit]
    return ("…" if start else "") + snippet + ("…" if start + limit < len(compact) else "")
