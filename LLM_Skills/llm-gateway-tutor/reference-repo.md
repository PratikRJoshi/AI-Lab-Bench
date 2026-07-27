# Reference Implementation Mapping — `mulesoft-emu/microgateway`

Reference: MuleSoft Flex Gateway Policy Engine (`https://github.com/mulesoft-emu/microgateway`).

**Shape at a glance:** Go control-plane agent (`flex-agent`) + **Envoy as the L7 data plane** + WASM policy filters + FluentBit for access logs + OTel for metrics. Policies declared as K8s-style YAML; hot-reloaded via xDS. **Not a monolithic in-process gateway** — the flex-agent never sits on the request path itself.

Two binaries:
- `cmd/flex-agent/` — the gateway daemon (control-plane side of policy management).
- `cmd/flexctl/` — runtime CLI over a Unix admin socket.

Every step below maps curriculum concepts → concrete repo locations, then calls out where the repo diverges from the textbook.

---

## F1 — What a gateway is (middle-boxes)

| Concept | Where it lives in the repo | Notes |
|---|---|---|
| TLS termination | `internal/models/gateway/configgenerator/envoy/policy_tls.go` (config gen); `internal/engine/certwatcher/` (hot-reload of certs) | flex-agent generates Envoy TLS config; Envoy actually terminates TLS. |
| Route matching | `internal/models/gateway/configgenerator/envoy/policy_routing.go`, `policy_routing_types.go`, `predicatebuildervisitor.go`, `headermatcherbuildervisitor.go` | Route match compiled into Envoy route table. |
| AuthN / AuthZ | Implemented as **Envoy WASM filters** (extensions); flex-agent loads/validates assets via `internal/services/asset/` + `internal/controlnode/asset/`. WASM ABI in `internal/wasmabi/`. | Auth is not in-process Go middleware — it runs inside Envoy as WASM. |
| Rate limiting | Modeled as a policy resource; state via `internal/sharedstorage/` (disk / redis / memory / objectstore / distributed). | See F3 mapping below — rate-limit counter storage is a first-class concern. |
| Response caching | Not a headline feature of this repo; achievable via Envoy filters/extensions if configured. | LLM caching would need to be added; no gateway-level response cache module here. |
| Logging / telemetry | `internal/fluentbit/` (access logs, FluentBit Go plugins); `internal/metrics/` (OTel dispatcher, serializer, HTTP connector, scheduler). | Access logs and metrics are separate subsystems from the request path — both driven by config the flex-agent writes. |
| Request/response transformation, header rewrite, version shim | `internal/models/gateway/configgenerator/envoy/headermatcherbuildervisitor.go`, `host_source_header.go`, and policy resources. | Rendered into Envoy filter config. |

**Delta vs canonical:** the "gateway" in this repo is **two processes**: flex-agent (Go control-plane manager) + Envoy (actual data plane). All the F1 "hop responsibilities" (TLS, auth, rate limit, routing, logging) execute inside Envoy — flex-agent's job is to *configure* Envoy to do them. This is exactly the "DP/CP split" from F2, applied one process boundary out from a monolithic gateway.

---

## F2 — Industry landscape (data plane vs control plane)

| Concept | Where it lives in the repo | Notes |
|---|---|---|
| Data plane | External **Envoy** process, managed as a child via `StoppableCommand` / `ReloadableCommand` (`internal/models/command/`). | The repo does not implement a proxy; it embeds and drives Envoy. |
| Control plane (the flex-agent itself) | `cmd/flex-agent/` + `internal/config/` (`ConfigServiceConfig.Run` orchestrates startup, wiring, hot-reload debounce). | flex-agent is the local control plane for its Envoy. |
| Data-plane control protocol (xDS) | `internal/io/xds/` — `service.go` (gRPC xDS service), `async_policy_updater.go`, `bootstrap.go`, `configwriter.go`, `stream_handler.go`. | flex-agent implements the xDS server; Envoy connects and pulls config. |
| Config sources (datasources) | `internal/engine/datasources/` — filesystem, Kubernetes, control-node (remote), platform, env-var, RTM, probes. | Multiple upstream config sources feed one canonical resource repository. |
| Remote control plane (upstream from flex-agent) | `internal/controlnode/` — gRPC client to MuleSoft's Flex control plane; `internal/controlnode/storage/` persists policy cache locally so a restart doesn't lose state. | Two-tier control plane: cloud CP → local flex-agent CP → Envoy DP. |
| Policy → subsystem-config translators | `internal/models/gateway/configgenerator/`: `envoy/`, `fluentbit/`, `controlnode/`, `composite/`. | Composite orchestrates all three generators for one policy graph. |
| Managed vs self-hosted analogue | Self-hosted (Flex Gateway is deployed on customer infra). Optional connect to MuleSoft-managed control plane (`FLEX_DATASOURCE_CONTROL_NODE_ENABLED`). | Same product supports connected (managed CP) and disconnected (local-only) modes. |
| Kubernetes integration | `internal/operator/` (informer watchers, adapters); K8s CRD types in `pkg/apis/`, `pkg/generated/`. | Adapters translate K8s `Service` and `Secret` into gateway domain types. |

**Delta vs canonical:** classic textbook picture is *one* control plane driving *one* data plane. This repo has **three tiers**: MuleSoft cloud control plane → local flex-agent (per-gateway local CP) → Envoy (DP). The middle tier exists so the gateway can run disconnected, cache policies to disk (`internal/controlnode/storage/`), and reconcile when the cloud CP is unreachable. Same pattern as Istio's istiod running in-cluster while pulling from a global source of truth — resilience via layering.

Also: xDS is used **internally** (flex-agent → its own Envoy child process). The gateway is essentially "Envoy + a policy compiler." Any team that adopts Envoy ends up building some version of this Go/C++/Rust config translator.

---

## F3 — Design & build a gateway from scratch

| Concept | Where it lives in the repo | Notes |
|---|---|---|
| Listener / TCP accept + TLS termination + HTTP parse | Envoy; configured via `internal/models/gateway/configgenerator/envoy/outbound_listener.go` and `policy_tls.go`. | flex-agent never runs an HTTP listener for request traffic; only for admin APIs (Unix sockets, see below). |
| Route match | `internal/models/gateway/configgenerator/envoy/policy_routing.go`, `policy_routing_types.go`. Predicates via `predicatebuildervisitor.go`. Header-based match via `headermatcherbuildervisitor.go`. | Compiled into Envoy route table, pushed via xDS. |
| Filter chain (per-route) | `internal/models/gateway/configgenerator/envoy/policy.go`, `policy_api_context.go`; WASM policy assets loaded from `internal/services/asset/` + `internal/controlnode/asset/`; ABI in `internal/wasmabi/` (`flex_abi_*` + `proxy_abi_*`). | Every policy is a WASM filter; filter chain is a per-route ordered list of WASM extensions. |
| Upstream cluster / instance pool | `internal/models/gateway/configgenerator/envoy/service.go` (renders `Service` domain type → Envoy cluster). | `Service.spec.address` becomes cluster endpoints. |
| Health checks | Envoy handles active/passive HC based on cluster config generated by flex-agent. Not implemented in Go. | Envoy's outlier detection ≈ passive HC. |
| Timeouts | `internal/models/gateway/configgenerator/envoy/policy_idle_timeout.go` (idle-timeout policy). Other timeouts set on clusters/routes in envoy config. | Timeout policy declared as YAML → xDS. |
| Retries | Configured on Envoy route policy (rendered from policy resources). | Retry policy is a first-class resource type. |
| Circuit breaker | `internal/models/gateway/configgenerator/envoy/policy_circuit_breaker.go`. | Rendered into Envoy cluster's `circuit_breakers` block. |
| Rate-limit counter state (F3's big Redis-vs-in-process question) | `internal/sharedstorage/` — pluggable backends: `disk/` (default), `redis/`, `memory/`, `objectstore/`, `distributed/` (memberlist). Manager in `manager/`, API in `api/`, client in `client/`. | Explicit multi-backend abstraction confirms the "shared state must be externalized for horizontal scale" lesson. Default is disk (local persistence), Redis for cross-replica correctness. |
| Connection pooling | Envoy connection pools per cluster (config generated by flex-agent). | Not in Go code path. |
| Config-driven vs coded | **Fully config-driven.** YAML resources (`v1alpha1`, `v1beta1`, `networkingk8siov1`) parsed by `internal/models/gateway/language/`. | Adding a policy = drop a YAML file; no code change, no restart. |
| Hot-reload | `ConfigServiceConfig` (`internal/config/`) debouncer + filesystem watcher (`internal/io/fs/`) + xDS push (`internal/io/xds/async_policy_updater.go`). Cert hot-reload in `internal/engine/certwatcher/`. | Textbook "control plane pushes to data plane with zero connection drops." |
| Admin surface / observability | `internal/server/httpserver/` on Unix sockets: `flex-agent-status-api.sock` (status, probes, config dump — what `flexctl` talks to) and `flex-agent-services.sock` (LDAP, config-resolver). Envoy admin socket `flex-gw-admin.sock` is separate. | Two-socket split: control operations vs. inter-subsystem services. |
| Stateless-vs-stateful split | Stateless in agent request/response handling; stateful items externalized to `sharedstorage/` (rate-limit buckets, control-node cache); JWKS/cert caches in `certwatcher/`; route table + policy graph in `ResourceRepository` (in-memory, source of truth is on disk / remote CP). | Matches F3's rule: **shared state externalized, per-request state discarded**. |
| WASM policies (unique to this design) | `internal/wasmabi/` defines ABIs; `internal/services/asset/` handles loading + validation; extensions execute inside Envoy via `wazero`. | Same "filter chain per route" idea, but filters are portable WASM binaries — you can ship a policy without recompiling the gateway. |

**Delta vs canonical:**

1. **Filters are WASM, not in-process middleware.** In a monolithic gateway (Spring Cloud Gateway, Express) filters are code compiled into the gateway binary. Here, each policy is a separate WASM module loaded into Envoy. Same abstraction (ordered per-route filter chain, short-circuitable, composable) — different execution substrate. Trade: portability + safety (Wasm sandbox) + hot-swap; cost: ABI complexity (`internal/wasmabi/`) and slightly higher per-request overhead.

2. **Rate-limit storage is a solved abstraction.** F3's "in-process vs Redis" question is settled at the design layer: `internal/sharedstorage/` has an interface with 5 backends. Real production gateways always end up with this.

3. **Two-tier control plane.** The flex-agent is the *local* control plane; a remote (cloud) control plane is optional. Local disk cache (`internal/controlnode/storage/`) provides resilience when the remote CP is unreachable. Textbook usually shows one CP; production shows two.

4. **No in-process ExtProc.** Some Envoy deployments do per-request gRPC callouts to a "policy sidecar" (Envoy ExtProc). This repo explicitly does **not** — all per-request policy runs inside Envoy as WASM. flex-agent is only touched at config-update time. This is faster (no gRPC hop per request) but means all policy logic must compile to WASM.

5. **Config hot-reload with debouncing.** Textbook says "push new config, done." Real: file watchers fire many events for one save; `ConfigServiceConfig` debounces before triggering the xDS update. Small detail, big operational win.

---

## Phase 1 — LLM Gateway concept mapping (populated as Days 1–10 run)

Empty until Phase 1 begins. Expect large deltas — this repo is a **generic API gateway**, not an LLM gateway. LLM-specific concerns (provider abstraction, token budgeting, semantic cache, streaming with cancel-propagation) will map to "not present; would need to be added as WASM extensions or new policy types."
