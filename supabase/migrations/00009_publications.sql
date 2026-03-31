-- 00009_publications.sql
-- 船内備付書籍管理: publications（マスターデータ）+ ship_publications（船舶別所持状況）

-- ========================================
-- publications: 書籍マスターデータ (システム管理、GHAバッチで更新)
-- ========================================
CREATE TABLE IF NOT EXISTS publications (
    id                      TEXT PRIMARY KEY,              -- 'SOLAS_CONSOLIDATED_2024' 等
    title                   TEXT NOT NULL,
    title_ja                TEXT,
    category                TEXT NOT NULL CHECK (category IN ('A', 'B', 'C', 'D')),
    publisher               TEXT,                          -- 'IMO' | '海上保安庁' | 'ClassNK' | 'UKHO' | 'NGA'
    current_edition         TEXT,
    current_edition_date    DATE,
    previous_edition        TEXT,
    isbn                    TEXT,
    legal_basis             TEXT,                          -- 'SOLAS Reg. I/11'
    applicable_conventions  TEXT[],                        -- '{SOLAS,MARPOL}'
    applicable_ship_types   TEXT[],                        -- '{bulk_carrier,tanker}' or empty = all
    applicable_gt_min       INT,
    applicable_gt_max       INT,
    applicable_navigation   TEXT[],                        -- '{international,coastal}'
    update_cycle            TEXT,                          -- '~3年' | '年次' | '週次'
    purchase_url            TEXT,
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now()
);

-- updated_at 自動更新トリガー（update_updated_at 関数は 00001 で定義済み）
CREATE TRIGGER publications_updated_at
    BEFORE UPDATE ON publications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ========================================
-- RLS: publications — 全ユーザー読み取り可、書き込みは service_role のみ
-- ========================================
ALTER TABLE publications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "publications_public_select"
    ON publications
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "publications_service_all"
    ON publications
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- ========================================
-- ship_publications: ユーザーの船舶別 備付書籍状況
-- ========================================
CREATE TABLE IF NOT EXISTS ship_publications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ship_profile_id     UUID NOT NULL REFERENCES ship_profiles(id) ON DELETE CASCADE,
    publication_id      TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,

    -- 所持状況
    status              TEXT DEFAULT 'unknown' CHECK (status IN ('current', 'outdated', 'missing', 'unknown', 'not_required')),
    owned_edition       TEXT,                              -- ユーザー入力: 手持ちの版数
    owned_edition_date  DATE,
    needs_update        BOOLEAN DEFAULT false,
    priority            TEXT DEFAULT 'mandatory' CHECK (priority IN ('mandatory', 'recommended')),

    -- メモ
    notes               TEXT,

    -- タイムスタンプ
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now(),

    UNIQUE(ship_profile_id, publication_id)
);

-- updated_at 自動更新トリガー
CREATE TRIGGER ship_publications_updated_at
    BEFORE UPDATE ON ship_publications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- インデックス
CREATE INDEX IF NOT EXISTS idx_ship_publications_ship ON ship_publications(ship_profile_id);
CREATE INDEX IF NOT EXISTS idx_ship_publications_pub ON ship_publications(publication_id);
CREATE INDEX IF NOT EXISTS idx_ship_publications_status ON ship_publications(status);
CREATE INDEX IF NOT EXISTS idx_ship_publications_needs_update ON ship_publications(needs_update) WHERE needs_update = true;

-- ========================================
-- RLS: ship_publications — ユーザーは自分の船の書籍のみ操作
-- ========================================
ALTER TABLE ship_publications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ship_publications_user_select"
    ON ship_publications
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM ship_profiles
            WHERE ship_profiles.id = ship_publications.ship_profile_id
              AND ship_profiles.user_id = auth.uid()
        )
    );

CREATE POLICY "ship_publications_user_insert"
    ON ship_publications
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM ship_profiles
            WHERE ship_profiles.id = ship_publications.ship_profile_id
              AND ship_profiles.user_id = auth.uid()
        )
    );

CREATE POLICY "ship_publications_user_update"
    ON ship_publications
    FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM ship_profiles
            WHERE ship_profiles.id = ship_publications.ship_profile_id
              AND ship_profiles.user_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM ship_profiles
            WHERE ship_profiles.id = ship_publications.ship_profile_id
              AND ship_profiles.user_id = auth.uid()
        )
    );

CREATE POLICY "ship_publications_service_all"
    ON ship_publications
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
