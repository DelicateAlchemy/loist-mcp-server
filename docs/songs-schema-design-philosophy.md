# Song Publishing Schema: Design Philosophy & Context

> **Purpose of this document**: Provide context for developers and LLM coding agents working on the Loist codebase. This explains the *why* behind our song publishing data model — the constraints we're working within, the trade-offs we made, and the mental model to use when implementing features.

---

## TL;DR

This schema is designed for **work-in-progress music project management**, not PRO registration or royalty accounting. It prioritises flexibility over strictness, allowing incomplete and messy data that reflects how music is actually created.

---

## Core Design Principles

### 1. Audio-First Workflow

**The mental model**: Users upload audio files. Everything else flows from that.

- Every `audio_track` automatically gets a `work` (composition) created for it
- The `work` starts as a stub with the same title, status `draft`, no parties attached
- Users can later enrich the work with writers, publishers, splits
- Users can merge multiple recordings into a single work when they realise "these are all the same song"

**Why this matters for implementation**:
- When creating an audio track, always create a work too (1:1 initially)
- The `work_id` on `audio_tracks` is NOT NULL — every track has a work
- Don't require splits or parties to be defined before a track can exist
- The "happy path" is: upload audio → work exists → add details later (or never)

### 2. Work-In-Progress Friendly

**The problem we're solving**: Real music creation is messy. Splits are negotiated over weeks. Co-writers disagree. Publishers change. Data is incomplete.

**Our solution**: The schema accepts incomplete, inconsistent, and disputed data as valid states.

| Scenario | How the Schema Handles It |
|----------|---------------------------|
| Splits don't sum to 100% | Valid. `split_percentage` has no sum constraint. UI can warn, but DB doesn't block. |
| Splits exceed 100% | Valid (up to 200%). This happens during disputes. Flag it, don't prevent it. |
| Split percentage unknown | Valid. `split_percentage` is nullable. |
| Writer disputes their share | Valid. `split_status = 'disputed'` + notes field for context. |
| No writers defined yet | Valid. Junction tables can be empty. Work still exists. |
| Publisher not yet confirmed | Valid. `split_status = 'proposed'` or `'unknown'`. |

**Why this matters for implementation**:
- Never add validation that requires splits to sum to 100%
- Never require parties to be attached before saving
- Use `split_status` to track the state of each relationship, not just the number
- The `notes` fields on junction tables are important — they capture negotiation context
- Build UIs that surface warnings ("splits only add up to 80%") not blockers

### 3. Recording ≠ Composition

**The distinction**:
- **Recording** (`audio_tracks`): The actual audio file. Has technical metadata, GCS paths, ISRCs.
- **Composition/Work** (`works`): The underlying song. Has writers, publishers, ISWCs.

**Why they're separate**:
- One composition can have many recordings (original, radio edit, live version, cover by another artist)
- The recording artist is often not the songwriter
- Rights and splits attach to the composition, not the recording
- Industry standards (CISAC, CWR, DDex) model it this way

**Example**:
```
Work: "Respect" (writers: Otis Redding)
  ├── Recording: Otis Redding - "Respect" (1965)
  └── Recording: Aretha Franklin - "Respect" (1967)
```

**Why this matters for implementation**:
- `recording_artists` links artists to `audio_tracks` (who performed this recording)
- `work_writers` links writers to `works` (who wrote this composition)
- These are different relationships — don't conflate them
- When merging works, you're saying "these recordings are all the same underlying composition"

### 4. Raw Metadata vs Structured Data

**We keep both**:
- `audio_tracks` has string fields: `artist`, `composer`, `publisher`, `record_label`, `isrc`
- These are **raw ingested data** from file metadata (ID3, XMP, etc.)
- The structured tables (`parties`, `work_writers`, etc.) are **intentionally created** by users

**Why both**:
- Ingested metadata is often inconsistent ("The Beatles" vs "Beatles, The" vs "BEATLES")
- Auto-creating parties from strings would create massive duplication
- Users should consciously create parties and link them
- Raw strings remain as a reference / suggestion for what to create

**Why this matters for implementation**:
- Don't auto-create parties from metadata strings
- Build features like "Create party from 'John Smith'?" that let users confirm
- When displaying a track, you might show raw `artist` string if no `recording_artists` are linked
- The string fields are not deprecated — they serve a different purpose

---

## What We Deliberately Excluded (MVP Scope)

These are **intentional omissions**, not oversights. Don't add them without product discussion.

| Feature | Why Excluded | Future Consideration |
|---------|--------------|---------------------|
| **Multi-territory rights** | Complexity explosion. One split per writer is hard enough. | Add `territory` column to junction tables if needed later. |
| **Role taxonomy** (composer/lyricist/arranger) | Adds UI complexity. "Writer" is sufficient for MVP. | Add `role` column to `work_writers` later. |
| **Writer vs Publisher share distinction** | PROs model these as separate pools (50/50). We don't need this yet. | Add `share_type` column if PRO integration happens. |
| **Master rights / recording ownership** | Different from composition rights. Labels, not publishers. Complex. | Separate `recording_rights` table if needed. |
| **Party merging workflow** | Duplicate "John Smith" entries are okay for now. | Add `merged_into_party_id` and merge logic later. |
| **Cue sheets** | Sync/TV use case. Out of MVP scope. | Add `cue_sheets` and `cue_sheet_items` tables. |
| **Work versioning** | CWR tracks revisions. We don't need this yet. | Add `revision_number`, `previous_version_id` to `works`. |
| **Sub-publishers / administrators** | Just "publishers" for now. | Add `publisher_role` to `work_publishers` later. |

---

## Key Schema Decisions Explained

### Why `ON DELETE RESTRICT` for party references?

```sql
party_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT
```

- Deleting a party that's linked to works/recordings should fail
- Forces explicit handling: remove from works first, then delete party
- Prevents accidental data loss
- Parties are "important" entities — deletion should be deliberate

### Why `ON DELETE CASCADE` for work relationships?

```sql
work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE
```

- If a work is deleted, its writers/publishers/alternative titles go with it
- Works are the "parent" in these relationships
- But note: `audio_tracks.work_id` uses `ON DELETE RESTRICT` — you can't delete a work that has recordings

### Why `DECIMAL(6,4)` for splits with max 200?

```sql
split_percentage DECIMAL(6,4) CHECK (split_percentage >= 0 AND split_percentage <= 200)
```

- `DECIMAL(6,4)` gives us `00.0000` to `99.9999` precision
- Max 200 allows for over-claimed works during disputes (rare but real)
- No negative values — there's no legitimate use case, and it prevents data entry errors
- Nullable — "unknown" is a valid state, represented as NULL not 0

### Why `split_status` as a separate field?

```sql
split_status VARCHAR(20) NOT NULL DEFAULT 'proposed'
    CHECK (split_status IN ('proposed', 'confirmed', 'disputed', 'unknown'))
```

- The percentage alone doesn't tell you if it's agreed
- A 25% split could be: proposed, accepted, or actively disputed
- This enables workflows like "show me all disputed splits"
- Default is `proposed` — new entries are suggestions until confirmed

### Why a `works.status` workflow?

```sql
status VARCHAR(30) NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'splits_pending', 'splits_disputed', 'ready', 'registered'))
```

- Works have a lifecycle independent of their recordings
- `draft` → just created, no splits defined
- `splits_pending` → working on it
- `splits_disputed` → disagreement between parties
- `ready` → complete, could be registered
- `registered` → submitted to PRO(s)

This enables queries like "show me works ready for registration" or "works with unresolved disputes".

---

## Common Implementation Patterns

### Creating an audio track (with auto-work creation)

```python
# Pseudocode — always create work alongside track
def create_audio_track(metadata, audio_gcs_path):
    work_id = uuid4()
    track_id = uuid4()
    
    # Create stub work first
    insert_work(id=work_id, title=metadata['title'], status='draft')
    
    # Create track linked to work
    insert_audio_track(id=track_id, work_id=work_id, ...)
    
    return track_id, work_id
```

### Merging recordings into one work

```python
# User realises Track A, B, C are all the same song
def merge_tracks_to_work(track_ids, target_work_id):
    for track_id in track_ids:
        old_work_id = get_track(track_id).work_id
        
        # Repoint track to target work
        update_track(track_id, work_id=target_work_id)
        
        # Optionally: merge writers/publishers from old work to target
        # Optionally: delete old work if now orphaned
```

### Adding a writer with unknown split

```python
# Writer is confirmed but split not yet negotiated
def add_writer_to_work(work_id, party_id):
    insert_work_writer(
        work_id=work_id,
        party_id=party_id,
        split_percentage=None,  # Unknown
        split_status='unknown'
    )
```

### Checking if splits are "complete"

```python
# For UI warnings, not blocking logic
def get_split_warnings(work_id):
    warnings = []
    
    writer_total = sum(w.split_percentage for w in work_writers if w.split_percentage)
    publisher_total = sum(p.split_percentage for p in work_publishers if p.split_percentage)
    
    if writer_total < 100:
        warnings.append(f"Writer splits only add up to {writer_total}%")
    if writer_total > 100:
        warnings.append(f"Writer splits exceed 100% ({writer_total}%)")
    if any(w.split_status == 'disputed' for w in work_writers):
        warnings.append("One or more writer splits are disputed")
    
    return warnings
```

---

## Data Model Summary

```
┌─────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
│   parties   │       │        works        │       │    audio_tracks     │
│─────────────│       │─────────────────────│       │─────────────────────│
│ id          │       │ id                  │◄──────│ work_id (FK, NOT NULL)
│ party_type  │       │ title               │       │ title               │
│ name        │       │ iswc                │       │ artist (string)     │
│ legal_name  │       │ language            │       │ composer (string)   │
│ ipi_cae     │       │ status              │       │ publisher (string)  │
│ isni        │       │ notes               │       │ record_label (string)
│ society     │       └─────────────────────┘       │ isrc (string)       │
│ email       │                 │                   │ ... technical fields│
│ notes       │                 │                   └─────────────────────┘
└─────────────┘                 │                             │
       │              ┌─────────┴─────────┐                   │
       │              │                   │                   │
       │              ▼                   ▼                   │
       │    ┌──────────────────┐ ┌───────────────────┐        │
       │    │ work_alternative │ │                   │        │
       │    │     _titles      │ │                   │        │
       │    └──────────────────┘ │                   │        │
       │                         │                   │        │
       ├─────────────────────────┼───────────────────┼────────┘
       │                         │                   │
       ▼                         ▼                   ▼
┌─────────────────┐    ┌─────────────────┐   ┌───────────────────┐
│  work_writers   │    │ work_publishers │   │ recording_artists │
│─────────────────│    │─────────────────│   │───────────────────│
│ work_id (FK)    │    │ work_id (FK)    │   │ audio_track_id(FK)│
│ party_id (FK)   │    │ party_id (FK)   │   │ party_id (FK)     │
│ split_percentage│    │ split_percentage│   │ is_primary        │
│ split_status    │    │ split_status    │   │ notes             │
│ notes           │    │ notes           │   └───────────────────┘
└─────────────────┘    └─────────────────┘
```

---

## Questions to Ask Before Adding Features

When implementing new features against this schema, ask:

1. **Does this require splits to be "complete"?** → Probably shouldn't. WIP-friendly means incomplete is okay.

2. **Am I auto-creating parties from strings?** → Probably shouldn't. Let users intentionally create parties.

3. **Am I adding territory/region logic?** → Out of MVP scope unless explicitly requested.

4. **Am I distinguishing writer types (composer/lyricist)?** → Out of MVP scope. Just "writer" for now.

5. **Am I blocking on data validation?** → Prefer warnings over blockers. Let users save messy data.

6. **Does this conflate recordings and compositions?** → Keep them separate. They have different relationships.

---

## Glossary

| Term | Meaning in This Codebase |
|------|--------------------------|
| **Work** | The composition — the song itself, independent of any recording |
| **Recording** | An audio file (`audio_track`) — a specific performance/version of a work |
| **Party** | A person or organisation involved in music (writer, publisher, artist, label) |
| **Writer** | Someone who contributed to creating the composition (we don't distinguish composer/lyricist) |
| **Publisher** | Organisation that administers composition rights (we don't distinguish sub-publishers) |
| **Recording Artist** | Performer credited on a specific recording (not necessarily the writer) |
| **Split** | Percentage ownership share on a work (for writers or publishers) |
| **ISWC** | International Standard Musical Work Code — identifies a composition globally |
| **ISRC** | International Standard Recording Code — identifies a recording globally |
| **IPI/CAE** | Interested Parties Identifier — identifies a writer/publisher for PRO registration |
| **PRO** | Performing Rights Organisation (PRS, BMI, ASCAP, etc.) |

---

*Last updated: [Date of schema creation]*
*Schema version: Migration 007*