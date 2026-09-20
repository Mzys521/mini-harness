# 文件：harness/platform/service.py
from dataclasses import asdict
from datetime import UTC, datetime

from harness.platform.errors import (
    AuthenticationError,
    AuthorizationError,
    QuotaExceededError,
    ResourceNotFoundError,
    TenantSuspendedError,
)
from harness.platform.models import (
    Principal,
    TenantStatus,
    UsageMetric,
)
from harness.platform.quota import utc_month_window


class CommercialPlatformService:
    """Commercial Control Plane Facade。

    这里负责：租户解析、API Scope、套餐能力、Quota、Metering、对象级授权。
    它不重新实现 AgentRunner / ToolExecutor / Durable Runtime。
    """

    def __init__(
        self,
        *,
        durable,
        durable_store,
        store,
        quota,
        metering,
        billing,
        api_keys,
        observability=None,
        metrics=None,
    ) -> None:
        self.durable = durable
        self.durable_store = durable_store
        self.store = store
        self.quota = quota
        self.metering = metering
        self.billing = billing
        self.api_keys = api_keys
        self.observability = observability
        self.metrics = metrics

    def authenticate(self, raw_key: str | None) -> Principal:
        try:
            principal = self.api_keys.authenticate(raw_key)
        except AuthenticationError:
            if self.metrics is not None:
                self.metrics.platform_auth_failures.add(1)
            raise
        tenant = self._require_tenant(principal.tenant_id)
        if tenant.status != TenantStatus.ACTIVE:
            raise TenantSuspendedError()
        return principal

    async def submit_run(
        self,
        *,
        principal: Principal,
        user_input: str,
        conversation_id: str | None = None,
    ):
        self._require_scope(principal, "runs:create")
        tenant, plan = self._tenant_and_plan(principal.tenant_id)
        decision = self.quota.check_run_submission(
            tenant=tenant,
            plan=plan,
        )
        if not decision.allowed:
            if self.metrics is not None:
                self.metrics.platform_quota_denials.add(
                    1,
                    {"code": decision.code},
                )
            raise QuotaExceededError(
                code=decision.code,
                detail=decision.reason,
            )

        result = await self.durable.submit(
            user_id=principal.api_key_id,
            tenant_id=tenant.id,
            user_input=user_input,
            permissions=plan.tool_permissions,
            conversation_id=conversation_id,
        )

        # 冻结本 Run 提交时的套餐；后续即使租户升级套餐，历史用量仍按原计划审计。
        self.store.bind_run_account(
            run_id=result.run_id,
            tenant_id=tenant.id,
            plan_id=plan.id,
        )

        # Run Submitted 在入口立即计量，避免大量 Pending Run 绕过每日提交配额。
        inserted = self.store.record_usage(
            event_key=f"{result.run_id}:{UsageMetric.RUN_SUBMITTED.value}",
            tenant_id=tenant.id,
            plan_id=plan.id,
            metric=UsageMetric.RUN_SUBMITTED,
            quantity=1,
            run_id=result.run_id,
            metadata={"blocked": result.blocked},
        )
        if inserted and self.metrics is not None:
            self.metrics.platform_usage_events.add(
                1,
                {"metric": UsageMetric.RUN_SUBMITTED.value},
            )
        return result

    def get_run(self, *, principal: Principal, run_id: str):
        self._require_scope(principal, "runs:read")
        self._assert_run_tenant(principal, run_id)
        result = self.durable.get_result(run_id)
        # 客户端查询结果时顺便做一次同步；后台 Reconciler 仍是可靠主路径。
        self.metering.sync_run(run_id)
        return result

    def approve_run(self, *, principal: Principal, run_id: str) -> None:
        self._require_scope(principal, "runs:approve")
        self._assert_run_tenant(principal, run_id)
        self.durable.approve(
            run_id=run_id,
            approved_by=principal.api_key_id,
        )
        self.store.record_audit(
            actor_api_key_id=principal.api_key_id,
            tenant_id=principal.tenant_id,
            action="run.approve",
            target_type="run",
            target_id=run_id,
        )

    def cancel_run(self, *, principal: Principal, run_id: str) -> None:
        self._require_scope(principal, "runs:cancel")
        self._assert_run_tenant(principal, run_id)
        self.durable.cancel(run_id=run_id)
        self.store.record_audit(
            actor_api_key_id=principal.api_key_id,
            tenant_id=principal.tenant_id,
            action="run.cancel",
            target_type="run",
            target_id=run_id,
        )

    def usage_summary(self, *, principal: Principal, start, end):
        self._require_scope(principal, "usage:read")
        self.metering.sync_once()
        return self.store.usage_summary(
            tenant_id=principal.tenant_id,
            start=start,
            end=end,
        )

    def billing_preview(self, *, principal: Principal, start=None, end=None):
        self._require_scope(principal, "billing:read")
        self.metering.sync_once()
        if start is None or end is None:
            start, end = utc_month_window()
        return self.billing.preview(
            tenant_id=principal.tenant_id,
            start=start,
            end=end,
        )

    # ---------- Admin Control Plane ----------

    def admin_list_tenants(self, *, principal: Principal):
        self._require_scope(principal, "platform:admin")
        return self.store.list_tenants()

    def admin_list_plans(self, *, principal: Principal):
        self._require_scope(principal, "platform:admin")
        return self.store.list_plans()

    def admin_create_tenant(
        self,
        *,
        principal: Principal,
        tenant_id: str,
        name: str,
        plan_id: str,
    ):
        self._require_scope(principal, "platform:admin")
        if self.store.get_plan(plan_id) is None:
            raise ResourceNotFoundError(f"plan not found: {plan_id}")
        tenant = self.store.create_tenant(
            tenant_id=tenant_id,
            name=name,
            plan_id=plan_id,
        )
        self.store.record_audit(
            actor_api_key_id=principal.api_key_id,
            tenant_id=tenant_id,
            action="tenant.create",
            target_type="tenant",
            target_id=tenant_id,
            metadata={"plan_id": plan_id},
        )
        return tenant

    def admin_create_api_key(
        self,
        *,
        principal: Principal,
        tenant_id: str,
        name: str,
        scopes: frozenset[str],
    ):
        self._require_scope(principal, "platform:admin")
        if self.store.get_tenant(tenant_id) is None:
            raise ResourceNotFoundError(f"tenant not found: {tenant_id}")
        issued = self.api_keys.create_key(
            tenant_id=tenant_id,
            name=name,
            scopes=scopes,
        )
        self.store.record_audit(
            actor_api_key_id=principal.api_key_id,
            tenant_id=tenant_id,
            action="api_key.create",
            target_type="api_key",
            target_id=issued.record.id,
            metadata={"scopes": sorted(scopes)},
        )
        return issued

    def admin_set_tenant_status(
        self,
        *,
        principal: Principal,
        tenant_id: str,
        status: TenantStatus,
    ) -> None:
        self._require_scope(principal, "platform:admin")
        self.store.set_tenant_status(
            tenant_id=tenant_id,
            status=status,
        )
        self.store.record_audit(
            actor_api_key_id=principal.api_key_id,
            tenant_id=tenant_id,
            action="tenant.status.update",
            target_type="tenant",
            target_id=tenant_id,
            metadata={"status": status.value},
        )

    def admin_set_tenant_plan(
        self,
        *,
        principal: Principal,
        tenant_id: str,
        plan_id: str,
    ) -> None:
        self._require_scope(principal, "platform:admin")
        if self.store.get_plan(plan_id) is None:
            raise ResourceNotFoundError(f"plan not found: {plan_id}")
        self.store.set_tenant_plan(tenant_id=tenant_id, plan_id=plan_id)
        self.store.record_audit(
            actor_api_key_id=principal.api_key_id,
            tenant_id=tenant_id,
            action="tenant.plan.update",
            target_type="tenant",
            target_id=tenant_id,
            metadata={"plan_id": plan_id},
        )

    # ---------- Internal boundaries ----------

    def _require_scope(self, principal: Principal, scope: str) -> None:
        if not principal.has_scope(scope):
            raise AuthorizationError(f"missing API scope: {scope}")

    def _require_tenant(self, tenant_id: str):
        tenant = self.store.get_tenant(tenant_id)
        if tenant is None:
            raise ResourceNotFoundError(f"tenant not found: {tenant_id}")
        return tenant

    def _tenant_and_plan(self, tenant_id: str):
        tenant = self._require_tenant(tenant_id)
        if tenant.status != TenantStatus.ACTIVE:
            raise TenantSuspendedError()
        plan = self.store.get_plan(tenant.plan_id)
        if plan is None or not plan.active:
            raise ResourceNotFoundError(f"active plan not found: {tenant.plan_id}")
        return tenant, plan

    def _assert_run_tenant(self, principal: Principal, run_id: str) -> None:
        tenant_id = self.store.get_run_tenant_id(run_id)
        if tenant_id is None:
            raise ResourceNotFoundError(f"run not found: {run_id}")
        # platform:admin 不自动获得普通租户 Run 数据读取权，避免后台凭据被滥用。
        if tenant_id != principal.tenant_id:
            raise ResourceNotFoundError(f"run not found: {run_id}")
