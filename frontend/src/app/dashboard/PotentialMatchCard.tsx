"use client";

import { toast } from "sonner";
import { HelpCircle } from "lucide-react";

interface PotentialMatchCardProps {
  matchId: string;
  reason: string | null;
}

export function PotentialMatchCard({ matchId, reason }: PotentialMatchCardProps) {
  const handleConfirm = (applicable: boolean) => {
    toast.info("この機能は準備中です", {
      description: applicable
        ? "「該当」として記録する機能を実装予定です"
        : "「非該当」として記録する機能を実装予定です",
    });
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
          onClick={() => handleConfirm(true)}
          className="rounded-md bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 transition-colors"
        >
          はい、該当します
        </button>
        <button
          type="button"
          onClick={() => handleConfirm(false)}
          className="rounded-md border border-zinc-300 bg-white px-3 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 transition-colors dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
        >
          いいえ、該当しません
        </button>
      </div>
    </div>
  );
}
