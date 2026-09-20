/** Domain types shared across stores and components. */

export type Mode = "demo" | "live";

export type TaskStatus =
  | "idle"
  | "pending"
  | "running"
  | "waiting"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  role: MessageRole;
  content: string;
  error?: boolean;
  time: string;
}

export type EventIcon = string;

export interface RunEvent {
  /** Monotonic per-task id: keeps `v-for` keys stable. */
  id: number;
  title: string;
  detail: string;
  icon: EventIcon;
  error: boolean;
  time: string;
}

export interface Task {
  id: string;
  title: string;
  mode: Mode;
  tenantId: string | null;
  messages: ChatMessage[];
  events: RunEvent[];
  attachments: string[];
  draft: string;
  createdAt: string;
  status: TaskStatus;
  conversationId: string | null;
  runId: string | null;
  waitingTool?: string | null;
  eventSeq: number;
}

export interface ProjectFile {
  name: string;
  caption: string;
  type: "doc" | "python" | "config";
  text: string;
}

export interface ToolCatalogEntry {
  icon: string;
  name: string;
  description: string;
  reference: string;
}

export type ContextTab = "context" | "tools";

export type MobileView = "tasks" | "chat" | "context";

export type Theme = "light" | "dark";

/** `GET /v1/me` — server-resolved identity. Never client-supplied. */
export interface Principal {
  tenant_id: string;
  api_key_id?: string;
  scopes: string[];
}

export interface RunSubmission {
  run_id: string;
  conversation_id: string | null;
  status: TaskStatus;
  output?: string | null;
  error_message?: string | null;
  waiting_tool_name?: string | null;
}

export interface RunState {
  run_id?: string;
  status: TaskStatus;
  output?: string | null;
  error_message?: string | null;
  waiting_tool_name?: string | null;
}

export interface PersistedWorkspace {
  activeId: string | null;
  tasks: Task[];
}

export interface PersistedLayout {
  sidebar: number;
  inspector: number;
  context: number;
  contextCollapsed?: boolean;
  activityCollapsed?: boolean;
}

export interface ToastMessage {
  id: number;
  text: string;
}
