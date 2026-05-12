import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from jumpcloud_mcp.core.client import jc_client
from jumpcloud_mcp.metrics import collector as col

router = APIRouter(prefix="/v1")


@router.get("/metrics/summary")
async def metrics_summary():
    last_ts = col.g_last_collection_ts._value.get()  # type: ignore[attr-defined]
    age = time.time() - last_ts if last_ts else None

    return {
        "users": {
            "total": _g(col.g_users_total),
            "active": _g(col.g_users_active),
            "suspended": _g(col.g_users_suspended),
            "locked": _g(col.g_users_locked),
            "mfa_configured": _g(col.g_users_mfa_configured),
        },
        "systems": {
            "total": _g(col.g_systems_total),
            "active": _g(col.g_systems_active),
            "online": _g(col.g_systems_online),
            "offline": _g(col.g_systems_offline),
            "agent_installed": _g(col.g_systems_agent_installed),
        },
        "alerts": {
            "open": _g(col.g_alerts_open),
            "critical": _g(col.g_alerts_critical),
        },
        "policies": {
            "total": _g(col.g_policies_total),
        },
        "last_collection_age_seconds": age,
    }


@router.get("/fleet/health")
async def fleet_health():
    total = _g(col.g_systems_total) or 1
    active = _g(col.g_systems_active) or 0
    online = _g(col.g_systems_online) or 0
    mfa_ok = _g(col.g_users_mfa_configured) or 0
    users = _g(col.g_users_total) or 1

    online_score = (online / active * 100) if active else 0
    mfa_score = (mfa_ok / users * 100) if users else 0

    return {
        "online_percent": round(online_score, 1),
        "mfa_coverage_percent": round(mfa_score, 1),
        "active_systems": active,
        "total_systems": total,
        "open_alerts": _g(col.g_alerts_open),
        "critical_alerts": _g(col.g_alerts_critical),
        "policies_total": _g(col.g_policies_total),
    }


@router.get("/security/posture")
async def security_posture():
    return {
        "users_without_mfa": _g(col.g_users_total) - _g(col.g_users_mfa_configured),
        "users_suspended": _g(col.g_users_suspended),
        "users_locked": _g(col.g_users_locked),
        "systems_offline": _g(col.g_systems_offline),
        "alerts_open": _g(col.g_alerts_open),
        "alerts_critical": _g(col.g_alerts_critical),
        "password_policies": _g(col.g_password_policies_total),
        "authn_policies": _g(col.g_authn_policies_total),
        "ip_lists": _g(col.g_ip_lists_total),
    }


@router.get("/licenses")
async def licenses():
    seats: list[dict] = []
    for labels, gauge in col.g_org_max_users._metrics.items():  # type: ignore[attr-defined]
        label_dict = dict(zip(col.g_org_max_users._labelnames, labels))
        org_id = label_dict.get("org_id", "")
        org_name = label_dict.get("org_name", "")
        max_u = gauge._value.get()
        cur_u = _g_labels(col.g_org_current_users, labels)
        pct = _g_labels(col.g_org_seats_used_pct, labels)
        sys_count = _g_labels(col.g_org_systems, labels)
        seats.append({
            "org_id": org_id,
            "org_name": org_name,
            "max_users": int(max_u),
            "current_users": int(cur_u),
            "seats_used_percent": round(pct, 1),
            "systems": int(sys_count),
        })
    return {"count": len(seats), "orgs": seats}


def _g(gauge) -> float:
    try:
        return gauge._value.get()  # type: ignore[attr-defined]
    except Exception:
        return 0.0


def _g_labels(gauge, labels) -> float:
    try:
        return gauge._metrics.get(labels, type("_", (), {"_value": type("_", (), {"get": lambda s: 0.0})()})())._value.get()
    except Exception:
        return 0.0
