import { AnimatePresence, motion } from "framer-motion";

import { fmtDateTime } from "../../lib/format";
import type { Person } from "../../lib/types";
import { Badge } from "../../ui/Badge";
import styles from "./PersonCard.module.css";

const FIELDS: { key: keyof Person; label: string }[] = [
  { key: "employer", label: "Employer" },
  { key: "role", label: "Role" },
  { key: "location", label: "Location" },
  { key: "comm_pref", label: "Contact via" },
  { key: "relationship", label: "Relationship" },
];

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div className={styles.field}>
      <span className="eyebrow">{label}</span>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={String(value)}
          className={styles.value}
          initial={{ opacity: 0, y: 7, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -7, filter: "blur(4px)" }}
          transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
        >
          {value ?? <span className={styles.unset}>—</span>}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

export function PersonCard({ person, asOf }: { person: Person | null; asOf: string | null }) {
  if (!person) {
    return <div className={styles.empty}>select a contact to inspect its memory</div>;
  }
  const past = asOf != null;
  return (
    <div className={styles.card}>
      <div className={styles.topline}>
        <span className="eyebrow">contact · #{person.id}</span>
        {past ? (
          <Badge tone="amber" outline title={asOf ?? undefined}>
            truth as of {fmtDateTime(asOf)}
          </Badge>
        ) : (
          <Badge tone="accent" outline>
            ● live · now
          </Badge>
        )}
      </div>

      <h1 className={`display ${styles.name}`}>{person.full_name ?? "Unnamed"}</h1>

      <div className={styles.grid}>
        {FIELDS.map((f) => (
          <Field key={f.key} label={f.label} value={(person[f.key] as string | null) ?? null} />
        ))}
      </div>

      <div className={styles.provenance}>
        <Badge tone="accent">{person.assertions.length} facts</Badge>
        <Badge tone="dim">{person.annotations.length} notes</Badge>
        <Badge tone="amber">{person.flags.length} flags</Badge>
        <span className={styles.synth}>
          synthesized from {person.intents_applied_as_of.length} applied intents
        </span>
      </div>
    </div>
  );
}
