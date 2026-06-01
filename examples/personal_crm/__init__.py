"""Personal-CRM 参考应用 —— memory-ledger 的可跑示例.

不随 wheel 发布 (repo / sdist only). 演示三大差异化:
  * 确定性 as-of 时光机 (Sarah 的 employer: Acme → Globex, 任意时点可回看)
  * 逐字 source_quote 溯源 ("你怎么知道她在 Acme — 因为你那天说了这句原话")
  * 高危 PATCH 人工确认 banner (改 employer/location 走 PROPOSED, 等用户拍板/拒绝)

全程确定性、离线、零 API key: MockExtractor 是脚本化的 turn 表, 不调任何模型.
"""

from __future__ import annotations
