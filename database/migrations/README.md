# Database Migrations

Hand-numbered, plain-SQL migrations applied by `database/migrate.py`. Files are applied
in **lexicographic filename order**, each in its own transaction, and tracked in a
`schema_migrations` table (one row per applied filename stem, i.e. `version`).

## Migration files

| File | Description |
|---|---|
| `001_initial_schema.sql` | Initial `audio_tracks` schema, full-text search, triggers |
| `002_performance_indexes.sql` | Additional performance indexes on `audio_tracks` |
| `003_add_a2a_tasks.sql` | Agent-to-agent task coordination table |
| `004_add_xmp_fields.sql` | XMP metadata fields (composer, publisher, record_label, isrc) |
| `005_optimize_xmp_indexes.sql` | Composite indexes for XMP field filtering |
| `006_optimize_search_vector.sql` | Enhanced full-text search optimization |
| `007_add_original_filename.sql` | Original filename tracking |
| `008_add_a2a_task_id_to_audio_tracks.sql` | Links `audio_tracks` to A2A tasks |
| `009_add_push_notification_configs.sql` | Push notification config table |
| `010_song_publishing_schema.sql` | Publishing/writer/publisher schema |
| `011_albums_schema.sql` | Albums schema |
| `012_playlists_schema.sql` | Playlists schema |
| `013_uploads_schema.sql` | Browser upload/ingestion schema (LOI-45) |
| `014_add_user_id.sql` | Multi-user support (`user_id` column on `audio_tracks`) |
| `015_add_waveform_support.sql` | Waveform generation columns on `audio_tracks` |

## LOI-51: dedupe of duplicate `002_` prefixes

Three files originally shared the `002_` prefix (`002_add_user_id.sql`,
`002_add_waveform_support.sql`, `002_performance_indexes.sql`), which is invalid for a
lexicographically-ordered migration runner — filenames must sort into a single,
unambiguous sequence.

None of the three had a functional dependency on each other or on any later migration
(all three only alter/index the `audio_tracks` table created in `001`, and no migration
003-013 reads the columns or indexes they add), so reordering them was safe. Two were
renamed to the next free sequential numbers (after `013`); the third kept its original
name. The relative order between the two renamed files reflects the order they were
originally authored, per `git log --follow` on each file:

| Old filename | New filename | First authored (git log) |
|---|---|---|
| `002_performance_indexes.sql` | `002_performance_indexes.sql` (unchanged) | 2025-11-04 |
| `002_add_user_id.sql` | `014_add_user_id.sql` | 2025-11-11 (morning) |
| `002_add_waveform_support.sql` | `015_add_waveform_support.sql` | 2025-11-11 (afternoon) |

### Baselining an already hand-migrated database

If a database already had these migrations applied by hand (or via an earlier ad-hoc
script) before `schema_migrations` tracking existed, running `apply` against it for the
first time will try to re-run `014_add_user_id.sql` and `015_add_waveform_support.sql`
under their new filenames (the tracking table only knows about filenames, not content).

`database/migrate.py` treats "already exists" style errors as idempotent (see
`DatabaseMigrator.IDEMPOTENT_ERRORS`) and will mark the migration as applied instead of
failing, so re-running `apply` is safe even without an explicit baseline. To avoid the
noisy idempotent-error log lines entirely, baseline explicitly instead:

```bash
# Mark every migration file as applied without executing any SQL
python database/migrate.py --action=baseline --database-url=postgresql://...

# Or, if a database only has the schema through the old "002_*" migrations applied,
# baseline just the renamed files explicitly using --up-to against the new filenames:
python database/migrate.py --action=baseline --up-to=015_add_waveform_support --database-url=postgresql://...
```

If a database was previously baselined (or migrated) against the *old* filenames
(`002_add_user_id`, `002_add_waveform_support`), its `schema_migrations` table will have
rows for those old version strings. Those rows are harmless to leave in place — they
simply won't match `014_add_user_id`/`015_add_waveform_support`, so `apply`/`baseline`
will (idempotently, per above) pick up the new filenames on the next run.

## Running migrations

`database/migrate.py` is a small, fully-typed CLI (argparse + psycopg2, no new
dependencies) that discovers `.sql` files in this directory and applies them.

```bash
# Apply all pending migrations
python database/migrate.py --action=apply --database-url=postgresql://user:pass@host:port/db

# Preview the plan without applying anything
python database/migrate.py --action=apply --dry-run --database-url=postgresql://user:pass@host:port/db

# "up" is a backward-compatible alias for "apply" — existing Cloud Build deploy
# pipelines (cloudbuild*.yaml) invoke --action=up and keep working unchanged.
python database/migrate.py --action=up --database-url=postgresql://user:pass@host:port/db

# Show applied vs. pending migrations
python database/migrate.py --action=status --database-url=postgresql://user:pass@host:port/db

# Mark all (or up to a given version) migrations as applied without running them —
# for databases whose schema was created by hand
python database/migrate.py --action=baseline --database-url=postgresql://user:pass@host:port/db
python database/migrate.py --action=baseline --up-to=006_optimize_search_vector --database-url=postgresql://user:pass@host:port/db

# Roll back the record for a specific migration (manual rollback SQL required)
python database/migrate.py --action=down --migration=001_initial_schema --database-url=postgresql://user:pass@host:port/db
```

The database URL can also come from the `DATABASE_URL` environment variable, or from
`src/config.py`'s `ServerConfig` (built from `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/
`DB_PASSWORD`), matching the rest of this codebase's configuration conventions.

### Tracking table

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,   -- migration filename stem, e.g. "014_add_user_id"
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    checksum VARCHAR(64),
    execution_time_ms INTEGER
);
```

This table is created automatically (if missing) by every `migrate.py` action. It has
been in production/staging use since the migration system was introduced, so its shape
(`version`/`checksum`/`execution_time_ms`/`applied_at`) is preserved as-is rather than
replaced with a different tracking-table schema, to avoid diverging from what is already
deployed.

### Guard against future duplicate prefixes

`tests/test_migration_filenames.py` is a pure-filesystem unit test (no database
required) that fails the build if two migration files ever share the same leading
numeric prefix again.
