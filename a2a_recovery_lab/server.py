"""Ephemeral loopback test server with bounded HTTP reads and clean shutdown."""

import threading
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import PROTOCOL_WIRE
from .faults import ResponseDropped
from .wire import MAX_BODY, WireError, canonical, decode_json, validate_request, validate_version


class LabServer:
    def __init__(self, agent, *, faults=None):
        self.agent = agent
        self.server = None
        self.thread = None
        self.closed = False
        self.faults = faults

    def __enter__(self):
        agent = self.agent
        faults = self.faults

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(8)

            def log_message(self, *_):
                pass

            def reply(self, value, status=200):
                body = canonical(value).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("A2A-Version", PROTOCOL_WIRE)
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except OSError:
                    agent.evidence.emit("harness", agent.name, "reply_unconsumed", http_status=status)
                self.close_connection = True

            def do_GET(self):
                if self.path != "/.well-known/agent-card.json":
                    self.reply({"error": "Route not found"}, 404)
                    return
                try:
                    validate_version(self.headers.get("A2A-Version"))
                    card = agent.card()
                    agent.evidence.emit("wire", agent.name, "card_served", url=agent.origin + self.path, card=card)
                    self.reply(card)
                except WireError as exc:
                    self.reply(exc.envelope(), 400)

            def do_POST(self):
                request_id = None
                if self.path != "/rpc":
                    self.reply({"error": "Route not found"}, 404)
                    return
                try:
                    if self.headers.get_content_type() != "application/json":
                        raise WireError(-32600, "M1 RPC requests require application/json")
                    if self.headers.get("Transfer-Encoding"):
                        raise WireError(-32600, "Chunked request bodies are outside M1")
                    try:
                        length = int(self.headers.get("Content-Length", "-1"))
                    except ValueError as exc:
                        raise WireError(-32600, "Invalid Content-Length") from exc
                    if not 0 <= length <= MAX_BODY:
                        raise WireError(-32600, "Request body exceeds the 64 KiB local limit")
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise WireError(-32600, "Incomplete request body")
                    payload = decode_json(raw)
                    if isinstance(payload, dict) and "id" in payload and not isinstance(payload["id"], bool) and isinstance(payload["id"], (str, int, float, type(None))):
                        request_id = payload["id"]
                    request_id, method, params = validate_request(payload)
                    agent.evidence.emit("wire", agent.name, "rpc_received", url=agent.origin + self.path,
                                        headers={"A2A-Version": self.headers.get("A2A-Version"),
                                                 "Content-Type": self.headers.get("Content-Type")}, payload=payload)
                    validate_version(self.headers.get("A2A-Version"))
                    if faults:
                        fault_reply = faults.before(method, payload)
                        if fault_reply:
                            self.reply(fault_reply.body, fault_reply.status)
                            return
                    value = {"jsonrpc": "2.0", "id": request_id, "result": agent.dispatch(method, params)}
                    if faults:
                        value = faults.after(method, payload, value)
                except ResponseDropped:
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    self.close_connection = True
                    return
                except WireError as exc:
                    value = exc.envelope(None if exc.code == -32600 else request_id)
                except (TimeoutError, OSError):
                    value = WireError(-32600, "HTTP request read exceeded its local bound").envelope(request_id)
                except Exception as exc:
                    agent.evidence.emit("harness", agent.name, "internal_error", error_type=type(exc).__name__)
                    value = WireError(-32603, "Internal local test-server error").envelope(request_id)
                agent.evidence.emit("wire", agent.name, "rpc_responded", url=agent.origin + self.path, payload=value)
                self.reply(value)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        # Request threads are joined by server_close; all supported waits are bounded.
        self.server.daemon_threads = False
        agent.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05},
                                       name=f"http-{agent.name}")
        self.thread.start()
        agent.evidence.emit("harness", agent.name, "server_started", origin=agent.origin)
        return self

    @property
    def origin(self):
        return self.agent.origin

    def __exit__(self, *_):
        if self.faults:
            self.faults.close()
        if hasattr(self.agent, "release"):
            self.agent.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.agent.close()
        self.closed = not self.thread.is_alive() and self.server.fileno() == -1 and self.agent.closed
        self.agent.evidence.emit("harness", self.agent.name, "server_stopped", origin=self.origin,
                                 clean=self.closed)
        if not self.closed:
            raise RuntimeError("Local HTTP server did not shut down cleanly")
