"""冻结的 Personal-CRM 对话脚本 (6 个 ScriptedTurn, 演一段 9 步的叙事).

每个 ScriptedTurn = (utterance, Extraction). Extraction 是预烘焙的"模型输出"
(reply + 想写的 intent), 由 MockExtractor 按轮号取出 —— 全程确定性、零模型调用.
叙事里的 "yes"/"why?"/"show me" 这几步不产生新 intent (是确认/读-only), 故不作为
独立 ScriptedTurn, 而由 confirm_after / 演示侧读取体现 —— 所以是 6 个脚本轮.

设计要点:
  * 每轮 source_id 唯一 (m1..m9): 既是幂等键, 也是溯源反查键.
  * source_quote 都是 utterance 的 **逐字子串** (不 paraphrase), 证明 §9 的原话规则.
  * 演三幕: 改 employer (Acme→Globex, supersede) / 溯源 / location 待确认-banner 再拒绝.

注意: 本脚本只负责"模型想写什么". 是否 auto-apply、是否进 banner, 由 ledger 的
AutoApplyPolicy 决定 (PATCH 一律 banner). confirm/reject 由 run_demo 编排 (模拟用户拍板).
"""

from __future__ import annotations

from dataclasses import dataclass

from memory_ledger.domain.extraction import Extraction, ProposedIntent


@dataclass(frozen=True, slots=True)
class ScriptedTurn:
    source_id: str          # 本轮消息 id (幂等 + 溯源键)
    utterance: str          # 用户原话
    extraction: Extraction  # 预烘焙的模型产物
    # 演示编排提示 (run_demo 用; 不影响 ledger):
    confirm_after: bool = False  # 本轮结束模拟用户点"采纳"上一/本轮的 PATCH
    reject_field: str | None = None  # 本轮拒绝某字段的待确认 PATCH


def _assert(quote: str, **payload: object) -> ProposedIntent:
    return ProposedIntent(
        kind="ASSERT", target_entity="person", target_row_id="1",
        patch_json=dict(payload), source_quote=quote, confidence=0.92,
    )


def _patch(field: str, value: object, quote: str, confidence: float = 0.9) -> ProposedIntent:
    return ProposedIntent(
        kind="PATCH", target_entity="person", target_row_id="1",
        target_field=field, patch_json={field: value},
        source_quote=quote, confidence=confidence,
    )


def _annotate(text: str, quote: str) -> ProposedIntent:
    return ProposedIntent(
        kind="ANNOTATE", target_entity="person", target_row_id="1",
        patch_json={"annotation": text}, source_quote=quote, confidence=0.95,
    )


def _flag(field: str, reason: str) -> ProposedIntent:
    return ProposedIntent(
        kind="FLAG", target_entity="person", target_row_id="1",
        target_field=field, patch_json={"flag_reason": reason},
        source_quote=None, confidence=0.7,
    )


# person 行的初始 seed (run_demo 建表后插入, 模拟 turn 1 之前已存在的联系人骨架)
SEED_PERSON = {
    "full_name": "Sarah Lin",
    "employer": "Acme Corp",
    "role": "PM",
    "location": "San Francisco",
    "comm_pref": "email",
}


TRANSCRIPT: tuple[ScriptedTurn, ...] = (
    ScriptedTurn(
        source_id="m1",
        utterance=(
            "Add Sarah Lin — senior PM at Acme Corp in San Francisco, "
            "prefers email over calls."
        ),
        extraction=Extraction(
            reply="Got it — saved Sarah Lin, senior PM at Acme Corp, SF, email-first.",
            intents=(
                _assert(
                    "senior PM at Acme Corp",
                    role="senior PM", employer="Acme Corp",
                ),
            ),
        ),
    ),
    ScriptedTurn(
        source_id="m2",
        utterance="Log it properly — she just started at Acme.",
        extraction=Extraction(
            reply="I'd like to update her employer to 'Acme'. Confirm?",
            intents=(
                _patch("employer", "Acme", "she just started at Acme", confidence=0.9),
                _assert("she just started at Acme", employer="Acme"),
            ),
        ),
        confirm_after=True,  # turn 3 'yes' — 采纳 employer→Acme
    ),
    ScriptedTurn(
        source_id="m4",
        utterance="Note she's juggling two roles right now, might be slow to reply.",
        extraction=Extraction(
            reply="Noted.",
            intents=(
                _annotate(
                    "juggling two roles, may be slow to reply",
                    "she's juggling two roles right now, might be slow to reply",
                ),
            ),
        ),
    ),
    ScriptedTurn(
        source_id="m5",
        utterance="Update: she moved to Globex.",
        extraction=Extraction(
            reply="Update her employer to 'Globex'? Confirm.",
            intents=(
                _patch("employer", "Globex", "she moved to Globex", confidence=0.93),
                _assert("she moved to Globex", employer="Globex"),
            ),
        ),
        confirm_after=True,  # 采纳 employer→Globex (触发 supersede Acme)
    ),
    ScriptedTurn(
        source_id="m6",
        utterance="I think she relocated to Berlin?",
        extraction=Extraction(
            reply=(
                "You're unsure — I'll hold a pending change of location to "
                "'Berlin' for your confirmation."
            ),
            intents=(
                _patch("location", "Berlin", "I think she relocated to Berlin", confidence=0.55),
                _flag("location", "unconfirmed relocation"),
            ),
        ),
        # 故意不 confirm — 这一轮留一个 pending banner
    ),
    ScriptedTurn(
        source_id="m9",
        utterance="No, she's still in SF, drop the Berlin thing.",
        extraction=Extraction(
            reply="Done — discarded the Berlin relocation; she stays in San Francisco.",
            intents=(),  # 纯拒绝, 不写新 intent
        ),
        reject_field="location",  # 拒绝 turn m6 的 location PATCH
    ),
)
