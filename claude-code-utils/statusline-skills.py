#!/usr/bin/env python3
"""Print skills used since the last user prompt, read from the end of a Claude Code transcript."""
import json
import os
import sys

TAIL_BYTES = 2_000_000
NOT_PROMPTS = ("<system-reminder>", "<task-notification", "<local-command", "[Request interrupted")
SKILL_MARKER = "Base directory for this skill:"


def text_of(content) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return " ".join(parts) if parts else None
    return None


def skills_since_last_prompt(path: str) -> list[str]:
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - TAIL_BYTES))
        lines = f.read().decode("utf-8", "ignore").splitlines()[1:]

    found: list[str] = []
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (entry.get("message") or {}).get("content")
        if entry.get("type") == "assistant" and isinstance(content, list):
            for part in content:
                if part.get("type") == "tool_use" and part.get("name") == "Skill":
                    found.append(str((part.get("input") or {}).get("skill", "")))
        elif entry.get("type") == "user":
            text = text_of(content)
            if not text:
                continue
            if text.startswith(SKILL_MARKER):
                found.append(os.path.basename(text[len(SKILL_MARKER):].split()[0].rstrip("/")))
            elif not entry.get("isMeta") and not text.lstrip().startswith(NOT_PROMPTS):
                break

    by_short: dict[str, str] = {}
    for name in reversed(found):
        if not name:
            continue
        short = name.split(":")[-1]
        if len(name) > len(by_short.get(short, "")):
            by_short[short] = name
    return list(by_short.values())


if __name__ == "__main__":
    try:
        print(", ".join(skills_since_last_prompt(sys.argv[1])))
    except Exception:
        pass
