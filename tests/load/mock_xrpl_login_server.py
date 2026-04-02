#
# Lightweight mock homeserver for Locust XRPL auth load tests.
#
from __future__ import annotations

import argparse
import json
import random
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class Handler(BaseHTTPRequestHandler):
    server_version = "MockXRPLHS/1.0"

    def _write(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _latency(self) -> None:
        # Include occasional latency spikes to simulate testnet instability.
        if random.random() < 0.1:
            time.sleep(0.35)
        else:
            time.sleep(0.02)

    def do_GET(self) -> None:  # noqa: N802
        self._latency()
        parsed = urlparse(self.path)
        if parsed.path == "/_matrix/client/v3/did/resolve":
            account = parse_qs(parsed.query).get("account", [""])[0]
            self._write(
                200,
                {
                    "did_uri": f"did:xrpl:testnet:{account}",
                    "resolution_type": "implicit",
                    "did_document": {
                        "id": f"did:xrpl:testnet:{account}",
                        "verificationMethod": [],
                        "authentication": [],
                    },
                },
            )
            return
        self._write(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        self._latency()
        body_raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        body = json.loads(body_raw.decode("utf-8") or "{}")

        if self.path == "/_matrix/client/v3/login":
            if "session" not in body:
                self._write(401, {"session": "sess-1", "challenge": "sign-this"})
            else:
                self._write(
                    200,
                    {
                        "access_token": "tok",
                        "user_id": "@load:test",
                        "device_id": "DEV",
                    },
                )
            return
        if self.path == "/_matrix/client/v3/credential/create":
            self._write(200, {"credential_id": "cred-load", "status": "issued"})
            return
        if self.path == "/_matrix/client/v3/credential/verify":
            self._write(200, {"credential_id": "cred-load", "valid": True})
            return
        if self.path == "/_matrix/client/v3/zkp/verify":
            proof = body.get("proof", {})
            if len(json.dumps(proof)) > 64 * 1024:
                self._write(400, {"errcode": "M_INVALID_PARAM", "error": "proof too large"})
                return
            self._write(200, {"valid": True, "verified_at": int(time.time() * 1000)})
            return

        self._write(404, {"error": "not found"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18009)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"mock xrpl login server listening on {args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
