# Product Discovery Report: "The Linear of Music"
## Loist as project-centric task management for music publishers & rights holders

**Author**: PM role agent (B2B SaaS / workflow tools)
**Date**: 2026-07-07
**Grounding**: `docs/songs-database-planning.md`, `docs/songs-schema-design-philosophy.md`, `docs/roadmap.md`, `src/schemas/publishing.py`, LOI-39 clearance model proposal (use_cases + clearance_tasks, lifecycle draft → requested → negotiating → cleared | rejected | expired | withdrawn)

---

## 0. Executive framing

The thesis is that Loist stops being "a music library with a publishing schema bolted on" and becomes **a system of work for rights teams**, where the library + works/parties/splits graph is the *domain backbone* (the equivalent of Linear's git/GitHub integration surface — the thing work items point at), and the product's actual value is the **workflow layer**: clearance tasks, pitches, split confirmations, registrations, each with owners, states, deadlines, and views.

My overall read after mapping the primitives: **the analogy is generative but not literal**. Roughly 60% of Linear's primitive set maps cleanly (Issues, Sub-issues, Views, Triage, Labels, Projects); ~25% maps with modification (Teams, Relations, Roadmaps); and ~15% is actively misleading (Cycles, the assumption that all actors are workspace members). The music domain forces **four new primitives Linear doesn't have**: the **Counterparty** (external actor you negotiate with but who never logs in), the **Deal/Quote** (money, terms, territory, MFN coupling), the **Deadline-with-decay** (holds, options, license expiries — time acts on the object, not just on the human), and the **Attachment-as-source-of-truth** (the license PDF *is* the deliverable, not a description of it). A "Linear of music" that ignores these ships a pretty kanban board that loses to Excel.

The good news: Loist's existing schema philosophy — WIP-friendly, warnings-not-blockers, split_status as negotiation state, notes fields capturing context — is *exactly* the right cultural DNA for this product. `split_status: proposed/confirmed/disputed/unknown` is already a tiny state machine over a counterparty negotiation. LOI-39's clearance_tasks (one per rights-holder per work per use-case) is precisely the "Issue" atom the thesis needs. The bones are right.

---

## 1. Primitive mapping: Linear → music rights workflow

### 1.1 The mapping table

| Linear primitive | What it is in Linear | Music-domain equivalent | Mapping quality | Notes |
|---|---|---|---|---|
| **Workspace** | The company | The publisher / rights-holder org | Clean | Multi-tenancy is a hard prerequisite (currently a known gap — LOI-5, auth disabled). |
| **Team** | A group with its own issue stream, statuses, cycles | A **department**: Sync Licensing, Copyright/Registration, Royalties, A&R, Legal/Business Affairs, Catalog Ops | Clean | Each has genuinely different work types and statuses — this justifies Linear-style per-team workflows rather than one global state machine. See §1.2. |
| **Project** | Time-bound body of work with a lead, target date, status updates | Polymorphic: a **sync brief/campaign**, a **release**, a **catalog acquisition/onboarding**, a **registration batch**, a **client campaign** | Good, but needs a `project_type` | A sync brief ("Netflix drama, ep 4, needs 90s soul, $15k all-in, air date Oct 12") is the single best fit: deadline, lead, cross-team, definite done state. See §1.3. |
| **Issue** | Atomic unit of work; one assignee; state machine | The **LOI-39 clearance_task** (one per rights-holder per work per use-case); also: a pitch, a registration task, a split-confirmation chase, a metadata-fix task | Clean — this is the heart of the product | Lifecycle draft → requested → negotiating → cleared/rejected/expired/withdrawn is a legitimate Linear-style workflow with domain-specific terminal states. |
| **Sub-issue** | Child issues under a parent | Per-rights-holder tasks under a per-track clearance parent ("Clear 'Song X' for Use Case Y" → sub-task per writer/publisher who must approve); per-society tasks under a registration parent | Clean | LOI-39's "per-track rollups" *are* parent-issue progress bars. A track is only cleared when 100% of rights-holder sub-tasks are cleared — Linear's "parent closes when children close" needs to become a *computed* rollup, not a manual close. |
| **Cycle** | Fixed sprint cadence, auto-rollover | **Weak / mostly wrong.** Rights work is deadline-driven (air dates, release dates, PRO submission windows, quarterly royalty close), not sprint-driven | Poor | Don't ship Cycles v1. The closest honest analogues: royalty quarter close (royalties team), CWR submission batches (copyright team). Model those as recurring Projects, not Cycles. See §1.5. |
| **Triage** | Inbox for un-routed inbound issues | The **brief inbox**: inbound sync requests (email from supervisors), inbound split sheets, inbound catalog delivery from a new signing, incoming license requests via the embed player | Excellent — possibly the killer feature | Publishers' real triage queue today is a shared Outlook inbox. "Forward brief@loist to create a triaged Project with parsed deadline/budget/media" is a genuinely Linear-quality move. |
| **View** | Saved filter/board across issues | "My clearances", "All negotiating > 7 days", "By counterparty (all open items with Netflix)", "Expiring holds this month", "Disputed splits", "Works ready to register", board-by-status per use-case | Clean | The by-counterparty view is *more* important than in Linear, because the bottleneck is almost always an external party. |
| **Label** | Freeform tags | Genre/mood (pitching), media type (film/TV/ad/game/trailer), territory, one-stop vs multi-party, MFN, rush | Clean | Some "labels" should be structured fields, not tags: territory, media, term are deal parameters that drive money — see §1.6. |
| **Relation: blocks** | Issue A blocks Issue B | "Split confirmation blocks clearance" (can't quote what you don't control); "co-publisher approval blocks license issuance"; "registration blocked by unconfirmed splits" | Clean and high-value | The schema's `split_status` already encodes the most common blocker in the industry. Surfacing "this clearance is blocked because writer splits are only 80% confirmed" is a direct competitive weapon. |
| **Relation: duplicate** | Same issue filed twice | Same **work** ingested twice (multiple recordings of one composition — `merge_works` deferred in roadmap); same **party** created twice; two briefs for the same production | Clean | Work-merge and party-merge, both explicitly deferred in current MVP scope, get promoted from data hygiene to workflow necessity under this thesis. |
| **Roadmap / Initiative** | Multi-project strategic container | A **production/client account** ("all Netflix projects"), a **catalog** ("everything in the acquired Foo Music catalog"), a **release campaign** spanning registration + sync + marketing | Good | Initiative = Counterparty-account or Catalog. Gives execs the "how much sync revenue is in flight with each studio" view. |
| **Milestone** | Checkpoint within a project | Air date, option deadline, spotting session, PRO submission window, release date | Good | These are *hard external dates*, unlike most Linear milestones. Missing one has legal/monetary consequences → needs louder escalation than Linear's gentle slippage UI. |
| **SLAs / due dates** | Optional | **Mandatory.** Quote validity windows, hold expirations, option exercise deadlines | Must be first-class | Time-based auto-transition (requested → expired) is in LOI-39 already. Good. |
| **Customer Requests** (Linear's newer primitive) | Link external customer asks to issues | The closest existing Linear primitive to the **Counterparty** concept | Instructive | Linear itself had to bolt on an "external actor" primitive when it moved toward customer-facing workflows. Loist needs this at the core, not bolted on. |

### 1.2 Teams inside a publisher — the honest org chart

A mid-to-large publisher (10–200 people; think Concord, Reservoir, Primary Wave, peermusic, or the indie tier: Secretly, Domino, Hipgnosis-administered catalogs) genuinely divides into Linear-shaped teams:

1. **Sync / Creative Licensing** — pitches catalog to supervisors, agencies, brands; negotiates fees; requests clearances. Work is fast, deal-shaped, deadline-driven (hours-to-weeks).
2. **Copyright / Registration Admin** — registers works with PROs (ASCAP/BMI/PRS/GEMA…), the MLC, HFA; maintains ISWC/IPI data; processes CWR files; resolves conflicts/counterclaims. Work is batch-shaped, accuracy-driven (weeks-to-months).
3. **Royalties** — ingests society/DSP statements, matches income to works, investigates unmatched income ("black box"), runs quarterly client accounting. Work is cyclical and data-heavy.
4. **A&R / Creative** — signs writers, tracks holds/cuts (songs placed with recording artists), manages writer relationships and sessions.
5. **Legal / Business Affairs** — drafts and reviews licenses, signs off on deals over a threshold, manages contract templates and precedents.
6. **Catalog / Copyright Ops** (sometimes merged with #2) — onboards acquired catalogs, chain-of-title verification, metadata cleanup.

The Linear insight that transfers perfectly: **each team owns its own issue types and states, but issues reference the same underlying objects** (works, parties, recordings). A clearance task (sync team) and a registration task (copyright team) both hang off the same `work_id`. That shared spine is exactly what Loist's schema provides and what email/Excel can never provide. **This is the core architectural bet and it's sound.**

### 1.3 What is a Project? Answer: it's polymorphic, and that's fine

Linear Projects are already loosely typed; Loist should type them:

| project_type | Contains (issues) | Lead | Done means |
|---|---|---|---|
| **Sync brief** (inbound) | Pitch tasks → hold → clearance tasks per rights-holder → license → invoice → cue sheet confirmation | Sync manager | Licensed & invoiced, or passed |
| **Pitch campaign** (outbound) | Pitch tasks per target supervisor/brand, playlist deliverables (Loist's existing playlists/embed player = the pitch deliverable!) | Sync manager | Campaign window closed |
| **Release** | Split confirmations, registrations per society, label licensing, metadata QA | Catalog/A&R coordinator | Live + registered |
| **Catalog onboarding** | Per-work data verification tasks, chain-of-title checks, bulk registration, ingestion QA | Catalog manager | Catalog live & registered |
| **Registration batch** | Per-work-per-society registration tasks, CWR export, acknowledgment reconciliation | Copyright admin | All ACKs processed |
| **Client campaign / account push** | Mixed pitches + relationship tasks for one counterparty | Sync or A&R | Quarter end |

Strategic note: **the sync brief is the wedge project type.** It has the strongest pain (deadline pressure + multi-party coordination + money), the clearest done-state, and it exercises every novel primitive (counterparty, quote, expiry, rollup). Build project_type=sync_brief first; the others reuse the machinery.

### 1.4 Where the mapping needs NEW primitives (the gap list)

These are the things that make this "the Linear of music" rather than "Linear with music labels." Each is a real schema/product object, not a skin:

**(a) Counterparty.** A `party` who participates in workflow without a seat. A music supervisor requests a quote; a co-publisher must approve; a writer must confirm a split. None of them are workspace members. Needs: per-task external-participant links, tokenized approval/confirmation links (magic-link "Approve this split" pages — the embed-player infrastructure and signed-URL machinery already in the codebase is genuinely reusable here), an activity log that distinguishes internal notes from counterparty-visible messages, and email-in/email-out threading per task. **Linear has nothing like this at the core.** This is the single biggest build item and the single biggest moat.

**(b) Deal / Quote.** Money and terms: fee, media, term, territory, options, exclusivity, MFN (most-favored-nations) linkage. A clearance task without a quote object is a to-do; with one, it's a pipeline. MFN creates a *coupling constraint Linear can't express*: if the master side gets $20k, the publishing side's quote auto-escalates — i.e., a field on task A is a function of a field on task B. v1 can store terms as structured fields on the use_case + per-task fee, and merely *flag* MFN pairs rather than compute them.

**(c) Split/ownership context on every task.** A clearance task's assignee needs to see, inline: who controls what % of this work, what's confirmed vs disputed, and whether the publisher can offer a "one-stop" (controls 100% of both sides). This is a *computed property of the works graph*, rendered inside the issue view. Linear issues describe work; Loist issues must *interrogate the rights graph*. Already 80% built (`get_work` warnings).

**(d) Time-as-actor.** Holds expire. Quotes lapse. Options must be exercised by a date. Licenses end (retro-renewal is a revenue opportunity: "this 3-year ad license expires next month — chase renewal"). Linear's due dates are advisory; Loist needs scheduled state transitions (`requested → expired`) and an "expiring soon" system view. LOI-39 already includes `expired` as a state — keep it machine-driven.

**(e) Document as artifact.** The license PDF, the signed split sheet, the fully-executed sync agreement. v1 answer: attachments with a `document_type` and status (draft/sent/executed) on tasks — NOT a contract-drafting or e-sign product. Integrate DocuSign later; never build it.

**(f) The Work/Recording distinction inside tasks.** A sync license clears *two* rights: the composition (publisher's side) and the master (label's side). Loist's schema already separates works from recordings — most workflow tools don't. A clearance task must declare which side(s) it covers; a publisher-side user often needs a task "confirm master side is cleared by [external label]" that they *track but don't own*. This maps to an issue assigned to a Counterparty — again primitive (a).

### 1.5 Cycles: skip them (v1 verdict)

Cycles encode "we plan work in fixed cadences and roll over remainder." Rights teams don't. Their cadences are external: air dates, society submission calendars (e.g., CWR windows), royalty quarters. Shipping Cycles v1 would be cargo-culting Linear's shape without its function. Ship instead: (1) hard-date milestones with escalation, (2) recurring project templates ("Q3 royalty close", "October BMI batch"). Revisit real Cycles only if copyright teams ask for throughput planning.

### 1.6 Labels vs fields: a design ruling

Resist the temptation to make territory/media/term/fee into labels. Anything that appears in a license or affects money is a **typed field on the use_case/quote** (filterable, reportable, exportable to the license). Labels are for the soft stuff: genre, mood, "rush", "trailer", "brand-safe", client tier. Getting this wrong poisons reporting forever (ask anyone who has tried to run revenue reports off Jira labels).

---

## 2. Personas inside a large publisher / rights holder

### P1. Sync Licensing Manager ("Maya", 29–45, Creative Licensing team of 2–8)
- **JTBD**: When a supervisor's brief lands, find matching songs I *actually control*, pitch them fast, and when one gets interest, confirm control/splits, quote, chase every co-publisher and the master side, and get a license signed before the air date.
- **Current tooling**: Outlook/Gmail (the real system of record), DISCO or SourceAudio or Disco-alternatives for pitching playlists, Excel "clearance grids" (rows = tracks, columns = rights-holders, cells = email status), sometimes Airtable/Monday, Synchtank at bigger shops, DocuSign for execution, the royalty system (Vistex/Counterpoint Music Maestro) consulted read-only to check ownership.
- **Pain**: state lives in her head and inbox; "did the co-pub ever reply?"; MFN surprises at signature time; discovering mid-deal that splits were never confirmed; zero visibility for her boss without a status email.
- **Buying power**: her VP of Sync is the likely economic buyer for the wedge product.

### P2. A&R Coordinator ("Dan", 24–35)
- **JTBD**: Track which of our writers are in sessions with whom, which songs are on hold with which artists/labels, chase split sheets after every session, and keep the pipeline from session → demo → hold → cut visible.
- **Current tooling**: Notes app + text messages + Excel hold lists; DISCO for sharing demos; split sheets as PDFs/photos of paper in email; maybe a CRM nobody updates.
- **Pain**: split sheets that never come back (blocks everything downstream); holds that silently expire; no single view of "songs by writer X and their status".

### P3. Copyright / Registration Administrator ("Priya", 30–55, Copyright team)
- **JTBD**: Get every controlled work registered accurately with every relevant society and the MLC, with correct splits and IPIs; process registration acknowledgments; resolve conflicts and counterclaims; keep chain-of-title defensible.
- **Current tooling**: Vistex/Counterpoint Music Maestro, Curve, or homegrown DB for the canonical copyright data; CWR files; society web portals; Excel trackers for "what's been sent where"; email for conflict resolution.
- **Pain**: knowing readiness ("which works have confirmed splits and complete IPIs and can therefore be registered?"); tracking per-society status per work (a work × 5 societies = 5 statuses); ACK reconciliation is manual.
- **Note**: Loist should be the *workflow tracker* around registration, not the CWR generator, in v1. `works.status` already ends at `registered` — the thesis expands that single status into a per-society task fan-out.

### P4. Royalty Analyst ("Tom", 28–50)
- **JTBD**: Match incoming statements to works, investigate unmatched income, answer writer/client queries about missing money, close the quarter.
- **Current tooling**: Vistex, Counterpoint, Curve, Music Maestro, heavy Excel.
- **Verdict**: **Not a v1 persona.** Royalty processing is a data-pipeline product (Curve et al.), not a task product. Loist touches him only as: "unmatched income investigation" tasks and as a consumer of clean splits data. Do not chase this persona early; it's a tarpit that kills music-tech startups.

### P5. Legal / Business Affairs ("Sandra", 35–60)
- **JTBD**: Review/approve deals above threshold, issue license paperwork from templates, ensure MFN and exclusivity terms don't conflict across deals, keep executed agreements findable.
- **Current tooling**: Word + email + DocuSign + a DMS (iManage/NetDocuments) or shared drives.
- **v1 role**: an approver inside clearance workflows (an issue state "awaiting BA approval") + attachment consumer. Not a contract-management buyer.

### P6. Catalog Manager / Copyright Ops ("Jorge", 30–50)
- **JTBD**: When we acquire or sign a catalog, get thousands of works ingested, deduplicated, ownership-verified, and registered — and know precisely how far along we are.
- **Current tooling**: Excel mapping sheets, the royalty system's import tools, consultants.
- **Fit**: catalog onboarding as a Project with per-work sub-tasks and rollups is a beautiful fit and directly exercises Loist's ingestion + dedup + merge_works machinery. Strong v1.5 candidate; too bulk-heavy for v1.

**Persona priority for the wedge: P1 (buyer + daily user), P2 (adjacent daily user, feeds P1 clean splits), P3 (fast follow), P6 (v1.5), P5 (participant not buyer), P4 (defer).**

---

## 3. User stories

### Workflow A — Sync clearance (inbound brief)
1. As a **sync manager at a mid-size publisher**, I want to forward a supervisor's email brief to a Loist address and have it become a triaged Project with parsed deadline, media, budget, and counterparty, so that briefs stop living in my inbox and my team sees them the moment they land.
2. As a **sync manager**, I want to attach candidate tracks from our library to a brief and have Loist auto-generate one clearance task per rights-holder per track per use-case (per LOI-39), pre-populated with each party's split and confirmation status, so that I never discover an unknown co-publisher after I've quoted.
3. As a **sync manager**, I want a per-track clearance rollup (e.g., "3 of 4 rights-holders cleared; blocked on Kobalt, requested 6 days ago") visible on the brief's board, so that I can answer "where are we on the Netflix spot?" without opening a spreadsheet.
4. As a **sync manager**, I want quote terms (fee, media, term, territory, MFN flag) captured as structured fields on the use-case, so that when the deal closes, the license request and invoice contain the negotiated terms instead of whatever was in the last email.
5. As a **head of sync**, I want a board of all open clearances across my team grouped by counterparty and sorted by time-in-state, so that I can spot stalled negotiations and chase the right external party this week.
6. As a **sync manager**, I want holds and quotes to auto-expire into an `expired` state with advance warning notifications, so that lapsed options get renegotiated instead of silently dying (or worse, silently assumed alive).

### Workflow B — Pitching (outbound)
7. As a **sync manager**, I want to build a pitch playlist from the library, send it via the existing embed player, and see per-recipient engagement (opened, played, downloaded) recorded on the pitch task, so that follow-ups are prioritized by actual interest, not guesswork.
8. As a **sync manager**, I want a pitch pipeline view per counterparty (pitched → shortlisted → on hold → licensed/passed), so that I know what each supervisor already has of ours and never re-pitch a track they passed on last month.

### Workflow C — Split confirmation
9. As an **A&R coordinator**, I want to send each writer/co-publisher on a new work a tokenized "confirm your split" link that flips their `work_writers` row from proposed to confirmed (or disputed, with a note) — no login required, so that split sheets stop dying in email attachments.
10. As an **A&R coordinator**, I want a "disputed & unconfirmed splits" view across the catalog, ranked by downstream demand (works attached to active briefs first), so that I chase the confirmations that are actually blocking money.
11. As a **sync manager**, I want clearance tasks automatically flagged blocked when the underlying work's splits are <100% confirmed, with a one-click "request confirmation" action that spawns the chase task, so that ownership problems surface at pitch time, not at contract time.

### Workflow D — Registration
12. As a **copyright administrator**, I want a "ready to register" view (splits 100% confirmed, IPIs present, no disputes) that fans out into per-society registration tasks per work, so that registration status is per-society and trackable instead of a single optimistic checkbox.
13. As a **copyright administrator**, I want registration tasks to hold society-specific data (submission date, society work ID, ACK status) and to bulk-transition when a society acknowledgment batch comes back, so that reconciliation takes minutes, not a day of Excel.

### Workflow E — Catalog onboarding
14. As a **catalog manager**, I want an acquired catalog imported as a Project with a per-work verification sub-task (metadata complete? ownership documented? duplicate of an existing work?), with duplicate-suspect tasks linked via a "duplicate" relation to drive `merge_works`, so that onboarding progress is a percentage my CEO can see, not a feeling.

### Workflow F — A&R relationship tracking
15. As an **A&R coordinator**, I want every hold (song X with artist Y's label, expires date Z) tracked as a time-boxed task linked to the work and counterparty, so that I can tell a supervisor instantly whether a song is encumbered before we pitch it — connecting A&R state to sync availability in one system.

**Strongest three, for the coordinator**: #2 (auto-fan-out of clearance tasks from the rights graph — the feature no horizontal tool can copy), #9 (tokenized counterparty split confirmation — the moat primitive, and it feeds everything downstream), #3/#5 (rollup + by-counterparty views — the daily-retention screen).

---

## 4. MVP cut

**Positioning sentence**: *Loist runs your sync clearances on top of your actual catalog — every brief becomes a tracked project, every rights-holder becomes a tracked task, and your ownership data tells you what's blocked before your counterparty does.*

### In scope v1 (the smallest thing a sync team adopts)
1. **Workspace/auth/multi-tenancy** — non-negotiable prerequisite; currently the codebase's biggest gap (auth disabled, LOI-5).
2. **Projects, type = sync brief** (+ a generic type): title, counterparty, deadline, budget, media/term/territory fields, status, lead. Email-in to create (even if parsing is manual-assist at first).
3. **Issues = clearance tasks per LOI-39** (`use_cases` + `clearance_tasks`, full lifecycle including machine-driven `expired`), plus a generic task type for chases/registrations. Assignee, due date, labels, comments, attachments.
4. **Auto-fan-out**: attach a track to a use-case → one clearance task per rights-holder from `work_writers`/`work_publishers`, seeded with split %, split_status, and blocked-flag when splits are incomplete/disputed. (Story #2/#11 — the wedge feature.)
5. **Rollups**: per-track and per-project clearance progress computed from child task states.
6. **Views**: My tasks; board by state per project; all-open by counterparty; time-in-state sort; expiring-soon. Saved filters. No custom view builder yet.
7. **Counterparty lite**: parties usable as external actors on tasks; tokenized confirm/approve pages for split confirmation (story #9) reusing the signed-URL + embed infrastructure; internal vs external comment visibility; outbound email with reply-threading onto the task (inbound full parsing can be assisted/manual).
8. **Quote fields, not a quote engine**: fee/media/term/territory/MFN-flag as structured fields; a rendered "quote summary" block for pasting into email.
9. **Pitch playlist link + basic engagement events** on a pitch task (leverages existing playlists/embed/waveform assets — cheap differentiation).
10. **Notifications & digest**: assignment, state change, counterparty action, expiry warnings.

### Deliberately OUT of v1
- **Royalty processing / statement ingestion** (P4) — different product, notorious tarpit. Integrate with Curve/Vistex later, never rebuild.
- **CWR generation & society API integration** — track registration as tasks (v1.5 fan-out per story #12/#13); generate CWR never-or-much-later.
- **Contract drafting / e-signature** — attachments + DocuSign links only.
- **MFN computation** — flag and link MFN-coupled tasks; humans do the math in v1.
- **Master-side (label) workflows as a first-class market** — publisher-side first; the master side appears only as a counterparty.
- **Cycles, roadmap/initiative UI, custom workflow designer, API/webhooks, mobile** — later.
- **Full supervisor-side portal** (two-sided marketplace) — the tokenized pages are the thin end; a supervisor login product is a Series-A bet, not an MVP.
- **AI features** (brief parsing, pitch matching) — genuinely promising given the MCP-native architecture, but v1 must prove the workflow spine first; bolt AI onto a working system of record.

### Adoption test for v1
A 3-person sync team at a 50-person indie publisher runs **one real brief end-to-end** (inbound → pitch → clearance fan-out → counterparty confirmations → cleared → license attached → done) and, four weeks later, their Excel clearance grid is stale because Loist is the truth. Secondary metric: ≥1 external counterparty action (split confirmation via token link) per active work — that's the moat primitive proving out.

---

## 5. Risks — where "Linear of music" misleads

1. **Counterparty-heavy vs internal-team work (the big one).** Linear's magic assumes everyone who moves an issue is in the workspace. In clearance, the *rate-limiting actor is almost always external* and unpaid to cooperate. If Loist only mirrors internal state, it's a status-typing tax on top of email and it loses to Outlook + Excel. Mitigation: the tokenized external-action primitive must be in v1, and email-in/out must be first-class, because email will remain the counterparty medium for years. The product wins by *absorbing* email, not replacing it.
2. **Small-N market with heavy incumbent gravity.** There are thousands of publishers but perhaps a few hundred with real sync teams; the big five run entrenched systems (Vistex, homegrown) and long procurement. Linear won by bottoms-up adoption among millions of developers; there is no equivalent long tail of "developers" here. Mitigation: land indie/mid-tier publishers and boutique sync agencies (fast sales cycles, acute pain), price per-seat+per-workspace, and accept this is a vertical-SaaS wedge (expand later toward supervisors/labels for TAM), not a Linear-scale horizontal.
3. **The system-of-record trap.** Publishers' canonical ownership data lives in their royalty/copyright system; Loist's works/splits copy will drift, and a clearance decision made on stale splits is a *legal* error, not a UX bug. Linear never had this problem — it doesn't claim to own the truth about your code. Mitigation: be honest about being the *workflow* system with a synced snapshot; build CSV/Counterpoint/Vistex import early, show data provenance and "as-of" timestamps on every splits panel, and treat the disputed/unknown states (already in the schema — a genuine advantage) as first-class UI.
4. **Issue-shaped vs deal-shaped work.** A negotiation isn't a linear state machine: quotes get revised, scope changes ("now they want worldwide in perpetuity"), MFN re-opens closed items, and one email can move five tasks at once. If the model is too rigid, users will do the real work in email and reluctantly update Loist after the fact — the death pattern of every CRM. Mitigation: cheap state edits, multi-task batch actions from one thread, revision history on quote fields, and the WIP-friendly warnings-not-blockers philosophy the schema already espouses.
5. **Two-sided cold start on the supervisor side.** Long-term upside is the network (supervisor sends brief in-product; clearance status flows back automatically), but supervisors adopt nothing that adds friction for them. Mitigation: everything the counterparty touches must be zero-login, zero-training (token links, email replies that thread automatically). Measure counterparty response rates obsessively; that metric decides whether the network story is real.
6. **Scope seduction toward adjacent tarpits.** Royalties, CWR, contracts, and DISCO-style pitching-with-search are each "obviously adjacent" and each is a company-killing detour. The MVP discipline above (integrate or track, don't rebuild) is the mitigation; the roadmap doc's existing "deliberately excluded" culture is encouraging.
7. **Rebuild-vs-reuse honesty.** The current codebase is an ingestion/streaming server with 8 publishing CRUD tools and no auth. The thesis requires a full multi-tenant collaborative app (users, permissions, comments, notifications, real-time views, email pipeline). Assume the *schema and media infrastructure* carry forward (they're genuinely good: works/parties/splits, WIP philosophy, embed/signed-URL machinery) but the *application layer is a new build* — roughly a re-founding, not a pivot of the existing surface. Budget accordingly.

---

## 6. Recommendation

Proceed with the repositioning, but name it honestly: not "Linear for music" as a horizontal work-graph, rather **"the clearance and rights-workflow system for publishers, built on their actual catalog."** Build the LOI-39 clearance model as the Issue atom, sync briefs as the Project wedge, the tokenized Counterparty primitive as the moat, and views/rollups as the retention surface. Defer Cycles, royalties, CWR, and contracts. The existing schema's WIP-friendly splits model is an unusually good foundation — the LOI-39 proposal is the right next brick, and this discovery supports promoting it from proposal to committed roadmap, with multi-tenancy/auth (LOI-5) sequenced immediately before or alongside it.
