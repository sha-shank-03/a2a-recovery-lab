import unittest

from a2a_recovery_lab.agents import normalize_ticket, validate_ticket
from a2a_recovery_lab.wire import WireError
from tests.helpers import send_params


class TransformTests(unittest.TestCase):
    def test_literal_expected_transformation(self):
        result = normalize_ticket(send_params()["message"]["parts"][0]["data"])
        self.assertEqual({"ticket_id": "INC-0042", "title": "Checkout returns 502", "priority": "high",
                          "input_sha256": "d37e90ba1e3f588afb51f9eb954856269c6eb06deb9e8247e2fd8dfce98ed027"}, result)

    def test_application_schema_rejects_invalid_priority_and_blank_title(self):
        for key, value in (("priority", "urgent"), ("title", "  "), ("ticket_id", 42)):
            message = send_params()["message"]
            message["parts"][0]["data"][key] = value
            with self.assertRaises(WireError) as raised:
                validate_ticket(message)
            self.assertEqual(-32602, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
