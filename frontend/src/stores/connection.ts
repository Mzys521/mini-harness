import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { api, setApiKey } from "@/api/client";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";
import type { Mode, Principal, Task } from "@/types/domain";

/**
 * Connection identity. The API key is deliberately memory-only: it is never
 * written to browser storage, so a reload returns to demo mode.
 */
export const useConnectionStore = defineStore("connection", () => {
  const toasts = useToastStore();
  const workspace = useWorkspaceStore();

  const mode = ref<Mode>("demo");
  const principal = ref<Principal | null>(null);
  const busy = ref(false);
  const error = ref("");
  const serverStatus = ref<"checking" | "online" | "offline" | "standalone">("checking");

  const isLive = computed(() => mode.value === "live" && principal.value !== null);
  const tenantLabel = computed(() => principal.value?.tenant_id ?? "");
  const canApprove = computed(() => hasScope("runs:approve"));
  const canCancel = computed(() => hasScope("runs:cancel"));

  function hasScope(scope: string): boolean {
    const scopes = principal.value?.scopes ?? [];
    return scopes.includes("platform:admin") || scopes.includes(scope);
  }

  async function probeServer(): Promise<void> {
    serverStatus.value = "checking";
    try {
      const data = await api.healthz();
      serverStatus.value = data.status === "ok" ? "online" : "standalone";
    } catch {
      serverStatus.value = "offline";
    }
  }

  async function connect(candidateKey: string): Promise<boolean> {
    busy.value = true;
    error.value = "";
    try {
      // Identity comes from the server; the client never asserts tenant or scopes.
      const identity = await api.me(candidateKey);
      if (typeof identity.tenant_id !== "string" || !Array.isArray(identity.scopes)) {
        throw new Error("服务返回了无法识别的身份信息。");
      }
      const scopes = identity.scopes;
      const sufficient =
        scopes.includes("platform:admin") ||
        ["runs:create", "runs:read"].every((scope) => scopes.includes(scope));
      if (!sufficient) throw new Error("此密钥需要 runs:create 与 runs:read 权限。");

      setApiKey(candidateKey);
      principal.value = identity;
      mode.value = "live";

      // Adopt a task that belongs to this tenant, or start a fresh one.
      const first = visibleTasks()[0];
      if (first) workspace.activeId = first.id;
      else workspace.createTask("live", identity.tenant_id);
      workspace.persist();

      toasts.push("已连接 Harness，可以开始真实任务了。");
      return true;
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause);
      return false;
    } finally {
      busy.value = false;
    }
  }

  function visibleTasks(): Task[] {
    return workspace.tasks.filter(
      (task) =>
        task.mode === mode.value &&
        (task.mode === "demo" || task.tenantId === principal.value?.tenant_id),
    );
  }

  function switchToDemo(): void {
    setApiKey("");
    principal.value = null;
    mode.value = "demo";
    error.value = "";
    const first = visibleTasks()[0];
    if (first) workspace.activeId = first.id;
    else workspace.createTask("demo", null);
    workspace.persist();
  }

  return {
    mode,
    principal,
    busy,
    error,
    serverStatus,
    isLive,
    tenantLabel,
    canApprove,
    canCancel,
    hasScope,
    visibleTasks,
    probeServer,
    connect,
    switchToDemo,
  };
});
