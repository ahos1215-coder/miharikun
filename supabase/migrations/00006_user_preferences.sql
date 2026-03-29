CREATE TABLE IF NOT EXISTS user_preferences (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    email_notify    BOOLEAN DEFAULT true,
    line_notify     BOOLEAN DEFAULT false,
    notify_severity TEXT DEFAULT 'critical',  -- 'all' | 'critical' | 'action_required'
    weekly_summary  BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_preferences_owner_select" ON user_preferences
    FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "user_preferences_owner_insert" ON user_preferences
    FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "user_preferences_owner_update" ON user_preferences
    FOR UPDATE TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "user_preferences_service_all" ON user_preferences
    FOR ALL TO service_role USING (true) WITH CHECK (true);
