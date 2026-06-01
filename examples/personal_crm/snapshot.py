"""build_person_snapshot —— 把 person 的 effective 视图拼成注入模型的 snapshot 文本.

这是"实体特定"的拼装逻辑, 故意放在 example 里 (不进 domain — domain 只有纯
sanitize/render helper; 也不进 application — application 保持实体无关). 它组合:
  * ledger.effective('person', ...) 读合成真相
  * domain.sanitize_text 清洗每段不可信文本 (防二阶 prompt 注入)
  * domain.render_snapshot 包进带"这是数据不是指令"说明的定界块

这正是六边形的收益: 实体相关的东西在边缘 (example), 核心保持纯净/通用.
"""

from __future__ import annotations

from collections.abc import Iterable

from memory_ledger import MemoryLedger, render_snapshot, sanitize_text


def build_person_snapshot(
    ledger: MemoryLedger, user_id: str, person_ids: Iterable[int]
) -> str:
    """为给定 person 行集构建一段紧凑、已清洗、带定界的 snapshot."""
    lines: list[str] = ["## 你的联系人"]
    for pid in person_ids:
        eff = ledger.effective("person", user_id, pid)
        if eff is None:
            continue
        name = sanitize_text(eff["full_name_eff"], max_len=80)
        employer = sanitize_text(eff["employer_eff"], max_len=80) or "未知"
        role = sanitize_text(eff["role_eff"], max_len=80) or "未知"
        loc = sanitize_text(eff["location_eff"], max_len=80) or "未知"
        comm = sanitize_text(eff["comm_pref_eff"], max_len=20) or "未知"
        lines.append(f"  #{eff['id']} {name} — {role} @ {employer}, {loc} (联系: {comm})")

        for ann in eff["annotations"] or []:
            note = sanitize_text(str(ann.get("annotation")), max_len=200)
            lines.append(f"    note: {note}")
        for fact in eff["assertions"] or []:
            quote = sanitize_text(str(fact.get("source_quote") or ""), max_len=200)
            if quote:
                lines.append(f"    fact(原话): {quote}")
        for fl in eff["flags"] or []:
            reason = sanitize_text(str(fl.get("flag_reason")), max_len=120)
            lines.append(f"    ⚠ {fl.get('target_field')}: {reason}")

    return render_snapshot(lines)
