# A2A Recovery Lab

[![CI](https://github.com/sha-shank-03/a2a-recovery-lab/actions/workflows/checks.yml/badge.svg)](https://github.com/sha-shank-03/a2a-recovery-lab/actions/workflows/checks.yml)

Open-source Apache-2.0 project. [Project context](docs/PROJECT_CONTEXT.md) · [Independent local verification](docs/INDEPENDENT_VERIFICATION.md) · [Contributing](CONTRIBUTING.md)

A local developer testbed for agent handoffs, task state, and inspectable recovery decisions. Two deterministic ticket agents communicate through separately addressed HTTP servers and produce assertions linked to observed wire events. **The agreed local MVP passed final coordinating-agent verification on Windows: 34 unit tests, seven HTTP tests, eight core outcomes with a retained failed safety control, and 26 scoped installed official-SDK checks.**

Specification baseline: **A2A v1.0.1**, commit `3303592588e388e62e0f69f701af531d2f4e3991`; negotiated wire version **1.0**; JSON-RPC 2.0 binding. The core uses Python's standard library. It makes no model/provider calls and needs no credentials, downloads, Docker, or package installation.

## Offline/mock quickstart

From the repository root on Windows, using the installed CPython 3.11 interpreter:

```powershell
py -3.11 -m a2a_recovery_lab demo --scenario happy-path --out work/my-first-demo
py -3.11 -m a2a_recovery_lab report work/my-first-demo/report.json
```

Choose a new output directory each time. Existing evidence is preserved. On a machine with Python 3.11 on PATH, use `python3.11`. M1/M2 execution was verified on Windows with CPython 3.11.9; Linux execution is pending.

POSIX equivalent (prepared; Linux has not run locally):

```sh
python3.11 -m a2a_recovery_lab demo --scenario happy-path --out work/my-first-demo
python3.11 -m a2a_recovery_lab report work/my-first-demo/report.json
```

The runner binds two ephemeral IPv4 loopback ports, uses bounded waits, and closes both servers before returning. A scenario writes:

- `report.json`: tasks, artifacts, protocol/policy/harness checks, and event references.
- `events.jsonl`: observed card, HTTP, handoff, task, recovery, fault, and teardown events.
- `agent-cards.json`: cards observed during that run.
- Two local SQLite databases containing task and initial-message deduplication records.

`report` starts no servers and labels its output `recorded_report_read`. [The preserved M1 report](evidence/m1-final/report.json) records mock computation over actual HTTP; its ports are closed. [EVIDENCE.md](EVIDENCE.md) separates executed results from prepared checks.

## M2 recovery suite

The eight-scenario suite ran on 2026-10-08 under the named HTTP resource lease. [The saved suite](evidence/m2-core/report.json) passed all expected outcomes, with one failed safety-policy assertion retained. In this portfolio workspace, HTTP/integration execution requires the main chat's named resource lease.

```powershell
py -3.11 -m a2a_recovery_lab demo --suite core --seed 7 --out work/my-core-suite
py -3.11 -m a2a_recovery_lab report work/my-core-suite/report.json
py -3.11 -m a2a_recovery_lab demo --scenario lost-ack --seed 7 --out work/my-lost-ack
```

The public core suite contains exactly these eight scenarios, run sequentially:

| Scenario | Observed outcome in the saved run |
| --- | --- |
| `happy-path` | Linked parent/child tasks complete with literal fixture output. |
| `duplicate-request` | Repeated parent and child message IDs resolve to their original tasks. |
| `lost-ack` | Peer accepts before the response drops; retry returns the same task under an explicit peer deduplication assumption. |
| `delayed-after-cancel` | Both tasks cancel; a captured late response and late mock artifact cannot revive a terminal task. |
| `peer-unavailable-recovers` | After child acknowledgment, failed GetTask exchanges recover by retrieving that known task ID. |
| `cancel-unavailable-recovers` | Parent cancels while child cancellation is pending; a later acknowledgment establishes the child's canceled outcome. |
| `recovery-exhausted` | Bounded retrieval attempts exhaust; parent fails locally and remote outcome stays unknown to Coordinator. |
| `unsafe-retry-baseline` | Explicit unsafe retry against a peer with deduplication disabled creates two tasks and fails the no-duplicate safety assertion. |

Suite exit 0 means the **expected scenario outcomes** passed. The unsafe baseline retains its failed safety-policy check, separately from its passing expected-negative-control check; the printed report and suite summary expose that failure. A transport-ambiguous submission without a deduplication contract is covered by a separate integration test and [saved supplemental evidence](evidence/m2-checks/ambiguous-submission/report.json): it is not resent and its remote result remains inconclusive. It is not a ninth public core scenario. [The corrupted-response case](evidence/m2-checks/invalid-peer-response/report.json) fails locally without retry. [Inspection receipts](evidence/m2-validation/inspection.json) verify traces, direct SQLite contents and twenty closed-port observations across these ten runs.

Fault stages use gates and fixed occurrence counts. The seed scopes reproducible initial message IDs; it does not make task UUIDs, ports, timestamps, or thread scheduling deterministic. Each case has fresh stores. The suite preserves nested reports/traces rather than flattening their event numbers.

## What the agents do

Coordinator receives fictional ticket `INC-0042`, discovers Normalizer's Agent Card, sends a child message, records an acknowledged task ID, and retrieves that task over HTTP. Normalizer collapses title whitespace and normalizes priority. Its artifact is checked against literal fixture values, including a canonical-input SHA256. Coordinator's artifact references observed child task/artifact IDs.

```text
Runner --HTTP--> Coordinator --HTTP--> Normalizer
                   | parent store        | child store + message ledger
                   +---- linked artifact/report/JSONL evidence ----+
```

Normal sends omit `returnImmediately`, so the response waits for terminal/interrupted state. Coordinator submits the child with `returnImmediately: true`. Cancellation cases use immediate parent submission to let the runner intervene. Default recovery bounds are twelve attempts and two seconds **per operation**, with each child HTTP exchange capped at the smaller of one second or its remaining budget. Exhaustion uses three retrieval attempts. Card discovery has one one-second attempt. These are local policies, not A2A guarantees.

## Verification

```powershell
py -3.11 -m unittest discover -s tests/unit -v
py -3.11 -m unittest discover -s tests/integration -v
```

No-socket tests cover literal output, scoped wire validation, atomic concurrent deduplication/conflict rejection, persisted lookup, cancellation/completion races, terminal guards, keyset pagination, and recovery decisions with a fake clock. HTTP tests cover blocking/immediate send, mapped malformed/version/history/correlation errors, the eight scenarios, ambiguous submission without retry, deliberately invalid peer responses, and clean teardown. Tests write under `work/`; gates synchronize critical fault stages. See EVIDENCE.md for actual counts and execution status.

## Optional official SDK check

This separate environment verifies the lab with **a2a-sdk 1.1.5** / **httpx 0.28.1**, their installed JSON-RPC transport/card resolver, and official protobuf message/task types. [The saved SDK report](evidence/m3-sdk/report.json) contains 26 actual assertions, source hashes and wire-event references. It checks gated ordinary blocking send, immediate send, linked GetTask/history, duplicate submission, parent/child cancellation and late-artifact rejection, expected error classes, version headers, card/message parsing, and invalid enum rejection. This is scoped interoperability evidence for one SDK/transport/profile, not certification.

Windows (package installation needs internet or a local wheel cache):

```powershell
py -3.11 -m venv work/sdk-check-venv
work/sdk-check-venv/Scripts/python.exe -m pip --isolated install --index-url https://pypi.org/simple --require-hashes --only-binary=:all: --disable-pip-version-check -r requirements-sdk-check.txt
work/sdk-check-venv/Scripts/python.exe -m pip check
work/sdk-check-venv/Scripts/python.exe scripts/sdk_smoke.py --out work/my-sdk-check
py -3.11 -m a2a_recovery_lab report work/my-sdk-check/report.json
```

POSIX equivalent (prepared; matching Linux wheel hashes/availability are verified, execution remains pending):

```sh
python3.11 -m venv work/sdk-check-venv
work/sdk-check-venv/bin/python -m pip --isolated install --index-url https://pypi.org/simple --require-hashes --only-binary=:all: --disable-pip-version-check -r requirements-sdk-check.txt
work/sdk-check-venv/bin/python -m pip check
work/sdk-check-venv/bin/python scripts/sdk_smoke.py --out work/my-sdk-check
python3.11 -m a2a_recovery_lab report work/my-sdk-check/report.json
```

Create the optional environment once; use a new output directory for each check. The core quickstart works without these packages. A missing SDK makes the optional script exit 2 with setup guidance, without producing a passing result. [The complete runtime lock](requirements-sdk-check.txt) pins 32 packages with Windows/Linux binary-wheel hashes. [Artifact/license receipts](evidence/m3-dependencies/artifacts.json) and [attribution](THIRD_PARTY.md) cover the entire resolved Python graph. No SDK extras, global installs, source builds, provider clients or credentials are used by the check.

## Prepared CI

[checks.yml](.github/workflows/checks.yml) defines read-only token permissions, checkout without persisted credentials, full action commit pins, Python **3.11.9**, and bounded sequential Windows/Linux core and optional SDK jobs. It needs no secrets or model calls. The workflow is prepared; **hosted CI and Linux execution have not run**. Current evidence is actual local Windows execution.

## Boundaries

Current source supports public cards plus `SendMessage`, `GetTask`, `CancelTask`, and a documented basic `ListTasks` subset for new fictional-ticket tasks. It handles canonical lowerCamelCase fields, enum names/numeric ROLE_USER, major/minor version compatibility, task wrappers, and request-ID correlation. It does not implement every ProtoJSON coercion or A2A operation. JSON-RPC batches/notifications, continuation, non-data content, tenant routing, and chunked requests are outside this scope.

Message-ID deduplication and changed-payload conflict rejection are local policies; send idempotency is optional in A2A. The durable ledger does not resume an interrupted executor or prove exactly-once external effects. Parent cancellation is separate from remote cancellation. After a bounded cancellation flight exhausts, repeated local cancel requests do not restart that flight; reconciliation requires further explicit work. ListTasks cursors are local keyset cursors without authentication or snapshot isolation.

The server is a bounded loopback fixture without authentication or production hardening. Passing scoped core/SDK checks cannot establish full A2A compliance, security, LLM quality, or production reliability. SDK transports other than JSONRPC, full TCK/ITK, general crash recovery and external side effects remain outside the verified profile.

See [architecture](docs/ARCHITECTURE.md), [protocol versus policy](docs/PROTOCOL_POLICY.md), [scenario/report format](docs/SCENARIOS_AND_REPORTS.md), and [the accepted plan](PLAN.md). The contribution is a workflow evidence format that exposes recovery assumptions, local/remote uncertainty, and a retained failing safety control, with an independent installed-SDK wire check. It overlaps with official [TCK](https://github.com/a2aproject/a2a-tck), [ITK](https://github.com/a2aproject/a2a-itk), and [Inspector](https://github.com/a2aproject/a2a-inspector), and claims no novel protocol or replacement for those tools.

Code is licensed under [Apache-2.0](LICENSE). See [third-party attribution](THIRD_PARTY.md).

## Get the source

```sh
git clone https://github.com/sha-shank-03/a2a-recovery-lab.git
cd a2a-recovery-lab
```

Follow the quickstart above for runtime/dependency setup. Demos use fictional/mock data; initial dependency setup, where required, is separate from offline execution.
