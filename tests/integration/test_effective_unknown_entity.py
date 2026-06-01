"""集成: effective() 对未注册/非法实体抛稳定的领域错误, 不泄漏驱动错误."""

from __future__ import annotations

import pytest

from memory_ledger.ports.repository import UnknownEntityError


def test_unknown_entity_raises_typed_error(crm_ledger):
    # 语法合法但没有 effective_<x>_at 函数 → UnknownEntityError (非裸 psycopg 错误)
    with pytest.raises(UnknownEntityError) as ei:
        crm_ledger.effective("nope", "u1", 1)
    assert ei.value.entity == "nope"


def test_non_identifier_entity_raises_value_error(crm_ledger):
    # 非法标识符 (防注入) → ValueError, 早于任何 SQL
    with pytest.raises(ValueError):
        crm_ledger.effective("person; DROP TABLE person;--", "u1", 1)


def test_registered_entity_does_not_raise(crm_ledger, make_person):
    pid = make_person()
    assert crm_ledger.effective("person", "u1", pid) is not None
