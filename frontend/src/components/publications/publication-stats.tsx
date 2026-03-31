"use client";

import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import { BookOpen, CheckCircle, AlertTriangle, HelpCircle } from "lucide-react";
import { useEffect } from "react";
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
  const mv = useMotionValue(0);
  const display = useTransform(mv, (v) => Math.round(v));

  useEffect(() => {
    const controls = animate(mv, value, {
      duration: 1.2,
      ease: [0.4, 0, 0.2, 1],
    });
    return controls.stop;
  }, [mv, value]);

  return <motion.span>{display}</motion.span>;
}

function StatCard({ icon, label, value, color, glowClass, index }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        duration: 0.5,
        delay: 0.15 + index * 0.08,
        ease: [0.4, 0, 0.2, 1],
      }}
      className={cn(
        "glass rounded-xl p-4 flex flex-col items-center gap-2 glass-hover transition-all duration-300",
        glowClass,
      )}
    >
      <div className={cn("flex items-center gap-2", color)}>
        {icon}
        <span className="text-xs font-medium text-zinc-400">{label}</span>
      </div>
      <span className={cn("text-3xl font-bold tabular-nums", color)}>
        <AnimatedNumber value={value} />
      </span>
    </motion.div>
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
