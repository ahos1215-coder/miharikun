-- regulations テーブルに船側/会社側アクションカラムを追加
ALTER TABLE regulations ADD COLUMN IF NOT EXISTS onboard_actions TEXT[];
ALTER TABLE regulations ADD COLUMN IF NOT EXISTS shore_actions TEXT[];
ALTER TABLE regulations ADD COLUMN IF NOT EXISTS sms_chapters TEXT[];

COMMENT ON COLUMN regulations.onboard_actions IS '船側対応アクション（箇条書き配列）';
COMMENT ON COLUMN regulations.shore_actions IS '会社側対応アクション（箇条書き配列）';
COMMENT ON COLUMN regulations.sms_chapters IS '関連する ISM SMS 章番号';
