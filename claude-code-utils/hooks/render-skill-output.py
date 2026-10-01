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
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11/styles/github.min.css">
<style>
body{{background:#f6f8fa}}
.markdown-body{{max-width:980px;margin:32px auto;padding:32px 40px;background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
.markdown-body h1{{color:#0969da;border-bottom:3px solid #0969da}}
.markdown-body h2{{color:#8250df;border-bottom:2px solid #d8b9ff;padding-left:10px;border-left:5px solid #8250df}}
.markdown-body h3{{color:#1a7f37}}
.markdown-body strong{{color:#953800}}
.markdown-body a{{color:#0969da}}
.markdown-body :not(pre)>code{{background:#ddf4ff;color:#0550ae;border-radius:4px}}
.markdown-body pre{{border-left:4px solid #54aeff;background:#f6f8fa}}
.markdown-body blockquote{{border-left-color:#bf8700;background:#fff8c5;color:#4d2d00;padding:8px 16px;border-radius:0 6px 6px 0}}
.markdown-body table th{{background:#ddf4ff;color:#0a3069}}
.markdown-body table tr:nth-child(2n){{background:#f6f8fa}}
.markdown-body h3.sev-critical{{color:#cf222e}}
.markdown-body h3.sev-important{{color:#bc4c00}}
.markdown-body h3.sev-minor{{color:#0969da}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;color:#fff;font-weight:600}}
.risk-low{{background:#1a7f37}}.risk-medium{{background:#bf8700}}.risk-high{{background:#bc4c00}}.risk-critical{{background:#cf222e}}
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
