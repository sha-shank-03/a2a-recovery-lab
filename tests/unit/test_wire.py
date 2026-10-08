import unittest

from a2a_recovery_lab.wire import (WireError, decode_json, validate_get, validate_request,
                                   validate_response, validate_send, validate_version)
from tests.helpers import send_params


class WireTests(unittest.TestCase):
    def assert_wire_error(self, code, callback):
        with self.assertRaises(WireError) as raised:
            callback()
        self.assertEqual(code, raised.exception.code)

    def test_canonical_a2a_message_and_modes(self):
        message, immediate, history = validate_send(send_params())
        self.assertEqual("ROLE_USER", message["role"])
        self.assertFalse(immediate)
        self.assertIsNone(history)
        self.assertTrue(validate_send(send_params(True))[1])
        self.assertFalse(validate_send(send_params(False))[1])

    def test_protojson_numeric_role_and_unknown_fields(self):
        params = send_params()
        params["message"].update(role=1, futureField="ignored")
        message, _, _ = validate_send(params)
        self.assertEqual("ROLE_USER", message["role"])
        self.assertNotIn("futureField", message)

    def test_malformed_json_is_parse_error(self):
        for body in (b'{', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'\xff'):
            with self.subTest(body=body):
                self.assert_wire_error(-32700, lambda: decode_json(body))

    def test_invalid_envelopes(self):
        for value in ([], {}, {"jsonrpc": "1.0"}, {"jsonrpc": "2.0", "method": "GetTask"},
                      {"jsonrpc": "2.0", "id": True, "method": "GetTask"}):
            self.assert_wire_error(-32600, lambda: validate_request(value))
        valid = {"jsonrpc": "2.0", "id": "request-1", "method": "GetTask", "params": {"id": "task-1"}}
        self.assertEqual(("request-1", "GetTask", {"id": "task-1"}), validate_request(valid))

    def test_required_message_fields_and_boolean_types(self):
        for mutation in ({"messageId": ""}, {"role": "user"}, {"role": True}, {"parts": []}, {"parts": {}}):
            params = send_params()
            params["message"].update(mutation)
            self.assert_wire_error(-32602, lambda: validate_send(params))
        params = send_params()
        params["configuration"] = {"returnImmediately": 1}
        self.assert_wire_error(-32602, lambda: validate_send(params))

    def test_part_oneof_and_declared_content(self):
        params = send_params()
        params["message"]["parts"][0]["text"] = "second content"
        self.assert_wire_error(-32602, lambda: validate_send(params))
        params["message"]["parts"] = [{"text": "ticket"}]
        self.assert_wire_error(-32005, lambda: validate_send(params))

    def test_history_bounds_and_zero_presence(self):
        self.assertEqual(("task-1", 0), validate_get({"id": "task-1", "historyLength": 0}))
        for history in (-1, True, 1.5, "1", 2147483648):
            self.assert_wire_error(-32602, lambda: validate_get({"id": "task-1", "historyLength": history}))

    def test_wire_version_ignores_spec_patch(self):
        validate_version("1.0")
        validate_version("1.0.1")
        for version in (None, "", "0.3", "1.1", "v1.0"):
            self.assert_wire_error(-32009, lambda: validate_version(version))

    def test_send_response_wrapper_and_correlation(self):
        task = {"id": "t", "contextId": "c", "status": {"state": "TASK_STATE_COMPLETED"}}
        wrapped = {"jsonrpc": "2.0", "id": "r", "result": {"task": task}}
        self.assertEqual({"task": task}, validate_response(wrapped, "r", "SendMessage"))
        self.assert_wire_error(-32006, lambda: validate_response(wrapped, "wrong", "SendMessage"))
        unwrapped = {"jsonrpc": "2.0", "id": "r", "result": task}
        self.assert_wire_error(-32006, lambda: validate_response(unwrapped, "r", "SendMessage"))
        task["status"]["state"] = "completed"
        self.assert_wire_error(-32006, lambda: validate_response(wrapped, "r", "SendMessage"))

    def test_mapped_a2a_error_detail(self):
        value = WireError(-32001, "Unknown task").envelope("request")
        self.assertEqual("TASK_NOT_FOUND", value["error"]["data"][0]["reason"])
        self.assertEqual("type.googleapis.com/google.rpc.ErrorInfo", value["error"]["data"][0]["@type"])


if __name__ == "__main__":
    unittest.main()
