"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ThumbsUp, ThumbsDown, Loader2, CheckCircle } from "lucide-react";

interface FeedbackButtonsProps {
  matchId: string;
  currentApplicable: boolean | null;
}

type FeedbackState = "idle" | "loading" | "correct" | "incorrect";

export function FeedbackButtons({
  matchId,
  currentApplicable,
}: FeedbackButtonsProps) {
  const router = useRouter();
  const [state, setState] = useState<FeedbackState>("idle");

  const handleFeedback = async (isCorrect: boolean) => {
    setState("loading");
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ matchId, isCorrect }),
      });

      if (!res.ok) {
        const data: { error?: string } = await res.json().catch(() => ({}));
        throw new Error(data.error ?? "リクエストに失敗しました");
      }

      setState(isCorrect ? "correct" : "incorrect");
      toast.success("フィードバックありがとうございます", {
        description: isCorrect
          ? "正しい判定として記録しました"
          : "誤判定として報告しました。確認後に修正いたします。",
      });

      router.refresh();
    } catch (err) {
      setState("idle");
      const message = err instanceof Error ? err.message : "エラーが発生しました";
      toast.error("送信に失敗しました", { description: message });
    }
  };

  if (state === "correct" || state === "incorrect") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-zinc-400 dark:text-zinc-500">
        <CheckCircle size={12} />
        {state === "correct" ? "正しい判定と報告済み" : "誤判定として報告済み"}
      </span>
    );
  }

  return (
    <div className="inline-flex items-center gap-1.5">
      <span className="text-[10px] text-zinc-400 dark:text-zinc-500 mr-0.5">
        判定は正しい?
      </span>
      <button
        type="button"
        disabled={state === "loading"}
        onClick={() => handleFeedback(true)}
        className="inline-flex items-center gap-0.5 rounded-md border border-zinc-200 bg-white px-2 py-0.5 text-[11px] text-zinc-600 hover:bg-green-50 hover:border-green-300 hover:text-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-green-900/30 dark:hover:border-green-700 dark:hover:text-green-400"
        title="正しい判定"
      >
        {state === "loading" ? (
          <Loader2 size={11} className="animate-spin" />
        ) : (
          <ThumbsUp size={11} />
        )}
      </button>
      <button
        type="button"
        disabled={state === "loading"}
        onClick={() => handleFeedback(false)}
        className="inline-flex items-center gap-0.5 rounded-md border border-zinc-200 bg-white px-2 py-0.5 text-[11px] text-zinc-600 hover:bg-red-50 hover:border-red-300 hover:text-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-red-900/30 dark:hover:border-red-700 dark:hover:text-red-400"
        title="誤った判定"
      >
        {state === "loading" ? (
          <Loader2 size={11} className="animate-spin" />
        ) : (
          <ThumbsDown size={11} />
        )}
      </button>
    </div>
  );
}
