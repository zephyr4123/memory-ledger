import { fmtDateTime, valueToText } from "../../lib/format";
import { displayValue, fieldLabel, KIND_LABEL, layerLabel, STATUS_LABEL } from "../../lib/labels";
import type { LedgerEvent, Status } from "../../lib/types";
import { Badge, type Tone } from "../../ui/Badge";
import styles from "./LedgerTimeline.module.css";

/* 颜色只编码"活性"(status): 活=sage, 待签=clay, 死(取代/拒绝/过期)=dim/danger。
   kind 退为中性标签, 由文字区分 —— 避免重新堆出一片彩虹。 */
const STATUS_TONE: Record<Status, Tone> = {
  APPLIED: "sage",
  PROPOSED: "clay",
  SUPERSEDED: "dim",
  REJECTED: "danger",
  EXPIRED: "dim",
};

function summarize(e: LedgerEvent): string {
  const p = e.patch_json ?? {};
  if (e.kind === "PATCH") {
    const f = e.target_field;
    return `${fieldLabel(f)} → ${displayValue(f, valueToText(p[f ?? ""]))}`;
  }
  if (e.kind === "ASSERT") {
    return (
      Object.entries(p)
        .map(([k, v]) => `${fieldLabel(k)}: ${displayValue(k, valueToText(v))}`)
        .join("   ·   ") || "—"
    );
  }
  if (e.kind === "ANNOTATE") return valueToText(p.annotation);
  return `${fieldLabel(e.target_field)} · ${valueToText(p.flag_reason)}`; // FLAG
}

export function LedgerTimeline({ events }: { events: LedgerEvent[] }) {
  const ordered = [...events].reverse(); // 最新在上
  if (!ordered.length) {
    return <div className={styles.empty}>还没记下什么 —— 跟小本聊两句就有了。</div>;
  }
  return (
    <ol className={styles.timeline}>
      {ordered.map((e) => {
        const dead =
          e.status === "SUPERSEDED" || e.status === "REJECTED" || e.status === "EXPIRED";
        return (
          <li key={e.id} className={`${styles.row} ${dead ? styles.dead : ""}`}>
            <span className={`${styles.node} ${styles[`s_${e.status}`]}`} />
            <div className={styles.content}>
              <div className={styles.line1}>
                <span className={styles.kind}>{KIND_LABEL[e.kind]}</span>
                <Badge tone={STATUS_TONE[e.status]} outline>
                  {STATUS_LABEL[e.status]}
                </Badge>
                <span className={styles.layer} title="来源层">
                  {layerLabel(e.source_layer)}
                </span>
                <span className={styles.time}>{fmtDateTime(e.applied_at ?? e.created_at)}</span>
              </div>

              {e.source_quote && (
                <blockquote className={`mono ${styles.quote}`}>“{e.source_quote}”</blockquote>
              )}

              <div className={`mono ${styles.summary} ${dead ? styles.strike : ""}`}>
                {summarize(e)}
              </div>

              <div className={`mono ${styles.meta}`}>
                <span>有 {Math.round(e.confidence * 100)}% 把握</span>
                {e.superseded_by && <span>↳ 被第 {e.superseded_by} 条换掉</span>}
                {e.rejected_reason && <span>你没让记 · {e.rejected_reason}</span>}
                <span className={styles.id}>#{e.id}</span>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
