import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export default async function SettingsPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">通知設定</h1>

      <div className="rounded border border-zinc-200 p-6 dark:border-zinc-800">
        <div className="flex flex-col gap-4">
          <label className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              disabled
              className="h-4 w-4"
            />
            <span className="text-zinc-400">メール通知 (coming soon)</span>
          </label>

          <label className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              disabled
              className="h-4 w-4"
            />
            <span className="text-zinc-400">LINE通知 (coming soon)</span>
          </label>
        </div>

        <p className="mt-6 text-sm text-zinc-500">
          通知機能は現在開発中です。
        </p>
      </div>
    </div>
  );
}
