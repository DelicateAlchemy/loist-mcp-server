# "The Linear of Music" — Feasibility, Customers & Go-to-Market

**Master recommendation synthesized from a five-role discovery exercise (LOI-39 follow-on)**
Date: 2026-07-07 · **Status: RATIFIED by Gareth 2026-07-07** — thesis confirmed (clearance & rights-workflow system for publishers, sync wedge, founder-led GTM), ambition set to the **MCP/agent-layer emphasis** (§1.2.4), next step: customer discovery interviews ([06-discovery-interview-kit.md](06-discovery-interview-kit.md)) before any build commitment · Doc only, no code/migrations

**Inputs** (full reports in this directory, all grounded in the live codebase and/or live web research):

| # | Role | Report | Core question |
|---|------|--------|---------------|
| 1 | Product Manager | [01-product-manager.md](01-product-manager.md) | Do Linear's primitives map to music rights work? Use-cases, user stories, MVP cut |
| 2 | MBA Business Executive | [02-business-executive.md](02-business-executive.md) | Market size, competition, business model, revenue scenarios |
| 3 | Sales Manager / GTM | [03-sales-gtm.md](03-sales-gtm.md) | Named target accounts, buyer map, campaign design, pipeline model |
| 4 | UI/UX Director | [04-ux-director.md](04-ux-director.md) | IA, novel UI primitives, key flows specified end-to-end |
| 5 | Multi-tenancy Researcher | [05-multitenancy-research.md](05-multitenancy-research.md) | Tenancy model for a cross-org rights ecosystem (LOI-5 discovery input) |

---

## 0. Master verdict

**CONDITIONAL GO — on a reframed thesis.**

The thesis *as originally stated* — "the Linear of music," sold per-seat in a campaign at the biggest 20% of music publishing — **fails on arithmetic**. The entire worldwide population of addressable seats (sync, copyright, licensing, A&R staff at every publisher that has a team) is ~4,000–9,000. At Linear-comparable pricing, 100% penetration of every seat on Earth is ~$1–3M ARR. No campaign fixes that math, and the top of the market is guarded by 40-year incumbents (Vistex/Counterpoint at 400+ music companies including UMG; Synchtank at Disney/Sony/Warner Chappell PM) and 6–9-month procurement cycles a pre-auth, single-tenant product cannot enter.

The thesis *reframed* is viable and genuinely differentiated:

> **Loist is the clearance and rights-workflow system for publishers and rights holders, built on their actual catalog** — every sync brief becomes a tracked project, every rights-holder becomes a tracked task generated from the work's real splits, and counterparties participate with zero login via email and magic links.

Under that framing all five reports converge: the product mapping works (~60% of Linear's primitives transfer cleanly; four new domain primitives are required), the white space is real (nobody owns the cross-company clearance state machine — it lives in Outlook + Excel), the existing Loist schema is an unusually good foundation, and a realistic founder-led GTM exists. The honest ambition level is **vertical SaaS with a low-single-digit-$M ARR ceiling in its wedge market**, with two credible expansion bets layered on top: the cross-tenant clearance network ("the DocuSign of sync") and the MCP-native agentic layer riding on incumbent ERPs — the one strategy that plays to what Loist already technically is.

**The "biggest 20%" campaign is re-scoped, not discarded**: the biggest 20% of the market by revenue (3 majors + ~25–35 large independents) is the *18–36-month nurture list*. The *campaign* targets the winnable core of that list — sync-forward independents and pure-play sync houses — first as paid design partners, then as lighthouse logos that make the majors conversation possible.

---

## 1. Feasibility

### 1.1 The numbers (Business Executive, verified via live research)

- Global music publishing: ~$8B revenue (2025), ~64% held by the 3 majors; sync itself is a thin pool (~$650M recorded-side; ~$1.2–1.5B both sides).
- Sellable universe: ~1,000–2,000 publishers with ≥5 professional staff. "Biggest 20%" ≈ 200–400 companies, only ~30–50 of which have >20 relevant seats.
- Addressable seats: **~4,000–9,000 worldwide** (majors ~1,200–1,700; large indies ~1,000–2,000; mid indies ~2,000–5,000).
- 24-month revenue scenarios (team of 1–3): conservative ~$40–70k ARR · base ~$200–400k · optimistic ~$0.9–1.5M (requires one major division + a distribution partnership).

### 1.2 Why conditional-go rather than no-go

The exec's no-go applies to the venture-scale horizontal reading. Four countervailing findings:

1. **The white space is confirmed, not hypothetical.** All three market-facing reports independently found that no product owns the clearance lifecycle (requested → negotiating → cleared/rejected/expired), split confirmation chasing, or registration workflow. Synchtank's own content marketing sells advice for the pain because their product doesn't close it.
2. **Loist's differentiator is structural, not cosmetic.** Tasks are *generated from splits* (`work_writers`/`work_publishers` → one clearance task per rights-holder, pre-blocked when splits <100% confirmed). No horizontal tool (Airtable/Monday/Linear) can copy this without becoming a music-rights database first. The schema's WIP-friendly `split_status` philosophy (proposed/confirmed/disputed/unknown) is already a negotiation state machine.
3. **Pricing need not be per-seat.** Sales packaging (per-seat + platform fee, enterprise from $50k) and per-catalog pricing (Reprtoir precedent) lift ACVs to $9–50k; the v2 network layer opens per-clearance transaction pricing later.
4. **The MCP-native angle is real optionality.** Loist is literally an MCP server. "Clearance agents" that read/write incumbent systems, chase counterparties by email, and maintain the task state machine sell as automation ROI, not seats — and ride the enterprise-agent budget wave rather than competing with Vistex for the system of record.

### 1.3 Go/kill gates (decide by ~January 2027)

| Gate | Threshold | Owner report |
|---|---|---|
| Paid design partners | **3–5 signed at $500–1,000/mo within 6 months** (not free pilots) | Sales, Exec |
| Email absorption | ≥70% of new requests entering via email-in with zero counterparty behavior change | Sales, PM |
| Counterparty moat proof | ≥1 external action (split confirmation / quote response via magic link) per active work | PM, UX |
| Measured ROI | Documented cycle-time cut (request→quote) and "% quotes expired unactioned" vs. the Excel baseline | Sales |
| Adoption truth test | One design partner's Excel clearance grid goes stale within 4 weeks because Loist is the truth | PM |

Miss the gates → stop or pivot fully to the agent-layer play. Hit them → Year 2 is a $500k–1M ARR pipeline with a reference cohort, and the majors nurture begins.

---

## 2. Who the customers are

### 2.1 Segment (decided in this exercise): music publishers & rights holders

- **Champion / daily user:** Sync Licensing Manager ("Maya") — lives in Outlook threads, shared Excel clearance grids, and DISCO links; every expired quote and unconfirmed split is her personal fire. ~300–400 such titles exist across the 34 named accounts.
- **Economic buyer:** at indies, the founder/MD/COO (often a product user themselves; <$25k is discretionary); at large indies, COO/CFO or EVP Publishing Ops; at majors, EVP Sync + CIO + procurement.
- **Blockers:** IT/security (splits and deal terms are the industry's most sensitive data), the incumbent ERP owner (Vistex/Counterpoint, Synchtank), legal on data-processing. Neutralized by positioning as the **work layer on top of the system of record, never a replacement**, with read-only import and provenance timestamps.
- **Persona priority:** Sync manager (wedge) → A&R coordinator (feeds clean splits) → Copyright/registration admin (fast follow) → Catalog manager (v1.5) → Legal (participant) → **Royalty analyst: deferred — royalties is a documented company-killing tarpit.**

### 2.2 The named account list (34 accounts, full table with sources in [03-sales-gtm.md](03-sales-gtm.md))

- **Tier A — design partners, months 0–6:** Position Music, Third Side Music, Domino Publishing, Secretly Group, Beggars Group, Ninja Tune, Warp, Partisan, Mom+Pop, Sub Pop, peermusic, Wixen. Sync-forward indies where the signer is reachable and often in the product.
- **Tier B — lighthouse logos, months 6–18:** Reservoir, Concord, Primary Wave, Kobalt, BMG, Round Hill, Anthem, Spirit, Big Machine, Pulse, Sentric, Bucks, Wise, Budde, Exploration, Downtown (post-integration).
- **Tier C — majors, 18–36-month nurture only:** Sony Music Publishing, UMPG, Warner Chappell. Gated on multi-tenancy + SOC 2 + referenceable Tier A/B cohort. Enter via one regional sync team, never a global deal.
- **Timing intelligence:** M&A is reshaping the top right now (Primary Wave↔Kobalt closing ~Q3 2026; Virgin/UMG↔Downtown closed Feb 2026; Sony↔Recognition catalog). Integrations freeze systems decisions *and* create the strongest wedge ("catalog migrations create 10,000 checkable tasks — we're the checklist"); target the post-close 3–6-month window.

---

## 3. Go-to-market strategy

### 3.1 Sequence

1. **Months 0–6 — Paid design partners (3–5, Tier A).** Single-tenant per-customer instances sold as a *security feature* ("your own isolated instance and database"). $500–1k/mo, 6-month term, 50% off Year-1 list, in exchange for weekly feedback, case-study quotes, logo rights. Win theme: *"clearance pipeline out of the inbox in 30 days."*
2. **Months 6–12 — Lighthouse logos (Tier B).** Multi-tenant + SOC 2 in flight; convert 2–3 partners to case studies anchored on cycle-time reduction and expired-quote elimination.
3. **Months 12–18 — Category campaign.** "State of Sync Ops" benchmark report; SyncSummit NYC (Oct 2026) / LA (Feb 2027), AIMP/IMPF panel circuit, MBW/Music Week press; 12-seat sync-ops dinners ("this industry buys from people it has eaten with"). Majors nurture begins — they will have watched the indies.
4. **Months 18+ — Majors** via a single regional team.

### 3.2 Channels & community wedge

Founder-led, no SDRs (the pond is small; spray-and-pray burns it). Warm-intro rails: AIMP chapters, IMPF, PRO business-affairs contacts. The **Catalog marketplace cohort** (Beggars, Domino, Ninja Tune, Warp, Partisan) is a pre-assembled cluster of sync-progressive indies who talk to each other — land one, referral-path the rest.

### 3.3 Pricing & packaging

- Sync Team $99/user/mo (min 5 seats) → Publishing Ops $149/user/mo → Enterprise from $50k/yr (SSO, audit log, dedicated instance, ERP import).
- Land one sync team (5–10 seats ≈ $9–15k/yr) → expand to copyright → A&R → other offices (multi-office orgs like peermusic are the expansion goldmine).
- Pilots: 60–90 days, paid, one team, 3 mutually signed success metrics, conversion price agreed on day 1.
- Do **not** price on catalog size or % of sync fees in year 1.

### 3.4 Honest Year-1 pipeline (founder-led)

~80–90 accounts touched → 35–40 first meetings → 18–20 qualified → 7–9 pilots → **4–6 paying logos, $75–150k ARR**. Year 1 buys references, not revenue. Top objections and tested answers are in [03-sales-gtm.md](03-sales-gtm.md) §5 — the keystone line: *"Linear didn't replace GitHub; we don't replace Counterpoint."*

---

## 4. Product: the Linear mapping and what music forces

### 4.1 What maps (~60%), what bends (~25%), what breaks (~15%)

| Linear | Loist | Quality |
|---|---|---|
| Workspace | The publisher/rights-holder org | Clean (requires LOI-5) |
| Team | Department lens: Sync, Copyright, A&R, Legal — lenses over shared data, not silos | Clean |
| Project | **Sync brief / use-case** (typed: brief, release, catalog onboarding, registration batch) | Clean — the brief is the wedge project type |
| Issue | **LOI-39 `clearance_task`** (counterparty × work × use-case) — the only object users "work" | Clean — the heart of the product |
| Sub-issue rollup | Per-track clearance rollup **weighted by ownership %, not count** | Needs new math |
| Triage | The brief inbox: email-in briefs, counterparty replies, magic-link actions | Killer feature |
| Views | Board by status · **swimlanes by counterparty** (novel; promotes to a Counterparties page) · timeline with expiry bands · staleness sort | Clean |
| Cycles | **Skip.** Rights work is deadline-driven (air dates, society windows), not sprint-driven | Breaks |
| Members-only actors | **Breaks** — the rate-limiting actor is almost always external | Breaks → new primitive |

### 4.2 Four new primitives (unanimous across PM and UX; the build list that makes this defensible)

1. **Counterparty** — an external rights-holder who never logs in: email-bridged dual-channel task threads (tinted internal notes vs external replies; compose defaults internal), tokenized zero-login magic-link pages (scoped snippet player + Approve/Counter/Decline), per-org relationship views ("6 open items with Sony"). *Biggest build item, biggest moat, and biggest trust risk — one leaked internal note ends a customer relationship.*
2. **Deal/Quote** — asked/offered/agreed ladder, currency, MFN flag as typed fields, never labels or comment text. Flag MFN pairs in v1; never compute them.
3. **Time-as-actor** — holds, quotes, and licenses that auto-expire (LOI-39's `expired` state, machine-driven); expiries as living liabilities on the timeline; T-90/T-30 re-license reminders.
4. **Split-weighted clearance rollup** — two stacked bars (publishing + master), segments sized by share % and colored by task status, with a hatched **unattributed gap** when splits <100%. One rejection flips the track to Blocked regardless of percentage. If the UI can't honestly render unknown/disputed, users will fudge ownership data to green the bars — corrupting the chain-of-title record the product exists to keep.

### 4.3 Top user stories (of 15 in [01-product-manager.md](01-product-manager.md) §3)

1. *Auto-fan-out:* attach a track to a brief → one clearance task per rights-holder generated from real splits, pre-seeded with share % and blocked-flag — with a mandatory generation-preview screen (missing contacts, disputed splits, sub-100% attribution surfaced before anything is created).
2. *Tokenized split confirmation:* send each writer/co-publisher a no-login link that flips their split row proposed→confirmed/disputed — split sheets stop dying in email attachments.
3. *Rollup + by-counterparty views:* "3 of 4 rights-holders cleared; blocked on Kobalt, requested 6 days ago" without opening a spreadsheet; all-open-by-counterparty sorted by time-in-state as the head-of-sync daily screen.

### 4.4 Deliberately out of v1 (each an adjacent tarpit)

Royalty processing · CWR *generation* (import yes — it's the onboarding story) · contract drafting/e-sign (DocuSign links only) · MFN computation · supervisor-side portal · Cycles · custom workflow designer · AI brief parsing (bolt onto a working spine later — the MCP architecture makes this cheap when the time comes).

Full IA, wireframes, and three end-to-end flows (brief creation with generation preview; clearance to cleared with quote/expiry ceremony; the "My Day — 6 need action" screen) are specified in [04-ux-director.md](04-ux-director.md).

---

## 5. Technical path (LOI-5 discovery answered)

**Recommended tenancy model: hybrid** — row-level `tenant_id` + Postgres RLS across all tables (works/parties tenant-scoped; global ISWC/IPI/ISNI unique indexes relaxed to per-tenant), with **nullable `registry_work_id`/`registry_party_id` pointers from day one** toward a global registry keyed on industry identifiers, and Slack-Connect-style cross-tenant clearance threads in v2. Key domain insight: in CWR/DDEX practice **splits are per-publisher claims about globally identified works, never one shared truth** — which kills any shared-splits design and independently validates the hybrid. Schema-per-tenant rejected.

| Phase | What | Effort | Notes |
|---|---|---|---|
| **v0** | Per-customer single-tenant deploys (Cloud Run + Cloud SQL per partner) + minimal hosted OIDC gate | **~2–4 wks** | Viable today — config is fully env-driven; doubles as the security/residency sales card. Ceiling ~5–10 customers (hand-numbered migrations, duplicate `002_` prefixes, no runner) |
| **v1** | `organizations`/`users`/`org_memberships` (WorkOS OIDC), `tenant_id` on ~15 tables + RLS + non-superuser role + `SET LOCAL` in `database/pool.py`, contextvar through repositories, MCP OAuth 2.1 resource-server auth (FastMCP supports it — identity rides the transport, tools unchanged), GCS per-tenant prefixes, **CWR import as onboarding** | **~8–12 eng-wks** | Fix the `user_id INTEGER` vs `owner_id UUID` prep clash; re-own the `v_work_split_summary`/`v_party_involvement` views or they bypass RLS. Start the SOC 2 clock here |
| **v2** | Global registry + entity resolution, `clearance_threads`/`thread_members` cross-tenant objects, guest magic links + email bridge | **~10–16 eng-wks** | The network-effect layer; guests promote to orgs — the growth loop |

Compliance, cheapest first: SSO via WorkOS (1–2 wk) < audit logs (2–4 wk — also a product feature) < NDA/unreleased-works controls (2–4 wk) < **SOC 2 Type II (4–9 months elapsed, ~$30–65k — even Tier A indies will ask within 12 months)** < data residency (defer; v0 deploys satisfy it trivially).

---

## 6. LOI-39's open product questions — answered by this discovery

1. **Internal team only, or external rights-holders in-product?** → Both, staged: internal-first, with external rights-holders acting via the **email bridge and zero-login magic links** (v1) — never full accounts. Cross-tenant in-product threads are v2. This unblocks LOI-39 Cut B without waiting for LOI-5's full build.
2. **System of record or tracker alongside email?** → **A tracker that absorbs email** and becomes the system of record *for clearance status only* — never for splits, which stay canonical in the ERP with visible provenance/"as-of" timestamps in Loist (clearance on stale splits is a legal error, not a UX bug).
3. **What is a "use case"?** → **The sync brief** (project-typed), carrying media/term/territory/budget as typed fields. Ad spot = the brief's terms; client project = Initiative/counterparty account; pitch = a task type inside a brief.
4. **v1 fee/master/trigger/MFN?** → Fees yes, as a structured quote object (asked/offered/agreed + MFN *flag*). Master ownership: per-task counterparty in v1; a `recording_rights` table when structured master data proves needed (and add an `isrc` column to `audio_tracks`). Task creation: manual + fan-out from splits, playlist-triggered later. MFN: link and flag coupled tasks; humans do the math.

---

## 7. Consolidated top risks

1. **TAM ceiling** (~4–9k seats worldwide) — accept vertical-SaaS economics; the network layer and agentic layer are the only routes past it.
2. **Spreadsheet gravity / counterparty non-adoption** — email-in ingestion and zero-login external actions are *launch-blocking*, not nice-to-haves; measure counterparty response rates obsessively.
3. **Internal/external leak in the email bridge** — the bridge is the v1 product and its riskiest component; default-internal compose, persistent tinting, send previews.
4. **System-of-record trap** — never own splits truth; import read-only, show provenance.
5. **Fast-followers** (Synchtank/DISCO one product decision away) and **M&A freeze** at 4 of the top-10 targets — speed to a reference cohort is the only defense; time outreach to post-close windows.
6. **Enterprise-readiness gap** — no auth/tenancy/SOC 2 today vs. the industry's most sensitive data; the v0→v1→v2 path above is the answer, and SOC 2 must start during v1, not after.

---

## 8. Recommended next steps

1. **Working session (Gareth):** ratify the reframed thesis and the §6 answers; pick the go/kill gate dates.
2. **Promote LOI-39 Cut B** (clearance tasks + quotes/expiry/history, migration slot `014_clearance_schema.sql`) from proposal to committed feature ticket — this discovery removes its product blockers.
3. **Scope LOI-5 as v0+v1** per §5 (v0 deploy templating + OIDC gate ~2–4 wks; v1 pooled tenancy ~8–12 wks) — it is no longer blocked on product discovery.
4. **New tickets:** email-in ingestion (launch-blocking), tokenized split-confirmation links, split-weighted rollup, CWR import, quote object.
5. **First commercial motion:** approach 3 Tier A accounts (suggest Position Music, Third Side Music, Domino) with the paid design-partner offer once v0 auth gate exists.
