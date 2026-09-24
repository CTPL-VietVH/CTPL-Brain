"""The background worker — ⭐ **exactly ONE thread, and that is a design
decision, not a setting** (PO chốt 24/9/2026, Phương án A).

docs/10 §4.0 and §4.1 both answer `202` and promise the work happens after
the call returns. This module is the thing that runs it: a FIFO of jobs and
one thread pulling them one at a time.

──────────────────────────────────────────────────────────────────────────
Why one worker, and what the number buys
──────────────────────────────────────────────────────────────────────────

The single worker is what makes `IngestionRecordStore.recover_orphans`
correct without a timeout, a heartbeat or a lease: if a row says `RUNNING`
while this process is starting up, the process that claimed it is the one
that just died. Two workers — in one process or two replicas — break that
sentence, and the failure is silent (a live job handed back to the queue and
ingested twice). So the number is not a knob:

⛔ **It is not in `config/`, and it must not become a config key** until a
durable claim exists (`API-xoa-space-chay-nen-va-kho-ben`). A number in a
YAML file invites an operator to raise it, and nothing would complain.

──────────────────────────────────────────────────────────────────────────
No poll interval, on purpose
──────────────────────────────────────────────────────────────────────────

The loop blocks on an `Event` and is woken by `submit`. There is no sleep
and therefore no interval to configure — CLAUDE.md Mục 4 quy tắc 5 (*"Không
con số cứng trong mã"*) is satisfied by not having the number at all, which
is better than having it in a config file nobody can tune meaningfully.

This works because v1 is ONE process: the only writer to the queue is the
same process that reads it. A second process would need PostgreSQL
`LISTEN/NOTIFY` or a poll — and would also need the durable claim above, so
the two limits fall away together.

──────────────────────────────────────────────────────────────────────────
A failing job must not take the thread with it
──────────────────────────────────────────────────────────────────────────

`run_pending` logs and continues. One unhandled exception killing the loop
would stop every LATER job too — including Space deletions — and the only
symptom would be work that never finishes. `IngestionPipeline` already ends
every job as a row; this is the second net, for the jobs that are not
ingestions.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable

__all__ = ["BackgroundWorker", "Job"]

logger = logging.getLogger(__name__)

#: A unit of background work. Takes nothing and returns nothing: everything a
#: job needs is captured when it is submitted, and everything it produces is
#: written to a store — there is no caller left to hand a value back to.
Job = Callable[[], None]


class BackgroundWorker:
    """A FIFO of jobs and one thread, or no thread at all.

    Two ways to run it, and tests use the second:

    * `start()` / `stop()` — the deployment's way. One daemon thread drains
      the queue and then blocks until something is submitted.
    * `run_pending()` — drain synchronously, in the calling thread. This is
      what every contract test uses, so a case asserts on a finished world
      instead of on a sleep.

    Both call the same `run_pending`, so the tests exercise the real drain.
    """

    def __init__(self) -> None:
        self._jobs: deque[Job] = deque()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    # -- submitting ------------------------------------------------------- #

    def submit(self, job: Job) -> None:
        """Queue a job and wake the thread if one is running."""
        with self._lock:
            self._jobs.append(job)
        self._wake.set()

    def pending(self) -> int:
        with self._lock:
            return len(self._jobs)

    # -- running ---------------------------------------------------------- #

    def run_pending(self) -> int:
        """Run every job queued right now. Returns how many ran.

        Jobs submitted BY a job are picked up by the same drain — the loop
        re-reads the queue — so a job that enqueues follow-up work does not
        have to wait for the next wake-up.
        """
        ran = 0
        while True:
            with self._lock:
                if not self._jobs:
                    return ran
                job = self._jobs.popleft()
            ran += 1
            try:
                job()
            except Exception:
                # The thread survives. See the module docstring: a dead loop
                # stops every later job and says nothing.
                logger.exception("Background job failed")

    def start(self) -> None:
        """Start the one worker thread. Calling it twice is refused.

        Refused rather than ignored: a second `start` means somebody believes
        they are adding capacity, and they are instead breaking the
        single-worker invariant `recover_orphans` rests on.
        """
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError(
                "the background worker is already running. v1 runs EXACTLY ONE "
                "worker — see this module's docstring for what a second one "
                "silently breaks."
            )
        self._stopping.clear()
        self._thread = threading.Thread(
            target=self._loop, name="cbrain-ingestion-worker", daemon=True
        )
        self._thread.start()

    def stop(self, *, timeout: float | None = None) -> None:
        """Ask the thread to finish the current drain and exit.

        `timeout` is a JOIN timeout for the shutdown path only — it is not a
        tuning parameter of the service and has no home in `config/`. The
        default `None` waits for the current job, which is what an orderly
        shutdown wants: a job cut in the middle costs a requeue at best and a
        lost staged file at worst.
        """
        self._stopping.set()
        self._wake.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
            self._thread = None

    def _loop(self) -> None:
        while True:
            # Cleared BEFORE draining, so a job submitted during the drain
            # leaves the event set and the next `wait` returns immediately.
            # Clearing after would be the classic lost wake-up.
            self._wake.clear()
            self.run_pending()
            if self._stopping.is_set():
                return
            self._wake.wait()
