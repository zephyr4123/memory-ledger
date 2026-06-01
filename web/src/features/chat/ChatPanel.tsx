import { AnimatePresence, motion } from "framer-motion";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";

import type { ChatMessage } from "../../hooks/useCrm";
import { valueToText } from "../../lib/format";
import { displayValue, fieldLabel } from "../../lib/labels";
import type { Banner } from "../../lib/types";
import styles from "./ChatPanel.module.css";

interface Props {
  messages: ChatMessage[];
  banners: Banner[];
  streaming: boolean;
  llm: "live" | "mock" | null;
  model: string | null;
  hasContact: boolean;
  onSend: (text: string) => void;
  onResolve: (intentId: number, action: "confirm" | "reject") => void;
}

/* 确认闸门 —— 全站唯一的"实心陶土块": 高危改动落盘前, 等你签字。 */
function GateBanner({ banner, onResolve }: { banner: Banner; onResolve: Props["onResolve"] }) {
  return (
    <motion.div
      className={styles.gate}
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.98 }}
      transition={{ duration: 0.34, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className={styles.gateHead}>
        <span className={styles.gateGlyph}>✎</span>
        <span className={styles.gateLabel}>落盘前请确认</span>
        <span className={styles.gateConf}>{Math.round(banner.confidence * 100)}%</span>
      </div>
      <div className={styles.gateBody}>
        <span className={styles.gateField}>{fieldLabel(banner.target_field)}</span>
        <span className={styles.gateArrow}>→</span>
        <span className={`mono ${styles.gateValue}`}>
          {displayValue(banner.target_field, valueToText(banner.proposed_value))}
        </span>
      </div>
      <div className={styles.gateActions}>
        <button className={styles.reject} onClick={() => onResolve(banner.intent_id, "reject")}>
          驳回
        </button>
        <button className={styles.confirm} onClick={() => onResolve(banner.intent_id, "confirm")}>
          确认
        </button>
      </div>
    </motion.div>
  );
}

export function ChatPanel({
  messages,
  banners,
  streaming,
  llm,
  model,
  hasContact,
  onSend,
  onResolve,
}: Props) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const live = llm === "live";

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, banners]);

  const submit = () => {
    const t = draft.trim();
    if (!t || streaming || !hasContact) return;
    onSend(t);
    setDraft("");
  };
  const onFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <span className={styles.title}>智能体</span>
        <span className={`${styles.conn} ${live ? styles.connLive : ""}`}>
          <i className={styles.connDot} />
          <span>{live ? "在线" : "离线"}</span>
          <span className={`mono ${styles.model}`}>{live ? model : "未配置 LLM_API_KEY"}</span>
        </span>
      </header>

      <div className={styles.scroll} ref={scrollRef}>
        {messages.length === 0 && (
          <div className={styles.placeholder}>
            <p className={`display ${styles.phTitle}`}>跟智能体说点什么。</p>
            <p className={styles.phBody}>
              “她升任产品总监了” · “她搬去了深圳” · “以后短信联系她就行”。
            </p>
            <p className={styles.phNote}>
              智能体会即时回复你，并把其中的变动整理成结构化记录 ——
              高危改动会先停在确认闸门，等你点头才真正落盘。
            </p>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`${styles.msg} ${styles[m.role]}`}>
            <span className={styles.roleTag}>{m.role === "user" ? "你" : "智能体"}</span>
            <div className={styles.bubble}>
              {m.text}
              {m.streaming && <span className={styles.caret} />}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.gates}>
        <AnimatePresence>
          {banners.map((b) => (
            <GateBanner key={b.intent_id} banner={b} onResolve={onResolve} />
          ))}
        </AnimatePresence>
      </div>

      <form className={styles.composer} onSubmit={onFormSubmit}>
        <textarea
          className={styles.input}
          rows={1}
          placeholder={hasContact ? "和智能体说点什么…" : "请先选择一位联系人"}
          value={draft}
          disabled={!hasContact || streaming}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKey}
        />
        <button
          className={styles.send}
          type="submit"
          disabled={!draft.trim() || streaming || !hasContact}
          aria-label="发送"
        >
          {streaming ? "…" : "↑"}
        </button>
      </form>
    </div>
  );
}
