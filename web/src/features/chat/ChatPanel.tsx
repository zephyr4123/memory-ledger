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
  focusName: string | null;
  nameOf: (id: number) => string;
  onSend: (text: string) => void;
  onResolve: (intentId: number, action: "confirm" | "reject") => void;
}

const EXAMPLES = ["她升任了产品总监", "他已搬去深圳", "今后改用短信联系"];

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "夜深了";
  if (h < 11) return "上午好";
  if (h < 13) return "午安";
  if (h < 18) return "下午好";
  if (h < 23) return "晚上好";
  return "夜深了";
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
        <span className={styles.gateLabel}>此项更改需经你确认</span>
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
          暂不
        </button>
        <button className={styles.confirm} onClick={() => onResolve(banner.intent_id, "confirm")}>
          确认更改
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
          <Thinking label={busy ? "正在检索记忆" : "正在思考"} />
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
  focusName,
  nameOf,
  onSend,
  onResolve,
}: Props) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const live = llm === "live";
  const empty = messages.length === 0;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, banners]);

  // 自动增高: 随内容长高, 封顶 140px (ChatGPT 式)
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [draft, empty]);

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
  const fillExample = (text: string) => {
    setDraft(text);
    taRef.current?.focus();
  };

  // 输入条本体 —— 居中(新对话)与沉底(对话中)两处共用同一份, 由 layoutId 平滑过渡。
  const composer = (
    <form className={styles.composerForm} onSubmit={onFormSubmit}>
      <div className={styles.inputWrap}>
        <textarea
          ref={taRef}
          className={styles.input}
          rows={1}
          placeholder={canSend ? "向小本讲述…" : "正在准备…"}
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
  );

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <span className={styles.title}>小本</span>
        {focusName && (
          <span className={styles.focus}>
            关于<b className={styles.focusName}>{focusName}</b>
          </span>
        )}
        <span className={`${styles.conn} ${live ? styles.connLive : ""}`}>
          <i className={styles.connDot} />
          <span>{live ? "在线" : "离线"}</span>
          <span className={`mono ${styles.model}`}>{live ? model : "未配置 LLM_API_KEY"}</span>
        </span>
      </header>

      {empty ? (
        // ── 新对话: 整体居中的迎接屏 (Claude 式) ──
        <div className={styles.landing}>
          <motion.div
            className={styles.hero}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1], delay: 0.05 }}
          >
            <p className={styles.greeting}>{greeting()}</p>
            <h1 className={`display ${styles.heroTitle}`}>讲述近况，小本为你逐一记录</h1>
          </motion.div>

          <motion.div className={styles.composerCenter} layoutId="composer">
            {composer}
          </motion.div>

          <motion.div
            className={styles.chips}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay: 0.22 }}
          >
            {EXAMPLES.map((ex) => (
              <button key={ex} className={styles.chip} onClick={() => fillExample(ex)}>
                {ex}
              </button>
            ))}
          </motion.div>
        </div>
      ) : (
        // ── 对话中: 消息流 + 闸门 + 沉底输入条 ──
        <>
          <div className={styles.scroll} ref={scrollRef}>
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

          <motion.div className={styles.composerBottom} layoutId="composer">
            {composer}
          </motion.div>
        </>
      )}
    </div>
  );
}
