# Contributing

Start with the [README](README.md), [project context](docs/PROJECT_CONTEXT.md), accepted [plan](PLAN.md), architecture documents, dependency attribution and [verification evidence](docs/INDEPENDENT_VERIFICATION.md).

## Reproduce before changing behavior

Use the documented interpreter/JDK and dependency setup. Run from the repository root with a new output directory. Windows examples after setup:

```powershell
py -3.11 -m unittest discover -s tests/unit -v
py -3.11 -m a2a_recovery_lab demo --suite core --seed 7 --out work/contribution-core
```

The README gives corresponding POSIX commands and explains which platform paths have actually been exercised. Java offline commands require a warmed Maven cache; Python virtual-environment commands require the documented hash-locked dependencies. A2A integration tests are separate from its unit suite and its SDK environment is optional. Expected failure exits in demonstrations are assertions, not permission to suppress failures.

## Propose a bounded change

Open an issue describing the user problem, a concrete example, expected behavior and scope. For a pull request, explain the resulting behavior, add a meaningful regression test when behavior changes, and include actual commands/results and unexecuted checks. Use a branch; preserve other contributors' work and existing evidence.

Keep authorization and acceptance oracles outside model-controlled code. Preserve fictional fixtures, pinned contracts, attribution and mock/replay labels. Never add credentials, personal/production data or provider calls to ordinary tests. Record live evaluations separately, with explicit setup, authorization and cost. Avoid unsupported exactly-once, security, isolation or benchmark claims.

Changes must remain under the project license, with licenses/notices for any new dependencies or borrowed assets. Documentation fixes need link/diff checks; repeat runtime checks when executable behavior or dependencies change.
