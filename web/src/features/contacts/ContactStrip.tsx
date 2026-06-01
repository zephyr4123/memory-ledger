import type { PersonListItem } from "../../lib/types";
import styles from "./ContactStrip.module.css";

interface Props {
  people: PersonListItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onAdd: () => void;
}

function initials(name: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2);
  return parts
    .map((s) => s[0])
    .slice(0, 2)
    .join("");
}

/** 焦点联系人选择条 —— 点头像即切焦点, 驱动右侧真相/时光机/账本与本轮记忆默认对象。 */
export function ContactStrip({ people, selectedId, onSelect, onAdd }: Props) {
  return (
    <div className={styles.strip}>
      {people.map((p) => {
        const active = p.id === selectedId;
        return (
          <button
            key={p.id}
            className={`${styles.chip} ${active ? styles.active : ""}`}
            onClick={() => onSelect(p.id)}
            title={p.full_name ?? "未命名"}
          >
            <span className={styles.avatar}>{initials(p.full_name)}</span>
            <span className={styles.name}>{p.full_name ?? "未命名"}</span>
          </button>
        );
      })}
      <button className={styles.add} onClick={onAdd} title="加个联系人">
        <span className={styles.addPlus}>＋</span>
        <span className={styles.addLabel}>加人</span>
      </button>
    </div>
  );
}
