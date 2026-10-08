# A2A Recovery Lab — proposed implementation plan

Status: **planning only; awaiting the main chat's accepted-milestone assignment**. No implementation, dependency installation, demo, or test suite has run.

Research retrieved on **2026-10-07**. Repository: `C:/Users/shash/Documents/CodexPortfolios/agentic-ai-2026-10-07/a2a-recovery-lab`.

## 1. Problem and useful developer journey

A developer connecting an agent to another team's A2A endpoint needs to know what happens when a request is accepted but its response is lost, cancellation crosses a handoff, or the peer disappears while work is running. A successful happy-path exchange does not answer whether a retry creates another task, whether local cancellation reaches the remote task, or whether a recovered workflow resumes the task it already started.

Build a local CLI that runs a small, inspectable workflow under reproducible faults and produces an assertion report with the corresponding request, response, task, and policy events. The first useful workflow is fictional support-ticket normalization:

1. The runner sends a structured synthetic ticket to **Coordinator** through A2A.
2. Coordinator discovers **Normalizer**, hands off the ticket, remembers its returned task ID, and polls it.
3. Normalizer applies deterministic rules: trim/collapse title whitespace, validate priority, and return an artifact containing the normalized ticket and an input hash.
4. Coordinator returns an artifact that links its parent task to the peer task. Both agents expose an Agent Card and task operations.
5. The runner repeats this journey with a chosen fault and reports protocol observations separately from the configured recovery policy.

The mock agents perform deterministic transformations. They do not call an LLM. The transport is real loopback HTTP. A report must say `execution_mode: deterministic_mock_over_http`; recorded JSONL examination, if added, must say `recorded_trace_analysis` and must never be presented as a fresh run.

Proposed CLI surface, finalized during the assigned milestone:

```powershell
py -3.11 -m a2a_recovery_lab demo --scenario happy-path --out work/demo-happy
py -3.11 -m a2a_recovery_lab demo --suite core --seed 7 --out work/demo-core
py -3.11 -m a2a_recovery_lab report work/demo-core/report.json
py -3.11 -m a2a_recovery_lab serve --agent normalizer --port 9102 --db work/normalizer.sqlite
py -3.11 -m a2a_recovery_lab serve --agent coordinator --port 9101 --peer http://127.0.0.1:9102 --db work/coordinator.sqlite
py -3.11 -m a2a_recovery_lab run --peer http://127.0.0.1:9101 --scenario fixtures/happy-path.json --out work/custom-run
```

`demo` owns its local servers, ephemeral ports, and teardown. `serve` supports a developer's two-terminal inspection. `run` accepts a small documented JSON scenario containing synthetic message content, expected artifact predicates, and explicit peer policy assumptions. It targets a developer-controlled local endpoint; it is not a production probe. The default path requires no pip installation or credentials. `report` reads an existing artifact and does not execute an agent.

## 2. Existing overlap and proposed contribution

| Existing primary-source project | Relevant overlap | Intended relationship |
| --- | --- | --- |
| [A2A TCK](https://github.com/a2aproject/a2a-tck/blob/main/README.md) | Compatibility checks across JSON-RPC, HTTP+JSON, and gRPC, organized by requirement level. | Refer developers there for broader conformance testing. This lab reports only the operations and assertions actually exercised. |
| [A2A ITK](https://github.com/a2aproject/a2a-itk/blob/main/README.md) | Cross-SDK, multi-hop traversal and trace verification across transports. | Do not recreate its SDK/transport matrix. Use a two-agent recovery workflow and a separate official-SDK client check. |
| [A2A Inspector](https://github.com/a2aproject/a2a-inspector/blob/main/README.md) | Interactive agent communication and raw JSON-RPC inspection. | Offer repeatable CLI scenarios and machine-readable outcomes; no browser UI. |
| [Official Python SDK](https://github.com/a2aproject/a2a-python/tree/v1.1.5) | Client/server implementation and protocol data types. | Use its independent client as a verification oracle, outside the dependency-free core. Do not call two copies of the lab implementation proof of ecosystem interoperability. |

The repository's contribution is the combination of scripted failure points around a handoff, explicit recovery assumptions, parent/child task evidence, and reports that distinguish a protocol violation from a failed local policy or an unknown remote outcome. This is a concrete design contribution, not a claim that fault testing or A2A testbeds are new. Passing the lab does not establish full A2A compliance, security, production readiness, or exactly-once external effects.

## 3. Protocol baseline and boundaries

The latest official specification release page read during planning lists **v1.0.1**. Pin that release, commit **`3303592588e388e62e0f69f701af531d2f4e3991`**. The negotiated wire version is **`1.0`**, not `1.0.1`. The release and wire versions must both appear in the report.

The MVP exercises the **JSON-RPC 2.0 binding**: `SendMessage`, `GetTask`, `CancelTask`, and basic `ListTasks`, plus `/.well-known/agent-card.json`. Use PascalCase methods, ProtoJSON field names and enum values, `application/json`, and `A2A-Version: 1.0`. Omitted/unsupported versions receive the mapped version error. Cards advertise only JSONRPC 1.0; streaming, push notification, and extended-card capabilities remain false. Unsupported optional operations return the appropriate mapped error.

| Protocol-grounded observation | Lab policy or implementation choice |
| --- | --- |
| A2A defines task IDs, contexts, task states, cancellation, and artifacts. | Parent/child task linkage, retry budgets, SQLite storage, and cancellation propagation are lab behavior. |
| Send-message idempotency is optional; `messageId` can be used for duplicate detection. | Normalizer deduplicates initial submissions by message ID within its local agent namespace and checks a payload fingerprint. |
| Canceling a task can fail if it has already finished; repeated cancellation has an idempotent effect. | A canceled Coordinator stops locally and records whether child cancellation is acknowledged, pending, or unknown. A local canceled state alone does not prove remote cancellation. |
| Terminal tasks do not accept additional messages. | Delayed local work uses conditional state updates so it cannot overwrite a canceled terminal state. |
| Task retrieval can recover the peer's current state. | Once a child ID is known, Coordinator retries retrieval instead of creating another task. |

Normative checks cite the pinned specification sections 3.1, 3.2.2, 3.3.1, 3.6, 4, 5.4, 8, and 9. The tagged document contains some broadly worded asynchronous descriptions alongside the explicit default-blocking configuration rule. Implement the specific configuration rule: `returnImmediately: true` for the demo's asynchronous submission; omitted/false waits for a terminal or interrupted result. Do not treat every intermediate state as required in every trace.

Repeated cancellation of an already canceled task may produce the mapped noncancelable error without changing the task. Tests check stable effects and terminal-state preservation; they do not require identical success responses on every cancellation attempt. A new message aimed at a terminal task is rejected. An identical retried initial submission with no task ID can return its deduplication lookup result without applying another message to that task; that is a documented lab policy.

Non-goals: SSE, gRPC, REST binding, 0.3 fallback, push callbacks, authentication/TLS deployment, signed cards, tenant isolation, LLM reasoning quality, orchestration frameworks, queues, arbitrary external side effects, production endpoint changes, UI, exhaustive conformance, fuzzing, and cross-language SDK matrices. Keep fault injection in the test harness, outside the agents' normal protocol API. No Docker or cloud infrastructure.

## 4. Architecture and dependency choices

Choose **Python**. Its standard library covers the CLI, JSON wire format, HTTP client/server, SQLite transactions, clocks, hashing, and tests. That keeps the default Windows/Linux demo directly runnable and makes the harness's policies easy to inspect. A second Java implementation would enlarge the MVP without proving more than the planned independent SDK client check. Java remains a possible later adapter, outside this accepted scope.

```text
CLI scenario runner / external official-SDK smoke client
        | A2A JSON-RPC over loopback HTTP
Coordinator server --> faulting HTTP transport/gateway --> Normalizer server
        | parent tasks + child references                    | tasks + dedup ledger
        +-------------------- SQLite -----------------------+
                         JSONL evidence + JSON report
```

The diagram shows logical stores; each agent gets its own database file. The gateway is a harness fixture, not a third agent or deployment dependency. Ordinary happy-path execution can connect the agents directly.

Proposed modules:

- `wire.py`: scoped validation, error-code mappings, version/card handling, and request/result serialization.
- `server.py`: bounded loopback `ThreadingHTTPServer` adapter and routing. This is a local test server, not a production HTTP stack.
- `store.py`: SQLite task records, initial-message ledger, atomic task creation, and conditional terminal-state updates.
- `agents.py`: deterministic Normalizer and Coordinator executors; an HTTP handoff client.
- `policy.py`: explicit peer assumptions, attempt budgets, timeout/deadline handling, and cancellation intent.
- `faults.py` / `scenarios.py`: scripted faults and gated execution for reproducible demonstrations.
- `evidence.py` / `__main__.py`: CLI, JSONL events, JSON report, and human-readable output.

Separate wire task states from internal policy fields such as `cancel_pending` and `remote_outcome_unknown`; never invent an A2A task enum. Agent executors cannot alter the runner's expected assertions.

Recovery contracts:

1. An initial submission's task row and message-ID/fingerprint mapping commit together. Identical duplicates return the same task ID; changed content under the same ID is rejected with a documented invalid-parameter policy.
2. The deduplication ledger lives as long as the scenario database. No retention or infinite-deduplication guarantee. Persistence/reopen tests cover lookup survival; this MVP does not claim general process-crash recovery of arbitrary executing work.
3. A lost response after acceptance can be retried only when the scenario explicitly supplies the peer's deduplication contract. This is an out-of-band assumption, not a standard A2A capability inferred from version or card.
4. Without that assumption, an ambiguous submission ends with an **inconclusive/unknown remote outcome**. The default policy does not blindly resend. An explicitly labeled unsafe baseline demonstrates how another submission can create a second mock task.
5. Retrieval and cancellation use bounded attempts. Record attempted and acknowledged child cancellation independently. After exhaustion, stop locally and preserve the unknown remote outcome.
6. A delayed completion cannot revive a terminal local task. Discard or record timed-out responses by request identity; do not assume peer timestamps provide a total order.
7. Mock transformation counters measure lab work only. They do not establish a transaction with an external service or an exactly-once side-effect guarantee.

### Pins and artifact availability

| Component | Proposed pin | Availability/license checked during planning |
| --- | --- | --- |
| Local acceptance interpreter | CPython **3.11.9**, invoked as `py -3.11` | Actually executed; SQLite **3.45.1** is bundled. `python` resolves to a different installed **3.12.7** interpreter, so Windows instructions must use the launcher. Python software license; bundled SQLite public-domain code. |
| Core runtime/test packages | **No third-party dependencies** | Standard library `argparse`, `json`, `urllib`, `http.server`, `sqlite3`, `threading`, `hashlib`, `unittest`. No SDK, model provider, packaging tool, database service, or Node runtime needed for the default demo. |
| A2A specification | **v1.0.1**, commit above; wire **1.0** | Tagged Markdown and proto actually fetched. Repository license **Apache-2.0** read. |
| Independent verification SDK | **a2a-sdk==1.1.5** | PyPI has a 255,110-byte universal wheel; Python >=3.10; **Apache-2.0**. Tag commit `9f0f00cb0417cb59958d3186d81651be7d9b9d59`. Wheel SHA256 `c1d63d36b79a097c62dd9be001fce21d5939f5a811a9c5afd0ba8082f13f68bf`. Not installed or executed. |
| SDK smoke HTTP client | **httpx==0.28.1** | PyPI has a 73,517-byte universal wheel; **BSD-3-Clause**. Wheel SHA256 `d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad`. Used only by the independent SDK check. |
| CI checkout action | v5.0.0 at **`08c6903cd8c0fde910a37f88322edcfb5dd907a8`** | GitHub tag API read; pin full commit in workflow. |
| CI Python action | v6.0.0 at **`e797f83bcb11b83ae66e0230d6156d7c80228e7c`** | GitHub tag API read; pin full commit in workflow. |

The official SDK manifest declares additional dependencies including protobuf, pydantic, Google API libraries, json-rpc, packaging, and culsans on Python <3.13. During the SDK milestone, resolve these into a separate, fully version/hash-pinned `requirements-sdk-check.txt`, verify their licenses and Windows wheels, and install only in a repository-local environment under a named resource lease. Their transitive versions and full environment availability are **not yet verified**. Do not add SDK extras for servers, telemetry, SQL, or gRPC. A failure to resolve this graph is a concrete milestone risk, not a reason to replace the core with another framework.

Use Apache-2.0 for repository code. Add `THIRD_PARTY.md` documenting the specification, interpreter/SQLite, optional SDK graph, and CI tools. Retain applicable notices for any code/schema actually reused. The downloaded planning references in `work/research/` are scratch evidence, not a vendored SDK or distributed protocol bundle.

## 5. Bounded milestones

Each milestone requires an explicit main-chat assignment. No milestone begins solely because this plan exists.

### M1 — first runnable end-to-end slice

Implement the dependency-free entry point, happy-path fixture, both Agent Cards and agents, `SendMessage`/`GetTask`, scoped validation, storage, HTTP handoff, and a report that links parent and child task/artifact IDs. Implement default blocking and explicit nonblocking send behavior. Add a concise offline quickstart and unit tests for parsing, atomic dedup lookup, and a successful transformation. Run one bounded loopback happy-path demo only when the assigned lease permits it. End with actual command evidence and stop for review.

Acceptance: `demo --scenario happy-path` exits 0, both tasks are completed, the expected normalized artifact is present, and the report contains a real HTTP handoff. Tests must observe two separately addressed server endpoints, not bypass the transport with direct method calls.

### M2 — required failure/recovery behavior

Add cancellation and its parent/child policy; known-task retrieval recovery; bounded failure/exhaustion; duplicate/conflicting messages; delay/response-loss injection; terminal-state guards; and basic `ListTasks` for developer inspection. Use deterministic gates and a fake monotonic clock for policy unit tests. Loopback integration tests use bounded timeouts and synchronization signals rather than timing-sensitive fixed sleeps. Acquire a named lease before the integration suite.

The `core` suite contains these eight bounded scenarios:

| Scenario | Fault and required evidence |
| --- | --- |
| `happy-path` | No fault; expected artifacts and linked completed tasks. |
| `duplicate-request` | Repeat the same initial message; one peer task, same task ID, one mock transformation. |
| `lost-ack` | Peer accepts, response is dropped; declared deduplication allows retry and returns the existing task. Evidence proves acceptance happened before the drop. |
| `delayed-after-cancel` | Completion or response is gated until after cancellation; the canceled local task stays canceled and no completion artifact is applied afterward. |
| `peer-unavailable-recovers` | A known peer task becomes unreachable through the harness, then reachable; bounded retrieval resumes that task without another submission. |
| `cancel-unavailable-recovers` | Local cancellation is recorded while peer access is unavailable; after recovery the child cancellation is acknowledged. No remote-canceled claim appears before acknowledgment. |
| `recovery-exhausted` | Peer stays unavailable through the attempt/deadline budget; the run stops, records unknown remote outcome, and does not loop indefinitely. |
| `unsafe-retry-baseline` | Explicitly unsafe retry against deduplication-disabled mock peer creates two tasks. The report labels the expected policy violation/risk and never treats it as a safe default. |

Test ambiguous submission without a dedup assumption separately: verdict inconclusive, no second `SendMessage`. Test cancellation/completion races, duplicate cancellation effects, malformed JSON/envelopes, mismatched response IDs, unknown tasks, conflicting message IDs, negative history limits, omitted/unsupported version, unsupported capabilities, and history bounds. For `ListTasks`, test context filtering, ordering, and cursor termination against the documented subset. Add a deliberately invalid response fixture to prove the contract checks can fail.

### M3 — independent wire verification and reviewable repository

Under a lease, create and freeze the SDK-only verification environment. Exercise the official SDK's JSON-RPC transport and proto types against the lab servers: card parse, nonblocking send, get, cancel, and expected errors. Include an ordinary blocking send. This is evidence for those interactions with this exact SDK and version, not a full interoperability certification. Keep the SDK import out of the core path; missing optional dependencies produce an actionable message, not a silently skipped claimed pass.

Finish architecture/protocol-policy documentation, scenario format, limitations, original contribution, license/attribution, a reproducible example report, and CI. CI runs core unit/integration scenarios and the pinned SDK check on Windows and Linux with CPython 3.11.9, no model calls. Record that hosted CI itself is unexecuted while the phase remains local. Main performs independent quickstart and evidence verification. Stop once the agreed MVP passes; no UI, framework migration, extra transport, or benchmark expansion.

## 6. Tests, reports, and acceptance commands

Tests assert behavior and independent expected values, including the unsafe negative control. They must not compare only against values produced by the same implementation helper. Fault scripts specify stage, method, occurrence number, and release gate; seed fixes scenario scheduling decisions, not wall-clock latency or OS port allocation. Compare semantic outcomes, not exact timestamp bytes.

The JSON report has a versioned schema and includes `protocol_spec`, `protocol_wire`, execution mode, seed, scenario/policy configuration, attempts, parent/child IDs, artifacts, and assertion results with event references. Each assertion has a scope (`protocol`, `implementation_policy`, or `harness`) and a result (`pass`, `fail`, `inconclusive`, or `not_checked`). The unsafe baseline preserves its failed safety-policy result and passes only its explicitly expected negative-control assertion. Aggregation must not erase that distinction.

The JSONL trace contains monotonically numbered observed events, agent/layer, method/request/message/task IDs, attempt, fault stage, and selected synthetic request/response bodies. Use an allowlist for logged headers. Bounded sample sizes and only fictional fixture data keep the evidence reviewable. Do not log credentials. `report` is an offline reader of this evidence, not an agent replay engine.

**The commands and output assertions below are proposed acceptance checks, not executed results.** Run from the repository root in PowerShell:

```powershell
py -3.11 -m a2a_recovery_lab --help
py -3.11 -m unittest discover -s tests/unit -v
py -3.11 -m a2a_recovery_lab demo --scenario happy-path --out work/acceptance-happy
py -3.11 -m unittest discover -s tests/integration -v
py -3.11 -m a2a_recovery_lab demo --suite core --seed 7 --out work/acceptance-core
py -3.11 -m a2a_recovery_lab report work/acceptance-core/report.json
```

Required assertions: help succeeds; all tests succeed; happy-path report says deterministic mock execution and A2A 1.0/v1.0.1; happy artifacts match literal fixture expectations; all eight scenarios reach their expected outcome within bounded attempts; the unsafe baseline visibly shows two tasks and a failed safety-policy assertion; lost-ack shows one task; no delayed completion changes a terminal task; unknown remote outcomes remain visible. A scenario whose observed outcome differs from its expected result exits 1. Invalid CLI/scenario input exits 2. Results classified inconclusive are counted separately, never converted to protocol passes.

Additional M3 commands, after resolution and lease allocation:

```powershell
py -3.11 -m venv work/sdk-check-venv
work/sdk-check-venv/Scripts/python.exe -m pip install --require-hashes -r requirements-sdk-check.txt
work/sdk-check-venv/Scripts/python.exe scripts/sdk_smoke.py --out work/sdk-check
```

Required assertions: official SDK version 1.1.5 reported, card and messages parsed by its proto types, send/get/cancel interactions complete as expected, errors map correctly, and no model credentials/network provider is involved. Installation needs network or a previously prepared local wheel cache; the core quickstart remains offline. Environment resolution, SDK execution, and CI cannot be reported successful before they run.

## 7. Risks and essential questions

- **Partial implementation:** clearly document and report the tested binding/operation coverage. Use TCK for broader checks; never label the repository fully compliant.
- **Policy mistaken for protocol:** require an explicit deduplication assumption for ambiguous retries and cite protocol sources only for protocol assertions.
- **Cancellation race:** local and remote outcomes can diverge. Keep their evidence separate and use conditional terminal transitions.
- **Fault realism:** a gateway models availability and response loss. It does not reproduce all networking failures or an arbitrary peer's process-crash behavior. Reports identify the injected boundary.
- **Test determinism:** use gates and fake clocks for policy decisions, bounded real networking for the handoff, and avoid latency benchmarks or exact scheduling claims.
- **SDK dependency availability:** only the top-level and HTTPX artifacts have been verified; freeze and license-check transitives before claiming a working oracle environment.
- **Local HTTP server limits:** loopback testbed only, no auth or production performance claim. No security assessment is implied by contract checks.
- **Evidence interpretation:** counters describe deterministic mock work; observed timings are not benchmarks. Trace reading is not fresh model execution.

No human answer is needed for routine architecture choices. The essential pending action is the main chat's accepted-plan review and explicit M1 assignment. Main must allocate any required resource lease before integration execution or dependency resolution/install; workers cannot edit the main-owned resource file.

## 8. Research record and evidence already observed

Every URL below was actually opened/read on 2026-10-07 through web tools or fetched directly. Mutable `main`/`latest` references establish the research context; the implementation baseline uses the pinned specification/SDK tags and commits.

| Exact source URL | Observation/use |
| --- | --- |
| https://github.com/a2aproject/A2A/releases | Latest listed release v1.0.1. |
| https://github.com/a2aproject/A2A/releases/tag/v1.0.1 | Release detail page. |
| https://api.github.com/repos/a2aproject/A2A/git/ref/tags/v1.0.1 | Full immutable baseline commit. |
| https://a2a-protocol.org/latest/specification/ | Current public specification read and compared with tagged source. |
| https://raw.githubusercontent.com/a2aproject/A2A/v1.0.1/docs/specification.md | Pinned operation/configuration/version/idempotency/error sections. Local fetched-file SHA256: `627ccfe6ffb1be2c56811c3dcc18780deb419f41cdc98248095c939b2d9dc9cb`. |
| https://raw.githubusercontent.com/a2aproject/A2A/v1.0.1/specification/a2a.proto | Required fields, enum names, SendMessage response wrapper, cards. SHA256: `e195bf96ab630c69797851970203e1b2b6b19528f2e9803b7d904b91a5104016`. |
| https://raw.githubusercontent.com/a2aproject/A2A/v1.0.1/LICENSE | Apache-2.0. |
| https://github.com/a2aproject/a2a-python | Official SDK compatibility table: wire 1.0 plus 0.3 compatibility. |
| https://api.github.com/repos/a2aproject/a2a-python/git/ref/tags/v1.1.5 | SDK tag commit. |
| https://raw.githubusercontent.com/a2aproject/a2a-python/v1.1.5/pyproject.toml | Dependency/extras manifest. SHA256: `5cdf8fdd9f297018cba28c9f91308f122264cab237acc41ee7c54bbb1f6ee776`. |
| https://raw.githubusercontent.com/a2aproject/a2a-python/v1.1.5/src/a2a/client/transports/jsonrpc.py | Independent transport has the chosen methods and proto conversion. |
| https://raw.githubusercontent.com/a2aproject/a2a-python/v1.1.5/src/a2a/client/client_factory.py | Card resolution, interface/version handling. |
| https://raw.githubusercontent.com/a2aproject/a2a-python/v1.1.5/LICENSE | Apache-2.0. |
| https://pypi.org/project/a2a-sdk/1.1.5/ and https://pypi.org/pypi/a2a-sdk/1.1.5/json | Actual wheel/sdist names, sizes, hashes, Python requirement. |
| https://pypi.org/project/httpx/0.28.1/ and https://pypi.org/pypi/httpx/0.28.1/json | SDK smoke client wheel/hash and BSD-3-Clause metadata. |
| https://raw.githubusercontent.com/a2aproject/a2a-tck/main/README.md and https://raw.githubusercontent.com/a2aproject/a2a-tck/main/LICENSE | TCK scope, invocation, Apache-2.0. Not installed/run. |
| https://raw.githubusercontent.com/a2aproject/a2a-itk/main/README.md and https://api.github.com/repos/a2aproject/a2a-itk/license | ITK scope; API identifies Apache-2.0 after raw-license web read failed. Not installed/run. |
| https://raw.githubusercontent.com/a2aproject/a2a-inspector/main/README.md and https://raw.githubusercontent.com/a2aproject/a2a-inspector/main/LICENSE | Inspector overlap and Apache-2.0. Not installed/run. |
| https://www.jsonrpc.org/specification | Request/response envelopes and request-ID correlation. |
| https://protobuf.dev/programming-guides/json/ | Canonical ProtoJSON naming/representation reference. |
| https://docs.python.org/3.11/library/http.server.html and https://docs.python.org/3.11/library/sqlite3.html | Standard-library capabilities and local-server limitation. These docs currently reflect a newer 3.11 patch; local interpreter version was checked separately. |
| https://api.github.com/repos/actions/checkout/git/ref/tags/v5.0.0 and https://raw.githubusercontent.com/actions/checkout/v5.0.0/README.md | CI action commit pin and documentation. |
| https://api.github.com/repos/actions/setup-python/git/ref/tags/v6.0.0 and https://raw.githubusercontent.com/actions/setup-python/v6.0.0/README.md | CI action commit pin and documentation. |

Local planning commands actually executed: `Get-Location`; reads of the human request, repository `AGENTS.md`, and own `status.json`; `rg --files`; `git status --short`; primary-source `Invoke-WebRequest`/`Invoke-RestMethod`; `Get-FileHash`; targeted `rg`/line reads; `python --version`; `py -0p`; `Get-Command python,py`; and `py -3.11 -c` interpreter/SQLite inspection.

Observed: initial repository inventory contained `AGENTS.md`; assigned paths are accessible; the launcher resolves CPython 3.11.9 while PATH `python` resolves 3.12.7; source tag/API and artifact metadata requests succeeded. No implementation or tests existed at that point. Planning scratch metadata is in `work/research/artifact-metadata.json`.

Unexecuted: package installation/resolution, build, core demo, unit/integration suites, SDK oracle, TCK/ITK, hosted CI, live model calls, benchmarks, publication, deployment. No lease was used. Next required assignment: **review this plan and assign M1 explicitly**.
