# Architecture

Core entry point: `python -m a2a_recovery_lab` from the repository root. Core runtime/tests have no third-party dependencies. M1/M2 are independently accepted. A separate optional M3 installed-SDK verifier passed on Windows; final review is pending.

| Module | Responsibility |
| --- | --- |
| `wire.py` | Scoped A2A/JSON-RPC checks, mapped errors, strict JSON decoding, canonical serialization. |
| `server.py` | One separately bound loopback HTTP server per agent; `/rpc` and public card routes. |
| `transport.py` | Actual HTTP card/RPC client; correlation, response validation, disabled redirects/proxies, timeouts. |
| `store.py` | Agent-owned SQLite task store, atomic submission ledger, terminal guards, cancellation, keyset listing. |
| `agents.py` | Deterministic ticket rules, bounded executors, Coordinator handoff/retrieval/cancellation. |
| `policy.py` | Bounded operation decisions with injected clock/sleep for no-socket tests. |
| `faults.py` | Runner-owned reply loss/delay/availability/corruption and mock-completion gates. |
| `evidence.py` | Numbered immutable JSONL snapshots and condition-based event waiting. |
| `demo.py` / `scenarios.py` | Two-peer workflow, exact eight-case suite, independent expectations and reports. |

## Acceptance and task state

SendMessage validates supported fields/ticket content before acceptance. An SQLite write transaction creates a task and message-ID fingerprint mapping together. Identical submissions return the same task; changed content under that ID returns invalid parameters. Blocking/history configuration does not change identity. An explicitly unsafe fixture disables the peer ledger to demonstrate duplicate tasks.

Agent-owned thread pools run tasks. Omitted/false `returnImmediately` waits on a condition for terminal/interrupted state, with a six-second local waiting bound. True returns the current task; a fast task may already be completed. Gated HTTP tests distinguish those paths. GetTask returns a snapshot with the requested history limit.

Completion and cancellation compete inside SQLite transactions. One terminal transition wins. Ordinary updates cannot modify state, artifacts, or execution metadata after a terminal state. Narrow policy annotations may still record recovery/cancellation observations, and an acknowledged child link may arrive after parent cancellation. Those annotations cannot add a late artifact or replace an existing child ID.

## Handoff and recovery

Coordinator discovers a same-origin card, submits the child, and retrieves/cancels it through HttpClient, never Normalizer's Python execution methods or database. Submission retries reuse the same child message ID and content. Each RPC exchange uses a fresh correlation ID.

RecoveryPolicy bounds each operation by attempts and a monotonic deadline. It retries transport failures only. Invalid responses and protocol errors are not retried. A pending task can trigger another known-ID retrieval within the same budget. Checks before/after exchanges reject late retrieval responses after local cancellation or deadline expiry. Discovery is one bounded request outside those retry budgets.

A failed initial submission may have been accepted. Without an explicit peer deduplication assumption, Coordinator stops after that exchange, fails the local workflow, and records `ambiguous_submission` plus `unknown_to_coordinator`. It never invents the unknown child ID. Lost-ack recovery explicitly assumes the shipped peer's ledger; the unsafe baseline deliberately retries without that contract against a ledger-disabled peer.

CancelTask first cancels the local parent. If the child ID is known, a separate bounded cancellation flight begins; metadata is `pending` until a validated canceled response is observed. An exhausted flight records `unknown`; a noncancelable child returns an explicit error outcome. Neither implies the child canceled. If an acknowledgment races parent cancellation, the child ID is retained and cancellation is then propagated. If submission ends without a known child ID, metadata records `unknown_child_id` or `not_started` as appropriate. Repeated parent cancellation does not create another flight after exhaustion.

Stores persist lookup/deduplication, not executable continuations. Restart reconciliation and general process-crash recovery are out of scope.

## Fault and report boundaries

Fault controls exist only in the runner's owned server wrapper. Availability returns HTTP 503 **before agent dispatch**. Lost ACK closes the response **after task acceptance/dispatch** and records the accepted ID. Delay holds an already captured GetTask result. A completion gate holds mock execution so cancellation precedes the attempted late artifact update. Cleanup releases every gate. No fault-control route is exposed on the agent API.

Both stores share one evidence sink. It records synthetic payloads and allowlisted headers, uses a lock/condition for contiguous event IDs, and freezes mutable data before writing. Reports classify assertions as `protocol`, `implementation_policy`, or `harness`; checks refer to actual event numbers. Independent fixture literals and test expectations live outside executors.

The scenario verdict evaluates the intended case outcome. In the unsafe baseline, expected-negative acceptance and the failed no-duplicate policy check remain separate. Harness-only peer task observations are identified separately from Coordinator's acknowledged child; this prevents using privileged runner observations to erase remote uncertainty.

## Listing and lifecycle

ListTasks loads the small local task set, filters by context/state/status timestamp, and orders status timestamp then task ID descending. Its cursor stores the last key and a filter fingerprint. See PROTOCOL_POLICY.md for options and restrictions. Pagination is not a transactionally stable snapshot across calls.

Shutdown releases test gates, stops accepting connections, joins request threads, closes the socket, and shuts down agent executors. Supported reads/client/execution waits are bounded. M2 records two clean server-stop events per saved case and twenty failed connection probes after teardown across eight core/two supplemental cases. These bounds apply to shipped fixtures, not arbitrary user executors.

## Optional installed-SDK oracle and CI

`scripts/sdk_smoke.py` imports the official SDK only when that script runs. It verifies installed versions against the separate 32-package/hash-pinned runtime closure, then uses installed `A2ACardResolver`, `JsonRpcTransport`, generated protobuf types and SDK error classes over actual owned HTTP endpoints. The script hashes inspected installed resolver/transport/type files. HTTPX event hooks observe SDK requests/replies, restrict the check to the two created loopback origins, disable ambient proxies/redirects and log allowlisted headers. SDK tracing decorators are disabled; no telemetry exporter/provider is configured.

The SDK verifier gates mock completion to prove blocking and immediate sends, validates independent fixture literals, retrieves acknowledged IDs, cancels parent/child, checks mapped errors and version compatibility, and verifies terminal guards and closed ports. All agents remain deterministic mocks. It does not reuse the core wire validator as its oracle. The SDK version header is supplied explicitly through HTTPX and varied through SDK call context for version checks.

The optional environment is repository-local and excluded from Git; the stdlib entry point never imports it. Wheel metadata/hash/licenses and dependency markers were verified for Windows AMD64 and Linux x86_64 Python 3.11.9. Only Windows executed. Binary wheels avoid source builds. The runtime graph includes mandatory Google/cryptography/OpenTelemetry API dependencies from the SDK's base requirements; no optional server/telemetry/SQL/gRPC extras were selected.

Prepared CI uses full checkout/setup-Python action pins, contents-read permissions, disabled persisted checkout credentials, job timeouts and matrix concurrency one. Core jobs precede SDK jobs. It does not publish/deploy or call models. Hosted CI/Linux execution is unexecuted, so local Windows receipts remain the observed evidence.

The scoped server/client are local fixtures, not production adapters.
