"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { HelpCircle, Loader2 } from "lucide-react";

interface PotentialMatchCardProps {
  matchId: string;
  reason: string | null;
}

export function PotentialMatchCard({ matchId, reason }: PotentialMatchCardProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleConfirm = async (confirmed: boolean) => {
    setLoading(true);
    try {
      const res = await fetch("/api/confirm-match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ matchId, confirmed }),
      });

      if (!res.ok) {
        const data: { error?: string } = await res.json().catch(() => ({}));
        throw new Error(data.error ?? "リクエストに失敗しました");
      }

      if (confirmed) {
        toast.success("判定を確定しました", {
          description: "該当する規制として記録されました",
        });
      } else {
        toast.success("非該当として記録しました", {
          description: "この規制は非該当として記録されました",
        });
      }

      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "エラーが発生しました";
      toast.error("更新に失敗しました", { description: message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-2 rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-700 dark:bg-amber-950/30">
      <div className="flex items-start gap-2 mb-2">
        <HelpCircle size={14} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
        <p className="text-xs text-amber-700 dark:text-amber-300">
          {reason ?? "この規制がお客様の船舶に該当するか確認が必要です。"}
        </p>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={() => handleConfirm(true)}
          className="inline-flex items-center gap-1 rounded-md bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading && <Loader2 size={12} className="animate-spin" />}
          はい、該当します
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => handleConfirm(false)}
          className="inline-flex items-center gap-1 rounded-md border border-zinc-300 bg-white px-3 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
        >
          {loading && <Loader2 size={12} className="animate-spin" />}
          いいえ、該当しません
        </button>
      </div>
    </div>
  );
}
