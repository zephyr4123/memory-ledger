import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import styles from "./Reasoning.module.css";

interface Props {
  text: string;
  live: boolean; // 本轮是否仍在流式
  answered: boolean; // 正文是否已开始 (开始作答 → 思考收起)
}

/** 深度思考过程 —— 折叠披露: 思考时自动展开live, 作答时自动收起, 用户可随时手动开合。 */
export function Reasoning({ text, live, answered }: Props) {
  const thinkingNow = live && !answered;
  const [open, setOpen] = useState(thinkingNow);
  const touched = useRef(false); // 用户一旦手动开合, 自动态就交还给用户(流式收尾不再强收)

  // 自动态: 正思考→展开, 一作答/结束→收起; 用户接管后不再覆盖
  useEffect(() => {
    if (!touched.current) setOpen(live && !answered);
  }, [live, answered]);

  if (!text) return null;
  return (
    <div className={`${styles.wrap} ${thinkingNow ? styles.active : ""}`}>
      <button
        className={styles.head}
        onClick={() => {
          touched.current = true;
          setOpen((o) => !o);
        }}
        aria-expanded={open}
      >
        <span className={styles.spark} aria-hidden>
          ✦
        </span>
        <span className={styles.label}>{thinkingNow ? "正在深度思考" : "深度思考过程"}</span>
        {thinkingNow && <span className={styles.pulse} aria-hidden />}
        <span className={`${styles.chev} ${open ? styles.chevOpen : ""}`} aria-hidden>
          ▸
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="b"
            className={styles.body}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div className={styles.text}>{text}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
