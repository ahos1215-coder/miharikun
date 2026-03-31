-- 無線局種別フィールド追加
ALTER TABLE ship_profiles ADD COLUMN IF NOT EXISTS radio_equipment TEXT[] DEFAULT '{}';
-- radio_equipment の値: 'gmdss_a1', 'gmdss_a2', 'gmdss_a3', 'gmdss_a4', 'ais', 'vdr', 'lrit', 'ssas'

COMMENT ON COLUMN ship_profiles.radio_equipment IS '搭載無線設備: gmdss_a1/a2/a3/a4, ais, vdr, lrit, ssas';
