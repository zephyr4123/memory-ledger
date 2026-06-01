import type { ReactNode } from "react";

import styles from "./Panel.module.css";

interface PanelProps {
  label?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean;
}

/** 仪表台基础框: 暗面 + 细线边 + 角标注 + 可选 eyebrow 抬头。 */
export function Panel({ label, right, children, className, flush }: PanelProps) {
  return (
    <section className={`${styles.panel} ${className ?? ""}`}>
      {(label || right) && (
        <header className={styles.head}>
          <span className="eyebrow">{label}</span>
          {right}
        </header>
      )}
      <div className={flush ? styles.bodyFlush : styles.body}>{children}</div>
    </section>
  );
}
