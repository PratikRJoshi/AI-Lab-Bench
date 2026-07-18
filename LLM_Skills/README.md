# LLM Skills

AI agent skills for [Cursor](https://cursor.sh) — structured instruction sets that give AI coding assistants domain-specific capabilities beyond general programming.

## Skills

| Skill | What it does | Key capabilities |
|-------|-------------|-----------------|
| [url-truth-analyzer](./url-truth-analyzer/) | Fact-checks health and science claims in social media content | Transcribes video/audio (Whisper), extracts text from images (OCR + vision), classifies content, applies EBM SORT grading for medical claims, validates science claims against peer-reviewed sources |
| [price-compare](./price-compare/) | Compare prices across 7 online grocery sources using a browser MCP | Amazon.com, Amazon Fresh, Whole Foods, Walmart.com, Walmart Groceries, Costco, Safeway. Per-site playbooks handle login walls, ZIP-based store selection, and price-node extraction via accessibility trees. Output: per-item tables sorted cheapest→most-expensive plus a basket-total summary. |
| [price-compare-fetch](./price-compare-fetch/) | Best-effort price comparison via WebFetch when browser MCP is unavailable | Fallback for sandboxed environments where retail domains aren't on the browser MCP allowlist. Covers Amazon.com and Walmart.com only; honestly flags blocked / CAPTCHA'd requests rather than fabricating prices. Prefer `price-compare` when a real browser MCP is available. |
| [llm-gateway-tutor](./llm-gateway-tutor/) | Socratic mentor for learning to design and build LLM Gateways | Runs a 10-day plan (provider abstraction, routing/fallbacks, streaming, token budgeting, semantic caching, guardrails, observability) framed as deltas from an engineer's existing API-gateway/Kafka/OTel background. Includes a standalone `teacher-prompt.md` and a `progress.md` tracker; teaches via targeted questions rather than handing over answers. |

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
