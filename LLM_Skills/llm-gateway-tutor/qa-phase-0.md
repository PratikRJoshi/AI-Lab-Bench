# Phase 0 — Gateway Foundations: Q&A Log

Every question asked during a Phase 0 step, with the canonical correct answer.
Append-only. Written for future re-reading, not as session transcript.

---

## F1 — What a gateway is

### Q: 50 clients, 30 services, each needing TLS + auth + rate limits. What breaks if you put those concerns inside every service? Name two failure modes.

**A:**
1. **Duplicated security-sensitive libs across services and languages.** TLS libs (OpenSSL), JWT parsers, auth SDKs get frequent CVEs (Heartbleed, Log4Shell, JWT alg-confusion). With 30 services on 4 languages you must patch 30 codebases, ship 30 deploys, coordinate 30 on-call fires. Version drift is invisible until exploited.
2. **Policy drift / inconsistency.** Service A rate-limits at 100 rps, B at 1000, C forgot to add it. Clients can't predict behavior, security posture varies per team, and there's no single place to change a policy globally.
3. **Wasted infra + engineer time** re-implementing the same cross-cutting logic per service.

Rule: concerns that must be **uniform + fast to change** don't belong in every service.

### Q: Draw the request path client → gateway → services and label the responsibilities the gateway takes on at that hop.

**A:** Minimum labels at the gateway hop:
- TLS termination (mTLS if needed)
- AuthN (verify identity: JWT, API key, mTLS cert)
- AuthZ (allowed to call this route?)
- Routing / path matching to correct upstream
- Rate limiting / quota enforcement
- Request & response transformation (header rewrites, version shims)
- Response caching (in-memory / Redis; distinct from edge CDN)
- Logging / telemetry (OTel spans, access logs)
- Timeouts, retries, health checks against upstreams

CDN sits *in front of* the gateway (edge). Gateway does application-tier response caching.

### Q: Reverse proxy vs load balancer vs API gateway — what's the distinction? (one line each)

**A:**
- **Reverse proxy:** one front door for many backends. Core jobs: TLS termination, path-based routing, response caching, hiding origin.
- **Load balancer:** spreads traffic across N instances of a backend. Can be **L4** (TCP, by IP/port) or **L7** (HTTP, path/header aware). Orthogonal to gateway — can be standalone or a function *inside* a gateway. Sticky sessions exist; not restricted to stateless services.
- **API gateway:** reverse proxy + LB + policy layer. Adds authN/Z, rate limiting, quotas, transformation, API-key management, request aggregation, versioning.

Mental model: **reverse proxy ⊂ API gateway**; LB is orthogonal.

### Q: What's L4 vs L7 routing? Give one thing L7 can do that L4 cannot.

**A:**
- **L4** = transport layer. Routes on IP address, TCP port. Doesn't parse the payload.
- **L7** = application layer. Parses HTTP: path, headers, cookies, JWT claims, hostname.

L7-only capabilities: route `/api/orders` → service A vs `/api/users` → service B; host-based routing (`orders.example.com` vs `users.example.com`); JWT-claim-based routing; header-based canary (`x-canary: true` → new version); request/response transformation.

L4 can only make routing decisions on connection-level info.

### Q: When do you NOT need a gateway?

**A:**
- **Single service, single client** (internal admin tool, no fan-out).
- **Service mesh already handles east-west needs** (Istio/Linkerd sidecars do gateway-ish work between services).
- **Ultra-low-latency path** where extra hop cost is unacceptable (HFT, real-time bidding under ~10ms budget).
- **Purely internal traffic** (gRPC/DB access with no external clients).

Rule: no gateway when there's nothing to centralize, or when the hop cost outweighs the benefit.

---

## F2 — Industry landscape (data plane vs control plane)

### Q: In K8s, which piece touches every request, and which piece decides how pods should behave but never sees traffic?

**A:**
- **Data plane** (touches requests): kube-proxy (iptables/IPVS rules), kubelet, CNI plugin, the Pod's own network stack. K8s Service is the abstraction; kube-proxy is the implementation on the request path.
- **Control plane** (decides, never touches traffic): kube-apiserver, controller-manager, scheduler, etcd. Watches desired state, tells nodes what to run.

Deployment/ReplicaSet manages *pod lifecycle*, not per-request behavior.

### Q: Why did Istio adopt Envoy as its data plane rather than write its own proxy?

**A:**
1. **Envoy already existed and was battle-tested** at Lyft. Writing a new L7 proxy = years of HTTP/2, TLS, connection-pooling, protocol-quirk debugging.
2. **Envoy was designed control-plane-friendly from day one** via **xDS** — a gRPC streaming API for dynamic config push and hot-reload. No other proxy had this.
3. **Separation of concerns.** Istio's value is policy/security/telemetry orchestration across a mesh, not packet shoving.
4. **Ecosystem leverage.** AWS App Mesh, Consul Connect, Gloo, Kong Mesh all use Envoy — shared investment.

Lesson: control plane and data plane are separately evolvable; multiple control planes can drive the same data plane.

### Q: Comparison table — NGINX, Envoy, Kong, AWS API Gateway, Istio.

**A:**

| Tool | Category | Deploy model | Config model | DP/CP split? | Killer feature | When to pick |
|---|---|---|---|---|---|---|
| **NGINX** | Reverse proxy + LB (L4/L7) | Binary on VM/container; NGINX Ingress on k8s | Static config file, `nginx -s reload` | No — monolithic | Rock-solid, low-latency static reverse proxy; huge ecosystem | Simple front door, TLS termination, static routing, low ops overhead, config rarely changes. |
| **Envoy** | Programmable L7 proxy (data plane) | Binary/sidecar; standalone or embedded in mesh | **xDS gRPC** dynamic push | Yes — Envoy is the data plane; you bring/build the control plane | Dynamic hot-reload config via xDS; rich L7 filters (HTTP/2, gRPC, Wasm) | Need programmable L7 with dynamic config; building your own gateway/mesh; mesh sidecar. |
| **Kong** | API gateway | Self-hosted (OSS/Enterprise) on k8s/VM; Konnect = managed | Admin REST API + declarative YAML + k8s CRDs | Yes — DB-backed CP + Kong Gateway DP nodes (hybrid mode) | Plugin ecosystem (Lua + Wasm); mature auth/rate-limit/transform plugins | Multi-team API platform, heavy plugin needs, want OSS + optional enterprise. |
| **AWS API Gateway** | API gateway (managed SaaS) | Fully managed AWS service | AWS console / CloudFormation / Terraform | Yes — AWS runs both, hidden | Zero ops; native IAM, Lambda, WAF, CloudWatch integration | AWS-native, no infra to run, REST/WebSocket/HTTP APIs. |
| **Istio** | Service mesh (control plane) | k8s only; istiod as CP, **Envoy sidecars as DP** | k8s CRDs (VirtualService, DestinationRule, Gateway) | Yes — istiod → Envoy via xDS | mTLS everywhere + fine-grained E/W policy + telemetry, no code changes | Many services on k8s needing zero-trust mTLS, canaries, observability transparent to apps. |

### Q: Why pick Envoy over NGINX when building a new API gateway?

**A:** The deciding factor is **dynamic config with zero-drop hot reloads via xDS**. NGINX reload (SIGHUP) can drop in-flight connections or blip workers; fine when config changes weekly, not fine when routes/canary weights/policies change per deploy or per tenant. Envoy also has richer L7 filters (native gRPC, HTTP/2 filter chain, Wasm plugins); NGINX extensibility is Lua (OpenResty) or C modules — harder ecosystem.

DP/CP split is the *mechanism*; dynamic config without downtime is the *user-visible win*.

### Q: On AWS, small team, need an API gateway next week — Kong vs AWS API Gateway?

**A:** Pick **AWS API Gateway** — zero ops, ships this week, native IAM/Lambda/WAF/CloudWatch integration.

Tradeoffs you're accepting:
- **Vendor lock-in** (Terraform helps but not portable).
- **Cost per request** at scale — pay-per-call can dwarf EC2 at high RPS.
- **Feature ceiling** — you get AWS's plugin menu; no custom Lua/Wasm.
- **Debugging opacity** — can't tail the proxy.

Rule of thumb: managed now; revisit at ~10k RPS or when custom plugins are required.

### Q: Is Istio a substitute for an API gateway at the edge (N/S)?

**A:** Not fully. Istio's primary strength is **east-west** (svc↔svc inside the mesh: mTLS, retries, canary, telemetry via sidecars). Istio also ships an **Ingress Gateway** — an Envoy at the mesh edge for N/S — but it's thinner on classic API-gateway features: no built-in developer portal, no API-key management/monetization, weaker rate-limit-per-consumer UX, no plugin marketplace.

Common composition: **Kong / AWS API Gateway at the edge (N/S)** + **Istio inside (E/W)**. Istio can replace an edge gateway for simple cases; for full API-as-product features you keep a dedicated one.

Rule: **mesh solves service-to-service policy uniformly; API gateway solves the API-as-product problem at the edge.** Overlap exists, not identical.

### Q: What does the DP/CP split buy you operationally? Two concrete benefits.

**A:**
1. **Policy updates without downtime.** Control plane pushes new routes / rate limits / auth rules → data plane hot-reloads. No proxy restart, no connection drops, no rolling deploy. Change latency drops from minutes to seconds.
2. **Blast-radius isolation.** Control plane crash ≠ traffic outage. Data plane keeps serving on last-known config. You can iterate/deploy the control plane aggressively while the data plane stays boring and stable. Same pattern as kube-apiserver down not killing running Pods.
3. (Bonus) **Independent scaling.** Data plane scales with request volume; control plane scales with config-change rate. Different resource profiles, sized separately.

### Q: Managed (AWS API Gateway) vs self-hosted (Kong on k8s) — one thing self-hosted does that managed cannot, and one thing managed does better.

**A:**

**Self-hosted only:**
- **Custom plugins / arbitrary code in the request path** (Kong Lua plugin, Envoy Wasm filter, calls into internal services). Managed = provider's plugin menu, period.
- Also: air-gapped / on-prem / non-AWS regions; deep protocol customization; unrestricted body sizes; sub-ms latency budgets with no managed-hop overhead.

**Managed does better:**
- **Zero ops.** No patching, no CVE fire drills, no capacity planning, no HA setup. Multi-AZ, autoscaling, TLS cert rotation, DDoS protection all handled.
- Also: instant global edge presence, native IAM/Lambda/CloudWatch integration, predictable pricing at low-to-medium volume.

Break-even often lands when the monthly managed bill exceeds one FTE cost.

---

## F3 — Design & implement a gateway from scratch

### Q: A request lands on port 443. Name the ordered stages before it reaches upstream.

**A:**

1. **Listener / TCP accept** — socket accepts connection on :443.
2. **TLS termination** — decrypt using server cert. (Client-cert mTLS validation is a *separate* optional step.)
3. **HTTP parse** — parse method, path, headers, body framing → structured request.
4. **Route match** — match `(method, path, host, headers)` against route table → pick route. Route determines which upstream cluster + which filter chain runs.
5. **Filter/middleware chain** (route-specific): logging, authN (JWT verify), authZ (scope check), rate limit, request transformation.
6. **Upstream selection** — from the cluster picked at step 4, pick a healthy instance via LB algo (round-robin, least-request, consistent-hash).
7. **Forward** — open/reuse upstream conn; apply timeout, retry, circuit breaker.
8. **Response pipeline** (reverse): upstream response → response filters (transform, cache-store, log-finish, close span) → back to client.

Key: **TLS termination ≠ authN ≠ authZ.** TLS is transport-layer decryption; authN is "who are you?"; authZ is "are you allowed?" Different stages.

### Q: Rate-limit counter — in-process (gateway pod memory) or external (Redis)? Real tradeoff?

**A:** Real tradeoff is **horizontal-scale correctness**, not redeployment.

- **In-process:** each pod holds its own count. In a fleet of 10 pods, a "100 rps" limit is enforced 10× because each pod sees only its share of the traffic. Broken for shared/tenant quotas.
- **External (Redis):** all pods increment same counter. Global limit is correct. Cost = one Redis round-trip per request (~0.5–1 ms).

Use in-process for per-pod overload protection or single-pod deploys; external for multi-pod tenant quotas; hybrid (fast local approx + async Redis sync) is what Envoy's local+global rate-limit filters implement together.

Second-order: Redis becomes SPOF / hot key on popular tenants → shard by tenant. Sliding-window in Redis needs a Lua script for atomicity.

### Q: Where does the filter chain run relative to routing, and why does the order matter?

**A:** Filter chain runs **after route match**, because chain composition is route-specific — public route may skip authN entirely; a secured route inserts authN + authZ + per-tenant rate limit.

Nuance: real gateways have two tiers. Envoy's **listener filters** run pre-route (TLS termination, global access log, DDoS shielding). Its **HTTP filters** run post-route (route-specific). Route-specific chain is always post-route.

### Q: How does the gateway decide an upstream instance is unhealthy?

**A:** Two complementary mechanisms, plus a related one.

**Active health check:**
- Background loop, per cluster, independent of request traffic.
- Probes each instance at fixed interval (e.g. `GET /healthz` every 5s).
- Per-instance state machine: healthy → unhealthy after N consecutive failures (2–3), unhealthy → healthy after M consecutive successes.
- Failure = non-2xx, timeout, connection refused.
- Unhealthy instance removed from LB pool; still probed; auto-recovers.

**Passive health check (outlier detection):**
- Observes real request traffic — no separate probe.
- Instance returning many 5xx / connection errors in a window → eject for cooldown (e.g. 30s).
- Cheaper (no extra probe traffic); slower to detect if traffic is low.

Real gateways run **both**. Active catches silent dead pods; passive catches "pod returns 500 to real traffic but /healthz still 200."

**Circuit breaker** ≠ health check. It's per-instance-per-caller state (open / half-open / closed) that gates *sending more requests* when in-flight failure rate spikes. Complements health check.

### Q: What state must the gateway hold, and what must it stay stateless about?

**A:**

**Must hold state (in-memory and/or Redis-backed):**
- Route table (updated by control plane / config reload).
- Upstream health status (per-instance up/down flags).
- Rate-limit counters (Redis for fleet-wide, in-process for best-effort local).
- Connection pools to upstreams.
- JWKS / cert cache (for JWT signature verification, refreshed periodically).
- Response cache (external if shared across fleet, in-process if node-local).
- Circuit breaker state per instance per gateway pod.

**Must stay stateless about (so any pod serves any request):**
- Client session identity — verify stateless tokens (JWT), do not store server-side sessions.
- Request-in-progress state that outlives one request.
- Per-client server-side memory across requests.
- Fleet coordination — no pod tracks which other pod served the previous request.

Rule: **shared state → externalize (Redis, control plane). Per-request state → local, discard on response. No per-client server-side state ever** — it kills horizontal scale.

### Q: Filter chain — is it one block or multiple internal blocks?

**A:** Both — same thing at different zoom. Zoomed out: one box "Chain C2". Zoomed in: an ordered pipeline of small filter boxes (log → authN → authZ → rate-limit → forward → log-finish).

Key properties:
1. **Ordered.** authN before authZ (must know who before checking what). Rate-limit before forward (don't waste upstream call).
2. **Short-circuitable.** Any filter can reject → response returns immediately; downstream filters skipped (401, 403, 429, cache hit).
3. **Composable.** Same filter type (e.g. `rate-limit`) reused across chains with different config.
4. **Bidirectional.** Filters have request-hook and/or response-hook. `cache-lookup` on request; `cache-store` on response — same filter, both hooks.
5. **Per-route.** Different routes → different chains → different filter mixes.

Mental model: middleware stack (Express/Spring), gRPC interceptor chain, Netty handler pipeline.
