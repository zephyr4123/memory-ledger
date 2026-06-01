import type { ReactNode } from "react";

import styles from "./Panel.module.css";

interface PanelProps {
  label?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean;
  /** body 改为 flex 列容器, 自身不滚动 —— 内部内容(如固定头 + 滚动列表)自管布局。 */
  bodyFlow?: boolean;
}

/** 仪表台基础框: 暗面 + 细线边 + 角标注 + 可选 eyebrow 抬头。 */
export function Panel({ label, right, children, className, flush, bodyFlow }: PanelProps) {
  const body = flush ? styles.bodyFlush : bodyFlow ? styles.bodyFlow : styles.body;
  return (
    <section className={`${styles.panel} ${className ?? ""}`}>
      {(label || right) && (
        <header className={styles.head}>
          <span className="eyebrow">{label}</span>
          {right}
        </header>
      )}
      <div className={body}>{children}</div>
    </section>
  );
}
