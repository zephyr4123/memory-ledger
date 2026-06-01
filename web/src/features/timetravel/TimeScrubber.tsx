import { motion } from "framer-motion";
import { useMemo } from "react";

import { fmtDateTime } from "../../lib/format";
import type { LedgerEvent } from "../../lib/types";
import styles from "./TimeScrubber.module.css";

interface Props {
  ledger: LedgerEvent[];
  asOf: string | null;
  onTravel: (at: string | null) => void;
}

/** 横向时间轴: 每个 tick = 记忆变动的一刻 (applied_at); 末端 = NOW。
 *  拖到哪一刻, 人卡就重合成那一刻的真相。 */
export function TimeScrubber({ ledger, asOf, onTravel }: Props) {
  const ticks = useMemo(() => {
    const ts = ledger.filter((e) => e.applied_at).map((e) => e.applied_at as string);
    return Array.from(new Set(ts)).sort();
  }, [ledger]);

  const n = ticks.length; // 位置 0..n-1 是 tick, n 是 NOW
  const index = asOf == null ? n : Math.max(ticks.indexOf(asOf), 0);
  const pct = n === 0 ? 100 : (index / n) * 100;

  const go = (i: number) => onTravel(i >= n ? null : ticks[i]);
  const step = (delta: number) => go(Math.min(Math.max(index + delta, 0), n));

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <span className="eyebrow">翻回那天</span>
        <span className={`${styles.readout} ${asOf ? styles.past : styles.now}`}>
          {asOf == null ? "● 现在" : fmtDateTime(asOf)}
        </span>
      </div>

      <div className={styles.controls}>
        <button
          className={styles.step}
          onClick={() => step(-1)}
          disabled={index <= 0}
          aria-label="earlier"
        >
          ‹
        </button>

        <div
          className={styles.track}
          role="slider"
          aria-valuenow={index}
          aria-valuemin={0}
          aria-valuemax={n}
        >
          <div className={styles.rail} />
          <motion.div
            className={styles.fill}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          />
          {ticks.map((t, i) => (
            <button
              key={t}
              className={`${styles.tick} ${i <= index ? styles.tickPast : ""}`}
              style={{ left: `${(i / (n || 1)) * 100}%` }}
              onClick={() => go(i)}
              title={fmtDateTime(t)}
              aria-label={`moment ${i + 1}`}
            />
          ))}
          <button
            className={`${styles.tick} ${styles.nowTick} ${index === n ? styles.tickOn : ""}`}
            style={{ left: "100%" }}
            onClick={() => go(n)}
            title="now"
            aria-label="now"
          />
          <motion.div
            className={styles.handle}
            animate={{ left: `${pct}%` }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          />
        </div>

        <button
          className={styles.step}
          onClick={() => step(1)}
          disabled={index >= n}
          aria-label="later"
        >
          ›
        </button>
      </div>

      <div className={styles.hint}>
        {n
          ? "拖一拖，看看 TA 那时候是什么样"
          : "还没有记录 —— 跟小本说点什么就有了"}
      </div>
    </div>
  );
}
