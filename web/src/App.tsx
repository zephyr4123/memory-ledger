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
import { Panel } from "./ui/Panel";

const enter = (delay: number) => ({
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] as const, delay },
});

export default function App() {
  const crm = useCrm();
  const live = crm.health?.llm === "live";
  const nameOf = (id: number) => crm.people.find((p) => p.id === id)?.full_name ?? "联系人";

  const [editor, setEditor] = useState<null | { mode: "create" | "edit" }>(null);
  const [snapOpen, setSnapOpen] = useState(true);

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
          className={styles.topbar}
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className={styles.brand}>
            <span className={styles.wordmark}>
              念念手记<span className={styles.glyph}>✎</span>
            </span>
            <span className={styles.tagline}>你说，小本替你记；要改之前先问你一句</span>
          </div>
          <div className={`${styles.status} ${live ? styles.statusLive : ""}`}>
            <span className={styles.statusDot} />
            {live ? "小本在线" : "离线"}
          </div>
        </motion.header>

        <main className={styles.grid}>
          <motion.div className={styles.col} {...enter(0.05)}>
            <Panel label="对话" className={styles.fill}>
              <ConversationList
                conversations={crm.conversations}
                activeId={crm.activeConvId}
                onSelect={crm.selectConversation}
                onNew={crm.newConversation}
                onRename={crm.renameConversation}
                onDelete={crm.deleteConversation}
              />
            </Panel>
          </motion.div>

          <motion.div className={styles.colCenter} {...enter(0.12)}>
            <div className={styles.strip}>
              <ContactStrip
                people={crm.people}
                selectedId={crm.selectedId}
                onSelect={crm.setSelectedId}
                onAdd={() => setEditor({ mode: "create" })}
              />
            </div>
            <Panel flush className={styles.truth}>
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
            </Panel>
            <Panel label="记过的事" className={`${styles.fill} ${styles.ledgerPanel}`} bodyFlow>
              <LedgerTimeline events={crm.ledger} />
            </Panel>
          </motion.div>

          <motion.div className={`${styles.col} ${styles.chatCol}`} {...enter(0.19)}>
            <ChatPanel
              messages={crm.messages}
              banners={crm.banners}
              streaming={crm.streaming}
              llm={crm.health?.llm ?? null}
              model={crm.health?.model ?? null}
              canSend={crm.activeConvId != null}
              nameOf={nameOf}
              onSend={crm.sendTurn}
              onResolve={crm.resolveBanner}
            />
          </motion.div>
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
