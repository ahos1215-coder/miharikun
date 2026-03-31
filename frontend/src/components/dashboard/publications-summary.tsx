"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { BookOpen, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PublicationRef } from "@/lib/publication-data";

interface PublicationsSummaryProps {
  shipId: string;
  publications: PublicationRef[];
}

const CATEGORY_COLORS: Record<string, string> = {
  A: "text-cyan-400",
  B: "text-indigo-400",
  C: "text-purple-400",
  D: "text-amber-400",
};

const CATEGORY_LABELS: Record<string, string> = {
  A: "条約",
  B: "航海用",
  C: "旗国/船級",
  D: "マニュアル",
};

type StatusLevel = "green" | "amber" | "red";

interface StatusInfo {
  level: StatusLevel;
  label: string;
  dotClass: string;
  rowClass: string;
}

const STATUS_MAP: Record<StatusLevel, Omit<StatusInfo, "level">> = {
  green: {
    label: "最新",
    dotClass: "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]",
    rowClass: "",
  },
  amber: {
    label: "要確認",
    dotClass: "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]",
    rowClass: "bg-amber-500/5",
  },
  red: {
    label: "要更新",
    dotClass: "bg-rose-400 shadow-[0_0_6px_rgba(251,113,133,0.5)]",
    rowClass: "bg-rose-500/5",
  },
};

function getEditionStatus(editionDate: string): StatusInfo {
  const now = new Date();
  const edition = new Date(editionDate);
  const diffYears = (now.getTime() - edition.getTime()) / (1000 * 60 * 60 * 24 * 365.25);

  let level: StatusLevel;
  if (diffYears <= 3) {
    level = "green";
  } else if (diffYears <= 6) {
    level = "amber";
  } else {
    level = "red";
  }

  return { level, ...STATUS_MAP[level] };
}

export function PublicationsSummary({ shipId, publications }: PublicationsSummaryProps) {
  if (publications.length === 0) return null;

  const preview = publications.slice(0, 8);
  const remaining = publications.length - preview.length;

  const statusCounts = useMemo(() => {
    const counts = { green: 0, amber: 0, red: 0 };
    for (const pub of publications) {
      const { level } = getEditionStatus(pub.editionDate);
      counts[level]++;
    }
    return counts;
  }, [publications]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.25 }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
          <BookOpen size={14} className="text-accent-cyan" />
          備付書籍 ({publications.length}件)
        </h3>
        <Link
          href={`/ships/${shipId}/publications`}
          className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors inline-flex items-center gap-1"
        >
          全て表示
          <ExternalLink size={10} />
        </Link>
      </div>

      <div className="flex gap-3 mb-3 text-xs">
        <span className="flex items-center gap-1.5 text-zinc-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
          最新 {statusCounts.green}
        </span>
        <span className="flex items-center gap-1.5 text-zinc-400">
          <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]" />
          要確認 {statusCounts.amber}
        </span>
        <span className="flex items-center gap-1.5 text-zinc-400">
          <span className="w-2 h-2 rounded-full bg-rose-400 shadow-[0_0_6px_rgba(251,113,133,0.5)]" />
          要更新 {statusCounts.red}
        </span>
      </div>

      <div className="glass rounded-xl overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/5 text-zinc-500">
              <th className="text-left px-3 py-2 font-medium">書籍名</th>
              <th className="text-left px-3 py-2 font-medium w-16">区分</th>
              <th className="text-left px-3 py-2 font-medium w-28">最新版</th>
              <th className="text-right px-3 py-2 font-medium w-20">発行日</th>
              <th className="text-center px-3 py-2 font-medium w-20">状態</th>
            </tr>
          </thead>
          <tbody>
            {preview.map((pub, i) => {
              const status = getEditionStatus(pub.editionDate);
              return (
                <motion.tr
                  key={pub.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.3 + i * 0.04 }}
                  className={cn(
                    "border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors",
                    status.rowClass
                  )}
                >
                  <td className="px-3 py-2 text-zinc-300 truncate max-w-[200px]" title={pub.titleJa}>
                    {pub.titleJa}
                  </td>
                  <td className={cn("px-3 py-2 font-medium", CATEGORY_COLORS[pub.category])}>
                    {CATEGORY_LABELS[pub.category]}
                  </td>
                  <td className="px-3 py-2 text-zinc-400 truncate max-w-[120px]" title={pub.currentEdition}>
                    {pub.currentEdition}
                  </td>
                  <td className="px-3 py-2 text-right text-zinc-500 tabular-nums">
                    {pub.editionDate.slice(0, 7)}
                  </td>
                  <td className="px-3 py-2">
                    <span className="flex items-center justify-center gap-1.5">
                      <span className={cn("w-2 h-2 rounded-full shrink-0", status.dotClass)} />
                      <span className="text-zinc-400">{status.label}</span>
                    </span>
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
        {remaining > 0 && (
          <div className="px-3 py-2 text-center">
            <Link
              href={`/ships/${shipId}/publications`}
              className="text-xs text-zinc-500 hover:text-cyan-400 transition-colors"
            >
              他 {remaining}件の書籍を表示 →
            </Link>
          </div>
        )}
      </div>
    </motion.div>
  );
}
