import { Clock, AlertTriangle, Calendar } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface TimelineItem {
  id: string;
  regulationId: string;
  title: string;
  effectiveDate: string;
  daysUntil: number;
  severity: "critical" | "action_required" | "informational";
}

interface TimelineStripProps {
  items: TimelineItem[];
}

function getUrgencyStyle(days: number) {
  if (days < 0) return { bg: "bg-rose-500/10", border: "border-rose-500/30", text: "text-rose-400", glow: "glow-rose" };
  if (days <= 30) return { bg: "bg-rose-500/10", border: "border-rose-500/30", text: "text-rose-400", glow: "glow-rose" };
  if (days <= 90) return { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400", glow: "glow-amber" };
  return { bg: "bg-cyan-500/10", border: "border-cyan-500/30", text: "text-cyan-400", glow: "" };
}

function getIcon(days: number) {
  if (days < 0) return <AlertTriangle size={12} />;
  if (days <= 30) return <Clock size={12} />;
  return <Calendar size={12} />;
}

export function TimelineStrip({ items }: TimelineStripProps) {
  if (items.length === 0) return null;

  return (
    <div className="motion-preset-slide-up motion-duration-500">
      <h3 className="text-sm font-medium text-zinc-400 dark:text-zinc-500 mb-3 flex items-center gap-2">
        <Clock size={14} className="text-accent-cyan" />
        適用スケジュール
      </h3>
      <div className="flex gap-3 overflow-x-auto pb-2 timeline-scroll">
        {items.map((item, i) => {
          const style = getUrgencyStyle(item.daysUntil);
          return (
            <div
              key={item.id}
              className="motion-preset-slide-right motion-duration-300"
            >
              <Link
                href={`/news/${item.regulationId}`}
                className={cn(
                  "block min-w-[180px] max-w-[220px] rounded-xl border p-3 transition-all duration-200",
                  "hover:scale-[1.02] hover:brightness-110",
                  style.bg,
                  style.border,
                  style.glow,
                )}
              >
                <div className={cn("flex items-center gap-1.5 text-xs font-medium mb-1.5", style.text)}>
                  {getIcon(item.daysUntil)}
                  {item.daysUntil < 0
                    ? `${Math.abs(item.daysUntil)}日経過`
                    : item.daysUntil === 0
                      ? "本日適用"
                      : `あと${item.daysUntil}日`}
                </div>
                <p className="text-xs text-zinc-300 dark:text-zinc-300 line-clamp-2 leading-relaxed">
                  {item.title}
                </p>
                <p className="text-[10px] text-zinc-500 mt-1.5">
                  {new Date(item.effectiveDate).toLocaleDateString("ja-JP")}
                </p>
              </Link>
            </div>
          );
        })}
      </div>
    </div>
  );
}
