"""Bounded JSON-RPC HTTP client; loopback-only and no ambient proxies."""

import ipaddress
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from . import PROTOCOL_WIRE
from .policy import TransportFailure
from .wire import MAX_BODY, WireError, canonical, decode_json, validate_card, validate_response


def require_loopback(url):
    parsed = urlsplit(url)
    try:
        loopback = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname).is_loopback
        valid_port = parsed.port is not None and 0 < parsed.port <= 65535
    except (ValueError, TypeError):
        loopback = valid_port = False
    if parsed.scheme != "http" or not loopback or not valid_port or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("M1 transport requires an HTTP loopback URL with an explicit port")
    return parsed


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Redirects are disabled", headers, fp)


class HttpClient:
    def __init__(self, origin, evidence, agent="runner", timeout=2):
        parsed = require_loopback(origin)
        if parsed.path not in ("", "/"):
            raise ValueError("Provide the peer origin, not an RPC path")
        self.origin, self.evidence, self.agent, self.timeout = origin.rstrip("/"), evidence, agent, timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def _request(self, url, payload=None):
        require_loopback(url)
        method = "GET" if payload is None else "POST"
        headers = {"A2A-Version": PROTOCOL_WIRE, "Accept": "application/json"}
        raw = None
        if payload is not None:
            raw = canonical(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request_seq = self.evidence.emit("wire", self.agent, "http_request", url=url,
                                         http_method=method, headers=headers, payload=payload)
        request = Request(url, data=raw, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.headers.get_content_type() != "application/json":
                    raise WireError(-32006, "Peer response is not application/json")
                body = response.read(MAX_BODY + 1)
                if len(body) > MAX_BODY:
                    raise WireError(-32006, "Peer response exceeds local size limit")
                try:
                    value = decode_json(body)
                except WireError as exc:
                    raise WireError(-32006, "Peer response contains invalid JSON") from exc
                self.evidence.emit("wire", self.agent, "http_response", url=url,
                                   request_event=request_seq, http_status=response.status, payload=value)
                return value
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if isinstance(exc, HTTPError):
                exc.close()
            self.evidence.emit("wire", self.agent, "http_transport_error", url=url,
                               request_event=request_seq, error_type=type(exc).__name__)
            raise TransportFailure("Local peer HTTP exchange failed") from exc

    def card(self):
        card = self._request(self.origin + "/.well-known/agent-card.json")
        endpoint = validate_card(card)
        parsed = require_loopback(endpoint)
        # A card cannot redirect this M1 runner to a different authority.
        if parsed.netloc != urlsplit(self.origin).netloc or parsed.path != "/rpc":
            raise WireError(-32006, "M1 card must advertise this origin's /rpc endpoint")
        return card

    def rpc(self, method, params):
        request_id = str(uuid.uuid4())
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        return validate_response(self._request(self.origin + "/rpc", payload), request_id, method)
