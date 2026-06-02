import { AnimatePresence, motion } from "framer-motion";
import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";

import type { ChatMessage } from "../../hooks/useCrm";
import { valueToText } from "../../lib/format";
import { displayValue, fieldLabel } from "../../lib/labels";
import type { Banner } from "../../lib/types";
import { Markdown } from "./Markdown";
import { Reasoning } from "./Reasoning";
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
  thinking: boolean;
  nameOf: (id: number) => string;
  onSend: (text: string) => void;
  onResolve: (intentId: number, action: "confirm" | "reject") => void;
  onToggleThinking: () => void;
  onScrolled?: (scrolled: boolean) => void;
}

const EXAMPLES = ["她升任了产品总监", "他已搬去深圳", "今后改用短信联系"];
const INPUT_MAX_PX = 168; // 输入框自动增高上限 (须与 .input / .composerCenter .input 的 max-height 一致)

/* 深度思考图标 —— 四角星火 + 一点, 表"推敲/灵光" */
function ThinkGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M8 1.5l1.25 3.25L12.5 6 9.25 7.25 8 10.5 6.75 7.25 3.5 6l3.25-1.25L8 1.5Z"
        fill="currentColor"
      />
      <circle cx="12.4" cy="11.6" r="1.4" fill="currentColor" />
    </svg>
  );
}

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
  // 思考块/工具条自身即活动指示; 仅当既无思考也无正文时, 才用三点呼吸兜底
  const showDots = !!m.streaming && !m.text && !m.reasoning;
  // 结束却无正文(只思考过/只调了工具) → 给一句占位, 不留"无答复死角"
  const noReply = !m.streaming && !m.text && (!!m.reasoning || tools.length > 0);
  return (
    <>
      {m.reasoning ? (
        <Reasoning text={m.reasoning} live={!!m.streaming} answered={!!m.text} />
      ) : null}
      {tools.length > 0 && <ToolStrip tools={tools} nameOf={nameOf} />}
      {m.text ? (
        <div className={styles.bubble}>
          <Markdown text={m.text} />
          {m.streaming && <span className={styles.caret} />}
        </div>
      ) : showDots ? (
        <div className={styles.bubble}>
          <Thinking label={busy ? "正在检索记忆" : "正在思考"} />
        </div>
      ) : noReply ? (
        <div className={styles.bubble}>
          <span className={styles.noReply}>（小本整理了思路，未给出文字结论）</span>
        </div>
      ) : null}
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
  thinking,
  nameOf,
  onSend,
  onResolve,
  onToggleThinking,
  onScrolled,
}: Props) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const live = llm === "live";
  const empty = messages.length === 0;

  // 顶栏柔影由对话滚动驱动; 用 ref 去抖 —— 仅在布尔翻转时上报, 避免每次 scroll 都触发父级 setState
  const scrolledRef = useRef(false);
  const reportScroll = useCallback(
    (v: boolean) => {
      if (v !== scrolledRef.current) {
        scrolledRef.current = v;
        onScrolled?.(v);
      }
    },
    [onScrolled],
  );

  // 滚到底 + 在同一处校准顶栏柔影态(切会话/迎接屏/短对话皆覆盖, 不再绑死在 empty 上)
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    reportScroll((scrollRef.current?.scrollTop ?? 0) > 4);
  }, [messages, banners, reportScroll]);

  // 自动增高: 随内容长高, 封顶 INPUT_MAX_PX (须与 CSS .input max-height 同步)
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, INPUT_MAX_PX)}px`;
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
        <div className={styles.toolbar}>
          <button
            type="button"
            className={`${styles.think} ${thinking ? styles.thinkOn : ""}`}
            onClick={onToggleThinking}
            aria-pressed={thinking}
            title={thinking ? "深度思考已开启 —— 小本会展示推敲过程" : "开启深度思考"}
          >
            <ThinkGlyph />
            <span>深度思考</span>
          </button>
          <button
            className={styles.send}
            type="submit"
            disabled={!draft.trim() || streaming || !canSend}
            aria-label="发送"
          >
            {streaming ? <span className={styles.sending} /> : "↑"}
          </button>
        </div>
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
          <div
            className={styles.scroll}
            ref={scrollRef}
            onScroll={(e) => reportScroll(e.currentTarget.scrollTop > 4)}
          >
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
