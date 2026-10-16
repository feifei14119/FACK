import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { parseArgs, initArgs, buildPrompt, finishRun, prepareSeed, recordProvenance,
  sha256, shellCommand, transcriptPaths, disposeAgent } from "./run_workflow.mjs";
import { renderAgentProfile } from "./run_workflow.mjs";

test("client-selected skill snapshots reach the model without hardcoded architecture or test methods", () => {
  const content = "Custom project uses event_timer and reference_check.\n";
  const profile = {arch: "gfx1100", client: "custom/case", skills: [
    {role: "client", path: "knowledge/skills/custom/SKILL.md", content, sha256: sha256(content)}],
    validation: {metrics: {event_timer: {unit: "us", direction: "lower"}}}};
  const prompt = buildPrompt({python: "python3", repo: "/repo", runDir: "/run", opts: options(),
    manifest: {budget: {}, perf_repeats: 3, evaluation_contract: {agent_profile: profile}}});
  assert.ok(prompt.includes(content));
  assert.ok(prompt.includes("gfx1100"));
  assert.equal(prompt.includes("gfx942"), false);
  assert.equal(prompt.includes("op_test"), false);
  assert.equal(prompt.includes("hip_graph"), false);
  assert.match(prompt, /do not\nexecute those outer steps or stop the shared environment/);
  assert.match(prompt, /each required metric with its unit/);
  profile.skills[0].content += "changed";
  assert.throws(() => renderAgentProfile(profile), /digest mismatch/);
});

const policy = { method: "paired_sign_v1", confirm_pairs: 8, final_pairs: 8,
  min_gain: 0.01, alpha: 0.05, max_confirmations: 3 };
const options = (extra = []) => parseArgs(["seed.s", "--client", "fake/case", ...extra]);

test("opaque tokens survive parsing/init and shell quoting without interpretation", () => {
  const params = ["--rounds", "99", "x=1", "x=2", "a b", "", "'quote'", "$(echo unsafe)", "`whoami`", "--"];
  const opts = options(["--rounds", "2", "--", ...params]);
  assert.equal(opts.rounds, 2);
  const args = initArgs(opts, "/seed with spaces.s");
  assert.deepEqual(args.slice(args.indexOf("--") + 1), params);
  const command = shellCommand([process.execPath, "-e", "console.log(JSON.stringify(process.argv.slice(1)))", "--", ...params]);
  const result = spawnSync("sh", ["-c", command], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), params);
});

test("default hard budgets and explicit policy-derived reserve are set before agent", () => {
  const plain = initArgs(options(), "seed.s");
  const value = (args, flag) => args[args.indexOf(flag) + 1];
  assert.equal(value(plain, "--eval-calls"), "24");
  assert.equal(value(plain, "--proposal-limit"), "24");
  assert.equal(value(plain, "--final-reserve"), "0");
  const paired = initArgs(options(["--comparison-policy", "policy.json"]), "seed.s", policy);
  assert.equal(value(paired, "--eval-calls"), "88");
  assert.equal(value(paired, "--final-reserve"), "16");
  const explicit = initArgs(options(["--eval-calls", "51", "--proposal-limit", "5", "--final-reserve", "16"]), "seed.s", policy);
  assert.equal(value(explicit, "--eval-calls"), "51");
  assert.equal(value(explicit, "--proposal-limit"), "5");
  const sequential = { method: "paired_sequential_v1", statistic: "signed_rank",
    confirm_looks: [{ pairs: 8, alpha_share: 0.2 }, { pairs: 32, alpha_share: 0.8 }],
    final_looks: [{ pairs: 16, alpha_share: 0.2 }, { pairs: 64, alpha_share: 0.8 }],
    min_gain: 0.005, alpha: 0.05, max_confirmations: 3, futility_stop: true };
  const looks = initArgs(options(["--comparison-policy", "policy.json"]), "seed.s", sequential);
  assert.equal(value(looks, "--final-reserve"), "128");
  assert.equal(value(looks, "--eval-calls"), String(24 + 128 + 2 * 32 * 3));
});

test("explicit search policy is forwarded only to init without changing hard budgets or opaque tokens", () => {
  const filename = "policy directory/search.json";
  const params = ["--search-policy", "client-owned.json", "a b", "x=1", "x=2"];
  const opts = options(["--search-policy", filename, "--", ...params]);
  const args = initArgs(opts, "seed.s");
  assert.equal(args[args.indexOf("--search-policy") + 1], path.resolve(filename));
  assert.deepEqual(args.slice(args.indexOf("--") + 1), params);
  assert.equal(args[args.indexOf("--eval-calls") + 1], "24");
  assert.equal(args[args.indexOf("--final-reserve") + 1], "0");
  assert.equal(initArgs(options(), "seed.s").includes("--search-policy"), false);
});

test("bad flags and numeric budgets are rejected before invocation", () => {
  for (const args of [["--rounds", "nan"], ["--eval-calls", "0"], ["--perf-repeats", "1.5"],
    ["--wall-seconds", "Infinity"], ["--run-id", "../escape"], ["--wat"], ["--region"],
    ["--history-candidate", "cand_example"], ["--history-run"]]) {
    assert.throws(() => options(args));
  }
});

test("history options affect navigation only and preserve init contract budgets and client tokens", () => {
  const params = ["--history-run", "client-owned-value", "x=1", "x=2"];
  const base = options(["--run-id", "fixed", "--comparison-policy", "policy.json", "--", ...params]);
  const explicit = options(["--run-id", "fixed", "--comparison-policy", "policy.json",
    "--history-run", "history directory/run", "--history-candidate", "cand_historical", "--", ...params]);
  assert.equal(explicit["history-run"], "history directory/run");
  assert.equal(explicit["history-candidate"], "cand_historical");
  assert.deepEqual(initArgs(explicit, "seed.s", policy), initArgs(base, "seed.s", policy));
});

function fakeLifecycle({ successful = true, configured = true, phase = "search", final = null, failFinal = false } = {}) {
  const calls = [];
  const invoke = (args) => {
    calls.push(args);
    if (args[1] === "status") return { manifest: { comparison_policy: configured ? policy : null }, state: { phase, final_result: final } };
    if (args[1] === "final" && failFinal) throw new Error("recovery_required");
    return { status: "fake" };
  };
  return { calls, result: finishRun({ invoke, runDir: "/frozen run", successful }) };
}

test("normal configured completion invokes one final and report", () => {
  const { calls, result } = fakeLifecycle();
  assert.deepEqual(calls.map((a) => a[1]), ["status", "final", "/frozen run"]);
  assert.equal(calls.at(-1)[0], "tools/tune_run_report.py");
  assert.deepEqual(result.errors, []);
});

test("no policy or existing final never starts a final comparison", () => {
  for (const config of [{ configured: false }, { phase: "finished", final: { status: "original_retained" } }, { phase: "finalizing" }]) {
    const { calls } = fakeLifecycle(config);
    assert.equal(calls.filter((a) => a[1] === "final").length, 0);
    assert.equal(calls.at(-1)[0], "tools/tune_run_report.py");
  }
});

test("SDK exception reports without client work; final error still reports once without retry", () => {
  const failed = fakeLifecycle({ successful: false });
  assert.deepEqual(failed.calls, [["tools/tune_run_report.py", "/frozen run"]]);
  const finalFailure = fakeLifecycle({ failFinal: true });
  assert.equal(finalFailure.calls.filter((a) => a[1] === "final").length, 1);
  assert.equal(finalFailure.calls.at(-1)[0], "tools/tune_run_report.py");
  assert.match(finalFailure.result.errors[0], /recovery_required/);
});

test("client-declared publication runs only after successful final and report, and errors are not retried", () => {
  for (const mode of ["gain", "retained", "report-error", "publish-error", "undeclared", "interrupted"]) {
    const calls = [];
    const invoke = (args) => {
      const command = args[0] === "tools/tune_run.py" ? args[1] : args[0];
      calls.push(command);
      if (command === "status") return { manifest: { comparison_policy: policy,
        evaluation_contract: { agent_profile: mode === "undeclared" ? {} : { publication: {mode: "git_commit_push"} } } },
        state: { phase: "search", final_result: null } };
      if (command === "final") return {status: mode === "retained" ? "original_retained" : "final_recommended"};
      if (command === "tools/tune_run_report.py" && mode === "report-error") throw Error("report invalid");
      if (command === "tools/publish_run.py" && mode === "publish-error") throw Error("push failed");
      return {status: "published"};
    };
    const result = finishRun({invoke, runDir: "/run", successful: mode !== "interrupted"});
    assert.equal(calls.filter(c => c === "tools/publish_run.py").length, ["gain", "publish-error"].includes(mode) ? 1 : 0);
    if (mode === "gain") {
      assert.deepEqual(calls, ["status", "final", "tools/tune_run_report.py", "tools/publish_run.py"]);
      assert.equal(result.publication.status, "published");
    }
    if (mode === "publish-error") assert.match(result.errors[0], /publication: push failed/);
  }
});

test("agent cleanup has a bounded wait for stalled creation and disposal", async () => {
  const stalled = new Promise(() => {});
  await assert.rejects(disposeAgent(stalled, { timeoutMs: 5 }), /termination is unverified/);
  await assert.rejects(disposeAgent(Promise.resolve({ [Symbol.asyncDispose]: () => stalled }),
    { timeoutMs: 5 }), /termination is unverified/);
  await assert.rejects(disposeAgent(Promise.resolve({})), /no async disposal method/);
});

test("prompt binds observations, region and authority without re-interpolating client tokens", () => {
  const opts = options(["--region", "epilogue", "--", "secret opaque marker"]);
  const prompt = buildPrompt({ python: "python3", repo: "/repo", runDir: "/run 'quoted'", opts,
    manifest: { budget: {}, perf_repeats: 3, comparison_policy: null } });
  assert.match(prompt, /observation_id, base_sha256/);
  assert.match(prompt, /Tune only region "epilogue"/);
  assert.match(prompt, /Do not call confirm or final/);
  assert.doesNotMatch(prompt, /secret opaque marker/);
  assert.match(prompt, /a zero CLI exit code alone does not mean a valid measurement/);
  assert.match(prompt, /bytes differ from original/);
  assert.match(prompt, /final_eval_reserve protects calls, not elapsed time/);
});

test("suggest prompt uses returned versioned observation and untried directions before refinement", () => {
  const prompt = buildPrompt({ python: "python3", repo: "/repo", runDir: "/run", opts: options(["--region", "epilogue"]),
    manifest: { budget: {}, perf_repeats: 3, comparison_policy: policy,
      search_policy: { direction_eval_call_limit: 6, profile_call_limit: 0, stagnation_limit: 4 } } });
  assert.match(prompt, /'suggest' '\/run' '--n' '6' '--region' 'epilogue'/);
  assert.match(prompt, /THAT returned observation/);
  assert.match(prompt, /UNTRIED independent/);
  assert.match(prompt, /locally refine/);
  assert.match(prompt, /status.search.direction_eval_calls/);
  assert.match(prompt, /search_stopped ends new search/);
  assert.match(prompt, /pending confirm may still run/);
  assert.match(prompt, /Do not call profile/);
  assert.doesNotMatch(prompt, /'profile' '\/run'/);
});

test("profile command requires frozen opt-in and never supplies a performance verdict or automatic retry", () => {
  const make = (search_policy) => buildPrompt({ python: "python3", repo: "/repo", runDir: "/run", opts: options(),
    manifest: { budget: {}, perf_repeats: 3, comparison_policy: null, search_policy } });
  for (const search of [undefined, {}, { profile_call_limit: 0 }]) {
    assert.match(make(search), /PROFILING DISABLED/);
    assert.doesNotMatch(make(search), /'profile' '\/run'/);
  }
  for (const profile_call_limit of [1, 2, null]) {
    const prompt = make({ profile_call_limit });
    assert.match(prompt, /'profile' '\/run' 'CANDIDATE_ID'/);
    assert.match(prompt, /one eval call AND one profile call/);
    assert.match(prompt, /timings never count as screen, confirm, final, or a performance verdict/);
    assert.match(prompt, /profile_needs_refresh\/current_profile_id/);
    assert.match(prompt, /bound to candidate and\nparent_revision/);
    assert.match(prompt, /At most one optional profile request per parent revision/);
    assert.match(prompt, /do not automatically retry/);
    assert.match(prompt, /Do not call confirm or final/);
  }
});

test("history navigation is opt-in with quoted explicit source, current baseline and one attempt", () => {
  const runDir = "/run 'quoted'";
  const source = "history dir/$(do-not-run)/'old'";
  const candidate = "cand_'quoted'";
  const make = (opts, comparison_policy = null) => buildPrompt({ python: "python3", repo: "/repo", runDir, opts,
    manifest: { budget: {}, perf_repeats: 3, comparison_policy,
      search_policy: { reuse_proposal_limit: 6, reuse_eval_call_limit: 9, independent_eval_reserve: 3 } } });
  const plain = make(options());
  assert.match(plain, /HISTORICAL IMPORTS DISABLED/);
  assert.doesNotMatch(plain, /'history'|'warm-start'/);
  const opts = options(["--history-run", source, "--history-candidate", candidate]);
  const prompt = make(opts);
  const command = (verb, ...args) => shellCommand(["python3", "tools/tune_run.py", verb, runDir, ...args]);
  const history = command("history", path.resolve(source), "--candidate", candidate);
  const warm = command("warm-start", path.resolve(source), "--candidate", candidate);
  assert.ok(prompt.includes(history));
  assert.ok(prompt.includes(warm));
  assert.ok(prompt.indexOf(command("eval", "original")) < prompt.indexOf(history));
  assert.ok(prompt.indexOf(history) < prompt.indexOf(warm));
  assert.match(prompt, /At most one history inspection and one warm-start attempt/);
  assert.match(prompt, /Do not automatically retry failed, partial, interrupted or duplicate imports/);
  assert.match(prompt, /No directory scanning or other history source/);
  assert.match(prompt, /Historical scores or old confirmed gains never count as a current baseline/);
  assert.match(prompt, /one request plus one proposal per prepared chain step, including normalization/);
  assert.match(prompt, /reuse_eval_call_limit and independent_eval_reserve/);
  assert.match(prompt, /Reuse provenance is sticky for duplicates and descendants/);
  assert.match(prompt, /Do not call confirm or final/);
  assert.match(make(opts, policy), /only confirmed_gain\ncan promote incumbent/);
  const automaticCandidate = make(options(["--history-run", source]));
  assert.ok(automaticCandidate.includes(command("history", path.resolve(source))));
  assert.ok(automaticCandidate.includes(command("warm-start", path.resolve(source))));
  assert.doesNotMatch(automaticCandidate, /'--candidate'/);
});

test("assembly source and provenance retain the original bytes", (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "sdk-run-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const source = path.join(root, "source.s");
  fs.writeFileSync(source, "assembly bytes");
  const prepared = prepareSeed({ seed: source, inputsDir: path.join(root, "inputs") });
  const runDir = path.join(root, "run");
  fs.mkdirSync(runDir);
  recordProvenance(runDir, prepared, { original_sha256: sha256("assembly bytes") });
  assert.equal(fs.readFileSync(path.join(runDir, "inputs/original.s"), "utf8"), "assembly bytes");
  const provenance = JSON.parse(fs.readFileSync(path.join(runDir, "input_provenance.json")));
  assert.equal(provenance.conversion, null);
  assert.equal(provenance.source.kind, "assembly");
  assert.equal(provenance.authority, "sdk_sidecar_not_frozen_manifest");
});

function temporaryRoot(t, prefix) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

test("transcript and Markdown are restricted within runs and cannot alias reports", (t) => {
  const root = temporaryRoot(t, "sdk-transcript-");
  const runDir = path.join(root, "runs/current");
  fs.mkdirSync(runDir, { recursive: true });
  const check = (transcriptPath, extra = {}) => transcriptPaths({ runDir, transcriptPath,
    protectedDirs: [path.join(root, "runs"), path.join(root, "sdk-inputs")], ...extra });
  assert.equal(check(undefined).jsonlPath, path.join(runDir, "transcript.jsonl"));
  assert.equal(check(path.join(runDir, "transcripts/nested/trace.jsonl")).mdPath,
    path.join(runDir, "transcripts/nested/trace.md"));
  assert.equal(check(path.join(root, "external/trace.jsonl")).mdPath, path.join(root, "external/trace.md"));
  for (const relative of ["state.json", "manifest.json", "state.jsonl", "artifacts/fake.jsonl",
    "inputs/fake.jsonl", "work/fake.jsonl", "report/fake.jsonl", "anything/fake.jsonl"]) {
    assert.throws(() => check(path.join(runDir, relative)));
  }
  assert.throws(() => check(path.join(root, "runs/other/transcript.jsonl")));
  assert.throws(() => check(path.join(root, "sdk-inputs/current/trace.jsonl")));
  const external = path.join(root, "external/summary.jsonl");
  assert.throws(() => check(external, { resultsPath: path.join(root, "external/summary.json") }), /report/);
  assert.throws(() => check(external, { reportDir: path.join(root, "external") }), /report/);
});

test("transcript path checks resolve symlinks in files and not-yet-created parents", (t) => {
  const root = temporaryRoot(t, "sdk-transcript-links-");
  const runDir = path.join(root, "runs/current");
  fs.mkdirSync(path.join(runDir, "artifacts"), { recursive: true });
  fs.mkdirSync(path.join(root, "external"));
  const state = path.join(runDir, "state.json");
  fs.writeFileSync(state, '{"untouched":true}');
  const check = (transcriptPath, extra = {}) => transcriptPaths({ runDir, transcriptPath, ...extra });
  const alias = path.join(root, "external/state-alias.jsonl");
  fs.symlinkSync(state, alias);
  assert.throws(() => check(alias), /protected/);
  fs.symlinkSync(path.join(runDir, "artifacts"), path.join(root, "archive-alias"));
  assert.throws(() => check(path.join(root, "archive-alias/new/trace.jsonl")), /protected/);
  fs.symlinkSync(path.join(runDir, "artifacts"), path.join(runDir, "transcripts"));
  assert.throws(() => check(path.join(runDir, "transcripts/new/trace.jsonl")), /protected/);
  const trace = path.join(root, "external/md-alias.jsonl");
  fs.symlinkSync(state, path.join(root, "external/md-alias.md"));
  assert.throws(() => check(trace), /protected/);
  fs.symlinkSync(path.join(root, "missing-target"), path.join(root, "dangling.jsonl"));
  assert.throws(() => check(path.join(root, "dangling.jsonl")), /Dangling/);
  assert.equal(fs.readFileSync(state, "utf8"), '{"untouched":true}');
  assert.deepEqual(fs.readdirSync(path.join(runDir, "artifacts")), []);
});

test("new seed preparation after failed init preserves previous attempts and legacy inputs", (t) => {
  const root = temporaryRoot(t, "sdk-prepare-retry-");
  const source = path.join(root, "seed.s");
  fs.writeFileSync(source, "first source");
  const inputsDir = path.join(root, "sdk-inputs/same-run-id");
  fs.mkdirSync(inputsDir, { recursive: true });
  fs.writeFileSync(path.join(inputsDir, "input.s"), "legacy evidence");
  const invoke = () => assert.fail("assembly preparation cannot invoke client or converter");
  const first = prepareSeed({ seed: source, inputsDir, invoke });
  // The caller's init can fail after preparation. Retrying the same run ID
  // gets an independent input snapshot, with neither overwrite nor cleanup.
  fs.writeFileSync(source, "corrected source");
  const retry = prepareSeed({ seed: source, inputsDir, invoke });
  assert.notEqual(first.seed, retry.seed);
  assert.equal(fs.readFileSync(first.seed, "utf8"), "first source");
  assert.equal(fs.readFileSync(retry.seed, "utf8"), "corrected source");
  assert.equal(fs.readFileSync(path.join(inputsDir, "input.s"), "utf8"), "legacy evidence");
});

test("code-object input is rejected before creating output directories", (t) => {
  const root = temporaryRoot(t, "sdk-unsupported-seed-");
  const source = path.join(root, "seed.co"), inputsDir = path.join(root, "inputs");
  fs.writeFileSync(source, "co bytes");
  assert.throws(() => prepareSeed({ seed: source, inputsDir }), /editable \.s assembly/);
  assert.equal(fs.existsSync(inputsDir), false);
  assert.equal(fs.readFileSync(source, "utf8"), "co bytes");
});

test("real driver without API key initializes budget then reports via fake Python, without SDK/client", (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "sdk-driver-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const seed = path.join(root, "seed.s");
  fs.writeFileSync(seed, "fake assembly");
  const runner = path.join(root, "fake-python");
  fs.writeFileSync(runner, `#!${process.execPath}
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const args = process.argv.slice(2), root = process.env.FAKE_ROOT;
fs.appendFileSync(path.join(root, "calls.jsonl"), JSON.stringify(args) + "\\n");
if (args[0] === "-m") {
  console.log(JSON.stringify({ spec: "fake/case", out_dir: path.join(root, "tune_out") }));
} else if (args[1] === "init") {
  const run = path.join(root, "tune_out/runs/fake"), data = fs.readFileSync(args[2]);
  fs.mkdirSync(run, { recursive: true });
  console.log(JSON.stringify({ run_dir: run, manifest: { original_sha256: crypto.createHash("sha256").update(data).digest("hex") } }));
} else if (args[0] === "tools/tune_run_report.py") {
  console.log(JSON.stringify({ markdown_path: path.join(root, "report.md") }));
} else { throw Error("Unexpected client/model invocation"); }
`, { mode: 0o700 });
  const result = spawnSync(process.execPath, [new URL("./tune.mjs", import.meta.url).pathname,
    seed, "--client", "fake/case", "--config", path.join(root, "no-config"), "--no-transcript",
    "--run-id", "fake", "--", "a b", "x=1", "x=2", "$(do-not-run)"], {
    encoding: "utf8", env: { ...process.env, CURSOR_API_KEY: "", TESTFT_PYTHON: runner, FAKE_ROOT: root },
  });
  assert.equal(result.status, 1, result.stderr);
  const calls = fs.readFileSync(path.join(root, "calls.jsonl"), "utf8").trim().split("\n").map(JSON.parse);
  assert.equal(calls.length, 3);
  assert.equal(calls[1][1], "init");
  assert.deepEqual(calls[1].slice(calls[1].indexOf("--") + 1), ["a b", "x=1", "x=2", "$(do-not-run)"]);
  assert.equal(calls[2][0], "tools/tune_run_report.py");
  assert.match(result.stderr, /No API key/);
  assert.match(result.stderr, /report.md/);
});

function fakeDriver(t) {
  const root = temporaryRoot(t, "sdk-driver-lifecycle-");
  const sdk = path.join(root, "tools/sdk");
  fs.mkdirSync(sdk, { recursive: true });
  for (const filename of ["tune.mjs", "run_workflow.mjs"]) {
    fs.copyFileSync(new URL(filename, import.meta.url), path.join(sdk, filename));
  }
  const stub = path.join(sdk, "node_modules/@cursor/sdk");
  fs.mkdirSync(stub, { recursive: true });
  fs.writeFileSync(path.join(stub, "package.json"), JSON.stringify({ type: "module", exports: "./index.mjs" }));
  fs.writeFileSync(path.join(stub, "index.mjs"), `
import fs from "node:fs";
import path from "node:path";
const root = process.env.FAKE_ROOT;
const mark = (name) => fs.writeFileSync(path.join(root, name), "fake SDK only");
async function interruptAt(stage) {
  if (process.env.FAKE_INTERRUPT_AT !== stage) return;
  setTimeout(() => process.kill(process.pid, process.env.FAKE_SIGNAL || "SIGTERM"), 0);
  await new Promise((resolve) => setTimeout(resolve, 40));
}
await interruptAt("import");
export const Agent = { async create() {
  mark("model-started");
  await interruptAt("create");
  return { agentId: "fake-agent", async send() { mark("model-sent"); await interruptAt("send"); return {
    id: "fake-sdk-run", async *stream() { await interruptAt("stream"); yield { type: "status" }; },
    async wait() { await interruptAt("wait"); return { status: "finished", id: "fake-sdk-run" }; }
  }; }, async [Symbol.asyncDispose]() {
    mark("model-disposed");
    if (process.env.FAKE_DISPOSE_ERROR === "1") throw new Error("fake disposal failed");
  } };
} };`);
  const runner = path.join(root, "fake-python");
  fs.writeFileSync(runner, `#!${process.execPath}
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const args = process.argv.slice(2), root = process.env.FAKE_ROOT;
const output = path.join(root, "tune_out"), run = path.join(output, "runs/fake");
fs.appendFileSync(path.join(root, "calls.jsonl"), JSON.stringify(args) + "\\n");
const reply = (value) => console.log(JSON.stringify(value));
if (args[0] === "-m") reply({ spec: "fake/case", out_dir: output });
else if (args[1] === "init") {
  if (process.env.FAKE_REJECT_INIT === "1") {
    reply({ error: { code: "arguments", message: "fake invalid policy" } }); process.exit(2);
  }
  fs.mkdirSync(path.dirname(run), { recursive: true });
  fs.mkdirSync(run);
  const searchIndex = args.indexOf("--search-policy");
  const manifest = { original_sha256: crypto.createHash("sha256").update(fs.readFileSync(args[2])).digest("hex"),
    budget: {}, perf_repeats: 1, comparison_policy: process.env.FAKE_COMPARISON === "1" ? {configured: true} : null,
    search_policy: searchIndex >= 0 ? JSON.parse(fs.readFileSync(args[searchIndex + 1])) : { profile_call_limit: 0 } };
  fs.writeFileSync(path.join(run, "manifest.json"), JSON.stringify(manifest));
  fs.writeFileSync(path.join(run, "state.json"), JSON.stringify({ authority: "untouched", phase: "search", final_result: null }));
  reply({ run_dir: run, manifest });
} else if (args[1] === "status") reply({
  manifest: JSON.parse(fs.readFileSync(path.join(run, "manifest.json"))),
  state: JSON.parse(fs.readFileSync(path.join(run, "state.json"))) });
else if (args[0] === "tools/tune_run_report.py") {
  JSON.parse(fs.readFileSync(path.join(run, "state.json")));
  reply({ markdown_path: path.join(run, "report/report.md") });
} else if (args[1] === "final") {
  if (!fs.existsSync(path.join(root, "model-disposed"))) throw Error("final before disposal");
  reply({ status: "original_retained" });
} else { throw Error("Unexpected client call"); }
`, { mode: 0o700 });
  const seed = path.join(root, "seed.s");
  fs.writeFileSync(seed, "fake assembly");
  const runDir = path.join(root, "tune_out/runs/fake");
  const invoke = (extra = [], env = {}) => spawnSync(process.execPath,
    [path.join(sdk, "tune.mjs"), seed, "--client", "fake/case", "--run-id", "fake", ...extra], {
      encoding: "utf8", timeout: 15000, env: { ...process.env, CURSOR_API_KEY: "fake-not-sent-to-network",
        TESTFT_PYTHON: runner, FAKE_ROOT: root, ...env },
    });
  return { root, runDir, invoke };
}

test("interrupt at each SDK await boundary stops work, disposes late creation and reports", (t) => {
  for (const stage of ["import", "create", "send", "stream", "wait"]) {
    for (const signal of ["SIGINT", "SIGTERM"]) {
      const fake = fakeDriver(t);
      const result = fake.invoke([], { FAKE_INTERRUPT_AT: stage, FAKE_SIGNAL: signal, FAKE_COMPARISON: "1" });
      assert.equal(result.status, signal === "SIGINT" ? 130 : 143, result.stderr);
      assert.equal(fs.existsSync(path.join(fake.root, "model-sent")), !["import", "create"].includes(stage));
      assert.equal(fs.existsSync(path.join(fake.root, "model-disposed")), stage !== "import");
      const calls = fs.readFileSync(path.join(fake.root, "calls.jsonl"), "utf8").trim().split("\n").map(JSON.parse);
      assert.equal(calls.at(-1)[0], "tools/tune_run_report.py");
      assert.equal(calls.some((args) => ["eval", "confirm", "final", "resume"].includes(args[1])), false);
    }
  }
});

test("normal SDK completion disposes the worker before one configured final and report", (t) => {
  const fake = fakeDriver(t);
  const result = fake.invoke([], { FAKE_COMPARISON: "1" });
  assert.equal(result.status, 0, result.stderr);
  const calls = fs.readFileSync(path.join(fake.root, "calls.jsonl"), "utf8").trim().split("\n").map(JSON.parse);
  assert.equal(calls.filter((args) => args[1] === "final").length, 1);
  assert.equal(calls.at(-1)[0], "tools/tune_run_report.py");
});

test("failed SDK disposal prevents final and returns an error while preserving the report", (t) => {
  const fake = fakeDriver(t);
  const result = fake.invoke([], { FAKE_DISPOSE_ERROR: "1", FAKE_COMPARISON: "1" });
  assert.equal(result.status, 3, result.stderr);
  assert.match(result.stderr, /fake disposal failed/);
  const calls = fs.readFileSync(path.join(fake.root, "calls.jsonl"), "utf8").trim().split("\n").map(JSON.parse);
  assert.equal(calls.at(-1)[0], "tools/tune_run_report.py");
  assert.equal(calls.some((args) => args[1] === "final"), false);
});

test("real driver blocks authority aliases before fake SDK starts and still reports", (t) => {
  for (const mode of ["state", "markdown-symlink", "report-md"]) {
    const fake = fakeDriver(t);
    const external = path.join(fake.root, "external");
    fs.mkdirSync(external);
    let extra;
    if (mode === "state") extra = ["--transcript-path", path.join(fake.runDir, "state.json")];
    else if (mode === "markdown-symlink") {
      fs.symlinkSync(path.join(fake.runDir, "state.json"), path.join(external, "trace.md"));
      extra = ["--transcript-path", path.join(external, "trace.jsonl")];
    } else extra = ["--transcript-path", path.join(external, "summary.jsonl"),
      "--results-path", path.join(external, "summary.json")];
    const result = fake.invoke(extra);
    assert.equal(result.status, 3, result.stderr);
    assert.equal(JSON.parse(fs.readFileSync(path.join(fake.runDir, "state.json"))).authority, "untouched");
    assert.equal(fs.existsSync(path.join(fake.root, "model-started")), false);
    const calls = fs.readFileSync(path.join(fake.root, "calls.jsonl"), "utf8").trim().split("\n").map(JSON.parse);
    assert.equal(calls.at(-1)[0], "tools/tune_run_report.py");
  }
});

test("real driver retries same run-id after init rejection using fresh input preparation", (t) => {
  const fake = fakeDriver(t);
  const failed = fake.invoke([], { FAKE_REJECT_INIT: "1" });
  assert.equal(failed.status, 3, failed.stderr);
  assert.equal(fs.existsSync(fake.runDir), false);
  const inputs = path.join(fake.root, "tune_out/sdk-inputs/fake");
  const first = fs.readdirSync(inputs);
  assert.equal(first.length, 1);
  const successful = fake.invoke();
  assert.equal(successful.status, 0, successful.stderr);
  assert.equal(fs.readdirSync(inputs).length, 2);
  assert.equal(fs.readFileSync(path.join(inputs, first[0], "input.s"), "utf8"), "fake assembly");
  assert.equal(JSON.parse(fs.readFileSync(path.join(fake.runDir, "state.json"))).authority, "untouched");
  assert.equal(fs.existsSync(path.join(fake.root, "model-started")), true);
  assert.equal(fs.existsSync(path.join(fake.runDir, "transcript.jsonl")), true);
  assert.equal(fs.existsSync(path.join(fake.runDir, "transcript.md")), true);
});

test("real driver passes search policy to fake init and builds its prompt from the frozen response", (t) => {
  const fake = fakeDriver(t);
  const filename = path.join(fake.root, "chosen search policy.json");
  const search = { profile_call_limit: 2, direction_eval_call_limit: 6, stagnation_limit: 5 };
  fs.writeFileSync(filename, JSON.stringify(search));
  const result = fake.invoke(["--search-policy", filename]);
  assert.equal(result.status, 0, result.stderr);
  const calls = fs.readFileSync(path.join(fake.root, "calls.jsonl"), "utf8").trim().split("\n").map(JSON.parse);
  const init = calls.find((args) => args[1] === "init");
  assert.equal(init[init.indexOf("--search-policy") + 1], filename);
  assert.equal(calls.filter((args) => args.includes("--search-policy")).length, 1);
  const prompt = JSON.parse(fs.readFileSync(path.join(fake.runDir, "transcript.jsonl"), "utf8").split("\n")[0]).prompt;
  assert.match(prompt, /OPTIONAL PROFILE/);
  assert.match(prompt, /"direction_eval_call_limit":6/);
  assert.equal(calls.some((args) => args[1] === "profile"), false);
});

test("real driver supplies history navigation in prompt without automatic import or changing init", (t) => {
  const fake = fakeDriver(t);
  const history = path.join(fake.root, "external old runs/old");
  const result = fake.invoke(["--history-run", history, "--history-candidate", "cand_old"]);
  assert.equal(result.status, 0, result.stderr);
  const calls = fs.readFileSync(path.join(fake.root, "calls.jsonl"), "utf8").trim().split("\n").map(JSON.parse);
  const init = calls.find((args) => args[1] === "init");
  assert.equal(init.includes("--history-run"), false);
  assert.equal(init.includes("--history-candidate"), false);
  assert.equal(init.includes(history), false);
  assert.equal(init[init.indexOf("--eval-calls") + 1], "24");
  assert.equal(init[init.indexOf("--final-reserve") + 1], "0");
  const prompt = JSON.parse(fs.readFileSync(path.join(fake.runDir, "transcript.jsonl"), "utf8").split("\n")[0]).prompt;
  assert.ok(prompt.includes(shellCommand(["warm-start", fake.runDir, history, "--candidate", "cand_old"])));
  assert.match(prompt, /Do not call confirm or final/);
  assert.equal(calls.some((args) => ["history", "warm-start", "eval", "confirm", "final"].includes(args[1])), false);
});

test("explicit historical storage is protected from transcript aliases before fake SDK starts", (t) => {
  const fake = fakeDriver(t);
  const history = path.join(fake.root, "external/history");
  fs.mkdirSync(history, { recursive: true });
  const state = path.join(history, "state.json");
  fs.writeFileSync(state, '{"historical":"untouched"}');
  const alias = path.join(fake.root, "trace.jsonl");
  fs.symlinkSync(state, alias);
  const result = fake.invoke(["--history-run", history, "--transcript-path", alias]);
  assert.equal(result.status, 3, result.stderr);
  assert.match(result.stderr, /protected run storage/);
  assert.equal(fs.existsSync(path.join(fake.root, "model-started")), false);
  assert.equal(fs.readFileSync(state, "utf8"), '{"historical":"untouched"}');
});
