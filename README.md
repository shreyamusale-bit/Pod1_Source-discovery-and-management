# CyArt Source Registry

Source Management module for the Dark Web Monitoring & Threat Intelligence
Platform prototype — FastAPI + SQLite, covering the Week 1/Week 2 task:
source data model, DISCOVERED → VALIDATED → AUTHORIZED → ACTIVE lifecycle,
authorization governance (PENDING/APPROVED/REJECTED/EXPIRED), health
monitoring, and a full CRUD API.

## Run it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs for interactive Swagger docs (auto-generated
from the Pydantic schemas — good for demoing to the team).

A `source_registry.db` SQLite file is created automatically on first run.

## How the two state machines fit together

Every source row carries two independent states:

- **`lifecycle_status`** — where the record is in its operational life:
  `discovered → validated → authorized → active`, with `quarantined` and
  `disabled` as side branches. Enforced transitions live in
  `models.ALLOWED_LIFECYCLE_TRANSITIONS`; anything not listed there is
  rejected with a 409.
- **`authorization_status`** — the governance gate: `pending → approved` or
  `rejected` (approved can later be re-set to `expired` by a scheduled job,
  not implemented here).

The two are cross-checked in one place: `crud.transition_lifecycle()` refuses
to move a source to `active` unless `authorization_status == approved`. That
line is the whole "discovery proposes, it never promotes" rule from the
governance model, expressed in code.

## API summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/sources/` | Submit a new candidate (always lands as `discovered` / `pending`) |
| GET | `/sources/` | List sources, filterable by lifecycle, authorization, transport, enabled |
| GET | `/sources/{id}` | Fetch one source |
| PUT | `/sources/{id}` | Edit editable fields (name, policy, trust_weight, enabled) |
| DELETE | `/sources/{id}` | Hard delete — testing only, see note below |
| PATCH | `/sources/{id}/authorize` | Approve or reject a pending source, with `decided_by` + `basis` recorded |
| PATCH | `/sources/{id}/lifecycle` | Move a source forward through its lifecycle |
| PATCH | `/sources/{id}/health` | Record a crawl attempt's outcome; 3 consecutive failures auto-quarantines |

### Revocation, not deletion

`DELETE /sources/{id}` is a hard delete meant for cleaning up bad test rows.
For a real source you want to pull, transition it to `disabled` via the
lifecycle endpoint instead — the record (and its link to any evidence already
collected) stays in place; only future crawling stops.

## Example flow

```bash
# 1. A discovery channel submits a candidate
curl -X POST localhost:8000/sources/ -H "Content-Type: application/json" -d '{
  "name": "Example Forum",
  "address": "http://example-forum.test",
  "source_type": "forum",
  "transport": "clearnet",
  "discovered_by": "analyst_1",
  "discovered_from": "link on source <id>"
}'

# 2. An analyst validates the address, then approves it
curl -X PATCH localhost:8000/sources/<id>/lifecycle -d '{"status":"validated"}'
curl -X PATCH localhost:8000/sources/<id>/authorize -d '{
  "decision": "approved",
  "decided_by": "lead_analyst",
  "basis": "Within programme scope, approved 2026-09-23"
}'

# 3. Move it the rest of the way to active — only possible now that it's approved
curl -X PATCH localhost:8000/sources/<id>/lifecycle -d '{"status":"authorized"}'
curl -X PATCH localhost:8000/sources/<id>/lifecycle -d '{"status":"active"}'

# 4. The crawler reports back after each fetch
curl -X PATCH localhost:8000/sources/<id>/health -d '{"success": true, "content_hash": "..."}'
```

## What's deliberately out of scope here

- No auth/RBAC on the API itself (the blueprint's JWT/RBAC layer sits in
  front of this module, not inside it)
- No hash-chained audit log — `authorized_by` / `authorized_at` / `basis`
  are stored on the row, but a tamper-evident log is a separate service
- No scheduler reading this table to actually dispatch crawls
- `expired` authorization status exists in the model but nothing sets it
  yet — that's a scheduled job checking `review_due` against `now()`

## Files

```
app/
  database.py    SQLite engine/session (swap the URL for Postgres later)
  models.py      Source table, enums, allowed lifecycle transitions
  validators.py  Address-format checks per transport (clearnet/onion/i2p)
  schemas.py     Pydantic request/response models
  crud.py        DB operations, separate from route handlers
  routers/
    sources.py   All /sources/* endpoints
  main.py        App entrypoint
```
