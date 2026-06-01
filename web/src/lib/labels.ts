// 展示层中文标签的单一真源 —— 后端 enum / 字段键保持英文标识, UI 一律说人话。
// 品牌: 念念手记 (Keepbook) · 对话的 AI 叫「小本」。
import type { Kind, SourceLayer, Status } from "./types";

export const FIELD_LABEL: Record<string, string> = {
  full_name: "姓名",
  employer: "公司",
  role: "职位",
  location: "在哪",
  comm_pref: "怎么联系",
  relationship: "关系",
  annotation: "备注",
  flag_reason: "拿不准什么",
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

// 4-kind: 全说人话(小本到底做了啥)
export const KIND_LABEL: Record<Kind, string> = {
  PATCH: "改一条",
  ASSERT: "记一笔",
  ANNOTATE: "随手记",
  FLAG: "拿不准",
};

// 状态: 这条记录现在算不算数
export const STATUS_LABEL: Record<Status, string> = {
  APPLIED: "在用",
  PROPOSED: "等你点头",
  SUPERSEDED: "被新的换掉了",
  REJECTED: "你没让记",
  EXPIRED: "过期了",
};

// 来源: 这条信息怎么知道的
export const LAYER_LABEL: Record<SourceLayer, string> = {
  USER_DIRECT: "你直接说的",
  L2_FORM: "表单填的",
  L2_CHAT: "聊天里说的",
  L2_VOICE: "语音里说的",
  AGENT_INFERENCE: "小本猜的",
};
export const layerLabel = (l?: string | null): string =>
  (l && LAYER_LABEL[l as SourceLayer]) || l || "";
