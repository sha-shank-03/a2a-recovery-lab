# Repository guidance

Work within this standalone repository and preserve other contributors' changes. Read README.md, PLAN.md, docs/PROJECT_CONTEXT.md, the architecture/contracts documents and docs/INDEPENDENT_VERIFICATION.md before changing behavior.

The agreed MVP is implemented and locally verified. Preserve its narrow scope, pinned dependencies/protocols, meaningful failure tests, licenses, fixtures and evidence. Prefer Java/Python choices already established here; avoid services/frameworks without a concrete need.

Keep acceptance tests and authorization policy outside model control. Label deterministic mocks and recorded replay accurately. Record actual commands, exit codes, assertions and unexecuted checks; never invent adoption, guarantees or live-model results.

Do not commit generated workspaces, caches, virtual environments, secrets or production data. Use a new demo output directory and bound expensive builds/processes. There is no dependency on the original private worker-chat coordination files.

The initial publication is human-authorized. Future pushes, releases, deployments, purchases, real-account mutations and paid calls require authorization appropriate to that task. Run the documented checks needed for the change; keep CI free of paid model calls.
