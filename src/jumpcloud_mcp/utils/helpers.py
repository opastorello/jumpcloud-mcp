from __future__ import annotations

from typing import Any

import httpx


def ok(data: Any) -> dict:
    return {"ok": True, "data": data}


def err(code: str, message: str, hint: str = "") -> dict:
    return {"ok": False, "error": {"code": code, "message": message, "hint": hint}}


def classify_error(exc: Exception) -> dict:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            body = exc.response.json()
            msg = body.get("message") or body.get("error") or str(body)
        except Exception:
            msg = exc.response.text or str(exc)
        if status == 401:
            return err("UNAUTHORIZED", msg, "Check JUMPCLOUD_API_KEY in .env")
        if status == 403:
            return err("FORBIDDEN", msg, "API key lacks permission for this resource")
        if status == 404:
            return err("NOT_FOUND", msg, "Resource does not exist or ID is wrong")
        if status == 429:
            return err("RATE_LIMITED", msg, "JumpCloud API rate limit hit — wait and retry")
        return err(f"HTTP_{status}", msg)
    if isinstance(exc, httpx.TimeoutException):
        return err("TIMEOUT", str(exc), "JumpCloud API did not respond in time")
    if isinstance(exc, httpx.ConnectError):
        return err("CONNECT_ERROR", str(exc), "Could not reach console.jumpcloud.com")
    if isinstance(exc, httpx.RequestError):
        return err("NETWORK_ERROR", str(exc), "Transport or network-level error reaching JumpCloud")
    return err("UNEXPECTED", str(exc))


def select_fields(data: Any, fields: list[str] | None) -> Any:
    if not fields or not data:
        return data
    if isinstance(data, list):
        return [_pick(item, fields) for item in data]
    return _pick(data, fields)


def _pick(item: Any, fields: list[str]) -> Any:
    if not isinstance(item, dict):
        return item
    out: dict = {}
    for f in fields:
        parts = f.split(".", 1)
        if parts[0] in item:
            val = item[parts[0]]
            if len(parts) == 2 and isinstance(val, dict):
                out[parts[0]] = _pick(val, [parts[1]])
            else:
                out[parts[0]] = val
    return out
