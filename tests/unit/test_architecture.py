"""单元: 架构依赖规则守护 (无需 DB).

六边形架构的价值全靠"依赖单向"这条铁律. 这组测试用静态 AST 扫描 import,
在 CI 里把铁律变成可执行断言 —— 谁违反分层, 测试就红. 这是让架构"每一次都
保持"而不是慢慢腐烂的关键.

依赖规则:
    interface ─┐
               ├─► application ─► ports ◄─ infrastructure
    bootstrap ─┘                    ▲              │
                                    └── domain ◄───┘   (domain 不依赖任何层)

  * domain         不得 import application / ports / infrastructure / interface
  * application    不得 import infrastructure / interface (只能 domain + ports)
  * ports          不得 import application / infrastructure / interface
  * infrastructure 不得 import application / interface
  * 只有 bootstrap (组合根) 与 interface 可以同时碰 application + infrastructure
"""

from __future__ import annotations

import ast
from pathlib import Path

import memory_ledger

PKG_ROOT = Path(memory_ledger.__file__).parent
PKG = "memory_ledger"


def _internal_imports(py_file: Path) -> set[str]:
    """提取一个文件里所有对 memory_ledger.* 的 import, 返回点路径集合."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    rel = py_file.relative_to(PKG_ROOT).with_suffix("")
    pkg_parts = (PKG, *rel.parts[:-1])  # 该文件所在包 (用于解析相对 import)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:  # 相对 import: from ..x import y
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)]
                mod = (*base, *(node.module.split(".") if node.module else ()))
                found.add(".".join(mod))
            elif node.module and node.module.startswith(PKG):
                found.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PKG):
                    found.add(alias.name)
    return found


def _layer_files(layer: str) -> list[Path]:
    return list((PKG_ROOT / layer).rglob("*.py"))


def _imports_layer(dotted: str, layer: str) -> bool:
    return f"{PKG}.{layer}" in dotted or dotted == f"{PKG}.{layer}"


def _assert_layer_forbids(layer: str, forbidden: list[str]) -> None:
    violations: list[str] = []
    for f in _layer_files(layer):
        for imp in _internal_imports(f):
            for bad in forbidden:
                if _imports_layer(imp, bad):
                    violations.append(f"{f.relative_to(PKG_ROOT)} → {imp}")
    assert not violations, f"{layer} 不应依赖 {forbidden}: " + "; ".join(violations)


def test_domain_depends_on_nothing():
    _assert_layer_forbids(
        "domain", ["application", "ports", "infrastructure", "interface"]
    )


def test_application_does_not_import_infrastructure_or_interface():
    _assert_layer_forbids("application", ["infrastructure", "interface"])


def test_ports_depend_only_on_domain():
    _assert_layer_forbids("ports", ["application", "infrastructure", "interface"])


def test_infrastructure_does_not_import_application_or_interface():
    _assert_layer_forbids("infrastructure", ["application", "interface"])
