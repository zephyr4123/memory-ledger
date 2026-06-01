import type { PersonListItem } from "../../lib/types";
import styles from "./ContactList.module.css";

interface Props {
  people: PersonListItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

function initials(name: string | null): string {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .map((s) => s[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function ContactList({ people, selectedId, onSelect }: Props) {
  return (
    <nav className={styles.list}>
      {people.map((p) => {
        const active = p.id === selectedId;
        const sub = [p.role, p.employer].filter(Boolean).join(" · ") || "—";
        return (
          <button
            key={p.id}
            className={`${styles.item} ${active ? styles.active : ""}`}
            onClick={() => onSelect(p.id)}
          >
            <span className={styles.avatar}>{initials(p.full_name)}</span>
            <span className={styles.meta}>
              <span className={styles.name}>{p.full_name ?? "Unnamed"}</span>
              <span className={styles.sub}>{sub}</span>
            </span>
          </button>
        );
      })}
      {people.length === 0 && <div className={styles.empty}>暂无联系人</div>}
    </nav>
  );
}
