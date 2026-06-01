"""person 实体的 auto-apply 策略 + 字段/值别名 (纯数据, 喂给 MemoryLedger).

策略: ASSERT/ANNOTATE/FLAG 低危 auto-apply; 所有 PATCH 走 banner (矩阵默认拒),
即使 confidence=1.0 也等用户确认 —— "改用户业务数据" 一律高危.

别名: LLM 常吐 'company'/'works at'/'city' 等同义词与口语 enum 值; normalize_intent
据此把它们规范回 canonical 列名/值, 避免撞 target_field / comm_pref 的 CHECK.
"""

from __future__ import annotations

from memory_ledger import AutoApplyPolicy

PERSON_ENTITY = "person"


def crm_auto_apply_policy() -> AutoApplyPolicy:
    """person 的写风险矩阵: 低危三 kind auto-apply, PATCH 全部 banner-gated."""
    return AutoApplyPolicy.low_risk_for([PERSON_ENTITY])


# LLM 易吐的字段别名 → canonical person 列名
FIELD_ALIASES: dict[str, str] = {
    "company": "employer",
    "works_at": "employer",
    "workplace": "employer",
    "org": "employer",
    "organization": "employer",
    "employer_name": "employer",
    "title": "role",
    "job": "role",
    "job_title": "role",
    "position": "role",
    "city": "location",
    "lives_in": "location",
    "based_in": "location",
    "locale": "location",
    "where": "location",
    "contact_pref": "comm_pref",
    "preferred_contact": "comm_pref",
    "reach_via": "comm_pref",
    "channel": "comm_pref",
    "name": "full_name",
    "fullname": "full_name",
    "rel": "relationship",
    "how_we_met": "relationship",
    "connection": "relationship",
}

# comm_pref 的口语值 → CHECK 允许的 canonical enum
VALUE_ALIASES: dict[str, dict[str, str]] = {
    "comm_pref": {
        "call": "phone",
        "calls": "phone",
        "phone_call": "phone",
        "mail": "email",
        "e-mail": "email",
        "text": "sms",
        "message": "sms",
        "dm": "sms",
    },
}
