import unittest

from a2a_recovery_lab.faults import FaultController, ResponseDropped


class MemoryEvidence:
    def __init__(self):
        self.events = []

    def emit(self, layer, agent, event, **fields):
        self.events.append({"layer": layer, "agent": agent, "event": event, **fields})
        return len(self.events)


class FaultControlTests(unittest.TestCase):
    def test_drop_action_only_after_dispatch_result_is_supplied(self):
        evidence = MemoryEvidence()
        faults = FaultController(evidence, drop_first_ack=True)
        payload = {"id": "request-1", "params": {"message": {"messageId": "m"}}}
        self.assertIsNone(faults.before("SendMessage", payload))
        value = {"result": {"task": {"id": "accepted-task", "status": {"state": "TASK_STATE_SUBMITTED"}}}}
        with self.assertRaises(ResponseDropped):
            faults.after("SendMessage", payload, value)
        self.assertEqual("accepted-task", evidence.events[0]["task_id"])
        self.assertEqual("after_agent_dispatch_before_http_reply", evidence.events[0]["fault_boundary"])

    def test_counted_unavailability_and_recovery_callback(self):
        evidence, recovered = MemoryEvidence(), []
        faults = FaultController(evidence, unavailable_method="GetTask", unavailable_count=2,
                                 on_recovered=lambda: recovered.append(True))
        for index in (1, 2):
            reply = faults.before("GetTask", {"id": f"request-{index}"})
            self.assertEqual(503, reply.status)
        self.assertIsNone(faults.before("GetTask", {"id": "request-3"}))
        self.assertEqual([True], recovered)
        self.assertEqual(3, faults.calls["GetTask"])

    def test_cleanup_releases_delay_gate(self):
        evidence = MemoryEvidence()
        faults = FaultController(evidence, delay_first_get=True)
        payload = {"id": "request-1", "params": {"id": "known-task"}}
        faults.before("GetTask", payload)
        faults.close()
        value = {"result": {"id": "known-task", "status": {"state": "TASK_STATE_WORKING"}}}
        self.assertEqual(value, faults.after("GetTask", payload, value))
        self.assertTrue(faults.held.is_set())
        self.assertEqual(["response_delay_gate_held", "delayed_response_released"], [event["event"] for event in evidence.events])


if __name__ == "__main__":
    unittest.main()
