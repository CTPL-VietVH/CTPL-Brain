"""T2.7 (h) — the runner cannot reach GĐ6 or GĐ7, proven by reading its
import list rather than by watching it behave.

This is the "đếm lượt gọi" shape CLAUDE.md Mục 7 asks for on R1: assert the
system CANNOT do the forbidden thing, not that it happened not to. A future
edit that adds `from ingestion.vectorization import ...` to the runner turns
this test red before the call is even written.
"""

from __future__ import annotations

import ast
import pathlib

FORBIDDEN_MODULES = {
    "ingestion.vectorization",  # GĐ6
    "ingestion.relations",  # GĐ7
    "ingestion.relations_scan",  # GĐ7
}

RUNNER_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "packages"
    / "ingestion"
    / "pre_approval_runner.py"
)


def _imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_runner_does_not_import_stage6_or_stage7() -> None:
    imported = _imported_modules(RUNNER_PATH)

    assert imported & FORBIDDEN_MODULES == set(), (
        "the pre-approval chain must stop before GĐ6 and GĐ7 (06 Mục 5.2 GĐ1); "
        f"it imports {sorted(imported & FORBIDDEN_MODULES)}"
    )
    # Sanity: the check is looking at the right file — the stages that MUST
    # run are all there.
    assert {
        "ingestion.extraction",
        "ingestion.chunking",
        "ingestion.labeling",
        "ingestion.intake",
    } <= imported


def test_runner_does_not_register_into_the_shared_profile_store() -> None:
    """`receive_and_validate` writes to the fingerprint index; the
    pre-approval path must use the read-only `decide_intake` instead."""
    source = RUNNER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    attribute_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "receive_and_validate" not in called_names
    assert "decide_intake" in called_names
    assert "register" not in attribute_calls, (
        "registering into the fingerprint index is a write into the official "
        "profile store — 08 T2.7 forbids it before approval"
    )
