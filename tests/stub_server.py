"""A real HTTP server for tests that pretends to be outside providers.

Our code talks to it over real HTTP, exactly as it would talk to OpenAI or
Anthropic, so tests check the real request and the real answer handling.

Each route maps (method, path) to an answer: a dict with "status", either
"json" or "body", and optionally "headers", or a function that receives the
request's JSON (or form fields) and returns such a dict. Every request
received is kept in stub.requests, with its raw body, form fields and query.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit


class StubServer:
    """Holds the routes and the requests received."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        self.http_server = ThreadingHTTPServer(("127.0.0.1", 0), StubRequestHandler)
        self.http_server.stub = self
        port = self.http_server.server_address[1]
        self.base_url = f"http://127.0.0.1:{port}"

    def start(self):
        """Start answering requests in a background thread."""
        # Check for "stop" every 10 ms (the default, 0.5 s, slows every test).
        thread = threading.Thread(
            target=self.http_server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        thread.start()

    def stop(self):
        """Stop the server."""
        self.http_server.shutdown()
        self.http_server.server_close()

    def set_route(self, method, path, answer):
        """Make requests to method + path get answer."""
        self.routes[(method, path)] = answer

    def requests_to(self, path):
        """Return the requests received for one path."""
        return [request for request in self.requests if request["path"] == path]


def read_request(handler):
    """Return the request as a dict: method, path, headers, body, form, query."""
    length = int(handler.headers.get("Content-Length", 0))
    raw_body = handler.rfile.read(length)
    content_type = handler.headers.get("Content-Type", "")
    body = None
    form = None
    if raw_body and content_type.startswith("application/json"):
        body = json.loads(raw_body)
    if content_type.startswith("application/x-www-form-urlencoded"):
        form = dict(parse_qsl(raw_body.decode()))
    parts = urlsplit(handler.path)
    return {
        "method": handler.command,
        "path": parts.path,
        "query": dict(parse_qsl(parts.query)),
        "headers": handler.headers,
        "body": body,
        "form": form,
        "raw_body": raw_body,
    }


def answer_request(handler):
    """Record one request and send back the route's answer."""
    stub = handler.server.stub
    request = read_request(handler)
    stub.requests.append(request)
    route = (request["method"], request["path"])
    answer = stub.routes.get(route, {"status": 404, "json": {}})
    if callable(answer):
        answer = answer(request["body"] or request["form"])
    time.sleep(answer.get("delay", 0))
    content = answer.get("body")
    if content is None:
        content = json.dumps(answer.get("json", {})).encode()
    handler.send_response(answer.get("status", 200))
    handler.send_header("Content-Type", answer.get("content_type", "application/json"))
    handler.send_header("Content-Length", str(len(content)))
    for name, value in answer.get("headers", {}).items():
        handler.send_header(name, value)
    handler.end_headers()
    handler.wfile.write(content)


class StubRequestHandler(BaseHTTPRequestHandler):
    """Passes every GET, POST, PUT and DELETE to answer_request()."""

    def do_GET(self):
        """Answer a GET request."""
        answer_request(self)

    def do_POST(self):
        """Answer a POST request."""
        answer_request(self)

    def do_PUT(self):
        """Answer a PUT request."""
        answer_request(self)

    def do_DELETE(self):
        """Answer a DELETE request."""
        answer_request(self)
