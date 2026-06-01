import { fmtDateTime, valueToText } from "../../lib/format";
import type { Kind, LedgerEvent, Status } from "../../lib/types";
import { Badge, type Tone } from "../../ui/Badge";
import styles from "./LedgerTimeline.module.css";

const KIND_TONE: Record<Kind, Tone> = {
  PATCH: "violet",
  ASSERT: "accent",
  ANNOTATE: "dim",
  FLAG: "amber",
};

const STATUS_TONE: Record<Status, Tone> = {
  APPLIED: "accent",
  PROPOSED: "amber",
  SUPERSEDED: "dim",
  REJECTED: "red",
  EXPIRED: "dim",
};

function summarize(e: LedgerEvent): string {
  const p = e.patch_json ?? {};
  if (e.kind === "PATCH") return `${e.target_field} → ${valueToText(p[e.target_field ?? ""])}`;
  if (e.kind === "ASSERT") {
    return (
      Object.entries(p)
        .map(([k, v]) => `${k}: ${valueToText(v)}`)
        .join("   ·   ") || "—"
    );
  }
  if (e.kind === "ANNOTATE") return valueToText(p.annotation);
  return `${e.target_field} · ${valueToText(p.flag_reason)}`; // FLAG
}

export function LedgerTimeline({ events }: { events: LedgerEvent[] }) {
  const ordered = [...events].reverse(); // 最新在上
  if (!ordered.length) {
    return <div className={styles.empty}>no ledger entries yet</div>;
  }
  return (
    <ol className={styles.timeline}>
      {ordered.map((e) => {
        const dead =
          e.status === "SUPERSEDED" || e.status === "REJECTED" || e.status === "EXPIRED";
        return (
          <li key={e.id} className={`${styles.row} ${dead ? styles.dead : ""}`}>
            <span className={`${styles.node} ${styles[`k_${e.kind}`]}`} />
            <div className={styles.content}>
              <div className={styles.line1}>
                <Badge tone={KIND_TONE[e.kind]}>{e.kind}</Badge>
                <Badge tone={STATUS_TONE[e.status]} outline>
                  {e.status}
                </Badge>
                <span className={styles.layer} title="source layer">
                  {e.source_layer}
                </span>
                <span className={styles.time}>{fmtDateTime(e.applied_at ?? e.created_at)}</span>
              </div>

              <div className={`${styles.summary} ${dead ? styles.strike : ""}`}>
                {summarize(e)}
              </div>

              {e.source_quote && (
                <blockquote className={styles.quote}>“{e.source_quote}”</blockquote>
              )}

              <div className={styles.meta}>
                <span>conf {Math.round(e.confidence * 100)}%</span>
                {e.superseded_by && <span>↳ superseded by #{e.superseded_by}</span>}
                {e.rejected_reason && <span>rejected · {e.rejected_reason}</span>}
                <span className={styles.id}>#{e.id}</span>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
