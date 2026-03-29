-- 00002_mlit_crawl.sql
-- 国交省クロール状態管理テーブル（Blueprint §7.2）

CREATE TABLE IF NOT EXISTS mlit_crawl_state (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url                   TEXT NOT NULL UNIQUE,
    page_hash             TEXT,                        -- SHA256 ハッシュ（差分検知）
    content_length        INT,                         -- 無駄な再処理を防止
    last_modified         TEXT,                        -- HTTP ヘッダーの Last-Modified
    first_seen            TIMESTAMPTZ DEFAULT now(),
    last_crawled_at       TIMESTAMPTZ DEFAULT now(),   -- 最終クロール日時
    pdf_links             TEXT[],                      -- ページ内の PDF リンク
    processed             BOOLEAN DEFAULT false
);
