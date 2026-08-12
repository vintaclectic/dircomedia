#!/usr/bin/env python3
"""
learn.py — the drip's self-optimizing brain (Vinta directive 2026-08-11:
"space them out ... learn how best they work use stats ... iterate and perfect").

What it does, every run:
  1. Pull public engagement (likes/replies/reposts/quotes/impressions) for every
     tweet the drip has posted, via the X API (twitter.tweet_metrics).
  2. Score each POST and roll those scores up by (a) posting HOUR-of-day and
     (b) ANGLE fingerprint, so we learn *what* lands and *when*.
  3. Write cadence.json — an adaptive spacing the drip obeys:
       - cold start / no signal yet   → post often (hourly) to gather data fast
       - once we have signal           → widen toward the best-performing rhythm
         (daily / few-days / weekly) and prefer the best hours + best angle styles
  4. Persist a per-tweet stats table (learn_stats.json) so trends compound.

This never posts anything. It only observes and tunes. The drip (drip.py) reads
cadence.json to decide "is it time to post, and if so favor which hour/angle?"

  python learn.py           # pull stats, update scores + cadence
  python learn.py --report  # human-readable: best hours, best angles, current cadence
"""
import sys, json, time, math, asyncio, pathlib, re
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).parent
STATS = HERE / "learn_stats.json"
CADENCE = HERE / "cadence.json"

sys.path.insert(0, str(HERE))
import drip  # reuse its api() + token


def _load(p, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _posted_tweets():
    """Every broadcast that produced a live X tweet id → (tweet_id, body, ts)."""
    allb = drip.api("GET", "/")
    if not isinstance(allb, list):
        return []
    out = []
    for b in allb:
        tw = ((b.get("results") or {}).get("twitter") or {}).get("data", {})
        tid = tw.get("id")
        if tid:
            out.append((str(tid), b.get("body") or tw.get("text") or "",
                        b.get("created_at") or ""))
    return out


def _angle_fingerprint(text: str) -> str:
    """Cheap style bucket so we learn which KINDS of hooks work, not just exact
    strings. Buckets by opening device."""
    t = (text or "").lower()
    if t.startswith("omegle") or "sequel" in t or "god of all" in t:
        return "sequel/legacy-hook"
    if t.startswith(("remember", "you miss", "admit it")):
        return "nostalgia-hook"
    if t.startswith(("one click", "bored", "50k", "50,000")):
        return "instant/proof-hook"
    if "?" in t[:40]:
        return "question-hook"
    return "other"


def _engagement_score(m: dict) -> float:
    """Weighted engagement. Replies+reposts (active) > likes (passive). Normalize
    by impressions when we have them so a small-but-punchy post isn't buried."""
    active = 3 * m.get("reply_count", 0) + 3 * m.get("retweet_count", 0) + 2 * m.get("quote_count", 0)
    passive = m.get("like_count", 0)
    raw = active + passive
    imp = m.get("impression_count", 0)
    if imp and imp > 0:
        return raw + 8.0 * (raw / imp)  # engagement-rate bonus
    return float(raw)


async def _fetch_metrics(ids):
    from app.services.distribution.platforms.twitter import TwitterClient
    return await TwitterClient().tweet_metrics(ids)


def run(report=False):
    posted = _posted_tweets()
    stats = _load(STATS, {"tweets": {}, "updated": 0})
    cadence = _load(CADENCE, {})

    ids = [tid for tid, _, _ in posted]
    metrics = {}
    if ids:
        try:
            metrics = asyncio.run(_fetch_metrics(ids))
        except Exception as e:
            print(f"[learn] metric fetch failed ({e}); using last-known stats")

    # merge fresh metrics into the persistent table
    by_hour, by_angle = {}, {}
    for tid, body, ts in posted:
        m = metrics.get(tid)
        rec = stats["tweets"].get(tid, {"body": body[:120], "first_seen": ts})
        if m:
            rec.update(m)
            rec["score"] = _engagement_score(m)
        stats["tweets"][tid] = rec
        score = rec.get("score", 0.0)
        # hour bucket (UTC hour the tweet went out)
        hr = None
        cre = rec.get("created_at") or ts
        try:
            hr = datetime.fromisoformat(cre.replace("Z", "+00:00")).astimezone(timezone.utc).hour
        except Exception:
            pass
        if hr is not None:
            by_hour.setdefault(hr, []).append(score)
        by_angle.setdefault(_angle_fingerprint(body), []).append(score)

    def avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    hour_rank = sorted(((h, avg(v), len(v)) for h, v in by_hour.items()),
                       key=lambda x: x[1], reverse=True)
    angle_rank = sorted(((a, avg(v), len(v)) for a, v in by_angle.items()),
                        key=lambda x: x[1], reverse=True)

    # ---- adaptive cadence -------------------------------------------------
    total_posts = len(ids)
    total_signal = sum(t.get("score", 0) for t in stats["tweets"].values())
    # Cold start: <8 posts OR ~no engagement yet → post OFTEN to gather data.
    # Warming: some data → widen to daily. Mature + real signal → widen to weekly
    # but keep a floor so the account never goes silent.
    if total_posts < 8 or total_signal < 3:
        min_gap_hours, phase = 1, "gather (hourly — building signal)"
    elif total_posts < 20 or total_signal < 30:
        min_gap_hours, phase = 24, "tune (daily — early signal)"
    else:
        min_gap_hours, phase = 72, "sustain (every ~3 days — favor best hours/angles)"

    best_hours = [h for h, _, _ in hour_rank[:4]] or list(range(13, 23))  # default US-active
    best_angles = [a for a, s, n in angle_rank if n >= 1][:3]

    cadence = {
        "min_gap_hours": min_gap_hours,
        "phase": phase,
        "best_hours_utc": best_hours,
        "best_angles": best_angles,
        "total_posts": total_posts,
        "total_signal": round(total_signal, 2),
        "updated": int(time.time()),
    }
    stats["updated"] = int(time.time())
    STATS.write_text(json.dumps(stats, indent=2))
    CADENCE.write_text(json.dumps(cadence, indent=2))

    if report or "--report" in sys.argv:
        print("=== DRIP LEARNING REPORT ===")
        print(f"posts with live tweet: {total_posts} | total engagement signal: {total_signal:.1f}")
        print(f"CADENCE → {phase}  (min gap {min_gap_hours}h)")
        print(f"best hours (UTC): {best_hours}")
        print("angle performance:")
        for a, s, n in angle_rank:
            print(f"   {a:22} avg {s:6.2f}  (n={n})")
        print("top tweets:")
        top = sorted(stats["tweets"].values(), key=lambda t: t.get("score", 0), reverse=True)[:5]
        for t in top:
            print(f"   {t.get('score',0):6.1f}  {t.get('body','')[:70]}")
    else:
        print(f"[learn] {phase} | posts={total_posts} signal={total_signal:.1f} "
              f"| best_hours={best_hours} | best_angles={best_angles}")
    return cadence


if __name__ == "__main__":
    run(report="--report" in sys.argv)
