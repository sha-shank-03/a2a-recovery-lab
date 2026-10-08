# Scenarios and evidence format

Public CLI:

```text
python -m a2a_recovery_lab demo [--scenario NAME | --suite core] [--seed INTEGER] --out NEW_DIRECTORY
python -m a2a_recovery_lab report REPORT_JSON
```

Omitting scenario/suite selects happy-path. The eight public scenario names and outcomes are in README.md. No custom JSON scenario loader or long-lived serve command is provided. Built-in scenarios are small Python harness fixtures with fresh local stores, separate ephemeral peers and fixed stage/occurrence/gate decisions. The seed scopes initial message IDs; task UUIDs, ports and times vary.

| Injected condition | Evidence boundary |
| --- | --- |
| Duplicate submission | Identical message ID/content; observe the ledger decision and task ID. |
| Lost ACK | Successful agent dispatch/acceptance precedes socket reply drop. |
| Availability | Counted HTTP 503 responses before agent dispatch on GetTask or CancelTask. |
| Captured response delay | First GetTask result held by a gate until cancellation is acknowledged. |
| Late mock completion | Executor reaches its gate before cancel; release attempts an artifact update that the terminal guard declines. |
| Invalid peer response | Supplemental corruption fixture changes a valid task enum to lowercase before reply. |

Fault settings exist only inside the runner-owned fixture. No agent API exposes injection controls. Built-in names remain exactly eight; ambiguous submission and invalid response are supplemental test/oracle cases.

## Files

Each fresh scenario writes `report.json`, `events.jsonl`, `agent-cards.json` and ignored agent-local SQLite files. A core suite nests one directory per case and writes a root summary with relative report paths. Event numbers belong to their individual trace; suite summaries never merge or renumber them. Existing output directories are rejected to preserve evidence.

Core happy reports retain schema `1.0`; recovery/core summaries use `1.1`. SDK reports use `sdk-smoke-1.0`. These are project evidence schemas, not A2A protocol message formats. The reports explicitly carry specification release `1.0.1`, negotiated wire `1.0`, implementation/SDK version as applicable, execution mode, scenario/seed/policy, observed tasks/artifacts, checks and unverified scope.

Representative check shape:

```json
{
  "id": "no_duplicate_peer_tasks",
  "scope": "implementation_policy",
  "result": "fail",
  "expected": "One peer task under safe policy",
  "actual": 2,
  "expected_negative_control": true,
  "evidence_events": [15, 25]
}
```

The numbers above illustrate structure; inspect saved JSON for actual event IDs. Core scopes are `protocol`, `implementation_policy` or `harness`. SDK checks use `sdk_interoperability` and identify the installed oracle. `pass`, `fail` and `inconclusive` remain distinct. A scenario verdict assesses its intended outcome. The unsafe baseline passes expected-negative acceptance while retaining its failed safety-policy assertion and two tasks. The no-contract supplemental case retains an inconclusive remote outcome despite the harness knowing a task was accepted.

`peer_tasks_observed_by_harness` is privileged runner knowledge, separate from Coordinator's acknowledged child. A retrieval-exhausted parent may fail while a harness-observed child completed. The report never uses that observation to claim Coordinator recovered or canceled remote work.

JSONL events have contiguous `seq`, monotonic elapsed time, agent/layer/event and relevant observed IDs/payloads. Card discovery, requests/replies, acceptance/deduplication, task transitions, recovery attempts, injection boundaries and teardown are recorded. Payload snapshots are frozen before writing. Only selected headers and fictional ticket data are logged. Event references are review links, not cryptographic proof of authenticity or a globally ordered distributed trace.

## Execution versus reading

`demo` starts fresh HTTP agents running deterministic rules. The SDK script starts fresh HTTP agents and uses the installed SDK to interact with them. `report` only reads saved JSON and prints `recorded_report_read; no fresh agent execution`; it is not a model rerun or executable workflow replay. All shipped demonstrations are `deterministic_mock_over_http`. There is no live-model/provider mode.

Core CLI exits 0 for expected scenario outcomes, 1 for an unexpected assertion failure and 2 for invalid input/existing output. Optional SDK missing dependencies exit 2; failing SDK checks exit nonzero. No missing optional dependency is silently marked passing. Gates/waits/cleanup are bounded for shipped fixtures. See EVIDENCE.md for commands actually run and hosted/Linux checks still unexecuted.
