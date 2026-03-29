-- 00005_ship_profiles.sql
-- ship_profiles テーブル（船舶スペック登録）+ user_matches テーブル（マッチング結果）
-- Strategic Pivot v5 §4.A に基づく実装

-- ========================================
-- ship_profiles: ユーザーが登録する自船スペック
-- ========================================
CREATE TABLE IF NOT EXISTS ship_profiles (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- 基本情報
    ship_name               TEXT NOT NULL,
    ship_type               TEXT NOT NULL,          -- 'bulk_carrier' | 'tanker' | 'container' | 'general_cargo' | 'passenger' | 'roro' | 'lpg' | 'lng' | 'chemical' | 'other'
    gross_tonnage           INT  NOT NULL,
    dwt                     INT,
    build_year              INT  NOT NULL,

    -- 認証・旗国
    classification_society  TEXT,                   -- 'NK' | 'JG' | 'ABS' | 'DNV' | 'LR' | 'BV' | 'other'
    flag_state              TEXT DEFAULT 'JPN',

    -- 航行区域・航路
    navigation_area         TEXT[] DEFAULT '{}',    -- '{international,coastal,near_sea,smooth_water}'
    routes                  TEXT[] DEFAULT '{}',    -- 具体的航路（例: '東京湾→シンガポール'）

    -- その他
    imo_number              TEXT,                   -- IMO 番号（任意、将来の自動照合用）

    -- タイムスタンプ
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now(),

    -- 同一ユーザーの船名は一意
    UNIQUE(user_id, ship_name)
);

-- updated_at 自動更新トリガー（update_updated_at 関数は 00001 で定義済み）
CREATE TRIGGER ship_profiles_updated_at
    BEFORE UPDATE ON ship_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- インデックス
CREATE INDEX IF NOT EXISTS idx_ship_profiles_user_id       ON ship_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_ship_profiles_ship_type     ON ship_profiles(ship_type);
CREATE INDEX IF NOT EXISTS idx_ship_profiles_gross_tonnage ON ship_profiles(gross_tonnage);

-- ========================================
-- RLS: ship_profiles
-- ========================================
ALTER TABLE ship_profiles ENABLE ROW LEVEL SECURITY;

-- 認証済みユーザーは自分の船のみ SELECT
CREATE POLICY "ship_profiles_user_select"
    ON ship_profiles
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- 認証済みユーザーは自分の船のみ INSERT
CREATE POLICY "ship_profiles_user_insert"
    ON ship_profiles
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

-- 認証済みユーザーは自分の船のみ UPDATE
CREATE POLICY "ship_profiles_user_update"
    ON ship_profiles
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 認証済みユーザーは自分の船のみ DELETE
CREATE POLICY "ship_profiles_user_delete"
    ON ship_profiles
    FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

-- service_role: 全操作（GHA バッチ処理用）
CREATE POLICY "ship_profiles_service_all"
    ON ship_profiles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- ========================================
-- user_matches: 規制 × 船舶プロファイルのマッチング結果
-- ========================================
CREATE TABLE IF NOT EXISTS user_matches (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 対象
    regulation_id       UUID NOT NULL REFERENCES regulations(id) ON DELETE CASCADE,
    ship_profile_id     UUID NOT NULL REFERENCES ship_profiles(id) ON DELETE CASCADE,

    -- マッチング結果
    is_applicable       BOOLEAN,
    match_method        TEXT,               -- 'rule_based' | 'ai_matching' | 'manual'
    confidence          FLOAT,              -- 0.0〜1.0（ルールベースの場合は 1.0 or 0.0）
    reason              TEXT,               -- 例: "GT 500 以上の国際航行船舶に適用（本船 GT 2,800）"
    citations           JSONB,              -- AI が根拠とした原文引用

    -- 通知管理
    notified            BOOLEAN DEFAULT false,

    -- タイムスタンプ
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now(),

    -- 同一 (regulation, ship) の組合せは一意
    UNIQUE(regulation_id, ship_profile_id)
);

-- updated_at 自動更新トリガー
CREATE TRIGGER user_matches_updated_at
    BEFORE UPDATE ON user_matches
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- インデックス
CREATE INDEX IF NOT EXISTS idx_user_matches_regulation_id   ON user_matches(regulation_id);
CREATE INDEX IF NOT EXISTS idx_user_matches_ship_profile_id ON user_matches(ship_profile_id);
CREATE INDEX IF NOT EXISTS idx_user_matches_is_applicable   ON user_matches(is_applicable);
CREATE INDEX IF NOT EXISTS idx_user_matches_notified        ON user_matches(notified) WHERE notified = false;

-- ========================================
-- RLS: user_matches
-- ========================================
ALTER TABLE user_matches ENABLE ROW LEVEL SECURITY;

-- 認証済みユーザーは自分の船に紐づくマッチング結果のみ SELECT
CREATE POLICY "user_matches_user_select"
    ON user_matches
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM ship_profiles
            WHERE ship_profiles.id = user_matches.ship_profile_id
              AND ship_profiles.user_id = auth.uid()
        )
    );

-- service_role: 全操作（GHA マッチングバッチ用）
CREATE POLICY "user_matches_service_all"
    ON user_matches
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
