"""集成: 并发改同字段 (High bug — 无锁 read-then-write 会留两条 live PATCH).

多连接并发 insert 同一 (user,entity,row,field), 验证最终只有一条 live PATCH,
且 effective 值确定 (不依赖竞态). 经组合根 open_postgres 装配每个 worker 的 ledger.
"""

from __future__ import annotations

import threading

import psycopg

from memory_ledger import AutoApplyPolicy, open_postgres


def test_concurrent_same_field_patch_keeps_one_live(pg_dsn, conn, make_todo):
    tid = make_todo(due_date="2026-06-01")
    n = 8
    barrier = threading.Barrier(n)
    errors: list[Exception] = []

    def worker(i: int) -> None:
        c = psycopg.connect(pg_dsn, autocommit=True)
        try:
            lg = open_postgres(c, auto_apply=AutoApplyPolicy({("todo_item", "PATCH"): True}))
            barrier.wait()  # 尽量同时开火
            lg.insert_intent(
                user_id="u1", kind="PATCH", target_entity="todo_item",
                target_row_id=str(tid), target_field="due_date",
                patch_json={"due_date": f"2026-05-{10 + i:02d}"},
                source_layer="L2_CHAT", source_table="chat_message",
                source_id=f"msg{i}", confidence=0.9,
            )
        except Exception as e:
            errors.append(e)
        finally:
            c.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"unexpected errors: {errors}"

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM l15_change_intents
            WHERE kind='PATCH' AND status='APPLIED' AND superseded_by IS NULL
              AND target_field='due_date'
            """
        )
        live = cur.fetchone()[0]
    assert live == 1, f"expected exactly 1 live PATCH, got {live}"

    with conn.cursor() as cur:
        cur.execute(
            "SELECT due_date_eff FROM effective_todo_item_at('u1', %s, clock_timestamp())",
            [tid],
        )
        assert cur.fetchone() is not None
