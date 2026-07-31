# Loist UX/IA Report — "The Linear of Music"
**Role:** UI/UX Director · **Date:** 2026-07-07 · **Grounding:** `src/schemas/{work,party,publishing}.py` (SplitStatus: proposed/confirmed/disputed/unknown; splits 0–200%; parties; recordings; playlists/waveforms/embeds already shipped)

---

## 0. The core mapping (read this first)

Linear's genius is that its object model is shallow (team → project → issue) and every view is a *saved query over issues*. Loist's mapping:

| Linear concept | Loist concept | Notes |
|---|---|---|
| Workspace | Company (publisher/rights-holder org) | |
| Team | Function: **Sync**, **Copyright**, **A&R** | Teams own default workflows, not data silos |
| Project | **Use-case / brief** ("Nike 30s spot") | Has target date = air/license date |
| Issue | **Clearance task** (one per rights-holder × work × use-case) | The atomic unit. Everything renders as queries over these |
| Sub-issue rollup | **Track clearance rollup** (weighted by share %) | NEW math: rollup is by ownership %, not count |
| Assignee | Internal owner (sync manager) | |
| — (no equivalent) | **Counterparty** (external rights-holder contact) | NEW first-class field; Linear has nothing like it |
| Labels | Territory, media type, term, exclusivity | |
| Cycle | Optional; weekly clearance sprint | Deprioritize for v1 |
| Triage | **Inbox**: inbound briefs + counterparty replies | Email-bridged |
| Milestone | Brief gates: pitched → quoted → licensed | |

**One rule that keeps this Linear and not Airtable:** the clearance task is the *only* thing users "work." Works, splits, and tracks are reference data rendered inside tasks; briefs are containers. Never make the user edit a grid.

---

## 1. Information architecture

### 1.1 Sidebar / workspace shell

```
┌──────────────────────────────────────────────────────────────────────┐
│ ◈ Meridian Music ▾            [⌘K]                    🔔 Inbox (3)   │
├──────────────┬───────────────────────────────────────────────────────┤
│ Inbox      3 │                                                       │
│ My Day    12 │                                                       │
│ ──────────── │                                                       │
│ ▾ SYNC       │              (content area)                           │
│   Briefs     │                                                       │
│   Clearances │                                                       │
│   Counterpts │                                                       │
│ ▸ COPYRIGHT  │                                                       │
│   Works      │                                                       │
│   Splits ⚠ 4 │                                                       │
│ ▸ A&R        │                                                       │
│ ──────────── │                                                       │
│ Library  ♫   │  ← existing audio library/playlists, kept as-is       │
│ Views        │  ← saved queries (Linear custom views)                │
└──────────────┴───────────────────────────────────────────────────────┘
```

- **Teams are lenses, not walls.** A work belongs to the workspace; Copyright's "Splits ⚠" badge counts works with `disputed`/`unknown` splits (these block clearance generation — see §4a). Sync sees the same works read-only.
- **Library** is the existing product (playlists, waveforms, embeds). It becomes the "asset plane"; the new "work plane" (briefs/clearances) references it. Don't merge navigation — a track row anywhere deep-links both ways.
- `⌘K` everywhere; `O` then `B/C/W/T` = open Brief/Clearance/Work/Track (Linear's `O,P`/`O,I` idiom).

### 1.2 Brief (project) view — the money screen

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Nike — "Run Fearless" 30s TVC            ● Quoting     Due: Aug 14 (38d)   │
│ Media: TV+Web · Term: 1yr · Territory: US · Budget: $40–60k all-in         │
├────────────────────────────────────────────────────────────────────────────┤
│ TRACKS (3)                                    Cleared by share │ Tasks     │
│ ▾ ♫ "Golden Hour" — Ava Reyes      ▶ ▁▂▅▇▅▂▁                              │
│     Publishing ████████░░░░░░░░ 50% cleared   │ 2/4 cleared    │           │
│     Master     ████████████████ 100% cleared  │ 1/1 cleared    │           │
│     ├ ◐ Sony ATV (25% pub) — negotiating · quote $12k · @dana   ⏱ 3d      │
│     ├ ◐ Kobalt (25% pub) — requested · sent Jul 2 · no reply    ⏱ 5d      │
│     ├ ● Self-pub (50%) — cleared · $8k · exp Jul 2027                     │
│     └ ● UMG (master 100%) — cleared · $15k                                │
│ ▸ ♫ "Static Bloom" — Nightjar       ▶ ▁▅▇▃▁    ██░░░░░░ 12% · 1/5  ⚠ disputed│
│ ▸ ♫ "Coastline" — R. Okafor         ▶ ▂▃▅▇▂    ░░░░░░░░  0% · 0/3  draft   │
├────────────────────────────────────────────────────────────────────────────┤
│ Board · List · By counterparty · Timeline        [+ Add track]  [Share ▾]  │
└────────────────────────────────────────────────────────────────────────────┘
```

Key decisions:
- Track rows are **collapsible groups of clearance tasks**, with the **split-weighted progress bar** (§2) always visible.
- Inline waveform player on every track row (existing waveform infra). Play with `Space` when row focused; playback continues across navigation (persistent mini-player, bottom-left — the ONE piece of chrome Linear would never have and music demands).
- Two bars per track — **Publishing** and **Master** — because "100% publishing cleared, master pending" is the single most common status a sync manager reports upward.

### 1.3 Clearance task (issue) view

```
┌───────────────────────────────────────────────┬────────────────────────────┐
│ CLR-214 · Sony ATV × "Golden Hour"            │ Status    ◐ Negotiating    │
│ for Nike "Run Fearless"                       │ Owner     @dana            │
│                                               │ Counterparty               │
│ ♫ ▶ ▁▂▅▇▅▂▁▂▅  1:04/3:12   [0:42–1:12 sync ✂]│   ✉ J. Park (Sony ATV)     │
│                                               │   ext · last reply 2d ago  │
│ ┌─ Rights context ─────────────────────────┐  │ Share     25% publishing   │
│ │  "Golden Hour" ownership     ◔ pie       │  │ ┌─ Quote ───────────────┐  │
│ │  ■ Self-pub 50%  ■ SonyATV 25% (this)    │  │ │ Asked   $15,000       │  │
│ │  ■ Kobalt 25% · all splits confirmed ✓   │  │ │ Offered $10,000       │  │
│ └──────────────────────────────────────────┘  │ │ Agreed  —             │  │
│                                               │ │ MFN: yes · pro-rata ✓ │  │
│ THREAD                                        │ └───────────────────────┘  │
│ ✉ J.Park (email) · 2d — "We can do 12 if…"    │ Expiry    — (set on clear) │
│ 💬 @dana (internal) · 2d — holding at 10, MFN │ Use terms TV+Web·US·1yr    │
│ ✉ dana → J.Park · 5d — quote request sent     │ Docs      license_v2.pdf   │
│ [Reply externally ✉]  [Internal note 💬]      │ Activity  created from     │
│                                               │   splits Jul 1 by @dana    │
└───────────────────────────────────────────────┴────────────────────────────┘
```

- **Who/what/share** pinned in the header sentence: `Counterparty × Work for Brief`. The ID (`CLR-214`) keeps Linear's referenceability (`⌘C` copies ID, paste anywhere autolinks).
- **Ownership pie** ("Rights context") shows where this task's slice sits among siblings; sibling slices are clickable → their tasks. Disputed/unknown slices render hatched with ⚠.
- **Thread is dual-channel** (§3): external emails (✉, visible to counterparty) vs internal notes (💬, tinted background, never sent). The compose box defaults to *internal* — safest failure mode.
- **Quote is a structured object** (asked/offered/agreed, currency, MFN flag), not a comment. Money in comments is how deals get lost.
- **Sync region selector** on the waveform (✂ 0:42–1:12): the brief usually clears a *portion*; attach the in/out points to the task so the counterparty's status page plays exactly that snippet.
- Keyboard: `S` status, `A` assign owner, `Q` edit quote, `E` set expiry, `X` select, `⇧⏎` reply externally, `⏎` internal note.

### 1.4 Views over clearance tasks

- **Board by status** (default): columns Draft / Requested / Negotiating / Cleared / Blocked (rejected+expired+withdrawn collapse into Blocked with sub-badges). Cards show counterparty avatar, work title, share chip `25% pub`, quote, days-in-column.
- **By counterparty** (the novel one): swimlanes per rights-holder org. A sync manager negotiates with *Sony ATV as a relationship*, across briefs — "we have 6 open items with Sony, let's bundle the call." Linear has no equivalent; this is a differentiator, promote it to a top-level "Counterparties" page with per-org aggregate (open tasks, total quoted $, median response time).
- **Timeline**: two marker types — brief due dates (hard) and **clearance expiries** (recurring liabilities that outlive the brief). Expiries within 90d get an amber band; this doubles as the re-license pipeline.
- **List**: Linear-style grouped list, sortable by deadline, quote size, staleness (days since counterparty contact — surface this everywhere; staleness is the sync manager's real enemy).

### 1.5 Triage inbox

Everything inbound lands here before it has an owner: forwarded briefs (each workspace gets `briefs@{org}.loist.com`), counterparty email replies that failed to auto-match a task, magic-link status changes (counterparty clicked Accept/Decline), and expiry warnings. Triage actions (keyboard-first, Linear idiom): `⏎` accept→convert to brief/attach to task, `⌫` decline, `M` merge into existing, `A` assign.

---

## 2. The rollup problem

**Rule:** a track is *cleared* only when 100% of publishing share AND 100% of master share have `cleared` tasks. Count-based fractions lie (3/4 tasks done but the missing one holds 70%), so:

**Primitive: the split-weighted clearance bar.** Two stacked bars (publishing, master), segments sized by share %, colored by task status:

```
Publishing  ████████▓▓▓▓░░░░▒▒▒▒   Master  ████████████████████
            └50%───┘└25%┘└─25%┘             └────── 100% ──────┘
             cleared neg.  req'd/            cleared
                           unknown
█ cleared  ▓ negotiating  ░ requested/draft  ▒ unknown-owner gap  ✖ rejected (red)
```

- Segment order: cleared left, blocked right — the bar "fills toward done" like a progress bar but never misstates weight.
- **The gap segment is load-bearing.** If confirmed splits sum to 80%, the remaining 20% renders as a hatched "unattributed" segment. You cannot clear what you can't attribute; the UI must make missing chain-of-title *visible as absence*, not silently show 100% of known holders.
- Hover any segment → popover: counterparty, share, status, quote, last activity, `⏎` to open task.
- **Compressed glyph** for dense lists (My Day, board cards): `◔ 50%·⚠` — donut of cleared share + worst-status icon. Worst-status precedence: rejected > disputed > expired > unknown > negotiating > requested > draft.
- **Partial/blocked language:** never "75% cleared" alone — always "75% cleared · **blocked: Kobalt (25%) rejected**". A single rejection flips the whole track chip to red "Blocked" regardless of percentage, because one rejected share kills the use (subject to re-approach). Roll up track → brief the same way: brief header shows "1 of 3 tracks cleared · 1 blocked".

---

## 3. External counterparties (v1: no external auth)

Counterparty = `party` + contact email + org. Rendered with a distinct treatment everywhere: square avatar + ✉ badge (internal users: round avatars), so "who can see this" is legible at a glance.

**v1 = email bridge + magic-link status page. No accounts, no passwords, no guest seats.**

1. **Email bridge.** Every clearance task gets a routing address (`clr-214+token@mail.loist.com`) as Reply-To on outbound. Inbound replies thread into the task's external channel; attachments (draft licenses!) auto-file into Docs. Unmatched inbound → Triage. This alone beats the status quo (Outlook + Excel) and needs zero counterparty behavior change.
2. **Magic-link status page** (per counterparty per brief, signed URL, expiring, revocable): read-only page showing *only their tasks* — work title, the ✂ snippet player (existing embed/signed-URL infra — already built!), requested terms, current quote, and three buttons: **Approve quote / Counter / Decline**, plus file upload. Actions write back to the task and appear in the thread as "J. Park via status page". No login; the link is the auth. Sensitive numbers (other holders' quotes, budget) never render here — the page is scoped to the recipient's own slice.
3. **Explicitly deferred:** guest workspace membership, counterparty inbox/portal, cross-org federation ("Sony also runs Loist" B2B graph — huge later, not v1).

Internal-vs-external visibility is the #1 trust risk: the compose default is internal, external sends require the ✉-styled button, and external-visible content is persistently tinted. One leaked internal note ("their catalog is worthless, lowball them") ends a customer relationship.

---

## 4. Key flows, end-to-end

### 4a. Create a brief and generate clearance tasks

1. Entry: `⌘K → "New brief"` or `B` on Briefs page, or Triage→convert from a forwarded email (pre-fills title/body; v1.5: LLM-extract media/term/territory as *suggestions the user confirms*, never silent).
2. Brief modal (Linear project-create pattern): name, client, media/term/territory/exclusivity chips, budget range, due date, owner.
3. **Add tracks:** inline search over the Library (`⌘K` scoped). Each added track resolves recording → work → splits.
4. **Generation preview** (the critical screen — never generate blind):
   ```
   "Golden Hour" → 4 tasks
     ✓ Self-pub 50% (auto-clear? ☑ — you own it)     ✓ UMG master 100%
     ✓ Sony ATV 25% → J. Park ✉                      ⚠ Kobalt 25% → no contact on file [add]
   "Static Bloom" → ⚠ splits sum to 80% (20% unknown) — tasks generated for known
     holders; a placeholder "Unattributed 20%" task is created and blocks rollup
   ⚠ "Coastline" → splits DISPUTED → tasks created as draft + work flagged to Copyright team
   ```
   Per-row checkboxes; "auto-clear owned shares" toggle (publishers clearing their own catalog is the happy path — don't make them email themselves).
5. Confirm → tasks created in `draft`, brief opens. Nothing external is sent yet — draft→requested is the explicit "fire the emails" action, per task or bulk (`X` multi-select, `S→Requested`), each send previewable from a per-counterparty template.
- **Empty states:** Briefs page first-run: "Briefs are sync opportunities. Create one, add tracks, and Loist generates a clearance checklist from each song's splits" + [Create sample brief] seeded with demo data. Brief with no tracks: search box front-and-center, "Add a track from your library to see its rights holders." Track with no work/splits: "No ownership data — link a work or add writers/publishers" → inline split editor (Copyright team's job, but don't dead-end Sync).
- **Errors:** track without work → block generation for that track with inline fix link, generate others. Missing contact → task created, send blocked, "add contact" inline. Duplicate (same counterparty×work×use already open in another brief) → warn + link, offer reuse instead of double-asking Sony for the same thing.

### 4b. Work a clearance to cleared (quote + expiry)

1. From My Day/board, `⏎` opens CLR-214 (status `requested`, sent 5d, no reply — staleness badge amber at 5d by default, configurable).
2. Counterparty replies by email → task auto-threads, status auto-suggests `negotiating` (one-key confirm — suggest, don't silently change), Inbox notifies owner.
3. Owner presses `Q` → quote panel: offered $10,000 · USD · MFN ☑ · note. Structured fields; history kept (asked/offered/agreed ladder renders in the sidebar).
4. Negotiate: external replies (`⇧⏎`) and internal notes (`⏎`) interleave in the thread. Counter-offers update the quote object.
5. Agreement: set Agreed $12,000 → `S → Cleared` opens a **clearance confirmation** step (deliberately heavier than a Linear status change — this is a legal event): agreed fee (prefilled), license term start/end → **expiry auto-derived**, territory/media (prefilled from brief, editable for negotiated carve-outs), attach executed license PDF. Doc attach is skippable with a persistent "missing doc" badge — don't block the workflow, but never let the gap be invisible.
6. Post-clear: task locks softly (edits become tracked amendments); track rollup recomputes; if this was the last share → track flips Cleared, brief activity + owner notification "Golden Hour fully cleared 🎉" (the one earned moment of delight); expiry lands on the Timeline and schedules T-90/T-30 reminders into My Day/Inbox.
- **Alt paths:** Decline → `Rejected` requires reason (price/usage/artist objection — structured, feeds analytics) → track chip flips Blocked → owner prompted: counter / replace track on brief / withdraw siblings ("release the other holders?" — courteous and reputation-preserving, one bulk action). Offer lapses → `Expired` via the offer-validity date if set. Brief dies → bulk `Withdrawn` from brief header, optional courtesy email per counterparty.
- **Errors:** cleared-share sum would exceed 100% (double-signed overlapping shares) → hard warning banner on work + Copyright flag. Email bounce → task banner "delivery failed" + status stays `draft`-equivalent visually (red send badge), fix contact inline.

### 4c. "My Day" — sync manager, 40 open clearances

Linear's My Issues, re-ranked by *what moves deals*, not recency. Sections in priority order:

```
MY DAY — Tue Jul 7                                    40 open · 6 need action
■ NEEDS REPLY (3)      counterparty spoke last; you're the bottleneck
   CLR-214 Sony×Golden Hour  ◐ neg  $12k offered   replied 2d ago  [⏎ open]
■ EXPIRING/DUE (4)     offer validity or brief due-date pressure ≤7d
■ GONE QUIET (6)       ≥5d silence, ball in their court     [bulk: nudge ✉]
■ DRAFTS TO SEND (2)   generated but never fired
■ EVERYTHING ELSE (25) collapsed by default, grouped by brief
```

- Triage keys: `⏎` open, `N` send nudge (templated follow-up, thread-aware), `Z` snooze to date (Linear-style; snoozed items leave My Day, return on wake or on counterparty reply — whichever first), `S` status, `Q` quote.
- Each row carries the compressed rollup glyph of its parent *track*, so "is my work the long pole?" is visible without opening anything.
- Header stat is "6 need action", not "40 open" — the anxiety-to-agency conversion. 40 open with 0 needing action is a *good* day and should read like one ("All caught up. 34 waiting on counterparties.").
- **Empty state (first-run):** "Your clearances will appear here, ranked by what needs you. Right now: nothing does." + link to open briefs. **Error state:** email bridge degraded → banner "Inbound email delayed since 09:12 — replies may be missing" (never let them believe silence that's actually an outage).

### First-run experience (workspace-level)
1. Import splits: CWR/CSV upload or connect existing Loist library → works get writers/publishers (Copyright onboarding).
2. Seeded **sample brief** with 2 demo tracks and fake counterparties, safe to poke — teaches board, task view, and rollup bar without sending real email.
3. Checklist card (Linear-style onboarding): Add a work ✓ → Confirm splits → Create a brief → Send first request → Invite a teammate. Email-domain verification gate before any real external send.

---

## 5. Risks & critiques

1. **Linear's minimalism vs legal gravity.** Linear optimizes for fast, reversible state changes; a clearance is slow, contractual, and evidentiary. Mitigation: keep motion Linear-fast *until* `cleared`, then deliberately add ceremony (confirmation step, doc prompt, soft-lock, tracked amendments, immutable per-task audit log — that log is a *feature* for publishers, surface it, don't hide it). If everything is one keystroke, someone will fat-finger `S→Cleared` on a $50k license.
2. **Money is not a label.** Quotes, MFN, currencies, pro-rata math don't fit Linear's chip aesthetic. Resist cramming fees into title text or comments; the structured quote object with history is non-negotiable. Ledger-style rendering (tabular numerals, right-aligned) inside an otherwise Linear-typographic UI.
3. **Documents.** Chain-of-title PDFs, executed licenses, cue sheets — Linear's attachments are an afterthought; here they're the product's legal spine. v1: per-task Docs slot with type tags (license/CoT/invoice) + "missing doc" badges. Don't build a DMS; do build the *absence indicators*.
4. **The email bridge is the product** in v1 — and its riskiest component. Misthreaded replies or a leaked internal note are trust-enders. Budget disproportionate design/eng care here (matching confidence states, "via status page" attribution, tinted internal channel, send-preview).
5. **"Airtable with a music skin" test.** Airtable = user assembles schema + views; nothing is computed, nothing has opinions. Loist's defensible deltas: (a) tasks are *generated from splits*, not typed in; (b) the split-weighted rollup is domain math no grid formula user will maintain; (c) counterparty as first-class social object with cross-brief relationship views; (d) audio as a native citizen (waveform, ✂ sync-region, magic-link snippet player — already built infra); (e) expiry as a living liability on a timeline, i.e., the system knows a "done" task un-dones itself in 2027. If any of these ship half-hearted, the product collapses into a prettier spreadsheet.
6. **Rollup honesty vs data reality.** Real catalogs have 80%-known splits and disputes everywhere. If the bar can't gracefully show "unknown," users will fudge data to make bars green — design the gap/hatched states as first-class, and make Copyright's split-confirmation queue (Splits ⚠ badge) the feeder workflow.
7. **Two-plane confusion.** Library (tracks/playlists) vs Works (rights) is a genuinely hard mental model — recording≠work is the industry's own confusion. Mitigate with relentless cross-linking and one shared track row component (art + waveform + rollup chip) used identically in both planes.
8. **Keyboard-first may not land.** Sync/licensing staff aren't engineers; Linear's ethos works because devs share it. Ship keyboard-first but audit every flow mouse-only; command palette as accelerator, never the only path.
