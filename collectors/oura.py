"""Oura Ring API v2 client (OAuth2)."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from collectors import CollectorError, request_json

API_BASE = "https://api.ouraring.com"
AUTH_BASE = "https://cloud.ouraring.com"
TOKEN_URL = f"{API_BASE}/oauth/token"
AUTHORIZE_URL = f"{AUTH_BASE}/oauth/authorize"

DEFAULT_SCOPES = [
    "email",
    "personal",
    "daily",
    "heartrate",
    "workout",
    "session",
    "spo2",
]

# Daily / date-based collections
DATE_ENDPOINTS = (
    "daily_sleep",
    "daily_readiness",
    "daily_activity",
    "daily_spo2",
    "daily_stress",
    "sleep",
    "workout",
    "session",
)


class OuraClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: str | None = None,
        token_path: Path | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_path = token_path

    @classmethod
    def from_env(cls, token_path: Path | None = None) -> "OuraClient":
        client_id = os.environ.get("OURA_CLIENT_ID", "").strip()
        client_secret = os.environ.get("OURA_CLIENT_SECRET", "").strip()
        access_token = os.environ.get("OURA_ACCESS_TOKEN", "").strip()
        refresh_token = os.environ.get("OURA_REFRESH_TOKEN", "").strip() or None

        if not access_token:
            raise CollectorError(
                "OURA_ACCESS_TOKEN is missing. Run: python auth_oura.py"
            )
        if not client_id or not client_secret:
            raise CollectorError(
                "OURA_CLIENT_ID and OURA_CLIENT_SECRET are required "
                "(create an app at https://cloud.ouraring.com/oauth/applications)."
            )
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            token_path=token_path,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def refresh_access_token(self) -> dict[str, Any]:
        if not self.refresh_token:
            raise CollectorError(
                "Oura access token expired and no OURA_REFRESH_TOKEN is set. "
                "Re-run: python auth_oura.py"
            )
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        data = request_json(
            "POST",
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
        )
        self.access_token = data["access_token"]
        # Refresh tokens are single-use; always store the new one.
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        self._persist_tokens()
        return data

    def _persist_tokens(self) -> None:
        if not self.token_path:
            return
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(
            "\n".join(
                [
                    f"OURA_ACCESS_TOKEN={self.access_token}",
                    f"OURA_REFRESH_TOKEN={self.refresh_token or ''}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{API_BASE}{path}"
        try:
            return request_json("GET", url, headers=self._headers(), params=params)
        except CollectorError as exc:
            if "401" not in str(exc):
                raise
            self.refresh_access_token()
            return request_json("GET", url, headers=self._headers(), params=params)

    def get_collection(
        self,
        name: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch all pages for a date-scoped usercollection endpoint."""
        params: dict[str, Any] = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        records: list[dict[str, Any]] = []
        next_token: str | None = None

        while True:
            if next_token:
                params["next_token"] = next_token
            elif "next_token" in params:
                del params["next_token"]

            payload = self._get(f"/v2/usercollection/{name}", params=params)
            batch = payload.get("data") or []
            records.extend(batch)
            next_token = payload.get("next_token")
            if not next_token:
                break
        return records

    def personal_info(self) -> dict[str, Any]:
        return self._get("/v2/usercollection/personal_info")

    def collect(self, *, start_date: date, end_date: date) -> dict[str, Any]:
        result: dict[str, Any] = {
            "source": "oura",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "personal_info": None,
            "collections": {},
        }
        try:
            result["personal_info"] = self.personal_info()
        except CollectorError as exc:
            result["personal_info_error"] = str(exc)

        for name in DATE_ENDPOINTS:
            try:
                result["collections"][name] = self.get_collection(
                    name, start_date=start_date, end_date=end_date
                )
            except CollectorError as exc:
                result["collections"][name] = {"error": str(exc)}
        return result


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: list[str] | None = None,
) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes or DEFAULT_SCOPES),
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    return request_json(
        "POST",
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
