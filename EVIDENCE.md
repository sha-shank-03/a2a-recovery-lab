# Execution evidence

M1/M2 are independently accepted. Their historical evidence is preserved below. M3 installed official-SDK verification and final local package results are recorded at the end; whole-repository independent acceptance is pending. Linux/hosted CI remain unexecuted.

Actual local verification on **2026-10-07**, Windows, CPython **3.11.9**, bundled SQLite **3.45.1**. Commands below were run from this repository's assigned root. The main-owned `a2a-recovery-lab` resource lease authorized the bounded two-peer networking/integration slice; no SDK installation was permitted or performed.

## Commands and observed results

| Command | Actual result |
| --- | --- |
| `py -3.11 -m a2a_recovery_lab --help` | Exit 0; exposed `demo` and recorded `report` reader. |
| `py -3.11 -m unittest discover -s tests/unit -v` | Exit 0; **16 tests passed**. Final run after the correlation fix: `Ran 16 tests ... OK`. |
| `py -3.11 -m unittest discover -s tests/integration -v` | Exit 0; **4 tests passed**, including absent/false blocking mode, gated nonblocking send, task/version/error correlation checks, and the subprocess CLI with two actual HTTP servers. Final run after the fix: `Ran 4 tests ... OK`. |
| `py -3.11 -m a2a_recovery_lab demo --scenario happy-path --out evidence/m1-demo` | Exit 0; first preserved demo: 10 assertions passed, both tasks completed, clean teardown. |
| `py -3.11 -m a2a_recovery_lab report evidence/m1-demo/report.json` | Exit 0; explicitly printed `recorded_report_read; no fresh agent execution`. |
| `py -3.11 -m a2a_recovery_lab demo --scenario happy-path --out evidence/m1-final` | Exit 0 on final source; **10 assertions passed, 0 failed**. Distinct HTTP origins, linked completed tasks/artifacts, literal normalized values, one mock transformation, and clean server shutdown. |
| `py -3.11 -m a2a_recovery_lab report evidence/m1-final/report.json` | Exit 0; read the preserved final result without executing agents. |

The first tests passed. A subsequent code review found that invalid `params` could lose a valid JSON-RPC request ID. The handler was corrected, a real HTTP regression assertion was added, and both suites were rerun successfully. No acceptance expectations were weakened.

A scratch SHA256 calculation first failed because PowerShell/native `-c` quoting stripped literal JSON quotes. It was rerun successfully through stdin using a single-quoted here-string. The test/fixture stores the independent literal hash `d37e90ba1e3f588afb51f9eb954856269c6eb06deb9e8247e2fd8dfce98ed027`. This was a shell preparation failure, not a passing test result.

The standard Apache-2.0 LICENSE text was fetched from the pinned specification repository. Current Python license and SQLite copyright primary pages were also read on 2026-10-07; see THIRD_PARTY.md. No package or runtime installation happened.

## Preserved final-run observations

```text
PASS happy-path | deterministic_mock_over_http | spec=1.0.1 wire=1.0
Checks: 10 passed, 0 failed
HTTP peers: coordinator=http://127.0.0.1:65402, normalizer=http://127.0.0.1:65401
Task parent: abbeb386-54f2-41f3-a2e2-4a09693d23c0 TASK_STATE_COMPLETED
Task child: 514fdaf6-f90a-46da-9222-cd1e4830e47d TASK_STATE_COMPLETED
```

These are recorded observations, not active endpoints. Inspect [the report](evidence/m1-final/report.json), [JSONL wire/task evidence](evidence/m1-final/events.jsonl), and [Agent Cards](evidence/m1-final/agent-cards.json). The final trace includes a Coordinator-origin HTTP `SendMessage`, Normalizer receiving that request at its separate `/rpc`, GetTask retrieval, linked task/artifact IDs, and two clean server-stop observations. SQLite databases are local run output and ignored by Git; the reproducible command creates new stores.

Expected normalized ticket is literal data: ticket ID `INC-0042`, title `Checkout returns 502`, priority `high`, and the hash above. Unit and integration acceptance expectations are outside the agent executors. IDs, ports, and event times vary between runs; they are not benchmark or performance claims.

## Unexecuted at the M1 boundary and out of scope

- At the M1 boundary, M2 HTTP cancellation/fault/recovery/ListTasks and unsafe baseline were unexecuted. The later M2 results are below.
- M3 SDK graph resolution/installation, independent official-SDK smoke, CI definition/execution, Linux verification, broader TCK/ITK suites.
- General process-crash recovery, production security/auth/TLS, and external side-effect guarantees.
- Live model execution, model-quality evaluation, benchmarks, publication, pushes or deployment.

Main independently accepted M1 and released its lease. The later M2 assignment authorizes source plus lightweight no-socket tests only until a named HTTP resource lease is granted. Neither milestone completes the entire PLAN.md.

## M2 source preparation — actual results, 2026-10-07

Current source version: **0.2.0**. Actual interpreter remains CPython **3.11.9** on Windows. Main's M2 review authorizes source/policy/store preparation but explicitly queues HTTP execution. At this boundary `coordination/resources.json` has no worker A2A M2 lease. No HTTP demo/integration command has been run on M2, and no SDK/dependency installation or CI expansion has occurred.

Implemented source: bounded transport recovery, honest ambiguous submission, cancellation propagation/terminal guards, basic ListTasks context/state/timestamp/keyset subset, runner-owned acceptance-before-response-loss and captured-response delay faults, exactly eight public scenarios, separate invalid-response/ambiguous-submission integration checks, and explicit retained unsafe safety failure. README/architecture/policy docs describe both semantics and unexecuted HTTP status.

| Command/check actually run | Exit / observed result |
| --- | --- |
| `py -3.11 -m unittest discover -s tests/unit -v` during preparation | Exit 0; preliminary source iterations passed 30, then 33 tests. |
| Final unit discovery under the socket-creation guard below | Exit 0; **34 tests passed**, `Ran 34 tests in 1.169s`, `socket.socket calls=0`. Raw local output: `work/m2-source-unit.txt`. |
| `py -3.11 -m a2a_recovery_lab --help` | Exit 0; command parser imports prepared M2 source without opening servers. |
| `py -3.11 -m a2a_recovery_lab demo --help` | Exit 0; exposes the exact eight scenario choices, `--suite core`, `--seed`, and required new `--out`. |
| `git status --short` / targeted documentation search | Exit 0; deliverables remain inside the assigned repository; `work/` and SQLite files are ignored. M3 dependencies/CI remain explicitly deferred. |

The final no-socket test command was run through PowerShell stdin:

```powershell
@'
import sys
import unittest
from unittest.mock import patch

with patch('socket.socket', side_effect=AssertionError('Socket creation forbidden during M2 source preparation')) as blocked:
    suite = unittest.defaultTestLoader.discover('tests/unit')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    blocked.assert_not_called()
print(f'No-socket guard: socket.socket calls={blocked.call_count}; tests={result.testsRun}')
sys.exit(0 if result.wasSuccessful() else 1)
'@ | py -3.11 - 2>&1 | Tee-Object -FilePath work/m2-source-unit.txt
exit $LASTEXITCODE
```

Tests include independent literal normalization/hash, malformed/envelope/version/history/correlation/schema cases, concurrent/persisted deduplication and conflicting payload rejection, cancellation/completion race, repeated cancellation, late artifact rejection, late acknowledged child linking, canceled/unacknowledged submission uncertainty, context/order/cursor termination/artifact omission, fake-clock retry/deadline limits, known-ID retrieval, ambiguous submission without resend, explicit unsafe duplication, and deliberately invalid response rejection. Fault-controller unit checks supply dispatch results directly; they do not establish actual HTTP loss/delay behavior.

Source review before this final run added an explicit completion-gate wait before cancellation, so prepared HTTP fixtures can observe an actual late artifact attempt. It also corrected canceled/unacknowledged execution to record `unknown_child_id` rather than leave cancellation indefinitely `pending_child_id`; a no-socket agent/store regression passes. Report endpoint checks require RPC observations at both agents. No acceptance expectation was weakened.

A documentation replacement patch was initially rejected because delete/add operations targeted the same file in one patch. No file changed in that rejected operation; it was reapplied as updates. This was an editing-tool failure, not a test result.

### Prepared but unexecuted at the 2026-10-07 source boundary

- `py -3.11 -m unittest discover -s tests/integration -v`: four retained M1 test methods plus three prepared recovery methods. The core method runs all eight scenarios; additional methods cover no-contract ambiguity and corrupted peer response.
- `py -3.11 -m a2a_recovery_lab demo --suite core --seed 7 --out evidence/m2-core`: intended new preserved report/JSONL/card/store evidence; **directory/report not generated yet**.
- M2 recorded-report CLI verification, event-reference/SQLite assertions and observed port closure after actual runs.
- Independent main M2 review, followed by a separate M3 assignment if accepted.

Historical worker boundary: **awaiting_resource_lease** after source/unit readiness was reported to main. Existing M1 evidence was preserved. The human resumed coordination and main granted a named M2 HTTP lease on 2026-10-08; actual execution follows.

## M2 HTTP execution — actual results, 2026-10-08

Main granted the worker lease at **2026-10-08T01:44:51.142629Z**, and it was read/confirmed before execution. All commands ran sequentially from the assigned repository with CPython **3.11.9** / SQLite **3.45.1**. Source stayed at **0.2.0**; no implementation changes were needed after the first actual HTTP run. Prior 34-test no-socket evidence is preserved. These are deterministic mock agents over real owned loopback HTTP, not live model evaluation.

| Actual argv | Exit / observed result |
| --- | --- |
| `py -3.11 -m unittest discover -s tests/integration -v` | Exit **0**; **7 tests passed** in **9.424s**, including all eight core cases, four retained M1 methods, no-contract ambiguity and invalid peer response. [Raw output](evidence/m2-validation/integration.txt). |
| `py -3.11 -m a2a_recovery_lab demo --suite core --seed 7 --out evidence/m2-core` | Exit **0**; **8/8 expected outcomes**, **one retained failed safety check**, no unexpected failures. [Suite report](evidence/m2-core/report.json), [CLI output](evidence/m2-validation/core-cli.txt). |
| `py -3.11 -m a2a_recovery_lab report evidence/m2-core/report.json` | Exit **0**; labels `recorded_report_read; no fresh agent execution`. SHA256 unchanged before/after: `5cc3af62280d0cd9f184e86d5e1bd909814fdf50a3d93f7e99fa8eae9b0e1dd3`. [Output](evidence/m2-validation/report-cli.txt). |
| Supplemental `py -3.11 -` script below | Exit **0**; saved ambiguous no-resend/inconclusive and corrupted-response/no-retry HTTP evidence outside the eight-case core. [Output](evidence/m2-validation/supplemental-cli.txt). |
| `py -3.11 work/inspect_m2.py` | Exit **0**; file/JSONL/correlation/direct-SQLite/literal-output assertions passed, **20 closed-port observations** across eight core/two supplemental cases. [Receipt](evidence/m2-validation/inspection.json). |
| `Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'py.exe'" ...` | Exit **0**; no matching processes remained. [Process receipt](evidence/m2-validation/process-check.json). |

The supplemental stdin script actually executed these operations in order:

```python
from pathlib import Path
from a2a_recovery_lab.scenarios import run_scenario

base = Path('evidence/m2-checks')
ambiguous = run_scenario('ambiguous-submission', base / 'ambiguous-submission', seed=7, _ambiguous=True)
assert ambiguous['verdict'] == 'pass'
assert ambiguous['summary']['inconclusive'] == 1
assert ambiguous['tasks']['child'] is None
assert ambiguous['tasks']['parent']['metadata']['submissionAttempts'] == 1
invalid = run_scenario('invalid-peer-response', base / 'invalid-peer-response', seed=7, _invalid_response=True)
assert invalid['tasks']['parent']['status']['state'] == 'TASK_STATE_FAILED'
assert invalid['tasks']['parent']['metadata']['failureType'] == 'WireError'
assert invalid['tasks']['parent']['metadata']['submissionAttempts'] == 1
```

| Core case | Observed preserved assertions |
| --- | --- |
| happy-path | 10 pass / 0 fail; both tasks completed; independent literal normalization/hash. |
| duplicate-request | 8 pass / 0 fail; both stores retain one task and one submission row. |
| lost-ack | 10 pass / 0 fail; acceptance precedes response drop; two same-message submissions resolve to one peer task under explicit dedup assumption. |
| delayed-after-cancel | 11 pass / 0 fail; both tasks canceled; late response and attempted mock artifact discarded. |
| peer-unavailable-recovers | 9 pass / 0 fail; one SendMessage, GetTask retries only the known ID; completed after availability returned. |
| cancel-unavailable-recovers | 11 pass / 0 fail; remote pending while unavailable, acknowledged after recovery; canceled stores contain no artifacts. |
| recovery-exhausted | 10 pass / 0 fail; exactly three retrieval attempts; local parent failed and Coordinator's remote outcome remains unknown, even though independent harness/store inspection sees the child completed. |
| unsafe-retry-baseline | 9 pass / **1 fail**; peer has **two completed tasks / zero ledger rows**. `no_duplicate_peer_tasks` remains **fail**; expected-negative assertion passes separately. |

The supplemental ambiguous report retains **one inconclusive** remote outcome, one SendMessage, no invented child ID and a locally failed workflow. Harness-only inspection sees one accepted/completed peer task; that knowledge does not repair Coordinator's uncertainty. The invalid-response case records one corrupted reply, one SendMessage and local `WireError` failure without retry.

Inspection read saved data without invoking agent code. Every report assertion references existing contiguous JSONL event numbers; both agents receive RPC traffic, request/response correlation and version headers match, both stop events are clean, each reopened database has expected tasks/submissions/states, and completed peer artifacts match independent fixture literals. Connection probes observed all twenty saved endpoints closed. SQLite files are local ignored run outputs; JSONL/reports/cards/receipts are retained and reproducible fresh runs create new databases. The inspection script is a local intermediate under `work/`, not a shipped CLI.

No acceptance test was weakened, and no retry/timing expectation was expanded to force a pass. Core PASS means intended scenario outcomes, not universal safety-policy success. Mock computation, local harness observations and protocol/implementation assertions stay separately labeled.

M2 delivery boundary: **slice_review**. Owned commands exited and servers closed; main subsequently independently accepted M2 and assigned M3. Linux, full TCK/ITK conformance, production/crash recovery, live models, benchmarks and publication remained unexecuted.

## M3 installed official-SDK verification — actual results, 2026-10-08

Main independently accepted M2 (34 unit/7 HTTP tests, fresh eight cases, 99 main assertions and 16 closed-port observations) and granted the named M3 worker lease at **2026-10-08T02:07:05.268937Z**. It was confirmed before downloads/install/integration. Cwd for all commands: `C:/Users/shash/Documents/CodexPortfolios/agentic-ai-2026-10-07/a2a-recovery-lab`. CPython **3.11.9**, Windows AMD64. Fresh disk before the optional environment: **26.13 GiB**. No global installation or SDK/core dependency substitution occurred.

The accepted size bounds were 250 MiB downloads / 1 GiB installed. Actual selected Windows/Linux wheels: **35 files / 16,498,589 bytes**. The initial pip resolver also fetched **9,945,648 bytes** of full wheels; known full-wheel payload total **26,444,237 bytes** (about 25.2 MiB), plus small metadata/license requests. This is artifact accounting, not an exact network wire-byte counter. The optional venv occupies **68,508,111 bytes** (about 65.3 MiB). The complete runtime graph has **32 exact pinned packages**; 49 original license files and two extracted author/license notices are retained. [Artifact/marker/license declarations](evidence/m3-dependencies/artifacts.json), [download/license mappings](evidence/m3-dependencies/download-licenses.json), [installed/size receipt](evidence/m3-dependencies/installed.json).

| Actual argv / action | Exit / observed result |
| --- | --- |
| `py -3.11 -m venv work/sdk-check-venv` | **0**; separate repo-local optional environment; bootstrap pip 24.0 / setuptools 65.5.0. |
| `work/sdk-check-venv/Scripts/python.exe -m pip --isolated install --dry-run --ignore-installed --only-binary=:all: --no-cache-dir --disable-pip-version-check --index-url https://pypi.org/simple --report work/sdk-resolution.json a2a-sdk==1.1.5 httpx==0.28.1` | **0**; resolved 32 runtime packages with binary wheels, no extras. [Raw resolver output](evidence/m3-validation/m3-resolve.txt). |
| `work/sdk-check-venv/Scripts/python.exe work/prepare_sdk_lock.py` | First **1** from Windows default text decoding of pip's UTF-8 report; corrected explicit UTF-8, then **0**. Both platform tags/dependency markers, license declarations and artifact sizes checked. [Final output](evidence/m3-validation/m3-artifact-preflight-final.txt). |
| `work/sdk-check-venv/Scripts/python.exe work/download_sdk_wheels.py` | Preparation failures **1** for omitted license files; final **0** after fetching verified tagged/commit license texts. All 35 wheel hashes match; 49 license texts retained. [Final output](evidence/m3-validation/m3-wheel-audit-complete.txt). |
| `work/sdk-check-venv/Scripts/python.exe -m pip --isolated install --no-index --find-links work/sdk-wheels --require-hashes --only-binary=:all: --disable-pip-version-check --report work/sdk-installed.json -r requirements-sdk-check.txt` | First **1** from a generated continuation line containing an unintended `+`; no packages installed in that attempt. Lock regenerated as valid one-line pins; final **0**, full audited graph installed offline. [Final output](evidence/m3-validation/m3-install-final.txt). |
| `work/sdk-check-venv/Scripts/python.exe -m pip check` | **0**; `No broken requirements found.` |
| `work/sdk-check-venv/Scripts/python.exe scripts/sdk_smoke.py --out work/sdk-first` | **0**; first real installed SDK run passed **26 checks**. |
| `work/sdk-check-venv/Scripts/python.exe scripts/sdk_smoke.py --out evidence/m3-sdk` | **0**; final preserved installed SDK run passed **26 checks / 0 failures**, 139 observed events, both peers stopped. [Report](evidence/m3-sdk/report.json), [trace](evidence/m3-sdk/events.jsonl), [output](evidence/m3-validation/m3-sdk-final.txt). |
| `py -3.11 scripts/sdk_smoke.py --out work/missing-sdk-evidence` | Expected **2** from the SDK-free core interpreter, actionable setup guidance, no evidence directory or claimed pass. Wrapper verified that outcome. [Output](evidence/m3-validation/m3-sdk-missing.txt). |
| `py -3.11 -m a2a_recovery_lab report evidence/m3-sdk/report.json` | **0** from the SDK-free interpreter; labels recorded reading and preserves SHA256 `810959fec20fb3bc461a021c14606b9d1bb32080b55fbe6287bbf89e7d6d2978`. [Output](evidence/m3-validation/m3-sdk-report-read.txt). |
| `py -3.11 -m unittest discover -s tests/unit -v` | **0**; final stdlib core **34 tests pass**, 1.006s. [Output](evidence/m3-validation/m3-core-unit.txt). |
| `py -3.11 -m unittest discover -s tests/integration -v` | **0**; final stdlib core **7 HTTP tests pass**, 7.486s, including eight-case core and retained safety failure/uncertainty. [Output](evidence/m3-validation/m3-core-integration.txt). |
| `py -3.11 -m a2a_recovery_lab demo --scenario happy-path --out evidence/m3-core-happy` | **0**; SDK-free default path, **10 checks pass / 0 fail**, linked completed tasks. Core report correctly retains its M2 implementation coverage. [Report](evidence/m3-core-happy/report.json). |
| `py -3.11 work/inspect_m3.py` | **0**; saved evidence/source/license/version/SQLite/correlation/event references pass, **four closed ports** observed, SDK absent from core interpreter, prepared CI safeguards statically checked. [Inspection](evidence/m3-validation/inspection.json). |
| Read-only Win32 process inventory after commands | **0**; no python.exe/pythonw.exe/py.exe remained. [Receipt](evidence/m3-validation/process-check.json). |

Actual primary-source API reads reverified both action commits and their MIT licenses. [Action pins](evidence/m3-dependencies/ci-actions.json), [license metadata](evidence/m3-dependencies/ci-action-licenses.json). The workflow has contents-read permissions, no persisted checkout credentials, Python 3.11.9, fixed action SHAs, job timeouts, matrix concurrency one, and SDK jobs after core jobs. Static text/pin/scope checks ran; **no YAML parser, hosted workflow or Linux execution ran**.

### SDK assertions and source independence

Installed `A2ACardResolver`, `JsonRpcTransport`, SDK protobuf AgentCard/Message/SendMessageResponse/Task types and SDK mapped error classes drive the real HTTP requests and parse the replies. Inspected installed resolver/transport/generated-type files and their SHA256 values appear in the SDK report. The oracle does not use the core wire parser to validate SDK responses. HTTPX event hooks observe the SDK's own exchanges and enforce the two owned loopback origins. Ambient proxies/redirects and SDK tracing are disabled; no exporter, credentials, model or remote agent provider is configured.

The 26 checks cover typed card/interface/message parsing; omitted default blocking configuration; completion-gated blocking behavior; SendMessageResponse wrapper; literal normalized data/hash; known-ID GetTask/history zero and linked child/history Message; repeated message same task; unknown task, noncancelable completed task and invalid history error classes; unsupported/missing version errors and compatible patch version; gated immediate return; typed local cancel and separately acknowledged child cancel; repeat-cancel effects; late artifact rejection; invalid lowercase enum rejection by SDK protobuf parsing; clean teardown and refused connections at both SDK ports.

Direct reopened SQLite stores independently contain two task/submission rows per SDK agent: one completed, one canceled, with no canceled artifacts. SDK request/response IDs match. All 139 event IDs are contiguous and all 26 check references point to observed events. The stdlib happy run adds 43 events and two closed ports. Times are observations, not benchmarks. M1/M2 evidence and the failed unsafe safety control are unchanged.

### Preparation corrections and remaining checks

aiologic/culsans wheels declare ISC runtime licensing but omit standalone license files. Initial guessed `v`-prefixed license URLs returned 404; official tag APIs showed unprefixed tags. Matching pinned commits supplied ISC/0BSD/CC-BY-4.0/CC0 license texts. Actual SPDX author notices from wheels are retained. A read of installed SDK files was attempted while pip was still installing, and failed because the SDK package was not installed yet; it was repeated after pip completed. These were preparation failures, not successful SDK checks. The UTF-8 decoder and lock-line errors above were corrected without changing version pins, relaxing hashes, adding source builds or weakening acceptance.

The complete lock and THIRD_PARTY.md attribute every resolved Python runtime package. Mandatory transitive cryptography/Google/OpenTelemetry API packages came from base SDK dependencies; no SDK extras were selected. Prepared Windows/POSIX setup instructions and CI reflect the exact graph. The optional environment/wheels remain ignored local files available for main's bounded review.

Remaining unexecuted: hosted CI/Linux execution, full protocol/TCK/ITK certification, other SDK transports, general crash/restart recovery, external side-effect guarantees, live models, benchmarks, publication/deployment. Matching Linux artifacts were downloaded and hashed; this is **availability**, not a Linux test result.

Final worker boundary: **slice_review** for independent whole-repository acceptance. All owned commands exited and HTTP peers stopped. Request main release the M3 named lease. No additional chat/subagent/global install/provider call/publication or main-owned coordination edit occurred.
