-- 00004_indexes.sql
-- パフォーマンスインデックス

-- regulations: ソース別の最新取得・検索用
CREATE INDEX idx_regulations_source
    ON regulations (source);

CREATE INDEX idx_regulations_source_scraped
    ON regulations (source, scraped_at DESC);

CREATE INDEX idx_regulations_published
    ON regulations (published_at DESC);

CREATE INDEX idx_regulations_category
    ON regulations (category);

CREATE INDEX idx_regulations_severity
    ON regulations (severity);

CREATE INDEX idx_regulations_needs_review
    ON regulations (needs_review)
    WHERE needs_review = true;

-- pending_queue: リトライ対象の取得用
CREATE INDEX idx_pending_queue_source
    ON pending_queue (source);

CREATE INDEX idx_pending_queue_retry
    ON pending_queue (retry_count)
    WHERE retry_count < 3;

-- mlit_crawl_state: URL 検索・未処理ページの取得用
CREATE INDEX idx_mlit_crawl_processed
    ON mlit_crawl_state (processed)
    WHERE processed = false;

CREATE INDEX idx_mlit_crawl_last_crawled
    ON mlit_crawl_state (last_crawled_at DESC);
