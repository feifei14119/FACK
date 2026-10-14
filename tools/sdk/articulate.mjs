/**
 * Layer 2 (offline AI articulation) -- HEADLESS driver.
 *
 * This REPLACES the "a human/IDE agent hand-writes ai_proposal.json" step with a
 * programmatic Cursor agent (via @cursor/sdk). It runs the whole Layer 2 loop
 * end-to-end, NO Cursor IDE needed:
 *
 *   1. export the AI brief from the mined quant skills  (tools/ai_skill_brief.py)
 *   2. ask a Cursor agent to READ the brief and EMIT ai_proposal.json
 *   3. validate + ingest it into capped, candidate-only ai-*.json skills
 *      (tools/ingest_ai_skills.py)
 *
 * The deterministic RED LINES still hold and are enforced by the Python ingest
 * gate regardless of what the model emits: measured numbers are copied verbatim
 * from Layer 1 (the agent cannot fabricate them), extrapolations are flagged +
 * weight/confidence-capped, scope stays structural, every skill stays candidate.
 * A wrong model output can only be dropped/clamped -- never pollute the store.
 *
 * Usage:
 *   node articulate.mjs [--out study_case/study_out] [--model auto] [--config P]
 *                       [--skip-brief] [--no-ingest] [--dry-run]
 *   (API key from env CURSOR_API_KEY or tools/sdk/cursor.config.json)
 *
 * Exit codes: 0 ok, 1 startup/auth failure (CursorAgentError), 2 run failed,
 *   3 unexpected, 4 model produced no parseable proposal JSON.
 */
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { Agent, CursorAgentError } from "@cursor/sdk";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "..", ".."); // testft/
const DEFAULT_CONFIG = path.join(__dirname, "cursor.config.json");
const PYTHON = "python3.8";

function arg(flag, def) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : def;
}
function has(flag) {
  return process.argv.includes(flag);
}

// --- key + model resolution (mirrors tune.mjs: env CURSOR_API_KEY > config) ---
function loadKeyAndModel() {
  let cfg = {};
  const cfgPath = arg("--config", DEFAULT_CONFIG);
  if (fs.existsSync(cfgPath)) {
    try {
      const st = fs.statSync(cfgPath);
      if (st.mode & 0o077) {
        console.error(`[articulate] WARNING: ${cfgPath} is not 0600 (mode ${(st.mode & 0o777).toString(8)}); run: chmod 600 ${cfgPath}`);
      }
      cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
    } catch (e) {
      console.error(`[articulate] failed to read config ${cfgPath}: ${e.message}`);
    }
  }
  const apiKey = process.env.CURSOR_API_KEY || cfg.apiKey;
  return { apiKey, cfgModel: cfg.model, cfgPath };
}

const OUT_REL = arg("--out", "study_case/study_out");
const OUT = path.isAbsolute(OUT_REL) ? OUT_REL : path.join(REPO, OUT_REL);
const SKIP_BRIEF = has("--skip-brief");
const DO_INGEST = !has("--no-ingest");
const INGEST_DRY = has("--dry-run");
const { apiKey, cfgModel, cfgPath } = loadKeyAndModel();
const model = arg("--model", cfgModel || "auto");

const briefJsonPath = path.join(OUT, "ai_brief.json");
const briefMdPath = path.join(OUT, "ai_brief.md");
const proposalPath = path.join(OUT, "ai_proposal.json");

function run(cmd, args) {
  console.error(`[articulate] $ ${cmd} ${args.join(" ")}`);
  const r = spawnSync(cmd, args, { cwd: REPO, encoding: "utf8", stdio: ["ignore", "inherit", "inherit"] });
  return r.status ?? 1;
}

// --- STAGE 1: export the brief from the mined quant skills -----------------
if (!SKIP_BRIEF) {
  const rc = run(PYTHON, ["tools/ai_skill_brief.py", "--out", OUT]);
  if (rc !== 0) {
    console.error(`[articulate] ai_skill_brief.py failed (rc=${rc}); run mine_corpus first.`);
    process.exit(rc);
  }
}
if (!fs.existsSync(briefJsonPath)) {
  console.error(`[articulate] brief not found: ${briefJsonPath} (run without --skip-brief, after mining)`);
  process.exit(2);
}
const briefJson = fs.readFileSync(briefJsonPath, "utf8");
const briefMd = fs.existsSync(briefMdPath) ? fs.readFileSync(briefMdPath, "utf8") : "";

if (!apiKey) {
  console.error(
    `No API key. Set env CURSOR_API_KEY, or put {"apiKey":"cursor_..."} in ${cfgPath}.\n` +
    "Mint one at cursor.com/dashboard/integrations.");
  process.exit(1);
}

// --- tolerant JSON extraction from the model's final text ------------------
function extractJson(text) {
  if (!text) return null;
  let t = text.trim();
  const fence = t.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) t = fence[1].trim();
  try { return JSON.parse(t); } catch { /* fall through */ }
  const i = t.indexOf("{");
  const j = t.lastIndexOf("}");
  if (i >= 0 && j > i) {
    try { return JSON.parse(t.slice(i, j + 1)); } catch { /* fall through */ }
  }
  return null;
}

const PROMPT = `You are the OFFLINE Layer-2 ARTICULATION agent for the testft GPU-kernel skill miner.
A deterministic static miner (Layer 1) measured per-region instruction-scheduling constraints from a
GOLD kernel corpus and packed them into the BRIEF below. Your job: emit a JSON "proposal" that
articulates richer, conditional, possibly EXTRAPOLATED scheduling skills from those measured ranges.

HARD RULES (a Python gate re-checks these; violations are dropped or clamped, never trusted):
  * MEASURED numbers are GROUND TRUTH. To include one, cite it by metric (+kind, or before/after for
    intra_gap_order) with "extrapolated": false. Do NOT invent or alter its numbers -- they are copied
    verbatim from Layer 1 on ingest. Citing a ref that is not in measured_refs => it is DROPPED.
  * Any rule BEYOND the measured ranges (a conditional/ordering heuristic the data implies but does not
    directly state) MUST set "extrapolated": true and carry a non-empty "note". It will be admitted only
    capped + low-confidence.
  * scope is FIXED to each group's (arch,kernel_class,region). Do NOT add a shape, kernel name, or any
    other key. (The ingest takes scope from the group; you only pick base_skill_id.)
  * Produce 1-3 skills per group. Each: a one-line human "statement" + a "rationale" + constraints
    (a mix of cited measured refs and flagged extrapolations) + optional "conflict_groups" (pairs of
    refs that are mutually tense, e.g. high per-slot capacity vs. low adjacent co-occurrence).

OUTPUT: print ONLY the JSON object for ai_proposal.json -- no prose, no markdown fences. Shape:
{"version":1,"skills":[{"base_skill_id":"<group id>","id_suffix":"...","statement":"...","rationale":"...",
"constraints":[{"metric":"per_slot_capacity","kind":"vmem_load","weight":0.8,"extrapolated":false},
{"metric":"hint","kind":"ds_read","note":"...","weight":0.3,"extrapolated":true}],
"conflict_groups":[["per_slot_capacity:ds_read","adjacent_cooccur:ds_read"]]}]}

=== BRIEF (human-readable: red lines, schema, citable refs) ===
${briefMd}

=== BRIEF (machine-readable: measured groups + GROUND-TRUTH numbers you may reason over) ===
${briefJson}

Now output ONLY the ai_proposal.json content.`;

let agent;
try {
  agent = await Agent.create({
    apiKey,
    model: { id: model },
    local: { cwd: REPO, settingSources: [] },
  });
  const send = await agent.send(PROMPT);
  console.error(`[articulate] agent=${agent.agentId} run=${send.id} model=${model}`);

  let text = "";
  for await (const ev of send.stream()) {
    if (ev?.type === "assistant" && ev.message?.content) {
      for (const b of ev.message.content) {
        if (b.type === "text" && b.text) { text += b.text; process.stdout.write(b.text); }
      }
    }
  }
  const result = await send.wait();
  process.stdout.write("\n");
  // keep an audit log of the raw model output next to the proposal
  try { fs.writeFileSync(path.join(OUT, "ai_articulate.out.txt"), text); } catch { /* ignore */ }

  if (result.status === "error") {
    console.error(`[articulate] run failed: ${result.id}`);
    process.exitCode = 2;
  } else {
    const proposal = extractJson(text);
    if (!proposal || !Array.isArray(proposal.skills)) {
      console.error(`[articulate] could not parse a {version,skills:[...]} proposal from the model output.`);
      console.error(`[articulate] raw output saved to ${path.join(OUT, "ai_articulate.out.txt")}`);
      process.exitCode = 4;
    } else {
      fs.writeFileSync(proposalPath, JSON.stringify(proposal, null, 2) + "\n");
      console.error(`[articulate] wrote ${proposalPath} (${proposal.skills.length} proposed skill/s)`);
      if (DO_INGEST) {
        // The proposal is the COMPLETE AI skill set; clear stale ai-*.json from a
        // previous proposal so they never linger (gold-*.json are untouched).
        if (!INGEST_DRY) {
          const skillsDir = path.join(OUT, "skills");
          if (fs.existsSync(skillsDir)) {
            for (const fn of fs.readdirSync(skillsDir)) {
              if (fn.startsWith("ai-") && fn.endsWith(".json")) {
                try { fs.unlinkSync(path.join(skillsDir, fn)); } catch { /* ignore */ }
              }
            }
          }
        }
        const ingestArgs = ["tools/ingest_ai_skills.py", "--out", OUT];
        if (INGEST_DRY) ingestArgs.push("--dry-run");
        const rc = run(PYTHON, ingestArgs);
        if (rc !== 0) process.exitCode = rc;
      } else {
        console.error(`[articulate] --no-ingest: skipping gate. Run: ${PYTHON} tools/ingest_ai_skills.py --out ${OUT}`);
      }
    }
  }
} catch (err) {
  if (err instanceof CursorAgentError) {
    console.error(`[articulate] startup failed: ${err.message} (retryable=${err.isRetryable})`);
    process.exitCode = 1;
  } else {
    console.error(`[articulate] unexpected error: ${err?.stack || err}`);
    process.exitCode = 3;
  }
} finally {
  await Promise.race([
    (async () => { try { await agent?.[Symbol.asyncDispose]?.(); } catch { /* ignore */ } })(),
    new Promise((r) => setTimeout(r, 8000)),
  ]);
  process.exit(process.exitCode ?? 0);
}
