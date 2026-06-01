import { AnimatePresence, motion } from "framer-motion";
import { type KeyboardEvent, useState } from "react";

import type { Conversation } from "../../lib/types";
import styles from "./ConversationList.module.css";

interface Props {
  conversations: Conversation[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  onRename: (id: number, title: string) => void;
  onDelete: (id: number) => void;
}

function relTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "";
  const min = Math.floor((Date.now() - t) / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day} 天前`;
  return new Date(t).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

export function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: Props) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [confirmId, setConfirmId] = useState<number | null>(null);

  const startEdit = (c: Conversation) => {
    setConfirmId(null);
    setEditingId(c.id);
    setDraft(c.title);
  };
  const commitEdit = (id: number) => {
    if (draft.trim()) onRename(id, draft);
    setEditingId(null);
  };
  const onEditKey = (e: KeyboardEvent<HTMLInputElement>, id: number) => {
    if (e.key === "Enter") commitEdit(id);
    else if (e.key === "Escape") setEditingId(null);
  };

  return (
    <div className={styles.wrap}>
      <button className={styles.new} onClick={onNew}>
        <span className={styles.newPlus}>＋</span>
        开个新话题
      </button>

      <nav className={styles.list}>
        <AnimatePresence initial={false}>
          {conversations.map((c) => {
            const active = c.id === activeId;
            const editing = c.id === editingId;
            const confirming = c.id === confirmId;
            return (
              <motion.div
                key={c.id}
                layout
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                className={`${styles.item} ${active ? styles.active : ""}`}
              >
                {editing ? (
                  <input
                    className={styles.edit}
                    autoFocus
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => onEditKey(e, c.id)}
                    onBlur={() => commitEdit(c.id)}
                  />
                ) : (
                  <button className={styles.body} onClick={() => onSelect(c.id)}>
                    <span className={styles.title}>{c.title || "新对话"}</span>
                    <span className={styles.meta}>
                      {relTime(c.updated_at)}
                      {c.message_count > 0 && ` · ${c.message_count} 条`}
                    </span>
                  </button>
                )}

                {!editing && !confirming && (
                  <span className={styles.actions}>
                    <button
                      className={styles.iconBtn}
                      title="改名"
                      onClick={() => startEdit(c)}
                    >
                      ✎
                    </button>
                    <button
                      className={styles.iconBtn}
                      title="删除"
                      onClick={() => setConfirmId(c.id)}
                    >
                      ✕
                    </button>
                  </span>
                )}

                {confirming && (
                  <span className={styles.confirm}>
                    <button className={styles.del} onClick={() => onDelete(c.id)}>
                      删
                    </button>
                    <button className={styles.keep} onClick={() => setConfirmId(null)}>
                      留
                    </button>
                  </span>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>

        {conversations.length === 0 && <div className={styles.empty}>还没有对话</div>}
      </nav>
    </div>
  );
}
