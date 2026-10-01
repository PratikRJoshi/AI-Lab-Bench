#!/usr/bin/env python3
"""Stop hook: render the final answer of /review, /code-walkthrough, /describing-pr-files as HTML."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILLS = {"review", "code-walkthrough", "describing-pr-files"}
OUT_DIR = Path.home() / ".claude" / "rendered-outputs"
CMD_RE = re.compile(r"<command-name>/?([\w:-]+)</command-name>")

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.min.css">
<link rel="stylesheet" media="(prefers-color-scheme: light)" href="https://cdn.jsdelivr.net/npm/highlight.js@11/styles/github.min.css">
<link rel="stylesheet" media="(prefers-color-scheme: dark)" href="https://cdn.jsdelivr.net/npm/highlight.js@11/styles/monokai.min.css">
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
</style>
</head><body><article class="markdown-body" id="out"></article>
<script type="text/markdown" id="src">
{body}
</script>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/common.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
<script>
const out = document.getElementById('out');
out.innerHTML = DOMPurify.sanitize(marked.parse(document.getElementById('src').textContent));
out.querySelectorAll('pre code').forEach(b => hljs.highlightElement(b));
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
    for e in turn:
        if e.get("type") == "assistant":
            for b in blocks(e):
                if b.get("type") == "tool_use" and b.get("name") == "Skill":
                    names.add(skill_of(str((b.get("input") or {}).get("skill", ""))))
    hit = names & SKILLS
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
    body = "\n\n".join(texts).replace("</script", "<\\/script")

    skill = sorted(hit)[0]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{skill}-{time.strftime('%Y%m%d-%H%M%S')}.html"
    out.write_text(HTML.format(title=f"/{skill}", body=body), encoding="utf-8")
    subprocess.run(["open", str(out)], check=False)
    print(json.dumps({"systemMessage": f"Rendered /{skill} output: {out}"}))


if __name__ == "__main__":
    main()
