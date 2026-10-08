"""Optional installed official-SDK oracle; core imports never depend on this file."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import inspect
import json
import os
import platform
import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INPUT = {"ticket_id": "INC-0042", "title": "  Checkout   returns  502  ", "priority": " HIGH "}
EXPECTED = {"ticket_id": "INC-0042", "title": "Checkout returns 502", "priority": "high",
            "input_sha256": "d37e90ba1e3f588afb51f9eb954856269c6eb06deb9e8247e2fd8dfce98ed027"}


def run(out):
    # SDK decorators are disabled before importing the installed SDK. No exporter/provider is configured.
    os.environ["OTEL_INSTRUMENTATION_A2A_SDK_ENABLED"] = "false"
    import httpx
    from google.protobuf import json_format
    from a2a.client.card_resolver import A2ACardResolver
    from a2a.client.client import ClientCallContext
    from a2a.client.transports.jsonrpc import JsonRpcTransport
    from a2a.types import a2a_pb2 as pb
    from a2a.utils.errors import InvalidParamsError, TaskNotCancelableError, TaskNotFoundError, VersionNotSupportedError
    from a2a_recovery_lab import EXECUTION_MODE, PROTOCOL_SPEC, PROTOCOL_WIRE
    from a2a_recovery_lab.agents import Coordinator
    from a2a_recovery_lab.evidence import EvidenceLog
    from a2a_recovery_lab.faults import GatedNormalizer
    from a2a_recovery_lab.server import LabServer

    lock_rows = [line.split()[0].split("==") for line in (ROOT / "requirements-sdk-check.txt").read_text(encoding="utf-8").splitlines()
                 if line and not line.startswith("#")]
    installed = {name: importlib.metadata.version(name) for name, _ in lock_rows}
    assert all(installed[name] == version for name, version in lock_rows), "Installed graph differs from exact SDK lock"
    assert installed["a2a-sdk"] == "1.1.5" and installed["httpx"] == "0.28.1"
    source_paths = {"card_resolver": Path(inspect.getfile(A2ACardResolver)),
                    "jsonrpc_transport": Path(inspect.getfile(JsonRpcTransport)),
                    "protobuf_types": Path(pb.__file__)}
    sources = {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
               for name, path in source_paths.items()}
    out.mkdir(parents=True, exist_ok=False)
    checks = []
    origins = {}
    tasks = {}
    with EvidenceLog(out / "events.jsonl") as evidence:
        evidence.emit("sdk_oracle", "official_sdk", "sdk_runtime", versions=installed,
                      python=platform.python_version(), source_hashes=sources)
        def check(check_id, passed, expected, actual, kinds=("sdk_http_response", "rpc_responded")):
            checks.append({"id": check_id, "scope": "sdk_interoperability", "result": "pass" if passed else "fail",
                           "expected": expected, "actual": actual, "_kinds": kinds})
            if not passed:
                raise AssertionError(f"SDK check failed: {check_id}: {actual!r}")

        normalizer = GatedNormalizer(out / "normalizer.sqlite", evidence)
        with LabServer(normalizer) as peer:
            coordinator = Coordinator(out / "coordinator.sqlite", evidence, peer.origin)
            with LabServer(coordinator) as front:
                origins = {"coordinator": front.origin, "normalizer": peer.origin}
                allowed = set(origins.values())
                async def on_request(request):
                    parsed = urlsplit(str(request.url))
                    if f"{parsed.scheme}://{parsed.netloc}" not in allowed:
                        raise ValueError("SDK oracle only permits its two owned loopback origins")
                    payload = json.loads(request.content) if request.content else None
                    evidence.emit("sdk_wire", "official_sdk", "sdk_http_request", url=str(request.url),
                                  http_method=request.method, headers={"A2A-Version": request.headers.get("A2A-Version"),
                                  "Content-Type": request.headers.get("Content-Type")}, payload=payload)
                async def on_response(response):
                    await response.aread()
                    evidence.emit("sdk_wire", "official_sdk", "sdk_http_response", url=str(response.request.url),
                                  http_status=response.status_code, payload=response.json())

                async def exercise():
                    async with httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False,
                            headers={"A2A-Version": "1.0"}, event_hooks={"request": [on_request], "response": [on_response]}) as client:
                        cards = {name: await A2ACardResolver(client, origin).get_agent_card() for name, origin in origins.items()}
                        check("official_card_type", all(isinstance(card, pb.AgentCard) for card in cards.values()),
                              "Official protobuf AgentCard at both peers", {name: type(card).__module__ for name, card in cards.items()})
                        for name, card in cards.items():
                            interface = card.supported_interfaces[0]
                            check("card_interface_" + name,
                                  interface.url == origins[name] + "/rpc" and interface.protocol_version == "1.0" and interface.protocol_binding == "JSONRPC",
                                  "Owned JSONRPC 1.0 interface", json_format.MessageToDict(interface))
                        transports = {name: JsonRpcTransport(client, card, origins[name] + "/rpc") for name, card in cards.items()}
                        sdk = transports["coordinator"]
                        peer_sdk = transports["normalizer"]
                        def send_request(message_id, immediate=None):
                            value = {"message": {"messageId": message_id, "role": "ROLE_USER",
                                     "parts": [{"data": INPUT, "mediaType": "application/json"}]}}
                            if immediate is not None:
                                value["configuration"] = {"returnImmediately": immediate}
                            return json_format.ParseDict(value, pb.SendMessageRequest())

                        request = send_request("sdk-blocking-message")
                        encoded = json_format.MessageToDict(request)
                        check("official_message_parse", isinstance(request.message, pb.Message) and request.message.role == pb.ROLE_USER,
                              "Official protobuf Message / ROLE_USER", encoded["message"], ("sdk_runtime",))
                        check("blocking_configuration_omitted", "configuration" not in encoded,
                              "Default blocking configuration omitted", encoded, ("sdk_runtime",))
                        pending = asyncio.create_task(sdk.send_message(request))
                        try:
                            reached = await asyncio.to_thread(normalizer.started.wait, 1)
                            check("sdk_blocking_waits_at_gate", reached and not pending.done(),
                                  "Send response waits while mock completion gate is held", {"gate_reached": reached, "send_done": pending.done()},
                                  ("sdk_http_request", "completion_gate_held"))
                        finally:
                            normalizer.release.set()
                        response = await asyncio.wait_for(pending, 8)
                        check("official_send_response_type", isinstance(response, pb.SendMessageResponse) and response.HasField("task"),
                              "Official SendMessageResponse containing Task", type(response).__module__)
                        parent = response.task
                        tasks["completed_parent"] = json_format.MessageToDict(parent)
                        check("blocking_completed", parent.status.state == pb.TASK_STATE_COMPLETED,
                              "TASK_STATE_COMPLETED", pb.TaskState.Name(parent.status.state))
                        normalized = json_format.MessageToDict(parent.artifacts[0])["parts"][0]["data"]["normalizedTicket"]
                        check("independent_literal_and_hash", normalized == EXPECTED, EXPECTED, normalized)
                        fetched = await sdk.get_task(pb.GetTaskRequest(id=parent.id, history_length=0))
                        check("official_get_task_history_zero", isinstance(fetched, pb.Task) and fetched.id == parent.id and not fetched.history,
                              "Same typed task with no history", json_format.MessageToDict(fetched))
                        child_id = str(parent.metadata["childTaskId"])
                        child = await peer_sdk.get_task(pb.GetTaskRequest(id=child_id))
                        check("official_peer_get_and_link", child.id == child_id and child.status.state == pb.TASK_STATE_COMPLETED and
                              child.context_id == parent.context_id and len(child.history) == 1 and isinstance(child.history[0], pb.Message),
                              "Actual linked completed child; SDK parses history Message", json_format.MessageToDict(child))
                        duplicate = await sdk.send_message(request)
                        check("sdk_duplicate_same_task", duplicate.task.id == parent.id,
                              parent.id, duplicate.task.id)

                        async def expected_error(check_id, call, error_type):
                            try:
                                await call
                            except error_type as exc:
                                evidence.emit("sdk_oracle", "official_sdk", "sdk_error_observed", check_id=check_id, error_type=type(exc).__name__)
                                check(check_id, True, error_type.__name__, type(exc).__name__, ("sdk_error_observed", "rpc_responded"))
                            else:
                                check(check_id, False, error_type.__name__, "No error")
                        await expected_error("sdk_unknown_task_error", sdk.get_task(pb.GetTaskRequest(id="sdk-no-such-task")), TaskNotFoundError)
                        await expected_error("sdk_completed_not_cancelable", sdk.cancel_task(pb.CancelTaskRequest(id=parent.id)), TaskNotCancelableError)
                        await expected_error("sdk_invalid_history_error", sdk.get_task(pb.GetTaskRequest(id=parent.id, history_length=-1)), InvalidParamsError)
                        context = ClientCallContext(service_parameters={"A2A-Version": "2.0"})
                        await expected_error("sdk_unsupported_version_error", sdk.get_task(pb.GetTaskRequest(id=parent.id), context=context), VersionNotSupportedError)
                        saved_header = client.headers.pop("A2A-Version")
                        try:
                            await expected_error("sdk_missing_version_error", sdk.get_task(pb.GetTaskRequest(id=parent.id)), VersionNotSupportedError)
                        finally:
                            client.headers["A2A-Version"] = saved_header
                        patched = await sdk.get_task(pb.GetTaskRequest(id=parent.id),
                            context=ClientCallContext(service_parameters={"A2A-Version": "1.0.99"}))
                        check("sdk_major_minor_version", patched.id == parent.id, parent.id, patched.id)

                        normalizer.started.clear()
                        normalizer.release.clear()
                        try:
                            immediate = await sdk.send_message(send_request("sdk-cancel-message", True))
                            reached = await asyncio.to_thread(normalizer.started.wait, 1)
                            check("sdk_immediate_returns_in_progress", reached and immediate.task.status.state in (pb.TASK_STATE_SUBMITTED, pb.TASK_STATE_WORKING),
                                  "Nonterminal parent while mock gate held", pb.TaskState.Name(immediate.task.status.state))
                            await asyncio.to_thread(evidence.wait_for, lambda event: event["event"] == "handoff_linked" and event["parent_task_id"] == immediate.task.id)
                            canceled = await sdk.cancel_task(pb.CancelTaskRequest(id=immediate.task.id))
                            check("sdk_local_cancel_type_and_state", isinstance(canceled, pb.Task) and canceled.status.state == pb.TASK_STATE_CANCELED,
                                  "Typed local canceled Task", json_format.MessageToDict(canceled))
                            await asyncio.to_thread(evidence.wait_for, lambda event: event["event"] == "remote_cancel_acknowledged" and event["parent_task_id"] == immediate.task.id)
                            final = await sdk.get_task(pb.GetTaskRequest(id=immediate.task.id))
                            child_id = str(final.metadata["childTaskId"])
                            canceled_child = await peer_sdk.get_task(pb.GetTaskRequest(id=child_id))
                            check("sdk_remote_cancel_separate_ack", final.metadata["remoteCancellation"]["status"] == "acknowledged" and
                                  canceled_child.status.state == pb.TASK_STATE_CANCELED,
                                  "Observed child canceled; separate acknowledged metadata", json_format.MessageToDict(final))
                            repeated = await sdk.cancel_task(pb.CancelTaskRequest(id=final.id))
                            check("sdk_cancel_idempotent_effect", repeated.id == final.id and repeated.status.state == pb.TASK_STATE_CANCELED,
                                  "Same canceled task", json_format.MessageToDict(repeated))
                            tasks["canceled_parent"] = json_format.MessageToDict(final)
                            tasks["canceled_child"] = json_format.MessageToDict(canceled_child)
                        finally:
                            normalizer.release.set()
                        await asyncio.to_thread(evidence.wait_for, lambda event: event["event"] == "terminal_update_discarded" and event["agent"] == "normalizer")
                        final = await sdk.get_task(pb.GetTaskRequest(id=final.id))
                        check("sdk_late_artifact_preserves_terminal", final.status.state == pb.TASK_STATE_CANCELED and not final.artifacts,
                              "Canceled parent without artifacts after late mock completion", json_format.MessageToDict(final))
                        invalid = json.loads((ROOT / "fixtures/invalid-task-response.json").read_text(encoding="utf-8"))
                        try:
                            json_format.ParseDict(invalid["result"], pb.SendMessageResponse())
                        except json_format.ParseError:
                            evidence.emit("sdk_oracle", "official_sdk", "sdk_invalid_fixture_rejected")
                            check("sdk_invalid_enum_fixture", True, "Official protobuf parser rejects lowercase task enum", "ParseError", ("sdk_invalid_fixture_rejected",))
                        else:
                            check("sdk_invalid_enum_fixture", False, "ParseError", "Accepted invalid enum")
                        (out / "agent-cards.json").write_text(json.dumps({name: json_format.MessageToDict(card) for name, card in cards.items()}, indent=2) + "\n", encoding="utf-8")
                asyncio.run(asyncio.wait_for(exercise(), 30))
        check("clean_sdk_peer_teardown", front.closed and peer.closed, True,
              {"coordinator": front.closed, "normalizer": peer.closed}, ("server_stopped",))
        closed = []
        for origin in origins.values():
            url = urlsplit(origin)
            with socket.socket() as probe:
                probe.settimeout(0.2)
                refused = probe.connect_ex((url.hostname, url.port)) != 0
            closed.append(refused)
        evidence.emit("sdk_oracle", "official_sdk", "sdk_closed_port_probes", origins=origins, connection_refused=closed)
        check("sdk_owned_ports_closed", all(closed), [True, True], closed, ("sdk_closed_port_probes",))
        events = evidence.snapshot()
        for check_row in checks:
            kinds = check_row.pop("_kinds")
            check_row["evidence_events"] = [event["seq"] for event in events if event["event"] in kinds]
            assert check_row["evidence_events"]
        report = {"report_schema": "sdk-smoke-1.0", "milestone": "M3", "execution_mode": EXECUTION_MODE,
                  "oracle": "installed_official_sdk_jsonrpc_and_protobuf", "sdk_version": installed["a2a-sdk"],
                  "httpx_version": installed["httpx"], "protocol_spec": PROTOCOL_SPEC, "protocol_wire": PROTOCOL_WIRE,
                  "runtime": {"python": platform.python_version(), "platform": platform.platform(), "executable": sys.executable},
                  "installed_runtime_closure": installed, "sdk_sources": sources, "agents": origins, "tasks": tasks,
                  "checks": checks, "summary": {"passed": len(checks), "failed": 0}, "verdict": "pass",
                  "not_checked": (["Linux execution"] if sys.platform != "linux" else ["Windows execution in this run"]) +
                  ([] if os.environ.get("GITHUB_ACTIONS") == "true" else ["hosted CI"]) +
                  ["full conformance", "SDK transports other than JSONRPC", "live models"],
                  "evidence_file": "events.jsonl"}
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report


def main():
    parser = argparse.ArgumentParser(description="Optional a2a-sdk 1.1.5 installed JSON-RPC/protobuf oracle")
    parser.add_argument("--out", type=Path, required=True, help="New evidence directory; existing output is preserved")
    args = parser.parse_args()
    try:
        report = run(args.out.resolve())
    except (ImportError, importlib.metadata.PackageNotFoundError):
        parser.exit(2, "SDK environment missing. Create a separate Python 3.11 venv and install requirements-sdk-check.txt with --require-hashes --only-binary=:all:. Core does not require it.\n")
    except (AssertionError, OSError, ValueError, RuntimeError, TimeoutError) as exc:
        parser.exit(1, f"Official SDK check failed: {exc}\n")
    print(f"PASS installed official SDK {report['sdk_version']} | {report['summary']['passed']} checks | {report['execution_mode']}")
    print(f"Report: {(args.out / 'report.json').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
