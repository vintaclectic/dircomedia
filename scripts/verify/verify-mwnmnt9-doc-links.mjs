#!/usr/bin/env node
/**
 * verify-mwnmnt9-doc-links.mjs — every path cited in the MWNMNT9 docs OPENS.
 *
 * WHY (task MWNMNT9, Lord Vinta 2026-09-21):
 *   "links to local review page and delivery zip are not working in council task
 *    board md files seen here, please fix and let me know when i can review the
 *    exports."
 *
 * MEASURED on the live board 2026-11-16, which is exactly why they failed:
 *   - the old doc used RELATIVE targets (`MWNMNT9-media/index.html`). The board's
 *     md() resolves those via absOf() against the open doc's dir, so the shape was
 *     survivable — but the two targets it pointed at are not servable:
 *   - `.html`  -> /api/file returns kind:"text" and prints HTML SOURCE. The board
 *                 deliberately never RENDERS html (stored-XSS lane; `html: null`
 *                 is a refusal marker in UP_KINDS). So it can never be a "review page".
 *   - `.zip`   -> /api/file  = 403 "That file type or location is not readable".
 *   - `.mp4`   -> /api/file  = 200 kind:"video" with src=/api/file-at... which
 *                 then serves the bytes 200. These PLAY. They always would have.
 *
 * So this asserts the contract Vinta actually needs: every path the docs tell him
 * to click is one the LIVE board answers 200 for, and no doc presents a
 * known-refused type as a clickable review surface.
 *
 * Hits only 127.0.0.1 (the board already running on state/gui-port). It makes
 * ONE serial request at a time — never a parallel fan-out at a live service
 * (KAXN8NP).
 *
 * NEGATIVE CONTROL (aborts loudly if its input is missing, so a control that did
 * not apply can never read as "the fix was unnecessary"):
 *   --control-olddoc   verify the PRE-FIX doc instead; it must FAIL on the
 *                      index.html and .zip links.
 */
import fs from 'node:fs';
import path from 'node:path';

const ROOT = '/home/vinta/.claude/council-loop';
const DOCS = path.join(ROOT, 'state', 'docs');
const CTL_OLD = process.argv.includes('--control-olddoc');

const DOC_NEW = [
  path.join(DOCS, 'MWNMNT9-video-handoff.md'),
  path.join(DOCS, 'MWNMNT9-reconnect-runbook.md'),
];
const DOC_OLD = [path.join(DOCS, 'MWNMNT9-video-handoff.md.pre-MWNMNT9fix')];
const DOCS_UNDER_TEST = CTL_OLD ? DOC_OLD : DOC_NEW;

let pass = 0, fail = 0;
const ok = (label, cond, saw = '') => {
  if (cond) { pass++; console.log(`  PASS  ${label}${saw ? `  [${saw}]` : ''}`); }
  else { fail++; console.log(`  FAIL  ${label}${saw ? `  [saw: ${saw}]` : ''}`); }
};
const die = (m) => {
  console.log(`\nABORTED: ${m}\nThis run's tally is NOT evidence. Fix the harness input.`);
  process.exit(3);
};

for (const d of DOCS_UNDER_TEST) if (!fs.existsSync(d)) die(`missing doc under test: ${d}`);

const port = fs.readFileSync(path.join(ROOT, 'state', 'gui-port'), 'utf8').trim();
if (!/^\d+$/.test(port)) die(`state/gui-port is not a port: ${JSON.stringify(port)}`);
const BASE = `http://127.0.0.1:${port}`;

// The board decides servability; ask IT, never a local guess.
async function lane(p) {
  const r = await fetch(`${BASE}/api/file?path=${encodeURIComponent(p)}`);
  let j = null; try { j = await r.json(); } catch {}
  const out = { status: r.status, kind: j?.kind ?? null, ok: !!j?.ok, src: j?.src ?? null,
                error: j?.error ?? null, bytes: null };
  if (out.src) {                       // media: the bytes come from the second lane
    const r2 = await fetch(`${BASE}${out.src}`, { headers: { Range: 'bytes=0-1023' } });
    out.bytes = r2.status;
    if (r2.body) await r2.body.cancel();   // never buffer a video in the harness
  }
  return out;
}

console.log(`board: ${BASE}   docs under test: ${DOCS_UNDER_TEST.map(d => path.basename(d)).join(', ')}`);

// ── 0. the board is the thing we think it is ────────────────────────────────
console.log('\n0. preconditions');
{
  const probe = await lane(DOCS_UNDER_TEST[0]);
  ok('the live board serves the doc under test itself', probe.status === 200 && probe.ok,
     `HTTP ${probe.status} ${probe.error || ''}`);
}

// ── 1. harvest every cited path, exactly as the renderer would see it ───────
// The board links an ABSOLUTE path with a linkable extension, a relative
// [label](target) resolved against the doc's dir, and a bare directory path.
const EXT = 'md|markdown|txt|json|jsonl|ya?ml|log|csv|sh|js|mjs|png|jpe?g|gif|webp|pdf|mp3|wav|m4a|mp4|mov|mkv|webm|zip|tar|gz|tgz|html';
const ABS_RE = new RegExp(`(?:^|[\\s(\\[\`])((?:/)[^\\s<>"'\`()\\[\\]]*\\.(?:${EXT}))\\b`, 'gi');
const MDLINK_RE = /\[[^\]\n]+\]\(([^)\s]+)\)/g;

const cited = new Map();   // abs path -> {docs:Set, forms:Set}
const note = (p, doc, form) => {
  if (!cited.has(p)) cited.set(p, { docs: new Set(), forms: new Set() });
  cited.get(p).docs.add(path.basename(doc)); cited.get(p).forms.add(form);
};
// MIRROR THE RENDERER: md() parks ```fenced``` blocks as @@CODEBLOCK<n>@@ BEFORE
// any path rule runs (bin/vintask-gui.html, the /```.../ replace above the line
// loop), so a path inside a fence is never clickable. A 4-space INDENTED block is
// NOT parked — measured: the first run of this harness correctly flagged a zip
// path sitting in an indented block, because the renderer does link it. So strip
// fenced blocks only, and keep indented text in scope exactly as the board does.
const defence = (t) => t.replace(/```[\s\S]*?```/g, '\n');
for (const doc of DOCS_UNDER_TEST) {
  const txt = defence(fs.readFileSync(doc, 'utf8'));
  const dir = path.dirname(doc);
  for (const m of txt.matchAll(ABS_RE)) note(m[1], doc, 'bare-abs');
  for (const m of txt.matchAll(MDLINK_RE)) {
    const t = m[1];
    if (/^https?:/i.test(t)) continue;                 // remote links are a different lane
    note(t.startsWith('/') ? t : path.join(dir, t.replace(/^\.\//, '')), doc, 'md-link');
  }
}
console.log(`\n1. harvested ${cited.size} distinct local path(s) cited across the doc(s)`);
ok('the doc(s) cite at least the three exports', cited.size >= 3, `${cited.size} paths`);

// ── 2. every cited path OPENS on the live board ─────────────────────────────
console.log('\n2. every cited path opens on the live board (serial)');
const refused = [];
for (const [p, meta] of [...cited.entries()].sort()) {
  const r = await lane(p);
  const label = `${path.basename(p)}  (${[...meta.forms].join('+')})`;
  const good = r.status === 200 && r.ok && (r.bytes === null || r.bytes === 200 || r.bytes === 206);
  ok(`opens: ${label}`, good,
     good ? `kind=${r.kind}${r.bytes ? ` bytes=${r.bytes}` : ''}`
          : `HTTP ${r.status} kind=${r.kind} bytes=${r.bytes} ${r.error || ''}`);
  if (!good) refused.push(p);
  // A path presented as a clickable REVIEW SURFACE must not be a type the board
  // refuses to render. .html opens 200 but prints source — that is the exact
  // thing Vinta reported, so it is a failure here even though the status is 200.
  if (/\.html$/i.test(p)) {
    ok(`not presented as a review page: ${path.basename(p)}`, false,
       'the board prints .html as SOURCE TEXT, never as a page');
  }
}

// ── 3. the three exports specifically PLAY ──────────────────────────────────
console.log('\n3. the three exports play (video lane end to end)');
for (const f of ['short-vertical.mp4', 'short-square.mp4', 'youtube-walkthrough.mp4']) {
  const p = path.join(DOCS, 'MWNMNT9-media', f);
  const isCited = cited.has(p);
  ok(`${f} is cited by the doc(s)`, isCited, isCited ? '' : 'NOT LINKED — Vinta cannot click it');
  const r = await lane(p);
  ok(`${f} resolves to the video lane and serves bytes`,
     r.ok && r.kind === 'video' && (r.bytes === 200 || r.bytes === 206),
     `kind=${r.kind} bytes=${r.bytes}`);
}

// ── 4. no doc offers a clickable link to a type the board refuses ───────────
console.log('\n4. no clickable link points at a board-refused type');
for (const doc of DOCS_UNDER_TEST) {
  const txt = fs.readFileSync(doc, 'utf8');
  const base = path.basename(doc);
  for (const m of txt.matchAll(MDLINK_RE)) {
    const t = m[1];
    if (/^https?:/i.test(t)) continue;
    ok(`${base}: markdown link target is not a refused type (${t})`,
       !/\.(html|zip)$/i.test(t), /\.(html|zip)$/i.test(t) ? t : '');
  }
}

// ── 5. relative targets are gone (they depend on the viewer's open-doc dir) ─
console.log('\n5. no relative link targets remain');
for (const doc of DOCS_UNDER_TEST) {
  const txt = fs.readFileSync(doc, 'utf8');
  const rel = [...txt.matchAll(MDLINK_RE)].map(m => m[1])
    .filter(t => !/^https?:/i.test(t) && !t.startsWith('/') && !t.startsWith('#'));
  ok(`${path.basename(doc)}: every markdown link target is absolute`, rel.length === 0,
     rel.join(', '));
}

// ── 6. no backticked bare filename of a refused type ───────────────────────
// The renderer also links a BARE FILENAME inside a `code` span (BARE_NAME_RE,
// resolved against the open doc's dir). So `council-video-package.zip` in
// backticks becomes the same always-403 chip as the absolute path would.
console.log('\n6. no backticked bare filename of a board-refused type');
for (const doc of DOCS_UNDER_TEST) {
  const txt = defence(fs.readFileSync(doc, 'utf8'));
  const bad = [...txt.matchAll(/`([A-Za-z0-9._-]+\.(?:html|zip))`/gi)].map(m => m[1]);
  ok(`${path.basename(doc)}: no refused-type filename in a code span`, bad.length === 0,
     bad.join(', '));
}

console.log(`\n${pass}/${pass + fail} pass`);
if (refused.length) console.log(`refused paths: ${refused.join(', ')}`);
process.exit(fail === 0 ? 0 : 1);
