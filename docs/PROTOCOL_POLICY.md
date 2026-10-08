# Protocol and implementation policy

Baseline: [official v1.0.1 specification](https://github.com/a2aproject/A2A/blob/v1.0.1/docs/specification.md), [canonical proto](https://github.com/a2aproject/A2A/blob/v1.0.1/specification/a2a.proto), commit `3303592588e388e62e0f69f701af531d2f4e3991`. Retrieved 2026-10-07; research URLs/hashes are in PLAN.md. M1/M2 are independently accepted. Installed a2a-sdk 1.1.5 JSONRPC/protobuf checks passed on Windows; see EVIDENCE.md for precise scope and remaining checks.

| Behavior | Classification |
| --- | --- |
| `A2A-Version: 1.0`; major/minor compatibility, patch ignored | Protocol version negotiation; no supported 0.3 fallback. |
| JSON-RPC 2.0, PascalCase methods, lowerCamelCase fields, task wrapper for SendMessage | Protocol binding; validation covers the stated subset. |
| Omitted/false `returnImmediately` waits for terminal/interrupted state; true permits asynchronous observation | Protocol configuration rule; six-second local wait is implementation policy. |
| GetTask returns current task with bounded/omitted history | Protocol behavior. |
| CancelTask returns a task; unknown task `-32001`, noncancelable task `-32002` | Protocol behavior/error mapping. Cancel effects are idempotent; completion may win a race. |
| ListTasks ordering/filter/count/token/artifact options | Protocol operation; implemented options and local cursor constraints listed below. |
| Unsupported version `-32009`, invalid parameters `-32602`, invalid peer response `-32006` | Scoped protocol/error handling. |
| Message-ID ledger and changed-content rejection | Implementation policy; send idempotency is optional in the protocol. |
| Parent-child hierarchy, retry limits/assumptions, remote outcome annotations, terminal storage guards | Implementation policy; no standard delegation/exactly-once contract claimed. |
| Ephemeral ports, synthetic data, fault gates, evidence events and assertion verdicts | Harness behavior. |

Cards declare JSONRPC 1.0; streaming, push notifications and extended cards are disabled. Supported operations are new-task SendMessage, GetTask, CancelTask and basic ListTasks. Advertising a version identifies the baseline being exercised, not full conformance. Complete ProtoJSON coercion/schema handling, every enum/content variant, continuation, tenants, batches/notifications and streaming are out of scope. Results are structured data artifacts.

## Recovery and cancellation assumptions

JSON-RPC IDs correlate exchanges, message IDs identify submissions, and server-generated task IDs support retrieval/cancellation. After a known task acknowledgment, GetTask retries use that ID and do not resubmit the work. An unavailable peer is an HTTP transport fault, not proof that the task disappeared.

The two-second/twelve-attempt default applies per submission, retrieval or cancellation operation. Exhaustion uses three retrieval attempts in its fixture. Individual child exchanges use at most one second or the remaining operation budget. Retry spacing is ten milliseconds. Fake-clock tests check both limits. These limits are not a hard whole-workflow deadline or restart recovery guarantee.

After an unacknowledged submission failure, a resend is allowed only under the configured peer deduplication assumption or the explicitly unsafe control. The protocol does not establish that assumption. Without it, Coordinator retains an inconclusive remote outcome and does not retry. Malformed responses/protocol errors fail the local workflow without retries.

Parent cancellation is immediately observable as local canceled state; it cannot establish child cancellation. Child outcome is recorded separately as pending, acknowledged, noncancelable or unknown. Late acknowledgments may supply a missing child link so cancellation can be sent. Late retrievals/artifacts cannot change terminal state. One cancellation flight is allowed per parent; exhaustion does not automatically restart on repeated CancelTask.

The runner can inspect the peer independently, including after Coordinator loses acknowledgment or exhausts retrieval. Reports label that knowledge `peer_tasks_observed_by_harness`; it does not become Coordinator knowledge. The unsafe case creates two mock tasks, keeps `no_duplicate_peer_tasks: fail`, and separately checks that the negative control behaved as intended. Suite PASS means expected case outcomes, not universal safety-policy success.

## Basic ListTasks subset

Example request parameters:

```json
{"contextId":"workflow-context","pageSize":2,"historyLength":0,"includeArtifacts":true}
```

| Field | Supported behavior |
| --- | --- |
| `contextId` | Exact context match; omitted/empty means no context filter. |
| `status` | Known task-state enum name or numeric value; omitted/unspecified means any state. |
| `statusTimestampAfter` | Timezone-aware ISO timestamp; matches status timestamp greater than or equal to the bound. |
| `pageSize` | Default 50; accepted integer range 1..100. Returned `pageSize` is this requested limit. |
| `pageToken` | Opaque local keyset token for a subsequent page; omitted/empty starts listing. |
| `historyLength` | Zero omits history; positive limits it; omitted preserves stored history. |
| `includeArtifacts` | Omitted/false omits the artifacts field. True returns stored artifacts, or an empty array. |

Results always contain `tasks`, `nextPageToken`, `pageSize` and `totalSize`. Ordering is most recent status timestamp first; task ID descending breaks ties. The final `nextPageToken` is an empty string. `totalSize` counts matching tasks before cursor pagination. Unknown/nonempty tenant routing is unsupported.

Tokens encode the last ordering key and a context/status/timestamp filter fingerprint. Changed filters or malformed tokens return invalid parameters. Page size/history/artifact presentation may change between pages. Tokens are not authenticated, do not protect access, and do not capture a stable snapshot. Concurrent task status updates may move tasks across pages. This is a small single-agent local listing implementation, not a multi-tenant/search service.

## SDK coverage

The optional oracle uses installed SDK-generated protobuf AgentCard/Message/Task types and its JSON-RPC client. It supplies `A2A-Version: 1.0` explicitly, verifies patch-compatible `1.0.99`, and checks unsupported/missing versions map to the SDK's `VersionNotSupportedError`. Unknown tasks, completed-task cancellation and invalid history map to SDK error classes. Protobuf parsing rejects the deliberately invalid lowercase task-state enum.

Those 26 checks validate the documented interactions with this exact SDK/runtime graph. Core ListTasks/filter/cursor checks remain core unit/HTTP evidence; the SDK oracle does not claim ListTasks coverage or verify every operation, transport, coercion or schema rule. Neither successful SDK parsing nor an advertised version establishes full protocol compliance.
