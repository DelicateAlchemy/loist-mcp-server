# Clearance Model Review & Per-Stakeholder Clearance Task Proposal (LOI-39)

**Date:** July 7, 2026 · **Status:** Discovery — no implementation, no migration
**Linear:** [LOI-39](https://linear.app/loist/issue/LOI-39)
**Follows:** LOI-31…36 (publishing MVP), LOI-44 (publishing routes under `/api/v1`)

Loist is, at its core, a music licensing/clearance system. The song publishing
MVP gave us the *nouns* of that domain — parties, works, writers, publishers,
splits — as static data records. This document reviews what exists, analyses
what "clearing a track" actually means, and proposes the *verbs*: a
per-stakeholder clearance task model with a lifecycle. It ends with the
product questions that must be answered before anything is built.

---

## 1. Current model review

### 1.1 What exists

Migration `database/migrations/010_song_publishing_schema.sql` created the
publishing data model:

| Table | Purpose | Key columns |
|---|---|---|
| `parties` | People & orgs (writers, publishers, artists, labels) | `party_type`, `name`, `ipi_cae_number`, `isni`, `society_affiliation`, `email`, `notes` |
| `works` | Compositions, distinct from recordings | `title`, `iswc`, `status`, `notes` |
| `work_writers` | Writer ↔ work with split | `split_percentage` (nullable, 0–200), `split_status`, `notes` |
| `work_publishers` | Publisher ↔ work with split | same shape as `work_writers` |
| `recording_artists` | Artist credit on a recording | `audio_track_id`, `party_id`, `is_primary`, `notes` |
| `work_alternative_titles` | Alt/translated titles | `title`, `title_type`, `language` |
| `audio_tracks.work_id` | Every recording belongs to a work (NOT NULL) | FK `ON DELETE RESTRICT` |

Plus two helper views: `v_work_split_summary` (split totals per work) and
`v_party_involvement` (counts per party).

The surface on top of this:

- **8 MCP tools** registered in `src/server.py`: `create_party`,
  `search_parties`, `get_party`, `get_work`, `search_works`,
  `update_work_writers`, `update_work_publishers`, `link_artist_to_recording`.
- **8 REST endpoints** under `/api/v1` in `src/http_api.py` (post-LOI-44):
  `POST /api/v1/parties`, `GET /api/v1/parties/search`,
  `GET /api/v1/parties/{partyId}`, `GET /api/v1/works/search`,
  `GET /api/v1/works/{workId}`, `PUT /api/v1/works/{workId}/writers`,
  `PUT /api/v1/works/{workId}/publishers`,
  `POST /api/v1/tracks/{audioId}/artists`.
- Layers per convention: `src/services/party_service.py` /
  `src/services/work_service.py` → `src/repositories/party_repository.py` /
  `src/repositories/work_repository.py` → raw SQL in
  `database/operations.py`. Schemas in `src/schemas/party.py`,
  `src/schemas/work.py`, `src/schemas/publishing.py`.

### 1.2 What it does well — keep honoring this

The design principles in the migration header and
`docs/songs-schema-design-philosophy.md` are deliberate and correct for
this problem space:

- **WIP-friendly splits.** `split_percentage` is nullable, capped at 200 (not
  100), with no sum constraint. Incomplete, over-claimed, and disputed states
  are *valid data*, surfaced as warnings via
  `calculate_split_warnings()` (`database/operations.py`), never as blockers.
  Clearance work is even messier than split negotiation — any clearance model
  must inherit this "warnings, not blockers" stance.
- **Recording ≠ Composition.** `work_writers`/`work_publishers` hang off
  `works`; `recording_artists` hangs off `audio_tracks`. This is exactly the
  split the licensing industry uses (composition side vs. master side), so the
  clearance model can attach to it cleanly rather than fight it.
- **Audio-first workflow.** Every track gets a stub work automatically
  (`save_audio_metadata()` in the audio pipeline). A clearance request can
  therefore always assume a work exists for any track.
- **Per-relationship status + notes.** `split_status`
  (`proposed`/`confirmed`/`disputed`/`unknown`) and free-text `notes` on each
  junction row already acknowledge that each stakeholder relationship has its
  own state. That is the seed of the idea this proposal grows.

### 1.3 Where it stops short of clearance workflow

The model describes *who owns what*. It says nothing about *whether a given
use of a track has been permitted by each of those owners*. Concrete gaps:

1. **No per-stakeholder clearance status.** `split_status = 'confirmed'`
   means "we agree this writer owns 25%". It does not mean "this writer's
   publisher has granted a sync license for the Nike ad". There is no field
   anywhere that can hold the second statement.
2. **No use-case / project concept.** Clearance is always *for something* — a
   film, an ad, a game, a playlist placement. There is no entity representing
   the thing being cleared for, so there is nowhere to hang "cleared" even if
   we had a status. `works.status` (`draft` → `splits_pending` →
   `splits_disputed` → `ready` → `registered`) is a *registration* lifecycle,
   global to the work — it cannot express "cleared for project A, rejected
   for project B".
3. **No negotiation history.** The `notes TEXT` columns on `work_writers` /
   `work_publishers` / `parties` are single mutable blobs. Real negotiations
   have a sequence: quote sent → counter → terms agreed → license signed —
   with dates, amounts, and expirations. None of that is representable.
4. **No master-side rights holder.** `recording_artists` records *credit*
   (who performed), not *ownership* (who controls the master). The only
   master-ownership signal in the system is `audio_tracks.record_label` — a
   raw ingested string, explicitly documented as reference data, not a party
   link. The design philosophy doc lists "Master rights / recording
   ownership" as a deliberate MVP exclusion ("Separate `recording_rights`
   table if needed"). Clearance needs it: you cannot clear a track without
   clearing the master.
5. **No rollup.** Even manually, there is no way to ask "is this track fully
   cleared for use X?" — the question is not representable, so
   `v_work_split_summary` has no clearance sibling.
6. **No expiry/terms.** Sync quotes expire; licenses have terms, territories,
   and durations. Nothing in the schema carries a date besides
   `created_at`/`updated_at`.

None of these are flaws in the MVP — they were correctly out of scope. But
they define exactly the shape of the missing layer.

---

## 2. Domain analysis: what "clearing a track" actually means

### 2.1 Two sides, always

Sync licensing (film/TV/ads/games — the paradigm case) requires clearing
**both** halves of a track, from different people, in parallel:

| Side | What's being licensed | Who grants it | Where Loist models the owners |
|---|---|---|---|
| **Composition** (publishing) | The underlying song — melody, lyrics | Each writer's share, usually controlled by their publisher; self-administered writers grant directly | `work_writers` + `work_publishers` on the `works` row |
| **Master** (recording) | The specific recording | The label or whoever owns the master (often the artist for indie tracks) | **Nowhere structured** — `audio_tracks.record_label` string only |

A quote for "the song" is meaningless until both sides say yes, usually at
matching fees (the industry's MFN — most favored nations — convention).

### 2.2 One uncleared share blocks the whole use

Composition rights are fractional. If a work has three writers with
60/30/10 splits controlled by two publishers, *each publisher* must clear
its controlled share. A 10% holdout blocks the entire use — there is no
"90% cleared, good enough". This is why clearance must be tracked
**per stakeholder per share**, not per work: the unit of negotiation is
"this rights-holder's share of this work (or master) for this use".

### 2.3 What varies per stakeholder

Each clearance thread has its own:

- **Contact** — the publisher's sync department, a manager, the writer
  directly. Not necessarily `parties.email`.
- **Status** — one publisher may have cleared in a day while another is
  three weeks into negotiation.
- **Terms** — quoted fee, term (duration), territory, media, exclusivity.
  Fees differ per stakeholder even under MFN (they're proportional to share).
- **Paper trail** — emails, quotes, counters, signed licenses.
- **Expiry** — quotes typically lapse if not accepted within a window.

### 2.4 Lifecycle of a clearance thread

Observed in practice, a single stakeholder thread moves through:

```
draft ──► requested ──► negotiating ──► cleared
  │            │              │
  │            │              ├──► rejected     (holder says no / unaffordable)
  │            │              └──► expired      (quote lapsed, deal died)
  └────────────┴──► withdrawn                   (we abandoned the use)
```

`draft` = identified but not yet contacted; `requested` = ask sent;
`negotiating` = any back-and-forth (quotes, counters). Terminal-ish states
can reopen (a rejected holder changes their mind) — like `works.status`, this
should be informational, not a hard state machine (matches the existing "no
status state machine enforcement" decision, Q8 in
`docs/songs-database-planning.md`).

### 2.5 What makes a track "fully cleared" for a use

Derived, never stored as ground truth:

1. **Composition side:** every controlled share of the work is covered by a
   `cleared` thread. (With WIP splits this is fuzzy — if splits don't sum to
   100% or a writer has no publisher attached, the rollup should *warn*
   "composition side may be incompletely mapped", in the same spirit as
   `calculate_split_warnings()`.)
2. **Master side:** the recording's rights-holder(s) have `cleared` threads.
3. Any `rejected`/`expired` thread ⇒ the use is **blocked** regardless of the
   others.

Rollup states per (track, use case): `not_started` / `in_progress` /
`blocked` / `cleared` — computed from the constituent threads, exactly as
`warnings` is computed in `get_work` today.

---

## 3. Proposed direction: per-stakeholder clearance tasks

Everything below is **illustrative sketching, not a migration**. It requires
**zero schema changes** to `parties`, `works`, `work_writers`,
`work_publishers`, `recording_artists`, or `audio_tracks` — the new tables
only reference them.

### 3.1 New concept 1 — the use case (probably a prerequisite)

Clearance is keyed by *what the track is being cleared for*. Without this
entity there is nothing to attach a status to, so **yes, a use-case entity
almost certainly needs to exist first**:

```
use_cases                              -- working name; "projects" also fits
  id            UUID PK
  name          VARCHAR      -- "Nike 'Run Fearless' Q4 spot"
  use_type      VARCHAR      -- film | tv | advert | game | trailer | playlist | other
  description   TEXT
  status        VARCHAR      -- active | closed | abandoned (informational)
  notes         TEXT
  created_at / updated_at
```

Deliberately thin — no client/brand/budget modeling until product discovery
says otherwise.

### 3.2 New concept 2 — the clearance task

One row per (use case, thing-being-cleared, rights-holder, share):

```
clearance_tasks
  id                 UUID PK
  use_case_id        UUID NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE

  -- what is being cleared (exactly one side set; CHECK enforces XOR)
  work_id            UUID NULL REFERENCES works(id)         -- composition side
  audio_track_id     UUID NULL REFERENCES audio_tracks(id)  -- master side

  -- who must grant it
  party_id           UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT

  -- which share (optional pointer into the existing split rows)
  work_writer_id     UUID NULL REFERENCES work_writers(id)
  work_publisher_id  UUID NULL REFERENCES work_publishers(id)
  share_percentage   DECIMAL(5,2) NULL   -- snapshot/override; WIP-friendly, nullable

  -- lifecycle (informational, per §2.4; CHECK constraint, no state machine)
  status             VARCHAR NOT NULL DEFAULT 'draft'
                     -- draft | requested | negotiating | cleared
                     -- | rejected | expired | withdrawn

  -- negotiation essentials (all nullable — WIP-friendly)
  contact_party_id   UUID NULL REFERENCES parties(id)  -- who we're actually talking to
  quoted_fee         DECIMAL(12,2) NULL
  currency           VARCHAR(3) NULL
  terms              TEXT NULL           -- territory/term/media, freeform for v1
  expires_at         TIMESTAMPTZ NULL    -- quote/clearance expiry
  notes              TEXT
  created_at / updated_at

  UNIQUE(use_case_id, party_id, work_id, audio_track_id)   -- one thread per stakeholder per side per use
```

Design notes, mirroring migration 010's philosophy:

- **The `work_id` XOR `audio_track_id` split** keeps Recording ≠ Composition
  intact: a composition-side task points at the work; a master-side task
  points at the recording.
- **`work_writer_id`/`work_publisher_id` are soft pointers** to the share
  being cleared, plus a `share_percentage` snapshot, because splits are
  batch-*replaced* today (`replace_work_writers()` deletes and re-inserts
  rows in `database/operations.py`). The snapshot keeps the thread meaningful
  even if the split rows are replaced mid-negotiation; the FK (nullable,
  `ON DELETE SET NULL`) reconnects it when stable. This is the one real
  friction point with the existing batch-replace pattern and deserves a
  design pass at implementation time.
- **No sum/coverage constraints.** A use case with tasks for only half the
  stakeholders is valid; the rollup warns.

### 3.3 New concept 3 — history (optional at v1)

```
clearance_events
  id                 UUID PK
  clearance_task_id  UUID NOT NULL REFERENCES clearance_tasks(id) ON DELETE CASCADE
  event_type         VARCHAR   -- status_change | quote | counter | note | contact_logged
  old_status / new_status VARCHAR NULL
  detail             TEXT      -- freeform; amount/terms in text for v1
  created_at         TIMESTAMPTZ
```

Append-only. Even if v1 ships without a UI for it, writing an event on every
status change is cheap and preserves the negotiation timeline that a mutable
`notes` blob loses.

### 3.4 The master-side attachment question

`recording_artists` is the wrong anchor — it models *credit*, and the design
philosophy doc explicitly reserved master ownership for a separate concept.
Two options:

- **(a) Minimal (recommended for v1):** no new ownership table. A master-side
  `clearance_task` simply names the `party_id` the user says controls the
  master (a label party, or the artist). The task itself *is* the assertion
  of ownership — consistent with "users intentionally create links".
- **(b) Structured:** add the deferred `recording_rights` table
  (`audio_track_id`, `party_id`, `rights_type`, `split_percentage`,
  `split_status`, `notes` — same WIP shape as `work_writers`), and have
  master tasks reference it like composition tasks reference splits.

Option (a) gets clearance shipping without a second modeling debate;
(b) becomes worthwhile the moment two parties co-own a master or ownership
needs to be reused across use cases. The task table above supports both.

### 3.5 Derived rollup

A view (or service-layer calculation, like `calculate_warnings()` in
`src/repositories/work_repository.py`) per (use_case, audio_track):

```
v_use_case_track_clearance
  use_case_id, audio_track_id,
  composition_tasks_total / cleared / rejected,
  master_tasks_total / cleared / rejected,
  rollup_status,     -- not_started | in_progress | blocked | cleared
  warnings[]         -- "no master-side task", "writer splits sum to 80%",
                     -- "2 shares have no clearance task", "1 quote expires in 5 days"
```

`cleared` only when both sides have ≥1 task and all tasks are `cleared`;
`blocked` if any task is `rejected`/`expired`; warnings carry the fuzziness
instead of pretending precision.

### 3.6 How it ties into the existing model (no changes to it)

```
use_cases ──< clearance_tasks >── parties            (existing, untouched)
                   │  ├── work_id ──────► works       (existing, untouched)
                   │  ├── work_writer_id ► work_writers    (soft ptr)
                   │  ├── work_publisher_id ► work_publishers (soft ptr)
                   │  └── audio_track_id ► audio_tracks (existing, untouched)
clearance_events ──┘
```

When built, this would be migration `014_clearance_schema.sql` (013 is
uploads), with `clearance_repository.py` / `clearance_service.py` /
`src/schemas/clearance.py` following the patterns in
`src/repositories/upload_repository.py` and `src/services/upload_service.py`
(the newest exemplars of the repo conventions).

---

## 4. Workflow & API sketch

Typical flow: create use case → attach tracks → generate stakeholder task
list (one per writer/publisher share + a master-side task) → work the
threads → watch the rollup.

Mapped to the `/api/v1` conventions in `docs/frontend-api-guide.md`
(success/error envelope, `limit`/`offset` pagination, `RESOURCE_NOT_FOUND`,
batch-replace `PUT` where lists are replaced wholesale):

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/use-cases` | Create a use case (201, entity in body) |
| `GET /api/v1/use-cases/search?q=&limit=&offset=` | Search, standard pagination |
| `GET /api/v1/use-cases/{useCaseId}` | Detail incl. tracks + per-track rollup + warnings (the `get_work`-with-warnings pattern) |
| `POST /api/v1/use-cases/{useCaseId}/tracks/{audioId}/tasks` | **Generate** tasks for a track from current splits (server derives the stakeholder list; returns created tasks; idempotent per UNIQUE constraint) |
| `POST /api/v1/clearance-tasks` | Manually add a task (e.g. master-side holder not in splits) |
| `PATCH /api/v1/clearance-tasks/{taskId}` | Update status/quote/terms/notes; server appends a `clearance_event` |
| `GET /api/v1/clearance-tasks?use_case_id=&party_id=&status=` | The worklist view — "everything I'm waiting on", "all threads with Publisher X" |
| `GET /api/v1/clearance-tasks/{taskId}/events` | Negotiation history (if events ship in v1) |

MCP mirrors (same services, per the two-interfaces-one-service-layer
architecture): `create_use_case`, `generate_clearance_tasks`,
`update_clearance_task`, `get_use_case_clearance` — 4 tools, matching the
consolidation instinct that cut 16 publishing tools to 8.

Notable choice: `PATCH` for task updates rather than the publishing batch
`PUT`-replace, because tasks are long-lived threads with history — replacing
them wholesale would destroy the negotiation record.

---

## 5. MVP scoping options

| | Cut A — status board | Cut B — negotiation tracker | Cut C — full threads |
|---|---|---|---|
| **Ships** | `use_cases` + `clearance_tasks` (status + notes only; no fee/terms/expiry columns), task generation from splits, manual status updates, rollup in use-case detail | Cut A + `quoted_fee`/`terms`/`expires_at` + `clearance_events` history + expiry warnings + party-centric worklist queries | Cut B + `recording_rights` table (master ownership, §3.4b), structured terms (territory/term/media columns), reminders/notifications, per-task contact log |
| **Answers** | "Where does clearance stand for this use?" | …plus "what did we quote, when does it lapse, what happened?" | …plus "who owns this master?" and proactive chasing |
| **Doesn't answer** | Money, history, expiry | Structured master ownership, notifications | External stakeholder access (that's a product question, §6) |
| **New tables** | 2 | 3 | 4–5 |
| **Rough effort** | ~1 sprint: migration + repo/service/schemas + 6 endpoints/4 tools + rollup + tests (comparable to the LOI-45 upload flow) | ~1.5–2 sprints | 3+ sprints, and blocked on product answers |
| **Risk** | Might be "a spreadsheet with extra steps" if statuses alone aren't the pain point | Terms-as-freeform-text may need remodeling later | Building ahead of discovery — the LOI-5 trap |

**Recommendation:** Cut A is the honest MVP *if* the primary user pain is
"I lose track of who has and hasn't cleared". Cut B is the better default if
the pain includes quotes and lapsing offers — the events table is much
cheaper to include from day one than to retrofit. Cut C should not start
before §6 is answered.

---

## 6. Open product questions (need answers before building)

Like LOI-5 (multi-tenancy), these are product decisions, not engineering
ones, and **no discovery has been done yet**. Building any cut beyond A
without answers risks modeling the wrong workflow.

1. **Who uses the clearance workflow?** Internal team only (Gareth/Loist
   staff tracking their own outreach)? Or do external rights-holders ever see
   or act on their thread (approve/reject/counter in-product)? External
   access changes everything: auth (currently `AUTH_ENABLED=false`),
   multi-tenancy (LOI-5), notifications, and legal weight of an in-app
   "cleared" click. The sketch above assumes **internal-only**.
2. **System of record, or tracker alongside email?** Negotiations happen in
   email/phone. Is Loist the authoritative record (licenses attached,
   statuses contractually meaningful) or a lightweight status board mirroring
   reality? This decides whether `clearance_events` needs document
   attachments and how much rigor `cleared` implies.
3. **What is a "use case" really?** One ad spot? A client project containing
   many placements? A pitch (briefs with candidate tracks, most never
   cleared)? If Loist's core loop is *pitching* playlists of candidates, the
   entity might be a brief with per-track shortlist status *upstream* of
   clearance — different shape, worth deciding before naming the table.
4. **Does money belong in v1?** Tracking quoted fees implies currency,
   revisions, maybe approval flows. Is fee tracking essential, or is `notes`
   enough until it hurts?
5. **How is the master side actually encountered?** Are tracks in the library
   mostly self-owned/indie (master holder = the artist party, trivially
   known) or label-controlled (unknown parties, research required)? This
   decides between §3.4(a) and (b).
6. **What triggers clearance?** Manual ("start clearing this track for this
   use") or automatic when a track is added to some entity (playlist →
   use case)? Touches the playlists surface merged in LOI-43.
7. **MFN and cross-thread coupling** — do quotes need to reference each other
   ("match publisher A's rate"), or is that a human concern outside the tool?

### Suggested next step

Answer questions 1–3 (a working session, not a build), then scope Cut A or B
as a normal feature ticket: migration `014_clearance_schema.sql`, repository/
service/schemas per repo conventions, endpoints under `/api/v1`, and an
update to `docs/frontend-api-guide.md` §5/§6.

---

*Cross-references: `database/migrations/010_song_publishing_schema.sql` ·
`docs/songs-schema-design-philosophy.md` · `docs/songs-database-planning.md` ·
`docs/frontend-api-guide.md` · `docs/rest-api-expansion-plan.md` ·
`src/schemas/{party,work,publishing}.py` ·
`src/services/{party,work}_service.py` ·
`src/repositories/{party,work}_repository.py` · `src/http_api.py`*
