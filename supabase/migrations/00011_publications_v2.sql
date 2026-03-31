-- 書籍テーブルの拡張: 日英対応 + applicability_rules + 鮮度追跡
ALTER TABLE publications ADD COLUMN IF NOT EXISTS applicability_rules JSONB;
ALTER TABLE publications ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ;
ALTER TABLE publications ADD COLUMN IF NOT EXISTS verified_by TEXT DEFAULT 'manual';
-- verified_by: 'manual' | 'auto_checker' | 'inferred_annual' | 'seed'

COMMENT ON COLUMN publications.applicability_rules IS 'JSON形式の適用条件: conventions, ship_types, gt_min, navigation, flag_state, class_society, radio_equipment';
COMMENT ON COLUMN publications.last_verified_at IS '最終確認日時';
COMMENT ON COLUMN publications.verified_by IS '確認方法: manual/auto_checker/inferred_annual/seed';
