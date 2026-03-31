-- user_matches に feedback 関連カラムを追加
ALTER TABLE user_matches ADD COLUMN IF NOT EXISTS user_feedback TEXT;
-- 'correct' | 'incorrect' | NULL
ALTER TABLE user_matches ADD COLUMN IF NOT EXISTS feedback_at TIMESTAMPTZ;

-- needs_review カラムがまだない場合のみ追加
ALTER TABLE user_matches ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE;

-- feedback のあるレコードを素早く検索するためのインデックス
CREATE INDEX IF NOT EXISTS idx_user_matches_feedback
  ON user_matches (user_feedback) WHERE user_feedback IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_matches_needs_review
  ON user_matches (needs_review) WHERE needs_review = TRUE;
