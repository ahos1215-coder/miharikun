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
  Ship,
  Anchor,
  Shield,
  BookOpen,
  CheckCircle,
  ArrowUpDown,
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
import { FeedbackButtons } from "@/components/feedback-buttons";
import { DeadlineBadge } from "@/components/deadline-badge";

/* ──────────────────── helpers ──────────────────── */

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

function sourceBadge(source: string | undefined) {
  if (!source) return null;
  const s = source.toLowerCase();
  if (s === "nk" || s.includes("classnk")) return <Badge variant="nk">NK</Badge>;
  if (s === "mlit" || s.includes("国土交通")) return <Badge variant="mlit">MLIT</Badge>;
  if (s === "egov" || s.includes("e-gov")) return <Badge variant="egov">e-Gov</Badge>;
  return null;
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

/* ──────────────── responsibility badges ──────────────── */

type Responsibility = "ship" | "company";

const SHIP_KEYWORDS = [
  "訓練", "操練", "点検", "掲示", "周知", "乗組員",
  "ドリル", "記録", "船上", "乗組",
];
const COMPANY_KEYWORDS = [
  "SMS", "証書", "機材", "図面", "改訂", "調達",
  "船級", "survey", "Survey", "検査受検", "設備工事",
];

function inferResponsibilities(text: string): Responsibility[] {
  const result: Responsibility[] = [];
  if (SHIP_KEYWORDS.some((kw) => text.includes(kw))) result.push("ship");
  if (COMPANY_KEYWORDS.some((kw) => text.includes(kw))) result.push("company");
  return result;
}

function responsibilityBadges(responsibilities: Responsibility[]) {
  return responsibilities.map((r) =>
    r === "ship" ? (
      <span
        key="ship"
        className="inline-flex items-center gap-0.5 rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-bold text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
      >
        <Anchor size={10} />
        船側対応
      </span>
    ) : (
      <span
        key="company"
        className="inline-flex items-center gap-0.5 rounded-full bg-purple-100 px-2 py-0.5 text-[11px] font-bold text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
      >
        <Shield size={10} />
        会社側対応
      </span>
    )
  );
}

/* ──────────────── SMS chapter inference ──────────────── */

interface SmsChapter {
  chapter: string;
  title: string;
}

const SMS_CHAPTER_MAP: { patterns: RegExp; chapter: SmsChapter }[] = [
  {
    patterns: /方針|安全.*環境.*方針|ISM.*目的/,
    chapter: { chapter: "第2章", title: "安全及び環境保護の方針" },
  },
  {
    patterns: /責任.*権限|指定者|DPA/i,
    chapter: { chapter: "第3章", title: "会社の責任及び権限" },
  },
  {
    patterns: /訓練|資格|manning|配乗|教育/i,
    chapter: { chapter: "第6章", title: "資源及び人員" },
  },
  {
    patterns: /閉囲区画|立入|作業手順|荷役|係留|船上作業/,
    chapter: { chapter: "第7章", title: "船上作業の計画の策定" },
  },
  {
    patterns: /緊急|非常|火災|退船|遭難|捜索救助|浸水/,
    chapter: { chapter: "第8章", title: "緊急事態への準備" },
  },
  {
    patterns: /不適合|事故|インシデント|報告.*分析/,
    chapter: { chapter: "第9章", title: "不適合、事故及び危険発生の報告及び分析" },
  },
  {
    patterns: /保守|整備|点検|メンテナンス|予防保全/,
    chapter: { chapter: "第10章", title: "船舶及び設備の保守整備" },
  },
  {
    patterns: /文書|記録|書類|管理.*体制/,
    chapter: { chapter: "第11章", title: "文書管理" },
  },
  {
    patterns: /内部監査|検証|レビュー/,
    chapter: { chapter: "第12章", title: "会社による検証、レビュー及び評価" },
  },
];

function inferSmsChapter(text: string): SmsChapter | null {
  for (const { patterns, chapter } of SMS_CHAPTER_MAP) {
    if (patterns.test(text)) return chapter;
  }
  return null;
}

/* ──────────────── action item detection ──────────────── */

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
  {
    pattern: /点検.*記録|点検記録|定期点検/,
    item: {
      label: "点検記録",
      icon: <BookOpen size={12} />,
      colorClass: "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400",
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

/* ──────────────── national law extraction ──────────────── */

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

/* ──────────────── category tab definitions ──────────────── */

interface CategoryTab {
  key: string;
  label: string;
  keywords: RegExp | null;
}

const CATEGORY_TABS: CategoryTab[] = [
  { key: "all", label: "全て", keywords: null },
  {
    key: "solas",
    label: "SOLAS / 安全",
    keywords: /SOLAS|安全|救命|消防|防火|航海|操舵|無線|復原性|構造/i,
  },
  {
    key: "marpol",
    label: "MARPOL / 環境",
    keywords: /MARPOL|環境|排出|汚染|バラスト|硫黄|NOx|SOx|GHG|CII|EEDI|EEXI|温室/i,
  },
  {
    key: "stcw",
    label: "STCW / 船員",
    keywords: /STCW|MLC|船員|乗組員|資格|manning|配乗|労働|当直|訓練/i,
  },
  {
    key: "national",
    label: "国内法 / 旗国",
    keywords: /国内法|旗国|船舶安全法|海防法|船員法|港則|海上交通|船舶職員|JG|MLIT|e-Gov|国土交通/i,
  },
];

type MatchWithReg = UserMatch & { regulation?: Regulation };

function matchesTab(m: MatchWithReg, tab: CategoryTab): boolean {
  if (!tab.keywords) return true;
  const searchText = [
    m.regulation?.title ?? "",
    m.regulation?.summary_ja ?? "",
    m.regulation?.category ?? "",
    m.reason ?? "",
  ].join(" ");
  return tab.keywords.test(searchText);
}

/* ──────────────── animation helper ──────────────── */

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

/* ══════════════════════════════════════════════════════════
   Page Component
   ══════════════════════════════════════════════════════════ */

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ show?: string; tab?: string; sort?: string }>;
}) {
  const params = await searchParams;
  const showAll = params.show === "all";
  const activeTabKey = params.tab ?? "all";
  const activeTab = CATEGORY_TABS.find((t) => t.key === activeTabKey) ?? CATEGORY_TABS[0];
  const sortByDeadline = params.sort === "deadline";

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

  let matchesByShip: Record<string, MatchWithReg[]> = {};

  if (shipIds.length > 0) {
    const { data: matches } = await supabase
      .from("user_matches")
      .select("*")
      .in("ship_profile_id", shipIds)
      .order("created_at", { ascending: false });

    const allMatches = (matches ?? []) as UserMatch[];

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
      <h1 className="text-2xl font-bold mb-1">ダッシュボード</h1>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
        自船に該当する規制の一覧
      </p>

      {shipList.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 p-6 shadow-sm dark:border-zinc-800 text-center motion-preset-fade">
          <Ship size={32} className="mx-auto mb-3 text-zinc-300 dark:text-zinc-600" />
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
          {/* Category tabs */}
          <nav className="flex gap-1 mb-4 overflow-x-auto pb-1 -mx-1 px-1">
            {CATEGORY_TABS.map((tab) => {
              const isActive = tab.key === activeTab.key;
              const p = new URLSearchParams();
              if (showAll) p.set("show", "all");
              if (tab.key !== "all") p.set("tab", tab.key);
              if (sortByDeadline) p.set("sort", "deadline");
              const qs = p.toString();
              const href = `/dashboard${qs ? `?${qs}` : ""}`;
              return (
                <Link
                  key={tab.key}
                  href={href}
                  className={cn(
                    "whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200",
                    isActive
                      ? "bg-blue-600 text-white shadow-sm"
                      : "border border-zinc-300 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
                  )}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>

          {/* Sort links */}
          <div className="flex items-center gap-1.5 text-sm mb-6">
            <ArrowUpDown size={14} className="text-zinc-400" />
            <Link
              href={(() => {
                const p = new URLSearchParams();
                if (showAll) p.set("show", "all");
                if (activeTabKey !== "all") p.set("tab", activeTabKey);
                const qs = p.toString();
                return `/dashboard${qs ? `?${qs}` : ""}`;
              })()}
              className={cn(
                "rounded-md px-2.5 py-1 transition-colors",
                !sortByDeadline
                  ? "bg-zinc-200 text-zinc-900 font-medium dark:bg-zinc-700 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200",
              )}
            >
              掲載日順
            </Link>
            <Link
              href={(() => {
                const p = new URLSearchParams();
                if (showAll) p.set("show", "all");
                if (activeTabKey !== "all") p.set("tab", activeTabKey);
                p.set("sort", "deadline");
                return `/dashboard?${p.toString()}`;
              })()}
              className={cn(
                "rounded-md px-2.5 py-1 transition-colors",
                sortByDeadline
                  ? "bg-zinc-200 text-zinc-900 font-medium dark:bg-zinc-700 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200",
              )}
            >
              適用日順
            </Link>
          </div>

          <div className="flex flex-col gap-6">
            {shipList.map((ship, shipIndex) => {
              const allShipMatches = (matchesByShip[ship.id] ?? []).sort((a, b) => {
                const order = (v: boolean | null) => v === true ? 0 : v === null ? 1 : 2;
                const orderDiff = order(a.is_applicable) - order(b.is_applicable);
                if (orderDiff !== 0) return orderDiff;
                if (sortByDeadline) {
                  const edA = a.regulation?.effective_date ?? "";
                  const edB = b.regulation?.effective_date ?? "";
                  if (edA && !edB) return -1;
                  if (!edA && edB) return 1;
                  if (edA && edB) return edA.localeCompare(edB);
                }
                const dateA = a.regulation?.published_at ?? "";
                const dateB = b.regulation?.published_at ?? "";
                return dateB.localeCompare(dateA);
              });

              // Split into applicable vs potential
              const applicableMatches = allShipMatches.filter((m) => m.is_applicable === true);
              const potentialMatches = allShipMatches.filter(
                (m) => m.is_applicable === null && m.match_method === "potential_match"
              );

              // Default: only applicable. show=all: everything
              const baseMatches = showAll ? allShipMatches : applicableMatches;

              // Apply category tab filter
              const filteredMatches = baseMatches.filter((m) => matchesTab(m, activeTab));

              const applicableCount = applicableMatches.length;
              const potentialCount = potentialMatches.length;

              return (
                <div
                  key={ship.id}
                  className={cn(
                    "rounded-xl border border-zinc-200 p-5 shadow-sm hover:shadow-md transition-shadow dark:border-zinc-800",
                    shipCardDelay(shipIndex)
                  )}
                >
                  {/* Ship header */}
                  <div className="mb-4 flex items-start justify-between">
                    <div>
                      <h2 className="text-lg font-semibold flex items-center gap-2">
                        <Ship size={18} className="text-zinc-400" />
                        {ship.ship_name}
                      </h2>
                      <p className="text-sm text-zinc-500 dark:text-zinc-400">
                        {SHIP_TYPE_LABELS[ship.ship_type as ShipType] ??
                          ship.ship_type}{" "}
                        / {ship.gross_tonnage.toLocaleString()} GT
                      </p>
                    </div>
                    <Link
                      href={`/ships/${ship.id}`}
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline dark:text-blue-400"
                    >
                      <Pencil size={12} />
                      編集
                    </Link>
                  </div>

                  {/* Summary counts */}
                  <div className="flex gap-3 mb-3 text-xs">
                    <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400">
                      <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                      該当 {applicableCount}件
                    </span>
                    {potentialCount > 0 && (
                      <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
                        <span className="inline-block h-2 w-2 rounded-full bg-amber-500" />
                        確認待ち {potentialCount}件
                      </span>
                    )}
                    {showAll && (
                      <span className="text-zinc-400">
                        全 {allShipMatches.length}件
                      </span>
                    )}
                  </div>

                  {/* Regulation cards */}
                  {filteredMatches.length === 0 ? (
                    <p className="text-sm text-zinc-400 dark:text-zinc-500">
                      {activeTab.key !== "all"
                        ? "このカテゴリに該当する規制はありません"
                        : "マッチした規制はまだありません"}
                    </p>
                  ) : (
                    <ul className="flex flex-col gap-3">
                      {filteredMatches.map((m) => {
                        const combinedText = [
                          m.regulation?.title ?? "",
                          m.regulation?.summary_ja ?? "",
                          m.reason ?? "",
                        ].join(" ");
                        const responsibilities = m.is_applicable === true
                          ? inferResponsibilities(combinedText)
                          : [];
                        const smsChapter = m.is_applicable === true
                          ? inferSmsChapter(combinedText)
                          : null;
                        const actions = m.is_applicable === true
                          ? extractActionItems(m.reason)
                          : [];
                        const nationalLaws = m.is_applicable === true
                          ? extractNationalLaws(m.reason)
                          : [];

                        return (
                          <li
                            key={m.id}
                            className={cn(
                              "rounded-lg border p-4 text-sm transition-colors",
                              m.is_applicable === true
                                ? "border-l-4 border-l-green-500 border-zinc-100 dark:border-zinc-800 dark:border-l-green-500"
                                : m.is_applicable === null
                                  ? "border-amber-200 bg-amber-50/30 dark:border-amber-800/50 dark:bg-amber-950/10"
                                  : "border-zinc-100 dark:border-zinc-800 opacity-60"
                            )}
                          >
                            {/* Row 1: Badges */}
                            <div className="flex flex-wrap items-center gap-1.5 mb-2">
                              {m.regulation && severityBadge(m.regulation.severity)}
                              {sourceBadge(m.regulation?.source)}
                              {m.match_method === "user_confirmed" && (
                                <span className="inline-flex items-center gap-0.5 rounded-full bg-green-100 px-2 py-0.5 text-[11px] font-bold text-green-700 dark:bg-green-900/30 dark:text-green-400">
                                  <CheckCircle size={10} />
                                  ユーザー確認済み
                                </span>
                              )}
                              {responsibilityBadges(responsibilities)}
                            </div>

                            {/* Row 2: Title */}
                            {m.regulation ? (
                              <Link
                                href={`/news/${m.regulation.id}`}
                                className="font-medium hover:underline leading-snug block mb-1"
                              >
                                {m.regulation.title}
                              </Link>
                            ) : (
                              <span className="text-zinc-400 block mb-1">
                                (規制情報なし)
                              </span>
                            )}

                            {/* Row 3: Summary */}
                            {m.regulation?.summary_ja && (
                              <p className="text-xs text-zinc-500 dark:text-zinc-400 line-clamp-2 mb-2">
                                {m.regulation.summary_ja}
                              </p>
                            )}

                            {/* Row 4: Metadata line */}
                            <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400 dark:text-zinc-500 mb-1">
                              <DeadlineBadge effectiveDate={m.regulation?.effective_date ?? null} />
                              {m.confidence !== null && (
                                <span>確度 {Math.round(m.confidence * 100)}%</span>
                              )}
                              {m.regulation?.published_at && (
                                <span>{formatDate(m.regulation.published_at)} 掲載</span>
                              )}
                            </div>

                            {/* Row 5: SMS chapter */}
                            {smsChapter && (
                              <p className="text-[11px] text-zinc-400 dark:text-zinc-500">
                                参考: SMS {smsChapter.chapter} {smsChapter.title}
                              </p>
                            )}

                            {/* Row 6: National laws */}
                            {nationalLaws.length > 0 && (
                              <p className="text-[11px] text-zinc-400 dark:text-zinc-500">
                                関連国内法: {nationalLaws.join("、")}
                              </p>
                            )}

                            {/* Row 7: Action items */}
                            {actions.length > 0 && (
                              <div className="mt-2 pt-2 border-t border-zinc-100 dark:border-zinc-800">
                                <p className="text-[10px] font-medium text-zinc-400 mb-1">
                                  対応:
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
                            )}

                            {/* Row 8: AI reason (collapsed for applicable) */}
                            {m.reason && m.is_applicable !== true && (
                              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                                {m.reason.startsWith("AI 判定失敗")
                                  ? "AI による判定を再試行中です。しばらくお待ちください。"
                                  : m.reason}
                              </p>
                            )}

                            {/* Row 9: Feedback buttons (convention_based / ai_matching only) */}
                            {m.is_applicable === true &&
                              (m.match_method === "convention_based" ||
                                m.match_method === "ai_matching") && (
                              <div className="mt-2 pt-2 border-t border-zinc-100 dark:border-zinc-800">
                                <FeedbackButtons
                                  matchId={m.id}
                                  currentApplicable={m.is_applicable}
                                />
                              </div>
                            )}

                            {/* Potential match confirmation UI */}
                            {m.is_applicable === null && m.match_method === "potential_match" && (
                              <PotentialMatchCard
                                matchId={m.id}
                                reason={m.reason}
                              />
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}

                  {/* Potential matches section (only in default applicable-only view) */}
                  {!showAll && potentialMatches.length > 0 && activeTab.key === "all" && (
                    <div className="mt-4 pt-4 border-t border-zinc-100 dark:border-zinc-800">
                      <p className="text-xs font-medium text-amber-600 dark:text-amber-400 mb-2">
                        確認待ちのマッチング ({potentialCount}件)
                      </p>
                      <ul className="flex flex-col gap-2">
                        {potentialMatches.slice(0, 3).map((m) => (
                          <li
                            key={m.id}
                            className="rounded-lg border border-amber-200 bg-amber-50/50 p-3 text-sm dark:border-amber-800/50 dark:bg-amber-950/20"
                          >
                            <div className="flex flex-wrap items-center gap-1.5 mb-1">
                              <Badge variant="action">確認待ち</Badge>
                              {m.regulation && severityBadge(m.regulation.severity)}
                            </div>
                            {m.regulation ? (
                              <Link
                                href={`/news/${m.regulation.id}`}
                                className="hover:underline block text-sm"
                              >
                                {m.regulation.title}
                              </Link>
                            ) : (
                              <span className="text-zinc-400">(規制情報なし)</span>
                            )}
                            <PotentialMatchCard matchId={m.id} reason={m.reason} />
                          </li>
                        ))}
                      </ul>
                      {potentialMatches.length > 3 && (
                        <Link
                          href="/dashboard?show=all"
                          className="text-xs text-amber-600 hover:underline mt-2 inline-block dark:text-amber-400"
                        >
                          他 {potentialMatches.length - 3}件の確認待ちを表示
                        </Link>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Footer links */}
          <div className="mt-6 flex items-center justify-between">
            <Link
              href="/ships/new"
              className="text-sm text-blue-600 hover:underline dark:text-blue-400"
            >
              + 船舶を追加する
            </Link>
            {!showAll ? (
              <Link
                href="/dashboard?show=all"
                className="text-xs text-zinc-400 hover:text-zinc-600 hover:underline dark:hover:text-zinc-300"
              >
                全てのマッチング結果を見る
              </Link>
            ) : (
              <Link
                href="/dashboard"
                className="text-xs text-blue-600 hover:underline dark:text-blue-400"
              >
                該当のみ表示に戻る
              </Link>
            )}
          </div>
        </>
      )}
    </div>
  );
}
