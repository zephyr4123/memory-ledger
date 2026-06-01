import { AnimatePresence, motion } from "framer-motion";

import { fmtDateTime } from "../../lib/format";
import { displayValue, FIELD_LABEL, fieldLabel } from "../../lib/labels";
import type { Person } from "../../lib/types";
import styles from "./PersonCard.module.css";

const FIELD_KEYS: (keyof Person)[] = ["employer", "role", "location", "comm_pref", "relationship"];

interface Props {
  person: Person | null;
  asOf: string | null;
  collapsed: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onResolve: (intentId: number, action: "confirm" | "reject") => void;
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div className={styles.field}>
      <span className={styles.flabel}>{label}</span>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={String(value)}
          className={styles.fvalue}
          initial={{ opacity: 0, y: 6, filter: "blur(3px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -6, filter: "blur(3px)" }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
        >
          {value ?? <span className={styles.unset}>—</span>}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

function summaryLine(p: Person): string {
  const role =
    p.role && p.employer ? `${p.role} @ ${p.employer}` : p.role || p.employer || "";
  return [role, p.location].filter(Boolean).join(" · ");
}

export function PersonCard({ person, asOf, collapsed, onToggle, onEdit, onResolve }: Props) {
  if (!person) {
    return <div className={styles.empty}>选择一位联系人，查看小本为你记录的内容。</div>;
  }
  const past = asOf != null;
  return (
    <div className={`${styles.card} ${past ? styles.cardPast : ""}`}>
      <div className={styles.topline}>
        <button className={styles.toggle} onClick={onToggle} aria-expanded={!collapsed}>
          <span className="eyebrow">当前状态</span>
          <span className={`${styles.chev} ${collapsed ? styles.chevClosed : ""}`}>▾</span>
        </button>
        <div className={styles.toplineRight}>
          {past ? (
            <span className={`${styles.state} ${styles.statePast}`} title={asOf ?? undefined}>
              回溯至 {fmtDateTime(asOf)}
            </span>
          ) : (
            <span className={`${styles.state} ${styles.stateLive}`}>
              <i className={styles.liveDot} />
              当前
            </span>
          )}
          <button className={styles.editBtn} onClick={onEdit} title="编辑联系人">
            ✎
          </button>
        </div>
      </div>

      <AnimatePresence initial={false} mode="wait">
        {collapsed ? (
          <motion.div
            key="sum"
            className={styles.summary}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <span className={styles.sumName}>{person.full_name ?? "尚未命名"}</span>
            {summaryLine(person) && <span className={styles.sumRest}>{summaryLine(person)}</span>}
            {person.flags.length > 0 && (
              <span className={styles.sumFlag}>⚠ {person.flags.length}</span>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="full"
            className={styles.body}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          >
            <h1 className={`display ${styles.name}`}>{person.full_name ?? "尚未命名"}</h1>

            <div className={styles.fields}>
              {FIELD_KEYS.map((key) => {
                const raw = (person[key] as string | null) ?? null;
                return (
                  <Field
                    key={key}
                    label={FIELD_LABEL[key] ?? key}
                    value={raw == null ? null : displayValue(key, raw)}
                  />
                );
              })}
            </div>

            {!past && person.flags.length > 0 && (
              <div className={styles.flagList}>
                {person.flags.map((f, i) => (
                  <div key={f.intent_id ?? i} className={styles.flagItem}>
                    <span className={styles.flagIcon}>⚠</span>
                    <span className={styles.flagText}>
                      <b>{fieldLabel(f.target_field)}</b>
                      {f.flag_reason ? ` · ${f.flag_reason}` : " 此项尚待核实"}
                    </span>
                    {f.intent_id != null && (
                      <button
                        className={styles.flagDismiss}
                        onClick={() => onResolve(f.intent_id as number, "reject")}
                      >
                        知悉
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className={styles.provenance}>
              <span className={styles.count}>
                <i className={`${styles.cdot} ${styles.cFact}`} />
                <b>{person.assertions.length}</b> 条事实
              </span>
              <span className={styles.count}>
                <i className={`${styles.cdot} ${styles.cNote}`} />
                <b>{person.annotations.length}</b> 条备注
              </span>
              <span className={styles.count}>
                <i className={`${styles.cdot} ${styles.cFlag}`} />
                <b>{person.flags.length}</b> 处待核实
              </span>
              <span className={styles.synth}>
                由 {person.intents_applied_as_of.length} 条记录合成
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
