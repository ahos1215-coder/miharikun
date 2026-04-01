"""
publications パッケージ — 備付書籍自動判定エンジン
=================================================
判定ロジック(engine)とマスターデータ(data_category_*)を分離して管理。

使い方:
    from utils.publications import determine_required_publications

    ship = {
        "ship_type": "bulk_carrier",
        "gross_tonnage": 5000,
        "navigation_area": ["international"],
        "flag_state": "JPN",
        "build_year": 2015,
        "classification_society": "NK",
    }
    publications = determine_required_publications(ship)
"""

from .engine import (
    determine_required_publications,
    get_mandatory_publications,
    get_publication_summary,
    get_publications_by_category,
)

__all__ = [
    "determine_required_publications",
    "get_mandatory_publications",
    "get_publications_by_category",
    "get_publication_summary",
]
