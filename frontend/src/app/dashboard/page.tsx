import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Pencil,
  FileEdit,
  Wrench,
  GraduationCap,
  FileCheck,
  ClipboardList,
} from "lucide-react";
import type {
  ShipProfile,
  UserMatch,
  Regulation,
  Severity,
  ShipType,
} from "@/lib/types";
import { SHIP_TYPE_LABELS } from "@/lib/types";
import { PotentialMatchCard } from "./PotentialMatchCard";

function severityBadge(severity: Severity) {
  switch (severity) {
    case "critical":
      return <Badge variant="critical">Critical</Badge>;
    case "action_required":
      return <Badge variant="action">要対応</Badge>;
    case "informational":
      return <Badge variant="info">情報</Badge>;
  }
}

function applicabilityLabel(isApplicable: boolean | null) {
  if (isApplicable === true) {
    return <Badge variant="success">該当</Badge>;
  }
  if (isApplicable === false) {
    return <Badge variant="info">非該当</Badge>;
  }
  return <Badge variant="action">判定中</Badge>;
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

// --- Action item detection from reason text ---

interface ActionItem {
  label: string;
  icon: React.ReactNode;
  colorClass: string;
}

const ACTION_PATTERNS: { pattern: RegExp; item: ActionItem }[] = [
  {
    pattern: /SMS改訂|SMS\s*改[訂定]|安全管理.*改訂/i,
    item: {
      label: "SMS改訂",
      icon: <FileEdit size={12} />,
      colorClass: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    },
  },
  {
    pattern: /設備工事|設備.*改[造修]|工事/,
    item: {
      label: "設備工事",
      icon: <Wrench size={12} />,
      colorClass: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
    },
  },
  {
    pattern: /乗組員訓練|訓練|教育.*実施/,
    item: {
      label: "乗組員訓練",
      icon: <GraduationCap size={12} />,
      colorClass: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    },
  },
  {
    pattern: /証書更新|証書.*取得|証書.*発行|検査.*受検/,
    item: {
      label: "証書更新",
      icon: <FileCheck size={12} />,
      colorClass: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    },
  },
  {
    pattern: /書類整備|書類.*準備|記録.*整備|文書.*改訂/,
    item: {
      label: "書類整備",
      icon: <ClipboardList size={12} />,
      colorClass: "bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-300",
    },
  },
];

function extractActionItems(reason: string | null): ActionItem[] {
  if (!reason) return [];
  const items: ActionItem[] = [];
  for (const { pattern, item } of ACTION_PATTERNS) {
    if (pattern.test(reason)) {
      items.push(item);
    }
  }
  return items;
}

// --- National law extraction from reason text ---

const NATIONAL_LAW_PATTERNS = [
  /船舶救命設備規則/,
  /船舶消防設備規則/,
  /船舶安全法/,
  /船舶職員.*法/,
  /海洋汚染.*防止法/,
  /船員法/,
  /港則法/,
  /海上交通安全法/,
  /船舶設備規程/,
  /船舶防火構造規則/,
  /船舶復原性規則/,
  /船舶機関規則/,
  /危険物船舶運送.*貯蔵規則/,
  /船舶のトン数.*測度.*法/,
];

function extractNationalLaws(reason: string | null): string[] {
  if (!reason) return [];
  const laws: string[] = [];
  for (const pattern of NATIONAL_LAW_PATTERNS) {
    const match = reason.match(pattern);
    if (match) {
      laws.push(match[0]);
    }
  }
  return [...new Set(laws)];
}

/** Staggered animation delay for ship cards */
function shipCardDelay(index: number): string {
  if (index >= 5) return "motion-preset-slide-up";
  const delays = [
    "motion-preset-slide-up",
    "motion-preset-slide-up motion-delay-100",
    "motion-preset-slide-up motion-delay-200",
    "motion-preset-slide-up motion-delay-300",
    "motion-preset-slide-up motion-delay-400",
  ] as const;
  return delays[index];
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ filter?: string }>;
}) {
  const params = await searchParams;
  const filterApplicable = params.filter === "applicable";
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const { data: ships } = await supabase
    .from("ship_profiles")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const shipList = (ships ?? []) as ShipProfile[];

  // Fetch matches for all user's ships
  const shipIds = shipList.map((s) => s.id);

  let matchesByShip: Record<string, (UserMatch & { regulation?: Regulation })[]> = {};

  if (shipIds.length > 0) {
    // user_matches を取得
    const { data: matches } = await supabase
      .from("user_matches")
      .select("*")
      .in("ship_profile_id", shipIds)
      .order("created_at", { ascending: false });

    const allMatches = (matches ?? []) as UserMatch[];

    // regulation_id を収集して regulations を別クエリで取得
    const regIds = [...new Set(allMatches.map((m) => m.regulation_id))];
    let regsMap: Record<string, Regulation> = {};

    if (regIds.length > 0) {
      const { data: regs } = await supabase
        .from("regulations")
        .select("*")
        .in("id", regIds);

      for (const r of (regs ?? []) as Regulation[]) {
        regsMap[r.id] = r;
      }
    }

    // matches に regulation を結合してグルーピング
    for (const m of allMatches) {
      const entry = { ...m, regulation: regsMap[m.regulation_id] };
      if (!matchesByShip[m.ship_profile_id]) {
        matchesByShip[m.ship_profile_id] = [];
      }
      matchesByShip[m.ship_profile_id].push(entry);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">ダッシュボード</h1>

      {shipList.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 p-6 shadow-sm dark:border-zinc-800 text-center motion-preset-fade">
          <p className="text-zinc-500 mb-4">船舶が登録されていません</p>
          <Link
            href="/ships/new"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            船舶を登録する
          </Link>
        </div>
      ) : (
        <>
          <div className="flex gap-2 mb-4">
            <Link
              href="/dashboard"
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200",
                !filterApplicable
                  ? "bg-blue-600 text-white shadow-sm"
                  : "border border-zinc-300 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              )}
            >
              全て表示
            </Link>
            <Link
              href="/dashboard?filter=applicable"
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200",
                filterApplicable
                  ? "bg-blue-600 text-white shadow-sm"
                  : "border border-zinc-300 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              )}
            >
              該当のみ
            </Link>
          </div>

          <div className="flex flex-col gap-6">
            {shipList.map((ship, shipIndex) => {
              const allMatches = (matchesByShip[ship.id] ?? []).sort((a, b) => {
                // 該当 > 判定中 > 非該当 の順、同じなら掲載日の新しい順
                const order = (v: boolean | null) => v === true ? 0 : v === null ? 1 : 2;
                const orderDiff = order(a.is_applicable) - order(b.is_applicable);
                if (orderDiff !== 0) return orderDiff;
                const dateA = a.regulation?.published_at ?? "";
                const dateB = b.regulation?.published_at ?? "";
                return dateB.localeCompare(dateA);
              });
              const applicableCount = allMatches.filter((m) => m.is_applicable === true).length;
              const matches = filterApplicable
                ? allMatches.filter((m) => m.is_applicable === true)
                : allMatches;
              return (
                <div
                  key={ship.id}
                  className={cn(
                    "rounded-xl border border-zinc-200 p-6 shadow-sm hover:shadow-md transition-shadow dark:border-zinc-800",
                    shipCardDelay(shipIndex)
                  )}
                >
                  <div className="mb-3 flex items-start justify-between">
                    <div>
                      <h2 className="text-lg font-semibold">
                        {ship.ship_name}
                      </h2>
                      <p className="text-sm text-zinc-500">
                        {SHIP_TYPE_LABELS[ship.ship_type as ShipType] ??
                          ship.ship_type}{" "}
                        / {ship.gross_tonnage.toLocaleString()} GT
                      </p>
                    </div>
                    <Link
                      href={`/ships/${ship.id}`}
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                    >
                      <Pencil size={12} />
                      編集
                    </Link>
                  </div>

                  {allMatches.length > 0 && (
                    <p className="text-xs text-zinc-500 mb-2">
                      該当: {allMatches.filter((m) => m.is_applicable === true).length}件
                      {" / "}判定中: {allMatches.filter((m) => m.is_applicable === null).length}件
                      {" / "}非該当: {allMatches.filter((m) => m.is_applicable === false).length}件
                    </p>
                  )}

                  {matches.length === 0 ? (
                    <p className="text-sm text-zinc-400">
                      マッチした規制はまだありません
                    </p>
                  ) : (
                    <ul className="flex flex-col gap-2">
                      {matches.map((m) => (
                        <li
                          key={m.id}
                          className={cn(
                            "rounded-lg border border-zinc-100 p-3 dark:border-zinc-800 text-sm transition-colors",
                            m.is_applicable === true && "border-l-4 border-l-green-500",
                            m.is_applicable === false && "opacity-60"
                          )}
                        >
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            {applicabilityLabel(m.is_applicable)}
                            {m.regulation &&
                              severityBadge(m.regulation.severity)}
                            {m.confidence !== null && (
                              <span className="text-xs text-zinc-400">
                                確度 {Math.round(m.confidence * 100)}%
                                {m.regulation?.published_at && ` | ${formatDate(m.regulation.published_at)}`}
                              </span>
                            )}
                            {m.confidence === null && m.regulation?.published_at && (
                              <span className="text-xs text-zinc-400">
                                {formatDate(m.regulation.published_at)}
                              </span>
                            )}
                          </div>
                          {m.regulation ? (
                            <Link
                              href={`/news/${m.regulation.id}`}
                              className="hover:underline"
                            >
                              {m.regulation.title}
                            </Link>
                          ) : (
                            <span className="text-zinc-400">
                              (規制情報なし)
                            </span>
                          )}
                          {m.reason && (
                            <p className="text-xs text-zinc-500 mt-1">
                              {m.reason.startsWith("AI 判定失敗")
                                ? "AI による判定を再試行中です。しばらくお待ちください。"
                                : m.reason}
                            </p>
                          )}
                          {/* Task 1: Action items for applicable matches */}
                          {m.is_applicable === true && (() => {
                            const actions = extractActionItems(m.reason);
                            if (actions.length === 0) return null;
                            return (
                              <div className="mt-2">
                                <p className="text-[10px] font-medium text-zinc-400 mb-1">
                                  対応が必要な項目
                                </p>
                                <div className="flex flex-wrap gap-1">
                                  {actions.map((action) => (
                                    <span
                                      key={action.label}
                                      className={cn(
                                        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
                                        action.colorClass
                                      )}
                                    >
                                      {action.icon}
                                      {action.label}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            );
                          })()}
                          {/* Task 3: National laws for applicable matches */}
                          {m.is_applicable === true && (() => {
                            const laws = extractNationalLaws(m.reason);
                            if (laws.length === 0) return null;
                            return (
                              <p className="text-[11px] text-zinc-400 mt-1">
                                関連国内法: {laws.join("、")}
                              </p>
                            );
                          })()}
                          {/* Task 2: Potential match confirmation UI */}
                          {m.is_applicable === null && m.match_method === "potential_match" && (
                            <PotentialMatchCard
                              matchId={m.id}
                              reason={m.reason}
                            />
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-6">
            <Link
              href="/ships/new"
              className="text-sm text-blue-600 hover:underline"
            >
              + 船舶を追加する
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
