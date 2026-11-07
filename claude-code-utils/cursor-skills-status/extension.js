// Shows skills used since the last user prompt, read from the newest Cursor agent transcript.
const vscode = require("vscode");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PROJECTS = path.join(os.homedir(), ".cursor", "projects");
const TAIL_BYTES = 2_000_000;
const SKILL_PATH = /\/skills\/([^/]+)\/SKILL\.md$/;
const INLINED = /Skill Name: (\S+)/g;

const slug = (p) => p.replace(/^\/+/, "").replace(/[^A-Za-z0-9]+/g, "-");

function transcriptRoots() {
  const ws = vscode.workspace.workspaceFile?.scheme === "file"
    ? [vscode.workspace.workspaceFile.fsPath]
    : (vscode.workspace.workspaceFolders ?? []).map((f) => f.uri.fsPath);
  const roots = ws.map((p) => path.join(PROJECTS, slug(p), "agent-transcripts")).filter(fs.existsSync);
  return roots.length ? roots : [PROJECTS];
}

function newestTranscript(dir, depth = 0, best = { file: null, mtime: 0 }) {
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return best; }
  for (const e of entries) {
    const p = path.join(dir, e.name);
    if (e.isDirectory() && depth < 3) newestTranscript(p, depth + 1, best);
    else if (e.isFile() && e.name.endsWith(".jsonl")) {
      const m = fs.statSync(p).mtimeMs;
      if (m > best.mtime) Object.assign(best, { file: p, mtime: m });
    }
  }
  return best;
}

function readTail(file) {
  const fd = fs.openSync(file, "r");
  try {
    const size = fs.fstatSync(fd).size;
    const start = Math.max(0, size - TAIL_BYTES);
    const buf = Buffer.alloc(size - start);
    fs.readSync(fd, buf, 0, buf.length, start);
    const lines = buf.toString("utf8").split("\n");
    return start > 0 ? lines.slice(1) : lines;
  } finally { fs.closeSync(fd); }
}

function skillsSinceLastPrompt(file) {
  const found = [];
  for (const line of readTail(file).reverse()) {
    let entry;
    try { entry = JSON.parse(line); } catch { continue; }
    const parts = Array.isArray(entry.message?.content) ? entry.message.content : [];
    if (entry.role === "assistant") {
      for (const p of parts) {
        const m = p.type === "tool_use" && SKILL_PATH.exec(String(p.input?.path ?? p.input?.target_file ?? ""));
        if (m) found.push(m[1]);
      }
    } else if (entry.role === "user") {
      const text = parts.filter((p) => p.type === "text").map((p) => p.text).join("\n");
      for (const m of text.matchAll(INLINED)) found.push(m[1]);
      break;
    }
  }
  return [...new Set(found.reverse())];
}

function activate(context) {
  const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  item.command = "skillsStatus.refresh";
  context.subscriptions.push(item);

  const refresh = () => {
    try {
      let best = { file: null, mtime: 0 };
      for (const r of transcriptRoots()) best = newestTranscript(r, 0, best);
      const skills = best.file ? skillsSinceLastPrompt(best.file) : [];
      if (!skills.length) return item.hide();
      item.text = `$(extensions) ${skills.join(", ")}`;
      item.tooltip = `Skills used for the current prompt\n${best.file}`;
      item.show();
    } catch { item.hide(); }
  };

  let timer;
  const debounced = () => { clearTimeout(timer); timer = setTimeout(refresh, 300); };
  for (const r of transcriptRoots()) {
    try {
      const w = fs.watch(r, { recursive: true }, debounced);
      context.subscriptions.push({ dispose: () => w.close() });
    } catch { /* fall back to polling */ }
  }
  const poll = setInterval(refresh, 5000);
  context.subscriptions.push(
    { dispose: () => { clearInterval(poll); clearTimeout(timer); } },
    vscode.commands.registerCommand("skillsStatus.refresh", refresh),
    vscode.workspace.onDidChangeWorkspaceFolders(refresh),
  );
  refresh();
}

module.exports = { activate, deactivate() {} };
