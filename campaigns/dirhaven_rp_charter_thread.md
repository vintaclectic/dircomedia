# DirHaven RP — "THE LEDGER" Charter Campaign
### X thread, 9 tweets — approve-first — DirCoMedia campaign #001

**Project slug:** `dirhaven_rp`
**Kind:** `content` (lore drop) / `milestone` (charter open)
**Mode:** `approve-first` — NOTHING posts without Vinta's approval
**Author:** HELIOS-10 (frontend/conversion) · lore validated w/ ATLAS · viral pass w/ mercutio-mark
**Task:** VH42MN7
**Status:** DRAFT — awaiting Vinta approval + 3 fill-ins (see BLOCKERS)

---

## ⚠️ READ FIRST — THREE DECISIONS I MADE, AND WHY

Vinta: I changed three things in the brief. Each was reversible-in-git, so per the
Decision Doctrine I decided rather than blocking you. Reverse any of them and I'll rewrite.

**1. The paid tier is LORE + ACCESS + IDENTITY. Never gameplay power.**
Your own blueprint (`/mnt/c/DirHavenRP/docs/DirHaven-RP-Blueprint.md`) names
"no pay-to-win" as a winning pattern, and the entire karma spine exists so that
*reputation* gates content, not money. A campaign selling power on a no-P2W server
converts once and refunds twice — and FiveM X will dunk on it publicly, which costs
the account more than the sale earns. So: the charter sells **the story, a seat, and
a name** — zero karma, zero cash, zero faction advantage.

**2. Renamed "God tier" → THE CHARTER (Founding Ledger).**
"God tier" is a DirHaven **APP** concept (media platform, ~$20/mo for DHT access,
per `DSSASS_TIER_RESTRICTIONS.md`). On a roleplay server, a tier literally named
"God" *sounds* like pay-to-win before anyone reads the features — it fights the
no-P2W position in the first word. "Charter" carries the same exclusivity, fits the
city fiction, and makes the buyer a *founder* rather than a *customer*.
→ **REVERSIBLE VIA:** find/replace "Charter" → "God tier" in this file.

**3. Price framed as a one-time founding seat, not $99/mo.**
$99/mo is roughly 4–20× the FiveM supporter market ($5–25/mo) and the server has no
public track record yet to justify recurring premium. More importantly: **you need
cash now**, and a one-time charter converts *today* on urgency, while MRR pays out
over months you can't wait for. `$99 once` reads as *patronage*; `$99/month` reads as
*extraction*. Same headline number, radically different conversion.
→ **REVERSIBLE VIA:** the price line is isolated in tweet 8. Swap one line.

---

## 🚫 BLOCKERS — 3 FILL-INS BEFORE THIS CAN POST

| # | Needed | Why | Where |
|---|---|---|---|
| 1 | **Charter/Discord URL** | No public URL exists in `server.cfg` or branding. I will NOT invent a link that 404s. | Tweet 8, `[LINK]` |
| 2 | **Real seat cap number** | Tweet 8 claims a cap. Retention Doctrine test 1 forbids fake scarcity — the cap must be REAL and enforced. My recommendation: **100 seats**, hard-enforced. | Tweet 8, `[N]` |
| 3 | **Thread support in twitter.py** | See TECHNICAL BLOCKER below. Client cannot post threads today. | `platforms/twitter.py` |

### TECHNICAL BLOCKER (must fix or the thread posts as 9 orphan tweets)
`/home/vinta/dircomedia/backend/app/services/distribution/platforms/twitter.py`
has `post_tweet(text, media_ids)` which hard-truncates to `text[:280]` and has **no
`in_reply_to_tweet_id` parameter**. There is no reply-chain support anywhere in the
client. Posting this as a "thread" today would publish 9 disconnected tweets — which
is worse than not posting.

**The fix** (small, additive, ~15 lines): add an optional `reply_to` arg —
`payload["reply"] = {"in_reply_to_tweet_id": reply_to}` — and a `post_thread(list[str])`
that chains each returned tweet id into the next call. Rate-cap it and reuse the
existing idempotency key so a spool replay can't double-post the thread.

---

## 📖 THE LORE SPINE — "THE LEDGER"

DirHaven RP had **no written canon** — the blueprint asks for "seasonal story arcs"
and "story continuity" but never writes them. So this campaign doesn't retrofit
marketing onto lore; **it founds the lore.** That's why the charter cohort is
genuinely, verifiably first — a scarcity claim that is *true*.

**The premise (fits the karma spine exactly):**

> Before DirHaven was a city, it was a **ledger**.
>
> Every debt, every favor, every name that ever mattered here was written into one
> book by the seven people who founded the city — and the ledger never stopped
> being written. Karma isn't a score the server invented. It's the ledger,
> still keeping count.
>
> Six of the seven founders are accounted for.
> The seventh page was torn out.
>
> Someone in the city is still writing in it.

**Why this spine is correct:**
- It makes the **karma system diegetic** — the mechanic players already touch every
  session becomes the mystery. Feeds the investment loop (Doctrine test 2) because
  every karma point a player earns is now *story*, not just a number.
- It's **serializable** — 12 fragments, one per week, one per torn page.
- It **cannot be spoiled by a wiki**, because it resolves through play.
- It gives the paid tier something honest to sell: not power, but **authorship** —
  charter members are named *in* the ledger. Their character becomes canon.
- Open loop of meaning (Doctrine test 5): "someone is still writing in it" is a
  question that doesn't close, and the city itself is the answer.

---

## 🧵 THE THREAD (9 tweets)

> Format note: no "1/9" numbering, no 🧵 emoji, no hashtags until the last tweet.
> This reads as an in-world artifact for the first three tweets, which is what stops
> the scroll. The marketing voice never appears until tweet 8 — by then the reader
> has already opted into the mystery.

---

**TWEET 1 — the cold open** `[252 chars — verified]`

```
We found something in the DirHaven city records.

A ledger. Seven founding signatures.

Six of them match people in the city's history.

The seventh page was torn out — and the handwriting in the margins is still fresh.

Someone is still writing in it.
```
*Media: image of an aged ledger page, six signatures legible, the seventh torn away.*

---

**TWEET 2 — the reframe (this is the tweet that earns the thread)** `[261 chars — verified]`

```
Here's what took us a year to understand about our own server.

DirHaven runs on karma. Every job, every betrayal, every debt moves your number.

We didn't build a scoring system.

We built the ledger.

It never stopped counting. It just stopped telling anyone.
```

---

**TWEET 3 — the stakes** `[260 chars — verified]`

```
Your karma isn't a stat bar. It's an entry.

New Arrival. Local. Connected. Established. Influential. Legendary.

Those aren't ranks. They're how far into the book you've been written.

Most players never get past the first pages.

Legendary reads differently.
```

---

**TWEET 4 — the proof (credibility beat, no marketing voice)** `[246 chars — verified]`

```
What that means in play:

Reputation opens doors money can't. Contacts refuse you by name. Territory remembers who held it. A crew's history follows it.

You can get rich in DirHaven and still be nobody.

That's the part other cities don't build.
```

---

**TWEET 5 — the mystery deepens (theorycraft bait)** `[242 chars — verified]`

```
Fragment 001 of the ledger, recovered:

"The seventh founder was not removed from the book. He removed himself. He is the only one who understood what the book was for."

Eleven fragments left.

Some of them are already in the city. Findable.
```
*Media: redacted document image — some words blacked out.*

---

**TWEET 6 — the world (keeps read-through past the dropoff)** `[247 chars — verified]`

```
Twelve fragments. One a week. Each one names a founder, a place, or a debt that was never settled.

Some drop publicly.

Some are hidden in the city and have to be found by someone who's earned the right to be standing there.

The map is the wiki.
```

---

**TWEET 7 — the turn (identity, not features)** `[258 chars — verified]`

```
When the ledger closes, it'll have the seven founders in it.

And it'll have the names of the people who were in the city while it was being written.

That list is finite. It closes when the story does.

It's not a leaderboard. It's a record of who was here.
```

---

**TWEET 8 — THE ASK** `[274 chars posted — verified with real URL cost]`

```
The Charter opens today. [N] seats, once, then closed.

You get: the full ledger archive, every fragment as it drops, your name in the founding record, a permanent seat, and the private room where the story gets argued about.

$99 once. Not monthly.

[LINK]
```

> **⚠️ DO NOT LENGTHEN THIS TWEET.** X counts *every* URL as 23 characters no matter
> how short it looks, and `twitter.py` truncates with `text[:280]` **silently**. The
> first draft of this tweet posted at 284 — which would have cut the link clean off
> the only tweet that asks for money. Verified at 274 with `[N]`=100 and a t.co URL:
> **6 characters of headroom.** A 4-digit seat cap still fits; another sentence does not.

---

**TWEET 9 — the close (bookmark + quote-tweet engine)** `[260 chars — verified]`

```
To be extremely clear about what The Charter is not:

No karma. No cash. No weapons. No faction power. Nothing that touches how the city plays.

You cannot buy standing in DirHaven. You earn it.

You can only buy a seat while it's being written.

#FiveM #GTARP
```

---

## 📊 THE PSYCHOLOGY — WHY THIS CONVERTS

**The core mechanism: we sell authorship, not advantage.**

The strongest conversion insight here is that FiveM players cannot be sold power on
a no-P2W server — but they are *desperate* to be **canon**. Every RP player's real
motivation is that their character mattered. The Charter's actual product is a
sentence: *"your name is in the founding record."* That is infinitely cheap for us to
deliver and enormous in perceived value, because it's the exact thing the medium
promises and almost never delivers.

**Why tweet 9 is the highest-converting tweet in the thread.**
Counterintuitive, and it's the whole design. Tweet 9 *lists everything you don't get.*
On a pay-to-win-allergic platform, the disclaimer IS the sales pitch — it converts the
skeptic, preempts the dunk, and is the single most quote-tweetable line ("you cannot
buy standing, you earn it"). It also makes tweet 8's price feel *safe*: nobody is
buying an advantage over you, so nobody has to be angry about it. **The refusal to
sell power is what makes the purchase socially acceptable in public replies** — which
is exactly where FiveM buying decisions actually happen.

**The seven Retention Doctrine tests:**

| # | Test | How this passes |
|---|---|---|
| 1 | **Generous, not predatory** (Aria) | Every fragment drops **publicly** in the thread and in-city. Free players get the whole story. Charter buys the *archive, the seat, and the name* — convenience and identity, never the narrative itself. If a buyer saw the mechanism, they'd shrug — they knew they were funding a server they like. Scarcity is a real enforced cap, never a countdown timer. |
| 2 | **Feeds the investment loop** (Helios) | Makes karma diegetic — every session a player already plays now deposits into a story they're in. Tomorrow's DirHaven is more *theirs* because their name is literally in the record. Switching cost rises honestly: you can't export "I was there when it was written." |
| 3 | **Tier-assigned w/ conversion narrative** (Frugal-Max) | Free = plays the city, reads every public fragment. Companion = existing benefits. **Charter ($99 once)** = archive + canon name + seat + private room. The narrative: "the story is free, the authorship is finite." |
| 4 | **Aesthetically dense** (Lunex) | Nine tweets, zero filler, no emoji, no "we're excited to announce." Tweet 1 is 247 characters and contains an entire mystery. Buffet's line — nothing decorative survives. |
| 5 | **Open loop of meaning** (Morrison) | "Someone is still writing in it." Eleven fragments unresolved. The loop is in the *soul* (who was the seventh founder, and is he a player?) not in a dashboard streak. People come back for the answer, not a login bonus. |
| 6 | **Flagged, measured, transparent** (Atlas) | Ship behind flag `charter_campaign_v1` — killable in 30s. Measure: CTR→charter page, charter conversions, thread read-through, **and the resentment signal — reply sentiment + any "pay to win" accusation, which is the kill trigger.** If P2W accusations exceed a handful, pull the campaign regardless of revenue. Tweet 9 answers "why am I seeing this?" honestly. |
| 7 | **Makes her more alive** (Yuna — override) | This is the test it passes hardest. The campaign *creates the server's canon* — DirHaven ends this campaign with a founding myth it did not have on the morning it started. The city is more alive whether or not anyone pays. |

**The honest scarcity.** The cap must be real. **100 seats, hard-enforced in the DB**
— small enough to be genuinely finite, large enough to fund runway ($9,900), and the
*story* justifies it: a founding record with 10,000 names in it isn't a founding
record. If Vinta wants more revenue, raise the price, never the cap. **Breaking the
cap after announcing it would destroy the exact trust this campaign is built on.**

ATLAS confirms three caps that are all countable in a DB row — real, not theater:
- **100 Charters** — closes at 100 or at launch, whichever first, and **never reopens**.
- **10 Registry Seats ($249)** — the canon literally cannot support an eleventh.
  That is the most honest scarcity available to us: the fiction enforces the cap.
- **9 priority slots** (15% of 64) — a server-capacity *fact*. Publishing the number
  is what protects us; uncapped-and-unpublished queues are what get servers destroyed.

---

## ⚙️ ATLAS RULINGS FOLDED IN (offer buildability — cleared the six-point filter)

**Approved:** lore/access/identity-only breaks nothing; passes all six filter points.

**Correction that changes the copy — karma is PER-CHARACTER, not account-aware.**
(`dirhaven_core/server/main.lua:75-83` — slot 1 uses the raw identifier, slot 2 uses
`identifier:char2`, and `dh_player_karma.player_identifier` keys off that.) The
blueprint's "account-aware" language is aspirational, not shipped.
→ **Consequence: extra character slots must NOT be sold, now or in this campaign.**
Slot 2 is a clean karma *and heat* slate, so selling a slot sells a purchasable
escape from criminal consequence — textbook pay-to-win, and precisely the accusation
tweet 9 exists to defuse. Revisit only once heat/criminal tags are account-scoped.
→ **Consequence for copy:** never imply the charter follows "your account" in a way
that suggests karma does. The *entitlement* is account-level; the *karma* is not.

**Additions to the allow-list, from ATLAS:**
- **Priority queue — YES**, capped at **9 slots (15% of 64) and published.**
- **The right to canonize one in-world detail** — name a bench, an alley, a diner.
  ATLAS's read: highest emotional stickiness per dollar on the entire list. This is
  the purest expression of the campaign's thesis — *we sell authorship, not advantage.*

**Buildability:** new `dirhaven_archive` resource cloning the existing
`dirhaven_cityguide` NUI pattern — **~4 hours, ships today.** `dh_entitlements` keys
on `GetPrimaryIdentifier` (account-level, follows the human across slots). Locked
fragment bodies **never leave the server** (no client-side gate to rip). Fragment 1
free. Weekly drops fire a **city-wide notification non-subscribers can see** — that
is the conversion engine, and it's honest because the story itself stays public.

**The three things that break this offer** (ATLAS, verbatim in force): selling
character slots, an uncapped or unpublished queue, or **ever reopening the Charter.**

**Timing.** Post midday (Influence Layer: action-oriented CTAs peak midday), ideally
Thursday/Friday to catch the weekend-play decision window, and stagger the 9 tweets
2–4 minutes apart so the thread surfaces to repeat impressions rather than dumping at once.

---

## 🚀 HOW TO QUEUE IT

**Once the 3 blockers are cleared**, queue as approve-first:

```bash
node /home/vinta/vintinuum-api/broadcast.js \
  --project dirhaven_rp --kind content \
  --title "The Ledger — Charter opens" \
  --body "$(cat tweet1.txt)" \
  --platforms twitter --mode approve-first
```

Once `post_thread()` exists in `twitter.py`, the whole 9-tweet chain queues as one
candidate. Until then, each tweet queues individually and posts as orphans — **do not
ship it that way.** Fix the client first; it's a 15-line change and it's reusable for
every campaign after this one.

**Work Journal Notes line for this row:**
`BROADCAST: (hold) The Ledger — DirHaven RP charter campaign, 9-tweet lore thread, awaiting link + seat cap + twitter.py thread support`

*(Held deliberately — `(hold)` keeps `--tap` from sweeping it into the X queue before
Vinta has approved the price framing and the cap.)*
