"""T2.6 (o) — *"BE không trả lời"* must not be mistaken for *"nothing left to
compare"* (docs/10 §7.1, added 24/9/2026).

docs/10 §7.1, verbatim: *"**BE không trả lời:** hoãn vòng quét, giữ trạng
thái "đang mở rộng", thử lại sau. Không đoán, không quét toàn kho. Trong lúc
đó câu trả lời tự nói "chưa đối chiếu xong" — cơ chế đã có (06 §5.1)."*

⭐ Why this needs its own file. From inside the scan loop the two situations
are one line apart and look identical: `expand` produced nothing new. They
mean opposite things.

* **Scope exhausted** — there is genuinely nothing further in reach. PO chốt
  22/9 that this counts as the cost ceiling, so a saturated scan may report
  `STOPPED` (see `test_m`).
* **Tree unreadable** — nobody knows what is in reach. Reporting `STOPPED`
  here would tell every future answer built on this document that
  reconciliation is complete, when no tree was ever consulted. NT2's third
  clause is precisely about this: *"chỗ nào bỏ sót gây hại thì phải NHÌN
  THẤY ĐƯỢC"*.

So the failure has to be a RAISE, not a fixed point, and the scan has to
treat it as a reason not to conclude.
"""

from __future__ import annotations

import pytest

from ingestion.relations_scan import (
    InMemorySpaceDocumentSource,
    InMemorySpace,
    InMemorySpaceScanScope,
    SpaceTopologyUnavailable,
    UnavailableSpaceScanScope,
    scan_relations_for_new_document,
)
from schema.document import RelationsScanState

from .conftest import CITATION_110, DOC_NUMBER_110, ISSUED_110, make_document

# The scan parameters, passed explicitly because the function has no defaults
# for them (they live in `config/ingestion.yaml`). Values are this file's own:
# nothing here is measuring a threshold, only which STATE is reported.
SATURATION_EPSILON = 0.01
SATURATION_ROUNDS = 3


def _scan(new_document, *, scope, documents):
    return scan_relations_for_new_document(
        new_document,
        scope=scope,
        document_source=InMemorySpaceDocumentSource(documents),
        saturation_epsilon=SATURATION_EPSILON,
        saturation_rounds=SATURATION_ROUNDS,
        scan_pair_budget=500,
        scan_time_budget=10.0,
    )


def test_o_an_unavailable_tree_leaves_the_document_expanding():
    """The saturation condition is met (one idle round, nothing found) and
    the scan STILL may not conclude, because the ceiling condition was never
    honestly evaluated — S8's two conditions have to hold together, and one
    of them was unanswerable."""
    new_document = make_document(
        document_id="doc-new", doc_number="01/2020/QĐ-UBND", space_id="space-a"
    )

    result = _scan(
        new_document,
        scope=UnavailableSpaceScanScope(reason="Backend did not answer"),
        documents=[new_document],
    )

    assert result.recommended_scan_state is RelationsScanState.EXPANDING


def test_o_an_exhausted_tree_is_still_allowed_to_stop():
    """The control case. Without it, the case above would also pass on a scan
    that could never reach `STOPPED` at all — and a document permanently
    saying *"chưa đối chiếu xong"* is the misconfiguration 07 Mục 3.2's hint
    for `scan_time_budget` sends an operator chasing in the wrong direction.
    """
    new_document = make_document(
        document_id="doc-new", doc_number="01/2020/QĐ-UBND", space_id="space-a"
    )

    result = _scan(
        new_document,
        scope=InMemorySpaceScanScope([InMemorySpace(space_id="space-a")]),
        documents=[new_document],
    )

    assert result.recommended_scan_state is RelationsScanState.STOPPED


def test_o_relations_found_before_the_tree_failed_are_kept():
    """A refusal to conclude is not a refusal to report.

    Round 1 compares against the document's own Space and really did read
    it, so whatever it found is a genuine proposal for a Manager (06 §5.3).
    Throwing those away would lose work that was correctly done, and would
    make an unreachable Backend cost more than the caveat it already costs.
    """
    cited = make_document(
        document_id="doc-cited", doc_number=DOC_NUMBER_110, space_id="space-a",
        issued_date=ISSUED_110,
    )
    citing = make_document(
        document_id="doc-citing",
        doc_number="30/2020/NĐ-CP",
        space_id="space-a",
        extracted_text=CITATION_110,
    )

    result = _scan(
        citing,
        scope=UnavailableSpaceScanScope(reason="Backend did not answer"),
        documents=[cited, citing],
    )

    assert result.relations, "relations found in round 1 were discarded"
    assert result.recommended_scan_state is RelationsScanState.EXPANDING


def test_o_the_stand_in_scope_refuses_rather_than_reporting_a_fixed_point():
    """⛔ The guard on the stand-in itself.

    `UnavailableSpaceScanScope` exists because a v1 install has no Backend
    topology client. The tempting shortcut — return `current_space_ids`
    unchanged "until the client lands" — is a fixed point, and a fixed point
    is how the scan learns it has finished. Every newly ingested document
    would be stamped `STOPPED` by a deployment that never looked at one
    other Space.
    """
    scope = UnavailableSpaceScanScope(reason="the topology client is not built")

    with pytest.raises(SpaceTopologyUnavailable) as excinfo:
        scope.expand(frozenset({"space-a"}))

    assert "the topology client is not built" in str(excinfo.value), (
        "the refusal must carry the reason an operator can act on"
    )
