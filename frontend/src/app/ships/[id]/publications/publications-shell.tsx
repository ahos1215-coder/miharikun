"use client";

import { motion } from "framer-motion";
import { BookOpen, Ship, Inbox } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { PublicationStats } from "@/components/publications/publication-stats";
import { GlassPublicationCard } from "@/components/publications/glass-publication-card";
import type {
  Publication,
  ShipPublication,
  PublicationCategory,
} from "@/lib/types";

/* ──── Compliance Gauge (publications-specific) ──── */

function PublicationGauge({
  shipName,
  rate,
}: {
  shipName: string;
  rate: number;
}) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (rate / 100) * circumference;

  const gaugeColor =
    rate >= 80 ? "#06b6d4" : rate >= 50 ? "#f59e0b" : "#f43f5e";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
      className="glass rounded-2xl p-6 glow-cyan"
    >
      <div className="flex items-center gap-6">
        {/* SVG Gauge */}
        <div className="relative shrink-0">
          <svg width="128" height="128" viewBox="0 0 128 128">
            <circle
              cx="64"
              cy="64"
              r={radius}
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="8"
            />
            <motion.circle
              cx="64"
              cy="64"
              r={radius}
              fill="none"
              stroke={gaugeColor}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: offset }}
              transition={{
                duration: 1.5,
                ease: [0.4, 0, 0.2, 1],
                delay: 0.3,
              }}
              transform="rotate(-90 64 64)"
              style={{ filter: `drop-shadow(0 0 8px ${gaugeColor}50)` }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <motion.span
              className="text-2xl font-bold tabular-nums"
              style={{ color: gaugeColor }}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.8 }}
            >
              {rate}%
            </motion.span>
            <span className="text-[10px] text-zinc-500">コンプライアンス</span>
          </div>
        </div>

        {/* Ship info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Ship size={16} className="text-accent-cyan shrink-0" />
            <h1 className="text-lg font-semibold truncate text-white">
              {shipName}
            </h1>
          </div>
          <p className="text-sm text-zinc-500 mb-1">備付書籍管理</p>
          <div className="flex items-center gap-1.5 text-xs text-zinc-400">
            <BookOpen size={12} className="text-cyan-500/60" />
            <span>
              必須書籍の最新版保有率
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ──── Category Tabs ──── */

const CATEGORIES: { key: PublicationCategory | "all"; label: string }[] = [
  { key: "all", label: "全て" },
  { key: "A", label: "A: 条約" },
  { key: "B", label: "B: 航海用" },
  { key: "C", label: "C: 旗国" },
  { key: "D", label: "D: マニュアル" },
];

function CategoryTabs({
  active,
  shipId,
}: {
  active: PublicationCategory | null;
  shipId: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.3 }}
      className="flex gap-2 overflow-x-auto pb-1"
    >
      {CATEGORIES.map((cat) => {
        const isActive =
          cat.key === "all" ? active === null : active === cat.key;
        const href =
          cat.key === "all"
            ? `/ships/${shipId}/publications`
            : `/ships/${shipId}/publications?category=${cat.key}`;

        return (
          <Link
            key={cat.key}
            href={href}
            className={cn(
              "shrink-0 rounded-lg px-4 py-2 text-xs font-medium transition-all duration-200",
              isActive
                ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                : "glass text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.08]",
            )}
          >
            {cat.label}
          </Link>
        );
      })}
    </motion.div>
  );
}

/* ──── Empty State ──── */

function EmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
      className="glass rounded-2xl p-12 text-center"
    >
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cyan-500/10 mb-4">
        <Inbox size={28} className="text-cyan-400" />
      </div>
      <h3 className="text-lg font-semibold text-zinc-200 mb-2">
        備付書籍が未登録です
      </h3>
      <p className="text-sm text-zinc-500 max-w-md mx-auto leading-relaxed">
        この船舶の備付書籍はまだ登録されていません。
        船舶プロファイルを元に、必要な書籍が自動で追加されます。
      </p>
    </motion.div>
  );
}

/* ──── Main Shell ──── */

interface PublicationsShellProps {
  shipName: string;
  complianceRate: number;
  stats: {
    mandatory: number;
    current: number;
    outdated: number;
    unknown: number;
  };
  publications: (ShipPublication & { publication: Publication })[];
  activeCategory: PublicationCategory | null;
  shipId: string;
  isEmpty: boolean;
}

export function PublicationsShell({
  shipName,
  complianceRate,
  stats,
  publications,
  activeCategory,
  shipId,
  isEmpty,
}: PublicationsShellProps) {
  return (
    <div className="space-y-6">
      {/* Hero gauge */}
      <PublicationGauge shipName={shipName} rate={complianceRate} />

      {/* Stats cards */}
      <PublicationStats
        mandatory={stats.mandatory}
        current={stats.current}
        outdated={stats.outdated}
        unknown={stats.unknown}
      />

      {/* Category tabs */}
      <CategoryTabs active={activeCategory} shipId={shipId} />

      {/* Content */}
      {isEmpty ? (
        <EmptyState />
      ) : publications.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="glass rounded-xl p-8 text-center"
        >
          <p className="text-sm text-zinc-500">
            このカテゴリに該当する書籍はありません
          </p>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.4 }}
          className="grid gap-4 sm:grid-cols-2"
        >
          {publications.map((sp, i) => (
            <GlassPublicationCard
              key={sp.id}
              shipPublication={sp}
              publication={sp.publication}
              index={i}
            />
          ))}
        </motion.div>
      )}
    </div>
  );
}
