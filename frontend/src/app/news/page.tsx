// ISR: ニュースは5分キャッシュ（週次更新なので十分）
export const revalidate = 300;

import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  ArrowUpDown,
  BookOpen,
  CheckCircle,
  Flag,
  HelpCircle,
  Leaf,
  List,
  Search,
  Shield,
  Star,
  Users,
} from "lucide-react";
import type { Regulation, Severity } from "@/lib/types";
import { DeadlineBadge } from "@/components/deadline-badge";
import type { Publication } from "@/lib/types";

const PAGE_SIZE = 10;

// --- Category tab definitions ---

type TabKey = "all" | "main" | "review" | "safety" | "environment" | "crew" | "domestic" | "publications";
type SortKey = "newest";

interface TabDef {
  key: TabKey;
  label: string;
  param: string;
  icon: React.ReactNode;
  keywords: string[];
}

const TABS: TabDef[] = [
  { key: "all", label: "全て", param: "", icon: <List size={16} />, keywords: [] },
  { key: "main", label: "主要 / My Ship", param: "main", icon: <Star size={16} />, keywords: [] },
  { key: "review", label: "確認待ち", param: "review", icon: <HelpCircle size={16} />, keywords: [] },
  {
    key: "safety",
    label: "SOLAS / 安全",
    param: "safety",
    icon: <Shield size={16} />,
    keywords: ["SOLAS", "ISM", "ISPS", "MSC", "安全", "救命", "防火", "構造", "航行", "閉囲"],
  },
  {
    key: "environment",
    label: "MARPOL / 環境",
    param: "environment",
    icon: <Leaf size={16} />,
    keywords: ["MARPOL", "MEPC", "環境", "油濁", "大気", "バラスト", "CII", "EEXI", "リサイクル", "排出"],
  },
  {
    key: "crew",
    label: "STCW / 船員",
    param: "crew",
    icon: <Users size={16} />,
    keywords: ["STCW", "MLC", "船員", "労働", "訓練", "資格", "manning"],
  },
  {
    key: "domestic",
    label: "国内法 / 旗国",
    param: "domestic",
    icon: <Flag size={16} />,
    keywords: ["船舶安全法", "海防法", "船員法", "NK", "ClassNK", "旗国", "船級", "テクニカル"],
  },
  {
    key: "publications",
    label: "備付書籍",
    param: "publications",
    icon: <BookOpen size={16} />,
    keywords: [],
  },
];

// --- Action tag keywords ---

const SHIP_SIDE_KEYWORDS = ["訓練", "操練", "点検", "掲示"];
const COMPANY_SIDE_KEYWORDS = ["SMS", "証書", "機材", "図面"];

// --- Helper functions ---

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

function sourceBadge(source: string) {
  if (source === "nk" || source === "NK") {
    return <Badge variant="nk">NK</Badge>;
  }
  if (source === "MLIT") {
    return <Badge variant="mlit">国交省</Badge>;
  }
  return <Badge>{source}</Badge>;
}

function confidenceLabel(confidence: number | null) {
  if (confidence === null) return null;
  if (confidence >= 0.8) return null;
  if (confidence >= 0.5) {
    return (
      <Badge variant="action" className="ml-1">
        <AlertTriangle size={12} className="mr-1" />
        要確認
      </Badge>
    );
  }
  return (
    <Badge variant="critical" className="ml-1">
      <HelpCircle size={12} className="mr-1" />
      AI不確実
    </Badge>
  );
}

function isWithin24Hours(dateStr: string | null): boolean {
  if (!dateStr) return false;
  const published = new Date(dateStr).getTime();
  const now = Date.now();
  return now - published < 24 * 60 * 60 * 1000;
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return "日付不明";
  return new Date(dateStr).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}


/** Staggered animation class for first 5 items */
function itemAnimationClass(index: number): string {
  if (index >= 5) return "";
  const delays = [
    "motion-preset-fade",
    "motion-preset-fade motion-delay-100",
    "motion-preset-fade motion-delay-200",
    "motion-preset-fade motion-delay-300",
    "motion-preset-fade motion-delay-400",
  ] as const;
  return delays[index];
}

/** Build .or() filter string for keyword-based category filtering */
function buildKeywordFilter(keywords: string[]): string {
  const conditions: string[] = [];
  for (const kw of keywords) {
    conditions.push(`title.ilike.%${kw}%`);
    conditions.push(`headline.ilike.%${kw}%`);
    conditions.push(`summary_ja.ilike.%${kw}%`);
    conditions.push(`category.ilike.%${kw}%`);
  }
  return conditions.join(",");
}

/** Determine the display title: headline first, then title, then fallback */
function getDisplayTitle(reg: Regulation): { text: string; isPlaceholder: boolean } {
  const isPdfFilename = (s: string) => /\.pdf$/i.test(s.trim());

  if (reg.headline && reg.headline.trim() && !isPdfFilename(reg.headline)) {
    return { text: reg.headline, isPlaceholder: false };
  }
  if (reg.title && reg.title.trim() && !isPdfFilename(reg.title)) {
    return { text: reg.title, isPlaceholder: false };
  }
  return { text: "（タイトル生成中）", isPlaceholder: true };
}

/** Infer action tags from headline + summary text */
function getActionTags(reg: Regulation): { shipSide: boolean; companySide: boolean } {
  const text = [reg.headline ?? "", reg.summary_ja ?? "", reg.title ?? ""].join(" ");
  const shipSide = SHIP_SIDE_KEYWORDS.some((kw) => text.includes(kw));
  const companySide = COMPANY_SIDE_KEYWORDS.some((kw) => text.includes(kw));
  return { shipSide, companySide };
}

// --- Main page component ---

export default async function NewsPage({
  searchParams,
}: {
  searchParams: Promise<{
    source?: string;
    page?: string;
    q?: string;
    tab?: string;
    sort?: string;
  }>;
}) {
  const params = await searchParams;
  const sourceFilter = params.source?.toUpperCase();
  const searchQuery = params.q?.trim() || "";
  const currentPage = Math.max(1, parseInt(params.page ?? "1", 10) || 1);
  const offset = (currentPage - 1) * PAGE_SIZE;
  const activeTab = (params.tab as TabKey) || "all";
  const activeSort: SortKey = "newest";

  const supabase = await createClient();

  // --- Auth check for main tab ---
  let userId: string | null = null;
  let matchedRegulationIds: string[] | null = null;
  let authError = false;

  // reviewRegulationIds: マッチ不明 (is_applicable=null) の規制ID
  let reviewRegulationIds: string[] | null = null;

  if (activeTab === "main" || activeTab === "review") {
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      userId = user.id;
      const { data: ships } = await supabase
        .from("ship_profiles")
        .select("id")
        .eq("user_id", user.id);

      if (ships && ships.length > 0) {
        const shipIds = ships.map((s: { id: string }) => s.id);

        if (activeTab === "main") {
          const { data: matches } = await supabase
            .from("user_matches")
            .select("regulation_id")
            .in("ship_profile_id", shipIds)
            .eq("is_applicable", true);

          matchedRegulationIds = matches
            ? matches.map((m: { regulation_id: string }) => m.regulation_id)
            : [];
        }

        if (activeTab === "review") {
          const { data: reviewMatches } = await supabase
            .from("user_matches")
            .select("regulation_id")
            .in("ship_profile_id", shipIds)
            .is("is_applicable", null);

          reviewRegulationIds = reviewMatches
            ? reviewMatches.map((m: { regulation_id: string }) => m.regulation_id)
            : [];
        }
      } else {
        matchedRegulationIds = [];
        reviewRegulationIds = [];
      }
    } else {
      authError = true;
    }
  }

  // --- Also fetch matches for applicability badges (when user is logged in on any tab) ---
  let allMatchedIds: Set<string> = new Set();
  if (activeTab !== "main") {
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      userId = user.id;
      const { data: ships } = await supabase
        .from("ship_profiles")
        .select("id")
        .eq("user_id", user.id);

      if (ships && ships.length > 0) {
        const shipIds = ships.map((s: { id: string }) => s.id);
        const { data: matches } = await supabase
          .from("user_matches")
          .select("regulation_id")
          .in("ship_profile_id", shipIds)
          .eq("is_applicable", true);

        if (matches) {
          allMatchedIds = new Set(matches.map((m: { regulation_id: string }) => m.regulation_id));
        }
      }
    }
  } else if (matchedRegulationIds) {
    allMatchedIds = new Set(matchedRegulationIds);
  }

  // --- Build query ---
  const selectFields = "id,source,source_id,title,headline,category,severity,confidence,published_at,scraped_at,effective_date,summary_ja";

  let query = supabase
    .from("regulations")
    .select(selectFields, { count: "exact" })
    .neq("needs_review", true)
    .range(offset, offset + PAGE_SIZE - 1);

  // Sort order（published_at が null の記事は scraped_at でフォールバック）
  query = query
    .order("published_at", { ascending: false, nullsFirst: false })
    .order("scraped_at", { ascending: false, nullsFirst: false });

  // Source filter
  if (sourceFilter) {
    query = query.ilike("source", sourceFilter);
  }

  // Search query
  if (searchQuery) {
    query = query.or(`title.ilike.%${searchQuery}%,headline.ilike.%${searchQuery}%,summary_ja.ilike.%${searchQuery}%`);
  }

  // Category tab filter
  const tabDef = TABS.find((t) => t.key === activeTab);

  if (activeTab === "main") {
    if (matchedRegulationIds && matchedRegulationIds.length > 0) {
      query = query.in("id", matchedRegulationIds);
      // My Ship: severity 優先ソート (critical > action_required > informational)
      query = query
        .order("severity", { ascending: true })
        .order("published_at", { ascending: false, nullsFirst: false });
    } else if (!authError) {
      query = query.in("id", ["__no_match__"]);
    }
  } else if (activeTab === "review") {
    if (reviewRegulationIds && reviewRegulationIds.length > 0) {
      query = query.in("id", reviewRegulationIds);
    } else if (!authError) {
      query = query.in("id", ["__no_match__"]);
    }
  } else if (tabDef && tabDef.keywords.length > 0) {
    query = query.or(buildKeywordFilter(tabDef.keywords));
  }

  // Only execute data query if not showing auth error for main tab
  let items: Regulation[] = [];
  let totalFiltered = 0;

  if (activeTab === "main" && authError) {
    // Don't query -- show login message
  } else {
    const { data: regulations, count: filteredCount } = await query;
    items = (regulations ?? []) as Regulation[];
    totalFiltered = filteredCount ?? 0;
  }

  const totalPages = Math.ceil(totalFiltered / PAGE_SIZE);

  // --- Source counts + publications を並列取得 ---
  const countQueries = [
    supabase.from("regulations").select("*", { count: "exact", head: true }).neq("needs_review", true),
    supabase.from("regulations").select("*", { count: "exact", head: true }).ilike("source", "nk").neq("needs_review", true),
    supabase.from("regulations").select("*", { count: "exact", head: true }).ilike("source", "MLIT").neq("needs_review", true),
  ] as const;

  // publications は "publications" タブの時のみ取得（遅延取得）
  const pubQuery = activeTab === "publications"
    ? supabase.from("publications")
        .select("id,title,title_ja,category,publisher,current_edition,current_edition_date,legal_basis,update_cycle")
        .order("current_edition_date", { ascending: false, nullsFirst: false })
    : null;

  const [totalResult, nkResult, mlitResult, pubResult] = await Promise.all([
    ...countQueries,
    pubQuery ?? Promise.resolve({ data: null }),
  ]);

  const totalCount = totalResult.count;
  const nkCount = nkResult.count;
  const mlitCount = mlitResult.count;
  const publications: Publication[] = (pubResult.data ?? []) as Publication[];

  // --- URL builders ---

  function buildUrl(overrides: {
    page?: number;
    source?: string;
    tab?: string;
    q?: string;
    sort?: string;
    clearSource?: boolean;
    clearTab?: boolean;
  }) {
    const p = new URLSearchParams();
    const tab = overrides.clearTab
      ? undefined
      : (overrides.tab ?? (activeTab !== "all" ? activeTab : undefined));
    const source = overrides.clearSource
      ? undefined
      : (overrides.source !== undefined
          ? overrides.source
          : (sourceFilter ? sourceFilter.toLowerCase() : undefined));
    const q = overrides.q !== undefined ? overrides.q : searchQuery;
    const page = overrides.page ?? undefined;
    const sort = overrides.sort !== undefined ? overrides.sort : (activeSort !== "newest" ? activeSort : undefined);

    if (tab) p.set("tab", tab);
    if (source) p.set("source", source);
    if (q) p.set("q", q);
    if (page && page > 1) p.set("page", String(page));
    if (sort && sort !== "newest") p.set("sort", sort);

    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  }

  function pageUrl(page: number) {
    return buildUrl({ page });
  }

  function sourceUrl(source?: string) {
    return buildUrl({ source: source ?? "", clearSource: !source, page: 1 });
  }

  function tabUrl(tab: TabKey) {
    return buildUrl({ tab: tab === "all" ? "" : tab, clearTab: tab === "all", page: 1 });
  }

  function clearSearchUrl() {
    return buildUrl({ q: "" });
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-5 dark:text-zinc-100">最新規制ニュース</h1>

      {/* Search bar */}
      <form method="GET" action="/news" className="flex gap-2 mb-5">
        {activeTab !== "all" && (
          <input type="hidden" name="tab" value={activeTab} />
        )}
        {sourceFilter && (
          <input type="hidden" name="source" value={sourceFilter.toLowerCase()} />
        )}
        {activeSort !== "newest" && (
          <input type="hidden" name="sort" value={activeSort} />
        )}
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
          />
          <input
            type="text"
            name="q"
            defaultValue={searchQuery}
            placeholder="規制を検索..."
            className="w-full rounded-lg border border-zinc-300 pl-9 pr-4 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder-zinc-500"
          />
        </div>
        <button
          type="submit"
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          検索
        </button>
      </form>

      {searchQuery && (
        <div className="flex items-center gap-2 mb-4 text-sm">
          <span className="text-zinc-600 dark:text-zinc-400">
            「{searchQuery}」の検索結果: {totalFiltered}件
          </span>
          <Link href={clearSearchUrl()} className="text-blue-600 hover:underline dark:text-blue-400">
            クリア
          </Link>
        </div>
      )}

      {/* Category tabs -- horizontal scrollable */}
      <div className="mb-4 -mx-4 px-4 overflow-x-auto scrollbar-hide">
        <nav className="flex gap-1 min-w-max" role="tablist">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.key;
            return (
              <Link
                key={tab.key}
                href={tabUrl(tab.key)}
                role="tab"
                aria-selected={isActive}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium whitespace-nowrap transition-all duration-200",
                  isActive
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800",
                )}
              >
                {tab.icon}
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Source filter + Sort dropdown row */}
      <div className="flex items-center justify-between gap-4 mb-6">
        {/* Source filter -- secondary */}
        <div className="flex gap-2 text-sm">
          <Link
            href={sourceUrl()}
            className={cn(
              "rounded-lg px-3 py-1.5 font-medium transition-all duration-200",
              !sourceFilter
                ? "bg-zinc-800 text-white dark:bg-zinc-200 dark:text-zinc-900 shadow-sm"
                : "border border-zinc-300 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900",
            )}
          >
            全て ({totalCount ?? 0})
          </Link>
          <Link
            href={sourceUrl("nk")}
            className={cn(
              "rounded-lg px-3 py-1.5 font-medium transition-all duration-200",
              sourceFilter === "NK"
                ? "bg-emerald-600 text-white shadow-sm"
                : "border border-zinc-300 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900",
            )}
          >
            NK ({nkCount ?? 0})
          </Link>
          <Link
            href={sourceUrl("mlit")}
            className={cn(
              "rounded-lg px-3 py-1.5 font-medium transition-all duration-200",
              sourceFilter === "MLIT"
                ? "bg-indigo-600 text-white shadow-sm"
                : "border border-zinc-300 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900",
            )}
          >
            国交省 ({mlitCount ?? 0})
          </Link>
        </div>

        {/* Sort: 新着順 fixed */}
        <div className="flex items-center gap-1.5 text-sm shrink-0 text-zinc-400">
          <ArrowUpDown size={14} />
          <span className="font-medium text-zinc-600 dark:text-zinc-300">新着順</span>
        </div>
      </div>

      {/* Main tab -- auth error message */}
      {/* Main tab -- match count header */}
      {activeTab === "main" && !authError && items.length > 0 && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 dark:border-emerald-900 dark:bg-emerald-950/30 mb-4 motion-preset-fade">
          <p className="text-sm text-emerald-700 dark:text-emerald-300">
            <Star size={14} className="inline mr-1.5 -mt-0.5" />
            全 {totalCount ?? 0} 件中 <strong>{totalFiltered}</strong> 件が自船に該当
          </p>
        </div>
      )}

      {activeTab === "main" && authError && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-6 text-center dark:border-blue-900 dark:bg-blue-950/30 motion-preset-fade">
          <Star size={32} className="mx-auto mb-3 text-blue-400" />
          <p className="text-sm text-zinc-700 dark:text-zinc-300">
            ログインすると自船に該当する規制だけを表示できます
          </p>
          <Link
            href="/login"
            className="mt-3 inline-block rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            ログイン
          </Link>
        </div>
      )}

      {/* Main tab -- logged in but no matches */}
      {activeTab === "main" && !authError && items.length === 0 && (
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-6 text-center dark:border-zinc-800 dark:bg-zinc-900 motion-preset-fade">
          <Star size={32} className="mx-auto mb-3 text-zinc-400" />
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            該当する規制はありません。船舶プロファイルを登録すると、マッチング結果がここに表示されます。
          </p>
          <Link
            href="/ships"
            className="mt-3 inline-block rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            船舶を登録
          </Link>
        </div>
      )}

      {/* Review tab -- header */}
      {activeTab === "review" && !authError && items.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 dark:border-amber-900 dark:bg-amber-950/30 mb-4 motion-preset-fade">
          <p className="text-sm text-amber-700 dark:text-amber-300">
            <HelpCircle size={14} className="inline mr-1.5 -mt-0.5" />
            以下の <strong>{totalFiltered}</strong> 件は自動判定できませんでした。内容を確認して自船に関係あるか判断してください。
          </p>
        </div>
      )}

      {activeTab === "review" && authError && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-6 text-center dark:border-blue-900 dark:bg-blue-950/30 motion-preset-fade">
          <HelpCircle size={32} className="mx-auto mb-3 text-blue-400" />
          <p className="text-sm text-zinc-700 dark:text-zinc-300">
            ログインすると確認待ちの規制を表示できます
          </p>
          <Link
            href="/login"
            className="mt-3 inline-block rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            ログイン
          </Link>
        </div>
      )}

      {activeTab === "review" && !authError && items.length === 0 && (
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-6 text-center dark:border-zinc-800 dark:bg-zinc-900 motion-preset-fade">
          <CheckCircle size={32} className="mx-auto mb-3 text-emerald-400" />
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            確認待ちの規制はありません。全て自動判定済みです。
          </p>
        </div>
      )}

      {/* Publications tab — DB から取得 */}
      {activeTab === "publications" && (
        <div className="space-y-4">
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            備付書籍マスター（{publications.length}冊） — 発行日の新しい順
          </p>
          <div className="flex flex-col gap-3">
            {publications.map((pub, i) => {
              const catColors: Record<string, string> = {
                A: "bg-cyan-500/15 text-cyan-300 border-cyan-500/20",
                B: "bg-indigo-500/15 text-indigo-300 border-indigo-500/20",
                C: "bg-purple-500/15 text-purple-300 border-purple-500/20",
                D: "bg-amber-500/15 text-amber-300 border-amber-500/20",
              };
              const catLabels: Record<string, string> = { A: "条約", B: "航海用", C: "旗国/船級", D: "マニュアル" };
              const editionDate = pub.current_edition_date;
              const editionYear = editionDate ? new Date(editionDate).getFullYear() : null;
              const currentYear = new Date().getFullYear();
              const isAnnual = pub.update_cycle?.includes("年") ?? false;
              const isVerified = isAnnual && editionYear === currentYear;
              return (
                <div
                  key={pub.id}
                  className={cn(
                    "rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950",
                    i < 5 ? "motion-preset-fade" : "",
                  )}
                >
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium", catColors[pub.category] ?? "")}>
                      {catLabels[pub.category] ?? pub.category}
                    </span>
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">{pub.publisher}</span>
                    {isVerified && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-500 dark:text-emerald-400">
                        <CheckCircle size={11} />
                        {editionYear}年版確認済
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-0.5">
                    {pub.title_ja ?? pub.title}
                  </h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2">{pub.title}</p>
                  <div className="flex items-center gap-4 text-xs text-zinc-400 dark:text-zinc-500">
                    <span>最新版: <strong className="text-zinc-600 dark:text-zinc-300">{pub.current_edition ?? "不明"}</strong></span>
                    {editionDate && <span>発行: <strong className="text-zinc-600 dark:text-zinc-300 tabular-nums">{editionDate}</strong></span>}
                    {pub.update_cycle && <span>更新: {pub.update_cycle}</span>}
                  </div>
                  {pub.legal_basis && (
                    <p className="text-[11px] text-zinc-400 dark:text-zinc-500 mt-1">
                      根拠: {pub.legal_basis}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Regular empty state (non-main tabs) */}
      {activeTab !== "main" && activeTab !== "publications" && items.length === 0 && (
        <p className="text-zinc-500 dark:text-zinc-400 py-8 text-center">
          該当する規制情報はありません
        </p>
      )}

      {/* News cards */}
      {activeTab !== "publications" && items.length > 0 && (
        <>
          <ul className="flex flex-col gap-4">
            {items.map((reg, index) => {
              const isNew = isWithin24Hours(reg.published_at ?? reg.scraped_at);
              const isApplicable = allMatchedIds.has(reg.id);
              const displayTitle = getDisplayTitle(reg);
              const actionTags = getActionTags(reg);

              return (
                <li key={reg.id} className={itemAnimationClass(index)}>
                  <Link
                    href={`/news/${reg.id}`}
                    className="block rounded-xl border border-zinc-200 bg-white p-4 shadow-sm hover:shadow-md transition-all duration-200 dark:border-zinc-800 dark:bg-zinc-950"
                  >
                    {/* Top row: source + severity + action tags + effective date */}
                    <div className="flex items-center justify-between mb-2.5 gap-2">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {sourceBadge(reg.source)}
                        {severityBadge(reg.severity)}
                        {confidenceLabel(reg.confidence)}
                        {actionTags.shipSide && (
                          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-bold text-blue-700 bg-blue-100 dark:text-blue-300 dark:bg-blue-900/40">
                            【船側】
                          </span>
                        )}
                        {actionTags.companySide && (
                          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-bold text-purple-700 bg-purple-100 dark:text-purple-300 dark:bg-purple-900/40">
                            【会社側】
                          </span>
                        )}
                      </div>
                      <DeadlineBadge effectiveDate={reg.effective_date} className="shrink-0" />
                    </div>

                    {/* Title (headline first) + TEC number for NK */}
                    <h3
                      className={cn(
                        "text-base font-semibold leading-snug mb-1.5",
                        displayTitle.isPlaceholder
                          ? "text-zinc-400 dark:text-zinc-600"
                          : "text-zinc-900 dark:text-zinc-100",
                      )}
                    >
                      {reg.source_id && reg.source_id.startsWith("TEC-") && (
                        <span className="text-xs font-mono text-cyan-500 dark:text-cyan-400 mr-1.5">
                          [{reg.source_id}]
                        </span>
                      )}
                      {displayTitle.text}
                    </h3>

                    {/* Summary */}
                    {reg.summary_ja && (
                      <p className="text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2 mb-2.5">
                        {reg.summary_ja}
                      </p>
                    )}

                    {/* Bottom row: category + badges + published date */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        {reg.category && (
                          <span className="text-xs text-zinc-500 dark:text-zinc-500">
                            {reg.category}
                          </span>
                        )}
                        {userId && isApplicable && (
                          <Badge variant="success">該当</Badge>
                        )}
                        {isNew && (
                          <Badge variant="new">NEW</Badge>
                        )}
                      </div>
                      <span className="text-xs text-zinc-400 dark:text-zinc-500 shrink-0">
                        {reg.published_at
                          ? `${formatDate(reg.published_at)} 掲載`
                          : reg.scraped_at
                            ? `${formatDate(reg.scraped_at)} 取得`
                            : ""}
                      </span>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 mt-8 text-sm">
              {currentPage > 1 ? (
                <Link
                  href={pageUrl(currentPage - 1)}
                  className="rounded-lg border border-zinc-300 px-4 py-2 text-zinc-700 hover:bg-zinc-50 transition-colors dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  ← 前へ
                </Link>
              ) : (
                <span className="rounded-lg border border-zinc-200 px-4 py-2 text-zinc-300 dark:border-zinc-800 dark:text-zinc-700">
                  ← 前へ
                </span>
              )}
              <span className="text-zinc-500 dark:text-zinc-400 tabular-nums">
                {currentPage} / {totalPages}
              </span>
              {currentPage < totalPages ? (
                <Link
                  href={pageUrl(currentPage + 1)}
                  className="rounded-lg border border-zinc-300 px-4 py-2 text-zinc-700 hover:bg-zinc-50 transition-colors dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  次へ →
                </Link>
              ) : (
                <span className="rounded-lg border border-zinc-200 px-4 py-2 text-zinc-300 dark:border-zinc-800 dark:text-zinc-700">
                  次へ →
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
