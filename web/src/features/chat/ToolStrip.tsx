import { motion } from "framer-motion";

import { toolDisplay } from "../../lib/labels";
import type { ToolEvent } from "../../lib/types";
import styles from "./ToolStrip.module.css";

/** 小本本轮调过的工具回执 —— 让"它真在查/真在记"看得见。 */
export function ToolStrip({
  tools,
  nameOf,
}: {
  tools: ToolEvent[];
  nameOf: (id: number) => string;
}) {
  if (!tools.length) return null;
  return (
    <div className={styles.strip}>
      {tools.map((t) => {
        const d = toolDisplay(t, nameOf);
        return (
          <motion.span
            key={t.id}
            className={`${styles.chip} ${styles[t.status]}`}
            initial={{ opacity: 0, scale: 0.92, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
          >
            <span className={styles.icon}>{d.icon}</span>
            <span className={styles.label}>{d.label}</span>
            <span className={styles.tick}>
              {t.status === "running" ? (
                <span className={styles.spin} />
              ) : t.status === "error" ? (
                "✕"
              ) : (
                "✓"
              )}
            </span>
          </motion.span>
        );
      })}
    </div>
  );
}
