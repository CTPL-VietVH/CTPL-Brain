"""What `GET /v1/meta` is allowed to say, and where each of its values comes
from (docs/10 §3.6).

Two kinds of thing live here, and neither is a value:

* `ApiLimits` — the limits Backend needs in order to build a VALID call. Every
  number in it is read from `config/*.yaml` through `schema.config`; there is
  no literal here for any of them (CLAUDE.md Mục 4 quy tắc 2 và 5).
* `ReadinessReport` — the answer to *"is this deployment serving right now"*,
  supplied by whoever builds the app.

──────────────────────────────────────────────────────────────────────────
Why `limits` is a strict SUBSET of docs/10 §3.6 today
──────────────────────────────────────────────────────────────────────────

§3.6 lists *"`max_recent_turns` (K), trần độ dài/số phần tử từng trường của
`conversation_state`, `conversation_state_schema_version`, cỡ file tối đa"*.
Every one of those belongs to a surface that does not exist yet — the answer
endpoint (§6.1) and the upload endpoint (§4.1). Publishing a K that no code
enforces would be worse than publishing nothing: Backend is told to call this
endpoint exactly so that it *"không phải đoán K"*, and a number nobody
enforces is a guess with a `200 OK` in front of it.

So `limits` carries only `accepted_formats` for now — the one request-shaping
limit that has a real config key behind it, and the sibling of §3.6's *"cỡ
file tối đa"*: it tells Backend which uploads are worth sending rather than
letting them come back `422 UNSUPPORTED_FORMAT`.

⚠️ It is also the boundary of what belongs in this endpoint at all. docs/10 §2
is explicit that *"Cấu hình mô hình và tham số"* does not travel over the API:
*"**Không qua API.** Chỉ đổi bằng file cấu hình. Cố ý không đưa lên giao diện
quản trị."* So `document_cap`, `inheritance_decay` and the rest of 07 Mục 3.2
are NOT publishable here, even though they are numbers this process has
loaded. The test for this endpoint checks that too — every number Backend can
see must be one it needs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from schema.config import IngestionConfig

__all__ = [
    "CONTRACT_CONFIG_FILENAME",
    "INGESTION_CONFIG_FILENAME",
    "RETRIEVAL_CONFIG_FILENAME",
    "ApiLimits",
    "ReadinessCheck",
    "ReadinessReport",
    "api_limits_from_ingestion_config",
]


#: The three config files of CLAUDE.md Mục 4, by name. The DIRECTORY they sit
#: in is never assumed — `app.build_app` takes it as a required argument, for
#: the reason `schema.config` gives for having no default path: where `config/`
#: lives is a deployment fact of each install (R6), not a constant of a shared
#: module.
CONTRACT_CONFIG_FILENAME: Final = "contract.yaml"
INGESTION_CONFIG_FILENAME: Final = "ingestion.yaml"
RETRIEVAL_CONFIG_FILENAME: Final = "retrieval.yaml"


@dataclass(frozen=True, slots=True, kw_only=True)
class ApiLimits:
    """The `limits` object of `GET /v1/meta`, built from loaded config.

    `frozen=True` for the same reason `ContractConfig` is: the values were
    checked when the process started, and a limit that can be edited at
    runtime is a limit Backend was told about and is no longer true.
    """

    accepted_formats: tuple[str, ...]

    def as_payload(self) -> dict[str, Any]:
        """The JSON shape. A tuple would serialise fine; a list is what the
        wire contract of docs/10 §3.1 (plain JSON) actually describes."""
        return {"accepted_formats": list(self.accepted_formats)}


def api_limits_from_ingestion_config(config: IngestionConfig) -> ApiLimits:
    """Read the publishable limits off the Ingestion config.

    Deliberately takes the CONFIG OBJECT, not a path: loading is
    `schema.config`'s job and happens once per process, and a second reader of
    the same file is a second place for the file to be misread.
    """
    return ApiLimits(accepted_formats=config.accepted_formats)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadinessReport:
    """docs/10 §3.6 — `ready` and `not_ready_reason`.

    `not_ready_reason` is free text for a human operator: §3.6 gives examples
    (*"lệch con dấu kho vector, thiếu khoá cấu hình"*) rather than an
    enumeration, and Backend's use for it is to show it, not to branch on it.
    A branchable code would be `SERVICE_MISCONFIGURED` (§3.5), which is what
    the calls that actually need the stores already return.

    Invariant: `ready` and `not_ready_reason` say the same thing. Not ready
    with no reason is an outage nobody can diagnose; ready with a reason is a
    warning nobody will read.
    """

    ready: bool
    not_ready_reason: str | None

    def __post_init__(self) -> None:
        if self.ready and self.not_ready_reason is not None:
            raise ValueError(
                "A ready service must not carry a not_ready_reason: "
                f"{self.not_ready_reason!r}"
            )
        if not self.ready and not self.not_ready_reason:
            raise ValueError(
                "A service reported as not ready must say why — docs/10 §3.6 "
                "exists so Backend learns the reason before a user hits a 503."
            )


#: Supplied by whoever builds the app. There is no default implementation, and
#: in particular no "always ready" one: the real check is the store-stamp
#: comparison of 07 Mục 3.1 (`assert_contract_matches_store_stamp`) against a
#: LIVE store, and a stand-in that answers `True` without asking anything would
#: be a lie with a green light on it.
ReadinessCheck = Callable[[], ReadinessReport]
