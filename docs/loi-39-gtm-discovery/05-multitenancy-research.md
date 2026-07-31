# Multi-Tenancy Research: Loist as "the Linear of music" (LOI-5 discovery input)

Role: senior researcher/architect. Scope: tenancy model selection, codebase gap analysis, industry data-standard alignment, enterprise security requirements, phased delivery path. Grounded in the repo at `/Users/Gareth/loist-mcp-server` (branch state as of 2026-07-07, migrations 001–013).

---

## 0. What the codebase says today (baseline facts)

| Fact | Evidence |
|---|---|
| No users table exists anywhere | `database/migrations/` — nothing creates `users`; `012_playlists_schema.sql:111` says "No FK to users table (doesn't exist yet)" |
| Auth is a single static bearer token, off by default | `src/config.py:37-39` (`bearer_token`, `auth_enabled: bool = False`); `src/api_auth.py` (ASGI middleware, `/api/*` only); `src/auth.py` `SimpleBearerAuth` for MCP |
| The MCP endpoint (`/mcp`), embed player (`/embed/*`), and oEmbed are explicitly **outside** the auth middleware | `src/api_auth.py` docstring: "This deliberately does NOT cover the MCP endpoint…" |
| Half-hearted tenancy prep already exists, inconsistently | `002_add_user_id.sql` adds `audio_tracks.user_id INTEGER` (nullable, unused); `011_albums_schema.sql:34` and `012_playlists_schema.sql:35` add `owner_id UUID` ("multi-tenancy prep: no FK enforcement yet"); `013_uploads_schema.sql` has **no** owner column at all. Note the type clash: INTEGER vs UUID. |
| Publishing schema is single-namespace with **global** unique constraints on industry IDs | `010_song_publishing_schema.sql:75-76` (unique `ipi_cae_number`, `isni` on `parties`), `:136` (unique `iswc` on `works`) |
| Splits are WIP-friendly, per-work junction rows | `work_writers` / `work_publishers` with `split_percentage DECIMAL(5,2)` 0–200, `split_status IN (proposed, confirmed, disputed, unknown)`, free-text `notes` ("negotiation notes, context for disputes") — i.e. exactly the data that is confidential per-tenant |
| All SQL is centralized, but tenant-blind | `database/operations.py`: 5,658 lines, 71 functions, ~77 `WHERE` clauses, zero tenant predicates |
| Repositories are module-level singletons with no request context | e.g. `src/repositories/work_repository.py`: `WorkRepositoryInterface.get_by_id(work_id)` — no tenant/user param anywhere; `get_work_repository()` returns a global |
| Connection pooling is psycopg2, no per-request session state | `database/pool.py` |
| 36 MCP tools registered on one FastMCP server | `src/server.py` (`@mcp.tool` count), plus REST routes in `src/http_api.py` and an A2A FastAPI server (`src/a2a_server/`, port 8081) |
| One GCS bucket, path conventions per feature not per tenant | `src/config.py:63` `gcs_bucket_name`; `uploads/{upload_id}/{filename}` staging (`013_uploads_schema.sql`) |
| Cross-tenant-ish views exist and will interact badly with RLS | `010:464-527` `v_work_split_summary`, `v_party_involvement` — views owned by a superuser bypass RLS (classic pitfall) |

Bottom line: this is a **clean single-tenant codebase with tenancy graffiti** (`user_id`, `owner_id`) sprayed on three tables in two incompatible types. Nothing enforces anything. That is actually good news: there is no half-built tenancy system to unwind.

---

## 1. Tenancy models compared for THIS product

### The domain constraint that drives everything

The music-rights ecosystem is a graph of organizations forced to collaborate on shared objects:

- **Semi-public industry facts**: works, writers, ISWC/ISRC/IPI/ISNI identifiers, canonical titles. Every serious publisher already exchanges these with societies via CWR and with counterparties via cue sheets. Not secret.
- **Highly confidential per-tenant data**: split percentages *as negotiated*, split status/disputes, negotiation `notes` (already a column on `work_writers`/`work_publishers`), contacts, quotes, deal terms, sync fees, unreleased audio.
- **Cross-tenant collaboration objects**: the clearance request/thread itself — supervisor B asks publisher A about a work co-published by C and D. All four need a view of the *thread*; none should see each other's internal splits or margins.

Crucially, in the real industry **each publisher maintains its own registration of a work** (its own view of splits) and societies reconcile conflicting claims — CWR submissions are per-publisher and must sum to 100% *within that publisher's claim*, and societies return ACK files with the assigned ISWC ([CWR Demystified — Reprtoir](https://www.reprtoir.com/blog/cwr-demystified), [Curve: How to Register a Work](https://www.curveroyaltysystems.com/royalties-101-publishing/lesson-8-how-to-register-a-work)). So "the splits" are not one global truth Loist can host; they are per-tenant claims about a globally identified work. This kills any design where `work_writers` is a shared global table.

### (a) Org-per-tenant, row-level `tenant_id` + Postgres RLS

Everything (works, parties, splits, audio, playlists) gets `tenant_id`; RLS policies filter by a per-transaction GUC (`SET LOCAL app.tenant_id = ...`), app connects as a non-superuser role so RLS applies ([AWS RLS guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/rls.html), [Nile: multi-tenant RLS](https://www.thenile.dev/blog/multi-tenant-rls)).

- **Pros**: single mechanism; secure-by-default (no tenant context ⇒ zero rows); leaves `database/operations.py`'s 71 functions largely intact — RLS enforces what the WHERE clauses forget. One migration pattern per table. Well-trodden.
- **Cons for this domain**: works/parties duplicate per tenant (every publisher re-keys "Shape of You"); the global unique indexes on `iswc`/`ipi`/`isni` must be relaxed to `UNIQUE(tenant_id, iswc)`; cross-tenant clearance is impossible without punching holes in the model later. Pure (a) treats the industry graph as disconnected islands — which is exactly the product's differentiator to avoid.
- **Perf note**: every RLS table needs `tenant_id` as the leading column of its hot indexes or queries degrade badly ([Permit.io RLS guide](https://www.permit.io/blog/postgres-rls-implementation-guide)).

### (b) Schema-per-tenant

One Postgres schema (or database) per org.

- **Pros**: hard isolation, trivially satisfies "our data is physically separated" procurement questions; per-tenant restore.
- **Cons**: migration fan-out across N schemas (14 migrations already, hand-numbered SQL, with an existing numbering collision at 002 — three files share the prefix); psycopg2 pool per schema; connection exhaustion; cross-tenant collaboration objects have *nowhere to live*; search across the ecosystem impossible. Operationally this is v0's "per-customer deploy" wearing a costume, with all its scaling costs and none of its simplicity. **Reject** as the multi-tenant end-state; its benefits are delivered more honestly by v0 single-tenant deploys.

### (c) Hybrid: global works/parties registry + tenant-private splits/contacts/tasks

Split the schema into three zones:

1. **Global reference zone** (no `tenant_id`, read-mostly, curated): `registry_works` (ISWC, canonical titles, language), `registry_parties` (IPI/ISNI, names, society affiliation). This is where the existing global unique indexes on `iswc`/`ipi_cae_number`/`isni` (`010:75-76,136`) belong — they are *already the right constraint for a registry* and the wrong one for tenant rows. Populated by CWR/DDEX import and by promotion of tenant records that acquire an ISWC.
2. **Tenant-private zone** (`tenant_id NOT NULL` + RLS): tenant's own `works` ("my catalog entry", FK → optional `registry_work_id`), `parties` ("my contact card for this person", FK → optional `registry_party_id`), `work_writers`/`work_publishers` (the tenant's *claim* of splits — matching CWR semantics), `audio_tracks` (unreleased masters!), `albums`, `playlists`, `uploads`, quotes, deal terms, tasks.
3. **Collaboration zone** (see (d)): clearance threads with explicit membership.

- **Pros**: matches industry reality (per-publisher claims over globally identified works); one publisher's ISWC lookup enriches everyone; no re-keying; the registry becomes a moat (network effect); confidential data never leaves the tenant zone.
- **Cons**: entity-resolution problem (when do two tenant works merge to one registry work? ISWC when present, fuzzy title+writer-IPI match otherwise — the `pg_trgm` indexes already in `010` help); two-hop reads; registry governance (who fixes a bad canonical title?).

### (d) Cross-tenant shared objects (clearance threads)

Prior art: **Slack Connect** broke the "workspace = atomic partition unit" assumption with channels having explicit per-org membership and per-org settings, only name/avatar/email shared by default ([How Slack Built Shared Channels](https://slack.engineering/how-slack-built-shared-channels/), [Slack Connect docs](https://docs.slack.dev/apis/slack-connect/)); **GitHub outside collaborators** (object-level grants without org membership); **Stripe Connect** (accounts linked to a platform with scoped data visibility). The common shape: a shared object with a membership table `(object_id, org_id, role, joined_at)`, where each org sees the shared surface (messages, status, attachments explicitly shared) but the object *references* rather than *contains* tenant-private data.

For Loist: `clearance_threads(id, registry_work_id, created_by_tenant, status, brief_ref)`, `thread_members(thread_id, member_type ∈ {tenant, guest}, tenant_id | guest_contact_id, role)`, `thread_events(...)`. Publisher A's splits stay in A's zone; the thread shows only what A chooses to assert ("we control 50%, confirmed").

### Recommendation

**(c) hybrid as the destination, built on (a)'s mechanics, with (d) as the v2 collaboration layer.** Concretely: v1 ships plain row-level `tenant_id` + RLS across all existing tables (works and parties included — tenant-scoped, with unique indexes relaxed to per-tenant), *plus* a nullable `registry_work_id`/`registry_party_id` column from day one so the global registry can be introduced without a second painful migration. Schema-per-tenant is rejected; pure (a) forever is rejected because cross-tenant clearance is the product.

### Counterparties who are NOT customers

Most of the long tail (small publishers, self-administered writers, one-off supervisors) will never sign up. They participate via:

- **Email bridge**: the clearance thread has an email address (`thread+<token>@mail.loist.io`); outbound messages go as email, inbound replies are parsed onto the thread (the Linear/Front pattern). Requires inbound-parse infra (SendGrid/Postmark) + a `guest_contacts` table. The existing `parties.email` column (`010:56`) is the natural join point.
- **Guest magic links**: a signed, expiring, thread-scoped URL (view + reply + accept/decline + upload one file), no account, no tenancy. Loist already has the signed-URL muscle (GCS signed URLs, `src/storage/`, LOI-45 upload flow) and a public-surface precedent (embed player /oEmbed routes deliberately outside auth, `src/api_auth.py`). Guests are `thread_members` with `member_type='guest'` — they never gain catalog visibility.
- **Promotion path**: a guest who keeps showing up gets prompted to claim an org — the growth loop (same as Slack Connect invites and Figma viewers).

---

## 2. Codebase gap analysis

### Tables (every one needs a decision, ~19 tables)

| Table | Tenancy treatment |
|---|---|
| `audio_tracks` | `tenant_id NOT NULL` (unreleased masters = most sensitive asset). Drop the vestigial `user_id INTEGER` from 002 — wrong type, never used. |
| `works`, `work_alternative_titles` | tenant-scoped + nullable `registry_work_id`; relax `idx_works_iswc_unique` → `UNIQUE(tenant_id, iswc)` |
| `parties` | tenant-scoped + nullable `registry_party_id`; relax IPI/ISNI unique indexes likewise |
| `work_writers`, `work_publishers`, `recording_artists` | inherit tenancy via `work_id`/`audio_track_id` FK, but give them their own `tenant_id` column anyway — RLS policies via join are the documented slow path; denormalized `tenant_id` with composite leading indexes is the fast one |
| `albums`, `album_tracks`, `playlists`, `playlist_tracks`, `playlist_collaborators` | rename/repurpose `owner_id` prep columns: `tenant_id` (org) + `created_by` (user). `playlist_collaborators.user_id` finally gets its FK to the new `users` table |
| `uploads` | add `tenant_id` + `created_by` (currently ownerless — anyone who can hit the API can poll any job) |
| `a2a_tasks`, `push_notification_configs` | `tenant_id` |
| New: `organizations`, `users`, `org_memberships(user_id, org_id, role)` | the missing foundation |
| Views `v_work_split_summary`, `v_party_involvement` | recreate owned by the non-superuser app role or convert to `security_invoker = true`, else they silently bypass RLS |

Backfill is trivial precisely because the system is single-tenant: create one org, `UPDATE ... SET tenant_id = :the_org` everywhere.

### Data-access layer

- `database/operations.py` (5,658 lines, 71 fns): with RLS doing enforcement, most functions need **no WHERE rewrites** — but every write needs `tenant_id` in its INSERT, and hot queries need new composite indexes `(tenant_id, ...)`. Estimate touching ~40 of 71 functions lightly.
- `database/pool.py`: the load-bearing change. Every connection checkout must run `SET LOCAL app.current_tenant = %s` inside the transaction, and the app must connect as a dedicated non-superuser role (RLS does not apply to table owners/superusers). Wrap checkout in a context manager that takes tenant context; make tenant-less checkout impossible except for an explicit `system` path (migrations, registry sync).
- Repositories (`src/repositories/*.py`, 6 modules): interfaces take no caller identity. Two options: thread a `TenantContext` param through every method (loud, ~60 signatures), or a `contextvars.ContextVar` set by middleware and read at pool checkout (quiet, matches the async-service/sync-repo split noted in CLAUDE.md). Recommend the contextvar + explicit param only where behavior branches.

### MCP tool layer — how does a session carry tenant identity?

Today `src/server.py` registers 36 tools with zero identity; `SimpleBearerAuth` is one shared secret. The MCP spec (rev 2025-11-25) makes the server an **OAuth 2.1 resource server**: clients obtain tokens from an authorization server, the MCP server validates them per request and must derive identity *only* from the validated token ([MCP Authorization spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), [Descope on the MCP auth spec](https://www.descope.com/blog/post/mcp-auth-spec)). FastMCP 2.12+ supports token-validation auth providers, so the shape is: token → claims (`sub`, `org_id`) → contextvar → RLS GUC. Tools themselves need no signature changes — identity rides the transport, which is the single best architectural break Loist gets for free. The A2A server (port 8081) and Cloud Tasks callbacks need equivalent service-identity handling (already partially present: `cloud_tasks_strict_auth`, `src/config.py:102`).

### Auth stack (currently: none that counts)

Minimal viable stack: **OIDC via a hosted provider, orgs/users/memberships in Postgres, short-lived JWTs**. For the enterprise tier, big publishers (UMPG, Sony, Warner Chappell scale) will demand SAML/OIDC SSO against their IdP plus SCIM deprovisioning. Buy, don't build: **WorkOS** is purpose-built for exactly this shape (free AuthKit up to 1M MAU, ~$125/mo per enterprise SSO connection, embeddable admin portal so the customer's IT configures their own SAML), versus Auth0 which gates enterprise federation behind ~$1,500+/mo plans ([WorkOS vs Auth0 vs Clerk 2026](https://workos.com/blog/workos-vs-auth0-vs-clerk-the-best-auth-platform-for-b2b-saas-in-2026), [SSOJet 10-tool comparison](https://ssojet.com/blog/enterprise-authentication-for-developers-10-tools-compared)). Same issuer can serve browser (REST), MCP OAuth, and guest-link minting.

### Storage & public surfaces

- GCS: move to per-tenant object prefixes (`gs://bucket/{tenant_id}/...`); signed-URL generation (`src/storage/`, `gcs_signed_url_expiration`) must check tenant before signing. Single bucket is fine until data residency demands otherwise.
- Embed player + oEmbed are *deliberately public* (`src/api_auth.py` docstring); under tenancy they become a per-track "publish to web" flag decision, not an accident.

---

## 3. Industry data-standard angle: the global registry is an import target, not a data-entry burden

- **CWR** (CISAC standard, current CWR 3.x): the batch format publishers already use to register works with societies — titles, writer IPIs, roles, ownership/collection shares; societies ACK with assigned ISWCs ([Reprtoir CWR technical reference](https://docs.reprtoir.com/docs/cwr-technical-reference), [matijakolaric CWR overview](https://matijakolaric.com/articles/formats/cwr/)). Every design-partner publisher has CWR export from their existing system. **v1 onboarding should be "upload your CWR file"** — it populates tenant works + writer/publisher claims *and* seeds the global registry (works keyed by ISWC, parties by IPI). The existing schema maps almost 1:1: `works.iswc`, `parties.ipi_cae_number`, `parties.society_affiliation`, split percentages/statuses.
- **DDEX MWDR suite** — MWN (Musical Work Right Share Notification) for communicating per-rights-holder share claims downstream, BWARM for bulk work+recording metadata ([DDEX MWDR](https://ddex.net/standards/musical-works-data-and-rights-communication/), [MWN standard](https://kb.ddex.net/implementing-each-standard/musical-work-data-and-rights-communication-(mwdr)/musical-work-right-share-notification-standard-(mwn)/)). DDEX itself documents the MWN↔CWR relationship ([MWN and CWR](https://kb.ddex.net/implementing-each-standard/musical-work-data-and-rights-communication-(mwdr)/musical-work-right-share-notification-standard-(mwn)/mwn-explained/mwn-and-the-common-works-registration-(cwr)/)). MWN's whole premise — *each rights holder notifies its own share claim* — is independent confirmation that splits are per-tenant claims, validating the hybrid model.
- **Identifiers**: ISWC (work), ISRC (recording — note: not yet a column on `audio_tracks`, should be added), IPI/CAE (writer/publisher rights identity), ISNI (name identity). The registry's merge keys, in that priority order.
- **Confidentiality norms**: shares are routinely disclosed to societies and *direct* counterparties (a co-publisher knows the other side's share on that work), but a publisher's full catalog splits, unregistered/WIP splits, dispute notes, and sync quotes are competitively sensitive. Norm to encode: **on a clearance thread, a tenant asserts only its own control percentage and clearance position; the registry stores identification, never shares.** Registry rows must contain zero split data.

---

## 4. Security/compliance the top-20% publishers will impose (effort-ranked, cheapest first)

1. **SSO (SAML/OIDC)** — ~1–2 wks with WorkOS (per-connection pricing, customer-self-serve admin portal). Table stakes for majors.
2. **Audit logs** — 2–4 wks. Append-only `audit_events(tenant_id, actor, action, object, before/after, ts)` written at the service layer; the repository pattern gives one choke point. Also a product feature (clearance threads *are* an audit trail).
3. **NDA/unreleased-works controls** — 2–4 wks. Expiring signed URLs already exist; add per-asset access policy, download watermarking later, guest-link expiry + revocation, "who streamed this" from audit log. Contractual side is legal work, not eng.
4. **SOC 2 Type II** — the long pole: 4–9 months elapsed (needs months of operating evidence), ~$30–65k first year (compliance platform ~$7.5–15k + CPA audit $15–50k) ([SOC 2 cost breakdown 2026](https://cavanex.com/blog/soc-2-compliance-cost-2026), [Vanta audit-cost guide](https://www.vanta.com/collection/soc-2/soc-2-audit-cost)). Start the clock early in v1; engineering prerequisites (auth, RLS, audit logs, access reviews) are the same work anyway.
5. **Data residency** — defer. EU publishers may ask; the honest v0/v1 answer is region pinning (Cloud SQL + GCS region per deployment). True per-tenant residency in a pooled system is v3+ territory; ironically the v0 per-customer-deploy model satisfies it trivially, which is a sales card for early EU design partners.

---

## 5. Phased path

### v0 — single-tenant per-customer deploys for design partners: **viable now, with one gap**

The architecture already supports it: Docker Compose / Cloud Run + Cloud SQL per customer, config entirely env-driven (`src/config.py` — per-deploy `DB_*`, `GCS_BUCKET_NAME`, `BEARER_TOKEN`, `AUTH_ENABLED=true`). Isolation is absolute (separate DB + bucket), data residency free, no schema changes.
The gap: a shared static bearer token is not a login. Design partners need at minimum hosted OIDC (WorkOS AuthKit or even Google Workspace-restricted OIDC) in front of the web UI, plus the LOI-45 upload surface. No users table needed yet if everyone in the org is equal.
**Effort: ~2–4 wks** (deploy templating/IaC + minimal OIDC gate + per-deploy ops runbook). Ceiling: ~5–10 customers before migration fan-out (14 hand-numbered SQL files, no migration runner, duplicate `002_` prefixes already) and ops toil bite.

### v1 — row-level multi-tenant (pooled): **~8–12 engineer-weeks**

- `organizations`/`users`/`org_memberships`; WorkOS OIDC + session JWTs (1–2 wk)
- `tenant_id` on ~15 tables + backfill + relaxed unique indexes + composite `(tenant_id, ...)` indexes + nullable `registry_*_id` columns for the future (1–2 wk)
- RLS policies everywhere + non-superuser app role + `SET LOCAL` wiring in `database/pool.py` + contextvar plumbing through repositories/services (2–3 wk)
- MCP OAuth 2.1 resource-server auth on FastMCP; REST middleware upgrade from static token to JWT; A2A/Cloud Tasks service identity (1–2 wk)
- GCS per-tenant prefixes + signed-URL tenancy checks; embed "publish" flag (1 wk)
- CWR import for onboarding (1–2 wk, worth it — it is also the registry seeder)
- Testing incl. cross-tenant leak tests (the `requires_db` marker suite exists) (1–2 wk)
- Start SOC 2 clock in parallel.

### v2 — cross-tenant clearance threads + global registry: **~10–16 engineer-weeks**

- `registry_works`/`registry_parties` + ISWC/IPI-first entity resolution + promotion/merge tooling (3–4 wk)
- `clearance_threads`/`thread_members`/`thread_events` with Slack-Connect-style membership RLS (`tenant_id IN (SELECT ...)` policies — the one place join-based policies are unavoidable; index accordingly) (3–4 wk)
- Guest magic links (signed, thread-scoped, expiring) + email bridge (inbound parse) (2–4 wk)
- Assertion model: what a tenant exposes onto a thread ("we control X%, status confirmed") decoupled from private splits (1–2 wk)
- Notifications (`push_notification_configs` exists) + audit surface (1–2 wk)

### Sequencing note

v0 and v1 are not alternatives — do v0 immediately for the first 2–3 design partners (it also answers residency/isolation questions), build v1 underneath, migrate v0 customers into the pooled system as the first tenants (single-org backfill per deploy makes this mechanical).

---

## Sources

- [MCP Authorization specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) · [Descope: MCP auth spec](https://www.descope.com/blog/post/mcp-auth-spec)
- [AWS Prescriptive Guidance: RLS for multi-tenant PostgreSQL](https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/rls.html) · [AWS blog: multi-tenant isolation with RLS](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/) · [Nile: shipping multi-tenant SaaS with RLS](https://www.thenile.dev/blog/multi-tenant-rls) · [Permit.io: Postgres RLS pitfalls](https://www.permit.io/blog/postgres-rls-implementation-guide)
- [Slack Engineering: How Slack built shared channels](https://slack.engineering/how-slack-built-shared-channels/) · [Slack Connect developer docs](https://docs.slack.dev/apis/slack-connect/)
- [Reprtoir: CWR demystified](https://www.reprtoir.com/blog/cwr-demystified) · [Reprtoir: CWR technical reference](https://docs.reprtoir.com/docs/cwr-technical-reference) · [matijakolaric: CWR](https://matijakolaric.com/articles/formats/cwr/) · [Curve: how to register a work](https://www.curveroyaltysystems.com/royalties-101-publishing/lesson-8-how-to-register-a-work)
- [DDEX: Musical Works Data & Rights Communication standards](https://ddex.net/standards/musical-works-data-and-rights-communication/) · [DDEX KB: MWN standard](https://kb.ddex.net/implementing-each-standard/musical-work-data-and-rights-communication-(mwdr)/musical-work-right-share-notification-standard-(mwn)/) · [DDEX KB: MWN and CWR](https://kb.ddex.net/implementing-each-standard/musical-work-data-and-rights-communication-(mwdr)/musical-work-right-share-notification-standard-(mwn)/mwn-explained/mwn-and-the-common-works-registration-(cwr)/) · [DDEX KB: BWARM](https://kb.ddex.net/implementing-each-standard/musical-work-data-and-rights-communication-(mwdr)/bulk-communication-of-work-and-recording-metadata-(bwarm)/)
- [WorkOS: WorkOS vs Auth0 vs Clerk (2026)](https://workos.com/blog/workos-vs-auth0-vs-clerk-the-best-auth-platform-for-b2b-saas-in-2026) · [SSOJet: 10 enterprise auth tools compared](https://ssojet.com/blog/enterprise-authentication-for-developers-10-tools-compared)
- [Cavanex: SOC 2 cost 2026](https://cavanex.com/blog/soc-2-compliance-cost-2026) · [Vanta: SOC 2 audit cost](https://www.vanta.com/collection/soc-2/soc-2-audit-cost)
