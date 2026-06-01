import { AnimatePresence, motion } from "framer-motion";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";

import type { ChatMessage } from "../../hooks/useCrm";
import { valueToText } from "../../lib/format";
import type { Banner } from "../../lib/types";
import { Badge } from "../../ui/Badge";
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

function GateBanner({ banner, onResolve }: { banner: Banner; onResolve: Props["onResolve"] }) {
  return (
    <motion.div
      className={styles.gate}
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.98 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className={styles.gateHead}>
        <span className={styles.gateGlyph}>⟳</span>
        <span className="eyebrow">confirm before write</span>
        <span className={styles.gateConf}>{Math.round(banner.confidence * 100)}%</span>
      </div>
      <div className={styles.gateBody}>
        <span className={styles.gateField}>{banner.target_field}</span>
        <span className={styles.gateArrow}>→</span>
        <span className={styles.gateValue}>{valueToText(banner.proposed_value)}</span>
      </div>
      <div className={styles.gateActions}>
        <button className={styles.reject} onClick={() => onResolve(banner.intent_id, "reject")}>
          Reject
        </button>
        <button className={styles.confirm} onClick={() => onResolve(banner.intent_id, "confirm")}>
          Confirm
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
        <div className={styles.title}>
          <span className={styles.dot} data-live={llm === "live"} />
          <span>agent</span>
        </div>
        <Badge tone={llm === "live" ? "accent" : "dim"} outline>
          {llm === "live" ? `live · ${model ?? ""}` : "mock — set ANTHROPIC_API_KEY"}
        </Badge>
      </header>

      <div className={styles.scroll} ref={scrollRef}>
        {messages.length === 0 && (
          <div className={styles.placeholder}>
            <p className={`display ${styles.phTitle}`}>Tell the agent something.</p>
            <p className={styles.phBody}>
              “she moved to Stripe” · “her title is now Director” · “she prefers texts”.
              <br />
              The agent replies and proposes structured changes — high-risk edits wait for your
              confirmation before they touch the record.
            </p>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`${styles.msg} ${styles[m.role]}`}>
            <span className={styles.roleTag}>{m.role === "user" ? "you" : "agent"}</span>
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
          placeholder={hasContact ? "message the agent…" : "select a contact first"}
          value={draft}
          disabled={!hasContact || streaming}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKey}
        />
        <button
          className={styles.send}
          type="submit"
          disabled={!draft.trim() || streaming || !hasContact}
          aria-label="send"
        >
          {streaming ? "…" : "↵"}
        </button>
      </form>
    </div>
  );
}
