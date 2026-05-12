"""Prometheus metrics collector for JumpCloud.

Runs a background async loop that periodically collects JumpCloud data
and updates Prometheus gauges. Exposed via the metrics HTTP server on
METRICS_PORT (default 9090) for Grafana scraping.

Field name notes (verified against JumpCloud SDK docs):
  System:    active (bool), lastContact (ISO str), agentVersion (str), os (str)
  User:      suspended (bool), activated (bool), accountLocked (bool),
             mfa.configured (bool), enableUserPortalMultifactor (bool)
  Org:       maxSystemUsers (int), systemUsers (int) — from GET /api/organizations/{id}
  Sub:       productCode (str), displayName (str), annualPrice (num) — NO usage count in v2 spec
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

from loguru import logger
from prometheus_client import Counter, Gauge, Info

from jumpcloud_mcp.core.client import jc_client

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

# Users
g_users_total = Gauge("jumpcloud_users_total", "Total JumpCloud users")
g_users_active = Gauge("jumpcloud_users_active_total", "Non-suspended active users")
g_users_suspended = Gauge("jumpcloud_users_suspended_total", "Suspended users")
g_users_locked = Gauge("jumpcloud_users_locked_total", "Account-locked users")
g_users_mfa_configured = Gauge("jumpcloud_users_mfa_configured_total", "Users with MFA configured")
g_users_mfa_portal = Gauge("jumpcloud_users_mfa_portal_total", "Users with portal MFA enabled")
g_users_pwd_never_expires = Gauge("jumpcloud_users_pwd_never_expires_total", "Users with non-expiring passwords")
g_users_activated = Gauge("jumpcloud_users_activated_total", "Users who completed email activation")

# Systems
g_systems_total = Gauge("jumpcloud_systems_total", "Total managed systems")
g_systems_active = Gauge("jumpcloud_systems_active_total", "Systems enrolled and active in JumpCloud")
g_systems_online = Gauge(
    "jumpcloud_systems_online_total",
    "Systems seen in last 15 minutes (lastContact-based)",
)
g_systems_offline = Gauge(
    "jumpcloud_systems_offline_total",
    "Active systems NOT seen in last 15 minutes",
)
g_systems_agent_installed = Gauge("jumpcloud_systems_agent_installed_total", "Systems with agent version present")
g_systems_by_os = Gauge(
    "jumpcloud_systems_by_os_total",
    "Systems grouped by OS family (derived from os field)",
    ["os_family"],
)

# Licenses / org seats
g_org_max_users = Gauge(
    "jumpcloud_org_max_system_users",
    "Organization user seat limit (maxSystemUsers)",
    ["org_id", "org_name"],
)
g_org_current_users = Gauge(
    "jumpcloud_org_current_users",
    "Current active user count per org (systemUsers)",
    ["org_id", "org_name"],
)
g_org_seats_used_pct = Gauge(
    "jumpcloud_org_seats_used_percent",
    "Percentage of user seats in use",
    ["org_id", "org_name"],
)
g_org_systems = Gauge(
    "jumpcloud_org_systems_total",
    "Total systems managed per org",
    ["org_id", "org_name"],
)

# Subscriptions (product/plan info — API does not expose usage counts)
g_sub_price = Gauge(
    "jumpcloud_subscription_annual_price",
    "Annual price of subscription product",
    ["product_code", "product_name"],
)

# Policies
g_policies_total = Gauge("jumpcloud_policies_total", "Total policies")
g_policy_compliance_pct = Gauge(
    "jumpcloud_policy_compliance_percent",
    "Percentage of systems in compliance with policy",
    ["policy_id", "policy_name"],
)
g_policy_results_pass = Gauge(
    "jumpcloud_policy_results_pass_total",
    "Passing policy results",
    ["policy_id", "policy_name"],
)
g_policy_results_fail = Gauge(
    "jumpcloud_policy_results_fail_total",
    "Failing policy results",
    ["policy_id", "policy_name"],
)

# Groups
g_system_groups_total = Gauge("jumpcloud_system_groups_total", "Total system groups")
g_user_groups_total = Gauge("jumpcloud_user_groups_total", "Total user groups")
g_policy_groups_total = Gauge("jumpcloud_policy_groups_total", "Total policy groups")

# Applications
g_applications_total = Gauge("jumpcloud_applications_total", "Total SSO applications")
g_software_apps_total = Gauge("jumpcloud_software_apps_total", "Total MDM software apps")
g_saas_apps_total = Gauge("jumpcloud_saas_apps_total", "Total SaaS managed apps")

# Authn / conditional access
g_authn_policies_total = Gauge("jumpcloud_authn_policies_total", "Conditional access policies")

# Alerts
g_alerts_total = Gauge("jumpcloud_alerts_total", "Alerts by severity and status", ["severity", "status"])
g_alerts_open = Gauge("jumpcloud_alerts_open_total", "Open (unresolved) alerts")
g_alerts_critical = Gauge("jumpcloud_alerts_critical_total", "Critical severity alerts")

# Health monitoring
g_health_rules_total = Gauge("jumpcloud_health_monitoring_rules_total", "Health monitoring rules by status", ["rule_status"])

# Apple MDM devices
g_mdm_devices_total = Gauge("jumpcloud_mdm_apple_devices_total", "Total Apple MDM devices", ["mdm_id"])
g_mdm_devices_enrolled = Gauge("jumpcloud_mdm_apple_devices_enrolled_total", "Enrolled Apple MDM devices", ["mdm_id"])

# Directory Insights — last 24h
g_dir_events_24h = Gauge(
    "jumpcloud_directory_events_24h_total",
    "Directory events in last 24 hours by service",
    ["service"],
)
g_failed_logins_24h = Gauge("jumpcloud_failed_logins_24h_total", "Failed login events last 24h")

# Commands
g_commands_total = Gauge("jumpcloud_commands_total", "Total defined commands")

# Infra
g_directories_total = Gauge("jumpcloud_directories_total", "Total directories")
g_ldap_servers_total = Gauge("jumpcloud_ldap_servers_total", "Total LDAP servers")
g_duo_accounts_total = Gauge("jumpcloud_duo_accounts_total", "Total Duo accounts")
g_ip_lists_total = Gauge("jumpcloud_ip_lists_total", "Total IP lists")
g_roles_total = Gauge("jumpcloud_roles_total", "Total roles")
g_service_accounts_total = Gauge("jumpcloud_service_accounts_total", "Total service accounts")
g_password_policies_total = Gauge("jumpcloud_password_policies_total", "Total password policies")
g_authn_total = Gauge("jumpcloud_authn_policies_count", "Authn policies count")

# Collection meta
g_collection_duration = Gauge(
    "jumpcloud_collection_duration_seconds",
    "Seconds to collect each metric group",
    ["collector"],
)
c_collection_errors = Counter(
    "jumpcloud_collection_errors_total",
    "Collection errors per group",
    ["collector"],
)
g_last_collection_ts = Gauge(
    "jumpcloud_last_collection_timestamp_seconds",
    "Unix timestamp of last successful full collection",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ONLINE_WINDOW_MINUTES = 15


def _safe_list(data: object) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("results") or []
    return []


def _is_online(last_contact: str | None) -> bool:
    """Return True if lastContact is within the last ONLINE_WINDOW_MINUTES minutes."""
    if not last_contact:
        return False
    try:
        # JumpCloud timestamps: "2024-01-15T10:30:00.000Z" or similar
        ts = datetime.fromisoformat(last_contact.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - ts < timedelta(minutes=_ONLINE_WINDOW_MINUTES)
    except Exception:
        return False


def _derive_os_family(os_str: str | None) -> str:
    """Derive a normalised OS family label from the raw 'os' field string."""
    if not os_str:
        return "unknown"
    s = os_str.lower()
    if "mac" in s or "darwin" in s or "macos" in s:
        return "macos"
    if "windows" in s or "win" in s:
        return "windows"
    if "ubuntu" in s or "debian" in s or "linux" in s or "centos" in s or "rhel" in s \
            or "fedora" in s or "suse" in s or "arch" in s:
        return "linux"
    if "android" in s:
        return "android"
    if "ios" in s or "ipad" in s or "iphone" in s:
        return "ios"
    return "other"


async def _timed(name: str, coro):
    t0 = time.monotonic()
    try:
        result = await coro
        g_collection_duration.labels(collector=name).set(time.monotonic() - t0)
        return result
    except Exception as exc:
        c_collection_errors.labels(collector=name).inc()
        logger.warning(f"metrics/{name} error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

async def _collect_users() -> None:
    data = await _timed("users", jc_client.list_users(limit=1000))
    if data is None:
        return
    users = _safe_list(data)
    total = data.get("totalCount", len(users)) if isinstance(data, dict) else len(users)

    suspended = 0
    locked = 0
    mfa_configured = 0
    mfa_portal = 0
    pwd_never = 0
    activated = 0

    for u in users:
        if u.get("suspended"):
            suspended += 1
        if u.get("accountLocked"):
            locked += 1
        mfa_obj = u.get("mfa") or {}
        if isinstance(mfa_obj, dict) and mfa_obj.get("configured"):
            mfa_configured += 1
        if u.get("enableUserPortalMultifactor"):
            mfa_portal += 1
        if u.get("password_never_expires") or u.get("passwordNeverExpires"):
            pwd_never += 1
        if u.get("activated"):
            activated += 1

    g_users_total.set(total)
    g_users_active.set(total - suspended)
    g_users_suspended.set(suspended)
    g_users_locked.set(locked)
    g_users_mfa_configured.set(mfa_configured)
    g_users_mfa_portal.set(mfa_portal)
    g_users_pwd_never_expires.set(pwd_never)
    g_users_activated.set(activated)


async def _collect_systems() -> None:
    data = await _timed("systems", jc_client.list_systems(limit=1000))
    if data is None:
        return
    systems = _safe_list(data)
    total = data.get("totalCount", len(systems)) if isinstance(data, dict) else len(systems)

    active_count = 0
    online_count = 0
    agent_installed = 0
    os_counts: dict[str, int] = {}

    for s in systems:
        if s.get("active"):
            active_count += 1
        if _is_online(s.get("lastContact")):
            online_count += 1
        if s.get("agentVersion"):
            agent_installed += 1
        fam = _derive_os_family(s.get("os") or s.get("osFamily"))
        os_counts[fam] = os_counts.get(fam, 0) + 1

    g_systems_total.set(total)
    g_systems_active.set(active_count)
    g_systems_online.set(online_count)
    g_systems_offline.set(max(0, active_count - online_count))
    g_systems_agent_installed.set(agent_installed)
    for fam, cnt in os_counts.items():
        g_systems_by_os.labels(os_family=fam).set(cnt)


async def _collect_org_seats() -> None:
    """Collect org seat/license data from GET /api/settings.

    This endpoint is accessible to standard API keys (unlike /organizations
    which requires MSP/Provider permissions). Returns MAX_SYSTEM_USERS and ORG_ID.
    Current user count comes from the /systemusers totalCount already collected.
    """
    data = await _timed("settings", jc_client.get_settings())
    if data is None:
        return

    org_id = data.get("ORG_ID") or ""
    org_name = data.get("SUPPORT_LEVEL") or "org"
    max_users = data.get("MAX_SYSTEM_USERS") or 0

    # Current user count from the users collector (already fetched)
    cur_users_val = g_users_total._value.get()  # type: ignore[attr-defined]
    cur_users = int(cur_users_val) if cur_users_val else 0
    pct = (cur_users / max_users * 100) if max_users else 0

    g_org_max_users.labels(org_id=org_id, org_name=org_name).set(max_users)
    g_org_current_users.labels(org_id=org_id, org_name=org_name).set(cur_users)
    g_org_seats_used_pct.labels(org_id=org_id, org_name=org_name).set(pct)
    g_org_systems.labels(org_id=org_id, org_name=org_name).set(
        g_systems_total._value.get() or 0  # type: ignore[attr-defined]
    )


async def _collect_subscriptions() -> None:
    """Collect subscription product catalog from /v2/subscriptions.

    Note: the v2 subscriptions endpoint exposes pricing/plan data only.
    Usage counts (seats used) are collected via _collect_org_seats().
    """
    data = await _timed("subscriptions", jc_client.list_subscriptions())
    if data is None:
        return
    subs = data if isinstance(data, list) else []
    for sub in subs:
        code = sub.get("productCode") or "unknown"
        name = sub.get("displayName") or code
        price = sub.get("annualPrice") or 0
        g_sub_price.labels(product_code=code, product_name=name).set(price)


async def _collect_policies() -> None:
    data = await _timed("policies", jc_client.list_policies(limit=200))
    if data is None:
        return
    policies = data if isinstance(data, list) else []
    g_policies_total.set(len(policies))

    for policy in policies[:50]:
        pid = policy.get("id") or policy.get("_id", "")
        pname = policy.get("name", "unknown")
        if not pid:
            continue
        try:
            results = await jc_client.get_policy_results(pid, limit=500)
            rlist = results if isinstance(results, list) else []
            total_r = len(rlist)
            pass_r = sum(1 for r in rlist if r.get("state") == "pass" or r.get("passed"))
            fail_r = total_r - pass_r
            pct = (pass_r / total_r * 100) if total_r else 0
            g_policy_compliance_pct.labels(policy_id=pid, policy_name=pname).set(pct)
            g_policy_results_pass.labels(policy_id=pid, policy_name=pname).set(pass_r)
            g_policy_results_fail.labels(policy_id=pid, policy_name=pname).set(fail_r)
        except Exception:
            pass


async def _collect_groups() -> None:
    sg, ug, pg = await asyncio.gather(
        _timed("system_groups", jc_client.list_system_groups(limit=500)),
        _timed("user_groups", jc_client.list_user_groups(limit=500)),
        _timed("policy_groups", jc_client.list_policy_groups(limit=500)),
        return_exceptions=True,
    )
    if isinstance(sg, list): g_system_groups_total.set(len(sg))
    if isinstance(ug, list): g_user_groups_total.set(len(ug))
    if isinstance(pg, list): g_policy_groups_total.set(len(pg))


async def _collect_applications() -> None:
    apps, sw, saas = await asyncio.gather(
        _timed("applications", jc_client.list_applications(limit=200)),
        _timed("software_apps", jc_client.list_software_apps(limit=200)),
        _timed("saas_apps", jc_client.list_saas_apps(limit=200)),
        return_exceptions=True,
    )
    if isinstance(apps, list): g_applications_total.set(len(apps))
    if isinstance(sw, list): g_software_apps_total.set(len(sw))
    if isinstance(saas, list): g_saas_apps_total.set(len(saas))


async def _collect_authn_policies() -> None:
    data = await _timed("authn_policies", jc_client.list_authn_policies(limit=200))
    if isinstance(data, list):
        g_authn_policies_total.set(len(data))


async def _collect_alerts() -> None:
    data = await _timed("alerts", jc_client.list_alerts(limit=500))
    if data is None:
        return
    alerts = data if isinstance(data, list) else []
    counts: dict[tuple[str, str], int] = {}
    open_count = 0
    critical_count = 0
    for a in alerts:
        sev = (a.get("severity") or "unknown").lower()
        status = (a.get("status") or "open").lower()
        counts[(sev, status)] = counts.get((sev, status), 0) + 1
        if status == "open":
            open_count += 1
        if sev == "critical":
            critical_count += 1
    for (sev, status), cnt in counts.items():
        g_alerts_total.labels(severity=sev, status=status).set(cnt)
    g_alerts_open.set(open_count)
    g_alerts_critical.set(critical_count)


async def _collect_health_rules() -> None:
    data = await _timed("health_rules", jc_client.list_health_rules(limit=200))
    if data is None:
        return
    rules = data if isinstance(data, list) else []
    status_counts: dict[str, int] = {}
    for r in rules:
        s = (r.get("status") or "unknown").lower()
        status_counts[s] = status_counts.get(s, 0) + 1
    for s, cnt in status_counts.items():
        g_health_rules_total.labels(rule_status=s).set(cnt)


async def _collect_apple_mdm() -> None:
    duo_data = await _timed("apple_mdm_list", jc_client.list_duo_accounts())
    # Apple MDM list via GET /applemdms — use _get_v2
    try:
        mdm_list = await jc_client._get_v2("/applemdms", {"limit": 10})
        if not isinstance(mdm_list, list):
            mdm_list = (mdm_list or {}).get("results") or []
        for mdm in mdm_list:
            mdm_id = mdm.get("_id") or mdm.get("id", "")
            if not mdm_id:
                continue
            devices = await jc_client._get_v2(f"/applemdms/{mdm_id}/devices", {"limit": 1000})
            dlist = devices if isinstance(devices, list) else []
            enrolled = sum(1 for d in dlist if d.get("enrolled"))
            g_mdm_devices_total.labels(mdm_id=mdm_id).set(len(dlist))
            g_mdm_devices_enrolled.labels(mdm_id=mdm_id).set(enrolled)
    except Exception as exc:
        logger.debug(f"metrics/apple_mdm: {exc}")


async def _collect_directory_events() -> None:
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=24)).isoformat()
    services = ["directory", "ldap", "mdm", "password_manager", "radius", "sso", "systems"]
    for svc in services:
        try:
            result = await jc_client.count_events(service=[svc], start_time=start)
            count = 0
            if isinstance(result, list) and result:
                count = result[0].get("count", 0)
            elif isinstance(result, dict):
                count = result.get("count", 0)
            g_dir_events_24h.labels(service=svc).set(count)
        except Exception as exc:
            logger.debug(f"metrics/dir_events/{svc}: {exc}")

    try:
        result = await jc_client.query_events(
            service=["sso"],
            start_time=start,
            limit=1,
            search_term={"and": [{"field": "event_type", "value": "login_attempt_failed"}]},
        )
        total_failed = 0
        if isinstance(result, list):
            total_failed = len(result)
        elif isinstance(result, dict):
            total_failed = result.get("totalCount") or 0
        g_failed_logins_24h.set(total_failed)
    except Exception as exc:
        logger.debug(f"metrics/failed_logins: {exc}")


async def _collect_infra() -> None:
    results = await asyncio.gather(
        _timed("directories", jc_client.list_directories(limit=100)),
        _timed("ldap_servers", jc_client.list_ldap_servers(limit=100)),
        _timed("duo_accounts", jc_client.list_duo_accounts()),
        _timed("ip_lists", jc_client.list_iplists(limit=200)),
        _timed("roles", jc_client.list_roles(limit=200)),
        _timed("service_accounts", jc_client.list_service_accounts(limit=200)),
        _timed("password_policies", jc_client.list_password_policies(limit=100)),
        _timed("commands", jc_client.list_commands(limit=500)),
        return_exceptions=True,
    )
    dirs, ldap, duo, iplists, roles, svcacc, pwdpol, cmds = results
    if isinstance(dirs, list): g_directories_total.set(len(dirs))
    if isinstance(ldap, list): g_ldap_servers_total.set(len(ldap))
    if isinstance(duo, list): g_duo_accounts_total.set(len(duo))
    if isinstance(iplists, list): g_ip_lists_total.set(len(iplists))
    if isinstance(roles, list): g_roles_total.set(len(roles))
    if isinstance(svcacc, list): g_service_accounts_total.set(len(svcacc))
    if isinstance(pwdpol, list): g_password_policies_total.set(len(pwdpol))
    if isinstance(cmds, dict):
        g_commands_total.set(cmds.get("totalCount") or len(cmds.get("results") or []))


# ---------------------------------------------------------------------------
# Main collection loop
# ---------------------------------------------------------------------------

async def collect_once() -> None:
    logger.info("metrics: starting collection run")
    t0 = time.monotonic()

    # Fast parallel collectors
    await asyncio.gather(
        _collect_users(),
        _collect_systems(),
        _collect_groups(),
        _collect_applications(),
        _collect_authn_policies(),
        _collect_alerts(),
        _collect_health_rules(),
        _collect_subscriptions(),
        _collect_infra(),
        return_exceptions=True,
    )

    # Sequential — each makes multiple API calls per item
    await _collect_org_seats()
    await _collect_policies()
    await _collect_directory_events()
    await _collect_apple_mdm()

    g_last_collection_ts.set(time.time())
    logger.info(f"metrics: collection done in {time.monotonic() - t0:.1f}s")


async def run_collection_loop(interval_seconds: int = 300) -> None:
    while True:
        try:
            await collect_once()
        except Exception as exc:
            logger.error(f"metrics: collection loop error: {exc}")
        await asyncio.sleep(interval_seconds)
