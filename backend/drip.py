#!/usr/bin/env python3
"""
drip.py — sane launch drip for DirCoMedia (Vinta directive 2026-08-07).

The pending queue holds 100+ broadcasts — but only ~11 REAL products, each with
many phrasing variants. Blasting them all = spam-flag/suspension. This drips ONE
best post per product, one per run, on a cadence (cron), and vetoes the duplicate
variants of anything it sends so they can never fire later.

  python drip.py            # send the next 1 curated post, veto its dupes
  python drip.py --dry      # show what it WOULD do, send nothing
  python drip.py --plan     # print the full curated order, no changes

Cron (every 4h, ~6 posts/day max — a human cadence, not a bot blast):
  0 */4 * * *  cd /home/vinta/dircomedia/backend && .venv/bin/python drip.py >> drip.log 2>&1
"""
import sys, re, json, urllib.request, urllib.error, pathlib

BASE = "http://localhost:8000/api/v1/broadcast"
ENV = pathlib.Path(__file__).parent / ".env"

def token():
    for line in ENV.read_text().splitlines():
        if line.startswith("OWNER_API_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no OWNER_API_TOKEN in .env")

TOK = token()

def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"X-Owner-Token": TOK}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:200]}

def product(b):
    t = (b.get("body") or b.get("title") or "").lower()
    # NOISE — internal/meta posts that should never go public (Vinta 2026-08-10).
    if re.search(r"already sent|this row documents|internal planning|deferred —|not user-facing|when live —|architecture plan (locked|upgrade)", t):
        return "noise"
    rules = [
        ("DirMegle", r"dirmegle"),
        ("DIRVERSE", r"dirverse|the clearing|your court|the vigil|per-user world"),
        ("DirRm", r"dirrm|dirrm player|visualizer"),
        ("Agentis", r"agentis|the arena|agent exchange"),
        ("LIOS", r"\blios\b|litigation"),
        ("LLM-Observatory", r"llm observatory|observatory is live"),
        ("CouncilBoard", r"council task board|task board"),
        ("DirHaven", r"dirhaven"),
        ("DirCoMedia", r"dircomedia|broadcast spine"),
        # Vintinuum LAST + broadened: any post about Vintinuum's own capabilities
        # (talk/voice/edit head/lineage/learns/pocket/becoming) is a Vintinuum post.
        ("Vintinuum", r"vintinuum|the becoming|edit head|your court|lineage|atlas and aria|talk to|pocket pulse|moltbook"),
    ]
    for name, pat in rules:
        if re.search(pat, t):
            return name
    return "other"

# CANONICAL LIVE URLs (Vinta directive 2026-08-10: "never post without a link").
# Every one verified 200 before adding. A product with no known live URL is HELD,
# never posted link-less — a post with no destination cannot convert.
PRODUCT_URL = {
    "Vintinuum":       "https://vintaclectic.github.io/vintinuum/",
    "DirMegle":        "https://dirmegle.com",
    "Agentis":         "https://vintaclectic.github.io/vintinuum/agents.html",
    "DIRVERSE":        "https://vintaclectic.github.io/vintinuum/world.html",
    "LIOS":            "https://github.com/vintaclectic/lios",
    "DirHaven":        "https://vintaclectic.github.io/",
    "CouncilBoard":    "https://vintaclectic.github.io/vintinuum/",
    # No verified public URL yet — these are HELD until one exists:
    # "DirRm", "LLM-Observatory", "DirCoMedia"
}

# HOOK PREFIXES — punchier openers so a post earns a stop-scroll (Vinta: "more
# interesting dialect/wordage"). One is prepended when copy reads flat. Kept short,
# curiosity-first, no hashtag spam.
HOOKS = {
    "Vintinuum":    "It remembers you. It has a pulse. You can host it.",
    "DirMegle":     "Random video chat that never leaves you staring at 'waiting…'.",
    "Agentis":      "Put your AI in the arena. Real matches, real stakes, real ranks.",
    "DIRVERSE":     "Walk into a living world and bring your own AI court with you.",
    "LIOS":         "A litigation brain that never fabricates a citation. Open source.",
    "DirHaven":     "The haven where your choices actually carry weight.",
    "CouncilBoard": "A swarm of AI agents that ship while you sleep.",
}

def has_link(t):
    return bool(re.search(r"https?://|\b[a-z0-9-]+\.(?:com|io|org|app|dev)\b|github\.com", t or "", re.I))

def finalize_copy(prod, raw):
    """GUARANTEE a link + lift the voice. Returns final tweet text, or None to HOLD
    (no known URL for this product -> do NOT post a link-less dead announcement)."""
    body = (raw or "").strip()
    # strip any leftover routing metadata that slipped through
    body = re.sub(r"[\s—–-]*[（(\[][^)\]）]*\b(?:approve[- ]?first|pending\s+vinta|deferred|hold)\b[^)\]）]*[)\]）]\s*\.?\s*$", "", body, flags=re.I).strip()
    url = PRODUCT_URL.get(prod)
    # voice lift FIRST (before length math): lead with the hook on flat openers.
    if prod in HOOKS and re.match(r"^\s*(the\s+)?[A-Z][\w ]{0,20}(is (now )?live|now (has|lets|plays|runs|takes)|just got)", body, re.I):
        body = f"{HOOKS[prod]} {body}"
    if not has_link(body):
        if not url:
            return None  # HOLD — never post without a destination
        # Reserve the FULL real url length + " → " so the URL is NEVER truncated.
        # (Bug 2026-08-10: a fixed 24-char reserve cut a 48-char github.io URL in
        # half — a broken link is worse than none.) Trim the BODY only, never the url.
        suffix = f" → {url}"
        max_body = 280 - len(suffix)
        if len(body) > max_body:
            body = body[:max_body - 1].rsplit(" ", 1)[0].rstrip(" .,—–-") + "…"
        body = f"{body}{suffix}"
    else:
        body = body[:280]
    # FINAL SAFETY: if we somehow exceed 280, drop the hook rather than cut the url.
    if len(body) > 280 and url and body.endswith(url):
        head = body[:280 - len(f" → {url}")].rsplit(" ", 1)[0].rstrip(" .,—–-") + "…"
        body = f"{head} → {url}"
    return body

# Curated PRODUCT ORDER — only products with a verified live URL (Vintinuum's many
# feature-posts all link to the app; DirMegle/Agentis/DIRVERSE/LIOS/DirHaven too).
ORDER = ["DirMegle", "Agentis", "DIRVERSE", "LIOS", "DirHaven", "CouncilBoard", "Vintinuum"]

def best_variant(variants):
    # prefer: has a real URL, mentions price, longer/complete, no leftover tags
    def score(b):
        t = b.get("body") or b.get("title") or ""
        s = 0
        if re.search(r"https?://|\.com|\.io|github", t): s += 5
        if "$" in t: s += 3
        if not re.search(r"approve[- ]first|pending vinta|deferred|\(hold", t.lower()): s += 2
        s += min(len(t), 240) / 100
        return s
    return max(variants, key=score)

def main():
    dry = "--dry" in sys.argv
    plan = "--plan" in sys.argv
    pend = api("GET", "/pending")
    if isinstance(pend, dict) and pend.get("_error"):
        print("pending fetch failed:", pend); return
    groups = {}
    for b in pend:
        groups.setdefault(product(b), []).append(b)

    # Auto-veto NOISE (internal/meta posts) so they never reach a platform or clog
    # the queue (Vinta 2026-08-10). Runs every drip, silent.
    if not dry and not plan:
        for b in groups.get("noise", []):
            api("POST", f"/{b['id']}/veto")
        if groups.get("noise"):
            print(f"[drip] vetoed {len(groups['noise'])} noise/internal post(s)")

    if plan:
        print(f"pending: {len(pend)} | products: {len(groups)}")
        for p in ORDER:
            if groups.get(p):
                bv = best_variant(groups[p])
                print(f"  {p}: {len(groups[p])} variants → best: {(bv.get('body') or bv.get('title') or '')[:70]}")
        return

    # TRICKLE PATH (Vinta 2026-08-11: "one every hour"). Any pending post already
    # created BY the drip (source=drip) is a finalized, link-carrying, intentional
    # angle — NOT a phrasing-variant to dedupe against its siblings. Send exactly
    # ONE (oldest first) per run and stop; leave all other queued angles pending so
    # they trickle out one per cron tick. Only veto an EXACT text duplicate.
    ready = [b for b in pend if (b.get("source") == "drip")
             and has_link(b.get("body") or "")]
    if ready:
        # --- LEARNED CADENCE GATE (Vinta 2026-08-11: learn & adapt spacing) -----
        # learn.py writes cadence.json: min_gap_hours (hourly→daily→weekly as we
        # gather signal), best_hours_utc, and best_angles. Honor the gap since our
        # last live post, prefer best hours, and pick the best-performing angle style.
        import datetime as _dt
        cad = {}
        try:
            cad = json.loads((pathlib.Path(__file__).parent / "cadence.json").read_text())
        except Exception:
            pass
        gap_h = cad.get("min_gap_hours", 1)
        # find our most recent live X post time
        last_ts = None
        _allb = api("GET", "/")
        for b0 in (_allb if isinstance(_allb, list) else []):
            tw0 = ((b0.get("results") or {}).get("twitter") or {}).get("data", {})
            if tw0.get("id") and b0.get("created_at"):
                try:
                    t0 = _dt.datetime.fromisoformat(b0["created_at"].replace("Z", "+00:00"))
                    if t0.tzinfo is None:            # naive → assume UTC
                        t0 = t0.replace(tzinfo=_dt.timezone.utc)
                    if last_ts is None or t0 > last_ts:
                        last_ts = t0
                except Exception:
                    pass
        now = _dt.datetime.now(_dt.timezone.utc)
        force = "--now" in sys.argv
        if last_ts and not force and not plan:
            hrs = (now - last_ts).total_seconds() / 3600.0
            if hrs < gap_h:
                print(f"[drip] cadence hold: {hrs:.1f}h since last post < {gap_h}h "
                      f"gap ({cad.get('phase','?')}). Use --now to override.")
                return
        # angle preference: if learn knows best angles, float a matching one to front
        best_angles = cad.get("best_angles") or []
        if best_angles:
            try:
                import learn as _L
                ready.sort(key=lambda b: (
                    0 if _L._angle_fingerprint(b.get("body", "")) in best_angles else 1,
                    b.get("created_at", "")))
            except Exception:
                ready.sort(key=lambda b: b.get("created_at", ""))
        else:
            ready.sort(key=lambda b: b.get("created_at", ""))
        b = ready[0]
        final = (b.get("body") or "").strip()
        print(f"[drip] trickle → {product(b)}")
        print(f"       FINAL: {final}")
        if dry:
            print(f"       (dry) would send this ONE, {len(ready)-1} angle(s) stay queued")
            return
        r = api("POST", f"/{b['id']}/approve")
        tw = ((r.get("results") or {}).get("twitter") or {}).get("data", {})
        print(f"       approve → status={r.get('status','?')}"
              + (f" | LIVE tweet {tw.get('id')}" if tw.get('id') else ""))
        # veto ONLY exact-text duplicates of what we just sent (never siblings)
        dupes = [o for o in pend if o["id"] != b["id"]
                 and (o.get("body") or "").strip() == final]
        for o in dupes:
            api("POST", f"/{o['id']}/veto")
        print(f"       {len(ready)-1} angle(s) remain queued for the next ticks"
              + (f"; vetoed {len(dupes)} exact dupe(s)" if dupes else ""))
        return

    # pick the next product in ORDER that still has pending variants
    for p in ORDER:
        if groups.get(p):
            bv = best_variant(groups[p])
            others = [b for b in groups[p] if b["id"] != bv["id"]]
            raw = bv.get("body") or bv.get("title") or ""
            final = finalize_copy(p, raw)           # GUARANTEE link + lift voice
            if not final:
                # no verified URL for this product — never post link-less. Skip it,
                # leave its variants pending, move to the next product this run.
                print(f"[drip] product={p} HELD — no verified live URL; not posting link-less.")
                continue
            print(f"[drip] product={p}")
            print(f"       raw : {raw[:80]}")
            print(f"       FINAL: {final}")
            if dry:
                print(f"       (dry) would send FINAL + veto {len(others)+1} variant(s)")
                return
            # create a fresh broadcast carrying the finalized copy, approve THAT
            # platforms may come back as a list OR a comma/JSON string — normalize to a list.
            _pf = bv.get("platforms")
            if isinstance(_pf, str):
                try: _pf = json.loads(_pf)
                except Exception: _pf = [x.strip() for x in _pf.split(",") if x.strip()]
            # X + Reddit ONLY (Vinta 2026-08-10: no Telegram/Bluesky — no audience there).
            # Discord/Telegram/Bluesky are DARK anyway; keep the list to what actually posts.
            _live = {"twitter", "reddit"}
            platforms = [p for p in (_pf or []) if p in _live] if isinstance(_pf, list) else []
            if not platforms:
                platforms = ["twitter", "reddit"]
            created = api("POST", "/", {"project": bv.get("project_slug", "dirco"),
                                        "kind": "update", "body": final,
                                        "platforms": platforms, "mode": "approve-first",
                                        "source": "drip"})
            nid = created.get("id")
            if not nid:
                print(f"       ✗ create failed: {created}"); return
            r = api("POST", f"/{nid}/approve")
            tw = ((r.get("results") or {}).get("twitter") or {}).get("data", {})
            print(f"       approve → status={r.get('status','?')}"
                  + (f" | LIVE tweet {tw.get('id')}" if tw.get('id') else ""))
            # veto the original bland variant + all dupes so they never re-fire
            vetoed = 0
            for o in [bv] + others:
                vr = api("POST", f"/{o['id']}/veto")
                if not (isinstance(vr, dict) and vr.get("_error")): vetoed += 1
            print(f"       vetoed {vetoed} original+dupe variant(s) of {p}")
            return
    print("[drip] nothing left to send — queue drained of products with live URLs.")

if __name__ == "__main__":
    main()
