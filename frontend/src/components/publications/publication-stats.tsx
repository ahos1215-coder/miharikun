"use client";

import { BookOpen, CheckCircle, AlertTriangle, HelpCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: string;
  glowClass: string;
  index: number;
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const start = performance.now();
    const duration = 1200;
    const from = 0;

    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + (value - from) * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [value]);

  return <span>{display}</span>;
}

function StatCard({ icon, label, value, color, glowClass, index }: StatCardProps) {
  return (
    <div
      className={cn(
        "glass rounded-xl p-4 flex flex-col items-center gap-2 glass-hover transition-all duration-300 motion-preset-slide-up motion-duration-500",
        glowClass,
      )}
      style={{ animationDelay: `${150 + index * 80}ms` }}
    >
      <div className={cn("flex items-center gap-2", color)}>
        {icon}
        <span className="text-xs font-medium text-zinc-400">{label}</span>
      </div>
      <span className={cn("text-3xl font-bold tabular-nums", color)}>
        <AnimatedNumber value={value} />
      </span>
    </div>
  );
}

interface PublicationStatsProps {
  mandatory: number;
  current: number;
  outdated: number;
  unknown: number;
}

export function PublicationStats({
  mandatory,
  current,
  outdated,
  unknown,
}: PublicationStatsProps) {
  const cards: Omit<StatCardProps, "index">[] = [
    {
      icon: <BookOpen size={16} />,
      label: "必須書籍",
      value: mandatory,
      color: "text-cyan-400",
      glowClass: "",
    },
    {
      icon: <CheckCircle size={16} />,
      label: "最新",
      value: current,
      color: "text-emerald-400",
      glowClass: current > 0 ? "glow-cyan" : "",
    },
    {
      icon: <AlertTriangle size={16} />,
      label: "要更新",
      value: outdated,
      color: "text-amber-400",
      glowClass: outdated > 0 ? "glow-amber" : "",
    },
    {
      icon: <HelpCircle size={16} />,
      label: "未確認",
      value: unknown,
      color: "text-zinc-400",
      glowClass: unknown > 0 ? "glow-rose" : "",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cards.map((card, i) => (
        <StatCard key={card.label} {...card} index={i} />
      ))}
    </div>
  );
}
