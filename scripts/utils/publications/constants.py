"""
constants.py — 備付書籍判定で使用する定数定義
================================================
船種定数、カテゴリ定数、優先度定数を集約。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 船種定数（maritime_knowledge.py と同期）
# ---------------------------------------------------------------------------

CARGO_SHIPS = ["bulk_carrier", "tanker", "container", "general_cargo", "roro"]
GAS_CARRIERS = ["lpg", "lng"]
CHEMICAL_CARRIERS = ["chemical"]
TANKER_TYPES = ["tanker", "chemical", "lpg", "lng"]
PASSENGER_SHIPS = ["passenger"]

# ---------------------------------------------------------------------------
# カテゴリ定数
# ---------------------------------------------------------------------------

CAT_A = "A"  # 条約書籍
CAT_B = "B"  # 航海用刊行物
CAT_C = "C"  # 旗国・船級
CAT_D = "D"  # 船上マニュアル

MANDATORY = "mandatory"
RECOMMENDED = "recommended"
