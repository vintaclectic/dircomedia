#!/usr/bin/env python3
"""
verify_reddit_destination_MWNMNT9.py — the Reddit destination is NEVER guessed.

WHY THIS EXISTS (task MWNMNT9, 2026-11-16)
------------------------------------------
THE ACCOUNTS ARE THE ASSET (DirCoMedia law #3). MEASURED before the fix:

  * `Broadcast` has NO `reddit_subreddit` column, so broadcast_tasks.py's
    `getattr(broadcast, "reddit_subreddit", None)` was ALWAYS "" and the worker
    never passed `subreddits=` to the scheduler.
  * `scheduler._post_reddit` therefore fell into a hardcoded table of LARGE
    THIRD-PARTY subreddits: vintinuum -> ["artificial","singularity"].
  * Net: setting REDDIT_AUTO_SUBREDDITS to a sub Vinta OWNS — the exact action
    the worker's own error message instructs — did not post to that sub. It
    submitted to r/artificial + r/singularity from his `vintaclectic` account.

So the allowlist was read as a BOOLEAN while the destination came from a table
of subs he does not moderate. That is the unsolicited-promo pattern Reddit bans
accounts for, armed by following the code's own advice.

WHAT IS ASSERTED
  A. The unowned-sub fallback table is gone from the source (all 6 literals).
  B. `_post_reddit` FAILS CLOSED with no destination — behaviourally, through
     the real imported method, with a tripwire client proving ZERO submissions.
  C. An explicit destination is honoured EXACTLY and reaches the real client.
  D. The worker's gate resolves the OWNED allowlist as the destination, and
     still holds Reddit when the allowlist is empty.
  E. The `subreddits=` wire exists at the worker's scheduler call site.

No network: the Reddit client is replaced by a recorder, so a submission that
should not happen is COUNTED, not merely absent from a status code.

NEGATIVE CONTROLS (each must ABORT if its anchor drifted — a control that
silently fails to apply reports a near-green tally that reads as "the fix was
unnecessary"):
    --control-fallback   restore the hardcoded unowned-sub table in _post_reddit
    --control-nowire     drop `subreddits=` from the worker's call site
"""
import argparse, ast, asyncio, importlib.util, pathlib, re, sys, types

ROOT = pathlib.Path(__file__).resolve().parents[1]          # .../backend
SCHED = ROOT / "app/services/distribution/scheduler.py"
WORKER = ROOT / "app/workers/broadcast_tasks.py"

ap = argparse.ArgumentParser()
ap.add_argument("--control-fallback", action="store_true")
ap.add_argument("--control-nowire", action="store_true")
A = ap.parse_args()

_p = _f = 0
def ok(label, cond, saw=""):
    global _p, _f
    if cond: _p += 1; print(f"  PASS  {label}" + (f"  [{saw}]" if saw else ""))
    else:    _f += 1; print(f"  FAIL  {label}" + (f"  [saw: {saw}]" if saw else ""))

def die(msg):
    print(f"\nCONTROL ABORTED: {msg}\n"
          "The control's anchor no longer matches the source, so it did not apply.\n"
          "This run's tally is NOT evidence about the fix. Re-point the control.")
    sys.exit(3)

# ── sources, with the control substitutions applied in memory ────────────────
sched_src  = SCHED.read_text(encoding="utf-8")
worker_src = WORKER.read_text(encoding="utf-8")

FALLBACK_TABLE = '''        if not subreddits:
            # Default subreddits per project
            defaults = {
                "dirhaven-rp": ["FiveM", "GrandTheftAutoV"],
                "dirmegle": ["SocialNetworking"],
                "medaled": ["gaming"],
                "agentis": ["artificial", "MachineLearning"],
                "vintinuum": ["artificial", "singularity"],
            }
            subreddits = defaults.get(project_slug, ["test"])
'''

if A.control_fallback:
    # Replace the fail-closed block with the pre-fix guessing table.
    m = re.search(r'\n        if not subreddits:\n(?:.*?\n)*?            \}\n', sched_src)
    if not m: die("could not find the fail-closed `if not subreddits:` block in scheduler.py")
    sched_src = sched_src[:m.start()] + "\n" + FALLBACK_TABLE + sched_src[m.end():]
    if "artificial" not in sched_src: die("fallback control applied but the table is absent")

if A.control_nowire:
    if "subreddits=reddit_targets," not in worker_src:
        die("could not find `subreddits=reddit_targets,` in broadcast_tasks.py")
    worker_src = worker_src.replace("                subreddits=reddit_targets,\n", "")

# ── A. the unowned-sub table is gone from the shipped source ─────────────────
print("A. the hardcoded unowned-subreddit table is gone")
# Only the explanatory comment may mention these names; no CODE may.
code_only = "\n".join(
    "" if re.match(r'^\s*#', ln) else ln for ln in sched_src.splitlines()
)
for sub in ("artificial", "singularity", "MachineLearning", "FiveM",
            "GrandTheftAutoV", "SocialNetworking"):
    ok(f'no code line names r/{sub} as a destination', f'"{sub}"' not in code_only,
       "present in code" if f'"{sub}"' in code_only else "")
ok("the comment still records WHY (so nobody re-adds the table)",
   "artificial" in sched_src, "named in the rationale comment")

# ── load the (possibly control-mutated) scheduler without importing the app ──
# Stub the sibling modules the real file imports, so this stays hermetic.
pkg_names = [
    "app", "app.services", "app.services.distribution",
    "app.services.distribution.platforms", "app.core", "app.models",
]
for n in pkg_names:
    if n not in sys.modules:
        m = types.ModuleType(n); m.__path__ = []; sys.modules[n] = m

class _Boom:
    """Any platform client the scheduler builds but this test must never use."""
    def __init__(self, *a, **k): pass
    def __getattr__(self, k):
        raise AssertionError(f"test touched a real platform client: {k}")
    @classmethod
    async def from_vault(cls, *a, **k): return cls()

# Auto-stub EVERY app.services.distribution.platforms.* module the real file
# imports. Enumerating them by hand rots the day a platform is added (measured:
# the first run of this harness died on a `discord` client nobody mentioned).
# Any attribute resolves to _Boom, which RAISES if the test ever touches it —
# so an accidental real client call is a loud failure, never a silent network hit.
class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"): raise AttributeError(name)
        return _Boom

class _PlatformFinder:
    # find_spec/exec_module, NOT the legacy find_module/load_module pair:
    # Python 3.12 removed the legacy protocol, so a legacy finder is silently
    # ignored and the import fails as if no stub existed (measured on 3.12).
    # Covers every `app.*` submodule the scheduler pulls in (platform
    # clients, content_engine, ...). sys.modules is consulted BEFORE
    # meta_path, so the modules pre-registered above with real contents
    # (app.core.errors's DistributionError, app.core.config's settings)
    # always win over this stub.
    PREFIX = "app."
    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(self.PREFIX): return None
        return importlib.util.spec_from_loader(fullname, self)
    def create_module(self, spec):
        m = _StubModule(spec.name)
        # Every stub is also a PACKAGE (__path__ set), so a deeper import such
        # as app.services.content_engine.youtube_seo resolves through this same
        # finder instead of dying on "is not a package".
        m.__path__ = []
        return m
    def exec_module(self, module): pass

sys.meta_path.insert(0, _PlatformFinder())

_err = types.ModuleType("app.core.errors")
class DistributionError(Exception):
    def __init__(self, msg, platform=""): super().__init__(msg); self.platform = platform
_err.DistributionError = DistributionError
sys.modules.setdefault("app.core.errors", _err)
_cfg = types.ModuleType("app.core.config")
_cfg.settings = types.SimpleNamespace(reddit_auto_subreddits="")
sys.modules.setdefault("app.core.config", _cfg)

spec = importlib.util.spec_from_loader("sched_under_test", loader=None)
sched_mod = importlib.util.module_from_spec(spec)
sched_mod.__dict__["__file__"] = str(SCHED)
sys.modules["sched_under_test"] = sched_mod
try:
    exec(compile(sched_src, str(SCHED), "exec"), sched_mod.__dict__)
except Exception as e:                      # a stubbed import we did not predict
    print(f"  (scheduler import needed another stub: {type(e).__name__}: {e})")
    raise SystemExit(f"cannot load scheduler.py — fix the harness, not the code")

Scheduler = sched_mod.DistributionScheduler

class RedditTripwire:
    """Records every submission attempt. ZERO is the assertion that matters."""
    def __init__(self): self.subs = []
    async def submit_post(self, subreddit, title, text=None, url=None):
        self.subs.append(("post", subreddit)); return {"id": "t3_fake", "sub": subreddit}
    async def submit_video(self, subreddit, title, video_url):
        self.subs.append(("video", subreddit)); return {"id": "t3_fake", "sub": subreddit}

def run_reddit(subreddits, project_slug="vintinuum", media_url=None):
    s = Scheduler.__new__(Scheduler)       # skip __init__: it builds real clients
    tw = RedditTripwire(); s.reddit = tw
    res = asyncio.run(s._post_reddit("body text", media_url, project_slug, subreddits))
    return res, tw

# ── B. fails closed with no destination ─────────────────────────────────────
print("\nB. no destination => Reddit does not post (behavioural)")
res, tw = run_reddit([])
ok("returns an error instead of posting", isinstance(res, dict) and "error" in res,
   str(res)[:120])
ok("ZERO submissions reached the client", len(tw.subs) == 0, f"{len(tw.subs)} submission(s)")
ok("the error says it refuses to guess",
   "error" in res and "guess" in str(res.get("error", "")).lower(), str(res.get("error",""))[:90])
for slug in ("vintinuum", "agentis", "dirhaven-rp", "dirco"):
    res2, tw2 = run_reddit([], project_slug=slug)
    landed = [s for _, s in tw2.subs]
    ok(f'project "{slug}" lands in NO subreddit', landed == [], str(landed))

# ── C. an explicit destination is honoured exactly ──────────────────────────
print("\nC. an explicit destination is honoured exactly")
res, tw = run_reddit(["vintinuum"])
ok("submits to exactly the named sub", [s for _, s in tw.subs] == ["vintinuum"],
   str([s for _, s in tw.subs]))
res, tw = run_reddit(["vintinuum", "dirhaven"])
ok("two named subs both receive it", [s for _, s in tw.subs] == ["vintinuum", "dirhaven"],
   str([s for _, s in tw.subs]))
res, tw = run_reddit(["a", "b", "c", "d"])
ok("still capped at 2 subs per post", len(tw.subs) == 2, f"{len(tw.subs)}")
res, tw = run_reddit(["vintinuum"], media_url="/x/short-square.mp4")
ok("a media post uses the video lane on the named sub",
   [(k, s) for k, s in tw.subs] == [("video", "vintinuum")], str(tw.subs))

# ── D. the worker's gate resolves the OWNED allowlist as the destination ────
# Extract the real gate block from the worker source and execute THAT, so this
# tests the shipped logic rather than a reimplementation of it.
print("\nD. the worker gate resolves the owned allowlist as the destination")
gate = re.search(
    r'(            platforms = list\(broadcast\.platforms or \[\]\)\n(?:.*?\n)*?'
    r'                    reddit_targets = .*?\n)', worker_src)
if not gate:
    if A.control_nowire:
        pass  # the wire control removes the call arg, not the gate
    ok("the gate block is extractable from the worker source", False, "regex missed")
    gate_src = None
else:
    gate_src = "\n".join(ln[12:] for ln in gate.group(1).splitlines())
    ok("the gate block is extractable from the worker source", True)

def run_gate(allowcfg, target=None):
    ns = {
        "broadcast": types.SimpleNamespace(platforms=["twitter", "reddit"]),
        "settings": types.SimpleNamespace(reddit_auto_subreddits=allowcfg),
    }
    if target is not None:
        ns["broadcast"].reddit_subreddit = target
    exec(compile(gate_src, "<worker-gate>", "exec"), ns)
    return ns["platforms"], ns["reddit_skipped"], ns["reddit_targets"]

if gate_src:
    pl, skipped, targets = run_gate("")
    ok("empty allowlist still HOLDS reddit", "reddit" not in pl and skipped, str(pl))
    ok("empty allowlist yields no destination", targets == [], str(targets))

    pl, skipped, targets = run_gate("Vintinuum,DirHaven")
    ok("owned allowlist keeps reddit in the fan-out", "reddit" in pl and not skipped, str(pl))
    ok("owned allowlist IS the destination (lowercased)",
       targets == ["vintinuum", "dirhaven"], str(targets))
    ok("the destination is NOT a third-party sub",
       not ({"artificial", "singularity"} & set(targets)), str(targets))

    pl, skipped, targets = run_gate("Vintinuum,DirHaven", target="DirHaven")
    ok("an explicit on-allowlist target wins", targets == ["dirhaven"], str(targets))
    pl, skipped, targets = run_gate("Vintinuum,DirHaven", target="artificial")
    ok("an off-allowlist target is HELD, never posted",
       "reddit" not in pl and skipped, str(pl))

    # The end-to-end claim: what the worker resolves is what the client receives.
    _, _, targets = run_gate("Vintinuum,DirHaven")
    _, tw = run_reddit(targets)
    ok("worker destination == what the Reddit client actually receives",
       [s for _, s in tw.subs] == ["vintinuum", "dirhaven"], str([s for _, s in tw.subs]))

# ── E. the wire exists at the call site ─────────────────────────────────────
print("\nE. the scheduler call site forwards the destination")
tree = ast.parse(worker_src)
wired = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "post":
            wired.append(sorted(k.arg for k in node.keywords if k.arg))
ok("a scheduler.post(...) call exists in the worker", len(wired) >= 1, str(wired))
ok("it passes subreddits=", any("subreddits" in kw for kw in wired), str(wired))

print(f"\n{_p}/{_p+_f} pass")
sys.exit(0 if _f == 0 else 1)
