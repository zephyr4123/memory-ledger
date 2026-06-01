import type { ReactNode } from "react";

import styles from "./Badge.module.css";

export type Tone = "accent" | "amber" | "red" | "dim" | "violet";

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
