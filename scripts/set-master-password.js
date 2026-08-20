#!/usr/bin/env node
/**
 * Set or rotate the DirCoMedia master password.
 *
 *   node scripts/set-master-password.js                     # prompt, print hash only
 *   node scripts/set-master-password.js --write             # prompt, write backend/.env
 *   node scripts/set-master-password.js --generate --write  # invent a strong one
 *   echo "mypassword" | node scripts/set-master-password.js --write
 *
 * The plaintext is never stored by this script (except with --generate, which
 * must print the password once — that is the only moment it exists in readable
 * form). Only the scrypt hash is written to backend/.env.
 */
const fs = require("fs");
const path = require("path");
const readline = require("readline");
const crypto = require("crypto");
const auth = require("../auth");

const ENV = path.join(__dirname, "..", "backend", ".env");
const MIN_LEN = 12;
const args = process.argv.slice(2);
const WRITE = args.includes("--write");
const GENERATE = args.includes("--generate");

function upsert(env, key, value) {
  // Preserve every other key and the file's ordering; only touch the one line.
  const re = new RegExp("^" + key + "=.*$", "m");
  return re.test(env)
    ? env.replace(re, key + "=" + value)
    : env.replace(/\n*$/, "\n" + key + "=" + value + "\n");
}

function generatePassword() {
  // 32 chars from an unambiguous alphabet — no 0/O/1/l/I to misread aloud.
  const abc = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789-_";
  const limit = 256 - (256 % abc.length); // reject-sample to keep it uniform
  let out = "";
  while (out.length < 32) {
    const b = crypto.randomBytes(1)[0];
    if (b < limit) out += abc[b % abc.length];
  }
  return out;
}

function askPassword(prompt) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(prompt, (a) => { rl.close(); resolve(a); });
  });
}

(async () => {
  let pw;
  if (GENERATE) {
    pw = generatePassword();
  } else if (!process.stdin.isTTY) {
    pw = fs.readFileSync(0, "utf8").trim(); // piped input
  } else {
    pw = await askPassword("New master password (min " + MIN_LEN + " chars): ");
  }

  if (!pw || pw.length < MIN_LEN) {
    console.error("FAILED: password must be at least " + MIN_LEN + " characters (got " + (pw ? pw.length : 0) + ").");
    process.exit(1);
  }

  const hash = auth.hashPassword(pw);

  if (!WRITE) {
    console.log("\nAdd this to backend/.env:\n");
    console.log("DIRCOMEDIA_MASTER_PASSWORD_HASH=" + hash);
    if (GENERATE) console.log("\nPassword (save it now, it is not recoverable):\n\n    " + pw + "\n");
    process.exit(0);
  }

  let env = fs.existsSync(ENV) ? fs.readFileSync(ENV, "utf8") : "";
  env = upsert(env, "DIRCOMEDIA_MASTER_PASSWORD_HASH", hash);
  // A session secret must exist too. Rotating the PASSWORD does not imply
  // rotating the SESSION SECRET — that would sign every device out on a routine
  // password change, which is not what anyone means by "change my password".
  if (!/^DIRCOMEDIA_SESSION_SECRET=.+$/m.test(env)) {
    env = upsert(env, "DIRCOMEDIA_SESSION_SECRET", crypto.randomBytes(32).toString("hex"));
    console.log("- generated DIRCOMEDIA_SESSION_SECRET (was missing)");
  }
  fs.writeFileSync(ENV, env, { mode: 0o600 });

  console.log("OK: wrote DIRCOMEDIA_MASTER_PASSWORD_HASH to " + ENV);
  if (GENERATE) console.log("\nPassword (save it now, it is not recoverable):\n\n    " + pw + "\n");
  console.log("Apply it with:  pm2 restart dircomedia-gateway");
})();
