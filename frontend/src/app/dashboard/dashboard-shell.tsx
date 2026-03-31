"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Pencil } from "lucide-react";
import { ComplianceGauge } from "@/components/dashboard/compliance-gauge";
import { TimelineStrip } from "@/components/dashboard/timeline-strip";
import { GlassRegulationCard } from "@/components/dashboard/glass-regulation-card";
import { PotentialMatchCard } from "./PotentialMatchCard";
import { Badge } from "@/components/ui/badge";
import type { Regulation } from "@/lib/types";

interface TimelineItem {
  id: string;
  regulationId: string;
  title: string;
  effectiveDate: string;
  daysUntil: number;
  severity: "critical" | "action_required" | "informational";
}

interface MatchData {
  matchId: string;
  regulation: Regulation | undefined;
  isApplicable: boolean | null;
  matchMethod: string;
  confidence: number | null;
  reason: string | null;
}

interface ShipSectionData {
  ship: {
    id: string;
    shipName: string;
    shipType: string;
    grossTonnage: number;
    editHref: string;
  };
  applicableCount: number;
  potentialCount: number;
  totalCount: number;
  timelineItems: TimelineItem[];
  filteredMatches: MatchData[];
  potentialMatches: MatchData[];
  hasMorePotential: boolean;
  totalPotential: number;
}

interface DashboardShellProps {
  shipData: ShipSectionData[];
  showAll: boolean;
  activeTabKey: string;
}

export function DashboardShell({ shipData, showAll, activeTabKey }: DashboardShellProps) {
  return (
    <div className="flex flex-col gap-8">
      {shipData.map((sd, shipIndex) => (
        <motion.div
          key={sd.ship.id}
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: shipIndex * 0.15, ease: [0.4, 0, 0.2, 1] }}
          className="space-y-5"
        >
          {/* Compliance Hero Gauge */}
          <div className="relative">
            <ComplianceGauge
              shipName={sd.ship.shipName}
              shipType={sd.ship.shipType}
              grossTonnage={sd.ship.grossTonnage}
              applicableCount={sd.applicableCount}
              totalCount={sd.totalCount}
              potentialCount={sd.potentialCount}
            />
            <Link
              href={sd.ship.editHref}
              className="absolute top-4 right-4 inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-cyan-400 transition-colors"
            >
              <Pencil size={12} />
              編集
            </Link>
          </div>

          {/* Timeline Strip */}
          {sd.timelineItems.length > 0 && (
            <TimelineStrip items={sd.timelineItems} />
          )}

          {/* Regulation cards */}
          {sd.filteredMatches.length === 0 ? (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-sm text-zinc-500 text-center py-8 glass rounded-xl"
            >
              {activeTabKey !== "all"
                ? "このカテゴリに該当する規制はありません"
                : "マッチした規制はまだありません"}
            </motion.p>
          ) : (
            <ul className="flex flex-col gap-3">
              {sd.filteredMatches.map((m, i) => (
                <GlassRegulationCard
                  key={m.matchId}
                  matchId={m.matchId}
                  regulation={m.regulation}
                  isApplicable={m.isApplicable}
                  matchMethod={m.matchMethod}
                  confidence={m.confidence}
                  reason={m.reason}
                  index={i}
                />
              ))}
            </ul>
          )}

          {/* Potential matches section */}
          {!showAll && sd.potentialMatches.length > 0 && activeTabKey === "all" && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.3 }}
              className="glass rounded-xl p-4 glow-amber"
            >
              <p className="text-xs font-medium text-amber-400 mb-3">
                確認待ちのマッチング ({sd.totalPotential}件)
              </p>
              <ul className="flex flex-col gap-2">
                {sd.potentialMatches.map((m) => (
                  <li
                    key={m.matchId}
                    className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm"
                  >
                    <div className="flex flex-wrap items-center gap-1.5 mb-1">
                      <Badge variant="action">確認待ち</Badge>
                    </div>
                    {m.regulation ? (
                      <Link
                        href={`/news/${m.regulation.id}`}
                        className="hover:text-cyan-300 block text-sm text-zinc-300 transition-colors"
                      >
                        {m.regulation.title}
                      </Link>
                    ) : (
                      <span className="text-zinc-500">(規制情報なし)</span>
                    )}
                    <PotentialMatchCard matchId={m.matchId} reason={m.reason} />
                  </li>
                ))}
              </ul>
              {sd.hasMorePotential && (
                <Link
                  href="/dashboard?show=all"
                  className="text-xs text-amber-400 hover:text-amber-300 mt-3 inline-block transition-colors"
                >
                  他 {sd.totalPotential - sd.potentialMatches.length}件の確認待ちを表示
                </Link>
              )}
            </motion.div>
          )}
        </motion.div>
      ))}
    </div>
  );
}
