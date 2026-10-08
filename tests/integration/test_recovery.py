import json
import unittest
from pathlib import Path

from a2a_recovery_lab.scenarios import CORE_SCENARIOS, run_scenario, run_suite
from tests.helpers import scratch


class RecoveryHttpTests(unittest.TestCase):
    def test_exact_eight_core_scenarios_and_retained_negative_failure(self):
        with scratch() as directory:
            out = Path(directory) / "suite"
            suite = run_suite(out, seed=7)
            self.assertEqual(CORE_SCENARIOS, tuple(scenario["name"] for scenario in suite["scenarios"]))
            self.assertEqual(8, suite["summary"]["scenario_count"])
            self.assertEqual(8, suite["summary"]["expected_outcomes_passed"])
            self.assertEqual(1, suite["summary"]["retained_safety_failures"])
            for scenario in suite["scenarios"]:
                with self.subTest(scenario=scenario["name"]):
                    report = json.loads((out / scenario["report_file"]).read_text(encoding="utf-8"))
                    self.assertEqual("pass", report["verdict"], report["checks"])
                    events = [json.loads(line) for line in (out / scenario["name"] / "events.jsonl").read_text(encoding="utf-8").splitlines()]
                    self.assertEqual(list(range(1, len(events) + 1)), [event["seq"] for event in events])
                    self.assertEqual(2, sum(event["event"] == "server_stopped" and event["clean"] for event in events))
                    self.assertTrue(all(check["evidence_events"] for check in report["checks"]))
            unsafe = json.loads((out / "unsafe-retry-baseline/report.json").read_text(encoding="utf-8"))
            safety = next(check for check in unsafe["checks"] if check["id"] == "no_duplicate_peer_tasks")
            self.assertEqual("fail", safety["result"])
            self.assertTrue(safety["expected_negative_control"])
            self.assertEqual(2, len(unsafe["peer_tasks_observed_by_harness"]))
            lost = json.loads((out / "lost-ack/report.json").read_text(encoding="utf-8"))
            self.assertTrue(lost["policy"]["peer_deduplication_assumed"])
            self.assertEqual(1, len(lost["peer_tasks_observed_by_harness"]))
            recovering = json.loads((out / "peer-unavailable-recovers/report.json").read_text(encoding="utf-8"))
            self.assertEqual(1, recovering["tasks"]["parent"]["metadata"]["submissionAttempts"])
            exhausted = json.loads((out / "recovery-exhausted/report.json").read_text(encoding="utf-8"))
            self.assertEqual(3, exhausted["tasks"]["parent"]["metadata"]["retrievalAttempts"])
            self.assertEqual("unknown_to_coordinator", exhausted["tasks"]["parent"]["metadata"]["remoteOutcome"])

    def test_ambiguous_submission_without_contract_no_resend(self):
        with scratch() as directory:
            out = Path(directory) / "ambiguous"
            report = run_scenario("ambiguous-submission", out, _ambiguous=True)
            self.assertEqual("pass", report["verdict"], report["checks"])
            self.assertFalse(report["policy"]["peer_deduplication_assumed"])
            self.assertEqual(1, report["tasks"]["parent"]["metadata"]["submissionAttempts"])
            self.assertEqual(1, len(report["peer_tasks_observed_by_harness"]))
            self.assertIsNone(report["tasks"]["child"], "Coordinator must not invent an unacknowledged child ID")
            self.assertEqual(1, report["summary"]["inconclusive"])

    def test_deliberately_corrupted_peer_response_is_not_retried(self):
        with scratch() as directory:
            out = Path(directory) / "invalid-peer"
            report = run_scenario("invalid-peer-response", out, _invalid_response=True)
            self.assertEqual("TASK_STATE_FAILED", report["tasks"]["parent"]["status"]["state"])
            self.assertEqual("WireError", report["tasks"]["parent"]["metadata"]["failureType"])
            self.assertEqual(1, report["tasks"]["parent"]["metadata"]["submissionAttempts"])
            self.assertEqual(1, len(report["peer_tasks_observed_by_harness"]))
            events = [json.loads(line) for line in (out / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(1, sum(event["event"] == "response_corrupted" for event in events))


if __name__ == "__main__":
    unittest.main()
