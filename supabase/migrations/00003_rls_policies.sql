-- 00003_rls_policies.sql
-- Row Level Security ポリシー
-- anon key = 読み取り専用、service_role = 全操作

-- ========================================
-- regulations
-- ========================================
ALTER TABLE regulations ENABLE ROW LEVEL SECURITY;

-- anon: SELECT のみ
CREATE POLICY "regulations_anon_select"
    ON regulations
    FOR SELECT
    TO anon
    USING (true);

-- service_role: 全操作（GHA バッチ用）
CREATE POLICY "regulations_service_all"
    ON regulations
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ========================================
-- pending_queue
-- ========================================
ALTER TABLE pending_queue ENABLE ROW LEVEL SECURITY;

-- anon: アクセス不可（内部キューなのでフロントには公開しない）
-- (ポリシーなし = 全拒否)

-- service_role: 全操作
CREATE POLICY "pending_queue_service_all"
    ON pending_queue
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ========================================
-- mlit_crawl_state
-- ========================================
ALTER TABLE mlit_crawl_state ENABLE ROW LEVEL SECURITY;

-- anon: アクセス不可（内部状態管理テーブル）
-- (ポリシーなし = 全拒否)

-- service_role: 全操作
CREATE POLICY "mlit_crawl_state_service_all"
    ON mlit_crawl_state
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
