from fastapi import APIRouter
from fastapi.responses import JSONResponse

from jumpcloud_mcp.core.client import jc_client
from jumpcloud_mcp.metrics.collector import g_last_collection_ts, g_collection_duration

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "jumpcloud-api"}


@router.get("/health/detailed")
async def health_detailed():
    auth_ok = False
    try:
        data = await jc_client.list_users(limit=1)
        auth_ok = True
        total_users = data.get("totalCount") if isinstance(data, dict) else None
    except Exception as exc:
        total_users = None
        auth_error = str(exc)

    last_ts = g_last_collection_ts._value.get()  # type: ignore[attr-defined]

    return {
        "status": "ok",
        "auth_ok": auth_ok,
        "total_users": total_users,
        "last_collection_timestamp": last_ts,
    }
