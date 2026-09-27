#!/usr/bin/env python3
"""One-time Oura OAuth2 setup: opens browser, captures tokens, updates .env."""

from __future__ import annotations

import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from collectors.oura import build_authorize_url, exchange_code

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


def _update_env(values: dict[str, str]) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    remaining = dict(values)
    updated: list[str] = []

    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            updated.append(line)
            continue
        key, _, _ = line.partition("=")
        if key in remaining:
            updated.append(f"{key}={remaining.pop(key)}")
        else:
            updated.append(line)

    if remaining:
        if updated and updated[-1] != "":
            updated.append("")
        for key, value in remaining.items():
            updated.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    load_dotenv(ENV_PATH)

    client_id = os.environ.get("OURA_CLIENT_ID", "").strip()
    client_secret = os.environ.get("OURA_CLIENT_SECRET", "").strip()
    redirect_uri = (
        os.environ.get("OURA_REDIRECT_URI", "").strip()
        or "http://localhost:8787/callback"
    )

    if not client_id or not client_secret:
        print(
            "Set OURA_CLIENT_ID and OURA_CLIENT_SECRET in .env first.\n"
            "Create an application at:\n"
            "  https://cloud.ouraring.com/oauth/applications\n"
            f"Use redirect URI: {redirect_uri}",
            file=sys.stderr,
        )
        return 1

    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8787
    path = parsed.path or "/callback"
    state = secrets.token_urlsafe(24)
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            req = urlparse(self.path)
            if req.path != path:
                self.send_response(404)
                self.end_headers()
                return
            qs = parse_qs(req.query)
            if qs.get("error"):
                result["error"] = qs["error"][0]
            else:
                result["code"] = qs.get("code", [""])[0]
                result["returned_state"] = qs.get("state", [""])[0]
            body = (
                b"<html><body><h1>Oura auth complete</h1>"
                b"<p>You can close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    auth_url = build_authorize_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
    )
    print("Opening browser for Oura authorization…")
    print(auth_url)
    webbrowser.open(auth_url)

    server = HTTPServer((host, port), Handler)
    print(f"Listening for callback on {redirect_uri}")
    server.serve_forever()

    if result.get("error"):
        print(f"Authorization failed: {result['error']}", file=sys.stderr)
        return 1
    if result.get("returned_state") != state:
        print("State mismatch — aborting.", file=sys.stderr)
        return 1
    code = result.get("code")
    if not code:
        print("No authorization code received.", file=sys.stderr)
        return 1

    tokens = exchange_code(
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
    )
    _update_env(
        {
            "OURA_ACCESS_TOKEN": tokens["access_token"],
            "OURA_REFRESH_TOKEN": tokens.get("refresh_token", ""),
            "OURA_REDIRECT_URI": redirect_uri,
        }
    )
    # Also keep a sidecar for auto-refresh without rewriting comments in .env
    token_file = ROOT / "tokens" / "oura.env"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(
        "\n".join(
            [
                f"OURA_ACCESS_TOKEN={tokens['access_token']}",
                f"OURA_REFRESH_TOKEN={tokens.get('refresh_token', '')}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("Oura tokens saved to .env and tokens/oura.env")
    print("You can now run: python collect.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
