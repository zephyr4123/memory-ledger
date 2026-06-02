import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import { useState } from "react";

import styles from "./App.module.css";
import { ChatPanel } from "./features/chat/ChatPanel";
import { ContactEditor } from "./features/contacts/ContactEditor";
import { ContactStrip } from "./features/contacts/ContactStrip";
import { ConversationList } from "./features/conversations/ConversationList";
import { LedgerTimeline } from "./features/ledger/LedgerTimeline";
import { PersonCard } from "./features/person/PersonCard";
import { TimeScrubber } from "./features/timetravel/TimeScrubber";
import { useCrm } from "./hooks/useCrm";
import type { PersonInput } from "./lib/types";

/* 两个面板开合图标 —— 与 Claude 顶栏同构: 左收会话列表, 右收记忆栏 */
function IconPanelLeft() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <rect x="2.25" y="3.25" width="13.5" height="11.5" rx="2.5" stroke="currentColor" strokeWidth="1.5" />
      <line x1="7" y1="3.75" x2="7" y2="14.25" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
function IconPanelRight() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <rect x="2.25" y="3.25" width="13.5" height="11.5" rx="2.5" stroke="currentColor" strokeWidth="1.5" />
      <line x1="11" y1="3.75" x2="11" y2="14.25" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export default function App() {
  const crm = useCrm();
  const live = crm.health?.llm === "live";
  const nameOf = (id: number) => crm.people.find((p) => p.id === id)?.full_name ?? "联系人";
  const focusName = crm.selectedId != null ? nameOf(crm.selectedId) : null;

  const [editor, setEditor] = useState<null | { mode: "create" | "edit" }>(null);
  const [snapOpen, setSnapOpen] = useState(true);
  const [navOpen, setNavOpen] = useState(true);
  const [memOpen, setMemOpen] = useState(true);
  const [chatScrolled, setChatScrolled] = useState(false);

  const submitContact = async (data: PersonInput) => {
    if (editor?.mode === "edit" && crm.selectedId != null) {
      await crm.updateContact(crm.selectedId, data);
    } else {
      await crm.createContact(data);
    }
    setEditor(null);
  };
  const removeContact = async () => {
    if (crm.selectedId != null) await crm.deleteContact(crm.selectedId);
    setEditor(null);
  };

  return (
    <MotionConfig reducedMotion="user">
      <div className={styles.shell}>
        <motion.header
          className={`${styles.topbar} ${chatScrolled ? styles.topbarScrolled : ""}`}
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className={styles.topLeft}>
            <button
              className={`${styles.railToggle} ${navOpen ? styles.railToggleOn : ""}`}
              onClick={() => setNavOpen((o) => !o)}
              title={navOpen ? "收起会话列表" : "展开会话列表"}
              aria-pressed={navOpen}
            >
              <IconPanelLeft />
            </button>
            <span className={styles.wordmark}>
              念念手记<span className={styles.glyph}>✎</span>
            </span>
            <span className={styles.tagline}>你讲述，小本为你记录；修改既有信息前，先经你确认</span>
          </div>

          <div className={styles.topRight}>
            <span className={`${styles.status} ${live ? styles.statusLive : ""}`}>
              <span className={styles.statusDot} />
              {live ? "小本在线" : "离线"}
            </span>
            <button
              className={`${styles.railToggle} ${styles.memToggle} ${memOpen ? styles.railToggleOn : ""}`}
              onClick={() => setMemOpen((o) => !o)}
              title={memOpen ? "收起记忆栏" : "展开记忆栏"}
              aria-pressed={memOpen}
            >
              <IconPanelRight />
              <span className={styles.memToggleLabel}>记忆</span>
            </button>
          </div>
        </motion.header>

        <main className={styles.main}>
          {/* ── 左: 会话列表 (可折叠) ── */}
          <aside className={styles.navRail} data-open={navOpen}>
            <div className={styles.navInner}>
              <ConversationList
                conversations={crm.conversations}
                activeId={crm.activeConvId}
                onSelect={crm.selectConversation}
                onNew={crm.newConversation}
                onRename={crm.renameConversation}
                onDelete={crm.deleteConversation}
              />
            </div>
          </aside>

          {/* ── 中: 对话主舞台 (开放画布, 不再是卡片) ── */}
          <section className={styles.stage}>
            <ChatPanel
              messages={crm.messages}
              banners={crm.banners}
              streaming={crm.streaming}
              llm={crm.health?.llm ?? null}
              model={crm.health?.model ?? null}
              canSend={crm.ready}
              focusName={focusName}
              thinking={crm.thinking}
              nameOf={nameOf}
              onSend={crm.sendTurn}
              onResolve={crm.resolveBanner}
              onToggleThinking={crm.toggleThinking}
              onScrolled={setChatScrolled}
            />
          </section>

          {/* ── 右: 记忆栏 (可折叠) —— 一条连续列, 发丝线分段, 无独立卡片 ── */}
          <aside className={styles.memRail} data-open={memOpen}>
            <div className={styles.memInner}>
              <div className={styles.memHead}>
                <span className="eyebrow">记忆</span>
                <span className={styles.memHint}>小本为你存留的人与事</span>
              </div>

              <div className={styles.strip}>
                <ContactStrip
                  people={crm.people}
                  selectedId={crm.selectedId}
                  onSelect={crm.setSelectedId}
                  onAdd={() => setEditor({ mode: "create" })}
                />
              </div>

              <div className={styles.seam} />

              <div className={styles.personSection}>
                <PersonCard
                  person={crm.person}
                  asOf={crm.asOf}
                  collapsed={!snapOpen}
                  onToggle={() => setSnapOpen((o) => !o)}
                  onEdit={() => setEditor({ mode: "edit" })}
                  onResolve={crm.resolveBanner}
                />
                {snapOpen && crm.person && (
                  <div className={styles.scrubber}>
                    <TimeScrubber ledger={crm.ledger} asOf={crm.asOf} onTravel={crm.travelTo} />
                  </div>
                )}
              </div>

              <div className={styles.seam} />

              <div className={styles.ledgerSection}>
                <div className={styles.ledgerHead}>
                  <span className="eyebrow">变更记录</span>
                </div>
                <LedgerTimeline events={crm.ledger} />
              </div>
            </div>
          </aside>
        </main>
      </div>

      <AnimatePresence>
        {editor && (
          <ContactEditor
            mode={editor.mode}
            person={editor.mode === "edit" ? crm.person : null}
            onClose={() => setEditor(null)}
            onSubmit={submitContact}
            onDelete={editor.mode === "edit" ? removeContact : undefined}
          />
        )}
      </AnimatePresence>
    </MotionConfig>
  );
}
