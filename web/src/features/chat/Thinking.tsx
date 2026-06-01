import styles from "./Thinking.module.css";

/** 等待小本回复时的专用加载态 —— 三点呼吸 + 一句"它在干嘛"。 */
export function Thinking({ label = "小本正在想" }: { label?: string }) {
  return (
    <span className={styles.wrap} aria-live="polite">
      <span className={styles.dots}>
        <i />
        <i />
        <i />
      </span>
      <span className={styles.label}>{label}…</span>
    </span>
  );
}
