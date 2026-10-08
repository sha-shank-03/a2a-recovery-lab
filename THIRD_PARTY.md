# Third-party attribution and version baseline

Core source/tests use only Python's standard library. The optional SDK verifier is installed in a separate ignored repository-local environment with the complete 32-package runtime closure below. Repository code is Apache-2.0; upstream license/notice texts retain their individual licenses. No SDK source is vendored.

| Reference/runtime | Pin and attribution |
| --- | --- |
| Agent2Agent specification and proto | [a2aproject/A2A v1.0.1](https://github.com/a2aproject/A2A/tree/v1.0.1), commit `3303592588e388e62e0f69f701af531d2f4e3991`, [Apache-2.0 license](https://github.com/a2aproject/A2A/blob/v1.0.1/LICENSE). Field/method/state names and protocol semantics follow this reference. No SDK code is vendored. |
| CPython | Local verification used 3.11.9, under the [Python software license](https://docs.python.org/3.11/license.html). Standard-library modules are shipped by the interpreter. |
| Bundled SQLite | Actual local `sqlite3.sqlite_version` was 3.45.1; SQLite is [public domain](https://www.sqlite.org/copyright.html). No separate database package/service is used. |
| JSON-RPC 2.0 | [Official specification](https://www.jsonrpc.org/specification); request/response contract reference, no code copied. |
| ProtoJSON | [Official protobuf documentation](https://protobuf.dev/programming-guides/json/); data-format reference, no generated protobuf runtime required by the core. |

Installed optional verification: `a2a-sdk==1.1.5` (Apache-2.0), `httpx==0.28.1` (BSD-3-Clause), exact/hash-pinned in requirements-sdk-check.txt with their full transitive graph. On 2026-10-08, actual Windows AMD64 / Linux x86_64 Python 3.11.9 wheels were downloaded, hashes checked and license texts retained before installation. Windows installation and 26 real SDK interactions passed. Linux wheel availability/dependency-marker checks are evidence of artifacts, not executed Linux validation.

Official TCK, ITK, and Inspector were researched for overlap; none is vendored, installed, or run. Ignored `work/` holds scratch research, wheels and the optional environment. Prepared CI pins actions/checkout v5.0.0 (`08c6903cd8c0fde910a37f88322edcfb5dd907a8`) and actions/setup-python v6.0.0 (`e797f83bcb11b83ae66e0230d6156d7c80228e7c`), both MIT-licensed action projects. Official Git tag references were rechecked on 2026-10-08; evidence/m3-dependencies/ci-actions.json records them. Hosted CI is unexecuted.

## Complete optional Python runtime closure

All exact package versions below were installed and `pip check` passed. For each version, [artifact metadata](evidence/m3-dependencies/artifacts.json) retains requirements, licenses, wheel names/URLs/sizes and hashes; [download/license receipts](evidence/m3-dependencies/download-licenses.json) map retained files to their sources. [Installed/runtime size receipts](evidence/m3-dependencies/installed.json) distinguish actual Windows execution from Linux availability. [requirements-sdk-check.txt](requirements-sdk-check.txt) permits only the audited platform wheel hashes.

| Package | Exact version | Declared/retained license | Retained texts |
| --- | --- | --- | --- |
| [a2a-sdk](https://pypi.org/project/a2a-sdk/1.1.5/) | 1.1.5 | Apache-2.0 | [Files](third_party/sdk-licenses/a2a-sdk-1.1.5/) |
| [aiologic](https://pypi.org/project/aiologic/0.17.1/) | 0.17.1 | ISC (runtime) | [Files](third_party/sdk-licenses/aiologic-0.17.1/) |
| [annotated-types](https://pypi.org/project/annotated-types/0.8.0/) | 0.8.0 | MIT | [Files](third_party/sdk-licenses/annotated-types-0.8.0/) |
| [anyio](https://pypi.org/project/anyio/4.15.1/) | 4.15.1 | MIT | [Files](third_party/sdk-licenses/anyio-4.15.1/) |
| [certifi](https://pypi.org/project/certifi/2026.7.22/) | 2026.7.22 | MPL-2.0 | [Files](third_party/sdk-licenses/certifi-2026.7.22/) |
| [cffi](https://pypi.org/project/cffi/2.1.1/) | 2.1.1 | MIT-0 | [Files](third_party/sdk-licenses/cffi-2.1.1/) |
| [charset-normalizer](https://pypi.org/project/charset-normalizer/3.5.2/) | 3.5.2 | MIT | [Files](third_party/sdk-licenses/charset-normalizer-3.5.2/) |
| [cryptography](https://pypi.org/project/cryptography/50.0.2/) | 50.0.2 | Apache-2.0 OR BSD-3-Clause | [Files](third_party/sdk-licenses/cryptography-50.0.2/) |
| [culsans](https://pypi.org/project/culsans/0.11.0/) | 0.11.0 | ISC (runtime) | [Files](third_party/sdk-licenses/culsans-0.11.0/) |
| [google-api-core](https://pypi.org/project/google-api-core/2.41.0/) | 2.41.0 | Apache-2.0 | [Files](third_party/sdk-licenses/google-api-core-2.41.0/) |
| [google-auth](https://pypi.org/project/google-auth/2.61.0/) | 2.61.0 | Apache-2.0 | [Files](third_party/sdk-licenses/google-auth-2.61.0/) |
| [googleapis-common-protos](https://pypi.org/project/googleapis-common-protos/1.75.5/) | 1.75.5 | Apache-2.0 | [Files](third_party/sdk-licenses/googleapis-common-protos-1.75.5/) |
| [h11](https://pypi.org/project/h11/0.16.0/) | 0.16.0 | MIT | [Files](third_party/sdk-licenses/h11-0.16.0/) |
| [httpcore](https://pypi.org/project/httpcore/1.0.9/) | 1.0.9 | BSD-3-Clause | [Files](third_party/sdk-licenses/httpcore-1.0.9/) |
| [httpx](https://pypi.org/project/httpx/0.28.1/) | 0.28.1 | BSD-3-Clause | [Files](third_party/sdk-licenses/httpx-0.28.1/) |
| [idna](https://pypi.org/project/idna/3.20/) | 3.20 | BSD-3-Clause | [Files](third_party/sdk-licenses/idna-3.20/) |
| [json-rpc](https://pypi.org/project/json-rpc/1.15.0/) | 1.15.0 | MIT | [Files](third_party/sdk-licenses/json-rpc-1.15.0/) |
| [opentelemetry-api](https://pypi.org/project/opentelemetry-api/1.45.1/) | 1.45.1 | Apache-2.0 | [Files](third_party/sdk-licenses/opentelemetry-api-1.45.1/) |
| [packaging](https://pypi.org/project/packaging/26.3/) | 26.3 | Apache-2.0 OR BSD-2-Clause | [Files](third_party/sdk-licenses/packaging-26.3/) |
| [proto-plus](https://pypi.org/project/proto-plus/1.29.0/) | 1.29.0 | Apache-2.0 | [Files](third_party/sdk-licenses/proto-plus-1.29.0/) |
| [protobuf](https://pypi.org/project/protobuf/7.36.2/) | 7.36.2 | BSD-3-Clause | [Files](third_party/sdk-licenses/protobuf-7.36.2/) |
| [pyasn1](https://pypi.org/project/pyasn1/0.6.4/) | 0.6.4 | BSD-2-Clause | [Files](third_party/sdk-licenses/pyasn1-0.6.4/) |
| [pyasn1-modules](https://pypi.org/project/pyasn1-modules/0.4.2/) | 0.4.2 | BSD-2-Clause | [Files](third_party/sdk-licenses/pyasn1-modules-0.4.2/) |
| [pycparser](https://pypi.org/project/pycparser/3.0/) | 3.0 | BSD-3-Clause | [Files](third_party/sdk-licenses/pycparser-3.0/) |
| [pydantic](https://pypi.org/project/pydantic/2.13.5/) | 2.13.5 | MIT | [Files](third_party/sdk-licenses/pydantic-2.13.5/) |
| [pydantic-core](https://pypi.org/project/pydantic-core/2.46.5/) | 2.46.5 | MIT | [Files](third_party/sdk-licenses/pydantic-core-2.46.5/) |
| [requests](https://pypi.org/project/requests/2.34.2/) | 2.34.2 | Apache-2.0 | [Files](third_party/sdk-licenses/requests-2.34.2/) |
| [sniffio](https://pypi.org/project/sniffio/1.3.1/) | 1.3.1 | MIT OR Apache-2.0 | [Files](third_party/sdk-licenses/sniffio-1.3.1/) |
| [typing-extensions](https://pypi.org/project/typing-extensions/4.16.0/) | 4.16.0 | PSF-2.0 | [Files](third_party/sdk-licenses/typing-extensions-4.16.0/) |
| [typing-inspection](https://pypi.org/project/typing-inspection/0.4.4/) | 0.4.4 | MIT | [Files](third_party/sdk-licenses/typing-inspection-0.4.4/) |
| [urllib3](https://pypi.org/project/urllib3/2.8.0/) | 2.8.0 | MIT | [Files](third_party/sdk-licenses/urllib3-2.8.0/) |
| [wrapt](https://pypi.org/project/wrapt/2.5.0/) | 2.5.0 | BSD-2-Clause | [Files](third_party/sdk-licenses/wrapt-2.5.0/) |

The base SDK graph mandates Google API/Auth, cryptography and OpenTelemetry API dependencies. No server, telemetry SDK/exporter, SQL or gRPC extras were requested. The verifier disables SDK tracing and sends traffic only to its owned loopback peers. The table describes package licenses, not a blanket license for native subcomponents; unmodified notices supplied in the selected wheel are retained.

aiologic/culsans wheels omit separate license files. Matching release tags resolve to commits `a3051c56f0b8a420780bbca17dcff5ac926eff88` and `56e826068fa91e5ad868e8d5108495201745c587`. ISC runtime, 0BSD tests, CC-BY-4.0 documentation and CC0-1.0 configuration license texts were fetched from each pinned source tree. Actual SPDX author/license lines from the wheels are retained as SOURCE-NOTICES.txt, attributing Ilya Egorov. These are unmodified source notices/texts; no runtime source is copied into the core.

CPython's venv bootstrap also contains pip 24.0 and setuptools 65.5.0 (MIT licenses). They are interpreter-provided bootstrap tooling, outside the SDK runtime requirement graph; no bootstrap upgrade was performed. Windows core uses CPython 3.11.9 and its bundled SQLite 3.45.1. Their licenses are linked above. This attribution and the wheel receipts cover the resolved Python closure and retained upstream notices; they are not a legal or supply-chain security certification.
