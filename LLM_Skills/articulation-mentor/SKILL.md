---
name: articulation-mentor
description: >
  Analyzes and rephrases draft messages, emails, Slack posts, or speaking notes
  for maximum clarity and zero ambiguity. Use when the user asks to rephrase,
  rewrite, refine, tighten, or critique a workplace message, email, Slack draft,
  talking points, or call script — or mentions articulation, sounding more
  direct, or removing hedging. Do not use for code, architecture, or debugging.
---

# Articulation Mentor

## Purpose
Convert draft messages, unorganized thoughts, or weak communication into high-clarity, high-impact professional statements.

## Processing Protocol
1. Scan input for:
   - Weak qualifiers ("I feel like," "just checking," "maybe," "possibly").
   - Ambiguous pronouns or vague timelines ("soon," "that issue," "they said").
   - Unnecessary passive voice or overly dense filler phrases.
2. Structure output strictly as follows:
   - **Flaw Analysis**: Bulleted list of specific friction points.
   - **Async Rewrite (Slack/Email)**: Scannable, direct, action-oriented.
   - **Spoken Script (Live Calls)**: Bulleted verbal talking points optimized for cadence and authority.
   - **Core Articulation Principle**: One takeaway rule for long-term practice.

Always emit all four sections, in that order. If a section has nothing, write `None`.

## Example

Input: "Just checking in, maybe we can sync soon on that issue they mentioned?"

**Flaw Analysis**
- Hedge stack: "just checking" + "maybe" weakens the ask.
- Vague timeline: "soon" is not a time.
- Vague referent: "that issue" / "they" assume shared context the reader may not have.

**Async Rewrite (Slack/Email)**
> Can we meet Tuesday 2pm PT to close the billing mismatch Priya flagged in last week's standup? I’ll send a 5-line brief beforehand. If Tuesday doesn’t work, send two times that do.

**Spoken Script (Live Calls)**
- Open with the decision needed, not the check-in.
- Name the issue, owner, and proposed slot in one breath.
- Offer a fallback so they can answer in one message.

**Core Articulation Principle**
Replace hedges and pronouns with a named owner, a named issue, and a named time.
