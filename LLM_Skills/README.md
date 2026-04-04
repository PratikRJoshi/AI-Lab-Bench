# LLM Skills

AI agent skills for [Cursor](https://cursor.sh) — structured instruction sets that give AI coding assistants domain-specific capabilities beyond general programming.

## Skills

| Skill | What it does | Key capabilities |
|-------|-------------|-----------------|
| [url-truth-analyzer](./url-truth-analyzer/) | Fact-checks health and science claims in social media content | Transcribes video/audio (Whisper), extracts text from images (OCR + vision), classifies content, applies EBM SORT grading for medical claims, validates science claims against peer-reviewed sources |

### url-truth-analyzer at a glance

- **51 analyses** produced across YouTube, Instagram, Facebook, LinkedIn, and local screenshot folders
- **Supports**: videos, reels, shorts, image carousels, DASH streams, local folders (recursive up to 5 levels)
- **Medical content**: graded using EBM SORT taxonomy (A/B/C) with safety, outcomes, bias, and total-evidence lenses
- **General science**: claim-by-claim validation with credible sources (PubMed, Cochrane, fact-checkers)
- **Rate-limited**: built-in delays, exponential backoff, and batch cooldowns to avoid platform bans
- **Automated pipeline**: `LLM_Skills/watch_urls.md` → download → transcribe → classify → analyze → save → git push

See the [full README](./url-truth-analyzer/README.md) for details.

## Usage

These skills are designed for Cursor's `.cursor/skills/` directory:

```bash
# Copy a skill into your Cursor skills folder
cp -r url-truth-analyzer ~/.cursor/skills/

# Then in Cursor, the agent will automatically pick up the skill
# when you mention relevant tasks (e.g., "analyze this URL", "process watch_urls.md")
```

Each skill contains a `SKILL.md` that the agent reads at invocation time — it defines the full workflow, commands, error handling, and output formats.
