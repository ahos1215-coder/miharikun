import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { UserPreferences } from "@/lib/types";
import SettingsForm from "./SettingsForm";

export default async function SettingsPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // Fetch existing preferences
  const { data: existing } = await supabase
    .from("user_preferences")
    .select("*")
    .eq("user_id", user.id)
    .single();

  let preferences: UserPreferences;

  if (existing) {
    preferences = existing as UserPreferences;
  } else {
    // Create default row on first visit
    const { data: created, error } = await supabase
      .from("user_preferences")
      .insert({ user_id: user.id })
      .select()
      .single();

    if (error || !created) {
      return (
        <div className="max-w-3xl mx-auto px-4 py-8">
          <p className="text-red-600">
            設定の初期化に失敗しました: {error?.message}
          </p>
        </div>
      );
    }

    preferences = created as UserPreferences;
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-4">通知設定</h1>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
        通知の受信方法と頻度を設定できます。設定はいつでも変更可能です。
      </p>
      <SettingsForm preferences={preferences} />
    </div>
  );
}
