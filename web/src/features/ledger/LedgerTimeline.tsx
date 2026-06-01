import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { fmtDateTime, valueToText } from "../../lib/format";
import { displayValue, fieldLabel, layerLabel, STATUS_LABEL } from "../../lib/labels";
import type { LedgerEvent, Status } from "../../lib/types";
import { Badge, type Tone } from "../../ui/Badge";
import styles from "./LedgerTimeline.module.css";

/* 颜色只编码"活性"(status): 活=sage, 待签=clay, 死(取代/拒绝/过期)=dim/danger。 */
const STATUS_TONE: Record<Status, Tone> = {
  APPLIED: "sage",
  PROPOSED: "clay",
  SUPERSEDED: "dim",
  REJECTED: "danger",
  EXPIRED: "dim",
};

const KIND_GLYPH: Record<string, string> = {
  PATCH: "✎",
  ASSERT: "✦",
  ANNOTATE: "✑",
  FLAG: "⚠",
};

type Filter = "all" | "live" | "pending";
const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "live", label: "在用" },
  { key: "pending", label: "等你点头" },
];

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

const matches = (e: LedgerEvent, f: Filter): boolean =>
  f === "all" || (f === "live" && e.status === "APPLIED") || (f === "pending" && e.status === "PROPOSED");

export function LedgerTimeline({ events }: { events: LedgerEvent[] }) {
  const [filter, setFilter] = useState<Filter>("all");
  // 用户显式开合记录; 未表态时, "等你点头"的默认展开(把待办推到眼前)
  const [override, setOverride] = useState<Record<number, boolean>>({});
  const openFor = (e: LedgerEvent) => override[e.id] ?? e.status === "PROPOSED";
  const toggle = (e: LedgerEvent) =>
    setOverride((o) => ({ ...o, [e.id]: !(o[e.id] ?? e.status === "PROPOSED") }));

  const counts = {
    all: events.length,
    live: events.filter((e) => e.status === "APPLIED").length,
    pending: events.filter((e) => e.status === "PROPOSED").length,
  };
  const ordered = [...events].reverse().filter((e) => matches(e, filter)); // 最新在上

  return (
    <div className={styles.wrap}>
      <div className={styles.filters}>
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`${styles.chip} ${filter === f.key ? styles.chipOn : ""}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
            <span className={styles.chipN}>{counts[f.key]}</span>
          </button>
        ))}
      </div>

      {ordered.length === 0 ? (
        <div className={styles.empty}>
          {events.length === 0 ? "还没记下什么 —— 跟小本聊两句就有了。" : "这个筛选下没有记录。"}
        </div>
      ) : (
        <ol className={styles.timeline}>
          {ordered.map((e) => {
            const dead =
              e.status === "SUPERSEDED" || e.status === "REJECTED" || e.status === "EXPIRED";
            const open = openFor(e);
            return (
              <li key={e.id} className={`${styles.row} ${dead ? styles.dead : ""}`}>
                <span className={`${styles.node} ${styles[`s_${e.status}`]}`} />
                <div className={styles.content}>
                  <button
                    className={styles.header}
                    onClick={() => toggle(e)}
                    aria-expanded={open}
                  >
                    <span className={styles.kind} aria-hidden>
                      {KIND_GLYPH[e.kind]}
                    </span>
                    <span className={`mono ${styles.summary} ${dead ? styles.strike : ""}`}>
                      {summarize(e)}
                    </span>
                    <Badge tone={STATUS_TONE[e.status]} outline>
                      {STATUS_LABEL[e.status]}
                    </Badge>
                    <span className={`${styles.chev} ${open ? styles.chevOpen : ""}`}>▸</span>
                  </button>

                  <AnimatePresence initial={false}>
                    {open && (
                      <motion.div
                        key="d"
                        className={styles.detail}
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
                        style={{ overflow: "hidden" }}
                      >
                        <div className={styles.detailInner}>
                          {e.source_quote && (
                            <blockquote className={`mono ${styles.quote}`}>
                              “{e.source_quote}”
                            </blockquote>
                          )}
                          <div className={styles.confRow}>
                            <span className={styles.confBar}>
                              <span
                                className={styles.confFill}
                                style={{ width: `${Math.round(e.confidence * 100)}%` }}
                              />
                            </span>
                            <span className={`mono ${styles.confPct}`}>
                              {Math.round(e.confidence * 100)}% 把握
                            </span>
                          </div>
                          <div className={`mono ${styles.meta}`}>
                            <span>{layerLabel(e.source_layer)}</span>
                            <span>{fmtDateTime(e.applied_at ?? e.created_at)}</span>
                            {e.superseded_by && <span>↳ 被第 {e.superseded_by} 条换掉</span>}
                            {e.rejected_reason && <span>你没让记 · {e.rejected_reason}</span>}
                            <span className={styles.id}>#{e.id}</span>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
