"use client";

import { createClient } from "@/lib/supabase/client";
import {
  UserPreferences,
  NotifySeverity,
  NOTIFY_SEVERITY_LABELS,
} from "@/lib/types";
import { useState } from "react";
import { toast } from "sonner";

const severityOptions = Object.keys(NOTIFY_SEVERITY_LABELS) as NotifySeverity[];

interface SettingsFormProps {
  preferences: UserPreferences;
}

export default function SettingsForm({ preferences }: SettingsFormProps) {
  const [emailNotify, setEmailNotify] = useState(preferences.email_notify);
  const [lineNotify, setLineNotify] = useState(preferences.line_notify);
  const [notifySeverity, setNotifySeverity] = useState<NotifySeverity>(
    preferences.notify_severity,
  );
  const [weeklySummary, setWeeklySummary] = useState(preferences.weekly_summary);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");

    const supabase = createClient();
    const { error: updateError } = await supabase
      .from("user_preferences")
      .update({
        email_notify: emailNotify,
        line_notify: lineNotify,
        notify_severity: notifySeverity,
        weekly_summary: weeklySummary,
      })
      .eq("id", preferences.id);

    setSaving(false);

    if (updateError) {
      setError(updateError.message);
      return;
    }

    toast.success("設定を保存しました");
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* 通知チャンネル */}
      <section>
        <h2 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-1">
          通知チャンネル
        </h2>
        <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-4">
          どの方法で通知を受け取るか選択します
        </p>
        <div className="border-t border-zinc-100 dark:border-zinc-800 pt-4">
          <div className="flex flex-col gap-4">
            <label className="flex items-center gap-3 text-sm">
              <input
                type="checkbox"
                checked={emailNotify}
                onChange={(e) => setEmailNotify(e.target.checked)}
                className="accent-blue-600 h-5 w-5"
              />
              メール通知
            </label>
            <label className="flex items-center gap-3 text-sm">
              <input
                type="checkbox"
                checked={lineNotify}
                onChange={(e) => setLineNotify(e.target.checked)}
                className="accent-blue-600 h-5 w-5"
              />
              LINE 通知
            </label>
          </div>
        </div>
      </section>

      {/* 通知フィルター */}
      <section>
        <h2 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-1">
          通知フィルター
        </h2>
        <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-4">
          通知する規制の重要度とサマリー設定
        </p>
        <div className="border-t border-zinc-100 dark:border-zinc-800 pt-4">
          <div className="flex flex-col gap-4">
            <div>
              <label
                htmlFor="notify_severity"
                className="block text-sm font-medium"
              >
                通知する重要度
              </label>
              <select
                id="notify_severity"
                value={notifySeverity}
                onChange={(e) =>
                  setNotifySeverity(e.target.value as NotifySeverity)
                }
                className="mt-1 block w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
              >
                {severityOptions.map((s) => (
                  <option key={s} value={s}>
                    {NOTIFY_SEVERITY_LABELS[s]}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-3 text-sm">
              <input
                type="checkbox"
                checked={weeklySummary}
                onChange={(e) => setWeeklySummary(e.target.checked)}
                className="accent-blue-600 h-5 w-5"
              />
              週次サマリー
            </label>
          </div>
        </div>
      </section>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {message && <p className="text-sm text-green-600">{message}</p>}

      <button
        type="submit"
        disabled={saving}
        className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 hover:scale-[1.02] transition-transform disabled:opacity-50"
      >
        {saving ? "保存中..." : "設定を保存"}
      </button>
    </form>
  );
}
