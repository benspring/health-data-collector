"""Eight Sleep unofficial client API (read-only sleep trends)."""

from __future__ import annotations

import os
import time
from datetime import date
from typing import Any

from collectors import CollectorError, request_json

AUTH_URL = "https://auth-api.8slp.net/v1/tokens"
CLIENT_API = "https://client-api.8slp.net/v1"

# Public mobile-app OAuth constants used by community clients (pyEight / HA).
# Not personal secrets; overridable via env if Eight rotates them.
DEFAULT_CLIENT_ID = "0894c7f33bb94800a03f1f4df13a4f38"
DEFAULT_CLIENT_SECRET = (
    "f0954a3ed5763ba3d06834c73731a32f15f168f47d4f164751275def86db0c76"
)

USER_AGENT = "okhttp/4.9.3"


class EightSleepClient:
    """Pull sleep trends for your own Eight Sleep account.

    Eight Sleep does not publish an official developer API. This client talks
    to the same private endpoints the mobile app uses (community-documented).
    Endpoints can change without notice — use only with your own credentials.
    """

    def __init__(
        self,
        *,
        email: str,
        password: str,
        timezone: str,
        client_id: str = DEFAULT_CLIENT_ID,
        client_secret: str = DEFAULT_CLIENT_SECRET,
    ) -> None:
        self.email = email
        self.password = password
        self.timezone = timezone
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._user_id: str | None = None

    @classmethod
    def from_env(cls) -> "EightSleepClient":
        email = os.environ.get("EIGHT_SLEEP_EMAIL", "").strip()
        password = os.environ.get("EIGHT_SLEEP_PASSWORD", "").strip()
        timezone = os.environ.get("EIGHT_SLEEP_TIMEZONE", "UTC").strip() or "UTC"
        client_id = (
            os.environ.get("EIGHT_SLEEP_CLIENT_ID", "").strip() or DEFAULT_CLIENT_ID
        )
        client_secret = (
            os.environ.get("EIGHT_SLEEP_CLIENT_SECRET", "").strip()
            or DEFAULT_CLIENT_SECRET
        )
        if not email or not password:
            raise CollectorError(
                "EIGHT_SLEEP_EMAIL and EIGHT_SLEEP_PASSWORD are required."
            )
        return cls(
            email=email,
            password=password,
            timezone=timezone,
            client_id=client_id,
            client_secret=client_secret,
        )

    def authenticate(self) -> None:
        data = request_json(
            "POST",
            AUTH_URL,
            headers={
                "content-type": "application/json",
                "user-agent": USER_AGENT,
                "accept": "application/json",
            },
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "password",
                "username": self.email,
                "password": self.password,
            },
        )
        self._access_token = data["access_token"]
        self._expires_at = time.time() + float(data.get("expires_in", 3600))
        self._user_id = data.get("userId")

    def _ensure_auth(self) -> None:
        if not self._access_token or time.time() + 120 >= self._expires_at:
            self.authenticate()

    def _headers(self) -> dict[str, str]:
        self._ensure_auth()
        assert self._access_token
        return {
            "authorization": f"Bearer {self._access_token}",
            "content-type": "application/json",
            "user-agent": USER_AGENT,
            "accept": "application/json",
            "accept-encoding": "gzip",
        }

    def get_me(self) -> dict[str, Any]:
        return request_json("GET", f"{CLIENT_API}/users/me", headers=self._headers())

    @property
    def user_id(self) -> str:
        if self._user_id:
            return self._user_id
        me = self.get_me()
        user = me.get("user") if isinstance(me.get("user"), dict) else me
        user_id = user.get("userId") or user.get("id") or me.get("userId")
        if not user_id:
            raise CollectorError("Could not resolve Eight Sleep userId from /users/me")
        self._user_id = str(user_id)
        return self._user_id

    def get_trends(
        self,
        *,
        start_date: date,
        end_date: date,
        include_all_sessions: bool = True,
    ) -> dict[str, Any]:
        # API allows only one of include-main / include-all-sessions.
        params = {
            "tz": self.timezone,
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "model-version": "v2",
        }
        if include_all_sessions:
            params["include-all-sessions"] = "true"
        else:
            params["include-main"] = "true"
        return request_json(
            "GET",
            f"{CLIENT_API}/users/{self.user_id}/trends",
            headers=self._headers(),
            params=params,
        )

    def collect(self, *, start_date: date, end_date: date) -> dict[str, Any]:
        me = self.get_me()
        trends = self.get_trends(start_date=start_date, end_date=end_date)
        return {
            "source": "eight_sleep",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": self.timezone,
            "user_id": self.user_id,
            "me": me,
            "trends": trends,
        }
