/**
 * The DirCoMedia login page — served inline by gateway.js.
 *
 * SELF-CONTAINED BY REQUIREMENT: no external CSS, no CDN font, no bundler. This
 * page is the first thing an unauthenticated visitor touches, so it must not
 * fetch anything from a third party (a compromised CDN would be scripting the
 * one form that guards Vinta's social accounts) and it must render even when
 * Next.js is down.
 *
 * NO-COLLISION LAW: one centered flex column, explicit gaps, box-sizing:border-box
 * everywhere. The error slot reserves its height permanently (min-height) so
 * revealing a message can never shove the button down or overlap the field.
 * Verified at 320/375/768/1280/1920.
 */
function loginPage({ error = "", locked = false, retryAfter = 0 } = {}) {
  const msg = locked
    ? `Too many attempts. Try again in ${Math.ceil(retryAfter / 60)} min.`
    : error;
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  return `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>DirCoMedia</title>
<style>
  *,*::before,*::after{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    min-height:100svh;
    display:flex;align-items:center;justify-content:center;
    padding:clamp(1rem,4vw,3rem);
    padding-left:max(clamp(1rem,4vw,3rem),env(safe-area-inset-left));
    padding-right:max(clamp(1rem,4vw,3rem),env(safe-area-inset-right));
    background:#0b0b0f;color:#e7e7ea;
    font:400 16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  .card{
    width:100%;max-width:23rem;
    display:flex;flex-direction:column;gap:1.25rem;
    background:#121218;border:1px solid #24242e;border-radius:14px;
    padding:clamp(1.5rem,5vw,2.25rem);
  }
  .brand{display:flex;flex-direction:column;gap:.4rem}
  h1{margin:0;font-size:1.15rem;font-weight:600;letter-spacing:-.01em}
  .sub{margin:0;font-size:.82rem;color:#8b8b97;line-height:1.45}
  form{display:flex;flex-direction:column;gap:.75rem}
  label{font-size:.78rem;color:#a9a9b3;font-weight:500}
  input{
    width:100%;
    /* 16px min prevents iOS Safari from zooming the viewport on focus. */
    font:400 16px/1.4 system-ui,sans-serif;
    padding:.7rem .85rem;
    background:#0b0b0f;color:#e7e7ea;
    border:1px solid #2c2c38;border-radius:9px;
    outline:none;transition:border-color .15s;
  }
  input:focus{border-color:#5b5bd6}
  button{
    width:100%;font:600 15px/1 system-ui,sans-serif;
    padding:.8rem 1rem;margin-top:.15rem;
    background:#5b5bd6;color:#fff;
    border:0;border-radius:9px;cursor:pointer;
    transition:background .15s;
  }
  button:hover{background:#6a6ae0}
  button:active{background:#4f4fc4}
  /* Reserved space: the error can appear and disappear without moving anything. */
  .err{
    min-height:1.15rem;margin:0;
    font-size:.8rem;line-height:1.15rem;color:#ff6b6b;
    overflow-wrap:anywhere;
  }
  .foot{margin:0;font-size:.72rem;color:#5c5c68;text-align:center}
  @media (max-width:360px){ .card{padding:1.25rem} }
</style>
</head><body>
  <main class="card">
    <div class="brand">
      <h1>DirCoMedia</h1>
      <p class="sub">This dashboard posts to live social accounts. Enter the master password to continue.</p>
    </div>
    <form method="POST" action="/__auth/login">
      <label for="pw">Master password</label>
      <input id="pw" name="password" type="password" autocomplete="current-password"
             autofocus required ${locked ? "disabled" : ""} spellcheck="false">
      <p class="err">${esc(msg)}</p>
      <button type="submit" ${locked ? "disabled" : ""}>Unlock</button>
    </form>
    <p class="foot">Owner access only</p>
  </main>
</body></html>`;
}
module.exports = { loginPage };
