"""GĐ7, step 1/2 — explicit-signal relation detection (T2.6, 06 Mục 5.3, 07
Mục 2.3).

Detects the two relation types that are read directly off a document's text,
no inference involved: REFERENCES ("Căn cứ <type> số <number>...") and
ATTACHMENT ("... kèm theo <type> số <number>..."). Both get
`origin=RelationOrigin.MACHINE_READ_EXPLICIT_REFERENCE` — `07` Mục 2.3 (DX1)
calls this origin "chắc chắn" (certain), same footing as a Manager's own
link, and `06` Mục 5.3 confirms explicit citations are still queued for
Manager approval, just fast-tracked: *"vẫn qua Manager, nhưng đánh dấu là
chắc chắn — hiện đầu hàng việc, duyệt nhanh."*

Deliberately NOT built here (separate work-orders):

- AMENDS_OR_REPLACES inferred from subject/type/date (06 Mục 5.3's K3 fix —
  needs `subject_entities`, a parallel work-order).
- SAME_TOPIC.
- The expanding-scope loop + `scan_pair_budget` / `scan_time_budget` /
  `saturation_epsilon` orchestration (06 Mục 5.3: *"Phạm vi xét: mở rộng
  dần, chạy ngầm — bắt đầu từ Space chứa tài liệu"*) — `detect_explicit_relations`
  takes a flat list of `Document` and treats it as one already-decided scan
  set (one Space's candidates); the caller owns the expansion loop.

Both patterns key on the standard Vietnamese administrative citation shape:
"<document type> số <number> ngày D tháng M năm Y của <authority>" — e.g.
"Nghị định số 14/2017/NĐ-CP ngày 17 tháng 02 năm 2017 của Chính phủ", a real
line from `data/test-corpus-vn-admin/nhan-su/10_2020_TT-BLDTBXH_454406.docx`.
A citation only becomes a `Relation` when its extracted number matches
another document's `doc_number` *within the same call's document list* — no
match, or an ambiguous match against more than one document sharing that
number, and nothing is produced (NT2: a miss here is accepted, not guessed
around).

⚠️ REFERENCES vs AMENDS_OR_REPLACES — a citation clause carrying amendment
vocabulary ("sửa đổi", "bổ sung", "thay thế", "bãi bỏ", "hết hiệu lực",
"thay cho") is excluded from REFERENCES, even if it starts with "Căn cứ".
Concrete case from the work-order (PO-verified against the real file
22/9/2026, `data/test-corpus-vn-admin/phap-che-tuan-thu/30_2020_ND_CP.docx`,
Điều 37): *"Nghị định này có hiệu lực thi hành kể từ ngày ký. Nghị định số
110/2004/NĐ-CP ngày 08 tháng 4 năm 2004 của Chính phủ về công tác văn thư ...
hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành."* — this must
NOT produce a REFERENCES relation toward 110-2004-nd-cp.docx. That specific
sentence is already excluded because it never follows "Căn cứ"; the
amendment-vocabulary guard is defense-in-depth for clauses that do.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date

from schema.document import Document
from schema.relation import ApprovalState, Relation, RelationOrigin, RelationType

__all__ = ["detect_explicit_relations"]

# ---------------------------------------------------------------------------
# Vietnamese administrative document-number shape: "<digits><opt letter>/
# <year>/<code>", e.g. "110/2004/NĐ-CP", "10/2020/TT-BLĐTBXH", "61/2020/QH14".
# ---------------------------------------------------------------------------
_DOCUMENT_NUMBER = r"\d+[A-Za-z]?/\d{2,4}/[A-ZĐƯĂÂÊÔƠ][A-ZĐƯĂÂÊÔƠ0-9\-]*"

_DOCUMENT_TYPE = (
    r"(?:Nghị\s+định|Nghị\s+quyết|Bộ\s+luật|Luật|"
    r"Thông\s+tư(?:\s+liên\s+tịch)?|Quyết\s+định|Chỉ\s+thị|Pháp\s+lệnh|Thông\s+báo)"
)

# "Căn cứ <type> số <number>" — the citing clause. `rest` (up to the next
# '.'/';'/newline) is kept so callers can look for a corroborating date/
# authority, or — for REFERENCES — amendment vocabulary that disqualifies it.
_REFERENCE_CLAUSE = re.compile(
    r"Căn\s+cứ\s+(?:vào\s+)?" + _DOCUMENT_TYPE + r"\s+số\s+(" + _DOCUMENT_NUMBER + r")"
    r"(?P<rest>[^.;\n]{0,200})",
    re.IGNORECASE,
)

# "(Ban hành) kèm theo <type> số <number>" — real phrasing, verbatim from
# `data/test-corpus-vn-admin/nhan-su/nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong.docx`:
# "Phụ lục III\n(Kèm theo Nghị định số 145/2020/NĐ-CP ngày 14 tháng 12 năm
# 2020 của Chính phủ)". In that source file the appendix is embedded in the
# SAME document it cites, so the match is a self-citation and produces no
# relation (see `_relations_from_document`) — but the identical phrase is
# exactly what a standalone appendix file, uploaded separately from its
# parent, would open with.
_ATTACHMENT_CLAUSE = re.compile(
    r"kèm\s+theo\s+" + _DOCUMENT_TYPE + r"\s+số\s+(" + _DOCUMENT_NUMBER + r")"
    r"(?P<rest>[^.;\n]{0,200})",
    re.IGNORECASE,
)

_AMENDMENT_LANGUAGE = re.compile(
    r"sửa\s+đổi|bổ\s+sung|thay\s+thế|bãi\s+bỏ|hết\s+hiệu\s+lực|thay\s+cho",
    re.IGNORECASE,
)

_CITATION_DATE = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE)
_CITATION_AUTHORITY = re.compile(r"của\s+[^\d,.;\n]{2,80}", re.IGNORECASE)


def _normalized_document_number(raw: str) -> str:
    return re.sub(r"\s+", "", raw).upper()


@dataclass(frozen=True, slots=True, kw_only=True)
class _Citation:
    document_number: str
    rest: str
    carries_amendment_language: bool


def _find_citations(pattern: re.Pattern[str], text: str) -> list[_Citation]:
    citations = []
    for match in pattern.finditer(text):
        rest = match.group("rest")
        citations.append(
            _Citation(
                document_number=_normalized_document_number(match.group(1)),
                rest=rest,
                carries_amendment_language=_AMENDMENT_LANGUAGE.search(rest) is not None,
            )
        )
    return citations


def _citation_confidence(rest: str, to_document: Document) -> float:
    """Additive signal, capped at 1.0 (work-order: "cộng dồn tín hiệu tới
    thang 1.0"). The document-number match itself is the necessary condition
    to produce a relation at all (0.7, applied by the caller before this is
    reached); a citation date matching `to_document.issued_date`, and a named
    issuing authority in the same clause, are corroborating — not required —
    signals on top of that.
    """
    score = 0.7
    date_match = _CITATION_DATE.search(rest)
    if date_match is not None:
        day, month, year = (int(group) for group in date_match.groups())
        try:
            cited_date = date(year, month, day)
        except ValueError:
            cited_date = None
        if cited_date is not None and cited_date == to_document.issued_date:
            score += 0.2
    if _CITATION_AUTHORITY.search(rest) is not None:
        score += 0.1
    return min(round(score, 2), 1.0)


def _relations_from_document(
    from_document: Document,
    candidates: list[Document],
    *,
    pattern: re.Pattern[str],
    relation_type: RelationType,
    exclude_amendment_language: bool,
) -> list[Relation]:
    """One document's citations turned into candidate relations toward the
    other documents in `candidates` that share the cited number.

    Keeps at most one relation per `to_document_id`: a document citing the
    same target twice (e.g. once in "Căn cứ", once again later) is one
    relationship, not two.
    """
    by_number: dict[str, list[Document]] = {}
    for candidate in candidates:
        if candidate.document_id == from_document.document_id:
            continue
        by_number.setdefault(_normalized_document_number(candidate.doc_number), []).append(candidate)

    best_by_target: dict[str, Relation] = {}
    for citation in _find_citations(pattern, from_document.extracted_text):
        if exclude_amendment_language and citation.carries_amendment_language:
            continue
        matches = by_number.get(citation.document_number, [])
        if len(matches) != 1:
            # Zero matches: the cited document isn't in this scan set — NT2
            # accepts the miss. More than one: `doc_number` collision inside
            # `candidates` — ambiguous, so no guess which one is meant.
            continue
        to_document = matches[0]
        confidence = _citation_confidence(citation.rest, to_document)
        existing = best_by_target.get(to_document.document_id)
        if existing is not None and existing.confidence is not None and existing.confidence >= confidence:
            continue
        best_by_target[to_document.document_id] = Relation(
            relation_id=str(uuid.uuid4()),
            from_document_id=from_document.document_id,
            to_document_id=to_document.document_id,
            relation_type=relation_type,
            origin=RelationOrigin.MACHINE_READ_EXPLICIT_REFERENCE,
            approval_state=ApprovalState.PENDING,
            confidence=confidence,
        )
    return list(best_by_target.values())


def detect_explicit_relations(documents: list[Document]) -> list[Relation]:
    """Scan every document in `documents` for REFERENCES and ATTACHMENT
    citations naming another document in the SAME list (06 Mục 5.3: scan
    scope is one Space's worth of candidates; the expanding-window loop is a
    later, separate work-order — see module docstring).

    Direction follows the CHỐT convention (`07` Mục 2.3): for REFERENCES,
    `from` = the citing document, `to` = the cited one ("văn bản viện dẫn" →
    "văn bản được viện dẫn"); for ATTACHMENT, `from` = the appendix, `to` =
    the main document ("phụ lục" → "văn bản chính") — in both patterns here,
    the document whose text CONTAINS the citation clause is `from`.
    """
    relations: list[Relation] = []
    for from_document in documents:
        relations.extend(
            _relations_from_document(
                from_document,
                documents,
                pattern=_REFERENCE_CLAUSE,
                relation_type=RelationType.REFERENCES,
                exclude_amendment_language=True,
            )
        )
        relations.extend(
            _relations_from_document(
                from_document,
                documents,
                pattern=_ATTACHMENT_CLAUSE,
                relation_type=RelationType.ATTACHMENT,
                exclude_amendment_language=False,
            )
        )
    return relations
