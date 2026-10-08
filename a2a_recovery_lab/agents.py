"""Two deterministic mock agents with a real HTTP handoff."""

import hashlib
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from . import EXECUTION_MODE, PROTOCOL_WIRE, __version__
from .policy import AmbiguousSubmission, BudgetExhausted, LocalCancellation, RecoveryPolicy
from .store import TaskStore
from .transport import HttpClient
from .wire import INTERRUPTED, TERMINAL, WireError, canonical, validate_cancel, validate_get, validate_list, validate_send


def validate_ticket(message):
    if len(message["parts"]) != 1 or not isinstance(message["parts"][0]["data"], dict):
        raise WireError(-32602, "Ticket skill requires one object data part", "message.parts")
    ticket = message["parts"][0]["data"]
    for key in ("ticket_id", "title", "priority"):
        if not isinstance(ticket.get(key), str) or not ticket[key].strip():
            raise WireError(-32602, "Ticket field requires nonempty text", f"message.parts.data.{key}")
    if ticket["priority"].strip().lower() not in {"low", "medium", "high"}:
        raise WireError(-32602, "Priority must be low, medium, or high", "message.parts.data.priority")
    return ticket


def normalize_ticket(ticket):
    return {"ticket_id": ticket["ticket_id"].strip(),
            "title": " ".join(ticket["title"].split()),
            "priority": ticket["priority"].strip().lower(),
            "input_sha256": hashlib.sha256(canonical(ticket).encode("utf-8")).hexdigest()}


def artifact(data, name):
    return {"artifactId": str(uuid.uuid4()), "name": name,
            "parts": [{"data": data, "mediaType": "application/json"}]}


class Agent:
    name = "abstract"

    def __init__(self, db_path, evidence, *, deduplicate=True):
        self.store = TaskStore(db_path, self.name)
        self.evidence = evidence
        self.origin = None
        self.condition = threading.Condition()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"a2a-{self.name}")
        self.closed = False
        self.deduplicate = deduplicate
        self.state_lock = threading.RLock()

    def card(self):
        return {"name": self.name, "description": "Deterministic ticket mock; scoped SendMessage/GetTask/CancelTask/ListTasks",
                "version": __version__, "supportedInterfaces": [
                    {"url": self.origin + "/rpc", "protocolBinding": "JSONRPC", "protocolVersion": PROTOCOL_WIRE}],
                "capabilities": {"streaming": False, "pushNotifications": False, "extendedAgentCard": False},
                "defaultInputModes": ["application/json"], "defaultOutputModes": ["application/json"],
                "skills": [{"id": "normalize-ticket", "name": "Normalize fictional ticket",
                            "description": "Trim title whitespace and normalize priority using deterministic rules",
                            "tags": ["mock", "ticket", "local"]}]}

    def dispatch(self, method, params):
        if method == "GetTask":
            task_id, history = validate_get(params)
            return self.store.get(task_id, history)
        if method == "CancelTask":
            return self.cancel(validate_cancel(params))
        if method == "ListTasks":
            return self.store.list_tasks(validate_list(params))
        if method != "SendMessage":
            if method in {"SendStreamingMessage", "SubscribeToTask", "GetExtendedAgentCard"}:
                raise WireError(-32004, "Operation is outside the supported subset")
            if "PushNotification" in method:
                raise WireError(-32003, "This interface does not support push notifications")
            raise WireError(-32601, "Method not found")
        message, immediate, history = validate_send(params)
        validate_ticket(message)
        if message.get("taskId"):
            task = self.store.get(message["taskId"])
            if message.get("contextId") and message["contextId"] != task["contextId"]:
                raise WireError(-32602, "Task and context IDs do not match", "message.contextId")
            raise WireError(-32004, "Continuing an existing task is outside the M1 subset")
        task, created = self.store.create_or_get(message, deduplicate=self.deduplicate)
        self.evidence.emit("policy", self.name, "submission_created" if created else "submission_deduplicated",
                           task_id=task["id"], message_id=message["messageId"], context_id=task["contextId"])
        if created:
            self.executor.submit(self._work, task["id"], message)
        if not immediate:
            task = self.wait(task["id"])
        else:
            task = self.store.get(task["id"])
        if history == 0:
            task.pop("history", None)
        elif history is not None:
            task["history"] = task.get("history", [])[-history:]
        return {"task": task}

    def wait(self, task_id):
        deadline = time.monotonic() + 6
        with self.condition:
            while True:
                task = self.store.get(task_id)
                if task["status"]["state"] in TERMINAL | INTERRUPTED:
                    return task
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WireError(-32603, "Local blocking wait exceeded its six-second bound")
                self.condition.wait(remaining)

    def _work(self, task_id, message):
        try:
            if not self.store.update(task_id, state="TASK_STATE_WORKING"):
                self.stopped(task_id)
                return
            self.evidence.emit("agent", self.name, "task_working", task_id=task_id)
            result = self.execute(task_id, message)
            if self.store.update(task_id, state="TASK_STATE_COMPLETED", artifacts=[result]):
                self.evidence.emit("agent", self.name, "task_completed", task_id=task_id,
                                   artifact_id=result["artifactId"])
            else:
                self.evidence.emit("policy", self.name, "terminal_update_discarded", task_id=task_id,
                                   artifact_id=result["artifactId"])
        except LocalCancellation:
            self.stopped(task_id)
            self.evidence.emit("policy", self.name, "local_execution_stopped", task_id=task_id)
        except Exception as exc:
            outcome = "ambiguous_submission" if isinstance(exc, AmbiguousSubmission) else (
                "exhausted" if isinstance(exc, BudgetExhausted) else "execution_failed")
            self.store.annotate_policy(task_id, {"recoveryOutcome": outcome,
                                                "remoteOutcome": "unknown_to_coordinator" if self.name == "coordinator" else "not_applicable"})
            changed = self.store.update(task_id, state="TASK_STATE_FAILED", metadata={"failureType": type(exc).__name__})
            if not changed and self.store.get(task_id)["status"]["state"] == "TASK_STATE_CANCELED":
                self.stopped(task_id)
            self.evidence.emit("agent" if changed else "policy", self.name, "task_failed" if changed else "terminal_failure_discarded",
                               task_id=task_id, error_type=type(exc).__name__, recovery_outcome=outcome)
        finally:
            with self.condition:
                self.condition.notify_all()

    def cancel(self, task_id):
        with self.state_lock:
            task, changed = self.store.cancel(task_id)
            if changed:
                self.evidence.emit("agent", self.name, "task_canceled", task_id=task_id)
            self.on_cancel(task_id)
        with self.condition:
            self.condition.notify_all()
        return self.store.get(task_id)

    def on_cancel(self, task_id):
        pass

    def stopped(self, task_id):
        pass

    def execute(self, task_id, message):
        raise NotImplementedError

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.closed = True


class Normalizer(Agent):
    name = "normalizer"

    def execute(self, task_id, message):
        result = artifact(normalize_ticket(validate_ticket(message)), "normalized-ticket")
        self.evidence.emit("agent", self.name, "mock_transformation", task_id=task_id,
                           execution_mode=EXECUTION_MODE, artifact_id=result["artifactId"])
        return result


class Coordinator(Agent):
    name = "coordinator"

    def __init__(self, db_path, evidence, peer_origin, *, policy=None):
        super().__init__(db_path, evidence)
        self.peer_origin = peer_origin
        self.policy = policy or RecoveryPolicy()
        self._cancel_flights = set()

    def _canceled(self, task_id):
        return self.store.get(task_id)["status"]["state"] == "TASK_STATE_CANCELED"

    def _observe(self, task_id):
        def observe(event, **fields):
            self.evidence.emit("policy", self.name, event, parent_task_id=task_id, **fields)
            if event == "recovery_attempt":
                key = {"submission": "submissionAttempts", "retrieval": "retrievalAttempts",
                       "cancellation": "cancellationAttempts"}[fields["operation"]]
                self.store.annotate_policy(task_id, {key: fields["attempt"]})
        return observe

    def stopped(self, task_id):
        task = self.store.get(task_id)
        if not task["metadata"].get("childTaskId"):
            status = "unknown_child_id" if task["metadata"].get("submissionStarted") else "not_started"
            self.store.annotate_policy(task_id, {"remoteCancellation": {"status": status}})

    def on_cancel(self, task_id):
        task = self.store.get(task_id)
        if task["metadata"].get("childTaskId"):
            self._schedule_cancel(task_id)
        elif not task["metadata"].get("remoteCancellation"):
            self.store.annotate_policy(task_id, {"remoteCancellation": {"status": "pending_child_id"}})

    def _schedule_cancel(self, task_id):
        with self.state_lock:
            if task_id in self._cancel_flights:
                return
            self._cancel_flights.add(task_id)
            self.store.annotate_policy(task_id, {"remoteCancellation": {"status": "pending"}})
            self.evidence.emit("policy", self.name, "remote_cancel_pending", parent_task_id=task_id)
            self.executor.submit(self._propagate_cancel, task_id)

    def _propagate_cancel(self, task_id):
        child_id = self.store.get(task_id)["metadata"]["childTaskId"]
        client = HttpClient(self.peer_origin, self.evidence, self.name, timeout=1)
        def call(_, remaining):
            client.timeout = min(1, remaining)
            return client.rpc("CancelTask", {"id": child_id})
        try:
            child = self.policy.run("cancellation", call,
                                    ready=lambda task: task["status"]["state"] == "TASK_STATE_CANCELED",
                                    observe=self._observe(task_id))
            outcome = {"status": "acknowledged", "childTaskId": child_id, "remoteState": child["status"]["state"]}
            self.store.annotate_policy(task_id, {"remoteCancellation": outcome, "remoteOutcome": "canceled_acknowledged"})
            self.evidence.emit("policy", self.name, "remote_cancel_acknowledged", parent_task_id=task_id, child_task_id=child_id)
        except WireError as exc:
            outcome = {"status": "not_cancelable" if exc.code == -32002 else "unknown", "errorCode": exc.code}
            self.store.annotate_policy(task_id, {"remoteCancellation": outcome})
            self.evidence.emit("policy", self.name, "remote_cancel_unconfirmed", parent_task_id=task_id, **outcome)
        except (BudgetExhausted, RuntimeError) as exc:
            self.store.annotate_policy(task_id, {"remoteCancellation": {"status": "unknown"}, "remoteOutcome": "unknown_to_coordinator"})
            self.evidence.emit("policy", self.name, "remote_cancel_unconfirmed", parent_task_id=task_id, error_type=type(exc).__name__)

    def execute(self, task_id, message):
        client = HttpClient(self.peer_origin, self.evidence, self.name, timeout=1)
        client.card()
        parent = self.store.get(task_id)
        self.store.annotate_policy(task_id, {"peerDeduplicationAssumed": self.policy.peer_deduplication_assumed,
                                            "unsafeRetry": self.policy.unsafe_retry})
        child_message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"coordinator:{task_id}:normalize"))
        params = {"message": {
            "messageId": child_message_id, "contextId": parent["contextId"],
            "role": "ROLE_USER", "parts": message["parts"]},
            "configuration": {"returnImmediately": True, "acceptedOutputModes": ["application/json"]}}
        def submit(_, remaining):
            with self.state_lock:
                if self._canceled(task_id):
                    raise LocalCancellation("Canceled before submission")
                self.store.annotate_policy(task_id, {"submissionStarted": True})
            client.timeout = min(1, remaining)
            return client.rpc("SendMessage", params)
        # Keep an acknowledged child ID even when cancellation races the response.
        response = self.policy.run("submission", submit, observe=self._observe(task_id))
        child = response["task"]
        self.store.link_child(task_id, child["id"], self.peer_origin)
        self.evidence.emit("policy", self.name, "handoff_linked", parent_task_id=task_id,
                           child_task_id=child["id"], child_message_id=child_message_id, peer=self.peer_origin)
        if self._canceled(task_id):
            self._schedule_cancel(task_id)
            raise LocalCancellation("Canceled during submission")
        child_id = child["id"]
        def retrieve(_, remaining):
            client.timeout = min(1, remaining)
            return client.rpc("GetTask", {"id": child_id, "historyLength": 0})
        child = self.policy.run("retrieval", retrieve,
                                ready=lambda task: task["status"]["state"] in TERMINAL | INTERRUPTED,
                                canceled=lambda: self._canceled(task_id), observe=self._observe(task_id))
        if child["status"]["state"] != "TASK_STATE_COMPLETED":
            raise RuntimeError("Peer did not complete the ticket task")
        peer_artifact = child["artifacts"][0]
        self.store.update(task_id, metadata={"childArtifactId": peer_artifact["artifactId"]})
        return artifact({"normalizedTicket": peer_artifact["parts"][0]["data"],
                         "childTaskId": child["id"], "childArtifactId": peer_artifact["artifactId"]},
                        "coordinated-ticket")
