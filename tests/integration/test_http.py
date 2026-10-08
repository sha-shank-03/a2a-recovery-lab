import json
import subprocess
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

from a2a_recovery_lab.agents import Normalizer
from a2a_recovery_lab.evidence import EvidenceLog
from a2a_recovery_lab.server import LabServer
from a2a_recovery_lab.transport import HttpClient
from a2a_recovery_lab.wire import WireError
from tests.helpers import ROOT, scratch, send_params


class GatedNormalizer(Normalizer):
    """Test synchronization outside the protocol API, without fixed sleeps."""

    def __init__(self, path, evidence):
        super().__init__(path, evidence)
        self.started = threading.Event()
        self.release = threading.Event()

    def execute(self, task_id, message):
        self.started.set()
        if not self.release.wait(2):
            raise RuntimeError("Test failed to release execution gate")
        return super().execute(task_id, message)


class HttpTests(unittest.TestCase):
    def test_default_and_explicit_false_send_wait_for_completion(self):
        for immediate in (None, False):
            with self.subTest(immediate=immediate), scratch() as directory:
                with EvidenceLog(Path(directory) / "events.jsonl") as evidence:
                    agent = GatedNormalizer(Path(directory) / "tasks.sqlite", evidence)
                    with LabServer(agent) as server, ThreadPoolExecutor(max_workers=1) as pool:
                        client = HttpClient(server.origin, evidence)
                        future = pool.submit(client.rpc, "SendMessage", send_params(immediate))
                        try:
                            self.assertTrue(agent.started.wait(1))
                            self.assertFalse(future.done(), "Blocking send returned before the executor gate opened")
                        finally:
                            agent.release.set()
                        task = future.result(timeout=2)["task"]
                        self.assertEqual("TASK_STATE_COMPLETED", task["status"]["state"])
                        self.assertEqual("Checkout returns 502", task["artifacts"][0]["parts"][0]["data"]["title"])
                    self.assertTrue(server.closed)

    def test_return_immediately_then_get_task(self):
        with scratch() as directory, EvidenceLog(Path(directory) / "events.jsonl") as evidence:
            agent = GatedNormalizer(Path(directory) / "tasks.sqlite", evidence)
            with LabServer(agent) as server:
                client = HttpClient(server.origin, evidence)
                try:
                    task = client.rpc("SendMessage", send_params(True))["task"]
                    self.assertTrue(agent.started.wait(1))
                    self.assertIn(task["status"]["state"], {"TASK_STATE_SUBMITTED", "TASK_STATE_WORKING"})
                    pending = client.rpc("GetTask", {"id": task["id"], "historyLength": 0})
                    self.assertEqual("TASK_STATE_WORKING", pending["status"]["state"])
                    self.assertNotIn("history", pending)
                finally:
                    agent.release.set()
                # A duplicate default-blocking submission waits on the same task.
                completed = client.rpc("SendMessage", send_params())["task"]
                self.assertEqual(task["id"], completed["id"])
                self.assertEqual("TASK_STATE_COMPLETED", completed["status"]["state"])
                self.assertEqual(1, agent.store.count())
            self.assertTrue(server.closed)

    def test_unknown_task_and_version_errors_over_http(self):
        with scratch() as directory, EvidenceLog(Path(directory) / "events.jsonl") as evidence:
            with LabServer(Normalizer(Path(directory) / "tasks.sqlite", evidence)) as server:
                client = HttpClient(server.origin, evidence)
                self.assertEqual("JSONRPC", client.card()["supportedInterfaces"][0]["protocolBinding"])
                with self.assertRaises(WireError) as raised:
                    client.rpc("GetTask", {"id": "unknown"})
                self.assertEqual(-32001, raised.exception.code)
                payload = json.dumps({"jsonrpc": "2.0", "id": "bad-version", "method": "GetTask", "params": {"id": "unknown"}}).encode()
                request = Request(server.origin + "/rpc", data=payload, headers={"Content-Type": "application/json", "A2A-Version": "0.3"})
                with build_opener(ProxyHandler({})).open(request, timeout=2) as response:
                    error = json.load(response)
                self.assertEqual("bad-version", error["id"])
                self.assertEqual(-32009, error["error"]["code"])
                invalid_params = Request(server.origin + "/rpc", data=b'{"jsonrpc":"2.0","id":"bad-params","method":"GetTask","params":[]}',
                                         headers={"Content-Type": "application/json", "A2A-Version": "1.0"})
                with build_opener(ProxyHandler({})).open(invalid_params, timeout=2) as response:
                    error = json.load(response)
                self.assertEqual("bad-params", error["id"], "Invalid parameters must preserve an otherwise valid request ID")
                self.assertEqual(-32602, error["error"]["code"])

    def test_cli_demo_two_servers_literal_artifacts_and_teardown(self):
        with scratch() as directory:
            out = Path(directory) / "demo"
            result = subprocess.run([sys.executable, "-m", "a2a_recovery_lab", "demo", "--scenario", "happy-path", "--out", str(out)],
                                    cwd=ROOT, text=True, capture_output=True, timeout=12)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("deterministic_mock_over_http", result.stdout)
            self.assertIn("spec=1.0.1 wire=1.0", result.stdout)
            report = json.loads((out / "report.json").read_text(encoding="utf-8"))
            self.assertEqual("pass", report["verdict"])
            self.assertEqual(0, report["summary"]["failed"])
            self.assertNotEqual(report["agents"]["normalizer"], report["agents"]["coordinator"])
            parent, child = report["tasks"]["parent"], report["tasks"]["child"]
            self.assertEqual("TASK_STATE_COMPLETED", parent["status"]["state"])
            self.assertEqual("TASK_STATE_COMPLETED", child["status"]["state"])
            self.assertEqual(child["id"], parent["metadata"]["childTaskId"])
            self.assertEqual(parent["contextId"], child["contextId"])
            self.assertEqual({"ticket_id": "INC-0042", "title": "Checkout returns 502", "priority": "high",
                              "input_sha256": "d37e90ba1e3f588afb51f9eb954856269c6eb06deb9e8247e2fd8dfce98ed027"},
                             child["artifacts"][0]["parts"][0]["data"])
            events = [json.loads(line) for line in (out / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(list(range(1, len(events) + 1)), [event["seq"] for event in events])
            started = [event for event in events if event["event"] == "server_started"]
            stopped = [event for event in events if event["event"] == "server_stopped"]
            self.assertEqual(2, len(started))
            self.assertEqual(2, len(stopped))
            self.assertTrue(all(event["clean"] for event in stopped))
            child_submissions = [event for event in events if event["event"] == "rpc_received" and event["agent"] == "normalizer" and event["payload"]["method"] == "SendMessage"]
            self.assertEqual(1, len(child_submissions), "Handoff must traverse Normalizer's actual HTTP endpoint")
            self.assertTrue(child_submissions[0]["payload"]["params"]["configuration"]["returnImmediately"])
            reread = subprocess.run([sys.executable, "-m", "a2a_recovery_lab", "report", str(out / "report.json")],
                                   cwd=ROOT, text=True, capture_output=True, timeout=3)
            self.assertEqual(0, reread.returncode, reread.stderr)
            self.assertIn("recorded_report_read", reread.stdout)
            # Existing evidence is preserved, not silently overwritten.
            repeated = subprocess.run([sys.executable, "-m", "a2a_recovery_lab", "demo", "--out", str(out)],
                                     cwd=ROOT, text=True, capture_output=True, timeout=3)
            self.assertEqual(2, repeated.returncode)
            self.assertIn("already exists", repeated.stderr)


if __name__ == "__main__":
    unittest.main()
