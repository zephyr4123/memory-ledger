import { AnimatePresence, motion } from "framer-motion";

import { fmtDateTime } from "../../lib/format";
import { displayValue, FIELD_LABEL } from "../../lib/labels";
import type { Person } from "../../lib/types";
import styles from "./PersonCard.module.css";

const FIELD_KEYS: (keyof Person)[] = ["employer", "role", "location", "comm_pref", "relationship"];

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

export function PersonCard({ person, asOf }: { person: Person | null; asOf: string | null }) {
  if (!person) {
    return <div className={styles.empty}>选一个人，看看小本替你记下的。</div>;
  }
  const past = asOf != null;
  return (
    <div className={`${styles.card} ${past ? styles.cardPast : ""}`}>
      <div className={styles.topline}>
        <span className="eyebrow">TA 现在的样子</span>
        {past ? (
          <span className={`${styles.state} ${styles.statePast}`} title={asOf ?? undefined}>
            翻回 {fmtDateTime(asOf)}
          </span>
        ) : (
          <span className={`${styles.state} ${styles.stateLive}`}>
            <i className={styles.liveDot} />
            现在
          </span>
        )}
      </div>

      <h1 className={`display ${styles.name}`}>{person.full_name ?? "还没名字"}</h1>

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

      <div className={styles.provenance}>
        <span className={styles.count}>
          <i className={`${styles.cdot} ${styles.cFact}`} />
          <b>{person.assertions.length}</b> 条记录
        </span>
        <span className={styles.count}>
          <i className={`${styles.cdot} ${styles.cNote}`} />
          <b>{person.annotations.length}</b> 条备注
        </span>
        <span className={styles.count}>
          <i className={`${styles.cdot} ${styles.cFlag}`} />
          <b>{person.flags.length}</b> 处拿不准
        </span>
        <span className={styles.synth}>
          这些都是从 {person.intents_applied_as_of.length} 条记录拼出来的
        </span>
      </div>
    </div>
  );
}
