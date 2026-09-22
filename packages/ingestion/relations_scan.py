"""GĐ7, orchestration — the expanding-scope relation scan for ONE new
document (T2.6, 06 Mục 5.3 + Mục 5.5, 07 S8).

`packages/ingestion/relations.py` gives two detectors that each take a flat
list of `Document` and treat it as one already-decided scan set. Neither
decides WHICH documents belong in that set, nor WHEN to stop looking. This
module is the missing half: it grows the scan set one hop at a time —
*"Phạm vi xét: mở rộng dần, chạy ngầm — bắt đầu từ Space chứa tài liệu, mở
rộng dần cho tới khi xác định không nên mở thêm"* (06 Mục 5.3) — and applies
the S8 stop criteria (07) to decide when the document may stop saying "chưa
đối chiếu xong".

--------------------------------------------------------------------------
Where the scan is allowed to expand — PO decision (Viet, 22/9/2026)
--------------------------------------------------------------------------

Expansion follows the INHERITING Space tree (parent/child), and is **cut at
a private branch** — the same invariant as 06 line 33 / line 72: *"Tri thức
tổ chức thành cây Space; quyền chảy một chiều xuống ... và cắt tại nhánh
riêng."* It does NOT widen to the whole tenant, and it does NOT stop at the
single Space holding the document.

⚠️ This is a SCAN-SCOPE decision, not a permission decision. Ingestion never
decides who may read what (NT1, R4) — the tree is borrowed here only to
bound how far a content comparison may reach. Nothing about the tree is
written anywhere by this module: the shape is read fresh through
`SpaceScanScope` on every call and discarded, exactly as NT3 requires
("không lưu thứ sẽ cũ đi").

--------------------------------------------------------------------------
Why two Protocols instead of a Space store
--------------------------------------------------------------------------

Space hierarchy is outside both sources of truth (07 Mục 0: *"Không bao gồm
hợp đồng với Backend"*), so this module defines the two questions it needs
answered and lets a later layer answer them — the same shape as
`FingerprintIndex` in `intake.py`, which names the fingerprint lookup
without choosing where the index lives.

--------------------------------------------------------------------------
What this module deliberately does NOT do
--------------------------------------------------------------------------

It does not write `document.relations_scan_state`. It returns a
*recommended* value and nothing else, matching the "máy gợi ý, người xác
nhận" / "return, never persist" shape of every other module under
`packages/ingestion/` (see `labeling.py`, `relations.py`). The caller owns
persistence.

It does not read configuration. `saturation_epsilon`, `saturation_rounds`,
`scan_pair_budget` and `scan_time_budget` are required arguments —
a default here would be the parameter's second home (CLAUDE.md Mục 3 #2,
R5). The caller reads `config/ingestion.yaml` through
`schema.config.IngestionConfig` and passes the values down, the same way
`cat_thanh_mau()` receives `chunk_length_cap`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from ingestion.relations import (
    detect_explicit_relations,
    detect_inferred_amendment_relations,
)
from schema.document import Document, RelationsScanState
from schema.relation import Relation, RelationType

__all__ = [
    "InMemorySpace",
    "InMemorySpaceDocumentSource",
    "InMemorySpaceScanScope",
    "RelationsScanResult",
    "SpaceDocumentSource",
    "SpaceScanScope",
    "scan_relations_for_new_document",
]


# ---------------------------------------------------------------------------
# The two questions this module asks of a layer it does not own.
# ---------------------------------------------------------------------------


class SpaceScanScope(Protocol):
    """One hop of scope growth over the Space tree.

    `expand` returns the scan scope AFTER ONE further round of widening. It
    never shrinks: the returned set always contains `current_space_ids`.
    When there is nothing left to widen into it returns `current_space_ids`
    unchanged — that fixed point is how the scan learns it has "xác định
    không nên mở thêm" (06 Mục 5.3).

    The real implementation (outside this work-order) owns the "cắt tại
    nhánh riêng" rule: a private (`riêng`) child is NOT crossed into, and a
    private Space does not reach up to its parent. `InMemorySpaceScanScope`
    below shows the rule applied, for tests and single-process runs.
    """

    def expand(self, current_space_ids: frozenset[str]) -> frozenset[str]: ...


class SpaceDocumentSource(Protocol):
    """Every document living in the given Spaces.

    The real implementation (outside this work-order) decides what "living"
    excludes — in particular whether a document already marked
    `removed_as_wrong` is handed back. This module does not filter: it
    compares whatever it is given, exactly as the two detectors in
    `relations.py` do. See the Escalations note in the T2.6 report.
    """

    def documents_in(self, space_ids: frozenset[str]) -> list[Document]: ...


# ---------------------------------------------------------------------------
# Minimal in-memory implementations — tests and single-process runs only,
# NOT the real store (same disclaimer as `InMemoryFingerprintIndex`).
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class InMemorySpace:
    """One node of a Space tree, carrying only what scope expansion needs.

    `inherits_from_parent` is the live "kế thừa / riêng" flag (06 line 32):
    `False` — the default, matching *"Khi tạo Space mới mà không chỉ định
    thì mặc định là riêng"* — marks the edge to the parent as NOT
    traversable in either direction, which is the branch cut.
    """

    space_id: str
    parent_space_id: str | None = None
    inherits_from_parent: bool = False


class InMemorySpaceScanScope:
    """`SpaceScanScope` over an in-memory tree, widening ONE hop per call.

    A hop crosses an edge only when the CHILD end of that edge inherits:
    upward from an inheriting child to its parent, and downward from a
    parent to its inheriting children. A `riêng` child is therefore
    unreachable from outside and cannot reach out — the cut of 06 line 33.
    """

    def __init__(self, spaces: list[InMemorySpace]) -> None:
        self._by_id = {space.space_id: space for space in spaces}
        self._children: dict[str, list[InMemorySpace]] = {}
        for space in spaces:
            if space.parent_space_id is not None:
                self._children.setdefault(space.parent_space_id, []).append(space)

    def expand(self, current_space_ids: frozenset[str]) -> frozenset[str]:
        widened = set(current_space_ids)
        for space_id in current_space_ids:
            space = self._by_id.get(space_id)
            if space is None:
                # Unknown id: keep it, never guess a parent for it.
                continue
            if space.inherits_from_parent and space.parent_space_id is not None:
                widened.add(space.parent_space_id)
            for child in self._children.get(space_id, []):
                if child.inherits_from_parent:
                    widened.add(child.space_id)
        return frozenset(widened)


class InMemorySpaceDocumentSource:
    """`SpaceDocumentSource` over a fixed list, preserving list order so a
    truncated round (pair budget) is deterministic."""

    def __init__(self, documents: list[Document]) -> None:
        self._documents = list(documents)

    def documents_in(self, space_ids: frozenset[str]) -> list[Document]:
        return [document for document in self._documents if document.space_id in space_ids]


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class RelationsScanResult:
    """What one complete scan pass over one new document produced.

    `recommended_scan_state` is a RECOMMENDATION — this module never writes
    `document.relations_scan_state` (see module docstring).

    `rounds_run` counts every loop iteration, including a final iteration
    that found no new candidate (that iteration is how the scan observes it
    has run out of Spaces).
    """

    relations: list[Relation] = field(default_factory=list)
    recommended_scan_state: RelationsScanState = RelationsScanState.EXPANDING
    rounds_run: int = 0
    pairs_compared: int = 0


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------

_RelationKey = tuple[str, str, RelationType]


def _relation_key(relation: Relation) -> _RelationKey:
    return (relation.from_document_id, relation.to_document_id, relation.relation_type)


def _confidence_rank(relation: Relation) -> float:
    """`None` sorts below every real score.

    Neither detector currently returns `None` (a Manager-assigned link does,
    and those never come from here — 07 Mục 2.3), but ranking it explicitly
    keeps "no machine score" from winning a tie-break by accident.
    """
    return relation.confidence if relation.confidence is not None else -1.0


def _touches(relation: Relation, document_id: str) -> bool:
    return document_id in (relation.from_document_id, relation.to_document_id)


def _deduplicate(relations: list[Relation]) -> dict[_RelationKey, Relation]:
    """One `(from, to, type)` triple keeps ONE relation — the one with the
    higher confidence (work-order: a pair must not come back as two
    relations of the same type just because both detectors proposed it).
    """
    best: dict[_RelationKey, Relation] = {}
    for relation in relations:
        key = _relation_key(relation)
        current = best.get(key)
        if current is None or _confidence_rank(relation) > _confidence_rank(current):
            best[key] = relation
    return best


def _detect_over(new_document: Document, candidates: list[Document]) -> dict[_RelationKey, Relation]:
    """Run BOTH detectors over the whole accumulated scan set and keep only
    what touches `new_document`.

    Why the whole accumulated set, and not just this round's newcomers:
    `detect_explicit_relations` refuses to guess when two documents in the
    SAME call share a `doc_number` ("ambiguous match"). Feeding it one round
    at a time would hide a collision whose two halves arrived in different
    rounds, and the scan would emit exactly the guess that guard exists to
    prevent. Recomputing over the full set each round also means a relation
    can DISAPPEAR when a later round reveals such a collision — which is why
    the caller below replaces its result set each round instead of
    accumulating into it.

    Relations between two candidates are discarded: this is the scan of ONE
    new document (06 Mục 5.5: *"Tái cơ cấu quan hệ ... ngay khi có tài liệu
    mới vào kho ... mở rộng dần từ Space chứa nó"*), and each of those
    candidates had — or will have — its own scan.
    """
    scan_set = [new_document, *candidates]
    proposed = [
        *detect_explicit_relations(scan_set),
        *detect_inferred_amendment_relations(scan_set),
    ]
    return _deduplicate(
        [relation for relation in proposed if _touches(relation, new_document.document_id)]
    )


# ---------------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------------


def scan_relations_for_new_document(
    new_document: Document,
    *,
    scope: SpaceScanScope,
    document_source: SpaceDocumentSource,
    saturation_epsilon: float,
    saturation_rounds: int,
    scan_pair_budget: int,
    scan_time_budget: float,
    clock: Callable[[], float] = time.monotonic,
) -> RelationsScanResult:
    """One complete expanding-scope relation scan for one newly ingested
    document (06 Mục 5.3, S8 in 07).

    Starts at `new_document.space_id` and widens one hop per round through
    `scope`, comparing `new_document` against every candidate the widened
    scope newly exposes.

    ---------------------------------------------------------------------
    S8 — the two stop conditions, which must hold TOGETHER
    ---------------------------------------------------------------------

    07 S8: *"Bão hoà một mình thì có thể không bao giờ đạt; trần chi phí một
    mình thì dừng khi hết tiền chứ không phải khi đã đủ. Chỉ khi cả hai cùng
    thoả, `relations_scan_state` mới được chuyển sang đã dừng."*

    1. **Saturation** — `saturation_rounds` CONSECUTIVE rounds whose
       new-relation yield stayed below `saturation_epsilon`.
    2. **Cost ceiling** — `scan_pair_budget` pairs compared, OR
       `scan_time_budget` minutes elapsed, OR the scan scope exhausted (see
       just below). (This inner "or" is the only "or" in S8; the outer
       relationship between 1 and 2 is "and".)

    Both → `STOPPED`; otherwise the recommendation stays `EXPANDING`, i.e.
    the answer keeps saying "chưa đối chiếu xong".

    **"Scope exhausted" counts as the cost ceiling — PO decision, 22/9/2026
    (escalation E1 of this work-order).** A round that ends with `expand`
    at its fixed point AND no new candidate has spent everything there was
    to spend: there is no further pair anywhere in reach to buy. Reading
    condition 2 as "đã chạm N cặp hoặc T phút" and nothing else left a kho
    of a few documents permanently at `EXPANDING` — it saturates after four
    pairs and never comes near 500 pairs or 10 minutes, so `STOPPED` was
    unreachable and every such document kept the "chưa đối chiếu xong"
    caveat forever. Worse, the misconfiguration hint printed beside the
    value in `config/ingestion.yaml` for exactly that symptom ("Tài liệu mới
    lâu ngày vẫn mang nhãn 'chưa đối chiếu xong' → nới") pushes the operator
    the wrong way in that case: loosening the budget makes the ceiling
    HARDER to reach. The saturation condition is untouched by this — only
    the definition of "trần chi phí" widens, and the two still have to hold
    together.

    What stays `EXPANDING` is therefore the case S8 wrote the "and" for:
    cut off with budget spent but not saturated — *"dừng khi hết tiền chứ
    không phải khi đã đủ"* — where "nới" is the right remedy.

    ---------------------------------------------------------------------
    "Tỷ lệ phát hiện quan hệ mới" — DESIGNED HERE, not verified with PO
    ---------------------------------------------------------------------

    Read as: `(relations newly discovered this round) / (pairs newly
    compared this round)`. The denominator is pairs because
    `scan_pair_budget` is already denominated in pairs (07 Mục 3.2: *"trần
    số cặp đối chiếu"*), so a ratio over the same unit is the one that can
    be compared against the budget's own spend. "Newly discovered" counts
    `(from, to, type)` triples absent from the previous round's result — a
    confidence upgrade on a triple already found is not a discovery.

    A round that compares ZERO new pairs counts as saturated **immediately**
    rather than as one more round on the streak (work-order: *"Nếu vòng đó
    có 0 cặp mới (đã hết Space để mở rộng), coi là bão hoà ngay"*) — there
    is no division by zero, and no reason to spin `saturation_rounds`
    no-op rounds to learn something already known.

    ---------------------------------------------------------------------
    Time
    ---------------------------------------------------------------------

    `scan_time_budget` is IN MINUTES — the unit lives here and in
    `config/ingestion.yaml`, not in the parameter's name: the key name is
    what 07 Mục 3.2 chốt and what PO re-confirmed 18/9/2026 when the
    `_minutes` suffix was dropped, and a parameter carrying a second spelling
    of a config key is that key's second home.

    `clock` is injected so a test can make time pass without waiting; the
    elapsed check happens at round boundaries, never inside a round, so a
    single round always runs to completion once started.
    """
    budget_seconds = scan_time_budget * 60.0  # `scan_time_budget` IS IN MINUTES
    started_at = clock()

    current_space_ids = frozenset({new_document.space_id})
    compared_document_ids = {new_document.document_id}
    candidates: list[Document] = []

    relations_by_key: dict[_RelationKey, Relation] = {}
    previous_keys: set[_RelationKey] = set()

    rounds_run = 0
    pairs_compared = 0
    low_yield_streak = 0

    while True:
        rounds_run += 1

        remaining_budget = scan_pair_budget - pairs_compared
        newcomers: list[Document] = []
        if remaining_budget > 0:
            for document in document_source.documents_in(current_space_ids):
                if document.document_id in compared_document_ids:
                    continue
                newcomers.append(document)
                if len(newcomers) == remaining_budget:
                    # The ceiling is a ceiling, not a quota: a round is cut
                    # short rather than allowed to overshoot it.
                    break

        if newcomers:
            for document in newcomers:
                compared_document_ids.add(document.document_id)
            candidates.extend(newcomers)
            pairs_compared += len(newcomers)

            relations_by_key = _detect_over(new_document, candidates)
            newly_found = set(relations_by_key) - previous_keys
            previous_keys = set(relations_by_key)

            yield_ratio = len(newly_found) / len(newcomers)
            low_yield_streak = low_yield_streak + 1 if yield_ratio < saturation_epsilon else 0
        else:
            low_yield_streak = saturation_rounds

        elapsed_seconds = clock() - started_at
        saturated = low_yield_streak >= saturation_rounds

        if pairs_compared >= scan_pair_budget or elapsed_seconds >= budget_seconds:
            # Ceiling reached by spend. Saturated too → S8 satisfied on both
            # counts; not saturated → cut off with the budget gone, S8's
            # "dừng khi hết tiền chứ không phải khi đã đủ", so the document
            # keeps saying "chưa đối chiếu xong".
            return _result(
                relations_by_key,
                RelationsScanState.STOPPED if saturated else RelationsScanState.EXPANDING,
                rounds_run,
                pairs_compared,
            )

        widened_space_ids = scope.expand(current_space_ids)
        if widened_space_ids == current_space_ids and not newcomers:
            # Scope exhausted: fixed point AND nothing new this round. Every
            # further round is a no-op, so waiting for the pair or time
            # ceiling would only burn wall-clock to learn nothing — and this
            # counts as the cost ceiling in its own right (PO 22/9/2026, see
            # docstring), because there is no pair left anywhere in reach to
            # spend budget on.
            return _result(
                relations_by_key,
                RelationsScanState.STOPPED if saturated else RelationsScanState.EXPANDING,
                rounds_run,
                pairs_compared,
            )
        current_space_ids = widened_space_ids


def _result(
    relations_by_key: dict[_RelationKey, Relation],
    recommended_scan_state: RelationsScanState,
    rounds_run: int,
    pairs_compared: int,
) -> RelationsScanResult:
    return RelationsScanResult(
        relations=list(relations_by_key.values()),
        recommended_scan_state=recommended_scan_state,
        rounds_run=rounds_run,
        pairs_compared=pairs_compared,
    )
