"""person 实体的写策略 + 字段/值别名.

从 examples/personal_crm/policy.py 移植 —— api 是独立部署物, 自包含一份, 不反向
依赖 examples。语义不变: person 的低危三 kind (ASSERT/ANNOTATE/FLAG) auto-apply,
所有 PATCH 走人工确认 banner。别名让"company/works at/lives in"等口语归一到 canonical 列。
"""

from __future__ import annotations

from memory_ledger import AutoApplyPolicy

PERSON_ENTITY = "person"

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

VALUE_ALIASES: dict[str, dict[str, str]] = {
    "comm_pref": {
        # 英文口语
        "call": "phone",
        "calls": "phone",
        "phone_call": "phone",
        "mail": "email",
        "e-mail": "email",
        "text": "sms",
        "message": "sms",
        "dm": "sms",
        # 中文口语 → canonical enum (防止真 LLM 吐中文值撞 CHECK 约束)
        "邮件": "email",
        "邮箱": "email",
        "发邮件": "email",
        "电话": "phone",
        "打电话": "phone",
        "电话联系": "phone",
        "短信": "sms",
        "发短信": "sms",
        "微信": "sms",
        "消息": "sms",
    },
}


def crm_auto_apply_policy() -> AutoApplyPolicy:
    """person 的写风险矩阵: 低危三 kind auto-apply, PATCH 全部 banner-gated。"""
    return AutoApplyPolicy.low_risk_for([PERSON_ENTITY])
