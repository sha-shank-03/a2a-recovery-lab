"""Exactly eight public M2 scenarios, each over two owned HTTP agents."""

import json
import uuid
from dataclasses import asdict
from pathlib import Path

from . import EXECUTION_MODE, PROTOCOL_SPEC, PROTOCOL_WIRE, __version__
from .agents import Coordinator, Normalizer
from .demo import FIXTURE, SPEC_SOURCE, run_demo
from .evidence import EvidenceLog
from .faults import FaultController, GatedNormalizer
from .policy import RecoveryPolicy
from .server import LabServer
from .transport import HttpClient

CORE_SCENARIOS = ("happy-path", "duplicate-request", "lost-ack", "delayed-after-cancel",
                  "peer-unavailable-recovers", "cancel-unavailable-recovers", "recovery-exhausted",
                  "unsafe-retry-baseline")


def run_scenario(name, out, seed=7, *, _ambiguous=False, _invalid_response=False):
    if name not in CORE_SCENARIOS and not (_ambiguous or _invalid_response):
        raise ValueError("Unknown scenario")
    if name == "happy-path" and not (_ambiguous or _invalid_response):
        return run_demo(out, seed=seed)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    canceled_case = name in {"delayed-after-cancel", "cancel-unavailable-recovers"}
    gated = canceled_case or name == "peer-unavailable-recovers"
    policy = RecoveryPolicy(max_attempts=3 if name == "recovery-exhausted" else 12,
                            peer_deduplication_assumed=name == "lost-ack",
                            unsafe_retry=name == "unsafe-retry-baseline")
    pending_snapshot = None
    with EvidenceLog(out / "events.jsonl") as evidence:
        peer_type = GatedNormalizer if gated else Normalizer
        normalizer = peer_type(out / "normalizer.sqlite", evidence,
                               deduplicate=name != "unsafe-retry-baseline")
        faults = FaultController(evidence,
            drop_first_ack=name in {"lost-ack", "unsafe-retry-baseline"} or _ambiguous,
            delay_first_get=name == "delayed-after-cancel",
            unavailable_method="CancelTask" if name == "cancel-unavailable-recovers" else (
                "GetTask" if name in {"peer-unavailable-recovers", "recovery-exhausted"} else None),
            unavailable_count=100 if name == "recovery-exhausted" else (2 if name in {
                "peer-unavailable-recovers", "cancel-unavailable-recovers"} else 0),
            pause_first_unavailable=name == "cancel-unavailable-recovers",
            corrupt_first_ack=_invalid_response,
            on_recovered=normalizer.release.set if name == "peer-unavailable-recovers" else lambda: None)
        with LabServer(normalizer, faults=faults) as peer:
            coordinator = Coordinator(out / "coordinator.sqlite", evidence, peer.origin, policy=policy)
            with LabServer(coordinator) as front:
                client = HttpClient(front.origin, evidence, timeout=8)
                peer_client = HttpClient(peer.origin, evidence, timeout=2)
                cards = {"coordinator": client.card(), "normalizer": peer_client.card()}
                params = {"message": {"messageId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"a2a-lab:{seed}:{name}")),
                                      "role": "ROLE_USER", "parts": [{"data": fixture["input"], "mediaType": "application/json"}]}}
                if canceled_case:
                    params["configuration"] = {"returnImmediately": True}
                try:
                    parent = client.rpc("SendMessage", params)["task"]
                    if canceled_case:
                        evidence.wait_for(lambda event: event["event"] == "handoff_linked" and event["parent_task_id"] == parent["id"])
                        if not normalizer.started.wait(1):
                            raise TimeoutError("Mock completion was not gated before cancellation")
                        if name == "delayed-after-cancel" and not faults.held.wait(1):
                            raise TimeoutError("Delayed GetTask was not gated")
                        parent = client.rpc("CancelTask", {"id": parent["id"]})
                        if name == "cancel-unavailable-recovers":
                            if not faults.held.wait(1):
                                raise TimeoutError("Child cancellation was not gated")
                            pending_snapshot = client.rpc("GetTask", {"id": parent["id"]})
                            faults.release.set()
                        evidence.wait_for(lambda event: event["event"] == "remote_cancel_acknowledged" and event["parent_task_id"] == parent["id"])
                        normalizer.release.set()
                        faults.release.set()
                        evidence.wait_for(lambda event: event["event"] == "terminal_update_discarded" and event["agent"] == "normalizer")
                        if name == "delayed-after-cancel":
                            evidence.wait_for(lambda event: event["event"] == "late_response_discarded" and event["parent_task_id"] == parent["id"])
                    elif name == "duplicate-request":
                        duplicate = client.rpc("SendMessage", params)["task"]
                        if duplicate["id"] != parent["id"]:
                            raise AssertionError("Duplicate parent submission created another task")
                        original = evidence.wait_for(lambda event: event["event"] == "rpc_received" and event["agent"] == "normalizer" and event["payload"]["method"] == "SendMessage")
                        peer_client.rpc("SendMessage", original["payload"]["params"])
                    parent = client.rpc("GetTask", {"id": parent["id"], "historyLength": 0})
                    peer_page = peer_client.rpc("ListTasks", {"contextId": parent["contextId"], "includeArtifacts": True, "historyLength": 0})
                    peer_tasks = peer_page["tasks"]
                finally:
                    faults.close()
                    if gated:
                        normalizer.release.set()
        events = evidence.snapshot()
        child_id = parent.get("metadata", {}).get("childTaskId")
        child = next((task for task in peer_tasks if task["id"] == child_id), None)
        expected_state = "TASK_STATE_CANCELED" if canceled_case else (
            "TASK_STATE_FAILED" if name == "recovery-exhausted" or _ambiguous or _invalid_response else "TASK_STATE_COMPLETED")
        checks = []
        def add(check_id, scope, passed, expected, actual, kinds, *, negative=False, result=None, section=None):
            check = {"id": check_id, "scope": scope, "result": result or ("pass" if passed else "fail"),
                     "expected": expected, "actual": actual,
                     "evidence_events": [event["seq"] for event in events if event["event"] in kinds]}
            if negative:
                check["expected_negative_control"] = True
            if section:
                check["source"] = SPEC_SOURCE + section
            checks.append(check)
        receivers = {event["agent"] for event in events if event["event"] == "rpc_received"}
        add("two_http_endpoints", "harness", front.origin != peer.origin and receivers == {"coordinator", "normalizer"},
            "Different origins; both receive RPC", {"coordinator": front.origin, "normalizer": peer.origin,
                                                       "rpc_receivers": sorted(receivers)}, {"server_started", "rpc_received"})
        add("clean_teardown", "harness", front.closed and peer.closed, True,
            {"coordinator": front.closed, "normalizer": peer.closed}, {"server_stopped"})
        received = [event for event in events if event["event"] == "rpc_received"]
        add("version_headers", "protocol", bool(received) and all(event["headers"]["A2A-Version"] == PROTOCOL_WIRE for event in received),
            "1.0", [event["headers"]["A2A-Version"] for event in received], {"rpc_received"}, section="#36-versioning")
        add("expected_parent_state", "implementation_policy", parent["status"]["state"] == expected_state,
            expected_state, parent["status"]["state"], {"task_completed", "task_canceled", "task_failed", "rpc_responded"})
        expected_count = 2 if name == "unsafe-retry-baseline" else 1
        add("observed_peer_task_count", "harness", len(peer_tasks) == expected_count,
            expected_count, len(peer_tasks), {"submission_created", "rpc_responded"})
        attempts = {key: value for key, value in parent["metadata"].items() if key.endswith("Attempts")}
        add("attempt_bounds", "implementation_policy", bool(attempts) and all(value <= policy.max_attempts for value in attempts.values()),
            f"Each operation <= {policy.max_attempts}", attempts, {"recovery_attempt", "exchange_failed"})
        add("no_duplicate_peer_tasks", "implementation_policy", len(peer_tasks) == 1,
            "One peer task under safe policy", len(peer_tasks), {"submission_created", "submission_deduplicated"},
            negative=name == "unsafe-retry-baseline")
        completed_data = [task["artifacts"][0]["parts"][0]["data"] for task in peer_tasks if task["status"]["state"] == "TASK_STATE_COMPLETED"]
        if completed_data:
            add("literal_normalization", "implementation_policy", all(data == fixture["expected"] for data in completed_data),
                fixture["expected"], completed_data, {"mock_transformation", "rpc_responded"})
        if name in {"lost-ack", "unsafe-retry-baseline"} or _ambiguous:
            drops = [event for event in events if event["event"] == "response_dropped_after_accept"]
            created = [event for event in events if event["event"] == "submission_created" and event["agent"] == "normalizer"]
            accepted_before_drop = len(drops) == 1 and any(event["task_id"] == drops[0]["task_id"] and event["seq"] < drops[0]["seq"] for event in created)
            add("accepted_before_ack_drop", "harness", accepted_before_drop,
                "Peer task transaction observed before response drop", drops, {"submission_created", "response_dropped_after_accept"})
        if name == "lost-ack":
            dedup = [event for event in events if event["event"] == "submission_deduplicated" and event["agent"] == "normalizer"]
            add("dedup_assumption_and_same_task", "implementation_policy", policy.peer_deduplication_assumed and len(dedup) == 1 and dedup[0]["task_id"] == child_id,
                "Explicit assumption; retry finds same accepted task", {"policy": asdict(policy), "dedup": dedup}, {"recovery_attempt", "submission_deduplicated"})
        if name == "unsafe-retry-baseline":
            add("expected_unsafe_negative_control", "harness", len(peer_tasks) == 2 and policy.unsafe_retry and not policy.peer_deduplication_assumed,
                "Explicit unsafe mode produces two mock tasks", {"peer_tasks": len(peer_tasks), "policy": asdict(policy)}, {"unsafe_retry_enabled", "submission_created"})
        if name in {"peer-unavailable-recovers", "recovery-exhausted"}:
            sends = [event for event in events if event["event"] == "rpc_received" and event["agent"] == "normalizer" and event["payload"]["method"] == "SendMessage"]
            gets = [event["payload"]["params"]["id"] for event in received if event["agent"] == "normalizer" and event["payload"]["method"] == "GetTask"]
            add("known_task_not_resubmitted", "implementation_policy", len(sends) == 1 and bool(gets) and set(gets) == {child_id},
                "One SendMessage; retries GetTask with known ID", {"submissions": len(sends), "retrieved_ids": gets}, {"rpc_received", "peer_unavailable", "peer_available_again"})
        if name == "recovery-exhausted":
            add("exhaustion_remote_unknown", "implementation_policy", parent["metadata"].get("recoveryOutcome") == "exhausted" and parent["metadata"].get("remoteOutcome") == "unknown_to_coordinator",
                "Bounded local failure, unknown remote outcome", parent["metadata"], {"recovery_attempt", "task_failed"})
        if canceled_case:
            add("canceled_tasks_have_no_artifacts", "implementation_policy", "artifacts" not in parent and all(task["status"]["state"] == "TASK_STATE_CANCELED" and not task.get("artifacts") for task in peer_tasks),
                "Both canceled; no late artifacts", {"parent": parent, "peer_tasks": peer_tasks}, {"task_canceled", "terminal_update_discarded"})
            acknowledgment = parent["metadata"].get("remoteCancellation", {})
            add("remote_cancel_acknowledged", "implementation_policy", acknowledgment.get("status") == "acknowledged",
                "Acknowledged separately from local cancellation", acknowledgment, {"remote_cancel_pending", "remote_cancel_acknowledged"})
            ack_events = [event["seq"] for event in events if event["event"] == "http_response" and event["agent"] == "coordinator" and event.get("payload", {}).get("result", {}).get("id") == child_id and event["payload"]["result"].get("status", {}).get("state") == "TASK_STATE_CANCELED"]
            claims = [event["seq"] for event in events if event["event"] == "rpc_responded" and event["agent"] == "coordinator" and event.get("payload", {}).get("result", {}).get("metadata", {}).get("remoteCancellation", {}).get("status") == "acknowledged"]
            add("no_remote_claim_before_ack", "implementation_policy", bool(ack_events) and all(seq > min(ack_events) for seq in claims),
                "Remote-canceled claim follows observed peer acknowledgment", {"ack_events": ack_events, "claim_events": claims}, {"http_response", "rpc_responded"})
        if name == "delayed-after-cancel":
            add("delayed_response_discarded", "implementation_policy", any(event["event"] == "late_response_discarded" for event in events) and any(event["event"] == "terminal_update_discarded" for event in events),
                "Late response and mock artifact cannot revive task", True, {"response_delay_gate_held", "delayed_response_released", "late_response_discarded", "terminal_update_discarded"})
        if name == "cancel-unavailable-recovers":
            pending = pending_snapshot["metadata"].get("remoteCancellation", {}) if pending_snapshot else {}
            add("remote_pending_during_unavailability", "implementation_policy", pending.get("status") == "pending",
                "Remote outcome pending before recovery", pending_snapshot, {"unavailability_gate_held", "rpc_responded", "remote_cancel_pending"})
        if _ambiguous:
            submissions = [event for event in received if event["agent"] == "normalizer" and event["payload"]["method"] == "SendMessage"]
            add("ambiguous_submission_not_resent", "implementation_policy", len(submissions) == 1 and parent["metadata"].get("recoveryOutcome") == "ambiguous_submission",
                "One submission, inconclusive remote acceptance", parent["metadata"], {"submission_inconclusive", "rpc_received"})
            add("remote_submission_outcome", "implementation_policy", False, "Remote outcome remains unknown",
                parent["metadata"].get("remoteOutcome"), {"submission_inconclusive", "response_dropped_after_accept"}, result="inconclusive")
        unexpected = sum(check["result"] == "fail" and not check.get("expected_negative_control") for check in checks)
        summary = {"passed": sum(check["result"] == "pass" for check in checks),
                   "failed": sum(check["result"] == "fail" for check in checks),
                   "expected_negative_failures": sum(check["result"] == "fail" and check.get("expected_negative_control", False) for check in checks),
                   "inconclusive": sum(check["result"] == "inconclusive" for check in checks), "unexpected_failed": unexpected}
        report = {"report_schema": "1.1", "implementation_version": __version__, "milestone": "M2", "scenario": name,
                  "execution_mode": EXECUTION_MODE, "protocol_spec": PROTOCOL_SPEC, "protocol_wire": PROTOCOL_WIRE,
                  "seed": seed, "policy": asdict(policy), "agents": {"coordinator": front.origin, "normalizer": peer.origin},
                  "tasks": {"parent": parent, "child": child}, "peer_tasks_observed_by_harness": peer_tasks,
                  "checks": checks, "summary": summary, "verdict": "pass" if unexpected == 0 else "fail",
                  "verdict_meaning": "expected_scenario_outcomes; safety-policy failures and inconclusive outcomes remain explicit",
                  "not_checked": ["official SDK", "full conformance", "production or crash recovery"], "evidence_file": "events.jsonl"}
        write_json(out / "report.json", report)
        write_json(out / "agent-cards.json", cards)
        return report


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def run_suite(out, seed=7):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    reports = [run_scenario(name, out / name, seed) for name in CORE_SCENARIOS]
    suite = {"report_schema": "1.1", "milestone": "M2", "scenario": "core", "seed": seed,
             "execution_mode": EXECUTION_MODE, "protocol_spec": PROTOCOL_SPEC, "protocol_wire": PROTOCOL_WIRE,
             "verdict": "pass" if all(report["verdict"] == "pass" for report in reports) else "fail",
             "scenarios": [{"name": report["scenario"], "verdict": report["verdict"], "summary": report["summary"],
                            "report_file": report["scenario"] + "/report.json"} for report in reports],
             "summary": {"scenario_count": len(reports), "expected_outcomes_passed": sum(report["verdict"] == "pass" for report in reports),
                         "retained_safety_failures": sum(report["summary"]["failed"] for report in reports)}}
    write_json(out / "report.json", suite)
    return suite
