from __future__ import annotations

from typing import Any

import httpx

from jumpcloud_mcp.core.config import settings

_V1_BASE = "https://console.jumpcloud.com/api"
_V2_BASE = "https://console.jumpcloud.com/api/v2"
_TIMEOUT = 30.0


class JumpCloudClient:
    def _headers(self) -> dict[str, str]:
        h = {
            "x-api-key": settings.JUMPCLOUD_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if settings.JUMPCLOUD_ORG_ID:
            h["x-org-id"] = settings.JUMPCLOUD_ORG_ID
        return h

    async def _get_v1(self, path: str, params: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{_V1_BASE}{path}", headers=self._headers(), params=params or {})
            r.raise_for_status()
            return r.json()

    async def _get_v2(self, path: str, params: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{_V2_BASE}{path}", headers=self._headers(), params=params or {})
            r.raise_for_status()
            return r.json()

    async def _post_v2(self, path: str, body: dict) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{_V2_BASE}{path}", headers=self._headers(), json=body)
            r.raise_for_status()
            return r.json()

    async def _post_v1(self, path: str, body: dict) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{_V1_BASE}{path}", headers=self._headers(), json=body)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    async def _put_v1(self, path: str, body: dict) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.put(f"{_V1_BASE}{path}", headers=self._headers(), json=body)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    async def _patch_v1(self, path: str, body: dict) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.patch(f"{_V1_BASE}{path}", headers=self._headers(), json=body)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    async def _delete_v1(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.delete(f"{_V1_BASE}{path}", headers=self._headers())
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    async def _put_v2(self, path: str, body: dict) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.put(f"{_V2_BASE}{path}", headers=self._headers(), json=body)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    async def _patch_v2(self, path: str, body: dict) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.patch(f"{_V2_BASE}{path}", headers=self._headers(), json=body)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    async def _delete_v2(self, path: str, params: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.delete(f"{_V2_BASE}{path}", headers=self._headers(), params=params or {})
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    async def _post_v2_action(self, path: str, body: dict | None = None) -> Any:
        """POST with optional body, treats 204 as success."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{_V2_BASE}{path}", headers=self._headers(), json=body or {})
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {}

    # =========================================================================
    # V1 — Organizations
    # =========================================================================

    async def list_organizations(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v1("/organizations", {"limit": limit, "skip": skip})

    async def get_organization(self, org_id: str) -> Any:
        return await self._get_v1(f"/organizations/{org_id}")

    async def get_settings(self) -> Any:
        """GET /api/settings — returns MAX_SYSTEM_USERS, ORG_ID, SUPPORT_LEVEL, etc."""
        return await self._get_v1("/settings")

    # =========================================================================
    # V1 — Users (systemusers)
    # =========================================================================

    async def list_users(self, limit: int = 100, skip: int = 0, search: str | None = None,
                         filter: str | None = None, sort: str | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if search:
            p["search[searchTerm]"] = search
        if filter:
            p["filter"] = filter
        if sort:
            p["sort"] = sort
        return await self._get_v1("/systemusers", p)

    async def get_user(self, user_id: str) -> Any:
        return await self._get_v1(f"/systemusers/{user_id}")

    # =========================================================================
    # V1 — Systems
    # =========================================================================

    async def list_systems(self, limit: int = 100, skip: int = 0,
                           search: str | None = None, filter: str | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if search:
            p["search[searchTerm]"] = search
        if filter:
            p["filter"] = filter
        return await self._get_v1("/systems", p)

    async def get_system(self, system_id: str) -> Any:
        return await self._get_v1(f"/systems/{system_id}")

    # =========================================================================
    # V1 — Commands
    # =========================================================================

    async def list_commands(self, limit: int = 100, skip: int = 0,
                            filter: str | None = None, sort: str | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        if sort:
            p["sort"] = sort
        return await self._get_v1("/commands", p)

    async def get_command(self, command_id: str) -> Any:
        return await self._get_v1(f"/commands/{command_id}")

    async def list_command_results(self, limit: int = 100, skip: int = 0,
                                   filter: str | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        return await self._get_v1("/commandresults", p)

    async def get_command_result(self, result_id: str) -> Any:
        return await self._get_v1(f"/commandresults/{result_id}")

    async def get_command_systems(self, command_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/commands/{command_id}/systems", {"limit": limit})

    # =========================================================================
    # V2 — Subscriptions / Licenses
    # =========================================================================

    async def list_subscriptions(self) -> Any:
        return await self._get_v2("/subscriptions")

    async def get_subscription(self, product_code: str) -> Any:
        return await self._get_v2(f"/subscriptions/{product_code}")

    async def get_subscription_components(self, product_code: str) -> Any:
        return await self._get_v2(f"/subscriptions/{product_code}/components")

    # =========================================================================
    # V2 — System Groups
    # =========================================================================

    async def list_system_groups(self, limit: int = 100, skip: int = 0,
                                 filter: list[str] | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        return await self._get_v2("/systemgroups", p)

    async def get_system_group(self, group_id: str) -> Any:
        return await self._get_v2(f"/systemgroups/{group_id}")

    async def get_system_group_members(self, group_id: str, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2(f"/systemgroups/{group_id}/members", {"limit": limit, "skip": skip})

    async def get_system_group_membership(self, group_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systemgroups/{group_id}/membership", {"limit": limit})

    async def get_system_group_users(self, group_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systemgroups/{group_id}/users", {"limit": limit})

    async def get_system_group_policies(self, group_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systemgroups/{group_id}/policies", {"limit": limit})

    # =========================================================================
    # V2 — User Groups
    # =========================================================================

    async def list_user_groups(self, limit: int = 100, skip: int = 0,
                               filter: list[str] | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        return await self._get_v2("/usergroups", p)

    async def get_user_group(self, group_id: str) -> Any:
        return await self._get_v2(f"/usergroups/{group_id}")

    async def get_user_group_members(self, group_id: str, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2(f"/usergroups/{group_id}/members", {"limit": limit, "skip": skip})

    async def get_user_group_membership(self, group_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/usergroups/{group_id}/membership", {"limit": limit})

    async def get_user_group_systems(self, group_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/usergroups/{group_id}/systems", {"limit": limit})

    async def get_user_group_system_groups(self, group_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/usergroups/{group_id}/systemgroups", {"limit": limit})

    # =========================================================================
    # V2 — Groups (all combined)
    # =========================================================================

    async def list_all_groups(self, limit: int = 200, skip: int = 0,
                              filter: list[str] | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        return await self._get_v2("/groups", p)

    # =========================================================================
    # V2 — Policies
    # =========================================================================

    async def list_policies(self, limit: int = 100, skip: int = 0,
                            filter: list[str] | None = None, sort: list[str] | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        if sort:
            p["sort"] = sort
        return await self._get_v2("/policies", p)

    async def get_policy(self, policy_id: str) -> Any:
        return await self._get_v2(f"/policies/{policy_id}")

    async def get_policy_results(self, policy_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/policies/{policy_id}/policyresults", {"limit": limit})

    async def get_policy_statuses(self, policy_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/policies/{policy_id}/policystatuses", {"limit": limit})

    async def get_policy_systems(self, policy_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/policies/{policy_id}/systems", {"limit": limit})

    async def get_policy_system_groups(self, policy_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/policies/{policy_id}/systemgroups", {"limit": limit})

    async def list_policy_results(self, limit: int = 100, skip: int = 0,
                                  filter: list[str] | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        return await self._get_v2("/policyresults", p)

    # =========================================================================
    # V2 — Policy Groups
    # =========================================================================

    async def list_policy_groups(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/policygroups", {"limit": limit, "skip": skip})

    async def get_policy_group(self, group_id: str) -> Any:
        return await self._get_v2(f"/policygroups/{group_id}")

    async def get_policy_group_members(self, group_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/policygroups/{group_id}/members", {"limit": limit})

    async def get_policy_group_systems(self, group_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/policygroups/{group_id}/systems", {"limit": limit})

    async def get_policy_group_system_groups(self, group_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/policygroups/{group_id}/systemgroups", {"limit": limit})

    # =========================================================================
    # V2 — Policy Templates
    # =========================================================================

    async def list_policy_templates(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/policytemplates", {"limit": limit, "skip": skip})

    async def get_policy_template(self, template_id: str) -> Any:
        return await self._get_v2(f"/policytemplates/{template_id}")

    # =========================================================================
    # V2 — Authn Policies (Conditional Access)
    # =========================================================================

    async def list_authn_policies(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/authn/policies", {"limit": limit, "skip": skip})

    async def get_authn_policy(self, policy_id: str) -> Any:
        return await self._get_v2(f"/authn/policies/{policy_id}")

    # =========================================================================
    # V2 — Applications
    # =========================================================================

    async def list_applications(self, limit: int = 100, skip: int = 0,
                                filter: list[str] | None = None, sort: list[str] | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        if sort:
            p["sort"] = sort
        return await self._get_v2("/applications", p)

    async def get_application(self, app_id: str) -> Any:
        return await self._get_v2(f"/applications/{app_id}")

    async def get_application_users(self, app_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/applications/{app_id}/users", {"limit": limit})

    async def get_application_user_groups(self, app_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/applications/{app_id}/usergroups", {"limit": limit})

    # =========================================================================
    # V2 — Software Apps (MDM)
    # =========================================================================

    async def list_software_apps(self, limit: int = 100, skip: int = 0,
                                 filter: list[str] | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        return await self._get_v2("/softwareapps", p)

    async def get_software_app(self, app_id: str) -> Any:
        return await self._get_v2(f"/softwareapps/{app_id}")

    async def get_software_app_statuses(self, app_id: str, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2(f"/softwareapps/{app_id}/statuses", {"limit": limit, "skip": skip})

    async def get_software_app_systems(self, app_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/softwareapps/{app_id}/systems", {"limit": limit})

    async def get_software_app_system_groups(self, app_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/softwareapps/{app_id}/systemgroups", {"limit": limit})

    # =========================================================================
    # V2 — SaaS Management
    # =========================================================================

    async def list_saas_apps(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/saas-management/applications", {"limit": limit, "skip": skip})

    async def get_saas_app(self, app_id: str) -> Any:
        return await self._get_v2(f"/saas-management/applications/{app_id}")

    async def get_saas_app_usage(self, app_id: str) -> Any:
        return await self._get_v2(f"/saas-management/applications/{app_id}/usage")

    async def get_saas_app_accounts(self, app_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/saas-management/applications/{app_id}/accounts", {"limit": limit})

    async def list_saas_app_licenses(self, limit: int = 100) -> Any:
        return await self._get_v2("/saas-management/application-licenses", {"limit": limit})

    async def get_saas_app_license(self, app_id: str) -> Any:
        return await self._get_v2(f"/saas-management/application-licenses/{app_id}")

    # =========================================================================
    # V2 — IP Lists
    # =========================================================================

    async def list_iplists(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/iplists", {"limit": limit, "skip": skip})

    async def get_iplist(self, list_id: str) -> Any:
        return await self._get_v2(f"/iplists/{list_id}")

    # =========================================================================
    # V2 — Roles
    # =========================================================================

    async def list_roles(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/roles", {"limit": limit, "skip": skip})

    async def get_role(self, role_id: str) -> Any:
        return await self._get_v2(f"/roles/{role_id}")

    # =========================================================================
    # V2 — Service Accounts
    # =========================================================================

    async def list_service_accounts(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/service-accounts", {"limit": limit, "skip": skip})

    # =========================================================================
    # V2 — Alerts (JumpCloud native)
    # =========================================================================

    async def list_alerts(self, limit: int = 100, skip: int = 0,
                          filter: list[str] | None = None) -> Any:
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        return await self._get_v2("/alerts", p)

    async def get_alert(self, alert_id: str) -> Any:
        return await self._get_v2(f"/alerts/{alert_id}")

    async def get_alerts_stats(self) -> Any:
        return await self._get_v2("/alerts-stats")

    # =========================================================================
    # V2 — Health Monitoring
    # =========================================================================

    async def list_health_rules(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/healthmonitoring/rules", {"limit": limit, "skip": skip})

    async def get_health_rule(self, rule_id: str) -> Any:
        return await self._get_v2(f"/healthmonitoring/rules/{rule_id}")

    async def get_health_rules_stats(self) -> Any:
        return await self._get_v2("/healthmonitoring/rules-stats")

    async def list_health_rule_templates(self, limit: int = 100) -> Any:
        return await self._get_v2("/healthmonitoring/ruletemplates", {"limit": limit})

    # =========================================================================
    # V2 — Reports
    # =========================================================================

    async def list_jumpcloud_reports(self, limit: int = 100) -> Any:
        return await self._get_v2("/reports/jumpcloud", {"limit": limit})

    async def list_scheduled_reports(self, limit: int = 100) -> Any:
        return await self._get_v2("/reports/scheduled", {"limit": limit})

    async def list_custom_reports(self, limit: int = 100) -> Any:
        return await self._get_v2("/reports/custom", {"limit": limit})

    # =========================================================================
    # V2 — Duo
    # =========================================================================

    async def list_duo_accounts(self) -> Any:
        return await self._get_v2("/duo/accounts")

    async def get_duo_account(self, account_id: str) -> Any:
        return await self._get_v2(f"/duo/accounts/{account_id}")

    async def list_duo_apps(self, account_id: str) -> Any:
        return await self._get_v2(f"/duo/accounts/{account_id}/applications")

    # =========================================================================
    # V2 — Directories / LDAP
    # =========================================================================

    async def list_directories(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/directories", {"limit": limit, "skip": skip})

    async def list_ldap_servers(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/ldapservers", {"limit": limit, "skip": skip})

    async def get_ldap_server(self, server_id: str) -> Any:
        return await self._get_v2(f"/ldapservers/{server_id}")

    async def get_ldap_server_users(self, server_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/ldapservers/{server_id}/users", {"limit": limit})

    # =========================================================================
    # V2 — Password Policies
    # =========================================================================

    async def list_password_policies(self, limit: int = 100, skip: int = 0) -> Any:
        return await self._get_v2("/passwordpolicies", {"limit": limit, "skip": skip})

    # =========================================================================
    # V2 — System associations (per-system traversals)
    # =========================================================================

    async def get_user_system_groups(self, user_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/users/{user_id}/systemgroups", {"limit": limit})

    async def get_user_systems(self, user_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/users/{user_id}/systems", {"limit": limit})

    async def get_system_users(self, system_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systems/{system_id}/users", {"limit": limit})

    async def get_system_user_groups(self, system_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systems/{system_id}/usergroups", {"limit": limit})

    async def get_system_policies(self, system_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systems/{system_id}/policies", {"limit": limit})

    async def get_system_policy_statuses(self, system_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systems/{system_id}/policystatuses", {"limit": limit})

    async def get_system_policy_groups(self, system_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systems/{system_id}/policygroups", {"limit": limit})

    async def get_system_software_app_statuses(self, system_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systems/{system_id}/softwareappstatuses", {"limit": limit})

    async def get_system_commands(self, system_id: str, limit: int = 100) -> Any:
        return await self._get_v2(f"/systems/{system_id}/commands", {"limit": limit})

    async def get_system_fde_key(self, system_id: str) -> Any:
        return await self._get_v2(f"/systems/{system_id}/fdekey")

    async def get_system_aggregated_policy_stats(self, system_id: str) -> Any:
        return await self._get_v2(f"/systems/{system_id}/aggregated-policy-stats")

    # =========================================================================
    # V2 — Directory Insights
    # =========================================================================

    async def query_events(self, service: list[str], start_time: str, end_time: str | None = None,
                           limit: int = 100, search_term: dict | None = None,
                           fields: list[str] | None = None, sort: str = "DESC") -> Any:
        body: dict[str, Any] = {
            "service": service,
            "start_time": start_time,
            "limit": limit,
            "sort": sort,
        }
        if end_time:
            body["end_time"] = end_time
        if search_term:
            body["search_term"] = search_term
        if fields:
            body["fields"] = fields
        return await self._post_v2("/directoryinsights/events", body)

    async def count_events(self, service: list[str], start_time: str, end_time: str | None = None) -> Any:
        body: dict[str, Any] = {"service": service, "start_time": start_time}
        if end_time:
            body["end_time"] = end_time
        return await self._post_v2("/directoryinsights/events/count", body)

    # =========================================================================
    # V2 — System Insights (generic + specific)
    # =========================================================================

    async def _get_si(self, insight: str, system_id: str | None = None,
                      limit: int = 100, skip: int = 0,
                      filter: list[str] | None = None) -> Any:
        path = f"/systeminsights/{system_id}/{insight}" if system_id else f"/systeminsights/{insight}"
        p: dict = {"limit": limit, "skip": skip}
        if filter:
            p["filter"] = filter
        return await self._get_v2(path, p)

    # Convenience wrappers kept for backward compat
    async def get_si_apps(self, system_id=None, limit=100, skip=0, filter=None) -> Any:
        return await self._get_si("apps", system_id, limit, skip, filter)

    async def get_si_patches(self, system_id=None, limit=100, skip=0) -> Any:
        return await self._get_si("patches", system_id, limit, skip)

    async def get_si_os_version(self, system_id=None, limit=100, skip=0, filter=None) -> Any:
        return await self._get_si("os_version", system_id, limit, skip, filter)

    async def get_si_disk_encryption(self, system_id=None, limit=100, skip=0) -> Any:
        return await self._get_si("disk_encryption", system_id, limit, skip)

    async def get_si_users(self, system_id=None, limit=100, skip=0, filter=None) -> Any:
        return await self._get_si("users", system_id, limit, skip, filter)

    async def get_si_programs(self, limit=100, skip=0, filter=None) -> Any:
        return await self._get_si("programs", None, limit, skip, filter)

    async def get_si_linux_packages(self, limit=100, skip=0, filter=None) -> Any:
        return await self._get_si("linux_packages", None, limit, skip, filter)

    async def get_si_logged_in_users(self, limit=100, skip=0) -> Any:
        return await self._get_si("logged_in_users", None, limit, skip)

    async def get_si_system_info(self, system_id=None, limit=100, skip=0) -> Any:
        return await self._get_si("system_info", system_id, limit, skip)

    async def get_si_uptime(self, system_id=None, limit=100, skip=0) -> Any:
        return await self._get_si("uptime", system_id, limit, skip)

    async def get_si_services(self, limit=100, skip=0, filter=None) -> Any:
        return await self._get_si("services", None, limit, skip, filter)

    async def get_si_interface_addresses(self, limit=100, skip=0) -> Any:
        return await self._get_si("interface_addresses", None, limit, skip)


    # =========================================================================
    # WRITE — V1 Users
    # =========================================================================

    async def create_user(self, body: dict) -> Any:
        return await self._post_v1("/systemusers", body)

    async def update_user(self, user_id: str, body: dict) -> Any:
        return await self._put_v1(f"/systemusers/{user_id}", body)

    async def patch_user(self, user_id: str, body: dict) -> Any:
        return await self._patch_v1(f"/systemusers/{user_id}", body)

    async def delete_user(self, user_id: str) -> Any:
        return await self._delete_v1(f"/systemusers/{user_id}")

    async def suspend_user(self, user_id: str) -> Any:
        return await self._patch_v1(f"/systemusers/{user_id}", {"suspended": True})

    async def reactivate_user(self, user_id: str) -> Any:
        return await self._patch_v1(f"/systemusers/{user_id}", {"suspended": False})

    async def unlock_user(self, user_id: str) -> Any:
        return await self._post_v1(f"/systemusers/{user_id}/unlock", {})

    async def reset_user_mfa(self, user_id: str, exclude_current: bool = False) -> Any:
        body: dict = {}
        if exclude_current:
            body["exclusion"] = True
        return await self._post_v1(f"/systemusers/{user_id}/resetmfa", body)

    async def expire_user_password(self, user_id: str) -> Any:
        return await self._post_v1(f"/systemusers/{user_id}/expire", {})

    # =========================================================================
    # WRITE — V2 Bulk Users
    # =========================================================================

    async def bulk_create_users(self, users: list[dict]) -> Any:
        return await self._post_v2("/bulk/users", users)

    async def bulk_update_users(self, users: list[dict]) -> Any:
        return await self._patch_v2("/bulk/users", users)

    async def bulk_expire_users(self, user_ids: list[str]) -> Any:
        return await self._post_v2("/bulk/user/expires", [{"id": uid} for uid in user_ids])

    async def bulk_unlock_users(self, user_ids: list[str]) -> Any:
        return await self._post_v2("/bulk/user/unlocks", [{"id": uid} for uid in user_ids])

    async def create_scheduled_userstate(self, user_ids: list[str], state: str,
                                          start_date: str, send_activation_emails: bool = False) -> Any:
        return await self._post_v2("/bulk/userstates", {
            "user_ids": user_ids, "state": state, "start_date": start_date,
            "send_activation_emails": send_activation_emails,
        })

    async def delete_scheduled_userstate(self, job_id: str) -> Any:
        return await self._delete_v2(f"/bulk/userstates/{job_id}")

    # =========================================================================
    # WRITE — V1 Systems
    # =========================================================================

    async def update_system(self, system_id: str, body: dict) -> Any:
        return await self._put_v1(f"/systems/{system_id}", body)

    async def delete_system(self, system_id: str) -> Any:
        return await self._delete_v1(f"/systems/{system_id}")

    # =========================================================================
    # WRITE — V2 System Groups
    # =========================================================================

    async def create_system_group(self, name: str, description: str = "",
                                   attributes: dict | None = None) -> Any:
        body: dict = {"name": name}
        if description:
            body["description"] = description
        if attributes:
            body["attributes"] = attributes
        return await self._post_v2("/systemgroups", body)

    async def update_system_group(self, group_id: str, body: dict) -> Any:
        return await self._put_v2(f"/systemgroups/{group_id}", body)

    async def delete_system_group(self, group_id: str) -> Any:
        return await self._delete_v2(f"/systemgroups/{group_id}")

    async def manage_system_group_members(self, group_id: str, system_id: str,
                                           op: str = "add") -> Any:
        return await self._post_v2(f"/systemgroups/{group_id}/members",
                                    {"id": system_id, "op": op, "type": "system"})

    async def manage_system_group_associations(self, group_id: str, target_id: str,
                                                target_type: str, op: str = "add") -> Any:
        return await self._post_v2(f"/systemgroups/{group_id}/associations",
                                    {"id": target_id, "op": op, "type": target_type})

    # =========================================================================
    # WRITE — V2 User Groups
    # =========================================================================

    async def create_user_group(self, name: str, description: str = "",
                                 attributes: dict | None = None) -> Any:
        body: dict = {"name": name}
        if description:
            body["description"] = description
        if attributes:
            body["attributes"] = attributes
        return await self._post_v2("/usergroups", body)

    async def update_user_group(self, group_id: str, body: dict) -> Any:
        return await self._put_v2(f"/usergroups/{group_id}", body)

    async def delete_user_group(self, group_id: str) -> Any:
        return await self._delete_v2(f"/usergroups/{group_id}")

    async def manage_user_group_members(self, group_id: str, user_id: str,
                                         op: str = "add") -> Any:
        return await self._post_v2(f"/usergroups/{group_id}/members",
                                    {"id": user_id, "op": op, "type": "user"})

    async def manage_user_group_associations(self, group_id: str, target_id: str,
                                              target_type: str, op: str = "add") -> Any:
        return await self._post_v2(f"/usergroups/{group_id}/associations",
                                    {"id": target_id, "op": op, "type": target_type})

    # =========================================================================
    # WRITE — V2 Policies
    # =========================================================================

    async def create_policy(self, name: str, template_id: str,
                             values: list[dict] | None = None, notes: str = "") -> Any:
        body: dict = {"name": name, "template": {"id": template_id}}
        if values:
            body["values"] = values
        if notes:
            body["notes"] = notes
        return await self._post_v2("/policies", body)

    async def update_policy(self, policy_id: str, name: str,
                             values: list[dict] | None = None, notes: str = "") -> Any:
        body: dict = {"name": name}
        if values:
            body["values"] = values
        if notes:
            body["notes"] = notes
        return await self._put_v2(f"/policies/{policy_id}", body)

    async def delete_policy(self, policy_id: str) -> Any:
        return await self._delete_v2(f"/policies/{policy_id}")

    async def manage_policy_associations(self, policy_id: str, target_id: str,
                                          target_type: str, op: str = "add") -> Any:
        return await self._post_v2(f"/policies/{policy_id}/associations",
                                    {"id": target_id, "op": op, "type": target_type})

    # =========================================================================
    # WRITE — V2 Policy Groups
    # =========================================================================

    async def create_policy_group(self, name: str, description: str = "") -> Any:
        body: dict = {"name": name}
        if description:
            body["description"] = description
        return await self._post_v2("/policygroups", body)

    async def update_policy_group(self, group_id: str, body: dict) -> Any:
        return await self._put_v2(f"/policygroups/{group_id}", body)

    async def delete_policy_group(self, group_id: str) -> Any:
        return await self._delete_v2(f"/policygroups/{group_id}")

    async def manage_policy_group_members(self, group_id: str, policy_id: str,
                                           op: str = "add") -> Any:
        return await self._post_v2(f"/policygroups/{group_id}/members",
                                    {"id": policy_id, "op": op, "type": "policy"})

    async def manage_policy_group_associations(self, group_id: str, target_id: str,
                                                target_type: str, op: str = "add") -> Any:
        return await self._post_v2(f"/policygroups/{group_id}/associations",
                                    {"id": target_id, "op": op, "type": target_type})

    # =========================================================================
    # WRITE — V2 Conditional Access (Authn Policies)
    # =========================================================================

    async def create_authn_policy(self, body: dict) -> Any:
        return await self._post_v2("/authn/policies", body)

    async def update_authn_policy(self, policy_id: str, body: dict) -> Any:
        return await self._patch_v2(f"/authn/policies/{policy_id}", body)

    async def delete_authn_policy(self, policy_id: str) -> Any:
        return await self._delete_v2(f"/authn/policies/{policy_id}")

    # =========================================================================
    # WRITE — V2 IP Lists
    # =========================================================================

    async def create_iplist(self, name: str, ips: list[str],
                             list_type: str = "cidr") -> Any:
        return await self._post_v2("/iplists", {"name": name, "ips": ips, "type": list_type})

    async def update_iplist(self, list_id: str, body: dict) -> Any:
        return await self._patch_v2(f"/iplists/{list_id}", body)

    async def replace_iplist(self, list_id: str, name: str, ips: list[str],
                              list_type: str = "cidr") -> Any:
        return await self._put_v2(f"/iplists/{list_id}",
                                   {"name": name, "ips": ips, "type": list_type})

    async def delete_iplist(self, list_id: str) -> Any:
        return await self._delete_v2(f"/iplists/{list_id}")

    # =========================================================================
    # WRITE — V2 Alerts
    # =========================================================================

    async def update_alert_status(self, alert_id: str, status: str,
                                   remark: str = "") -> Any:
        body: dict = {"status": status}
        if remark:
            body["remark"] = remark
        return await self._post_v2(f"/alerts/{alert_id}/status", body)

    async def delete_alert(self, alert_id: str) -> Any:
        return await self._delete_v2(f"/alerts/{alert_id}")

    async def bulk_delete_alerts(self, filter: dict | None = None,
                                  exclude_ids: list[str] | None = None) -> Any:
        body: dict = {}
        if filter:
            body["filter"] = filter
        if exclude_ids:
            body["excludeIds"] = exclude_ids
        return await self._post_v2("/alerts/bulk-delete", body)

    async def bulk_update_alerts(self, update_field: str, filter: dict | None = None,
                                  remark: str = "", exclude_ids: list[str] | None = None) -> Any:
        body: dict = {"updateField": update_field}
        if filter:
            body["filter"] = filter
        if remark:
            body["remark"] = remark
        if exclude_ids:
            body["excludeIds"] = exclude_ids
        return await self._post_v2("/alerts/bulk-update", body)

    # =========================================================================
    # WRITE — V2 Health Monitoring
    # =========================================================================

    async def create_health_rule(self, rule: dict) -> Any:
        return await self._post_v2("/healthmonitoring/rules", {"rule": rule})

    async def update_health_rule(self, rule_id: str, rule: dict) -> Any:
        return await self._patch_v2(f"/healthmonitoring/rules/{rule_id}", {"rule": rule})

    async def delete_health_rule(self, rule_id: str) -> Any:
        return await self._delete_v2(f"/healthmonitoring/rules/{rule_id}")

    async def update_health_rule_status(self, rule_id: str, status: str) -> Any:
        return await self._patch_v2(f"/healthmonitoring/rules/{rule_id}/status", {"status": status})

    # =========================================================================
    # WRITE — V2 Software Apps (MDM)
    # =========================================================================

    async def create_software_app(self, display_name: str, settings_body: dict | None = None) -> Any:
        body: dict = {"displayName": display_name}
        if settings_body:
            body["settings"] = settings_body
        return await self._post_v2("/softwareapps", body)

    async def update_software_app(self, app_id: str, display_name: str,
                                   settings_body: dict | None = None) -> Any:
        body: dict = {"displayName": display_name}
        if settings_body:
            body["settings"] = settings_body
        return await self._put_v2(f"/softwareapps/{app_id}", body)

    async def delete_software_app(self, app_id: str) -> Any:
        return await self._delete_v2(f"/softwareapps/{app_id}")

    async def reclaim_software_app_licenses(self, app_id: str) -> Any:
        return await self._post_v2_action(f"/softwareapps/{app_id}/reclaim-licenses")

    async def retry_software_app_installation(self, app_id: str) -> Any:
        return await self._post_v2_action(f"/softwareapps/{app_id}/retry-installation")

    async def manage_software_app_associations(self, app_id: str, target_id: str,
                                                target_type: str, op: str = "add") -> Any:
        return await self._post_v2(f"/softwareapps/{app_id}/associations",
                                    {"id": target_id, "op": op, "type": target_type})

    # =========================================================================
    # WRITE — V2 SaaS Management
    # =========================================================================

    async def create_saas_app(self, app_name: str, app_domains: list[str],
                               catalog_app_id: str = "", description: str = "",
                               owner_user_id: str = "") -> Any:
        body: dict = {"app_name": app_name, "app_domains": app_domains}
        if catalog_app_id:
            body["catalog_app_id"] = catalog_app_id
        if description:
            body["description"] = description
        if owner_user_id:
            body["owner_user_id"] = owner_user_id
        return await self._post_v2("/saas-management/applications", body)

    async def update_saas_app(self, app_id: str, body: dict) -> Any:
        return await self._put_v2(f"/saas-management/applications/{app_id}", body)

    async def delete_saas_app(self, app_id: str) -> Any:
        return await self._delete_v2(f"/saas-management/applications/{app_id}")

    async def delete_saas_account(self, app_id: str, account_id: str) -> Any:
        return await self._delete_v2(f"/saas-management/applications/{app_id}/accounts/{account_id}")

    # =========================================================================
    # WRITE — V2 Duo
    # =========================================================================

    async def create_duo_account(self) -> Any:
        return await self._post_v2("/duo/accounts", {})

    async def delete_duo_account(self, account_id: str) -> Any:
        return await self._delete_v2(f"/duo/accounts/{account_id}")

    async def create_duo_app(self, account_id: str, name: str, api_host: str,
                              integration_key: str, secret_key: str) -> Any:
        return await self._post_v2(f"/duo/accounts/{account_id}/applications", {
            "name": name, "apiHost": api_host,
            "integrationKey": integration_key, "secretKey": secret_key,
        })

    async def update_duo_app(self, account_id: str, app_id: str, name: str,
                              api_host: str, integration_key: str, secret_key: str) -> Any:
        return await self._put_v2(f"/duo/accounts/{account_id}/applications/{app_id}", {
            "name": name, "apiHost": api_host,
            "integrationKey": integration_key, "secretKey": secret_key,
        })

    async def delete_duo_app(self, account_id: str, app_id: str) -> Any:
        return await self._delete_v2(f"/duo/accounts/{account_id}/applications/{app_id}")

    # =========================================================================
    # WRITE — V2 Roles
    # =========================================================================

    async def create_role(self, name: str, scopes: list[str] | None = None,
                           description: str = "", organization_ids: list[str] | None = None) -> Any:
        body: dict = {"name": name}
        if scopes:
            body["scopes"] = scopes
        if description:
            body["description"] = description
        if organization_ids:
            body["organizationIds"] = organization_ids
        return await self._post_v2("/roles", body)

    async def update_role(self, role_id: str, body: dict) -> Any:
        return await self._put_v2(f"/roles/{role_id}", body)

    async def delete_role(self, role_id: str) -> Any:
        return await self._delete_v2(f"/roles/{role_id}")

    # =========================================================================
    # WRITE — V2 Service Accounts
    # =========================================================================

    async def create_service_account(self, name: str, role_id: str,
                                      auth_config: dict | None = None) -> Any:
        body: dict = {"name": name, "roleId": role_id}
        if auth_config:
            body["authConfig"] = auth_config
        return await self._post_v2("/service-accounts", body)

    async def delete_service_account(self, service_account_id: str) -> Any:
        return await self._delete_v2(f"/service-accounts/{service_account_id}")

    # =========================================================================
    # WRITE — V2 Password Policies
    # =========================================================================

    async def create_password_policy(self, policy: dict,
                                      group_ids: list[str] | None = None) -> Any:
        body: dict = {"policy": policy}
        if group_ids:
            body["groupIds"] = group_ids
        return await self._post_v2("/passwordpolicies", body)

    async def update_password_policy(self, policy_id: str, policy: dict,
                                      group_ids: list[str] | None = None) -> Any:
        body: dict = {"policy": policy}
        if group_ids:
            body["groupIds"] = group_ids
        return await self._put_v2(f"/passwordpolicies/{policy_id}", body)

    async def delete_password_policy(self, policy_id: str) -> Any:
        return await self._delete_v2(f"/passwordpolicies/{policy_id}")

    # =========================================================================
    # WRITE — V2 Apple MDM device actions
    # =========================================================================

    async def apple_mdm_erase_device(self, apple_mdm_id: str, device_id: str,
                                      pin: str = "") -> Any:
        body: dict = {}
        if pin:
            body["pin"] = pin
        return await self._post_v2_action(f"/applemdms/{apple_mdm_id}/devices/{device_id}/erase", body)

    async def apple_mdm_lock_device(self, apple_mdm_id: str, device_id: str,
                                     pin: str = "") -> Any:
        body: dict = {}
        if pin:
            body["pin"] = pin
        return await self._post_v2_action(f"/applemdms/{apple_mdm_id}/devices/{device_id}/lock", body)

    async def apple_mdm_restart_device(self, apple_mdm_id: str, device_id: str) -> Any:
        return await self._post_v2_action(f"/applemdms/{apple_mdm_id}/devices/{device_id}/restart")

    async def apple_mdm_shutdown_device(self, apple_mdm_id: str, device_id: str) -> Any:
        return await self._post_v2_action(f"/applemdms/{apple_mdm_id}/devices/{device_id}/shutdown")

    async def apple_mdm_clear_passcode(self, apple_mdm_id: str, device_id: str) -> Any:
        return await self._post_v2_action(f"/applemdms/{apple_mdm_id}/devices/{device_id}/clearPasscode")

    async def apple_mdm_schedule_os_update(self, apple_mdm_id: str, device_id: str,
                                            install_action: str, product_key: str = "",
                                            max_user_deferrals: int = 0) -> Any:
        body: dict = {"install_action": install_action}
        if product_key:
            body["product_key"] = product_key
        if max_user_deferrals:
            body["max_user_deferrals"] = max_user_deferrals
        return await self._post_v2_action(f"/applemdms/{apple_mdm_id}/devices/{device_id}/scheduleOSUpdate", body)

    async def apple_mdm_refresh_dep_devices(self, apple_mdm_id: str) -> Any:
        return await self._post_v2_action(f"/applemdms/{apple_mdm_id}/refreshdepdevices")

    async def apple_mdm_clear_activation_lock(self, apple_mdm_id: str, device_id: str) -> Any:
        return await self._post_v2_action(f"/applemdms/{apple_mdm_id}/devices/{device_id}/clearActivationLock")

    async def apple_mdm_delete_device(self, apple_mdm_id: str, device_id: str) -> Any:
        return await self._delete_v2(f"/applemdms/{apple_mdm_id}/devices/{device_id}")

    # =========================================================================
    # WRITE — V2 Google EMM device actions
    # =========================================================================

    async def google_emm_lock_device(self, device_id: str) -> Any:
        return await self._post_v2_action(f"/google-emm/devices/{device_id}/lock")

    async def google_emm_reboot_device(self, device_id: str) -> Any:
        return await self._post_v2_action(f"/google-emm/devices/{device_id}/reboot")

    async def google_emm_erase_device(self, device_id: str) -> Any:
        return await self._post_v2_action(f"/google-emm/devices/{device_id}/erase-device")

    async def google_emm_reset_password(self, device_id: str, new_password: str,
                                         flags: list[str] | None = None) -> Any:
        body: dict = {"newPassword": new_password}
        if flags:
            body["flags"] = flags
        return await self._post_v2(f"/google-emm/devices/{device_id}/resetpassword", body)

    # =========================================================================
    # WRITE — V1 Commands
    # =========================================================================

    async def cancel_queued_commands(self, workflow_instance_id: str) -> Any:
        return await self._delete_v1(f"/commandqueue/{workflow_instance_id}")

    # =========================================================================
    # WRITE — V2 Graph Associations (generic)
    # =========================================================================

    async def manage_system_associations(self, system_id: str, target_id: str,
                                          target_type: str, op: str = "add") -> Any:
        return await self._post_v2(f"/systems/{system_id}/associations",
                                    {"id": target_id, "op": op, "type": target_type})

    async def manage_user_associations(self, user_id: str, target_id: str,
                                        target_type: str, op: str = "add") -> Any:
        return await self._post_v2(f"/users/{user_id}/associations",
                                    {"id": target_id, "op": op, "type": target_type})

    async def manage_application_associations(self, app_id: str, target_id: str,
                                               target_type: str, op: str = "add") -> Any:
        return await self._post_v2(f"/applications/{app_id}/associations",
                                    {"id": target_id, "op": op, "type": target_type})

    async def transfer_system(self, system_id: str, org_id: str) -> Any:
        return await self._post_v2(f"/systems/{system_id}/transfer", {"org_id": org_id})

    # =========================================================================
    # WRITE — V2 Reports
    # =========================================================================

    async def create_custom_report(self, report_view: dict) -> Any:
        return await self._post_v2("/reports/custom", {"reportView": report_view})

    async def delete_custom_report(self, report_id: str) -> Any:
        return await self._delete_v2(f"/reports/custom/{report_id}")

    async def create_scheduled_report(self, scheduled_report: dict) -> Any:
        return await self._post_v2("/reports/scheduled", {"scheduledReport": scheduled_report})

    async def update_scheduled_report(self, report_id: str, scheduled_report: dict) -> Any:
        return await self._put_v2(f"/reports/scheduled/{report_id}", {"scheduledReport": scheduled_report})

    async def delete_scheduled_report(self, report_id: str) -> Any:
        return await self._delete_v2(f"/reports/scheduled/{report_id}")

    async def trigger_scheduled_report(self, report_id: str) -> Any:
        return await self._post_v2_action(f"/reports/scheduled/{report_id}/trigger")

    # =========================================================================
    # WRITE — V2 Access Requests
    # =========================================================================

    async def create_access_request(self, resource_id: str, resource_type: str,
                                     requestor_id: str, reason: str = "",
                                     expiry: str = "") -> Any:
        body: dict = {"resourceId": resource_id, "resourceType": resource_type,
                      "requestorId": requestor_id}
        if reason:
            body["remarks"] = reason
        if expiry:
            body["expiry"] = expiry
        return await self._post_v2("/accessrequests", body)

    async def revoke_access_request(self, access_id: str) -> Any:
        return await self._post_v2_action(f"/accessrequests/{access_id}/revoke")

    # =========================================================================
    # WRITE — V2 Notification Channels
    # =========================================================================

    async def create_notification_channel(self, channel: dict) -> Any:
        return await self._post_v2("/notifications/channels", {"channel": channel})

    async def update_notification_channel(self, channel_id: str, channel: dict) -> Any:
        return await self._patch_v2(f"/notifications/channels/{channel_id}", {"channel": channel})

    async def delete_notification_channel(self, channel_id: str) -> Any:
        return await self._delete_v2(f"/notifications/channels/{channel_id}")

    # =========================================================================
    # WRITE — V2 LDAP Servers
    # =========================================================================

    async def update_ldap_server(self, server_id: str, body: dict) -> Any:
        return await self._patch_v2(f"/ldapservers/{server_id}", body)


jc_client = JumpCloudClient()

