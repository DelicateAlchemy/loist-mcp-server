# LLM Handover Note / Code Review Prompt

**Task**: Review the fix for LOI-30 - Missing `--add-cloudsql-instances` flag causing database connection failures in A2A staging.

**Context**: 
The A2A staging service was failing to connect to Cloud SQL with `FileNotFoundError: [Errno 2] No such file or directory` when accessing `/cloudsql/{connection_name}`. Root cause: Cloud Build deploy steps were missing the `--add-cloudsql-instances` flag, which is required for Cloud Run to mount the Cloud SQL Proxy Unix socket.

**Objective**:
Add `--add-cloudsql-instances` flag to all 4 Cloud Build deploy steps so Cloud Run services can connect to Cloud SQL via the Unix socket at `/cloudsql/`.

**Files Modified**:
1. `cloudbuild-a2a-staging.yaml` (line ~357) - Added flag with staging DB connection: `loist-music-library:us-central1:loist-music-library-db-staging`
2. `cloudbuild-a2a-prod.yaml` (line ~432) - Added flag with production DB connection: `loist-music-library:us-central1:loist-music-library-db`
3. `cloudbuild-staging.yaml` (line ~360) - Added flag with staging DB connection: `loist-music-library:us-central1:loist-music-library-db-staging`
4. `cloudbuild.yaml` (line ~387) - Added flag with production DB connection: `loist-music-library:us-central1:loist-music-library-db`

**Change Pattern**:
Added one line to each deploy step's args array:
```yaml
- '--add-cloudsql-instances=loist-music-library:us-central1:loist-music-library-db[-staging]'
```

Positioned immediately before the `--quiet` flag (last arg in each deploy step).

**Git Status**:
- Branch: `task-loi-30` (created from `dev`)
- Commit: `addafc8` - "fix(infra): Add --add-cloudsql-instances flag to all Cloud Build deploy steps (Task LOI-30)"
- Commit format follows project conventions

**Review Focus**:
1. ✅ Correct connection names (staging vs production)
2. ✅ Flag placement and syntax
3. ✅ YAML formatting and indentation
4. ✅ Consistency across all 4 configs
5. ✅ Alignment with Cloud Run Cloud SQL connection documentation

**Expected Outcome**:
After deployment, Cloud Run services will have the `run.googleapis.com/cloudsql-instances` annotation set, mounting the Unix socket at `/cloudsql/{connection_name}`, allowing database connections via the Cloud SQL Proxy.

**Related Documentation**:
- Issue: LOI-30 (Linear)
- Related fix: `docs/a2a-cloud-run-tempfile-fix.md` (TMPDIR fixes deployed successfully, this is separate infrastructure issue)

---

**Review Instructions**: Review these changes for correctness, consistency, and alignment with Google Cloud Run Cloud SQL connection requirements.

