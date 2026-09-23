"""Minimal fault injection — cut a process at a chosen step and prove the
re-run converges. Shared test infrastructure, not tied to T2.8.

Kept out of `packages/` on purpose: no production module should carry a hook
whose only job is to fail. The only thing this touches is the boundary a
module already has.

──────────────────────────────────────────────────────────────────────────
What "cut the process at one step" means here
──────────────────────────────────────────────────────────────────────────

A step is **one call to a port method that changes durable state.** A module
like `ingestion.deletion` talks to its stores through Protocols, so every
durable effect it can possibly have is one such call — which makes the set of
cut points finite, nameable, and exactly as large as the set of steps.

Two cut positions per step, which is the whole space:

* `before` — the process dies with the effect NOT applied. Re-running must
  do the step normally.
* `after`  — the effect IS applied, the process dies before the next step
  starts. Re-running must find the step already done and move on.

"During" a step is not a third position: a step is atomic or it is not, and
when it is not — a PostgreSQL transaction that rolls back, a delete-by-filter
that matched nothing — what is observable afterwards is one of the two above.
Where atomicity is the claim under test, wrap the call and crash `after`, then
assert the store shows none of it.

──────────────────────────────────────────────────────────────────────────
Use
──────────────────────────────────────────────────────────────────────────

    store = crash_after(real_store, "delete_document_and_relations")
    with pytest.raises(InjectedCrash):
        purge_document_permanently("doc-1", ..., profile_store=store, ...)
    store.assert_fired()          # ← never skip this

`assert_fired()` is the guard against the failure mode that makes a fault
test worthless: the method was renamed, or never reached, the crash never
happened, the test still passed because nothing asserted it did.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

__all__ = [
    "CallRecorder",
    "CrashPoint",
    "FaultInjector",
    "InjectedCrash",
    "crash_after",
    "crash_before",
]


class InjectedCrash(RuntimeError):
    """The simulated process death. Deliberately not an exception any module
    under test raises itself, so a test cannot mistake a real failure for the
    injected one."""


@dataclass(frozen=True, slots=True)
class CrashPoint:
    """Which call to cut, and on which side of it.

    `on_call` counts calls TO THAT METHOD on this wrapper, from 1. It matters
    when a step is reached more than once in a run — the second round of a
    loop, a retry inside the module — where crashing on the first call would
    be testing a different step than the one intended.
    """

    method: str
    when: Literal["before", "after"]
    on_call: int = 1


class FaultInjector:
    """A transparent proxy over any object, raising `InjectedCrash` at one
    point. Everything else passes straight through, including attributes that
    are not callable.

    Duck-typed on purpose: the wrapped object keeps satisfying whatever
    Protocol it satisfied, because Protocols are structural and this forwards
    every attribute.
    """

    def __init__(self, target: Any, crash: CrashPoint) -> None:
        self._target = target
        self._crash = crash
        self.fired = False
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._target, name)
        if name != self._crash.method or not callable(attribute):
            return attribute

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(name)
            nth = self.calls.count(name)
            hit = nth == self._crash.on_call
            if hit and self._crash.when == "before":
                self.fired = True
                raise InjectedCrash(
                    f"cut BEFORE {name}() call #{nth} — the step must not have run"
                )
            result = attribute(*args, **kwargs)
            if hit and self._crash.when == "after":
                self.fired = True
                raise InjectedCrash(
                    f"cut AFTER {name}() call #{nth} — the step ran, the next one must not"
                )
            return result

        return wrapped

    def assert_fired(self) -> None:
        """Fail loudly when the injected crash never happened.

        Without this, a fault test that never reaches its cut point passes
        while proving nothing at all.
        """
        if not self.fired:
            raise AssertionError(
                f"no crash was injected: {self._crash.when} "
                f"{self._crash.method}() call #{self._crash.on_call} was never reached. "
                f"Calls seen on this wrapper: {self.calls or 'none'}"
            )

    def __repr__(self) -> str:
        return (
            f"FaultInjector({self._target!r}, {self._crash.when} "
            f"{self._crash.method}#{self._crash.on_call}, fired={self.fired})"
        )


def crash_before(target: Any, method: str, *, on_call: int = 1) -> FaultInjector:
    """Wrap `target` so `method` dies without running."""
    return FaultInjector(target, CrashPoint(method=method, when="before", on_call=on_call))


def crash_after(target: Any, method: str, *, on_call: int = 1) -> FaultInjector:
    """Wrap `target` so `method` runs, then the process dies."""
    return FaultInjector(target, CrashPoint(method=method, when="after", on_call=on_call))


class CallRecorder:
    """A transparent proxy that appends `"<label>.<method>"` to a shared list
    on every call, and changes nothing else.

    The companion to `FaultInjector`: one proves what survives a cut, this
    one proves the steps happened in the order the design fixed. Give several
    recorders the SAME list and the list is the interleaved order across
    ports — which is the only place an ordering constraint like S6 can be
    observed, since no single port sees it.
    """

    def __init__(self, target: Any, *, label: str, sink: list[str]) -> None:
        self._target = target
        self._label = label
        self._sink = sink

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._target, name)
        if not callable(attribute):
            return attribute

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            self._sink.append(f"{self._label}.{name}")
            return attribute(*args, **kwargs)

        return wrapped
