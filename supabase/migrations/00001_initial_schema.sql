-- 00001_initial_schema.sql
-- regulations テーブル + pending_queue テーブル
-- Blueprint §7.1 + 実装コードのフィールドを統合

-- ========================================
-- regulations: 規制情報のメインテーブル
-- ========================================
CREATE TABLE IF NOT EXISTS regulations (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source                TEXT NOT NULL,                -- 'nk' | 'mlit' | 'imo'
    source_id             TEXT NOT NULL,
    title                 TEXT NOT NULL,
    title_en              TEXT,
    summary_ja            TEXT,
    url                   TEXT,
    pdf_url               TEXT,
    published_at          TIMESTAMPTZ,
    effective_date        TEXT,                         -- 施行日（MLIT スクレイパー）
    contact_dept          TEXT,                         -- 担当部署（NK スクレイパー）

    -- 適用範囲
    domain                TEXT DEFAULT 'ship',          -- 'ship' | 'crew' | 'management' | 'environment' | 'psc'
    applicable_ship_types TEXT[],
    applicable_gt_min     INT,
    applicable_gt_max     INT,
    applicable_built_after INT,
    applicable_routes     TEXT[],
    applicable_flags      TEXT[],
    applicable_crew_roles TEXT[],                       -- 船員職種の適用範囲

    -- 分類
    category              TEXT,
    severity              TEXT DEFAULT 'informational', -- 'critical' | 'action_required' | 'informational'

    -- AI 分類メタデータ
    confidence            FLOAT,                       -- 0.0〜1.0
    citations             JSONB,                       -- AI が根拠とした原文引用
    needs_review          BOOLEAN DEFAULT false,       -- 低確度 → 手動レビュー待ち
    raw_gemini_response   JSONB,                       -- Gemini 生レスポンス（デバッグ用）
    processing_notes      TEXT,                        -- 処理時の備考

    -- ストレージ
    gdrive_text_file_id   TEXT,                        -- Google Drive テキストファイル ID

    -- タイムスタンプ
    scraped_at            TIMESTAMPTZ DEFAULT now(),
    created_at            TIMESTAMPTZ DEFAULT now(),
    updated_at            TIMESTAMPTZ DEFAULT now(),

    UNIQUE(source, source_id)
);

-- updated_at 自動更新トリガー
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER regulations_updated_at
    BEFORE UPDATE ON regulations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ========================================
-- pending_queue: 処理失敗アイテムのリトライキュー
-- ========================================
CREATE TABLE IF NOT EXISTS pending_queue (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source                TEXT NOT NULL,                -- 'nk' | 'mlit' | 'imo'
    source_id             TEXT NOT NULL,
    pdf_url               TEXT NOT NULL,
    reason                TEXT NOT NULL,                -- 'download_error' | 'classification_failed' 等
    error_detail          TEXT DEFAULT '',
    retry_count           INT DEFAULT 0,
    last_error            TEXT,
    created_at            TIMESTAMPTZ DEFAULT now(),
    updated_at            TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER pending_queue_updated_at
    BEFORE UPDATE ON pending_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
