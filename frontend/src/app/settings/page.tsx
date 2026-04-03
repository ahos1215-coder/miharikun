import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { UserPreferences } from "@/lib/types";
import SettingsForm from "./SettingsForm";

export default async function SettingsPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  // 開発モード: 認証不要
  // if (!user) redirect("/login");

  // Fetch existing preferences (開発モード: user が null ならデフォルト)
  let preferences: UserPreferences = {
    id: "",
    user_id: "",
    email_notify: false,
    line_notify: false,
    notify_severity: "all",
    weekly_summary: false,
    created_at: "",
    updated_at: "",
  };

  if (user) {
    const { data: existing } = await supabase
      .from("user_preferences")
      .select("*")
      .eq("user_id", user.id)
      .single();

    if (existing) {
      preferences = existing as UserPreferences;
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">通知設定</h1>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
        通知の受信方法と頻度を設定できます。設定はいつでも変更可能です。
      </p>
      <div className="motion-preset-fade rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-800 p-6">
        <SettingsForm preferences={preferences} />
      </div>
    </div>
  );
}
