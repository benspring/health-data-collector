"""Shared HTTP helpers for data collectors."""

from __future__ import annotations

from typing import Any

import requests


class CollectorError(RuntimeError):
    """Raised when an upstream API call fails."""


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> Any:
    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json,
        data=data,
        timeout=timeout,
    )
    if response.status_code >= 400:
        detail = response.text[:500]
        raise CollectorError(f"{method} {url} -> {response.status_code}: {detail}")
    if not response.content:
        return None
    return response.json()
