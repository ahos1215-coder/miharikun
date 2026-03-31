-- 00012: regulations テーブルに applicability_rules JSONB カラムを追加
-- Gemini で抽出した適用条件（船種・GT・航行区域・旗国・条約等）を格納する

ALTER TABLE regulations ADD COLUMN IF NOT EXISTS applicability_rules JSONB;

COMMENT ON COLUMN regulations.applicability_rules IS 'Gemini抽出の適用条件JSON: ship_types, gt_min, gt_max, navigation, flag_state, conventions, radio_equipment等';
