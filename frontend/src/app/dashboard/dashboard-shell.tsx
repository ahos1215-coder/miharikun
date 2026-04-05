"use client";

import Link from "next/link";
import { Pencil, BookOpen } from "lucide-react";
import { GlassRegulationCard } from "@/components/dashboard/glass-regulation-card";
import { Badge } from "@/components/ui/badge";
import type { Regulation, Publication } from "@/lib/types";

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
  filteredMatches: MatchData[];
  potentialMatches: MatchData[];
  hasMorePotential: boolean;
  totalPotential: number;
  publications: Publication[];
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
        <div
          key={sd.ship.id}
          className="space-y-5 motion-preset-fade"
        >
          {/* Ship Info Card */}
          <div className="glass rounded-2xl p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white">{sd.ship.shipName}</h2>
                <p className="text-sm text-zinc-400">
                  {sd.ship.shipType} / {sd.ship.grossTonnage.toLocaleString()} GT
                </p>
                <div className="flex items-center gap-4 mt-2 text-sm">
                  <span className="text-cyan-400 font-medium">該当 {sd.applicableCount}</span>
                  {sd.potentialCount > 0 && (
                    <span className="text-amber-400">確認待ち {sd.potentialCount}</span>
                  )}
                  <span className="text-zinc-500">全件 {sd.totalCount}</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Link
                  href={`${sd.ship.editHref}/publications`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 hover:text-cyan-400 hover:border-cyan-600 transition-colors"
                >
                  <BookOpen size={13} />
                  書籍
                </Link>
                <Link
                  href={sd.ship.editHref}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 hover:text-cyan-400 hover:border-cyan-600 transition-colors"
                >
                  <Pencil size={13} />
                  編集
                </Link>
              </div>
            </div>
          </div>

          {/* Publications Summary — DB から取得した法定書籍 */}
          {sd.publications.length > 0 && (
            <div className="glass rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-zinc-300 flex items-center gap-1.5">
                  <BookOpen size={14} className="text-cyan-400" />
                  備付書籍 ({sd.publications.length}件)
                </h3>
                <Link
                  href={`${sd.ship.editHref}/publications`}
                  className="text-xs text-cyan-400 hover:text-cyan-300"
                >
                  全て表示 →
                </Link>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800 text-zinc-500">
                      <th className="text-left py-1.5 pr-2">書籍名</th>
                      <th className="text-left py-1.5 px-2 w-16">区分</th>
                      <th className="text-left py-1.5 px-2 w-28">最新版</th>
                      <th className="text-left py-1.5 px-2 w-24">発行日</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sd.publications.slice(0, 8).map((pub) => {
                      const catLabels: Record<string, string> = { A: "条約", B: "航海用", C: "旗国/船級", D: "マニュアル" };
                      const catColors: Record<string, string> = {
                        A: "text-cyan-400",
                        B: "text-indigo-400",
                        C: "text-purple-400",
                        D: "text-amber-400",
                      };
                      return (
                        <tr key={pub.id} className="border-b border-zinc-800/50 text-zinc-300">
                          <td className="py-1.5 pr-2">{pub.title_ja ?? pub.title}</td>
                          <td className={`py-1.5 px-2 ${catColors[pub.category] ?? "text-zinc-400"}`}>
                            {catLabels[pub.category] ?? pub.category}
                          </td>
                          <td className="py-1.5 px-2 text-zinc-400 truncate max-w-[7rem]">
                            {pub.current_edition ?? "—"}
                          </td>
                          <td className="py-1.5 px-2 text-zinc-500 tabular-nums">
                            {pub.current_edition_date?.slice(0, 7) ?? "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {sd.publications.length > 8 && (
                  <Link
                    href={`${sd.ship.editHref}/publications`}
                    className="text-xs text-zinc-500 hover:text-cyan-400 mt-2 inline-block"
                  >
                    他 {sd.publications.length - 8}件の書籍を表示 →
                  </Link>
                )}
              </div>
            </div>
          )}

          {/* Regulation cards */}
          {sd.filteredMatches.length === 0 ? (
            <p className="text-sm text-zinc-500 text-center py-8 glass rounded-xl motion-preset-fade">
              {activeTabKey !== "all"
                ? "このカテゴリに該当する規制はありません"
                : "マッチした規制はまだありません"}
            </p>
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
            <div className="glass rounded-xl p-4 glow-amber motion-preset-fade">
              <p className="text-xs font-medium text-amber-400 mb-3">
                確認待ち ({sd.totalPotential}件)
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
                        {m.regulation.headline ?? m.regulation.title}
                      </Link>
                    ) : (
                      <span className="text-zinc-500">(規制情報なし)</span>
                    )}
                  </li>
                ))}
              </ul>
              {sd.hasMorePotential && (
                <Link
                  href="/dashboard?show=all"
                  className="text-xs text-amber-400 hover:text-amber-300 mt-3 inline-block transition-colors"
                >
                  他 {sd.totalPotential - sd.potentialMatches.length}件を表示
                </Link>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
