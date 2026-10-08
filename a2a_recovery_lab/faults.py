"""Owned-server harness faults. No fault controls are exposed on the agent API."""

import copy
import threading
from dataclasses import dataclass

from .agents import Normalizer


class ResponseDropped(Exception):
    pass


@dataclass
class FaultReply:
    status: int
    body: dict


class FaultController:
    def __init__(self, evidence, *, drop_first_ack=False, delay_first_get=False,
                 unavailable_method=None, unavailable_count=0, pause_first_unavailable=False,
                 corrupt_first_ack=False, on_recovered=lambda: None):
        self.evidence = evidence
        self.drop_first_ack, self.delay_first_get = drop_first_ack, delay_first_get
        self.unavailable_method, self.unavailable_count = unavailable_method, unavailable_count
        self.pause_first_unavailable, self.corrupt_first_ack = pause_first_unavailable, corrupt_first_ack
        self.on_recovered = on_recovered
        self.held, self.release = threading.Event(), threading.Event()
        self.calls, self._ordinals = {}, {}
        self._lock = threading.Lock()

    def _gate(self, event, **fields):
        self.evidence.emit("harness", "normalizer", event, **fields)
        self.held.set()
        if not self.release.wait(2):
            raise TimeoutError("Fault gate was not released within two seconds")

    def before(self, method, payload):
        with self._lock:
            occurrence = self.calls.get(method, 0) + 1
            self.calls[method] = occurrence
            self._ordinals[payload["id"]] = occurrence
        if method == self.unavailable_method and occurrence <= self.unavailable_count:
            if self.pause_first_unavailable and occurrence == 1:
                self._gate("unavailability_gate_held", method=method, occurrence=occurrence)
            self.evidence.emit("harness", "normalizer", "peer_unavailable", method=method,
                               occurrence=occurrence, request_id=payload["id"], fault_boundary="before_agent_dispatch")
            return FaultReply(503, {"jsonrpc": "2.0", "id": payload["id"],
                                   "error": {"code": -32603, "message": "Injected local peer unavailability"}})
        if method == self.unavailable_method and occurrence == self.unavailable_count + 1 and self.unavailable_count:
            self.evidence.emit("harness", "normalizer", "peer_available_again", method=method, occurrence=occurrence)
            self.on_recovered()
        return None

    def after(self, method, payload, value):
        with self._lock:
            occurrence = self._ordinals[payload["id"]]
        if method == "SendMessage" and occurrence == 1 and "result" in value:
            if self.drop_first_ack:
                task = value["result"]["task"]
                self.evidence.emit("harness", "normalizer", "response_dropped_after_accept",
                                   task_id=task["id"], message_id=payload["params"]["message"]["messageId"],
                                   request_id=payload["id"], accepted_state=task["status"]["state"],
                                   fault_boundary="after_agent_dispatch_before_http_reply")
                raise ResponseDropped
            if self.corrupt_first_ack:
                value = copy.deepcopy(value)
                value["result"]["task"]["status"]["state"] = "completed"
                self.evidence.emit("harness", "normalizer", "response_corrupted", request_id=payload["id"])
        if method == "GetTask" and occurrence == 1 and self.delay_first_get:
            self._gate("response_delay_gate_held", request_id=payload["id"], task_id=payload["params"]["id"],
                       captured_state=value.get("result", {}).get("status", {}).get("state"))
            self.evidence.emit("harness", "normalizer", "delayed_response_released", request_id=payload["id"])
        return value

    def close(self):
        self.release.set()


class GatedNormalizer(Normalizer):
    """Delay mock completion to exercise cancellation; cleanup always releases it."""

    def __init__(self, path, evidence, *, deduplicate=True):
        super().__init__(path, evidence, deduplicate=deduplicate)
        self.started, self.release = threading.Event(), threading.Event()

    def execute(self, task_id, message):
        self.evidence.emit("harness", self.name, "completion_gate_held", task_id=task_id)
        self.started.set()
        if not self.release.wait(3):
            raise TimeoutError("Completion gate was not released within three seconds")
        self.evidence.emit("harness", self.name, "completion_gate_released", task_id=task_id)
        return super().execute(task_id, message)
