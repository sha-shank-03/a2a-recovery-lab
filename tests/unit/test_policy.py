import json
import unittest

from a2a_recovery_lab.policy import (AmbiguousSubmission, BudgetExhausted, LocalCancellation,
                                     RecoveryPolicy, TransportFailure)
from a2a_recovery_lab.wire import WireError, validate_response
from tests.helpers import ROOT


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class PolicyTests(unittest.TestCase):
    def test_ambiguous_submission_without_contract_is_not_resent(self):
        calls, events = [], []
        def call(attempt, _):
            calls.append(attempt)
            raise TransportFailure("Accepted response may be lost")
        clock = FakeClock()
        with self.assertRaises(AmbiguousSubmission):
            RecoveryPolicy().run("submission", call, clock=clock.clock, sleep=clock.sleep,
                                 observe=lambda event, **fields: events.append(event))
        self.assertEqual([1], calls)
        self.assertEqual([], clock.sleeps)
        self.assertIn("submission_inconclusive", events)

    def test_explicit_dedup_contract_reuses_accepted_task(self):
        calls, ledger = [], {}
        def call(attempt, _):
            calls.append(attempt)
            task = ledger.setdefault("same-message", "one-task")
            if attempt == 1:
                raise TransportFailure("Drop after acceptance")
            return task
        clock = FakeClock()
        result = RecoveryPolicy(peer_deduplication_assumed=True).run(
            "submission", call, clock=clock.clock, sleep=clock.sleep)
        self.assertEqual("one-task", result)
        self.assertEqual([1, 2], calls)
        self.assertEqual(1, len(ledger))

    def test_explicit_unsafe_control_creates_two_tasks(self):
        tasks, events = [], []
        def call(attempt, _):
            tasks.append(f"task-{attempt}")
            if attempt == 1:
                raise TransportFailure("Drop after acceptance")
            return tasks[-1]
        clock = FakeClock()
        result = RecoveryPolicy(unsafe_retry=True).run(
            "submission", call, clock=clock.clock, sleep=clock.sleep,
            observe=lambda event, **fields: events.append(event))
        self.assertEqual("task-2", result)
        self.assertEqual(["task-1", "task-2"], tasks)
        self.assertIn("unsafe_retry_enabled", events)

    def test_known_task_retrieval_recovery_does_not_submit(self):
        calls = []
        def get(attempt, _):
            calls.append(("GetTask", "known-task"))
            if attempt < 3:
                raise TransportFailure("Unavailable")
            return {"id": "known-task", "state": "completed"}
        clock = FakeClock()
        result = RecoveryPolicy(max_attempts=3).run("retrieval", get, clock=clock.clock, sleep=clock.sleep)
        self.assertEqual("known-task", result["id"])
        self.assertEqual([("GetTask", "known-task")] * 3, calls)

    def test_attempt_limit_stops_pending_or_failed_calls(self):
        for fails in (False, True):
            clock, calls = FakeClock(), []
            def call(attempt, _):
                calls.append(attempt)
                if fails:
                    raise TransportFailure("Unavailable")
                return "pending"
            with self.assertRaises(BudgetExhausted) as raised:
                RecoveryPolicy(max_attempts=3).run("retrieval", call, ready=lambda _: False,
                                                   clock=clock.clock, sleep=clock.sleep)
            self.assertEqual([1, 2, 3], calls)
            self.assertEqual("attempt_limit", raised.exception.reason)
            self.assertEqual(3, raised.exception.attempts)

    def test_deadline_prevents_another_attempt(self):
        clock, calls = FakeClock(), []
        def call(attempt, remaining):
            calls.append((attempt, remaining))
            clock.now += 0.075
            raise TransportFailure("Unavailable")
        with self.assertRaises(BudgetExhausted) as raised:
            RecoveryPolicy(deadline_seconds=0.1, retry_delay_seconds=0.1).run(
                "retrieval", call, clock=clock.clock, sleep=clock.sleep)
        self.assertEqual(1, len(calls))
        self.assertEqual("deadline", raised.exception.reason)
        self.assertAlmostEqual(0.025, clock.sleeps[0])

    def test_late_response_is_discarded_after_cancellation(self):
        state, events = {"canceled": False}, []
        def call(_, remaining):
            state["canceled"] = True
            return "late completed result"
        clock = FakeClock()
        with self.assertRaises(LocalCancellation):
            RecoveryPolicy().run("retrieval", call, canceled=lambda: state["canceled"],
                                 clock=clock.clock, sleep=clock.sleep,
                                 observe=lambda event, **fields: events.append(event))
        self.assertIn("late_response_discarded", events)

    def test_invalid_peer_response_is_not_retried(self):
        fixture = json.loads((ROOT / "fixtures/invalid-task-response.json").read_text(encoding="utf-8"))
        calls = []
        def call(attempt, _):
            calls.append(attempt)
            return validate_response(fixture, "invalid-fixture-request", "SendMessage")
        with self.assertRaises(WireError) as raised:
            RecoveryPolicy(peer_deduplication_assumed=True).run("submission", call)
        self.assertEqual(-32006, raised.exception.code)
        self.assertEqual([1], calls)


if __name__ == "__main__":
    unittest.main()
