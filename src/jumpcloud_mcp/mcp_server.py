import json
import sys

from fastmcp import FastMCP
from loguru import logger

from jumpcloud_mcp.core.client import jc_client
from jumpcloud_mcp.core.config import settings
from jumpcloud_mcp.utils.helpers import classify_error, err, ok, select_fields

mcp = FastMCP("JumpCloud MCP")


def _json(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


def _require_write() -> str | None:
    """Return an error JSON string if writes are disabled, else None."""
    if not settings.ALLOW_WRITE:
        return _json(err(
            "WRITE_DISABLED",
            "Write operations are disabled.",
            "Set ALLOW_WRITE=true in .env to enable mutations.",
        ))
    return None


# =============================================================================
# AUTH / ORG / LICENSES
# =============================================================================


@mcp.tool()
async def auth_status() -> str:
    """Check if the JumpCloud API key is valid. Returns org connectivity status and user count."""
    try:
        data = await jc_client.list_users(limit=1)
        count = data.get("totalCount") if isinstance(data, dict) else None
        return _json(ok({"status": "ok", "totalUsers": count}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_org_summary() -> str:
    """Get organization summary: admin links, user/system counts, billing info.

    Calls /api/organizations to get org-level metadata including total user and system counts.
    """
    try:
        data = await jc_client.list_organizations(limit=10)
        orgs = data.get("results") or [] if isinstance(data, dict) else data if isinstance(data, list) else []
        return _json(ok({"count": len(orgs), "organizations": orgs}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_subscriptions() -> str:
    """Get all JumpCloud product subscriptions with license counts and limits.

    Returns product codes, quantities (used vs. total), and billing plan details.
    This is the primary tool for license management and capacity planning.
    """
    try:
        data = await jc_client.list_subscriptions()
        subs = data if isinstance(data, list) else []
        return _json(ok({"count": len(subs), "subscriptions": subs}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_subscription_detail(product_code: str) -> str:
    """Get details and components of a specific product subscription by product code.

    Product codes examples: 'platform', 'ldap', 'mdm', 'radius', 'sso', 'jumpcloud_go'
    """
    try:
        detail = await jc_client.get_subscription(product_code)
        components = await jc_client.get_subscription_components(product_code)
        return _json(ok({"detail": detail, "components": components}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# USERS
# =============================================================================


@mcp.tool()
async def list_users(
    limit: int = 100,
    skip: int = 0,
    search: str | None = None,
    filter: str | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
    not_suspended: bool | None = None,
    mfa_enabled: bool | None = None,
    password_expired: bool | None = None,
    locked: bool | None = None,
) -> str:
    """List JumpCloud directory users (systemusers).

    Client-side filters:
      - not_suspended: True keeps non-suspended users; False keeps only suspended
      - mfa_enabled: True/False — based on mfa.configured field
      - password_expired: True/False
      - locked: True/False — account lockout state
    Server-side filter: e.g. 'suspended:true' or 'email:user@company.com'
    Use `fields=["_id","email","displayname","suspended","mfa","account_locked"]` to reduce tokens.
    """
    try:
        data = await jc_client.list_users(limit=limit, skip=skip, search=search,
                                          filter=filter, sort=sort)
        results = data.get("results") or [] if isinstance(data, dict) else []
        total = data.get("totalCount") if isinstance(data, dict) else None

        if not_suspended is not None:
            results = [u for u in results if bool(u.get("suspended")) != not_suspended]
        if mfa_enabled is not None:
            results = [u for u in results
                       if bool((u.get("mfa") or {}).get("configured")) == mfa_enabled]
        if password_expired is not None:
            results = [u for u in results
                       if bool(u.get("password_expired")) == password_expired]
        if locked is not None:
            results = [u for u in results if bool(u.get("account_locked")) == locked]

        results = select_fields(results, fields)
        return _json(ok({"totalCount": total, "count": len(results), "users": results}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_user(user_id: str, fields: list[str] | None = None) -> str:
    """Get full details of a JumpCloud user by ID."""
    try:
        data = await jc_client.get_user(user_id)
        return _json(ok(select_fields(data, fields)))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def search_users_by_email(email_substring: str, limit: int = 50) -> str:
    """Search users by email substring. Projects key fields to reduce tokens."""
    return await list_users(
        search=email_substring,
        limit=limit,
        fields=["_id", "email", "displayname", "activated", "suspended", "mfa",
                "account_locked", "password_expired", "created"],
    )


@mcp.tool()
async def get_user_systems(user_id: str, limit: int = 100) -> str:
    """Get systems that a user has access to (via group or direct bind)."""
    try:
        data = await jc_client.get_user_systems(user_id, limit=limit)
        return _json(ok({"userId": user_id, "systems": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_user_system_groups(user_id: str, limit: int = 100) -> str:
    """Get system groups that a user belongs to."""
    try:
        data = await jc_client.get_user_system_groups(user_id, limit=limit)
        return _json(ok({"userId": user_id, "systemGroups": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# SYSTEMS
# =============================================================================


@mcp.tool()
async def list_systems(
    limit: int = 100,
    skip: int = 0,
    search: str | None = None,
    filter: str | None = None,
    fields: list[str] | None = None,
    os_family: str | None = None,
    active: bool | None = None,
) -> str:
    """List JumpCloud managed systems (endpoints).

    Client-side filters:
      - os_family: e.g. "Windows", "Mac OS X", "Linux" (case-insensitive substring on `os` field)
      - active: True/False — filter by last-contact active state
    Server-side filter: e.g. 'os:Windows Server 2022' or 'active:true'
    Use `fields=["_id","displayName","os","hostname","active","lastContact","agentVersion"]`.
    """
    try:
        data = await jc_client.list_systems(limit=limit, skip=skip, search=search, filter=filter)
        results = data.get("results") or [] if isinstance(data, dict) else []
        total = data.get("totalCount") if isinstance(data, dict) else None

        if os_family is not None:
            needle = os_family.lower()
            results = [s for s in results if needle in (s.get("os") or "").lower()]
        if active is not None:
            results = [s for s in results if bool(s.get("active")) == active]

        results = select_fields(results, fields)
        return _json(ok({"totalCount": total, "count": len(results), "systems": results}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system(system_id: str, fields: list[str] | None = None) -> str:
    """Get full details of a JumpCloud system by ID."""
    try:
        data = await jc_client.get_system(system_id)
        return _json(ok(select_fields(data, fields)))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def search_systems_by_hostname(hostname_substring: str, limit: int = 50) -> str:
    """Search systems by hostname substring. Projects key fields."""
    return await list_systems(
        search=hostname_substring,
        limit=limit,
        fields=["_id", "displayName", "hostname", "os", "osVersionDetail", "active",
                "lastContact", "agentVersion", "templateName"],
    )


@mcp.tool()
async def get_system_users(system_id: str, limit: int = 100) -> str:
    """Get users bound to a system."""
    try:
        data = await jc_client.get_system_users(system_id, limit=limit)
        return _json(ok({"systemId": system_id, "users": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_policies(system_id: str, limit: int = 100) -> str:
    """Get all policies applied to a specific system."""
    try:
        data = await jc_client.get_system_policies(system_id, limit=limit)
        return _json(ok({"systemId": system_id, "policies": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_policy_statuses(system_id: str, limit: int = 100) -> str:
    """Get policy compliance status per policy for a specific system (pass/fail per policy)."""
    try:
        data = await jc_client.get_system_policy_statuses(system_id, limit=limit)
        statuses = data if isinstance(data, list) else []
        passed = sum(1 for s in statuses if s.get("success") is True)
        return _json(ok({
            "systemId": system_id,
            "total": len(statuses),
            "passed": passed,
            "failed": len(statuses) - passed,
            "statuses": statuses,
        }))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_aggregated_policy_stats(system_id: str) -> str:
    """Get aggregated policy compliance summary for a system (total pass/fail counts per group)."""
    try:
        data = await jc_client.get_system_aggregated_policy_stats(system_id)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_software_app_statuses(system_id: str, limit: int = 100) -> str:
    """Get MDM software app installation status for a specific system."""
    try:
        data = await jc_client.get_system_software_app_statuses(system_id, limit=limit)
        return _json(ok({"systemId": system_id, "appStatuses": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_fde_key(system_id: str) -> str:
    """Get the FileVault/BitLocker FDE recovery key for a system.

    WARNING: This returns the actual recovery key — use only when needed for support/recovery.
    Requires 'Systems Read' admin role minimum.
    """
    try:
        data = await jc_client.get_system_fde_key(system_id)
        return _json(ok({"systemId": system_id, "fdeKey": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# SYSTEM GROUPS
# =============================================================================


@mcp.tool()
async def list_system_groups(
    limit: int = 100,
    skip: int = 0,
    fields: list[str] | None = None,
    name_contains: str | None = None,
) -> str:
    """List system groups (device collections) in the org."""
    try:
        data = await jc_client.list_system_groups(limit=limit, skip=skip)
        groups = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            groups = [g for g in groups if needle in (g.get("name") or "").lower()]
        groups = select_fields(groups, fields)
        return _json(ok({"count": len(groups), "systemGroups": groups}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_group(group_id: str) -> str:
    """Get details of a specific system group by ID."""
    try:
        return _json(ok(await jc_client.get_system_group(group_id)))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_group_members(group_id: str, limit: int = 100, skip: int = 0) -> str:
    """Get systems that are members of a system group."""
    try:
        data = await jc_client.get_system_group_members(group_id, limit=limit, skip=skip)
        return _json(ok({"groupId": group_id, "members": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_group_users(group_id: str, limit: int = 100) -> str:
    """Get users that have access to systems in a system group."""
    try:
        data = await jc_client.get_system_group_users(group_id, limit=limit)
        return _json(ok({"groupId": group_id, "users": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# USER GROUPS
# =============================================================================


@mcp.tool()
async def list_user_groups(
    limit: int = 100,
    skip: int = 0,
    fields: list[str] | None = None,
    name_contains: str | None = None,
) -> str:
    """List user groups in the org."""
    try:
        data = await jc_client.list_user_groups(limit=limit, skip=skip)
        groups = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            groups = [g for g in groups if needle in (g.get("name") or "").lower()]
        groups = select_fields(groups, fields)
        return _json(ok({"count": len(groups), "userGroups": groups}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_user_group(group_id: str) -> str:
    """Get details of a specific user group by ID."""
    try:
        return _json(ok(await jc_client.get_user_group(group_id)))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_user_group_members(group_id: str, limit: int = 100, skip: int = 0) -> str:
    """Get users that are members of a user group."""
    try:
        data = await jc_client.get_user_group_members(group_id, limit=limit, skip=skip)
        return _json(ok({"groupId": group_id, "members": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_user_group_systems(group_id: str, limit: int = 100) -> str:
    """Get systems accessible to members of a user group."""
    try:
        data = await jc_client.get_user_group_systems(group_id, limit=limit)
        return _json(ok({"groupId": group_id, "systems": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def list_all_groups(
    limit: int = 200,
    skip: int = 0,
    group_type: str | None = None,
) -> str:
    """List ALL groups (system + user + policy groups combined) from a single endpoint.

    Optional client-side filter:
      - group_type: 'system_group', 'user_group', 'policy_group' (case-insensitive)
    """
    try:
        data = await jc_client.list_all_groups(limit=limit, skip=skip)
        groups = data if isinstance(data, list) else []
        if group_type:
            t_lower = group_type.lower()
            groups = [g for g in groups if (g.get("type") or "").lower() == t_lower]
        return _json(ok({"count": len(groups), "groups": groups}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# POLICIES
# =============================================================================


@mcp.tool()
async def list_policies(
    limit: int = 100,
    skip: int = 0,
    fields: list[str] | None = None,
    template_name: str | None = None,
    name_contains: str | None = None,
) -> str:
    """List MDM/configuration policies deployed in the org.

    Client-side filters:
      - template_name: substring match on policy template name
      - name_contains: substring match on policy name
    """
    try:
        data = await jc_client.list_policies(limit=limit, skip=skip)
        policies = data if isinstance(data, list) else []
        if template_name:
            t_lower = template_name.lower()
            policies = [p for p in policies
                        if t_lower in (p.get("template", {}).get("name") or "").lower()]
        if name_contains:
            needle = name_contains.lower()
            policies = [p for p in policies if needle in (p.get("name") or "").lower()]
        policies = select_fields(policies, fields)
        return _json(ok({"count": len(policies), "policies": policies}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_policy(policy_id: str) -> str:
    """Get full configuration of a specific policy including template values."""
    try:
        return _json(ok(await jc_client.get_policy(policy_id)))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_policy_statuses(policy_id: str, limit: int = 100) -> str:
    """Get per-system compliance status for a policy (pass/fail per device)."""
    try:
        data = await jc_client.get_policy_statuses(policy_id, limit=limit)
        statuses = data if isinstance(data, list) else []
        passed = sum(1 for s in statuses if s.get("success") is True)
        return _json(ok({
            "policyId": policy_id,
            "total": len(statuses),
            "passed": passed,
            "failed": len(statuses) - passed,
            "statuses": statuses,
        }))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_policy_results(policy_id: str, limit: int = 100) -> str:
    """Get raw policy result entries for a specific policy."""
    try:
        data = await jc_client.get_policy_results(policy_id, limit=limit)
        return _json(ok({"policyId": policy_id, "results": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_policy_systems(policy_id: str, limit: int = 100) -> str:
    """Get systems that a policy is applied to."""
    try:
        data = await jc_client.get_policy_systems(policy_id, limit=limit)
        return _json(ok({"policyId": policy_id, "systems": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# POLICY GROUPS
# =============================================================================


@mcp.tool()
async def list_policy_groups(
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
) -> str:
    """List policy groups (bundles of policies deployed together to system groups)."""
    try:
        data = await jc_client.list_policy_groups(limit=limit, skip=skip)
        groups = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            groups = [g for g in groups if needle in (g.get("name") or "").lower()]
        return _json(ok({"count": len(groups), "policyGroups": groups}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_policy_group_systems(group_id: str, limit: int = 100) -> str:
    """Get systems that have a policy group applied."""
    try:
        data = await jc_client.get_policy_group_systems(group_id, limit=limit)
        return _json(ok({"groupId": group_id, "systems": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_policy_group_members(group_id: str, limit: int = 100) -> str:
    """Get policies that belong to a policy group."""
    try:
        data = await jc_client.get_policy_group_members(group_id, limit=limit)
        return _json(ok({"groupId": group_id, "policies": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# POLICY TEMPLATES
# =============================================================================


@mcp.tool()
async def list_policy_templates(limit: int = 100) -> str:
    """List all available JumpCloud policy templates (built-in policy types).

    Templates define what a policy can configure: disk_encryption, password_policy,
    screen_lock, firewall, software_update, etc.
    """
    try:
        data = await jc_client.list_policy_templates(limit=limit)
        templates = data if isinstance(data, list) else []
        return _json(ok({"count": len(templates), "policyTemplates": templates}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_policy_template(template_id: str) -> str:
    """Get full schema and configuration options for a specific policy template."""
    try:
        return _json(ok(await jc_client.get_policy_template(template_id)))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# CONDITIONAL ACCESS (AUTHN POLICIES)
# =============================================================================


@mcp.tool()
async def list_authn_policies(
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
    disabled: bool | None = None,
) -> str:
    """List authentication policies (conditional access rules).

    Controls when/how users must authenticate — MFA requirements, IP restrictions,
    device trust, time-based access, etc.

    Client-side filters:
      - name_contains: substring match on policy name
      - disabled: True keeps only disabled policies; False keeps only active ones
    """
    try:
        data = await jc_client.list_authn_policies(limit=limit, skip=skip)
        policies = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            policies = [p for p in policies if needle in (p.get("name") or "").lower()]
        if disabled is not None:
            policies = [p for p in policies if bool(p.get("disabled")) == disabled]
        return _json(ok({"count": len(policies), "authnPolicies": policies}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_authn_policy(policy_id: str) -> str:
    """Get full configuration of a specific conditional access (authn) policy."""
    try:
        return _json(ok(await jc_client.get_authn_policy(policy_id)))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# APPLICATIONS (SSO)
# =============================================================================


@mcp.tool()
async def list_applications(
    limit: int = 100,
    skip: int = 0,
    fields: list[str] | None = None,
    name_contains: str | None = None,
    sso_type: str | None = None,
) -> str:
    """List SSO applications configured in JumpCloud.

    Client-side filters:
      - name_contains: substring match on app name
      - sso_type: e.g. 'saml', 'oidc' (case-insensitive)
    """
    try:
        data = await jc_client.list_applications(limit=limit, skip=skip)
        apps = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            apps = [a for a in apps if needle in (a.get("displayLabel") or a.get("name") or "").lower()]
        if sso_type:
            t_lower = sso_type.lower()
            apps = [a for a in apps if t_lower in (a.get("ssoType") or "").lower()]
        apps = select_fields(apps, fields)
        return _json(ok({"count": len(apps), "applications": apps}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_application(app_id: str) -> str:
    """Get full SSO application configuration."""
    try:
        return _json(ok(await jc_client.get_application(app_id)))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_application_users(app_id: str, limit: int = 100) -> str:
    """Get users who have access to a specific SSO application."""
    try:
        data = await jc_client.get_application_users(app_id, limit=limit)
        return _json(ok({"appId": app_id, "users": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# SOFTWARE APPS (MDM DEPLOYMENT)
# =============================================================================


@mcp.tool()
async def list_software_apps(
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
) -> str:
    """List MDM software apps configured for deployment (macOS/Windows app management).

    These are apps pushed via JumpCloud MDM — different from SSO applications.
    Client-side filter: name_contains — substring match on app name.
    """
    try:
        data = await jc_client.list_software_apps(limit=limit, skip=skip)
        apps = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            apps = [a for a in apps if needle in (a.get("displayName") or a.get("name") or "").lower()]
        return _json(ok({"count": len(apps), "softwareApps": apps}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_software_app(app_id: str) -> str:
    """Get full configuration of a specific MDM software app deployment."""
    try:
        return _json(ok(await jc_client.get_software_app(app_id)))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_software_app_statuses(
    app_id: str,
    limit: int = 100,
    skip: int = 0,
    status_filter: str | None = None,
) -> str:
    """Get per-system installation status for a software app deployment.

    Client-side filter status_filter: 'installed', 'pending', 'failed' (case-insensitive).
    """
    try:
        data = await jc_client.get_software_app_statuses(app_id, limit=limit, skip=skip)
        statuses = data if isinstance(data, list) else []
        if status_filter:
            s_lower = status_filter.lower()
            statuses = [s for s in statuses if (s.get("status") or "").lower() == s_lower]
        installed = sum(1 for s in statuses if (s.get("status") or "").lower() == "installed")
        failed = sum(1 for s in statuses if (s.get("status") or "").lower() == "failed")
        pending = len(statuses) - installed - failed
        return _json(ok({
            "appId": app_id,
            "total": len(statuses),
            "installed": installed,
            "failed": failed,
            "pending": pending,
            "statuses": statuses,
        }))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_software_app_systems(app_id: str, limit: int = 100) -> str:
    """Get systems targeted by a software app deployment."""
    try:
        data = await jc_client.get_software_app_systems(app_id, limit=limit)
        return _json(ok({"appId": app_id, "systems": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# SAAS MANAGEMENT
# =============================================================================


@mcp.tool()
async def list_saas_apps(limit: int = 100, skip: int = 0, name_contains: str | None = None) -> str:
    """List SaaS applications discovered/managed by JumpCloud SaaS Management.

    Shows actual SaaS usage data (Slack, Salesforce, etc.) discovered via browser extension
    or integrations. Different from SSO applications.
    """
    try:
        data = await jc_client.list_saas_apps(limit=limit, skip=skip)
        apps = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            apps = [a for a in apps if needle in (a.get("displayName") or a.get("name") or "").lower()]
        return _json(ok({"count": len(apps), "saasApps": apps}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_saas_app_usage(app_id: str) -> str:
    """Get usage statistics for a specific SaaS application (active users, login frequency)."""
    try:
        data = await jc_client.get_saas_app_usage(app_id)
        return _json(ok({"appId": app_id, "usage": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def list_saas_app_licenses(limit: int = 100) -> str:
    """List SaaS application license allocations and usage counts.

    Shows licensed vs. used seats per SaaS application — key for license optimization.
    """
    try:
        data = await jc_client.list_saas_app_licenses(limit=limit)
        licenses = data if isinstance(data, list) else []
        return _json(ok({"count": len(licenses), "licenses": licenses}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_saas_app_accounts(app_id: str, limit: int = 100) -> str:
    """Get user accounts for a specific SaaS application."""
    try:
        data = await jc_client.get_saas_app_accounts(app_id, limit=limit)
        return _json(ok({"appId": app_id, "accounts": data,
                         "count": len(data) if isinstance(data, list) else 0}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# IP LISTS
# =============================================================================


@mcp.tool()
async def list_iplists(limit: int = 100, skip: int = 0, name_contains: str | None = None) -> str:
    """List IP allowlists/denylists used in conditional access policies.

    These IP lists are referenced by authn policies to allow/block access by source IP.
    """
    try:
        data = await jc_client.list_iplists(limit=limit, skip=skip)
        lists = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            lists = [l for l in lists if needle in (l.get("name") or "").lower()]
        return _json(ok({"count": len(lists), "ipLists": lists}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_iplist(list_id: str) -> str:
    """Get a specific IP list including all IP ranges/CIDRs."""
    try:
        return _json(ok(await jc_client.get_iplist(list_id)))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# ROLES
# =============================================================================


@mcp.tool()
async def list_roles(
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
) -> str:
    """List admin roles defined in the JumpCloud organization.

    Roles control which parts of the JumpCloud console administrators can access.
    """
    try:
        data = await jc_client.list_roles(limit=limit, skip=skip)
        roles = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            roles = [r for r in roles if needle in (r.get("name") or "").lower()]
        return _json(ok({"count": len(roles), "roles": roles}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_role(role_id: str) -> str:
    """Get full details of a specific admin role including assigned permissions."""
    try:
        return _json(ok(await jc_client.get_role(role_id)))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# SERVICE ACCOUNTS
# =============================================================================


@mcp.tool()
async def list_service_accounts(limit: int = 100) -> str:
    """List service accounts (API-only accounts used by integrations and automations)."""
    try:
        data = await jc_client.list_service_accounts(limit=limit)
        accounts = data if isinstance(data, list) else []
        return _json(ok({"count": len(accounts), "serviceAccounts": accounts}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# COMMANDS
# =============================================================================


@mcp.tool()
async def list_commands(
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
    os_filter: str | None = None,
) -> str:
    """List remote commands configured in JumpCloud (MDM command library).

    Client-side filters:
      - name_contains: substring match on command name
      - os_filter: 'linux', 'windows', 'mac' (case-insensitive substring on `commandType`)
    """
    try:
        data = await jc_client.list_commands(limit=limit, skip=skip)
        commands = data.get("results") or [] if isinstance(data, dict) else []
        if name_contains:
            needle = name_contains.lower()
            commands = [c for c in commands if needle in (c.get("name") or "").lower()]
        if os_filter:
            os_lower = os_filter.lower()
            commands = [c for c in commands
                        if os_lower in (c.get("commandType") or "").lower()]
        total = data.get("totalCount") if isinstance(data, dict) else None
        return _json(ok({"totalCount": total, "count": len(commands), "commands": commands}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_command(command_id: str) -> str:
    """Get full configuration of a specific JumpCloud command including the script body."""
    try:
        return _json(ok(await jc_client.get_command(command_id)))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def list_command_results(
    limit: int = 100,
    skip: int = 0,
    filter: str | None = None,
) -> str:
    """Get command execution history/results.

    Use `filter` for server-side filtering, e.g. 'exitCode:1' for failed executions.
    Key fields: system, command, exitCode, responseTime, response (stdout).
    """
    try:
        data = await jc_client.list_command_results(limit=limit, skip=skip, filter=filter)
        results = data.get("results") or [] if isinstance(data, dict) else []
        total = data.get("totalCount") if isinstance(data, dict) else None
        failed = sum(1 for r in results if (r.get("exitCode") or 0) != 0)
        return _json(ok({
            "totalCount": total,
            "count": len(results),
            "failed": failed,
            "results": results,
        }))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# ALERTS (JumpCloud native alerts)
# =============================================================================


@mcp.tool()
async def list_jc_alerts(
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
) -> str:
    """List JumpCloud-native platform alerts (health/security notifications).

    These are JumpCloud's own alerts — not related to Prometheus. Covers things like
    system offline, policy failures, license limits approaching, etc.
    """
    try:
        data = await jc_client.list_alerts(limit=limit, skip=skip)
        alerts = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            alerts = [a for a in alerts if needle in (a.get("name") or "").lower()]
        return _json(ok({"count": len(alerts), "alerts": alerts}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_jc_alerts_stats() -> str:
    """Get aggregated statistics for JumpCloud alerts (counts by severity and status)."""
    try:
        return _json(ok(await jc_client.get_alerts_stats()))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# HEALTH MONITORING
# =============================================================================


@mcp.tool()
async def list_health_monitoring_rules(limit: int = 100) -> str:
    """List health monitoring rules configured in JumpCloud.

    Health monitoring watches for system conditions (disk space, agent offline, etc.)
    and triggers alerts.
    """
    try:
        data = await jc_client.list_health_rules(limit=limit)
        rules = data if isinstance(data, list) else []
        return _json(ok({"count": len(rules), "rules": rules}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_health_monitoring_stats() -> str:
    """Get aggregate statistics across all health monitoring rules (firing/OK counts)."""
    try:
        return _json(ok(await jc_client.get_health_rules_stats()))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# DUO MFA INTEGRATION
# =============================================================================


@mcp.tool()
async def list_duo_accounts() -> str:
    """List Duo MFA accounts integrated with JumpCloud."""
    try:
        data = await jc_client.list_duo_accounts()
        accounts = data if isinstance(data, list) else []
        return _json(ok({"count": len(accounts), "duoAccounts": accounts}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def list_duo_apps(account_id: str) -> str:
    """List Duo applications configured for a specific Duo account integration."""
    try:
        data = await jc_client.list_duo_apps(account_id)
        apps = data if isinstance(data, list) else []
        return _json(ok({"accountId": account_id, "count": len(apps), "apps": apps}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# DIRECTORY INSIGHTS (AUDIT LOG)
# =============================================================================


@mcp.tool()
async def query_directory_events(
    service: list[str],
    start_time: str,
    end_time: str | None = None,
    limit: int = 100,
    search_term: dict | None = None,
    fields: list[str] | None = None,
    sort: str = "DESC",
) -> str:
    """Query JumpCloud Directory Insights audit log events.

    Args:
      service: List of service names. Common values:
        'all', 'directory', 'sso', 'radius', 'ldap', 'mdm',
        'systems', 'password_manager', 'software_apps', 'user_portal'
      start_time: ISO 8601 UTC, e.g. '2025-05-01T00:00:00Z'
      end_time: ISO 8601 UTC (optional)
      limit: Max events (default 100, max 1000)
      search_term: Structured JumpCloud query object:
        {"and": [{"field": "success", "value": "false"}]}
        {"or": [{"field": "event_type", "value": "user_login_attempt"}]}
      sort: "DESC" (newest first) or "ASC"
    """
    try:
        data = await jc_client.query_events(
            service=service, start_time=start_time, end_time=end_time,
            limit=limit, search_term=search_term, fields=fields, sort=sort,
        )
        events = data if isinstance(data, list) else []
        return _json(ok({"count": len(events), "events": events}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def count_directory_events(
    service: list[str],
    start_time: str,
    end_time: str | None = None,
) -> str:
    """Count Directory Insights events for a time range without fetching the full payload."""
    try:
        return _json(ok(await jc_client.count_events(service=service, start_time=start_time,
                                                     end_time=end_time)))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_recent_login_events(hours_back: int = 24, limit: int = 100) -> str:
    """Get recent SSO/directory login events for the last N hours."""
    from datetime import datetime, timedelta, timezone
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours_back)
    return await query_directory_events(
        service=["sso", "directory"],
        start_time=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end_time=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        limit=limit,
        fields=["timestamp", "event_type", "initiated_by", "success",
                "resource", "client_ip", "geoip"],
    )


@mcp.tool()
async def get_failed_login_events(hours_back: int = 24, limit: int = 100) -> str:
    """Get failed login events for the last N hours — useful for security monitoring.

    Fetches all auth events from sso/directory/ldap/radius and filters client-side for success=false.
    """
    from datetime import datetime, timedelta, timezone
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours_back)
    raw = await query_directory_events(
        service=["sso", "directory", "ldap", "radius"],
        start_time=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end_time=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        limit=limit,
        fields=["timestamp", "event_type", "initiated_by", "success",
                "resource", "client_ip", "geoip", "error_message"],
    )
    import json as _j
    parsed = _j.loads(raw)
    if not parsed.get("ok"):
        return raw
    events = parsed.get("data", {}).get("events", [])
    failed = [e for e in events
              if e.get("success") is False or str(e.get("success", "")).lower() == "false"]
    return _json(ok({"count": len(failed), "hoursBack": hours_back, "events": failed}))


# =============================================================================
# SYSTEM INSIGHTS — existing tools
# =============================================================================


@mcp.tool()
async def get_system_apps(
    system_id: str | None = None,
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
) -> str:
    """Get apps installed on systems (macOS/Linux). Use system_id for a specific device."""
    try:
        data = await jc_client.get_si_apps(system_id=system_id, limit=limit, skip=skip)
        apps = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            apps = [a for a in apps if needle in (a.get("name") or "").lower()]
        return _json(ok({"systemId": system_id, "count": len(apps), "apps": apps}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_programs(
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
) -> str:
    """Get Windows programs (from registry) across all systems."""
    try:
        data = await jc_client.get_si_programs(limit=limit, skip=skip)
        programs = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            programs = [p for p in programs if needle in (p.get("name") or "").lower()]
        return _json(ok({"count": len(programs), "programs": programs}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_patches(system_id: str | None = None, limit: int = 100, skip: int = 0) -> str:
    """Get OS patches/updates status. Use system_id for a specific system."""
    try:
        data = await jc_client.get_si_patches(system_id=system_id, limit=limit, skip=skip)
        return _json(ok({"systemId": system_id, "count": len(data) if isinstance(data, list) else 0,
                         "patches": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_os_versions(system_id: str | None = None, limit: int = 100, skip: int = 0) -> str:
    """Get OS version across all systems or a specific system."""
    try:
        data = await jc_client.get_si_os_version(system_id=system_id, limit=limit, skip=skip)
        return _json(ok({"systemId": system_id, "count": len(data) if isinstance(data, list) else 0,
                         "osVersions": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_disk_encryption_status(system_id: str | None = None, limit: int = 100) -> str:
    """Get disk encryption status (BitLocker/FileVault) for all systems or a specific one.

    Returns encrypted count vs. unencrypted count + per-disk details.
    """
    try:
        data = await jc_client.get_si_disk_encryption(system_id=system_id, limit=limit)
        disks = data if isinstance(data, list) else []
        encrypted = sum(1 for d in disks if d.get("encrypted") is True)
        return _json(ok({
            "systemId": system_id,
            "total": len(disks),
            "encrypted": encrypted,
            "unencrypted": len(disks) - encrypted,
            "disks": disks,
        }))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_uptime(system_id: str | None = None, limit: int = 100) -> str:
    """Get uptime data for all systems or a specific system."""
    try:
        data = await jc_client.get_si_uptime(system_id=system_id, limit=limit)
        return _json(ok({"systemId": system_id, "count": len(data) if isinstance(data, list) else 0,
                         "uptimes": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_logged_in_users(limit: int = 100, skip: int = 0) -> str:
    """Get users currently/recently logged in across all systems."""
    try:
        data = await jc_client.get_si_logged_in_users(limit=limit, skip=skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "loggedInUsers": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_services(
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
    status: str | None = None,
) -> str:
    """Get Windows/Linux services. Filter by name or status (RUNNING/STOPPED)."""
    try:
        data = await jc_client.get_si_services(limit=limit, skip=skip)
        services = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            services = [s for s in services if needle in (s.get("name") or "").lower()]
        if status:
            s_upper = status.upper()
            services = [s for s in services if (s.get("status") or "").upper() == s_upper]
        return _json(ok({"count": len(services), "services": services}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_linux_packages(limit: int = 100, skip: int = 0, name_contains: str | None = None) -> str:
    """Get Linux packages across all Linux systems."""
    try:
        data = await jc_client.get_si_linux_packages(limit=limit, skip=skip)
        packages = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            packages = [p for p in packages if needle in (p.get("name") or "").lower()]
        return _json(ok({"count": len(packages), "packages": packages}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_system_info(system_id: str | None = None, limit: int = 100, skip: int = 0) -> str:
    """Get hardware/system info (CPU, RAM, model) for all systems or a specific one."""
    try:
        data = await jc_client.get_si_system_info(system_id=system_id, limit=limit, skip=skip)
        return _json(ok({"systemId": system_id, "count": len(data) if isinstance(data, list) else 0,
                         "systemInfo": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# SYSTEM INSIGHTS — security & compliance
# =============================================================================


@mcp.tool()
async def get_si_certificates(
    system_id: str | None = None,
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
) -> str:
    """Get SSL/TLS and code-signing certificates installed on systems.

    Useful for certificate expiry auditing. Key fields: common_name, not_valid_after,
    issuer, self_signed, sha1, system_id.
    """
    try:
        data = await jc_client._get_si("certificates", system_id, limit, skip)
        certs = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            certs = [c for c in certs if needle in (c.get("common_name") or "").lower()]
        return _json(ok({"systemId": system_id, "count": len(certs), "certificates": certs}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_chrome_extensions(
    system_id: str | None = None,
    limit: int = 100,
    skip: int = 0,
    name_contains: str | None = None,
) -> str:
    """Get Chrome extensions installed across systems — useful for security policy audit.

    Key fields: name, version, uid (extension ID), profile, system_id, permissions.
    """
    try:
        data = await jc_client._get_si("chrome_extensions", system_id, limit, skip)
        exts = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            exts = [e for e in exts if needle in (e.get("name") or "").lower()]
        return _json(ok({"systemId": system_id, "count": len(exts), "chromeExtensions": exts}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_browser_plugins(
    system_id: str | None = None,
    limit: int = 100,
    skip: int = 0,
) -> str:
    """Get browser plugins (non-Chrome) across systems (Safari, Firefox, etc.)."""
    try:
        data = await jc_client._get_si("browser_plugins", system_id, limit, skip)
        return _json(ok({"systemId": system_id, "count": len(data) if isinstance(data, list) else 0,
                         "browserPlugins": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_firefox_addons(
    system_id: str | None = None,
    limit: int = 100,
    skip: int = 0,
) -> str:
    """Get Firefox add-ons installed across systems."""
    try:
        data = await jc_client._get_si("firefox_addons", system_id, limit, skip)
        return _json(ok({"systemId": system_id, "count": len(data) if isinstance(data, list) else 0,
                         "firefoxAddons": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_usb_devices(limit: int = 100, skip: int = 0, vendor_contains: str | None = None) -> str:
    """Get USB devices connected/detected across systems — DLP and security monitoring.

    Key fields: vendor, model, serial, removable, system_id.
    """
    try:
        data = await jc_client._get_si("usb_devices", None, limit, skip)
        devices = data if isinstance(data, list) else []
        if vendor_contains:
            needle = vendor_contains.lower()
            devices = [d for d in devices if needle in (d.get("vendor") or "").lower()]
        return _json(ok({"count": len(devices), "usbDevices": devices}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_authorized_keys(limit: int = 100, skip: int = 0) -> str:
    """Get SSH authorized_keys entries across all Linux/macOS systems.

    Critical for SSH access auditing — shows who can SSH into each system.
    Key fields: username, key, key_file, system_id.
    """
    try:
        data = await jc_client._get_si("authorized_keys", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0,
                         "authorizedKeys": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_user_ssh_keys(limit: int = 100, skip: int = 0) -> str:
    """Get user SSH keys (private key presence indicators) across systems."""
    try:
        data = await jc_client._get_si("user_ssh_keys", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0,
                         "userSshKeys": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_windows_security_products(limit: int = 100, skip: int = 0) -> str:
    """Get Windows Security Center products (AV, firewall, anti-spyware) across Windows systems.

    Key fields: type (antivirus/firewall), name, state, product_state, system_id.
    Use to verify AV coverage and state across the Windows fleet.
    """
    try:
        data = await jc_client._get_si("windows_security_products", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0,
                         "windowsSecurityProducts": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_windows_security_center(limit: int = 100, skip: int = 0) -> str:
    """Get Windows Security Center summary state per system.

    Key fields: autoupdate, firewall, antivirus, antispyware, internet_settings, uac, system_id.
    """
    try:
        data = await jc_client._get_si("windows_security_center", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0,
                         "windowsSecurityCenter": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_bitlocker_info(system_id: str | None = None, limit: int = 100) -> str:
    """Get BitLocker encryption status per drive (Windows only).

    Key fields: device_id, drive_letter, protection_status, encryption_method, system_id.
    More detailed than disk_encryption for Windows-specific BitLocker data.
    """
    try:
        data = await jc_client._get_si("bitlocker_info", system_id, limit, 0)
        drives = data if isinstance(data, list) else []
        protected = sum(1 for d in drives if d.get("protection_status") == "1")
        return _json(ok({
            "systemId": system_id,
            "total": len(drives),
            "protected": protected,
            "unprotected": len(drives) - protected,
            "drives": drives,
        }))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_secureboot(limit: int = 100, skip: int = 0) -> str:
    """Get Secure Boot status across all systems.

    Key fields: secure_boot_enabled, secure_boot_current_enabled, system_id.
    """
    try:
        data = await jc_client._get_si("secureboot", None, limit, skip)
        items = data if isinstance(data, list) else []
        enabled = sum(1 for i in items if i.get("secure_boot_enabled") == "1")
        return _json(ok({"total": len(items), "enabled": enabled,
                         "disabled": len(items) - enabled, "secureboot": items}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_tpm_info(limit: int = 100, skip: int = 0) -> str:
    """Get TPM (Trusted Platform Module) information across systems.

    Key fields: tpm_version, manufacturer, manufacturer_version, activated, enabled, system_id.
    """
    try:
        data = await jc_client._get_si("tpm_info", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "tpmInfo": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_crashes(limit: int = 100, skip: int = 0) -> str:
    """Get system crash reports across macOS/Linux systems.

    Key fields: path, crash_type, identifier, version, system_id, datetime.
    """
    try:
        data = await jc_client._get_si("crashes", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "crashes": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_startup_items(limit: int = 100, skip: int = 0) -> str:
    """Get startup items (autorun entries) across macOS systems.

    Key fields: name, path, type, status, system_id.
    """
    try:
        data = await jc_client._get_si("startup_items", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "startupItems": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_scheduled_tasks(limit: int = 100, skip: int = 0,
                                 name_contains: str | None = None) -> str:
    """Get Windows scheduled tasks across all systems.

    Key fields: name, action, path, enabled, state, system_id.
    """
    try:
        data = await jc_client._get_si("scheduled_tasks", None, limit, skip)
        tasks = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            tasks = [t for t in tasks if needle in (t.get("name") or "").lower()]
        return _json(ok({"count": len(tasks), "scheduledTasks": tasks}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_launchd(limit: int = 100, skip: int = 0) -> str:
    """Get launchd jobs (LaunchAgents/LaunchDaemons) across macOS systems.

    Key fields: name, path, inetd_compatibility, keep_alive, run_at_load, system_id.
    """
    try:
        data = await jc_client._get_si("launchd", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "launchdJobs": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_kernel_info(system_id: str | None = None, limit: int = 100) -> str:
    """Get kernel version information across systems.

    Key fields: version, build, platform, system_id.
    """
    try:
        data = await jc_client._get_si("kernel_info", system_id, limit, 0)
        return _json(ok({"systemId": system_id, "count": len(data) if isinstance(data, list) else 0,
                         "kernelInfo": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_dns_resolvers(limit: int = 100, skip: int = 0) -> str:
    """Get DNS resolver configuration across all systems.

    Key fields: address, netmask, type, options, system_id.
    """
    try:
        data = await jc_client._get_si("dns_resolvers", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "dnsResolvers": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_interface_details(limit: int = 100, skip: int = 0) -> str:
    """Get network interface details (MAC, MTU, flags, speed) across all systems."""
    try:
        data = await jc_client._get_si("interface_details", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0,
                         "interfaceDetails": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_wifi_networks(limit: int = 100, skip: int = 0) -> str:
    """Get Wi-Fi networks seen/connected by systems.

    Key fields: ssid, network_name, security_type, last_connected, system_id.
    """
    try:
        data = await jc_client._get_si("wifi_networks", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "wifiNetworks": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_logical_drives(system_id: str | None = None, limit: int = 100) -> str:
    """Get logical drives (partitions) across systems.

    Key fields: device_id, size, free_space, file_system, drive_letter, system_id.
    """
    try:
        data = await jc_client._get_si("logical_drives", system_id, limit, 0)
        return _json(ok({"systemId": system_id, "count": len(data) if isinstance(data, list) else 0,
                         "logicalDrives": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_mounts(system_id: str | None = None, limit: int = 100) -> str:
    """Get mounted filesystems across systems (macOS/Linux).

    Key fields: path, device, type, flags, blocks_size, system_id.
    """
    try:
        data = await jc_client._get_si("mounts", system_id, limit, 0)
        return _json(ok({"systemId": system_id, "count": len(data) if isinstance(data, list) else 0,
                         "mounts": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_python_packages(limit: int = 100, skip: int = 0,
                                 name_contains: str | None = None) -> str:
    """Get Python packages installed across all systems.

    Key fields: name, version, summary, author, system_id.
    """
    try:
        data = await jc_client._get_si("python_packages", None, limit, skip)
        packages = data if isinstance(data, list) else []
        if name_contains:
            needle = name_contains.lower()
            packages = [p for p in packages if needle in (p.get("name") or "").lower()]
        return _json(ok({"count": len(packages), "pythonPackages": packages}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_battery(limit: int = 100, skip: int = 0) -> str:
    """Get battery information for laptops (macOS/Linux).

    Key fields: charging, serial_number, percent_remaining, minutes_to_full_charge, system_id.
    """
    try:
        data = await jc_client._get_si("battery", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "battery": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_connectivity(limit: int = 100, skip: int = 0) -> str:
    """Get connectivity status (network reachability tests) across systems."""
    try:
        data = await jc_client._get_si("connectivity", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "connectivity": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_shadow(limit: int = 100, skip: int = 0) -> str:
    """Get /etc/shadow user password metadata across Linux systems.

    Key fields: username, password_status, last_change, expire, system_id.
    Note: returns metadata only, never actual password hashes.
    """
    try:
        data = await jc_client._get_si("shadow", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "shadow": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_managed_policies(limit: int = 100, skip: int = 0) -> str:
    """Get macOS managed configuration profiles (MDM policies) applied to systems."""
    try:
        data = await jc_client._get_si("managed_policies", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "managedPolicies": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_sharing_preferences(limit: int = 100, skip: int = 0) -> str:
    """Get macOS sharing preferences (file sharing, screen sharing, etc.) across systems."""
    try:
        data = await jc_client._get_si("sharing_preferences", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0,
                         "sharingPreferences": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_sip_config(limit: int = 100, skip: int = 0) -> str:
    """Get macOS System Integrity Protection (SIP) status across systems.

    Key fields: config_nvram_boot_args, csr_apple_internal, csr_allow_unrestricted_fs,
    csr_allow_task_for_pid, csr_allow_kernel_debugger, system_id.
    """
    try:
        data = await jc_client._get_si("sip_config", None, limit, skip)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "sipConfig": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_si_alf(limit: int = 100, skip: int = 0) -> str:
    """Get macOS Application Layer Firewall (ALF) status across systems.

    Key fields: global_state (0=off,1=on,2=block all), logging_enabled,
    stealth_enabled, system_id.
    """
    try:
        data = await jc_client._get_si("alf", None, limit, skip)
        enabled = sum(1 for d in (data if isinstance(data, list) else [])
                      if str(d.get("global_state", "0")) != "0")
        return _json(ok({"total": len(data) if isinstance(data, list) else 0,
                         "firewallEnabled": enabled, "alf": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def query_system_insight(
    insight_type: str,
    system_id: str | None = None,
    limit: int = 100,
    skip: int = 0,
    filter: list[str] | None = None,
) -> str:
    """Generic system insight query — covers all 50+ insight types not exposed as dedicated tools.

    insight_type must be one of:
      alf, alf_exceptions, alf_explicit_auths, appcompat_shims, apps,
      authorized_keys, azure_instance_metadata, azure_instance_tags, battery,
      bitlocker_info, browser_plugins, certificates, chassis_info, chrome_extensions,
      connectivity, crashes, cups_destinations, disk_encryption, disk_info,
      dns_resolvers, etc_hosts, firefox_addons, groups, ie_extensions,
      interface_addresses, interface_details, kernel_info, launchd, linux_packages,
      logged_in_users, logical_drives, managed_policies, mounts, os_version, patches,
      programs, python_packages, safari_extensions, scheduled_tasks, secureboot,
      services, shadow, shared_folders, shared_resources, sharing_preferences,
      sip_config, startup_items, system_controls, system_info, tpm_info, uptime,
      usb_devices, user_groups, user_ssh_keys, userassist, users, wifi_networks,
      wifi_status, windows_crashes, windows_security_center, windows_security_products

    Pass system_id to scope to a single device. filter is a list of JumpCloud filter
    strings e.g. ["name:eq:chrome", "system_id:eq:abc123"].
    """
    try:
        data = await jc_client._get_si(insight_type, system_id, limit, skip, filter)
        return _json(ok({
            "insightType": insight_type,
            "systemId": system_id,
            "count": len(data) if isinstance(data, list) else 1,
            "data": data,
        }))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# DIRECTORIES / LDAP / PASSWORD POLICIES
# =============================================================================


@mcp.tool()
async def list_directories(limit: int = 100) -> str:
    """List directories connected to JumpCloud (GSuite, Office365, AD, LDAP)."""
    try:
        data = await jc_client.list_directories(limit=limit)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "directories": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def list_ldap_servers(limit: int = 100) -> str:
    """List LDAP servers configured in JumpCloud."""
    try:
        data = await jc_client.list_ldap_servers(limit=limit)
        return _json(ok({"count": len(data) if isinstance(data, list) else 0, "ldapServers": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def get_ldap_server_users(server_id: str, limit: int = 100) -> str:
    """Get users bound to a specific LDAP server."""
    try:
        data = await jc_client.get_ldap_server_users(server_id, limit=limit)
        return _json(ok({"serverId": server_id, "count": len(data) if isinstance(data, list) else 0,
                         "users": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def list_password_policies(limit: int = 100) -> str:
    """List password policies configured in the org."""
    try:
        data = await jc_client.list_password_policies(limit=limit)
        policies = data if isinstance(data, list) else []
        return _json(ok({"count": len(policies), "passwordPolicies": policies}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# REPORTS
# =============================================================================


@mcp.tool()
async def list_jumpcloud_reports(limit: int = 100) -> str:
    """List available JumpCloud built-in reports (pre-built by JumpCloud)."""
    try:
        data = await jc_client.list_jumpcloud_reports(limit=limit)
        reports = data if isinstance(data, list) else []
        return _json(ok({"count": len(reports), "reports": reports}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def list_scheduled_reports(limit: int = 100) -> str:
    """List scheduled reports configured to run automatically."""
    try:
        data = await jc_client.list_scheduled_reports(limit=limit)
        reports = data if isinstance(data, list) else []
        return _json(ok({"count": len(reports), "scheduledReports": reports}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Users
# =============================================================================


@mcp.tool()
async def create_user(
    username: str,
    email: str,
    firstname: str = "",
    lastname: str = "",
    password: str = "",
    attributes: list[dict] | None = None,
) -> str:
    """Create a new JumpCloud user. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        body: dict = {"username": username, "email": email}
        if firstname: body["firstname"] = firstname
        if lastname: body["lastname"] = lastname
        if password: body["password"] = password
        if attributes: body["attributes"] = attributes
        data = await jc_client.create_user(body)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_user(user_id: str, body: dict) -> str:
    """Replace a user record (PUT). Requires ALLOW_WRITE=true.

    body: full user object fields to set (email, firstname, lastname, attributes, etc.)
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_user(user_id, body)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def patch_user(user_id: str, fields: dict) -> str:
    """Partially update a user (PATCH). Requires ALLOW_WRITE=true.

    fields: only the fields you want to change (e.g. {"email": "new@example.com"}).
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.patch_user(user_id, fields)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_user(user_id: str) -> str:
    """Permanently delete a user. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_user(user_id)
        return _json(ok({"deleted": user_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def suspend_user(user_id: str) -> str:
    """Suspend a user account (sets suspended=true). Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.suspend_user(user_id)
        return _json(ok({"suspended": user_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def reactivate_user(user_id: str) -> str:
    """Reactivate a suspended user account. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.reactivate_user(user_id)
        return _json(ok({"reactivated": user_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def unlock_user(user_id: str) -> str:
    """Unlock a locked-out user account. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.unlock_user(user_id)
        return _json(ok({"unlocked": user_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def reset_user_mfa(user_id: str, exclude_current_device: bool = False) -> str:
    """Reset a user's MFA enrollment. Requires ALLOW_WRITE=true.

    exclude_current_device: if True, the current device is excluded from the reset.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.reset_user_mfa(user_id, exclude_current_device)
        return _json(ok({"mfa_reset": user_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def expire_user_password(user_id: str) -> str:
    """Force a user's password to expire on next login. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.expire_user_password(user_id)
        return _json(ok({"password_expired": user_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def bulk_create_users(users: list[dict]) -> str:
    """Bulk-create multiple users in one request. Requires ALLOW_WRITE=true.

    users: list of user objects with at minimum username and email.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.bulk_create_users(users)
        return _json(ok({"created": len(users), "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def bulk_update_users(users: list[dict]) -> str:
    """Bulk-update multiple users. Each entry must include id. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.bulk_update_users(users)
        return _json(ok({"updated": len(users), "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def bulk_expire_users(user_ids: list[str]) -> str:
    """Bulk-expire passwords for multiple users. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.bulk_expire_users(user_ids)
        return _json(ok({"expired": len(user_ids), "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def bulk_unlock_users(user_ids: list[str]) -> str:
    """Bulk-unlock multiple locked-out users. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.bulk_unlock_users(user_ids)
        return _json(ok({"unlocked": len(user_ids), "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def schedule_userstate_change(
    user_ids: list[str],
    state: str,
    start_date: str,
    send_activation_emails: bool = False,
) -> str:
    """Schedule a bulk user state change (activate/suspend/delete) at a future date.

    state: 'ACTIVATED', 'SUSPENDED', or 'DELETED'
    start_date: ISO-8601 datetime string (e.g. '2025-09-01T00:00:00Z')
    Requires ALLOW_WRITE=true.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_scheduled_userstate(
            user_ids, state, start_date, send_activation_emails
        )
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Systems
# =============================================================================


@mcp.tool()
async def update_system(system_id: str, body: dict) -> str:
    """Update system attributes (display name, SSH settings, etc.). Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_system(system_id, body)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_system(system_id: str) -> str:
    """Remove a system from JumpCloud. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_system(system_id)
        return _json(ok({"deleted": system_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def transfer_system_to_org(system_id: str, target_org_id: str) -> str:
    """Transfer a device to a different organization (MSP use case). Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.transfer_system(system_id, target_org_id)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def manage_system_association(
    system_id: str,
    target_id: str,
    target_type: str,
    op: str = "add",
) -> str:
    """Add or remove a system's association with another resource. Requires ALLOW_WRITE=true.

    target_type: 'command', 'policy', 'policy_group', 'user', 'user_group', etc.
    op: 'add' or 'remove'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_system_associations(system_id, target_id, target_type, op)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — System Groups
# =============================================================================


@mcp.tool()
async def create_system_group(name: str, description: str = "") -> str:
    """Create a new system group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_system_group(name, description)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_system_group(group_id: str, name: str, description: str = "") -> str:
    """Update a system group's name or description. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        body: dict = {"name": name}
        if description: body["description"] = description
        data = await jc_client.update_system_group(group_id, body)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_system_group(group_id: str) -> str:
    """Delete a system group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_system_group(group_id)
        return _json(ok({"deleted": group_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def add_system_to_group(group_id: str, system_id: str) -> str:
    """Add a system to a system group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_system_group_members(group_id, system_id, "add")
        return _json(ok({"added": system_id, "group": group_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def remove_system_from_group(group_id: str, system_id: str) -> str:
    """Remove a system from a system group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_system_group_members(group_id, system_id, "remove")
        return _json(ok({"removed": system_id, "group": group_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def manage_system_group_association(
    group_id: str, target_id: str, target_type: str, op: str = "add"
) -> str:
    """Manage a system group's associations with policies, user groups, etc. Requires ALLOW_WRITE=true.

    target_type: 'policy', 'policy_group', 'user', 'user_group', etc.
    op: 'add' or 'remove'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_system_group_associations(group_id, target_id, target_type, op)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — User Groups
# =============================================================================


@mcp.tool()
async def create_user_group(name: str, description: str = "") -> str:
    """Create a new user group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_user_group(name, description)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_user_group(group_id: str, name: str, description: str = "") -> str:
    """Update a user group's name or description. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        body: dict = {"name": name}
        if description: body["description"] = description
        data = await jc_client.update_user_group(group_id, body)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_user_group(group_id: str) -> str:
    """Delete a user group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_user_group(group_id)
        return _json(ok({"deleted": group_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def add_user_to_group(group_id: str, user_id: str) -> str:
    """Add a user to a user group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_user_group_members(group_id, user_id, "add")
        return _json(ok({"added": user_id, "group": group_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def remove_user_from_group(group_id: str, user_id: str) -> str:
    """Remove a user from a user group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_user_group_members(group_id, user_id, "remove")
        return _json(ok({"removed": user_id, "group": group_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def manage_user_group_association(
    group_id: str, target_id: str, target_type: str, op: str = "add"
) -> str:
    """Manage a user group's associations. Requires ALLOW_WRITE=true.

    target_type: 'application', 'ldap_server', 'office365', 'radius_server', 'system', 'system_group', etc.
    op: 'add' or 'remove'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_user_group_associations(group_id, target_id, target_type, op)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def manage_user_association(
    user_id: str, target_id: str, target_type: str, op: str = "add"
) -> str:
    """Manage a user's direct associations with systems, groups, applications. Requires ALLOW_WRITE=true.

    target_type: 'system', 'system_group', 'user_group', 'application', etc.
    op: 'add' or 'remove'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_user_associations(user_id, target_id, target_type, op)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Policies
# =============================================================================


@mcp.tool()
async def create_policy(
    name: str,
    template_id: str,
    values: list[dict] | None = None,
    notes: str = "",
) -> str:
    """Create a new policy from a template. Requires ALLOW_WRITE=true.

    template_id: ID from list_policy_templates().
    values: list of {configFieldID, value} dicts.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_policy(name, template_id, values, notes)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_policy(
    policy_id: str,
    name: str,
    values: list[dict] | None = None,
    notes: str = "",
) -> str:
    """Update an existing policy name and values. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_policy(policy_id, name, values, notes)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_policy(policy_id: str) -> str:
    """Delete a policy. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_policy(policy_id)
        return _json(ok({"deleted": policy_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def manage_policy_association(
    policy_id: str, target_id: str, target_type: str, op: str = "add"
) -> str:
    """Add or remove a policy's association with a system or system group. Requires ALLOW_WRITE=true.

    target_type: 'system' or 'system_group'
    op: 'add' or 'remove'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_policy_associations(policy_id, target_id, target_type, op)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Policy Groups
# =============================================================================


@mcp.tool()
async def create_policy_group(name: str, description: str = "") -> str:
    """Create a new policy group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_policy_group(name, description)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_policy_group(group_id: str, name: str, description: str = "") -> str:
    """Update a policy group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        body: dict = {"name": name}
        if description: body["description"] = description
        data = await jc_client.update_policy_group(group_id, body)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_policy_group(group_id: str) -> str:
    """Delete a policy group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_policy_group(group_id)
        return _json(ok({"deleted": group_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def add_policy_to_group(group_id: str, policy_id: str) -> str:
    """Add a policy to a policy group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_policy_group_members(group_id, policy_id, "add")
        return _json(ok({"added": policy_id, "group": group_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def remove_policy_from_group(group_id: str, policy_id: str) -> str:
    """Remove a policy from a policy group. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_policy_group_members(group_id, policy_id, "remove")
        return _json(ok({"removed": policy_id, "group": group_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def manage_policy_group_association(
    group_id: str, target_id: str, target_type: str, op: str = "add"
) -> str:
    """Manage a policy group's associations. Requires ALLOW_WRITE=true.

    target_type: 'system' or 'system_group'
    op: 'add' or 'remove'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_policy_group_associations(group_id, target_id, target_type, op)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Conditional Access (Authn Policies)
# =============================================================================


@mcp.tool()
async def create_authn_policy(body: dict) -> str:
    """Create a conditional access (authentication) policy. Requires ALLOW_WRITE=true.

    body: full authn policy object with name, conditions, targets, etc.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_authn_policy(body)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_authn_policy(policy_id: str, fields: dict) -> str:
    """Partially update a conditional access policy (PATCH). Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_authn_policy(policy_id, fields)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_authn_policy(policy_id: str) -> str:
    """Delete a conditional access policy. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_authn_policy(policy_id)
        return _json(ok({"deleted": policy_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — IP Lists
# =============================================================================


@mcp.tool()
async def create_iplist(name: str, ips: list[str], list_type: str = "cidr") -> str:
    """Create a new IP list for use in conditional access policies. Requires ALLOW_WRITE=true.

    list_type: 'cidr' or 'range'
    ips: list of CIDR blocks or IP ranges
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_iplist(name, ips, list_type)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_iplist(list_id: str, name: str, ips: list[str], list_type: str = "cidr") -> str:
    """Replace an IP list's contents entirely (PUT). Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.replace_iplist(list_id, name, ips, list_type)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_iplist(list_id: str) -> str:
    """Delete an IP list. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_iplist(list_id)
        return _json(ok({"deleted": list_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Alerts
# =============================================================================


@mcp.tool()
async def update_alert_status(alert_id: str, status: str, remark: str = "") -> str:
    """Update an alert's status. Requires ALLOW_WRITE=true.

    status: 'RESOLVED', 'ACKNOWLEDGED', 'OPEN'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_alert_status(alert_id, status, remark)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_alert(alert_id: str) -> str:
    """Delete an alert. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_alert(alert_id)
        return _json(ok({"deleted": alert_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def bulk_update_alerts(
    update_field: str,
    remark: str = "",
    filter: dict | None = None,
    exclude_ids: list[str] | None = None,
) -> str:
    """Bulk-update alert status or field. Requires ALLOW_WRITE=true.

    update_field: field to update (e.g. 'status')
    filter: optional filter dict to select alerts
    exclude_ids: alert IDs to skip
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.bulk_update_alerts(update_field, filter, remark, exclude_ids)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def bulk_delete_alerts(
    filter: dict | None = None,
    exclude_ids: list[str] | None = None,
) -> str:
    """Bulk-delete alerts matching a filter. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.bulk_delete_alerts(filter, exclude_ids)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Health Monitoring Rules
# =============================================================================


@mcp.tool()
async def create_health_rule(rule: dict) -> str:
    """Create a health monitoring rule. Requires ALLOW_WRITE=true.

    rule: rule object with name, ruleType, conditions, etc.
    Use list_health_rule_templates() to see available rule types and their schemas.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_health_rule(rule)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_health_rule(rule_id: str, rule: dict) -> str:
    """Update a health monitoring rule. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_health_rule(rule_id, rule)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_health_rule(rule_id: str) -> str:
    """Delete a health monitoring rule. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_health_rule(rule_id)
        return _json(ok({"deleted": rule_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def set_health_rule_status(rule_id: str, status: str) -> str:
    """Enable or disable a health monitoring rule. Requires ALLOW_WRITE=true.

    status: 'ENABLED' or 'DISABLED'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_health_rule_status(rule_id, status)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Software Apps (MDM)
# =============================================================================


@mcp.tool()
async def create_software_app(display_name: str, settings_body: dict | None = None) -> str:
    """Create a new MDM software app configuration. Requires ALLOW_WRITE=true.

    settings_body: platform-specific settings (packageId, etc.)
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_software_app(display_name, settings_body)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_software_app(app_id: str, display_name: str, settings_body: dict | None = None) -> str:
    """Update an MDM software app. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_software_app(app_id, display_name, settings_body)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_software_app(app_id: str) -> str:
    """Delete an MDM software app. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_software_app(app_id)
        return _json(ok({"deleted": app_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def reclaim_software_app_licenses(app_id: str) -> str:
    """Reclaim unused licenses for a software app. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.reclaim_software_app_licenses(app_id)
        return _json(ok({"app_id": app_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def retry_software_app_installation(app_id: str) -> str:
    """Retry failed software app installations. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.retry_software_app_installation(app_id)
        return _json(ok({"app_id": app_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def manage_software_app_association(
    app_id: str, target_id: str, target_type: str, op: str = "add"
) -> str:
    """Associate a software app with a system or system group. Requires ALLOW_WRITE=true.

    target_type: 'system' or 'system_group'
    op: 'add' or 'remove'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_software_app_associations(app_id, target_id, target_type, op)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — SaaS Management
# =============================================================================


@mcp.tool()
async def create_saas_app(
    app_name: str,
    app_domains: list[str],
    catalog_app_id: str = "",
    description: str = "",
    owner_user_id: str = "",
) -> str:
    """Add a SaaS application to management. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_saas_app(app_name, app_domains, catalog_app_id, description, owner_user_id)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_saas_app(app_id: str, fields: dict) -> str:
    """Update a SaaS app record. Requires ALLOW_WRITE=true.

    fields: any subset of app_name, app_domains, description, owner_user_id, status, etc.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_saas_app(app_id, fields)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_saas_app(app_id: str) -> str:
    """Remove a SaaS app from management. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_saas_app(app_id)
        return _json(ok({"deleted": app_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_saas_account(app_id: str, account_id: str) -> str:
    """Remove a user account from a SaaS app. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_saas_account(app_id, account_id)
        return _json(ok({"deleted_account": account_id, "app_id": app_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Duo
# =============================================================================


@mcp.tool()
async def create_duo_account() -> str:
    """Create a new Duo account integration. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_duo_account()
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_duo_account(account_id: str) -> str:
    """Delete a Duo account. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_duo_account(account_id)
        return _json(ok({"deleted": account_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def create_duo_app(
    account_id: str,
    name: str,
    api_host: str,
    integration_key: str,
    secret_key: str,
) -> str:
    """Create a Duo application within a Duo account. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_duo_app(account_id, name, api_host, integration_key, secret_key)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_duo_app(
    account_id: str,
    app_id: str,
    name: str,
    api_host: str,
    integration_key: str,
    secret_key: str,
) -> str:
    """Update a Duo application. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_duo_app(account_id, app_id, name, api_host, integration_key, secret_key)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_duo_app(account_id: str, app_id: str) -> str:
    """Delete a Duo application. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_duo_app(account_id, app_id)
        return _json(ok({"deleted": app_id, "account": account_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Roles
# =============================================================================


@mcp.tool()
async def create_role(
    name: str,
    scopes: list[str] | None = None,
    description: str = "",
    organization_ids: list[str] | None = None,
) -> str:
    """Create a new admin role. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_role(name, scopes, description, organization_ids)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_role(role_id: str, fields: dict) -> str:
    """Update an admin role (name, scopes, description). Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_role(role_id, fields)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_role(role_id: str) -> str:
    """Delete an admin role. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_role(role_id)
        return _json(ok({"deleted": role_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Service Accounts
# =============================================================================


@mcp.tool()
async def create_service_account(
    name: str,
    role_id: str,
    auth_config: dict | None = None,
) -> str:
    """Create a new service account. Requires ALLOW_WRITE=true.

    auth_config: optional dict with type and config (e.g. API key settings).
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_service_account(name, role_id, auth_config)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_service_account(service_account_id: str) -> str:
    """Delete a service account. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_service_account(service_account_id)
        return _json(ok({"deleted": service_account_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Password Policies
# =============================================================================


@mcp.tool()
async def create_password_policy(policy: dict, group_ids: list[str] | None = None) -> str:
    """Create a password policy. Requires ALLOW_WRITE=true.

    policy: policy configuration object (minLength, requireUppercase, requireNumbers, etc.)
    group_ids: user group IDs this policy applies to.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_password_policy(policy, group_ids)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_password_policy(
    policy_id: str, policy: dict, group_ids: list[str] | None = None
) -> str:
    """Update a password policy. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_password_policy(policy_id, policy, group_ids)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_password_policy(policy_id: str) -> str:
    """Delete a password policy. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_password_policy(policy_id)
        return _json(ok({"deleted": policy_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Apple MDM Device Actions
# =============================================================================


@mcp.tool()
async def apple_mdm_lock_device(apple_mdm_id: str, device_id: str, pin: str = "") -> str:
    """Send a lock command to an Apple MDM device. Requires ALLOW_WRITE=true.

    pin: optional 6-digit numeric PIN (required for macOS devices).
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.apple_mdm_lock_device(apple_mdm_id, device_id, pin)
        return _json(ok({"locked": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def apple_mdm_erase_device(apple_mdm_id: str, device_id: str, pin: str = "") -> str:
    """Erase (factory reset) an Apple MDM device. IRREVERSIBLE. Requires ALLOW_WRITE=true.

    pin: required for macOS (6-digit numeric PIN).
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.apple_mdm_erase_device(apple_mdm_id, device_id, pin)
        return _json(ok({"erased": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def apple_mdm_restart_device(apple_mdm_id: str, device_id: str) -> str:
    """Restart an Apple MDM device. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.apple_mdm_restart_device(apple_mdm_id, device_id)
        return _json(ok({"restarted": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def apple_mdm_shutdown_device(apple_mdm_id: str, device_id: str) -> str:
    """Shut down an Apple MDM device. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.apple_mdm_shutdown_device(apple_mdm_id, device_id)
        return _json(ok({"shutdown": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def apple_mdm_clear_passcode(apple_mdm_id: str, device_id: str) -> str:
    """Clear the passcode on an Apple MDM iOS device. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.apple_mdm_clear_passcode(apple_mdm_id, device_id)
        return _json(ok({"cleared_passcode": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def apple_mdm_schedule_os_update(
    apple_mdm_id: str,
    device_id: str,
    install_action: str,
    product_key: str = "",
    max_user_deferrals: int = 0,
) -> str:
    """Schedule an OS update on an Apple MDM device. Requires ALLOW_WRITE=true.

    install_action: 'DOWNLOAD_ONLY', 'INSTALL_ASAP', 'NOTIFY_ONLY', 'INSTALL_LATER'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.apple_mdm_schedule_os_update(
            apple_mdm_id, device_id, install_action, product_key, max_user_deferrals
        )
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def apple_mdm_clear_activation_lock(apple_mdm_id: str, device_id: str) -> str:
    """Clear Activation Lock on an Apple MDM device. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.apple_mdm_clear_activation_lock(apple_mdm_id, device_id)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def apple_mdm_delete_device(apple_mdm_id: str, device_id: str) -> str:
    """Remove an Apple MDM device enrollment. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.apple_mdm_delete_device(apple_mdm_id, device_id)
        return _json(ok({"removed": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def apple_mdm_refresh_dep_devices(apple_mdm_id: str) -> str:
    """Refresh DEP device list from Apple. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.apple_mdm_refresh_dep_devices(apple_mdm_id)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Google EMM Device Actions
# =============================================================================


@mcp.tool()
async def google_emm_lock_device(device_id: str) -> str:
    """Lock a Google EMM managed device. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.google_emm_lock_device(device_id)
        return _json(ok({"locked": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def google_emm_reboot_device(device_id: str) -> str:
    """Reboot a Google EMM managed device. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.google_emm_reboot_device(device_id)
        return _json(ok({"rebooted": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def google_emm_erase_device(device_id: str) -> str:
    """Factory reset a Google EMM device. IRREVERSIBLE. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.google_emm_erase_device(device_id)
        return _json(ok({"erased": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def google_emm_reset_password(
    device_id: str, new_password: str, flags: list[str] | None = None
) -> str:
    """Reset the password on a Google EMM device. Requires ALLOW_WRITE=true.

    flags: optional list of flags, e.g. ['REQUIRE_ENTRY']
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.google_emm_reset_password(device_id, new_password, flags)
        return _json(ok({"device_id": device_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Commands
# =============================================================================


@mcp.tool()
async def cancel_queued_commands(workflow_instance_id: str) -> str:
    """Cancel all queued commands for a workflow instance. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.cancel_queued_commands(workflow_instance_id)
        return _json(ok({"cancelled": workflow_instance_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Application Associations
# =============================================================================


@mcp.tool()
async def manage_application_association(
    app_id: str, target_id: str, target_type: str, op: str = "add"
) -> str:
    """Manage an SSO application's associations with users or groups. Requires ALLOW_WRITE=true.

    target_type: 'user' or 'user_group'
    op: 'add' or 'remove'
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.manage_application_associations(app_id, target_id, target_type, op)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Reports
# =============================================================================


@mcp.tool()
async def create_custom_report(report_view: dict) -> str:
    """Create a custom report. Requires ALLOW_WRITE=true.

    report_view: report configuration object (columns, filters, groupBy, etc.)
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_custom_report(report_view)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_custom_report(report_id: str) -> str:
    """Delete a custom report. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_custom_report(report_id)
        return _json(ok({"deleted": report_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def create_scheduled_report(scheduled_report: dict) -> str:
    """Create a scheduled report job. Requires ALLOW_WRITE=true.

    scheduled_report: object with name, schedule, reportType, recipients, etc.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_scheduled_report(scheduled_report)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_scheduled_report(report_id: str) -> str:
    """Delete a scheduled report. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_scheduled_report(report_id)
        return _json(ok({"deleted": report_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def trigger_scheduled_report(report_id: str) -> str:
    """Run a scheduled report immediately. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.trigger_scheduled_report(report_id)
        return _json(ok({"triggered": report_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Access Requests
# =============================================================================


@mcp.tool()
async def create_access_request(
    resource_id: str,
    resource_type: str,
    requestor_id: str,
    reason: str = "",
    expiry: str = "",
) -> str:
    """Create an access request for a resource. Requires ALLOW_WRITE=true.

    resource_type: 'system', 'application', etc.
    expiry: ISO-8601 datetime string.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_access_request(resource_id, resource_type, requestor_id, reason, expiry)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def revoke_access_request(access_id: str) -> str:
    """Revoke an active access request. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.revoke_access_request(access_id)
        return _json(ok({"revoked": access_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — Notification Channels
# =============================================================================


@mcp.tool()
async def create_notification_channel(channel: dict) -> str:
    """Create a notification channel (Slack, webhook, email). Requires ALLOW_WRITE=true.

    channel: object with type ('SLACK', 'WEBHOOK', 'EMAIL') and config fields.
    """
    if guard := _require_write(): return guard
    try:
        data = await jc_client.create_notification_channel(channel)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def update_notification_channel(channel_id: str, channel: dict) -> str:
    """Update a notification channel. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_notification_channel(channel_id, channel)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


@mcp.tool()
async def delete_notification_channel(channel_id: str) -> str:
    """Delete a notification channel. Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.delete_notification_channel(channel_id)
        return _json(ok({"deleted": channel_id, "result": data}))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# WRITE — LDAP Servers
# =============================================================================


@mcp.tool()
async def update_ldap_server(server_id: str, fields: dict) -> str:
    """Update LDAP server settings (lockout action, password expiry action). Requires ALLOW_WRITE=true."""
    if guard := _require_write(): return guard
    try:
        data = await jc_client.update_ldap_server(server_id, fields)
        return _json(ok(data))
    except Exception as exc:
        return _json(classify_error(exc))


# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    from jumpcloud_mcp.core.logging import setup_logging
    setup_logging(settings.LOG_LEVEL)

    logger.info(f"write_mode={'ENABLED' if settings.ALLOW_WRITE else 'DISABLED (read-only)'}")

    if settings.MCP_TRANSPORT == "stdio":
        mcp.run(transport="stdio")
    else:
        from starlette.middleware import Middleware
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import JSONResponse

        class BearerTokenMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                if request.url.path == "/":
                    return await call_next(request)
                auth = request.headers.get("Authorization", "")
                if settings.MCP_SECRET_TOKEN and auth != f"Bearer {settings.MCP_SECRET_TOKEN}":
                    return JSONResponse(
                        status_code=401,
                        content={"error": "unauthorized"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return await call_next(request)

        mcp.run(
            transport="streamable-http",
            host=settings.MCP_HOST,
            port=settings.MCP_PORT,
            middleware=[Middleware(BearerTokenMiddleware)],
        )
