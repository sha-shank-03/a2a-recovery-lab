# Project context

## Developer problem

Observe handoff, cancellation and recovery behavior across two peers without treating implementation retry policy as a protocol guarantee.

## Engineering contribution

Separately addressed HTTP agents, task persistence and deduplication policy, event-linked fault scenarios and a separate official-SDK interoperability smoke. The existing tools, overlap and primary sources considered during planning are retained in [PLAN.md](../PLAN.md). The contribution is scoped engineering and inspectable evidence; no adoption, novelty, superiority or production guarantee is implied.

## Why this portfolio exists

This independently usable repository belongs to a ten-project Java/Python portfolio focused on agent harnesses, orchestration, tool contracts, reliability, evaluation and debugging. The author brings Java backend experience and uses Python where a small local tool is sufficient. Implementation used separate AI coding workers and coordinating-agent reviews. Human maintainers remain responsible for reviewing changes.

The accepted MVP is recorded in the README and architecture documents. Future work should preserve its clear entry point, meaningful failure tests, small dependency surface and explicit trust boundaries. A supported integration or live model evaluation requires its own design and evidence.

## Demonstration and support status

34 unit tests and seven HTTP tests; eight core fault scenarios; fresh core 10 checks and installed official SDK 26 checks; four SQLite stores inspected. See [independent verification](INDEPENDENT_VERIFICATION.md) for commands and qualifications. Local acceptance on 2026-10-08 used Windows, CPython 3.11.9 and/or JDK 17 as recorded. Mocks, recorded replay, actual local tools and the optional official SDK are labelled separately. These are authored-fixture results, not a live-model benchmark or third-party certification. GitHub Actions reports hosted execution separately.

Project licensing is [Apache-2.0](../LICENSE); dependencies retain their own licenses and attribution in the repository.

## Related repositories

Each project has its own Git repository, entry point, license, tests and limits. No other portfolio checkout is required to run this project.

- [spring-migration-agent](https://github.com/sha-shank-03/spring-migration-agent) — Java migration harness combining OpenRewrite, bounded mock repair and protected verification for a pinned Spring Boot fixture.
- [durable-agent-jobs](https://github.com/sha-shank-03/durable-agent-jobs) — Java and SQLite runtime for durable mock agent jobs, checkpoints, bounded retries and explicit side-effect recovery contracts.
- [agent-failure-lab](https://github.com/sha-shank-03/agent-failure-lab) — Offline Python CLI for agent trace analysis, recorded replay, failure injection and evidence-linked regression comparisons.
- [mcp-contract-guard](https://github.com/sha-shank-03/mcp-contract-guard) — Python CLI for pinned MCP stdio contract checks, schema drift, malformed responses, timeouts and offline compatibility reports.
- [agent-tool-authority](https://github.com/sha-shank-03/agent-tool-authority) — Python policy gateway for scoped agent tools, explicit operator approval, expiration and transactional SQLite audit.
- [incident-evidence-agent](https://github.com/sha-shank-03/incident-evidence-agent) — Read-only Python incident investigation harness producing evidence-linked observations, hypotheses and explicit uncertainty.
- [agent-budget-scheduler](https://github.com/sha-shank-03/agent-budget-scheduler) — Python scheduler for cooperative agent work with tenant fairness, concurrency limits, deadlines and observed usage ledgers.
- [agent-memory-lifecycle-bench](https://github.com/sha-shank-03/agent-memory-lifecycle-bench) — Offline SQLite-backed evaluation suite for agent memory retention, expiration, deletion, tenant separation and conflicting facts.
- [openclaw-skill-ci](https://github.com/sha-shank-03/openclaw-skill-ci) — Offline CI tooling for pinned OpenClaw skill metadata, prerequisites, team policy and safe synthetic behavior contracts.
