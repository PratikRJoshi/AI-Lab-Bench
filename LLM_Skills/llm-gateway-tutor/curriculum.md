# 10-Day LLM Gateway Learning Plan

~1.5–2 hrs/day. Built for an engineer who already owns API gateways (Istio/Envoy),
Kafka streaming, resilience (circuit breakers, rate limiting, load shedding),
multi-tenancy, K8s, and OpenTelemetry. Focus = the LLM-specific delta + design craft,
not re-teaching gateways.

Each day: **Hook** (connect to prior knowledge) → **Concept** → **Exercise** (artifact) → **Self-check**.

---

## Day 1 — What an LLM Gateway is, and why

- **Concept:** An LLM Gateway is an API gateway specialized for model traffic:
  unified API over many providers, routing/fallback, key management, quotas/cost,
  caching, guardrails, observability. It sits between apps and providers
  (OpenAI, Anthropic, Bedrock, Gemini, self-hosted).
- **Hook:** How is this the same as / different from an Envoy/Istio ingress gateway?
  What does "the backend is a probabilistic, expensive, rate-limited, streaming
  API you don't control" change?
- **Study:** LiteLLM, Portkey, Kong AI Gateway, Cloudflare AI Gateway, Envoy AI
  Gateway — skim docs/architecture pages.
- **Exercise:** One-page comparison table of 4 gateways (axes: provider abstraction,
  routing, caching, rate/cost control, guardrails, observability, deploy model).
- **Self-check:** What problems does a gateway solve that an SDK in each app can't?
  What does it centralize? What new single-point-of-failure does it create?

## Day 2 — Design principles in gateway context

- **Concept:** SOLID / separation of concerns / dependency inversion applied to a
  provider-agnostic core. The core should depend on an abstraction (`LLMProvider`),
  not concrete SDKs. Ports & adapters (hexagonal) fits perfectly.
- **Hook:** Where did you last use an interface to avoid vendor lock-in?
  (Telemetry Exporter / OTel collector receivers — reuse that instinct.)
- **Exercise:** Design the **unified request/response schema** — one canonical
  chat request + response that every provider maps to/from. List the fields that
  don't cleanly generalize (tool-calling, system prompts, stop reasons, usage).
- **Self-check:** Which is your stable core vs. volatile edge? Where do you put the
  "leaky" provider quirks so they don't leak into the core?

## Day 3 — Provider abstraction layer

- **Concept:** Adapter + Strategy. Each provider is an adapter translating the
  canonical schema to its wire format and back. Normalize: auth, endpoints,
  message roles, tool/function-calling formats, streaming chunk shapes, error
  taxonomy, token-usage reporting.
- **Hook:** This is your custom OTel Kafka receiver pattern — pluggable inputs to a
  common pipeline. What's the equivalent of the "common pipeline" here?
- **Exercise:** Write the `LLMProvider` interface + a pseudo-adapter for two
  providers with genuinely different tool-calling formats. Show the mapping table.
- **Self-check:** How do you version the canonical schema without breaking adapters?
  What happens when a provider adds a field yours doesn't model?

## Day 4 — Routing & reliability

- **Concept:** Model/provider routing, weighted load balancing, fallback chains,
  retries w/ jittered backoff, timeouts, circuit breakers, request hedging.
  LLM twist: routing is **cost-, latency-, and capability-aware**; fallbacks must
  preserve semantics; retries risk double-billing and duplicate side effects.
- **Hook:** You built latency-based circuit breakers + load shedding for 3M events/min.
  What transfers directly? What breaks because responses are non-idempotent,
  seconds-long, and token-metered?
- **Exercise:** Design a routing policy: primary → fallback across 2 providers with
  health checks, budget cap, and a "don't retry a partially-streamed response" rule.
- **Self-check:** When is a fallback to a weaker model worse than failing? How do
  you make retries safe when the first attempt may have already streamed tokens?

## Day 5 — Streaming

- **Concept:** SSE / chunked transfer, token-by-token streaming, backpressure,
  client cancellation propagating to the provider (to stop billing), mid-stream
  failures and partial results, buffering vs. pass-through.
- **Hook:** Map this to Kafka streaming + backpressure — where's the consumer lag
  analogue? Where does the analogy break (no replay, one-shot stream)?
- **Exercise:** Sequence diagram of a streamed request through the gateway,
  including cancel and mid-stream provider error → fallback decision.
- **Self-check:** Can you fall back to another provider after 200 tokens already
  streamed to the client? What do you do instead? How is cost counted on a cancel?

## Day 6 — Rate limiting, quotas, token budgeting, cost

- **Concept:** RPM/TPM limits (requests and *tokens* per minute), per-tenant/per-key
  budgets, token counting (tokenizers, pre-flight estimation vs. actual usage),
  cost accounting per model, load shedding under LLM latency profiles, spike arrest.
- **Hook:** You did LaunchDarkly-driven dynamic rate limiting/throttling. New axis:
  the limit is on *tokens*, not just requests, and you must estimate before you send.
- **Exercise:** Design a multi-tenant budget system: pre-flight token estimate →
  admission decision → post-hoc reconciliation with actual usage. Pick the data store.
- **Self-check:** Why is token-based limiting harder than request-based? What do you
  do when the estimate < actual and the tenant is now over budget mid-stream?

## Day 7 — Caching

- **Concept:** Exact-match cache, **semantic cache** (embed prompt → vector search →
  reuse if similarity ≥ threshold), provider-side prompt caching. Tradeoffs:
  correctness vs. hit rate, staleness, cache poisoning, per-tenant isolation.
- **Hook:** You've used PGVector for semantic search — same machinery, new use.
  What's the risk of returning a "close enough" cached answer?
- **Exercise:** Design the semantic cache: key derivation, similarity threshold,
  what you refuse to cache (tool calls? high-temperature? PII?), invalidation.
- **Self-check:** When does semantic caching silently return a wrong answer? How do
  you tune the threshold, and how would you measure a bad hit in production?

## Day 8 — Security, governance, guardrails

- **Concept:** AuthN/Z, API key vaulting (Vault) & virtual keys, tenant isolation,
  PII detection/redaction, prompt-injection defense, input/output content
  moderation, audit logging, data residency, "don't log secrets/PII" constraints.
- **Hook:** You used Vault + mTLS + multi-tenant enrichment. Add: the *payload*
  itself (prompt) is now untrusted and may attack downstream tools.
- **Exercise:** Threat-model the gateway (STRIDE-lite): list top 5 threats unique to
  LLM traffic and one mitigation each. Include prompt injection via retrieved docs.
- **Self-check:** How do you give per-team virtual keys without distributing real
  provider keys? Where must redaction happen relative to logging and caching?

## Day 9 — Observability & evaluation

- **Concept:** Metrics (tokens in/out, cost, TTFT, latency, error/fallback rates by
  model & tenant), distributed tracing (OTel) across gateway→provider, safe
  request/response logging, tagging/attribution, online quality eval and drift.
- **Hook:** This is your home turf (OTel, 20M metrics/min). Design the metric set
  and cardinality budget — tenant × model × route can explode.
- **Exercise:** Define the OTel span + attributes for one gateway request, plus the
  5 dashboards you'd ship day one. Call out cardinality risks.
- **Self-check:** What's the token/cost attribution key? How do you log prompts for
  debugging without leaking PII or blowing up storage? What signals detect a bad
  model deploy?

## Day 10 — Capstone

- **Concept:** Synthesize everything into a design doc + prototype.
- **Exercise (design):** Architecture doc for a multi-tenant LLM Gateway: context +
  container diagram (C4), the canonical schema, 3 key ADRs (e.g., sync vs. async
  streaming, cache strategy, routing policy), non-functional requirements, and a
  capacity + cost model.
- **Exercise (code, optional):** Extend your existing Spring AI + Bedrock service
  into a mini-gateway: 2 providers behind one interface, one fallback route, a
  semantic cache, and token/cost metrics via OTel.
- **Self-check:** Present the design as if to the new team. Defend the 3 ADRs.
  Where would it fall over at 10× traffic, and what's the first thing you'd fix?

---

## Reference reading (pull as needed)

- LiteLLM proxy, Portkey, Kong AI Gateway, Cloudflare AI Gateway, Envoy AI Gateway docs
- OpenAI / Anthropic / Bedrock API refs (compare request/response + tool calling)
- "Ports & Adapters (Hexagonal Architecture)" — Alistair Cockburn
- OpenTelemetry GenAI semantic conventions
- Papers/blogs on semantic caching and prompt-injection defense
