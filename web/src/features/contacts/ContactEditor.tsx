import { motion } from "framer-motion";
import { type FormEvent, useState } from "react";

import { COMM_PREF_LABEL } from "../../lib/labels";
import type { Person, PersonInput } from "../../lib/types";
import styles from "./ContactEditor.module.css";

interface Props {
  mode: "create" | "edit";
  person: Person | null;
  onClose: () => void;
  onSubmit: (data: PersonInput) => Promise<void>;
  onDelete?: () => Promise<void>;
}

const TEXT_FIELDS: { key: keyof PersonInput; label: string; ph: string }[] = [
  { key: "full_name", label: "姓名", ph: "TA 叫什么" },
  { key: "employer", label: "公司", ph: "在哪上班" },
  { key: "role", label: "职位", ph: "做什么的" },
  { key: "location", label: "在哪", ph: "在哪个城市" },
  { key: "relationship", label: "关系", ph: "你们怎么认识的" },
];
const ALL_KEYS = [
  "full_name", "employer", "role", "location", "comm_pref", "relationship",
] as const;
const COMM_OPTS = ["", "email", "phone", "sms"] as const;

export function ContactEditor({ mode, person, onClose, onSubmit, onDelete }: Props) {
  const init = (k: keyof PersonInput): string =>
    mode === "edit" && person ? ((person[k] as string | null) ?? "") : "";
  const [form, setForm] = useState<Record<string, string>>(() => ({
    full_name: init("full_name"),
    employer: init("employer"),
    role: init("role"),
    location: init("location"),
    comm_pref: init("comm_pref"),
    relationship: init("relationship"),
  }));
  const [confirmDel, setConfirmDel] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.full_name.trim() || busy) return;
    const data: PersonInput = {};
    for (const k of ALL_KEYS) {
      const v = form[k]?.trim();
      if (v) data[k] = v;
    }
    setBusy(true);
    try {
      await onSubmit(data);
    } catch {
      setBusy(false);
    }
  };

  const doDelete = async () => {
    if (!onDelete || busy) return;
    setBusy(true);
    try {
      await onDelete();
    } catch {
      setBusy(false);
    }
  };

  return (
    <motion.div
      className={styles.backdrop}
      onClick={onClose}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div
        className={styles.card}
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 12, scale: 0.98 }}
        transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className={styles.head}>
          <span className={`display ${styles.title}`}>
            {mode === "create" ? "加个联系人" : "编辑联系人"}
          </span>
          <button className={styles.close} onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>

        <form className={styles.form} onSubmit={submit}>
          {TEXT_FIELDS.map((f) => (
            <label key={f.key} className={styles.field}>
              <span className={styles.label}>{f.label}</span>
              <input
                className={styles.input}
                value={form[f.key] ?? ""}
                placeholder={f.ph}
                onChange={(e) => set(f.key, e.target.value)}
                autoFocus={f.key === "full_name"}
              />
            </label>
          ))}
          <label className={styles.field}>
            <span className={styles.label}>怎么联系</span>
            <select
              className={styles.input}
              value={form.comm_pref}
              onChange={(e) => set("comm_pref", e.target.value)}
            >
              {COMM_OPTS.map((o) => (
                <option key={o} value={o}>
                  {o === "" ? "—（不设）" : COMM_PREF_LABEL[o]}
                </option>
              ))}
            </select>
          </label>

          {mode === "edit" && (
            <p className={styles.hint}>改动会作为「你直接改的」记进账本、立刻生效。</p>
          )}

          <div className={styles.actions}>
            {mode === "edit" &&
              onDelete &&
              (confirmDel ? (
                <span className={styles.delConfirm}>
                  <span className={styles.delAsk}>删掉这人 + TA 全部记忆？</span>
                  <button type="button" className={styles.delYes} onClick={doDelete} disabled={busy}>
                    删
                  </button>
                  <button
                    type="button"
                    className={styles.delNo}
                    onClick={() => setConfirmDel(false)}
                  >
                    留着
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  className={styles.delBtn}
                  onClick={() => setConfirmDel(true)}
                >
                  删除
                </button>
              ))}
            <span className={styles.spacer} />
            <button type="button" className={styles.cancel} onClick={onClose}>
              取消
            </button>
            <button
              type="submit"
              className={styles.save}
              disabled={!form.full_name.trim() || busy}
            >
              {mode === "create" ? "创建" : "保存"}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}
