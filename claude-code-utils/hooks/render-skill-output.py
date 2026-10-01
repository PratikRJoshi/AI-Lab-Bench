#!/usr/bin/env python3
"""Stop hook: render the final answer of /review, /code-walkthrough, /describing-pr-files as HTML."""
import html
import json
import re
import subprocess
import tempfile
import sqlite3
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

SKILLS = {"review", "code-walkthrough", "describing-pr-files"}
OUT_DIR = Path.home() / ".claude" / "rendered-outputs"
CMD_RE = re.compile(r"<command-name>/?([\w:-]+)</command-name>")

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.min.css">
<link rel="stylesheet" media="(prefers-color-scheme: light)" href="https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11/styles/github.min.css">
<link rel="stylesheet" media="(prefers-color-scheme: dark)" href="https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11/styles/monokai.min.css">
<style>
:root{{color-scheme:light dark;
  --page:#f6f8fa;--card:#fff;--text:#1f2328;--muted:#59636e;--border:#d1d9e0;
  --h1:#0969da;--h2:#8250df;--h2line:#d8b9ff;--h3:#1a7f37;--strong:#953800;--link:#0969da;
  --code-bg:#ddf4ff;--code:#0550ae;--pre-bg:#f6f8fa;--pre-line:#54aeff;
  --quote-bg:#fff8c5;--quote:#4d2d00;--quote-line:#bf8700;--th-bg:#ddf4ff;--th:#0a3069;--row:#f6f8fa;
  --crit:#cf222e;--imp:#bc4c00;--minor:#0969da;
  --b-low:#1a7f37;--b-med:#bf8700;--b-high:#bc4c00;--b-crit:#cf222e;--b-text:#fff}}
@media (prefers-color-scheme: dark){{:root{{
  --page:#1e1f1c;--card:#272822;--text:#f8f8f2;--muted:#a59f85;--border:#49483e;
  --h1:#f92672;--h2:#a6e22e;--h2line:#49483e;--h3:#66d9ef;--strong:#fd971f;--link:#66d9ef;
  --code-bg:#3e3d32;--code:#e6db74;--pre-bg:#2d2e27;--pre-line:#ae81ff;
  --quote-bg:#3e3d32;--quote:#f8f8f2;--quote-line:#e6db74;--th-bg:#3e3d32;--th:#66d9ef;--row:#2d2e27;
  --crit:#f92672;--imp:#fd971f;--minor:#66d9ef;
  --b-low:#a6e22e;--b-med:#e6db74;--b-high:#fd971f;--b-crit:#f92672;--b-text:#272822}}}}
body{{background:var(--page)}}
.markdown-body{{max-width:980px;margin:32px auto;padding:32px 40px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.15);
  background:var(--card);color:var(--text)}}
.markdown-body p,.markdown-body li,.markdown-body td{{color:var(--text)}}
.markdown-body hr,.markdown-body table td,.markdown-body table th{{border-color:var(--border)}}
.markdown-body h1{{color:var(--h1);border-bottom:3px solid var(--h1)}}
.markdown-body h2{{color:var(--h2);border-bottom:2px solid var(--h2line);padding-left:10px;border-left:5px solid var(--h2)}}
.markdown-body h3{{color:var(--h3)}}
.markdown-body strong{{color:var(--strong)}}
.markdown-body a{{color:var(--link)}}
.markdown-body :not(pre)>code{{background:var(--code-bg);color:var(--code);border-radius:4px}}
.markdown-body pre,.markdown-body pre code.hljs{{background:var(--pre-bg)}}
.markdown-body pre{{border-left:4px solid var(--pre-line)}}
.markdown-body blockquote{{border-left-color:var(--quote-line);background:var(--quote-bg);color:var(--quote);padding:8px 16px;border-radius:0 6px 6px 0}}
.markdown-body table tr{{background:var(--card)}}
.markdown-body table tr:nth-child(2n){{background:var(--row)}}
.markdown-body table th{{background:var(--th-bg);color:var(--th)}}
.markdown-body h3.sev-critical{{color:var(--crit)}}
.markdown-body h3.sev-important{{color:var(--imp)}}
.markdown-body h3.sev-minor{{color:var(--minor)}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;color:var(--b-text);font-weight:600}}
.risk-low{{background:var(--b-low)}}.risk-medium{{background:var(--b-med)}}.risk-high{{background:var(--b-high)}}.risk-critical{{background:var(--b-crit)}}
.tok-fn{{color:#8250df}}.tok-attr{{color:#953800}}.tok-type{{color:#0550ae;font-style:italic}}.tok-op{{color:#cf222e}}.markdown-body .tok-ln{{color:#8c959f;user-select:none}}
@media (prefers-color-scheme: dark){{.tok-fn{{color:#a6e22e}}.tok-attr{{color:#fd971f}}.tok-type{{color:#66d9ef}}.tok-op{{color:#f92672}}.markdown-body .tok-ln{{color:#75715e}}}}
html{{scroll-behavior:smooth}}.markdown-body h1,.markdown-body h2,.markdown-body h3{{scroll-margin-top:16px}}
.markdown-body a.file-link{{text-decoration:none}}.markdown-body a.file-link code{{border-bottom:1px dashed currentColor}}
.markdown-body a.file-link:hover code{{filter:brightness(1.25)}}
.markdown-body .back-link{{font-size:.55em;font-weight:400;margin-left:12px;color:var(--muted);text-decoration:none}}
.markdown-body .back-link:hover{{color:var(--link)}}
.note-box{{margin:12px 0 28px;padding:10px 12px;border:1px dashed var(--border);border-radius:8px;background:var(--row)}}
.note-box label{{display:block;font-size:12px;color:var(--muted);margin-bottom:6px}}
.note-box textarea{{width:100%;min-height:56px;resize:vertical;overflow:hidden;box-sizing:border-box;background:var(--card);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:8px 10px;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.note-box textarea:focus{{outline:2px solid var(--link);outline-offset:1px}}
.notes-bar{{position:fixed;top:12px;right:16px;z-index:10;display:flex;gap:8px;align-items:center;padding:6px 10px;border-radius:8px;background:var(--card);color:var(--muted);border:1px solid var(--border);box-shadow:0 2px 10px rgba(0,0,0,.2);font:13px -apple-system,sans-serif}}
.notes-bar button{{cursor:pointer;border:0;border-radius:6px;padding:5px 10px;font-weight:600;background:var(--h2);color:var(--b-text)}}
.notes-bar button:hover{{filter:brightness(1.1)}}
.markdown-body{{max-width:1360px}}
.section-row{{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:28px;align-items:start}}
.section-notes .note-box{{position:sticky;top:64px;margin:6px 0 24px}}
@media (max-width:1100px){{.section-row{{display:block}}.section-notes .note-box{{position:static;margin:12px 0 28px}}}}
.note-answer{{margin:18px 0 10px;padding:12px 18px;border-left:4px solid var(--h3);background:var(--row);border-radius:0 8px 8px 0}}
.note-answer-label{{font-weight:700;color:var(--h3);margin-bottom:8px;font-size:15px}}
.note-box .answer-link{{display:inline-block;margin-top:8px;font-size:12px;font-weight:600;color:var(--h3);text-decoration:none}}
.source-banner{{margin:0 0 24px;padding:10px 14px;border:1px solid var(--border);border-left:4px solid var(--h1);border-radius:8px;background:var(--row);font-size:13px;line-height:1.7}}
.source-banner .k{{display:inline-block;min-width:96px;color:var(--muted);font-weight:600}}
.source-banner .v{{color:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-all}}
.source-banner a.v{{color:var(--link)}}
</style>
</head><body><article class="markdown-body" id="out"></article>
<script type="text/markdown" id="src">
{body}
</script>
<script type="application/json" id="answers">{answers}</script>
<script type="application/json" id="meta">{meta}</script>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11/highlight.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
<script>
const out = document.getElementById('out');
out.innerHTML = DOMPurify.sanitize(marked.parse(document.getElementById('src').textContent));
const TOKENS = /([A-Za-z_]\\w*)(?=\\s*\\()|(?<=\\.)([A-Za-z_]\\w*)|\\b([A-Z][A-Za-z0-9_]*)\\b|([=+\\-*/<>!%&|^~]+)/g;
function enrich(code) {{
  code.querySelectorAll('.hljs-number').forEach(n => {{
    const prev = n.previousSibling, next = n.nextSibling;
    const atLineStart = !prev || (prev.nodeType === 3 && /(^|\\n)[ \\t]*$/.test(prev.textContent));
    if (atLineStart && next && next.nodeType === 3 && /^ {{2,}}/.test(next.textContent)) n.classList.add('tok-ln');
  }});
  [...code.childNodes].filter(n => n.nodeType === 3).forEach(t => {{
    const s = t.textContent, matches = [...s.matchAll(TOKENS)];
    if (!matches.length) return;
    const frag = document.createDocumentFragment();
    let last = 0;
    for (const m of matches) {{
      if (m.index > last) frag.append(s.slice(last, m.index));
      const span = document.createElement('span');
      span.className = m[1] ? 'tok-fn' : m[2] ? 'tok-attr' : m[3] ? 'tok-type' : 'tok-op';
      span.textContent = m[0];
      frag.append(span);
      last = m.index + m[0].length;
    }}
    if (last < s.length) frag.append(s.slice(last));
    t.replaceWith(frag);
  }});
}}
if (window.hljs) out.querySelectorAll('pre code').forEach(b => {{ hljs.highlightElement(b); enrich(b); }});

const FILE_RE = /[\\w.\\-\\/]+\\.[A-Za-z0-9]+/;
const baseName = s => s.split('/').pop().toLowerCase();
const usedIds = new Set();
const sectionFor = new Map();
out.querySelectorAll('h1, h2, h3').forEach(h => {{
  let id = h.textContent.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'section';
  for (let i = 2; usedIds.has(id); i++) id = id.replace(/-\\d+$/, '') + '-' + i;
  usedIds.add(id);
  h.id = id;
  const m = h.textContent.match(FILE_RE);
  if (h.tagName === 'H3' && m && !sectionFor.has(baseName(m[0]))) sectionFor.set(baseName(m[0]), h);
}});
const linkedSections = new Set();
out.querySelectorAll('li').forEach(li => {{
  const code = li.querySelector('code');
  const m = code && code.textContent.match(FILE_RE);
  const target = m && sectionFor.get(baseName(m[0]));
  if (!target || code.closest('a') || !(li.compareDocumentPosition(target) & Node.DOCUMENT_POSITION_FOLLOWING)) return;
  const list = li.closest('ul, ol');
  if (!list.id) {{ list.id = 'files-' + usedIds.size; usedIds.add(list.id); }}
  const a = document.createElement('a');
  a.href = '#' + target.id;
  a.className = 'file-link';
  code.replaceWith(a);
  a.appendChild(code);
  if (!linkedSections.has(target)) {{
    linkedSections.add(target);
    const back = document.createElement('a');
    back.href = '#' + list.id;
    back.className = 'back-link';
    back.textContent = '↑ back to files';
    target.appendChild(back);
  }}
}});
out.querySelectorAll('h3').forEach(h => {{
  const m = h.textContent.match(/^(Critical|Important|Minor)/i);
  if (m) h.classList.add('sev-' + m[1].toLowerCase());
}});
out.querySelectorAll('h2').forEach(h => {{
  const m = h.textContent.match(/^(Risk Level|Recommendation):\\s*(.+)$/i);
  if (!m) return;
  const v = m[2].trim(), k = v.toLowerCase();
  const cls = m[1].toLowerCase().startsWith('risk') ? 'risk-' + k
    : k.startsWith('approve') ? 'risk-low' : k.startsWith('request') ? 'risk-critical' : 'risk-medium';
  const badge = document.createElement('span');
  badge.className = 'badge ' + cls;
  badge.textContent = v;
  h.textContent = m[1] + ': ';
  h.appendChild(badge);
}});
const SRC_TEXT = document.getElementById('src').textContent;
const ANSWERS = JSON.parse((document.getElementById('answers') || {{}}).textContent || '{{}}');
let pageHash = 0;
for (const ch of SRC_TEXT) pageHash = (pageHash * 31 + ch.charCodeAt(0)) | 0;
const noteKey = id => 'claude-notes:' + pageHash + ':' + id;
const headingText = h => [...h.childNodes]
  .filter(n => !(n.classList && n.classList.contains('back-link')))
  .map(n => n.textContent).join('').trim();
const noteHeads = [...out.querySelectorAll('h2, h3')];
const countEl = document.createElement('span');
const refreshCount = () => {{
  const n = noteHeads.filter(h => (localStorage.getItem(noteKey(h.id)) || '').trim()).length;
  countEl.textContent = n + (n === 1 ? ' note' : ' notes');
}};
noteHeads.forEach(h => {{
  let end = h;
  while (end.nextElementSibling && !/^H[1-3]$/.test(end.nextElementSibling.tagName)) end = end.nextElementSibling;
  const box = document.createElement('div');
  box.className = 'note-box';
  const label = document.createElement('label');
  label.textContent = 'Notes: ' + headingText(h);
  const ta = document.createElement('textarea');
  ta.placeholder = 'Your notes or follow-up questions about this section...';
  ta.value = localStorage.getItem(noteKey(h.id)) || '';
  const grow = () => {{ ta.style.height = 'auto'; ta.style.height = Math.max(56, ta.scrollHeight) + 'px'; }};
  ta.addEventListener('input', () => {{
    if (ta.value.trim()) localStorage.setItem(noteKey(h.id), ta.value);
    else localStorage.removeItem(noteKey(h.id));
    grow(); refreshCount();
  }});
  box.append(label, ta);
  const row = document.createElement('div');
  row.className = 'section-row';
  const main = document.createElement('div');
  main.className = 'section-main';
  const aside = document.createElement('aside');
  aside.className = 'section-notes';
  const stop = end.nextElementSibling;
  h.before(row);
  for (let cur = h; cur && cur !== stop; ) {{ const next = cur.nextElementSibling; main.appendChild(cur); cur = next; }}
  aside.appendChild(box);
  row.append(main, aside);
  const ans = ANSWERS[h.id];
  if (ans) {{
    const ansBox = document.createElement('div');
    ansBox.className = 'note-answer';
    ansBox.id = h.id + '-answer';
    const ansLabel = document.createElement('div');
    ansLabel.className = 'note-answer-label';
    ansLabel.textContent = 'Answers to your notes';
    const ansBody = document.createElement('div');
    ansBody.innerHTML = DOMPurify.sanitize(marked.parse(ans));
    if (window.hljs) ansBody.querySelectorAll('pre code').forEach(b => {{ hljs.highlightElement(b); enrich(b); }});
    ansBox.append(ansLabel, ansBody);
    main.appendChild(ansBox);
    const jump = document.createElement('a');
    jump.href = '#' + ansBox.id;
    jump.className = 'answer-link';
    jump.textContent = 'Answered below';
    box.appendChild(jump);
  }}
  requestAnimationFrame(grow);
}});
const exportNotes = () => {{
  const title = (out.querySelector('h1, h2') || {{}}).textContent || document.title;
  const parts = ['# My notes on: ' + title.trim(), 'Rendered page: ' + decodeURIComponent(location.pathname), ''];
  noteHeads.forEach(h => {{
    const v = (localStorage.getItem(noteKey(h.id)) || '').trim();
    if (v) parts.push('## ' + headingText(h), v, '');
  }});
  return parts.join('\\n');
}};
const flash = (btn, text) => {{ const old = btn.textContent; btn.textContent = text; setTimeout(() => btn.textContent = old, 1500); }};
const bar = document.createElement('div');
bar.className = 'notes-bar';
const copyBtn = document.createElement('button');
copyBtn.textContent = 'Copy notes';
copyBtn.addEventListener('click', async () => {{
  const text = exportNotes();
  try {{ await navigator.clipboard.writeText(text); }}
  catch (e) {{
    const tmp = document.createElement('textarea');
    tmp.value = text; document.body.appendChild(tmp); tmp.select();
    document.execCommand('copy'); tmp.remove();
  }}
  flash(copyBtn, 'Copied');
}});
const dlBtn = document.createElement('button');
dlBtn.textContent = 'Download';
dlBtn.addEventListener('click', () => {{
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([exportNotes()], {{ type: 'text/markdown' }}));
  a.download = decodeURIComponent(location.pathname.split('/').pop()).replace(/\\.html$/, '') + '-notes.md';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}});
bar.append(countEl, copyBtn, dlBtn);
document.body.appendChild(bar);
refreshCount();
const META = JSON.parse((document.getElementById('meta') || {{}}).textContent || '{{}}');
if (META.command || META.source) {{
  const banner = document.createElement('div');
  banner.className = 'source-banner';
  const addRow = (label, value, href) => {{
    if (!value) return;
    const row = document.createElement('div');
    const key = document.createElement('span');
    key.className = 'k';
    key.textContent = label;
    const val = document.createElement(href ? 'a' : 'span');
    if (href) {{ val.href = href; val.target = '_blank'; val.rel = 'noopener'; }}
    val.className = 'v';
    val.textContent = value;
    row.append(key, val);
    banner.appendChild(row);
  }};
  const src = META.source || '';
  const srcHref = /^https?:\\/\\//.test(src) ? src : (src.startsWith('/') ? 'file://' + encodeURI(src) : null);
  addRow('Command', META.command);
  addRow('Source', src, srcHref);
  const rev = META.branch ? '(' + META.branch + (META.commit ? ' @ ' + META.commit : '') + ')' : '';
  addRow('Repository', [META.repo, rev].filter(Boolean).join(' '));
  addRow('Rendered', META.rendered);
  out.prepend(banner);
}}
</script></body></html>
"""


def blocks(entry):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def is_prompt(entry):
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    bs = blocks(entry)
    return bool(bs) and not any(b.get("type") == "tool_result" for b in bs)


def skill_of(name):
    return name.split(":")[-1]


def unsnappy(b: bytes) -> bytes:
    i = n = shift = 0
    while True:
        c = b[i]
        i += 1
        n |= (c & 0x7F) << shift
        shift += 7
        if c < 0x80:
            break
    out = bytearray()
    while i < len(b):
        tag = b[i]
        i += 1
        kind = tag & 3
        if kind == 0:
            ln = (tag >> 2) + 1
            if ln > 60:
                k = ln - 60
                ln = int.from_bytes(b[i : i + k], "little") + 1
                i += k
            out += b[i : i + ln]
            i += ln
            continue
        if kind == 1:
            ln, off = ((tag >> 2) & 7) + 4, ((tag >> 5) << 8) | b[i]
            i += 1
        elif kind == 2:
            ln, off = (tag >> 2) + 1, int.from_bytes(b[i : i + 2], "little")
            i += 2
        else:
            ln, off = (tag >> 2) + 1, int.from_bytes(b[i : i + 4], "little")
            i += 4
        for _ in range(ln):
            out.append(out[-off])
    return bytes(out)


def read_firefox_notes(page: Path) -> dict:
    # Firefox keys file:// storage per file path, with ':' and '/' replaced by '+'.
    origin = ("file://" + str(page.resolve())).replace(":", "+").replace("/", "+")
    profiles = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    notes = {}
    for db in profiles.glob(f"*/storage/default/{origin}/ls/data.sqlite"):
        tmp = Path(tempfile.mkdtemp()) / "data.sqlite"
        shutil.copy(db, tmp)
        wal = db.with_name("data.sqlite-wal")
        if wal.exists():
            shutil.copy(wal, tmp.with_name("data.sqlite-wal"))
        con = sqlite3.connect(tmp)
        rows = con.execute(
            "select key, compression_type, conversion_type, value from data where key like 'claude-notes:%'"
        )
        for key, comp, conv, val in rows:
            raw = unsnappy(val) if comp == 1 else val
            notes[key.split(":", 2)[2]] = raw.decode("utf-8" if conv == 1 else "utf-16-le")
        con.close()
    return notes


SRC_RE = re.compile(r'<script type="text/markdown" id="src">\n(.*?)\n</script>', re.S)
ANS_RE = re.compile(r'<script type="application/json" id="answers">(.*?)</script>', re.S)
META_RE = re.compile(r'<script type="application/json" id="meta">(.*?)</script>', re.S)
TITLE_RE = re.compile(r"<title>(.*?)</title>")
ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.S)


def git_info(path: Path) -> dict:
    folder = path if path.is_dir() else path.parent

    def git(*args):
        r = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""

    top = git("rev-parse", "--show-toplevel")
    if not top:
        return {}
    return {
        "repo": Path(top).name,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": git("rev-parse", "--short", "HEAD"),
    }


def describe_source(args: str, cwd: str) -> dict:
    """Short tab label plus the link or path that the page was generated from."""
    text = (args or "").strip()
    here = git_info(Path(cwd)) if cwd and Path(cwd).exists() else {}

    url = re.search(r"https?://[^\s)>\]]+", text)
    if url:
        link = url.group(0).rstrip(".,")
        parts = [p for p in urlsplit(link).path.split("/") if p]
        label = parts[-1] if parts else urlsplit(link).netloc
        for marker in ("pull", "pulls", "merge_requests"):
            if marker in parts and parts.index(marker) >= 1:
                i = parts.index(marker)
                number = parts[i + 1] if len(parts) > i + 1 else ""
                label = f"PR #{number} · {parts[i - 1]}"
                break
        else:
            for marker in ("blob", "tree"):
                if marker in parts and parts.index(marker) >= 1:
                    label = f"{parts[-1]} · {parts[parts.index(marker) - 1]}"
                    break
        return {"label": label, "source": link}

    path = re.search(r"@?(~?/\S+|\.{1,2}/\S+)", text)
    if path:
        raw = path.group(1)
        line_range = re.search(r":L?\d+(?:-L?\d+)?$", raw)
        target = Path(raw[: line_range.start()] if line_range else raw).expanduser()
        if not target.is_absolute() and cwd:
            target = Path(cwd) / target
        info = git_info(target) if target.exists() else {}
        name = (target.name or raw) + (line_range.group(0) if line_range else "")
        repo = info.get("repo")
        label = name if not repo or repo == name else f"{name} · {repo}"
        return {"label": label, "source": str(target), **info}

    repo = here.get("repo")
    if text:
        short = text if len(text) <= 48 else text[:47] + "…"
        return {"label": f"{short} · {repo}" if repo else short, "source": text, **here}
    return {"label": repo or "", "source": cwd or "", **here}


def page_title(meta: dict) -> str:
    label, command = meta.get("label", ""), meta.get("command", "")
    if label and command:
        return f"{label} — {command}"
    return label or command or "Claude output"


def build_page(markdown: str, answers: dict, meta: dict) -> str:
    return HTML.format(
        title=html.escape(page_title(meta)),
        body=markdown.replace("</script", "<\\/script"),
        answers=json.dumps(answers).replace("</", "<\\/"),
        meta=json.dumps(meta).replace("</", "<\\/"),
    )


def rebuild_page(page: Path, answers_update: dict = None, meta_update: dict = None) -> dict:
    """Re-render an existing page in place, keeping its path so saved notes stay attached."""
    text = page.read_text(encoding="utf-8")
    src = SRC_RE.search(text)
    if not src:
        sys.exit(f"No embedded markdown found in {page}")
    old_answers = ANS_RE.search(text)
    answers = json.loads(old_answers.group(1)) if old_answers and old_answers.group(1).strip() else {}
    answers.update(answers_update or {})
    old_meta = META_RE.search(text)
    meta = json.loads(old_meta.group(1)) if old_meta and old_meta.group(1).strip() else {}
    if not meta:
        title = TITLE_RE.search(text)
        meta = {"command": html.unescape(title.group(1)) if title else page.stem}
    meta.update(meta_update or {})
    markdown = src.group(1).replace("<\\/script", "</script")
    page.write_text(build_page(markdown, answers, meta), encoding="utf-8")
    return answers


def answer_page(page: Path, answers_file: Path) -> None:
    answers = rebuild_page(page, answers_update=json.loads(answers_file.read_text(encoding="utf-8")))
    print(f"Added {len(answers)} answers to {page}; reload the page to see them.")


def main():
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return
    path = payload.get("transcript_path")
    if not path or not Path(path).exists():
        return
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]

    start = next((i for i in range(len(rows) - 1, -1, -1) if is_prompt(rows[i])), None)
    if start is None:
        return
    turn = rows[start:]

    prompt_text = " ".join(b.get("text", "") for b in blocks(rows[start]) if b.get("type") == "text")
    names = {skill_of(m) for m in CMD_RE.findall(prompt_text)}
    args_match = ARGS_RE.search(prompt_text)
    args = args_match.group(1).strip() if args_match else ""
    for e in turn:
        if e.get("type") == "assistant":
            for b in blocks(e):
                if b.get("type") == "tool_use" and b.get("name") == "Skill":
                    tool_input = b.get("input") or {}
                    names.add(skill_of(str(tool_input.get("skill", ""))))
                    if not args and skill_of(str(tool_input.get("skill", ""))) in SKILLS:
                        args = str(tool_input.get("args", "")).strip()
    hit = names & SKILLS
    if payload.get("force"):
        hit = {payload.get("label") or "notes"}
    if not hit:
        return

    last_tool_result = max(
        (i for i, e in enumerate(turn) if e.get("type") == "user" and any(b.get("type") == "tool_result" for b in blocks(e))),
        default=0,
    )
    texts = [
        b["text"]
        for e in turn[last_tool_result:]
        if e.get("type") == "assistant"
        for b in blocks(e)
        if b.get("type") == "text" and b.get("text", "").strip()
    ]
    if not texts:
        return
    body = "\n\n".join(texts)

    skill = sorted(hit)[0]
    if payload.get("force"):
        args = payload.get("source") or args
    cwd = payload.get("cwd") or ""
    meta = {
        "command": f"/{skill}",
        "args": args,
        "cwd": cwd,
        **describe_source(args, cwd),
        "rendered": time.strftime("%Y-%m-%d %H:%M"),
    }
    if payload.get("title"):
        meta["label"] = payload["title"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{skill}-{time.strftime('%Y%m%d-%H%M%S')}.html"
    out.write_text(build_page(body, {}, meta), encoding="utf-8")
    subprocess.run(["open", str(out)], check=False)
    print(json.dumps({"systemMessage": f"Rendered /{skill} output: {out}"}))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--read-notes":
        print(json.dumps(read_firefox_notes(Path(sys.argv[2])), indent=1, ensure_ascii=False))
    elif len(sys.argv) == 4 and sys.argv[1] == "--answer":
        answer_page(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) == 4 and sys.argv[1] == "--set-source":
        rebuild_page(Path(sys.argv[2]), meta_update=json.loads(sys.argv[3]))
        print(f"Updated source details for {sys.argv[2]}")
    else:
        main()
