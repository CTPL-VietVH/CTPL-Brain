"""The HTTP surface AI Services exposes to Backend C.Brain (docs/10).

This package is the ENTRY LAYER, not a third service. Everything it does is
one of four things: authenticate the caller as Backend (docs/10 §1 T1), parse
and validate the wire shape (§3.2, §3.3), call one business function that
already exists elsewhere in this repo, and turn whatever comes back — value or
refusal — into the `{code, message}` envelope of §3.5.

⛔ **No business rule is implemented here, and none may be.** A permission
decision, a Space lookup, a deletion order — each already has an owner module,
and a second copy behind an HTTP handler is a copy that will drift. The route
functions in `ingestion_routes.py` are deliberately three to eight lines long:
anything longer is a rule that escaped its module.

──────────────────────────────────────────────────────────────────────────
Why `ingestion_routes.py` is a separate module from `app.py`
──────────────────────────────────────────────────────────────────────────

CLAUDE.md Mục 6: *"Hai service độc lập ở mức mã nguồn — chỉ gặp nhau qua module
Nhóm 1 và qua hai kho."* An API package that imported both services at the top
of one file would be a third meeting point, and the independence would be gone
without a single test going red.

So the split is: `app.py` and `meta.py` import `schema.*` only (Nhóm 1), and
each service gets its own router module which the composition root passes in.
A deployment that runs only Retrieval imports no Ingestion code, exactly as it
does today at the library level.

──────────────────────────────────────────────────────────────────────────
What is NOT here, on purpose
──────────────────────────────────────────────────────────────────────────

* **No composition root that builds live stores.** `build_app` takes the
  routers, the store-backed services, the readiness check and the idempotency
  store from its caller. Wiring them to PostgreSQL and Qdrant belongs with the
  write surface (08 T2.10), which has no owner yet — a module here that
  quietly `new`-ed in-memory stores would be a deployment that loses every
  document on restart and says nothing.
* **No background task runner.** `DELETE /v1/spaces/{space_id}` (docs/10 §4.0)
  is specified as `202` + *"chạy nền"*; this version runs the one unit of work
  synchronously inside the request. `space_deletion.delete_space` was written
  to be called repeatedly, so a runner can be put in front of it later without
  touching the route — see that route's docstring.
* **No answer/conversation endpoints (§6.1).** Retrieval v2 does not exist yet,
  so `GET /v1/meta` publishes a strict SUBSET of the `limits` §3.6 lists, and
  deliberately does not invent `max_recent_turns` or the `conversation_state`
  ceilings: a number published with no mechanism behind it is a number Backend
  would rely on.
"""
