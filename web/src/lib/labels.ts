// 展示层中文标签的单一真源 —— 后端 enum / 字段键保持英文标识, 仅在 UI 映射成中文。
import type { Kind, SourceLayer, Status } from "./types";

export const FIELD_LABEL: Record<string, string> = {
  full_name: "姓名",
  employer: "雇主",
  role: "职位",
  location: "所在地",
  comm_pref: "联系方式",
  relationship: "关系",
  annotation: "批注",
  flag_reason: "存疑原因",
};
export const fieldLabel = (k?: string | null): string => (k && FIELD_LABEL[k]) || k || "—";

// comm_pref 是受 CHECK 约束的 enum(email/phone/sms 为 canonical), 仅在展示层映射成中文。
export const COMM_PREF_LABEL: Record<string, string> = {
  email: "邮件",
  phone: "电话",
  sms: "短信",
};
/** 把某字段的存储值映射成中文展示值 (目前只有 comm_pref 是 enum, 其余原样)。 */
export const displayValue = (field: string | null | undefined, raw: string): string =>
  field === "comm_pref" ? (COMM_PREF_LABEL[raw] ?? raw) : raw;

export const KIND_LABEL: Record<Kind, string> = {
  PATCH: "改写",
  ASSERT: "断言",
  ANNOTATE: "批注",
  FLAG: "存疑",
};

export const STATUS_LABEL: Record<Status, string> = {
  APPLIED: "已生效",
  PROPOSED: "待确认",
  SUPERSEDED: "已取代",
  REJECTED: "已驳回",
  EXPIRED: "已过期",
};

export const LAYER_LABEL: Record<SourceLayer, string> = {
  USER_DIRECT: "用户直述",
  L2_FORM: "表单",
  L2_CHAT: "对话",
  L2_VOICE: "语音",
  AGENT_INFERENCE: "智能体推断",
};
export const layerLabel = (l?: string | null): string =>
  (l && LAYER_LABEL[l as SourceLayer]) || l || "";
