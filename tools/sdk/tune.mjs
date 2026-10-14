/** Cursor SDK driver for persistent, budgeted instruction-tuning runs. */
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { USAGE, parseArgs, initArgs, buildPrompt, finishRun, prepareSeed,
  recordProvenance, transcriptPaths } from "./run_workflow.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const PY = process.env.TESTFT_PYTHON ||
  (spawnSync("python3.8", ["--version"]).status === 0 ? "python3.8" : "python3");
let opts;
try { opts = parseArgs(process.argv.slice(2)); }
catch (error) { console.error(error.message); process.exit(2); }
if (opts.help) { console.log(USAGE); process.exit(0); }

function invoke(args, json = true) {
  const result = spawnSync(PY, args, { cwd: REPO, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  if (result.stderr) process.stderr.write(result.stderr);
  if (!json && result.stdout) process.stdout.write(result.stdout);
  let value;
  if (json && result.stdout) {
    try { value = JSON.parse(result.stdout); }
    catch { throw new Error(`Invalid JSON from ${args[0]}: ${result.stdout.slice(0, 1000)}`); }
  }
  if (result.error || result.status !== 0 || value?.error) {
    throw new Error(value?.error ? `${value.error.code}: ${value.error.message}` :
      value?.integrity_errors?.length ? `Report integrity errors: ${value.integrity_errors.join("; ")}; ${value.markdown_path}` :
      `${args[0]} failed (exit=${result.status}): ${result.error?.message || result.stderr || ""}`);
  }
  return value;
}

function config() {
  const filename = path.resolve(opts.config || path.join(HERE, "cursor.config.json"));
  let cfg = {};
  if (fs.existsSync(filename)) {
    if (fs.statSync(filename).mode & 0o077) console.error(`[tune] config should be chmod 600: ${filename}`);
    cfg = JSON.parse(fs.readFileSync(filename, "utf8"));
  }
  return { apiKey: process.env.CURSOR_API_KEY || cfg.apiKey, model: opts.model || cfg.model || "auto" };
}
function selectModel(model) {
  const [id, ...params] = model.split(",").map((s) => s.trim()).filter(Boolean);
  if (!id) throw new Error("Empty model ID");
  return { id, ...(params.length ? { params: params.map((param) => {
    const sep = param.indexOf("=");
    if (sep <= 0 || sep === param.length - 1) throw new Error(`Invalid model param: ${param}`);
    return { id: param.slice(0, sep), value: param.slice(sep + 1) };
  }) } : {}) };
}

const SAVE_TRANSCRIPT = opts.transcript;
let jsonlPath, mdPath;
const rawLine = (obj) => { if (SAVE_TRANSCRIPT && jsonlPath) fs.appendFileSync(jsonlPath, JSON.stringify(obj) + "\n"); };
const mdLine = (s) => { if (SAVE_TRANSCRIPT && mdPath) fs.appendFileSync(mdPath, s + "\n"); };
// The SDK streams assistant text and thinking token-by-token (one event per
// token). Writing a header per token shreds the .md into one-char sections, so
// we BUFFER consecutive same-kind deltas and flush them as a SINGLE block when
// the stream switches to another kind of event. (.jsonl stays faithful/full.)
let _pendKind = null;   // "text" | "thinking" | null
let _pendBuf = "";
function _flushPending() {
  if (_pendKind === "text" && _pendBuf) mdLine(`\n#### LLM 输出(文本)\n${_pendBuf}`);
  else if (_pendKind === "thinking" && _pendBuf) mdLine(`\n#### LLM 思考\n${_pendBuf}`);
  _pendKind = null;
  _pendBuf = "";
}
function _accum(kind, s) {
  if (!s) return;
  if (_pendKind && _pendKind !== kind) _flushPending();
  _pendKind = kind;
  _pendBuf += s;
}

/** Best-effort human-readable rendering of one SDK stream event into the .md.
 * The .jsonl is the faithful full record; this is for eyeballing. Streamed
 * text/thinking deltas are coalesced (see _accum/_flushPending). */
function renderEvent(ev) {
  const t = ev?.type;
  if (t === "assistant" && ev.message?.content) {
    for (const b of ev.message.content) {
      if (b.type === "text" && b.text) { _accum("text", b.text); process.stdout.write(b.text); }
      else if (b.type === "thinking" && (b.thinking || b.text)) _accum("thinking", b.thinking || b.text);
      else if (b.type === "tool_call" || b.name || b.toolName) { _flushPending(); mdLine(`\n#### LLM 工具调用(动作)\n\`\`\`json\n${JSON.stringify(b, null, 2)}\n\`\`\``); }
      else { _flushPending(); mdLine(`\n#### LLM 输出(其它块)\n\`\`\`json\n${JSON.stringify(b, null, 2)}\n\`\`\``); }
    }
  } else if (t === "thinking") {              // top-level streamed thinking delta
    _accum("thinking", ev.thinking || ev.text || "");
  } else if (t === "tool_call") {
    _flushPending();
    if (ev.status === "running") {
      mdLine(`\n#### LLM 工具调用(动作): ${ev.name}\n\`\`\`bash\n${ev.args?.command ?? JSON.stringify(ev.args)}\n\`\`\``);
    } else {
      const v = ev.result?.value ?? ev.result;
      const out = (v?.stdout || "") + (v?.stderr ? `\n[stderr]\n${v.stderr}` : "");
      mdLine(`\n#### 工具结果 -> 下一轮输入 (${ev.name}, exit=${v?.exitCode ?? "?"})\n\`\`\`\n${out.slice(0, 4000)}\n\`\`\``);
    }
  } else if (t === "user" && ev.message?.content) {
    _flushPending();
    mdLine(`\n#### 用户/工具消息 -> 下一轮输入\n\`\`\`json\n${JSON.stringify(ev.message.content, null, 2)}\n\`\`\``);
  } else if (t === "status") {
    _flushPending();   // RUNNING/FINISHED noise -> just a flush boundary
  } else if (t) {
    _flushPending();
    mdLine(`\n#### 事件: ${t}\n\`\`\`json\n${JSON.stringify(ev, null, 2)}\n\`\`\``);
  }
}

let agent, runDir;
let successful = false;
let stopping = false;
let interrupt;
const interrupted = new Promise((_, reject) => { interrupt = reject; });
const handlers = Object.fromEntries(["SIGINT", "SIGTERM"].map((signal) => [signal, () => {
  if (stopping) return;
  stopping = true;
  process.exitCode = signal === "SIGINT" ? 130 : 143;
  interrupt(new Error(`Interrupted by ${signal}; no automatic confirmation/final/recovery`));
}]));
for (const [signal, handler] of Object.entries(handlers)) process.on(signal, handler);

try {
  const client = invoke(["-m", "client", "resolve", opts.client]);
  const prepared = prepareSeed({ seed: opts.seed,
    inputsDir: path.join(client.out_dir, "sdk-inputs", opts["run-id"]), invoke });
  const policy = opts["comparison-policy"]
    ? JSON.parse(fs.readFileSync(opts["comparison-policy"], "utf8")) : null;
  const initialized = invoke(initArgs(opts, prepared.seed, policy));
  runDir = initialized.run_dir;
  console.error(`[tune] persistent run: ${runDir}`);
  recordProvenance(runDir, prepared, initialized.manifest);
  if (SAVE_TRANSCRIPT) {
    ({ jsonlPath, mdPath } = transcriptPaths({ runDir, transcriptPath: opts["transcript-path"],
      reportDir: opts["report-dir"], resultsPath: opts["results-path"],
      protectedDirs: [path.join(client.out_dir, "runs"), path.join(client.out_dir, "sdk-inputs"),
        ...(opts["history-run"] ? [path.resolve(opts["history-run"])] : [])] }));
    fs.mkdirSync(path.dirname(jsonlPath), { recursive: true });
    fs.mkdirSync(path.dirname(mdPath), { recursive: true });
  }
  const { apiKey, model } = config();
  if (!apiKey) {
    process.exitCode = 1;
    throw new Error("No API key. Set CURSOR_API_KEY or configure tools/sdk/cursor.config.json");
  }
  const modelSel = selectModel(model);
  const prompt = buildPrompt({ python: PY, repo: REPO, runDir, opts, manifest: initialized.manifest });
  // Dynamic import lets --help, init failure, and no-key reporting work without the SDK package.
  const { Agent } = await import("@cursor/sdk");
  await Promise.race([interrupted, (async () => {
    agent = await Agent.create({ apiKey, model: modelSel, local: { cwd: REPO } });
    rawLine({ ts: Date.now(), kind: "input_prompt", agentId: agent.agentId, runDir, model, prompt });
    mdLine(`# tune transcript\n- persistent run: ${runDir}\n- agent: ${agent.agentId}\n- model: ${model}\n\n## 初始提示词\n\`\`\`\n${prompt}\n\`\`\``);
    const run = await agent.send(prompt);
    console.error(`[tune] agent=${agent.agentId} sdk_run=${run.id}`);
    rawLine({ ts: Date.now(), kind: "run_started", runId: run.id });
    for await (const event of run.stream()) {
      rawLine({ ts: Date.now(), kind: "event", event });
      renderEvent(event);
    }
    _flushPending();
    const result = await run.wait();
    process.stdout.write("\n");
    rawLine({ ts: Date.now(), kind: "result", status: result.status, id: result.id });
    try {
      if (run.supports?.("conversation")) rawLine({ ts: Date.now(), kind: "conversation", conversation: await run.conversation() });
    } catch (error) { rawLine({ ts: Date.now(), kind: "conversation_error", error: error.message }); }
    successful = result.status === "finished";
    if (!successful) process.exitCode = 2;
    console.error(`[tune] SDK status: ${result.status}`);
  })()]);
} catch (error) {
  successful = false;
  console.error(`[tune] ${error?.stack || error}`);
  process.exitCode ||= error?.name === "CursorAgentError" ? 1 : 3;
} finally {
  // Stop the SDK before reading the run. A live controller lock may still reject
  // reporting after an interrupt; leave it pending rather than guessing recovery.
  let timer;
  await Promise.race([
    (async () => { try { await agent?.[Symbol.asyncDispose]?.(); } catch { /* best effort */ } })(),
    new Promise((resolve) => { timer = setTimeout(resolve, 8000); }),
  ]);
  clearTimeout(timer);
  if (runDir) {
    const reportArgs = [];
    if (opts["report-dir"]) reportArgs.push("--out", path.resolve(opts["report-dir"]));
    if (opts["results-path"]) reportArgs.push("--json-path", path.resolve(opts["results-path"]));
    const result = finishRun({ invoke, runDir, successful: successful && !stopping, reportArgs });
    if (result.report) console.error(`[tune] report: ${result.report.markdown_path}`);
    for (const error of result.errors) console.error(`[tune] ${error}`);
    if (result.errors.length) process.exitCode ||= 3;
  }
  for (const [signal, handler] of Object.entries(handlers)) process.off(signal, handler);
  process.exit(process.exitCode ?? 0);
}
