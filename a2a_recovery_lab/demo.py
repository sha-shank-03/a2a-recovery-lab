"""M1 happy path: two actual HTTP endpoints and independently expected output."""

import json
import uuid
from pathlib import Path

from . import EXECUTION_MODE, PROTOCOL_SPEC, PROTOCOL_WIRE, __version__
from .agents import Coordinator, Normalizer
from .evidence import EvidenceLog
from .server import LabServer
from .transport import HttpClient

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "happy-path.json"
SPEC_SOURCE = "https://github.com/a2aproject/A2A/blob/v1.0.1/docs/specification.md"


def run_demo(out, seed=None):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with EvidenceLog(out / "events.jsonl") as evidence:
        normalizer = Normalizer(out / "normalizer.sqlite", evidence)
        with LabServer(normalizer) as peer:
            coordinator = Coordinator(out / "coordinator.sqlite", evidence, peer.origin)
            with LabServer(coordinator) as front:
                client = HttpClient(front.origin, evidence, timeout=8)
                parent_card = client.card()
                child_card = HttpClient(peer.origin, evidence).card()
                # Default blocking: returnImmediately is deliberately absent.
                parent = client.rpc("SendMessage", {"message": {
                    "messageId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"a2a-lab:{seed}:happy-path")) if seed is not None else str(uuid.uuid4()), "role": "ROLE_USER",
                    "parts": [{"data": fixture["input"], "mediaType": "application/json"}]}})["task"]
                retrieved = client.rpc("GetTask", {"id": parent["id"], "historyLength": 0})
                child_id = parent.get("metadata", {}).get("childTaskId")
                child = HttpClient(peer.origin, evidence).rpc("GetTask", {"id": child_id, "historyLength": 0}) if child_id else None
        events = evidence.snapshot()
        checks = []

        def add(check_id, scope, passed, expected, actual, event_types, section=None):
            refs = [event["seq"] for event in events if event["event"] in event_types]
            check = {"id": check_id, "scope": scope, "result": "pass" if passed else "fail",
                     "expected": expected, "actual": actual, "evidence_events": refs}
            if section:
                check["source"] = SPEC_SOURCE + section
            checks.append(check)

        origins = {"coordinator": front.origin, "normalizer": peer.origin}
        receivers = {event["agent"] for event in events if event["event"] == "rpc_received"}
        add("two_http_endpoints", "harness", front.origin != peer.origin and receivers == {"coordinator", "normalizer"},
            "Two different server endpoints receive JSON-RPC", {"origins": origins, "receivers": sorted(receivers)},
            {"server_started", "rpc_received"})
        add("advertised_wire_version", "protocol", all(
            card["supportedInterfaces"][0]["protocolVersion"] == PROTOCOL_WIRE
            for card in (parent_card, child_card)), "1.0", [parent_card["supportedInterfaces"], child_card["supportedInterfaces"]],
            {"card_served"}, "#36-versioning")
        received = [event for event in events if event["event"] == "rpc_received"]
        add("version_headers", "protocol", bool(received) and all(
            event["headers"]["A2A-Version"] == PROTOCOL_WIRE for event in received),
            "Every observed RPC uses A2A-Version 1.0", [event["headers"] for event in received],
            {"rpc_received"}, "#92-service-parameter-transmission")
        add("default_send_blocks", "protocol", parent["status"]["state"] == "TASK_STATE_COMPLETED",
            "Completed task in default blocking SendMessage result", parent["status"]["state"],
            {"rpc_responded", "task_completed"}, "#322-sendmessageconfiguration")
        add("get_task_completed", "protocol", retrieved["status"]["state"] == "TASK_STATE_COMPLETED",
            "TASK_STATE_COMPLETED", retrieved["status"]["state"], {"rpc_responded"}, "#313-get-task")
        add("child_completed", "protocol", child is not None and child["status"]["state"] == "TASK_STATE_COMPLETED",
            "TASK_STATE_COMPLETED", child["status"]["state"] if child else None,
            {"task_completed", "rpc_responded"}, "#411-task")
        data = parent.get("artifacts", [{}])[0].get("parts", [{}])[0].get("data", {})
        child_data = child.get("artifacts", [{}])[0].get("parts", [{}])[0].get("data") if child else None
        add("literal_normalized_artifact", "implementation_policy", data.get("normalizedTicket") == fixture["expected"] and child_data == fixture["expected"],
            fixture["expected"], {"parent": data.get("normalizedTicket"), "child": child_data},
            {"mock_transformation", "rpc_responded"})
        child_artifact_id = child["artifacts"][0]["artifactId"] if child and child.get("artifacts") else None
        linked = child is not None and child_id == data.get("childTaskId") and child_artifact_id == data.get("childArtifactId") and child_artifact_id == parent["metadata"].get("childArtifactId")
        add("parent_child_artifact_link", "implementation_policy", linked,
            "Parent references the observed child task and artifact", {"parent_id": parent["id"], "child_id": child_id, "child_artifact_id": child_artifact_id},
            {"handoff_linked", "rpc_responded"})
        mock_count = sum(event["event"] == "mock_transformation" for event in events)
        add("one_mock_transformation", "implementation_policy", mock_count == 1 and normalizer.store.count() == 1 and coordinator.store.count() == 1,
            {"transformations": 1, "tasks_per_agent": 1}, {"transformations": mock_count, "normalizer_tasks": normalizer.store.count(), "coordinator_tasks": coordinator.store.count()},
            {"mock_transformation", "submission_created"})
        add("clean_teardown", "harness", peer.closed and front.closed, True,
            {"normalizer": peer.closed, "coordinator": front.closed}, {"server_stopped"})
        failed = sum(check["result"] == "fail" for check in checks)
        report = {"report_schema": "1.0", "implementation_version": __version__,
                  "milestone": "M2", "scenario": "happy-path", "seed": seed, "execution_mode": EXECUTION_MODE,
                  "protocol_spec": PROTOCOL_SPEC, "protocol_wire": PROTOCOL_WIRE,
                  "protocol_commit": "3303592588e388e62e0f69f701af531d2f4e3991",
                  "coverage": ["AgentCard", "SendMessage", "GetTask"],
                  "not_checked": ["cancellation in this run", "fault recovery in this run", "ListTasks in this run", "official SDK", "full conformance"],
                  "agents": origins, "tasks": {"parent": parent, "child": child},
                  "checks": checks, "summary": {"passed": len(checks) - failed, "failed": failed},
                  "verdict": "pass" if not failed else "fail", "evidence_file": "events.jsonl"}
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        (out / "agent-cards.json").write_text(json.dumps({"coordinator": parent_card, "normalizer": child_card}, indent=2) + "\n", encoding="utf-8")
        return report


def format_report(report):
    if report.get("oracle") == "installed_official_sdk_jsonrpc_and_protobuf":
        return (f"{report['verdict'].upper()} installed official SDK {report['sdk_version']} | {report['execution_mode']} | "
                f"spec={report['protocol_spec']} wire={report['protocol_wire']}\n"
                f"Checks: {report['summary']['passed']} passed, {report['summary']['failed']} failed\n"
                "Scope: installed SDK JSONRPC/protobuf interactions; full conformance not checked.")
    if "scenarios" in report:
        lines = [f"{report['verdict'].upper()} core expected outcomes | {report['execution_mode']} | spec={report['protocol_spec']} wire={report['protocol_wire']}"]
        lines.extend(f"{scenario['name']}: expected outcome {scenario['verdict'].upper()}, retained failed checks={scenario['summary']['failed']}"
                     for scenario in report["scenarios"])
        lines.append(f"Safety-policy failures remain visible: {report['summary']['retained_safety_failures']}")
        return "\n".join(lines)
    summary = report["summary"]
    lines = [f"{report['verdict'].upper()} {report['scenario']} | {report['execution_mode']} | spec={report['protocol_spec']} wire={report['protocol_wire']}",
             f"Checks: {summary['passed']} passed, {summary['failed']} failed",
             "HTTP peers: " + ", ".join(f"{name}={url}" for name, url in report["agents"].items())]
    for name, task in report["tasks"].items():
        if task:
            lines.append(f"Task {name}: {task['id']} {task['status']['state']}")
    if summary.get("expected_negative_failures"):
        lines.append(f"Expected negative-control failures retained: {summary['expected_negative_failures']} (safety policy FAIL)")
    if summary.get("inconclusive"):
        lines.append(f"Inconclusive outcomes retained: {summary['inconclusive']}")
    lines.append(f"Scope: {report.get('milestone', 'M1')} scoped task operations; mock computation; full conformance not checked.")
    return "\n".join(lines)
