import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from a2a_recovery_lab.agents import Coordinator
from a2a_recovery_lab.evidence import EvidenceLog
from a2a_recovery_lab.policy import AmbiguousSubmission
from a2a_recovery_lab.store import TaskStore
from a2a_recovery_lab.wire import WireError, validate_cancel, validate_list, validate_send
from tests.helpers import scratch, send_params


class CancellationListingTests(unittest.TestCase):
    def test_cancel_during_unacknowledged_submission_records_unknown_child(self):
        with scratch() as directory, EvidenceLog(Path(directory) / "events.jsonl") as evidence:
            agent = Coordinator(Path(directory) / "store.sqlite", evidence, "http://127.0.0.1:9001")
            message = validate_send(send_params())[0]
            task, _ = agent.store.create_or_get(message)
            def ambiguous_after_cancel(task_id, _):
                agent.store.annotate_policy(task_id, {"submissionStarted": True})
                agent.cancel(task_id)
                raise AmbiguousSubmission("Submission acknowledgment was lost")
            try:
                with patch.object(agent, "execute", side_effect=ambiguous_after_cancel):
                    agent._work(task["id"], message)
                final = agent.store.get(task["id"])
                self.assertEqual("TASK_STATE_CANCELED", final["status"]["state"])
                self.assertEqual("unknown_child_id", final["metadata"]["remoteCancellation"]["status"])
                self.assertEqual("unknown_to_coordinator", final["metadata"]["remoteOutcome"])
                self.assertNotIn("childTaskId", final["metadata"])
                self.assertNotIn("artifacts", final)
                self.assertEqual(0, final["metadata"].get("cancellationAttempts", 0))
            finally:
                agent.close()

    def test_repeat_cancel_and_late_artifact_preserve_terminal_task(self):
        with scratch() as directory:
            store = TaskStore(Path(directory) / "store.sqlite", "normalizer")
            task, _ = store.create_or_get(validate_send(send_params())[0])
            canceled, changed = store.cancel(task["id"])
            self.assertTrue(changed)
            repeated, changed = store.cancel(task["id"])
            self.assertFalse(changed)
            self.assertEqual(canceled, repeated)
            self.assertFalse(store.update(task["id"], state="TASK_STATE_COMPLETED", artifacts=[{"artifactId": "late"}]))
            final = store.get(task["id"])
            self.assertEqual("TASK_STATE_CANCELED", final["status"]["state"])
            self.assertNotIn("artifacts", final)
            store.annotate_policy(task["id"], {"remoteCancellation": {"status": "pending"}})
            self.assertEqual("pending", store.get(task["id"])["metadata"]["remoteCancellation"]["status"])
            with self.assertRaises(ValueError):
                store.annotate_policy(task["id"], {"childArtifactId": "late"})

    def test_completion_cancellation_race_has_one_terminal_winner(self):
        with scratch() as directory:
            store = TaskStore(Path(directory) / "store.sqlite", "normalizer")
            task, _ = store.create_or_get(validate_send(send_params())[0])
            def cancel():
                try:
                    return store.cancel(task["id"])[1]
                except WireError as exc:
                    self.assertEqual(-32002, exc.code)
                    return False
            with ThreadPoolExecutor(max_workers=2) as pool:
                completing = pool.submit(store.update, task["id"], state="TASK_STATE_COMPLETED", artifacts=[{"artifactId": "winner"}])
                canceling = pool.submit(cancel)
                outcomes = [completing.result(), canceling.result()]
            self.assertEqual(1, sum(outcomes))
            final = store.get(task["id"])
            if final["status"]["state"] == "TASK_STATE_COMPLETED":
                self.assertEqual([{"artifactId": "winner"}], final["artifacts"])
            else:
                self.assertEqual("TASK_STATE_CANCELED", final["status"]["state"])
                self.assertNotIn("artifacts", final)

    def test_late_child_link_does_not_change_canceled_state(self):
        with scratch() as directory:
            store = TaskStore(Path(directory) / "store.sqlite", "coordinator")
            task, _ = store.create_or_get(validate_send(send_params())[0])
            store.cancel(task["id"])
            store.link_child(task["id"], "accepted-child", "http://127.0.0.1:9001")
            final = store.get(task["id"])
            self.assertEqual("accepted-child", final["metadata"]["childTaskId"])
            self.assertEqual("TASK_STATE_CANCELED", final["status"]["state"])
            self.assertNotIn("artifacts", final)

    def test_list_context_order_keyset_and_artifact_omission(self):
        with scratch() as directory:
            store = TaskStore(Path(directory) / "store.sqlite", "normalizer")
            ids = []
            with patch("a2a_recovery_lab.store.timestamp", side_effect=["2026-01-01T00:00:01.000Z", "2026-01-01T00:00:02.000Z", "2026-01-01T00:00:03.000Z"]):
                for index in range(3):
                    message = validate_send(send_params())[0]
                    message.update(messageId=f"m-{index}", contextId="same-context")
                    ids.append(store.create_or_get(message)[0]["id"])
            first = store.list_tasks(validate_list({"contextId": "same-context", "pageSize": 2, "historyLength": 0}))
            self.assertEqual(ids[::-1][:2], [task["id"] for task in first["tasks"]])
            self.assertTrue(first["nextPageToken"])
            self.assertEqual(3, first["totalSize"])
            self.assertTrue(all("artifacts" not in task and "history" not in task for task in first["tasks"]))
            second = store.list_tasks(validate_list({"contextId": "same-context", "pageSize": 2, "pageToken": first["nextPageToken"], "includeArtifacts": True}))
            self.assertEqual([ids[0]], [task["id"] for task in second["tasks"]])
            self.assertEqual("", second["nextPageToken"])
            self.assertEqual([], second["tasks"][0]["artifacts"])
            empty = store.list_tasks(validate_list({"contextId": "different-context"}))
            self.assertEqual([], empty["tasks"])
            self.assertEqual("", empty["nextPageToken"])
            with self.assertRaises(WireError):
                store.list_tasks(validate_list({"contextId": "changed", "pageToken": first["nextPageToken"]}))

    def test_list_status_and_timestamp_filters(self):
        with scratch() as directory:
            store = TaskStore(Path(directory) / "store.sqlite", "normalizer")
            with patch("a2a_recovery_lab.store.timestamp", side_effect=["2026-01-01T00:00:01.000Z", "2026-01-01T00:00:02.000Z"]):
                task, _ = store.create_or_get(validate_send(send_params())[0])
                store.cancel(task["id"])
            page = store.list_tasks(validate_list({"status": "TASK_STATE_CANCELED", "statusTimestampAfter": "2026-01-01T00:00:02Z"}))
            self.assertEqual([task["id"]], [task["id"] for task in page["tasks"]])
            self.assertEqual([], store.list_tasks(validate_list({"status": "TASK_STATE_COMPLETED"}))["tasks"])

    def test_invalid_cancel_and_list_fields(self):
        for params in ({"pageSize": 0}, {"pageSize": 101}, {"pageSize": True}, {"includeArtifacts": 1}, {"status": "running"}, {"statusTimestampAfter": "bad"}):
            with self.assertRaises(WireError) as raised:
                validate_list(params)
            self.assertEqual(-32602, raised.exception.code)
        with self.assertRaises(WireError):
            validate_cancel({"id": ""})


if __name__ == "__main__":
    unittest.main()
