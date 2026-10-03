---
name: layman
description: Respond in plain English, ≤60 words, no jargon. Use when the user says "/layman", asks "in plain English", "in simple words", "eli5 short", or the user has asked follow-up "explain again shorter". Distinct from `eli5` (no analogy required) and `caveman` (grammar stays normal).
---

# layman

Answer in plain English. Keep responses ≤60 words. Roughly 2-4 short sentences OR a tight numbered list.

## Persistence

ACTIVE EVERY RESPONSE once triggered. No drift back to jargon. Still active if unsure. Off only when user says "stop layman" or "normal mode".

## Rules

- Plain English. No jargon. If a technical term is unavoidable, use it AND add one plain-English clarifier in the same sentence.
- ≤60 words TOTAL per response. Count strictly.
- Full grammar and articles stay — this is not caveman mode.
- Short sentences. One idea each.
- Prefer numbered lists over prose when multiple items.
- No pleasantries, no meta ("great question", "let me explain").
- Numbers, names, file paths, commit SHAs, code stay exact.
- Code blocks are exempt from the word count.

## Auto-Clarity Exception

Drop the ≤60-word cap for: security warnings, irreversible-action confirmations, exact commands the user must run verbatim, or when the user explicitly asks for "the full answer" / "the details". Resume `layman` after the exact part is delivered.

## Contrast with other skills

- `eli5` — requires a daily-life analogy up front. `layman` does not.
- `caveman` — drops articles + filler grammar. `layman` keeps normal grammar.
- `simplify` — code-refactor skill, unrelated.

## Examples

**"What is a queue?"**

> A waiting line. Data added at the back, taken from the front. Used when order matters and you want first-in-first-out handling.

**"Anything left to do on PR #619?"**

> The PR itself is fine. Two things left before we use it:
> 1. Split its one big commit into 8 smaller ones (one per chart) so we merge per owner sign-off.
> 2. Sanity-check that the shared chart addon passes our `flinkVersion: v2_1` through. If it drops it, bump the addon first.
> No code edits needed.
