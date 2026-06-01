// 展示层中文标签的单一真源 —— 后端 enum / 字段键保持英文标识, UI 一律说人话。
// 品牌: 念念手记 (Keepbook) · 对话的 AI 叫「小本」。
import type { Kind, SourceLayer, Status } from "./types";

export const FIELD_LABEL: Record<string, string> = {
  full_name: "姓名",
  employer: "公司",
  role: "职位",
  location: "所在地",
  comm_pref: "联系方式",
  relationship: "关系",
  annotation: "备注",
  flag_reason: "待核实事项",
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

// 4-kind: 这条记录属于哪类动作
export const KIND_LABEL: Record<Kind, string> = {
  PATCH: "更改",
  ASSERT: "记录",
  ANNOTATE: "备注",
  FLAG: "待核实",
};

// 状态: 这条记录当前是否生效
export const STATUS_LABEL: Record<Status, string> = {
  APPLIED: "生效中",
  PROPOSED: "待确认",
  SUPERSEDED: "已被更新",
  REJECTED: "未采纳",
  EXPIRED: "已过期",
};

// 来源: 这条信息的获取途径
export const LAYER_LABEL: Record<SourceLayer, string> = {
  USER_DIRECT: "本人录入",
  L2_FORM: "表单录入",
  L2_CHAT: "对话中提及",
  L2_VOICE: "语音中提及",
  AGENT_INFERENCE: "小本推断",
};
export const layerLabel = (l?: string | null): string =>
  (l && LAYER_LABEL[l as SourceLayer]) || l || "";

// 工具调用 → 图标 + 人话动作 (让用户看见小本"真在查/真在记")。
export interface ToolDisplay {
  icon: string;
  label: string;
}
export function toolDisplay(
  ev: { name: string; args?: Record<string, unknown> },
  nameOf: (id: number) => string,
): ToolDisplay {
  const a = ev.args ?? {};
  switch (ev.name) {
    case "list_contacts": {
      const q = typeof a.query === "string" ? a.query.trim() : "";
      return { icon: "📇", label: q ? `检索「${q}」` : "浏览联系人" };
    }
    case "get_contact": {
      const id = Number(a.contact_id);
      const who = Number.isFinite(id) ? nameOf(id) : "联系人";
      return { icon: "🔍", label: `查阅 ${who}${a.as_of ? " · 回溯" : ""}` };
    }
    case "review_open_items":
      return { icon: "📋", label: "梳理待办事项" };
    case "record_memory_intents": {
      const n = Array.isArray(a.intents) ? a.intents.length : 0;
      return { icon: "✎", label: n ? `记录 ${n} 项` : "记录" };
    }
    default:
      return { icon: "•", label: ev.name };
  }
}
