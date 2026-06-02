// 镜像 crm_api 的 HTTP 契约 (api/src/crm_api/schemas.py)。

export type Kind = "PATCH" | "ASSERT" | "ANNOTATE" | "FLAG";
export type Status = "PROPOSED" | "APPLIED" | "SUPERSEDED" | "REJECTED" | "EXPIRED";
export type SourceLayer =
  | "USER_DIRECT"
  | "L2_FORM"
  | "L2_CHAT"
  | "L2_VOICE"
  | "AGENT_INFERENCE";

export interface Health {
  status: string;
  llm: "live" | "mock";
  model: string | null;
}

export interface PersonListItem {
  id: number;
  full_name: string | null;
  employer: string | null;
  role: string | null;
  location: string | null;
}

export interface ProvenanceItem {
  intent_id?: number;
  source_id?: string;
  source_quote?: string | null;
  confidence?: number;
  applied_at?: string;
  payload?: Record<string, unknown>;
  annotation?: string;
  target_field?: string;
  flag_reason?: string;
}

export interface Person {
  id: number;
  full_name: string | null;
  employer: string | null;
  role: string | null;
  location: string | null;
  comm_pref: string | null;
  relationship: string | null;
  assertions: ProvenanceItem[];
  annotations: ProvenanceItem[];
  flags: ProvenanceItem[];
  intents_applied_as_of: number[];
  as_of: string | null;
}

export interface LedgerEvent {
  id: number;
  kind: Kind;
  status: Status;
  target_field: string | null;
  patch_json: Record<string, unknown>;
  source_layer: SourceLayer;
  source_priority: number | null;
  source_quote: string | null;
  confidence: number;
  reason: string;
  applied_at: string | null;
  superseded_by: number | null;
  rejected_at: string | null;
  rejected_reason: string | null;
  expired_at: string | null;
  created_at: string;
}

export interface Banner {
  intent_id: number;
  target_field: string | null;
  proposed_value: unknown;
  confidence: number;
}

export interface TurnDone {
  banners: Banner[];
  person: Person | null;
  ledger: LedgerEvent[];
  error?: string;
}

// 一次工具调用的回执 (流式可视化 + 落盘回看)。
export type ToolStatus = "running" | "done" | "error";
export interface ToolEvent {
  id: string;
  name: string;
  args?: Record<string, unknown>;
  ok?: boolean;
  status: ToolStatus;
}

// 对话线程 (聊天容器)。记忆本体按 user 全局共享, 不随线程走。
export interface Conversation {
  id: number;
  title: string;
  focus_person_id: number | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConvMessage {
  id: number;
  role: "user" | "agent";
  content: string;
  tools: ToolEvent[];
  reasoning?: string;
  created_at: string;
}

// 新建/编辑联系人的入参 (full_name 在新建时必填)。
export interface PersonInput {
  full_name?: string;
  employer?: string;
  role?: string;
  location?: string;
  comm_pref?: string;
  relationship?: string;
}
