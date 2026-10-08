import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from a2a_recovery_lab.store import TaskStore
from a2a_recovery_lab.wire import WireError, validate_send
from tests.helpers import scratch, send_params


class StoreTests(unittest.TestCase):
    def test_concurrent_duplicates_create_one_task_and_survive_reopen(self):
        with scratch() as directory:
            path = Path(directory) / "normalizer.sqlite"
            store = TaskStore(path, "normalizer")
            message = validate_send(send_params())[0]
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda _: store.create_or_get(message), range(8)))
            self.assertEqual(1, len({task["id"] for task, _ in results}))
            self.assertEqual(1, sum(created for _, created in results))
            reopened = TaskStore(path, "normalizer")
            task, created = reopened.create_or_get(message)
            self.assertFalse(created)
            self.assertEqual(results[0][0]["id"], task["id"])
            self.assertEqual(1, reopened.count())

    def test_conflicting_message_id_is_rejected_without_new_task(self):
        with scratch() as directory:
            store = TaskStore(Path(directory) / "store.sqlite", "normalizer")
            message = validate_send(send_params())[0]
            store.create_or_get(message)
            message["parts"][0]["data"]["title"] = "different content"
            with self.assertRaises(WireError) as raised:
                store.create_or_get(message)
            self.assertEqual(-32602, raised.exception.code)
            self.assertEqual(1, store.count())

    def test_history_zero_unknown_task_and_terminal_preservation(self):
        with scratch() as directory:
            store = TaskStore(Path(directory) / "store.sqlite", "normalizer")
            task, _ = store.create_or_get(validate_send(send_params())[0])
            self.assertNotIn("history", store.get(task["id"], 0))
            self.assertEqual(1, len(store.get(task["id"], 1)["history"]))
            self.assertTrue(store.update(task["id"], state="TASK_STATE_COMPLETED"))
            self.assertFalse(store.update(task["id"], state="TASK_STATE_WORKING"))
            self.assertEqual("TASK_STATE_COMPLETED", store.get(task["id"])["status"]["state"])
            with self.assertRaises(WireError) as raised:
                store.get("unknown")
            self.assertEqual(-32001, raised.exception.code)

    def test_database_cannot_be_reused_by_another_agent(self):
        with scratch() as directory:
            path = Path(directory) / "store.sqlite"
            TaskStore(path, "normalizer")
            with self.assertRaises(ValueError):
                TaskStore(path, "coordinator")


if __name__ == "__main__":
    unittest.main()
