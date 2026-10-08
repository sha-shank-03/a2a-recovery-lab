import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def scratch():
    directory = ROOT / "work"
    directory.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="test-", dir=directory)


def send_params(immediate=None):
    params = {"message": {"messageId": "test-message-1", "role": "ROLE_USER",
                          "parts": [{"data": {"ticket_id": "INC-0042",
                                              "title": "  Checkout   returns  502  ",
                                              "priority": " HIGH "},
                                     "mediaType": "application/json"}]}}
    if immediate is not None:
        params["configuration"] = {"returnImmediately": immediate}
    return params
