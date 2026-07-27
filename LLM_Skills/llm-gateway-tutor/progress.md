# Progress Tracker

Update after every session. Do not advance a step until its artifact exists,
the self-check is answered, Q&A is appended to `qa-phase-0.md` / `qa-phase-1.md`,
and the reference-repo mapping is appended to `reference-repo.md`.

- **Current step:** Phase 1 — Day 1 (next). Phase 0 complete.
- **Started:** 2026-07-25
- **Target pace:** ~1.5–2 hrs/day
- **Rule:** finish Phase 0 (F1–F3) before any Phase 1 (LLM) day.

## Log — Phase 0: Gateway Foundations

| Step | Topic | Status | Artifact | Got wrong / follow-ups |
|------|-------|--------|----------|------------------------|
| F1 | What a gateway is (middle boxes) | ✅ done 2026-07-25 | ASCII/whiteboard diagram of gateway hop w/ 8 responsibilities | Reverse proxy shallow (thought "hide origin" was core; real core = one front door + TLS/routing/cache). LB≠only-stateless (sticky sessions exist; L4 vs L7 is real axis). "When not needed" answered too generically — real cases: single-svc/single-client, mesh covers east-west, ultra-low-latency budget, no external clients. |
| F2 | Industry landscape (data/control plane) | ✅ done 2026-07-25 | Comparison table (NGINX/Envoy/Kong/AWS API GW/Istio) — teacher-built, learner defended | Didn't know *why* DP/CP split matters operationally (hot-reload no-downtime + blast-radius isolation + independent scaling). Didn't know Istio Ingress Gateway exists; mesh vs API gateway overlap unclear. Weak on managed-vs-self-hosted tradeoffs (custom plugins, air-gap, cost inflection). Revisit: xDS internals, when mesh Ingress replaces edge gateway. |
| F3 | Design & build a gateway from scratch | ✅ done 2026-07-26 | Pipeline diagram (Excalidraw) + ASCII spec of 2 routes, 2 chains, orders-svc cluster w/ health check, timeouts, retry policy | Initially thought gateway was one black box; couldn't enumerate stages. Conflated TLS termination with authN/Z. Missed rate-limit-counter horizontal-scale correctness issue (fleet + local counter = N× intended limit). Health-check answer shallow — didn't know active vs passive vs circuit-breaker distinction. Stateful/stateless split too generic. |

## Log — Phase 1: LLM Gateways

| Day | Topic | Status | Artifact | Got wrong / follow-ups |
|-----|-------|--------|----------|------------------------|
| 1 | What an LLM Gateway is | ⬜ not started | — | — |
| 2 | Design principles in gateway context | ⬜ | — | — |
| 3 | Provider abstraction layer | ⬜ | — | — |
| 4 | Routing & reliability | ⬜ | — | — |
| 5 | Streaming | ⬜ | — | — |
| 6 | Rate limiting, quotas, token budgeting | ⬜ | — | — |
| 7 | Caching | ⬜ | — | — |
| 8 | Security, governance, guardrails | ⬜ | — | — |
| 9 | Observability & evaluation | ⬜ | — | — |
| 10 | Capstone | ⬜ | — | — |

## Open threads / weak spots

- (none yet)
