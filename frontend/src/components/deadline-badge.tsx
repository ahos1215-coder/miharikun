"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Clock, Calendar } from "lucide-react";

interface DeadlineBadgeProps {
  effectiveDate: string | null;
  className?: string;
}

export function DeadlineBadge({ effectiveDate, className }: DeadlineBadgeProps) {
  if (!effectiveDate) return null;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(effectiveDate);
  target.setHours(0, 0, 0, 0);

  const diffMs = target.getTime() - today.getTime();
  const days = Math.round(diffMs / (1000 * 60 * 60 * 24));

  const formatted = target.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });

  // Past due
  if (days < 0) {
    return (
      <Badge
        variant="critical"
        className={cn("inline-flex items-center gap-1", className)}
      >
        <AlertTriangle size={11} />
        適用済み（{Math.abs(days)}日経過）
      </Badge>
    );
  }

  // Urgent: 0-30 days
  if (days <= 30) {
    return (
      <Badge
        variant="critical"
        className={cn(
          "inline-flex items-center gap-1 motion-preset-pulse",
          className,
        )}
      >
        <Clock size={11} />
        あと{days}日で強制適用
      </Badge>
    );
  }

  // Soon: 31-90 days
  if (days <= 90) {
    return (
      <Badge
        variant="action"
        className={cn("inline-flex items-center gap-1", className)}
      >
        <Clock size={11} />
        あと{days}日
      </Badge>
    );
  }

  // Planned: 91-365 days
  if (days <= 365) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
          className,
        )}
      >
        <Calendar size={11} />
        {formatted} 適用予定
      </span>
    );
  }

  // Far future: > 365 days
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs text-zinc-400 dark:text-zinc-500",
        className,
      )}
    >
      <Calendar size={11} />
      {formatted} 適用予定
    </span>
  );
}
