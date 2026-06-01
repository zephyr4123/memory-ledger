import { motion } from "framer-motion";

import styles from "./App.module.css";
import { ChatPanel } from "./features/chat/ChatPanel";
import { ContactList } from "./features/contacts/ContactList";
import { LedgerTimeline } from "./features/ledger/LedgerTimeline";
import { PersonCard } from "./features/person/PersonCard";
import { TimeScrubber } from "./features/timetravel/TimeScrubber";
import { useCrm } from "./hooks/useCrm";
import { Panel } from "./ui/Panel";

const enter = (delay: number) => ({
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] as const, delay },
});

export default function App() {
  const crm = useCrm();

  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <div className={styles.brand}>
          <span className={styles.mark}>◷</span>
          <span className={styles.wordmark}>
            memory<span className={styles.thin}>·</span>ledger
          </span>
          <span className={styles.tag}>chronograph</span>
        </div>
        <div className={styles.tagline}>
          deterministic memory for LLM agents — it asks before it rewrites your data
        </div>
      </header>

      <main className={styles.grid}>
        <motion.div className={styles.col} {...enter(0)}>
          <Panel label="contacts" className={styles.fill}>
            <ContactList
              people={crm.people}
              selectedId={crm.selectedId}
              onSelect={crm.setSelectedId}
            />
          </Panel>
        </motion.div>

        <motion.div className={styles.colCenter} {...enter(0.08)}>
          <Panel label="effective truth">
            <PersonCard person={crm.person} asOf={crm.asOf} />
            <div className={styles.scrubber}>
              <TimeScrubber ledger={crm.ledger} asOf={crm.asOf} onTravel={crm.travelTo} />
            </div>
          </Panel>
          <Panel label="ledger · provenance" className={styles.fill}>
            <LedgerTimeline events={crm.ledger} />
          </Panel>
        </motion.div>

        <motion.div className={`${styles.col} ${styles.chatCol}`} {...enter(0.16)}>
          <ChatPanel
            messages={crm.messages}
            banners={crm.banners}
            streaming={crm.streaming}
            llm={crm.health?.llm ?? null}
            model={crm.health?.model ?? null}
            hasContact={crm.selectedId != null}
            onSend={crm.sendTurn}
            onResolve={crm.resolveBanner}
          />
        </motion.div>
      </main>
    </div>
  );
}
