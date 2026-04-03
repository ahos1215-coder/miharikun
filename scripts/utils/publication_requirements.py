"""
publication_requirements.py — 後方互換ラッパー
==============================================
実体は scripts/utils/publications/ パッケージに移動済み。

使い方（変更なし）:
    from utils.publication_requirements import determine_required_publications

    ship = {
        "ship_type": "bulk_carrier",
        "gross_tonnage": 5000,
        "navigation_area": ["international"],
        "flag_state": "JPN",
        "build_year": 2015,
        "classification_society": "NK",
    }
    publications = determine_required_publications(ship)

純粋データ＋ロジックファイル — API呼び出し・DB接続は一切なし。
"""

from utils.publications import (
    determine_required_publications,
    get_mandatory_publications,
    get_publication_summary,
    get_publications_by_category,
)

# データ定数の re-export（seed_publications.py 等から使用）
from utils.publications.data_category_a import CATEGORY_A_PUBLICATIONS
from utils.publications.data_category_b import (
    JHO_PUBLICATIONS,
    ITU_PUBLICATIONS,
    NAVIGATION_REFERENCE_PUBLICATIONS,
    NGA_PUBLICATIONS,
    UKHO_PUBLICATIONS,
)
from utils.publications.data_category_c import (
    CLASS_SOCIETY_PUBLICATIONS,
    ISM_REFERENCE_PUBLICATIONS,
    JPN_FLAG_PUBLICATIONS,
    NK_SPECIALIZED_PUBLICATIONS,
)
from utils.publications.data_category_d import CATEGORY_D_PUBLICATIONS

__all__ = [
    "determine_required_publications",
    "get_mandatory_publications",
    "get_publications_by_category",
    "get_publication_summary",
    "CATEGORY_A_PUBLICATIONS",
    "CATEGORY_D_PUBLICATIONS",
    "JHO_PUBLICATIONS",
    "ITU_PUBLICATIONS",
    "NAVIGATION_REFERENCE_PUBLICATIONS",
    "UKHO_PUBLICATIONS",
    "NGA_PUBLICATIONS",
    "JPN_FLAG_PUBLICATIONS",
    "CLASS_SOCIETY_PUBLICATIONS",
    "NK_SPECIALIZED_PUBLICATIONS",
    "ISM_REFERENCE_PUBLICATIONS",
]
