import type { PersonListItem } from "../../lib/types";
import styles from "./ContactStrip.module.css";

interface Props {
  people: PersonListItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onAdd: () => void;
}

// 6 枚植物印章拼在一张精灵图里 (3列×2行, 120px 缩放下每格 40×60, 圆心居中)。
// 按联系人 id 取一枚作头像 —— 无人像、稳定一致、零额外请求, 且每位联系人都能稳定见到自己那枚。
const SEAL_POS = ["-5px -15px", "-45px -15px", "-85px -15px", "-5px -75px", "-45px -75px", "-85px -75px"];
function sealStyle(id: number) {
  return {
    backgroundImage: "url(/img/brand/seals.png)",
    backgroundRepeat: "no-repeat",
    backgroundSize: "120px 120px",
    backgroundPosition: SEAL_POS[id % SEAL_POS.length],
  };
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
            <span className={styles.avatar} style={sealStyle(p.id)} aria-hidden />
            <span className={styles.name}>{p.full_name ?? "未命名"}</span>
          </button>
        );
      })}
      <button className={styles.add} onClick={onAdd} title="添加联系人">
        <span className={styles.addPlus}>＋</span>
        <span className={styles.addLabel}>添加</span>
      </button>
    </div>
  );
}
