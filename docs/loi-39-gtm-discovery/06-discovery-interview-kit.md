# Customer Discovery Interview Kit — Sync Clearance Workflow

Purpose: validate the ratified thesis (Loist as the clearance & rights-workflow system for publishers, agent-layer emphasis) with **5–10 real conversations** before any build commitment. These interviews test the five simulated reports against reality — treat every report claim as a hypothesis until a sync manager confirms it.

**These are research conversations, not sales calls.** Rule of thumb (Mom Test): ask about *what they did last time*, never *whether they'd use your idea*. No pitching until the final two minutes, and only if asked.

---

## 1. Who to talk to

**Target title:** Sync Licensing Manager, Head of Sync, Director of Licensing, Licensing Coordinator — the person who personally chases clearances. Secondary: Head of Copyright (split confirmation angle), A&R coordinator (holds/split sheets).

**Where they work (pull from the Tier A list, [03-sales-gtm.md](03-sales-gtm.md) §2):** Position Music, Third Side Music, Domino Publishing, Secretly Group, Beggars Group, Ninja Tune, Warp, Partisan, Mom+Pop, Sub Pop, peermusic, Wixen — plus any UK indie via MPA/AIMP/IMPF orbits. 2–3 interviews at boutique sync agencies also count (highest clearance volume per head).

**Sourcing routes, in order of yield:**
1. Warm intros through any existing music-industry contacts ("who do you know who does sync licensing at a publisher?").
2. AIMP chapter events (LA/NY/Nashville — monthly, open) and IMPF for European indies.
3. LinkedIn: the target titles at the named accounts (~300–400 people exist); personalize to a real placement.
4. The Catalog-marketplace cohort (Beggars, Domino, Ninja Tune, Warp, Partisan) — sync-progressive, talk to each other; one good interview refers the next.

**Outreach template (LinkedIn/email, ≤90 words):**
> Subject: research on sync clearance workflow — 25 min?
>
> Hi {name} — I'm researching how sync teams at independent publishers actually track clearances (the who's-cleared-what-by-when problem), because I'm building tooling in this space and don't want to build the wrong thing. Not selling anything — I'd genuinely like 25 minutes to hear how {company} runs a clearance from brief to license. Happy to share back what I learn across the ~10 teams I'm speaking with. Would next week work?

The "share back what I learn" offer matters — it's the seed of the "State of Sync Ops" benchmark report and a reason for busy people to say yes.

---

## 2. The script (25–30 min)

### Warm-up (2 min)
- Role, team size, how long in sync, roughly how many active briefs/clearances at once.

### The core: reconstruct the last clearance (10 min — the heart of the interview)
- "Walk me through the **last** track you cleared — from the moment the request landed to signature. Blow by blow."
- Probe: How did the request arrive? (email? DISCO? phone?) How did you find out who owns the song? Where did you record what was happening? How many parties had to say yes? How long did each take to respond? What was the fee ballpark and who negotiated it?
- **The artifact ask:** "Where does the status live while that's happening — could you show me / describe the tracker?" (If they screen-share an Excel clearance grid, photograph the moment — that grid is the product spec.)

### Pain mapping (5 min)
- "What's the worst clearance you've had in the last year? What made it bad?"
- "Has a quote or hold ever expired without anyone noticing? What happened?"
- "How do you find out a song's splits aren't confirmed — and when in the deal do you find out?" (Thesis test: discovery says this surfaces at contract time and should surface at pitch time.)
- "When your boss asks 'where are we on X?' — how do you answer?"
- "What happens when you're on holiday?"

### Counterparty behavior (4 min — tests the moat primitive)
- "When you need a co-publisher or writer to confirm something, how do you ask, and how do they answer?"
- "If they got a link — no login — showing just their item with Approve / Counter / Decline, would they click it? Would *you*, if another publisher sent you one?" (Watch for hesitation; this is the magic-link hypothesis.)

### Tooling & money (4 min)
- "What do you use today — and what have you tried and abandoned?" (Listen for: Airtable/Monday attempts, Synchtank, DISCO, Vistex/Counterpoint read-only, homegrown.)
- "Who decides on new software here, and what did the last purchase look like?"
- "If a tool cut a week off your average clearance, what would that be worth?" (Don't suggest a number.)

### Agent appetite (3 min — tests the ratified agent-layer emphasis)
- "Imagine an assistant that drafted the chase emails, kept the tracker updated from replies automatically, and flagged what needs you today — nothing sent without your approval. What's your reaction?" (Gauge: delight vs. trust concerns vs. 'my emails ARE the job'.)
- "What would you never let it do on its own?"

### Wrap (2 min)
- "What should I have asked that I didn't?"
- **"Who else runs clearances like you do — could you introduce me?"** (Every interview must end with this; referral rate is itself a signal.)
- Only if they ask what you're building: one sentence — "a system that turns each brief into a tracked clearance checklist generated from the song's actual splits, with counterparties responding by email or one-click links."

---

## 3. What counts as evidence (score each interview)

| Signal | Validates | Strong signal looks like |
|---|---|---|
| They show/describe a real Excel clearance grid | The core pain + product shape | Screen-share, visible column chaos, "everyone has one of these" |
| A specific expired-quote or missed-deadline story with a cost | Time-as-actor primitive | Named deal, named consequence |
| Splits problems discovered mid-deal | Auto-fan-out from splits (the moat feature) | "We found a third co-publisher after we quoted" |
| They'd click / send a no-login approve link | Counterparty primitive | Unprompted "god yes" vs. polite "maybe" |
| Abandoned Airtable/Monday attempt | Whitespace between ERP and email | "We set one up, it was stale in a month" |
| Positive agent reaction with clear guardrails | Agent-layer emphasis | They name the tasks they'd delegate first |
| Unprompted "what would this cost?" or an intro given | Willingness to pay / referral loop | They introduce you before you ask |

**Thresholds (pre-committed, per the go/kill gates):** if after 8–10 interviews fewer than half show the Excel-grid pain firsthand, or the counterparty-link reaction is consistently lukewarm, the thesis needs revision before Cut B is built. If 3+ interviews end with "can I try it?", that's the design-partner pipeline starting itself.

## 4. Log template (one per interview, keep in this directory as `interviews/NN-company.md`)

```
Company / role / date / how sourced:
Team size, briefs in flight:
Last-clearance walkthrough (verbatim highlights):
Where state lives today:
Worst-clearance story:
Counterparty-link reaction (verbatim):
Tooling tried/abandoned:
Buying process / budget signals:
Agent reaction + guardrails they named:
Referrals given:
Score vs. evidence table (which rows hit):
Surprises / thesis contradictions:
```
