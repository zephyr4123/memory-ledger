import type { ReactNode } from "react";

import styles from "./Badge.module.css";

/* 颜色纪律: sage = 活/真相, clay = 待签/留意, danger = 拒绝, dim = 中性。
   clay 在全站只作轮廓徽章 (PROPOSED / flag) 出现; 唯一的"实心陶土块"是确认闸门本体。 */
export type Tone = "sage" | "clay" | "danger" | "dim";

interface BadgeProps {
  children: ReactNode;
  tone?: Tone;
  outline?: boolean;
  title?: string;
}

export function Badge({ children, tone = "dim", outline = false, title }: BadgeProps) {
  return (
    <span
      className={`${styles.badge} ${styles[tone]} ${outline ? styles.outline : ""}`}
      title={title}
    >
      {children}
    </span>
  );
}
