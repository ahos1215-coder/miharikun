"""
Gemini API レスポンスの Pydantic バリデーション
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class GeminiClassificationResult(BaseModel):
    """classify_pdf の出力スキーマ"""
    status: str = "ok"
    category: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    severity: str = "informational"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    citations: list[dict] = Field(default_factory=list)
    applicable_vessel_types: list[str] = Field(default_factory=list)
    effective_date: Optional[str] = None

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: object) -> float:
        if v is None:
            return 0.5
        try:
            v = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, v))

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(cls, v: object) -> str:
        valid = {"critical", "warning", "info", "informational", "upcoming", "important", "action_required"}
        if v and str(v).lower() in valid:
            return str(v).lower()
        return "informational"


class GeminiMatchingResult(BaseModel):
    """ai_match の出力スキーマ"""
    is_applicable: Optional[bool] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reason: str = ""
    onboard_actions: list[str] = Field(default_factory=list)
    shore_actions: list[str] = Field(default_factory=list)
    sms_chapters: list[str] = Field(default_factory=list)
    effective_date: Optional[str] = None
    citations: list[dict] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: object) -> float:
        if v is None:
            return 0.5
        try:
            v = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, v))

    @field_validator("sms_chapters", mode="before")
    @classmethod
    def validate_sms_chapters(cls, v: object) -> list[str]:
        if not v:
            return []
        valid_chapters = {str(i) for i in range(1, 13)}
        return [str(ch) for ch in v if str(ch) in valid_chapters]  # type: ignore[union-attr]


def validate_classification(raw: dict) -> dict:
    """分類結果をバリデートし、安全な dict を返す"""
    try:
        result = GeminiClassificationResult(**raw)
        return result.model_dump()
    except Exception:
        return raw  # バリデーション失敗時は元データをそのまま返す


def validate_matching(raw: dict) -> dict:
    """マッチング結果をバリデートし、安全な dict を返す"""
    try:
        result = GeminiMatchingResult(**raw)
        return result.model_dump()
    except Exception:
        return raw
