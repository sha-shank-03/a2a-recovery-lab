"""Canonical A2A 1.0 JSON-RPC checks for the documented M1 subset.

This is deliberately not a complete protocol/schema validator. Unknown fields
are ignored on input; supported content is one JSON data part per ticket.
"""

import json
import math
import re
from datetime import datetime

from . import PROTOCOL_WIRE

MAX_BODY = 65536
TERMINAL = frozenset({"TASK_STATE_COMPLETED", "TASK_STATE_FAILED",
                      "TASK_STATE_CANCELED", "TASK_STATE_REJECTED"})
INTERRUPTED = frozenset({"TASK_STATE_INPUT_REQUIRED", "TASK_STATE_AUTH_REQUIRED"})
STATES = {"TASK_STATE_UNSPECIFIED": 0, "TASK_STATE_SUBMITTED": 1,
          "TASK_STATE_WORKING": 2, "TASK_STATE_COMPLETED": 3,
          "TASK_STATE_FAILED": 4, "TASK_STATE_CANCELED": 5,
          "TASK_STATE_INPUT_REQUIRED": 6, "TASK_STATE_REJECTED": 7,
          "TASK_STATE_AUTH_REQUIRED": 8}
REASONS = {-32001: "TASK_NOT_FOUND", -32002: "TASK_NOT_CANCELABLE", -32003: "PUSH_NOTIFICATION_NOT_SUPPORTED", -32004: "UNSUPPORTED_OPERATION",
           -32005: "CONTENT_TYPE_NOT_SUPPORTED", -32006: "INVALID_AGENT_RESPONSE",
           -32009: "VERSION_NOT_SUPPORTED"}


class WireError(Exception):
    def __init__(self, code, message, field=None):
        super().__init__(message)
        self.code, self.message, self.field = code, message, field

    def envelope(self, request_id=None):
        error = {"code": self.code, "message": self.message}
        if self.field:
            error["data"] = [{"@type": "type.googleapis.com/google.rpc.BadRequest",
                              "fieldViolations": [{"field": self.field,
                                                   "description": self.message}]}]
        elif self.code in REASONS:
            error["data"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
                              "reason": REASONS[self.code], "domain": "a2a-protocol.org"}]
        return {"jsonrpc": "2.0", "id": request_id, "error": error}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def decode_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate object key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("Non-finite JSON value")

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Non-finite JSON number")
        return result

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=invalid_constant, parse_float=finite_float)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise WireError(-32700, "Invalid JSON payload") from exc


def require_object(value, field):
    if not isinstance(value, dict):
        raise WireError(-32602, "Expected an object", field)
    return value


def require_string(value, field, allow_empty=False):
    if not isinstance(value, str) or (not value and not allow_empty):
        raise WireError(-32602, "Expected a nonempty string", field)
    return value


def validate_version(value):
    # Compatibility uses major.minor; specification patches do not negotiate.
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.\d+)?", value or "0.3")
    if not match or f"{match[1]}.{match[2]}" != PROTOCOL_WIRE:
        raise WireError(-32009, "This local interface supports A2A 1.0 only")


def validate_request(value):
    if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
        raise WireError(-32600, "Expected a JSON-RPC 2.0 request object")
    request_id = value.get("id")
    if "id" not in value or isinstance(request_id, bool) or not isinstance(
            request_id, (str, int, float, type(None))):
        raise WireError(-32600, "M1 requires a request ID; notifications are unsupported")
    if not isinstance(value.get("method"), str) or not value["method"]:
        raise WireError(-32600, "Expected a method name")
    params = value.get("params", {})
    require_object(params, "params")
    return request_id, value["method"], params


def history_length(container):
    value = container.get("historyLength")
    if value is not None and (type(value) is not int or not 0 <= value <= 2147483647):
        raise WireError(-32602, "Expected a nonnegative int32", "historyLength")
    return value


def validate_part(part):
    require_object(part, "message.parts")
    contents = [key for key in ("text", "raw", "url", "data") if key in part]
    if len(contents) != 1:
        raise WireError(-32602, "A part requires exactly one content field", "message.parts")
    if "mediaType" in part:
        require_string(part["mediaType"], "message.parts.mediaType")
    if "metadata" in part:
        require_object(part["metadata"], "message.parts.metadata")
    # Other part kinds are valid A2A, but outside the card's input modes.
    if contents[0] != "data" or part.get("mediaType", "application/json") != "application/json":
        raise WireError(-32005, "This skill accepts application/json data parts only")
    return {key: part[key] for key in ("data", "mediaType", "metadata") if key in part}


def validate_send(params):
    if params.get("tenant") not in (None, ""):
        raise WireError(-32004, "This local interface has no tenant routing")
    if "metadata" in params:
        require_object(params["metadata"], "metadata")
    message = require_object(params.get("message"), "message")
    require_string(message.get("messageId"), "message.messageId")
    role = message.get("role")
    if role != "ROLE_USER" and not (type(role) is int and role == 1):
        raise WireError(-32602, "Client messages require ROLE_USER", "message.role")
    for key in ("contextId", "taskId"):
        if key in message:
            require_string(message[key], f"message.{key}", allow_empty=True)
    if "metadata" in message:
        require_object(message["metadata"], "message.metadata")
    parts = message.get("parts")
    if not isinstance(parts, list) or not parts:
        raise WireError(-32602, "At least one part is required", "message.parts")
    normalized = {key: message[key] for key in ("messageId", "contextId", "taskId", "metadata")
                  if key in message and message[key] != ""}
    normalized.update(role="ROLE_USER", parts=[validate_part(part) for part in parts])
    configuration = require_object(params.get("configuration", {}), "configuration")
    immediate = configuration.get("returnImmediately", False)
    if type(immediate) is not bool:
        raise WireError(-32602, "Expected a boolean", "configuration.returnImmediately")
    modes = configuration.get("acceptedOutputModes", [])
    if not isinstance(modes, list) or any(not isinstance(x, str) for x in modes):
        raise WireError(-32602, "Expected a string array", "configuration.acceptedOutputModes")
    if modes and "application/json" not in modes:
        raise WireError(-32005, "This skill produces application/json only")
    if configuration.get("taskPushNotificationConfig") is not None:
        raise WireError(-32003, "This interface does not support push notifications")
    return normalized, immediate, history_length(configuration)


def validate_get(params):
    if params.get("tenant") not in (None, ""):
        raise WireError(-32004, "This local interface has no tenant routing")
    return require_string(params.get("id"), "id"), history_length(params)


def validate_cancel(params):
    task_id, _ = validate_get(params)
    if "metadata" in params:
        require_object(params["metadata"], "metadata")
    return task_id


def validate_list(params):
    if params.get("tenant") not in (None, ""):
        raise WireError(-32004, "This local interface has no tenant routing")
    context = params.get("contextId", "")
    token = params.get("pageToken", "")
    require_string(context, "contextId", allow_empty=True)
    require_string(token, "pageToken", allow_empty=True)
    size = params.get("pageSize", 50)
    if type(size) is not int or not 1 <= size <= 100:
        raise WireError(-32602, "pageSize must be in [1,100]", "pageSize")
    include = params.get("includeArtifacts", False)
    if type(include) is not bool:
        raise WireError(-32602, "Expected a boolean", "includeArtifacts")
    state = params.get("status", "TASK_STATE_UNSPECIFIED")
    if type(state) is int:
        state = next((name for name, value in STATES.items() if value == state), None)
    if not isinstance(state, str) or state not in STATES:
        raise WireError(-32602, "Unknown status filter", "status")
    after = params.get("statusTimestampAfter")
    if after is not None:
        try:
            require_string(after, "statusTimestampAfter")
            parsed = datetime.fromisoformat(after.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Timezone required")
            after = parsed.timestamp()
        except (WireError, ValueError) as exc:
            raise WireError(-32602, "Expected timezone-aware ISO timestamp", "statusTimestampAfter") from exc
    return {"context": context, "state": None if state == "TASK_STATE_UNSPECIFIED" else state,
            "after": after, "size": size, "token": token, "history": history_length(params),
            "include_artifacts": include}


def validate_task(task):
    try:
        require_object(task, "task")
        require_string(task.get("id"), "task.id")
        if "contextId" in task:
            require_string(task["contextId"], "task.contextId")
        status = require_object(task.get("status"), "task.status")
        state = status.get("state")
        if not (isinstance(state, str) and state in STATES) and not (
                type(state) is int and state in STATES.values()):
            raise WireError(-32602, "Invalid task state", "task.status.state")
        if "timestamp" in status:
            timestamp = require_string(status["timestamp"], "task.status.timestamp")
            if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)", timestamp):
                raise WireError(-32602, "Expected RFC3339 timestamp", "task.status.timestamp")
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if "artifacts" in task:
            if not isinstance(task["artifacts"], list):
                raise WireError(-32602, "Expected artifact array", "task.artifacts")
            for artifact in task["artifacts"]:
                require_object(artifact, "artifact")
                require_string(artifact.get("artifactId"), "artifact.artifactId")
                if not isinstance(artifact.get("parts"), list) or not artifact["parts"]:
                    raise WireError(-32602, "Expected artifact parts", "artifact.parts")
                for part in artifact["parts"]:
                    validate_part(part)
        return task
    except (WireError, ValueError) as exc:
        raise WireError(-32006, "Peer returned an invalid task") from exc


def validate_response(value, request_id, method):
    if not isinstance(value, dict) or value.get("jsonrpc") != "2.0" or value.get("id") != request_id:
        raise WireError(-32006, "Invalid or mismatched JSON-RPC response")
    if ("result" in value) == ("error" in value):
        raise WireError(-32006, "Response requires exactly one result or error")
    if "error" in value:
        error = value["error"]
        if not isinstance(error, dict) or type(error.get("code")) is not int or not isinstance(error.get("message"), str):
            raise WireError(-32006, "Malformed peer error")
        raise WireError(error["code"], error["message"])
    result = value["result"]
    if method == "SendMessage":
        if not isinstance(result, dict) or "task" not in result or "message" in result:
            raise WireError(-32006, "M1 peer must return a SendMessageResponse task wrapper")
        validate_task(result["task"])
    elif method in {"GetTask", "CancelTask"}:
        validate_task(result)
    elif method == "ListTasks":
        if not isinstance(result, dict) or not isinstance(result.get("tasks"), list) or not isinstance(result.get("nextPageToken"), str):
            raise WireError(-32006, "Malformed ListTasks response")
        for key in ("pageSize", "totalSize"):
            if type(result.get(key)) is not int or result[key] < 0:
                raise WireError(-32006, "Invalid ListTasks count")
        for task in result["tasks"]:
            validate_task(task)
    return result


def validate_card(card):
    try:
        require_object(card, "card")
        for key in ("name", "description", "version"):
            require_string(card.get(key), f"card.{key}")
        require_object(card.get("capabilities"), "card.capabilities")
        for key in ("skills", "defaultInputModes", "defaultOutputModes", "supportedInterfaces"):
            if not isinstance(card.get(key), list) or not card[key]:
                raise WireError(-32602, "Required nonempty array", key)
        matching = [interface for interface in card["supportedInterfaces"]
                    if isinstance(interface, dict) and interface.get("protocolBinding") == "JSONRPC"
                    and interface.get("protocolVersion") == PROTOCOL_WIRE]
        if not matching:
            raise WireError(-32602, "No JSONRPC 1.0 interface", "supportedInterfaces")
        require_string(matching[0].get("url"), "interface.url")
        return matching[0]["url"]
    except WireError as exc:
        raise WireError(-32006, "Peer card does not satisfy M1 interface checks") from exc
