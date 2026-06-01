import { AnimatePresence, motion } from "framer-motion";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";

import type { ChatMessage } from "../../hooks/useCrm";
import { valueToText } from "../../lib/format";
import { displayValue, fieldLabel } from "../../lib/labels";
import type { Banner } from "../../lib/types";
import { Markdown } from "./Markdown";
import { Thinking } from "./Thinking";
import { ToolStrip } from "./ToolStrip";
import styles from "./ChatPanel.module.css";

interface Props {
  messages: ChatMessage[];
  banners: Banner[];
  streaming: boolean;
  llm: "live" | "mock" | null;
  model: string | null;
  canSend: boolean;
  nameOf: (id: number) => string;
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
        <span className={styles.gateLabel}>这条要改，先问问你</span>
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
          不改
        </button>
        <button className={styles.confirm} onClick={() => onResolve(banner.intent_id, "confirm")}>
          改吧
        </button>
      </div>
    </motion.div>
  );
}

function AgentBubble({ m, nameOf }: { m: ChatMessage; nameOf: Props["nameOf"] }) {
  const tools = m.tools ?? [];
  const busy = tools.some((t) => t.status === "running");
  return (
    <>
      {tools.length > 0 && <ToolStrip tools={tools} nameOf={nameOf} />}
      <div className={styles.bubble}>
        {m.text ? (
          <>
            <Markdown text={m.text} />
            {m.streaming && <span className={styles.caret} />}
          </>
        ) : m.streaming ? (
          <Thinking label={busy ? "小本正在翻记忆" : "小本正在想"} />
        ) : null}
      </div>
    </>
  );
}

export function ChatPanel({
  messages,
  banners,
  streaming,
  llm,
  model,
  canSend,
  nameOf,
  onSend,
  onResolve,
}: Props) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const live = llm === "live";

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, banners]);

  // 自动增高: 随内容长高, 封顶 140px (ChatGPT 式)
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [draft]);

  const submit = () => {
    const t = draft.trim();
    if (!t || streaming || !canSend) return;
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
        <span className={styles.title}>小本</span>
        <span className={`${styles.conn} ${live ? styles.connLive : ""}`}>
          <i className={styles.connDot} />
          <span>{live ? "在线" : "离线"}</span>
          <span className={`mono ${styles.model}`}>{live ? model : "未配置 LLM_API_KEY"}</span>
        </span>
      </header>

      <div className={styles.scroll} ref={scrollRef}>
        {messages.length === 0 && (
          <div className={styles.placeholder}>
            <p className={`display ${styles.phTitle}`}>随口说一句，小本替你记一笔</p>
            <p className={styles.phBody}>
              “她升产品总监了” · “搬去深圳了” · “以后发短信就行”
            </p>
            <p className={styles.phNote}>
              小本一边跟你搭话，一边自己翻本子查、把变化记下来;
              要改你写过的事，它会先停下来问你一句，你点头才改。
            </p>
          </div>
        )}
        {messages.map((m) => (
          <motion.div
            key={m.id}
            className={`${styles.msg} ${styles[m.role]}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          >
            <span className={styles.roleTag}>{m.role === "user" ? "你" : "小本"}</span>
            {m.role === "agent" ? (
              <AgentBubble m={m} nameOf={nameOf} />
            ) : (
              <div className={styles.bubble}>{m.text}</div>
            )}
          </motion.div>
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
        <div className={styles.inputWrap}>
          <textarea
            ref={taRef}
            className={styles.input}
            rows={1}
            placeholder={canSend ? "跟小本说一句…" : "正在准备…"}
            value={draft}
            disabled={!canSend || streaming}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
          />
          <button
            className={styles.send}
            type="submit"
            disabled={!draft.trim() || streaming || !canSend}
            aria-label="发送"
          >
            {streaming ? <span className={styles.sending} /> : "↑"}
          </button>
        </div>
      </form>
    </div>
  );
}
