/** CPU-testable orchestration. The shell-capable SDK is not a security boundary. */
import fs from "node:fs";
import path from "node:path";
import { createHash, randomUUID } from "node:crypto";

export const USAGE = `usage: node tools/sdk/tune.mjs <seed.s> --client SPEC
  [--rounds 6] [--proposal-limit N] [--eval-calls N] [--perf-repeats 3]
  [--comparison-policy FILE] [--final-reserve N] [--wall-seconds 1800]
  [--search-policy FILE] [--history-run DIR] [--history-candidate ID]
  [--region loop|prologue|epilogue|inter|loop#1|all] [--loop 20] [--kernel NAME]
  [--run-id ID] [--model auto] [--config FILE]
  [--transcript|--no-transcript] [--transcript-path FILE] [--report-dir DIR]
  [--results|--no-results] [--results-path FILE]
  -- <opaque client tokens, forwarded exactly once at init>
Default: persistent run; no comparison policy means screening only.
--results-path names the JSON report (with a matching .md); run evidence/report
remain mandatory even with --no-results. Use tune_run.py for explicit recovery.`;

const valued = new Set(["client", "rounds", "proposal-limit", "eval-calls", "perf-repeats",
  "comparison-policy", "search-policy", "final-reserve", "wall-seconds", "region", "loop", "kernel",
  "run-id", "model", "config", "transcript-path", "report-dir", "results-path",
  "history-run", "history-candidate"]);
const switches = new Set(["transcript", "no-transcript", "results", "no-results"]);

export function parseArgs(argv) {
  const sep = argv.indexOf("--");
  const tokens = sep < 0 ? argv : argv.slice(0, sep);
  const params = sep < 0 ? [] : argv.slice(sep + 1);
  if (tokens.length === 1 && ["--help", "-h"].includes(tokens[0])) return { help: true };
  if (!tokens[0] || tokens[0].startsWith("--")) throw new Error(USAGE);
  const opts = { seed: tokens[0], params, transcript: true };
  for (let i = 1; i < tokens.length; i++) {
    const flag = tokens[i].slice(2);
    if (!tokens[i].startsWith("--") || (!valued.has(flag) && !switches.has(flag))) {
      throw new Error(`Unknown option: ${tokens[i]}`);
    }
    if (switches.has(flag)) {
      if (flag.endsWith("transcript")) opts.transcript = flag === "transcript";
      continue; // legacy --results switches cannot disable authoritative run evidence
    }
    if (!tokens[i + 1] || tokens[i + 1].startsWith("--")) throw new Error(`Missing value: --${flag}`);
    opts[flag] = tokens[++i];
  }
  if (!opts.client) throw new Error("--client is required");
  if (opts["history-candidate"] && !opts["history-run"]) throw new Error("--history-candidate requires --history-run");
  for (const [key, def, minimum] of [["rounds", 6, 1], ["perf-repeats", 3, 1],
    ["loop", 20, 1], ["proposal-limit", null, 1], ["eval-calls", null, 1], ["final-reserve", null, 0]]) {
    const value = opts[key] === undefined ? def : Number(opts[key]);
    if (value !== null && (!Number.isSafeInteger(value) || value < minimum)) throw new Error(`Invalid --${key}`);
    opts[key] = value;
  }
  opts["wall-seconds"] = Number(opts["wall-seconds"] ?? 1800);
  if (!Number.isFinite(opts["wall-seconds"]) || opts["wall-seconds"] <= 0) throw new Error("Invalid --wall-seconds");
  opts.region ??= "loop";
  opts["run-id"] ??= `sdk-${new Date().toISOString().replace(/[:.]/g, "-")}-${randomUUID().slice(0, 8)}`;
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$/.test(opts["run-id"])) throw new Error("Invalid --run-id");
  return opts;
}

export const sha256 = (data) => createHash("sha256").update(data).digest("hex");
export const shellQuote = (text) => "'" + String(text).replaceAll("'", "'\\''") + "'";
export const shellCommand = (args) => args.map(shellQuote).join(" ");

/** Resolve symlinks through the nearest existing ancestor of a new output. */
export function resolveOutputPath(filename) {
  const absolute = path.resolve(filename);
  try { return fs.realpathSync(absolute); }
  catch (error) {
    if (error.code !== "ENOENT") throw error;
    // A dangling symlink is not a missing output file: refuse it rather than
    // following a target that might later become an authority/archive path.
    try {
      if (fs.lstatSync(absolute).isSymbolicLink()) throw new Error(`Dangling output symlink: ${absolute}`);
    } catch (statError) { if (statError.code !== "ENOENT") throw statError; }
    const parent = path.dirname(absolute);
    if (parent === absolute) throw error;
    return path.join(resolveOutputPath(parent), path.basename(absolute));
  }
}

const within = (filename, directory) => filename === directory || filename.startsWith(directory + path.sep);
const markdownFor = (filename) => filename.slice(0, -path.extname(filename).length) + ".md";

/** Logs have a small allowlist within a run and cannot alias report outputs. */
export function transcriptPaths({ runDir, transcriptPath, reportDir, resultsPath, protectedDirs = [] }) {
  const root = resolveOutputPath(runDir);
  const requested = path.resolve(transcriptPath || path.join(root, "transcript.jsonl"));
  if (path.extname(requested) !== ".jsonl") throw new Error("Transcript path must end in .jsonl");
  const requestedMd = markdownFor(requested);
  const jsonlPath = resolveOutputPath(requested);
  const mdPath = resolveOutputPath(requestedMd);
  const reports = resolveOutputPath(reportDir || path.join(root, "report"));
  const reportJson = resolveOutputPath(resultsPath || path.join(reports, "report.json"));
  const reportMd = resolveOutputPath(markdownFor(reportJson));
  const protectedRoots = [root, ...protectedDirs.map(resolveOutputPath)];
  const allowed = (filename) => filename === path.join(root, "transcript.jsonl") ||
    filename === path.join(root, "transcript.md") ||
    (filename !== path.join(root, "transcripts") && within(filename, path.join(root, "transcripts")));
  for (const filename of [requested, requestedMd, jsonlPath, mdPath]) {
    if (protectedRoots.some((directory) => within(filename, directory)) && !allowed(filename)) {
      throw new Error(`Transcript may only use default files or RUN/transcripts inside protected run storage: ${filename}`);
    }
    if (within(filename, reports) || filename === reportJson || filename === reportMd) {
      throw new Error(`Transcript conflicts with report output: ${filename}`);
    }
  }
  if (jsonlPath === mdPath) throw new Error("Transcript JSONL and Markdown resolve to the same file");
  return { jsonlPath, mdPath };
}

// Sequential policies may stop early, but budgets must cover their last look.
export function plannedPairs(policy, stage) {
  const looks = policy[`${stage}_looks`];
  return Array.isArray(looks) ? looks.at(-1)?.pairs : policy[`${stage}_pairs`];
}

export function initArgs(opts, seed, policy = null) {
  // Statistical thresholds come only from the user's file. Derived budgets
  // cover the configured comparisons; the controller validates the policy.
  const reserve = opts["final-reserve"] ?? (policy ? 2 * plannedPairs(policy, "final") : 0);
  const proposals = opts["proposal-limit"] ?? opts.rounds * 4;
  const calls = opts["eval-calls"] ?? ((opts.rounds + 2) * opts["perf-repeats"] + reserve +
    (policy ? 2 * plannedPairs(policy, "confirm") * policy.max_confirmations : 0));
  for (const value of [reserve, proposals, calls]) {
    if (!Number.isSafeInteger(value) || value < 0) throw new Error("Invalid policy-derived budget");
  }
  const args = ["tools/tune_run.py", "init", seed, "--client", opts.client,
    "--run-id", opts["run-id"], "--proposal-limit", String(proposals), "--eval-calls", String(calls),
    "--perf-repeats", String(opts["perf-repeats"]), "--final-reserve", String(reserve),
    "--wall-seconds", String(opts["wall-seconds"]), "--loop", String(opts.loop),
    "--region", ["all", "auto", "any"].includes(opts.region) ? "loop" : opts.region];
  if (opts.kernel) args.push("--kernel", opts.kernel);
  if (opts["comparison-policy"]) args.push("--comparison-policy", path.resolve(opts["comparison-policy"]));
  if (opts["search-policy"]) args.push("--search-policy", path.resolve(opts["search-policy"]));
  args.push("--", ...opts.params);
  return args;
}

export function buildPrompt({ python, repo, runDir, opts, manifest }) {
  const cli = (command, ...args) => shellCommand([python, "tools/tune_run.py", command, runDir, ...args]);
  const roaming = ["all", "auto", "any"].includes(opts.region);
  const region = roaming ? [] : ["--region", opts.region];
  const searchPolicy = manifest.search_policy || {};
  const historyArgs = opts["history-run"]
    ? [path.resolve(opts["history-run"]), ...(opts["history-candidate"] ? ["--candidate", opts["history-candidate"]] : [])]
    : null;
  const historical = historyArgs
    ? `EXPLICIT HISTORY SOURCE: after the current original has a valid screening batch, inspect once:
   ${cli("history", ...historyArgs)}
   This is a CPU-only compatibility/provenance check; it returns a recipe requiring current evaluation.
   If compatible and current status permits search, use its chain length to reserve 1 + N proposal
   slots in BOTH the global proposal budget and reuse_proposal_limit before one warm-start request:
   ${cli("warm-start", ...historyArgs)}
   Warm-start rebuilds every step from the current original through current CPU gates. It imports no
   old measurements and does not change the current exploration parent or incumbent. Inspect the
   returned registered steps, source_evidence_ref and final candidate_id. Screen that candidate using
   this run's eval command below, then apply only the CURRENT comparison policy and confirmation gates.
   Historical scores or old confirmed gains never count as a current baseline, gain or recommendation.
   Its screen counts toward the ${opts.rounds} candidate-screen target; cached screens are not new evidence.
   Each warm-start costs one request plus one proposal per prepared chain step, including normalization;
   invalid requests and duplicate steps still consume their applicable proposal/reuse budgets.
   Respect reuse_eval_call_limit and independent_eval_reserve for screens and the complete confirmation;
   preserve final reserve. Reuse provenance is sticky for duplicates and descendants: do not relabel it.
   At most one history inspection and one warm-start attempt for this supplied source in this SDK session.
   Do not automatically retry failed, partial, interrupted or duplicate imports, or choose another
   historical candidate/path to bypass the limit. Inspect status; continue independent current-observation
   exploration only when allowed. Never automatically resume. No directory scanning or other history source.`
    : `HISTORICAL IMPORTS DISABLED: no --history-run was supplied. Do not scan prior runs, inspect history,
   or call warm-start. Continue from this run's current observations.`;
  const profileLimit = searchPolicy.profile_call_limit;
  const profileAllowed = profileLimit === null || (Number.isSafeInteger(profileLimit) && profileLimit > 0);
  const profiling = profileAllowed
    ? `OPTIONAL PROFILE: the frozen search policy permits profile calls (limit=${JSON.stringify(profileLimit)}).
Use ${cli("profile", "CANDIDATE_ID")} only for a concrete stall hypothesis after both original and
that candidate have valid screening batches, while status.search.search_stopped is false and budgets
permit it. Replace CANDIDATE_ID with the actual ID; normally profile the current exploration_parent_id.
Each profile is a separate charged client evaluate call, consuming one eval call AND one profile call;
final reserve and independent_eval_reserve remain protected. It is navigation evidence only: profile
timings never count as screen, confirm, final, or a performance verdict, even if a score is returned.
Read status.search.profile_needs_refresh/current_profile_id. Profiles are bound to candidate and
parent_revision; after parent change or promotion, old profile data cannot explain the new parent.
At most one optional profile request per parent revision in this SDK session. An unavailable profile,
missing counters, or an error is recorded evidence; do not automatically retry to clear needs_refresh.
Keep searching from static facts or stop when budgets/stagnation require it. A null profile limit
removes only the profile-specific cap, not the total eval budget or this no-retry rule.`
    : `PROFILING DISABLED: the frozen search policy has no positive or explicit null profile allowance.
Do not call profile. status.search.profile_needs_refresh alone is not permission to spend client calls.`;
  const confirmation = manifest.comparison_policy
    ? `An explicit comparison policy is frozen in manifest. A promising measured candidate may be
confirmed using ${cli("confirm", "CANDIDATE_ID")}. Read the returned verdict; only confirmed_gain
can promote incumbent. Never repeat a candidate/reference confirmation to chase significance.
After promotion observe again: instruction IDs belong to the new parent. SDK performs final once
after you finish normally; do not call final yourself. Do not spend its reserved evaluation calls.`
    : `There is NO comparison policy. Do not call confirm or final. All results are screening only,
not confirmed gains or recommendations. A measured exploration branch may be selected with
${cli("select-parent", "CANDIDATE_ID")}; this does not promote incumbent. Re-observe after selection.`;
  return `You navigate single-kernel instruction scheduling in FACK. Work from ${repo}.
The persistent run is ${runDir}; original, normalized, candidates and budgets are controller-owned.
Static checks cover the modeled ISA; client numerical checks and measurements are still required.
Use only this run's tune_run.py commands for evaluation. Do not edit engine/client/archive/state,
call legacy agent_session.py, invoke a client directly, create another run, or change frozen params.
Write proposal JSON files under ${path.join(runDir, "proposals-input")} (create it if needed).
This shell instruction is an operating convention, not a sandbox security guarantee.

Self-study is disabled in the default tuning workflow. selfstudy/ is the pinned
gfx_hw_prob submodule, checked out sparsely for gfx942. Read the existing export at
selfstudy/gfx942/mfma_issue/skills_out/skills/mfma-interleave-gfx942 through
knowledge/skills/mfma-interleave-gfx942. Never run pipeline, study, fit, hardware
discovery, or skill regeneration to prepare a tuning run. If the export is missing,
report the missing dependency; do not generate replacements or update the submodule.

Budget: ${JSON.stringify(manifest.budget)}; screening repeats=${manifest.perf_repeats}.
Frozen search policy: ${JSON.stringify(searchPolicy)}. Do not change this policy or increase its limits.
Aim for at most ${opts.rounds} candidate screens. Rejected prepare requests spend proposal budget;
all client calls, including baselines, optional profiles, confirmation and final sides, spend the hard eval budget.
Stop on exhaustion. No automatic --repeat or resume; interrupted work needs explicit recovery.
${roaming ? "You may choose any observed region; re-observe before changing regions." : `Tune only region ${JSON.stringify(opts.region)}; include it on every observe.`}

1. Read status: ${cli("status")}. Establish original with ${cli("eval", "original")}.
   If original is not measured, stop: no replacement baseline or claim of speedup.
   Screen normalized with ${cli("eval", "normalized")}. Failure keeps original as reference.
   Normalization itself may be a confirmation candidate if it improves screening.
   ${historical}
2. Observe: ${cli("observe", ...region)}. Read facts plus observation_id, base_sha256 and parent_id.
   To generate a small pool of engine-checked directions, use:
   ${cli("suggest", "--n", String(Math.min(6, opts.rounds)), ...region)}
   suggest is CPU-only and returns {observation,suggestions,search}; use THAT returned observation's
   observation_id/base_sha256 with each suggestion's spec and hypothesis. It does not evaluate candidates.
   Anchored regions expose anchors/slots/fillers: JSON {"kind":"layout","layout":{"0":[IID]}}.
   Anchor-less regions expose dag/tunable/critical/segments/waitcnt_preview:
   JSON {"kind":"order","order":[IID,IID]}; use small partial orders (typically 2-15 IDs).
   Region must match observation. Look at dependencies and legal windows; do not hand-edit assembly.
   Read status.search.direction_eval_calls. Start with small batches across available UNTRIED independent
   directions (zero charged screen calls), before more variants of one direction. Keep stable direction
   names and never rename a used direction to evade its frozen direction_eval_call_limit. Reserve a whole
   perf_repeats batch before requesting eval; every failed/returned call still spends its quota.
   If a candidate earns confirmed_gain, re-observe the promoted parent and locally refine that candidate's
   direction. One confirmed candidate does not prove every layout in its direction is beneficial.
3. Save the spec JSON and hypothesis JSON with hypothesis, expected_observable, source
   (observation/profile/knowledge/history/replay), direction (stable lowercase identifier),
   and evidence_refs [{"kind":"observation","id":"OBSERVATION_ID"}]. Then prepare:
   ${cli("prepare", "--observation", "OBSERVATION_ID", "--base-sha256", "BASE_SHA256", "--spec-file", "SPEC_PATH", "--hypothesis-file", "HYPOTHESIS_PATH")}
   Replace placeholders with returned values. Prepare materializes and archives the candidate.
   Read legal/skipped and materialized diagnostics (actual payload moves, repairs, original/new findings).
   Revise within budget. Duplicate/no_change is not new evidence and repair-only is not proof of your move.
   Read ${cli("ledger")} to avoid repeating failed intents under the same parent/contract.
   Optional ${cli("annotate", "--file", "ANNOTATION_PATH")} records {text,evidence_refs} as interpretation only.
4. Screen prepared candidate: ${cli("eval", "CANDIDATE_ID")}. Only measured valid scores are usable.
   Compare screening scores to the measured reference; a high score alone is not confirmation.
5. ${confirmation}

Re-read status.search before new prepare/eval/profile/warm-start: use direction_eval_calls, profile_calls,
reuse_proposals, reuse_eval_calls and independent_eval_calls,
stagnation_count and search_stopped together with the frozen limits. search_stopped ends new search,
including suggest, prepare, warm-start, new screen batches and profiles. An eligible pending confirm may still run
once; then finish so the SDK can perform its configured final. Do not bypass a stop with new direction
names, repeated eval, another run, or changed policy. Duplicate/no_change and cached batches are not
fresh independent experiments. A single failed or noisy candidate does not condemn a whole direction.

${profiling}

Client params are already frozen by init; do not append -- or params to subsequent commands.
OPTIONAL COMBINATION: ${cli("replay", "SOURCE_CANDIDATE_ID")} (combine is an alias) re-expresses
the source candidate's last successful layout/order intent on the current exploration parent.
The source must have passed its latest screening. The engine rebuilds both ancestry chains from
original and rejects ambiguous instruction matches or conflicts with retained target intents.
A replay request spends one proposal; successful mapping then spends a second ordinary prepare.
It performs no client calls and does not select a parent or promote incumbent. Inspect returned
provenance/diagnostics, then screen and confirm the resulting candidate through the normal gates.
Do not add individual speedups or reuse old instruction IDs. A failed combination retains the current
selection; revise a fresh observation if mapping is ambiguous.
End with candidate IDs, region, hypothesis, screening evidence and any actual confirm verdict.
The report comes from authoritative state; do not claim final recommendation before driver final.
`;
}

/** Finalize only a normal completed SDK turn. Failure paths export without new GPU work. */
export function finishRun({ invoke, runDir, successful, reportArgs = [] }) {
  const errors = [];
  let finalResult = null;
  try {
    if (successful) {
      const status = invoke(["tools/tune_run.py", "status", runDir]);
      if (status.manifest.comparison_policy && status.state.phase === "search" && !status.state.final_result) {
        // The controller checks pending attempts and returns a structured error;
        // never recover or retry a failed final here.
        finalResult = invoke(["tools/tune_run.py", "final", runDir]);
      }
    }
  } catch (error) { errors.push(`final: ${error.message}`); }
  let report = null;
  try { report = invoke(["tools/tune_run_report.py", runDir, ...reportArgs]); }
  catch (error) { errors.push(`report: ${error.message}`); }
  return { finalResult, report, errors };
}

/** Preserve the assembly source bytes in a fresh initialization attempt. */
export function prepareSeed({ seed, inputsDir }) {
  const source = path.resolve(seed);
  if (!source.endsWith(".s")) throw new Error("Seed must be an editable .s assembly file");
  const data = fs.readFileSync(source);
  fs.mkdirSync(inputsDir, { recursive: true });
  // Each initialization attempt owns a fresh directory. A failed init or
  // preparation must not block retrying its run-id or delete earlier evidence.
  const preparationDir = fs.mkdtempSync(path.join(inputsDir, "attempt-"));
  const archived = path.join(preparationDir, "input.s");
  fs.writeFileSync(archived, data, { flag: "wx" });
  return { seed: archived, source: { path: source, kind: "assembly",
    sha256: sha256(data), archive: archived }, assembly_sha256: sha256(fs.readFileSync(archived)),
    conversion: null };
}

export function recordProvenance(runDir, prepared, manifest) {
  if (prepared.assembly_sha256 !== manifest.original_sha256) throw new Error("Initialized assembly digest differs from prepared input");
  const data = fs.readFileSync(prepared.source.archive);
  if (sha256(data) !== prepared.source.sha256) throw new Error("Input source changed before archival");
  const relative = "inputs/original.s";
  fs.mkdirSync(path.join(runDir, "inputs"), { recursive: true });
  fs.writeFileSync(path.join(runDir, relative), data, { flag: "wx" });
  const provenance = { schema_version: 1, authority: "sdk_sidecar_not_frozen_manifest",
    source: { ...prepared.source, archive: relative }, assembly_sha256: prepared.assembly_sha256,
    conversion: prepared.conversion };
  fs.writeFileSync(path.join(runDir, "input_provenance.json"), JSON.stringify(provenance, null, 2) + "\n", { flag: "wx" });
}
