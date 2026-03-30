import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Regulation, Severity } from "@/lib/types";

const PAGE_SIZE = 10;

function severityBadge(severity: Severity) {
  switch (severity) {
    case "critical":
      return <span className="text-red-600 font-bold">[CRITICAL]</span>;
    case "action_required":
      return <span className="text-amber-600 font-bold">[ACTION]</span>;
    case "informational":
      return <span className="text-zinc-500 font-bold">[INFO]</span>;
  }
}

function sourceBadge(source: string) {
  if (source === "nk" || source === "NK") {
    return <span className="text-emerald-700 font-semibold">[NK]</span>;
  }
  if (source === "MLIT") {
    return <span className="text-indigo-700 font-semibold">[MLIT]</span>;
  }
  return <span className="text-zinc-500 font-semibold">[{source}]</span>;
}

function confidenceLabel(confidence: number | null) {
  if (confidence === null) return null;
  if (confidence >= 0.8) return null;
  if (confidence >= 0.5) {
    return (
      <span className="text-amber-600 text-xs ml-2">[!] 要確認</span>
    );
  }
  return (
    <span className="text-red-500 text-xs ml-2">[?] AI不確実</span>
  );
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return "日付不明";
  return new Date(dateStr).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export default async function NewsPage({
  searchParams,
}: {
  searchParams: Promise<{ source?: string; page?: string; q?: string }>;
}) {
  const params = await searchParams;
  const sourceFilter = params.source?.toUpperCase();
  const searchQuery = params.q?.trim() || "";
  const currentPage = Math.max(1, parseInt(params.page ?? "1", 10) || 1);
  const offset = (currentPage - 1) * PAGE_SIZE;

  const supabase = await createClient();

  // フィルタ付きのクエリ（ページネーション）
  let query = supabase
    .from("regulations")
    .select("id,source,source_id,title,category,severity,confidence,published_at,summary_ja", { count: "exact" })
    .order("published_at", { ascending: false })
    .range(offset, offset + PAGE_SIZE - 1);

  if (sourceFilter) {
    query = query.ilike("source", sourceFilter);
  }

  if (searchQuery) {
    query = query.ilike("title", `%${searchQuery}%`);
  }

  const { data: regulations, count: filteredCount } = await query;
  const items = (regulations ?? []) as Regulation[];
  const totalFiltered = filteredCount ?? 0;
  const totalPages = Math.ceil(totalFiltered / PAGE_SIZE);

  // ソース別件数
  const { count: totalCount } = await supabase
    .from("regulations")
    .select("*", { count: "exact", head: true });

  const { count: nkCount } = await supabase
    .from("regulations")
    .select("*", { count: "exact", head: true })
    .ilike("source", "nk");

  const { count: mlitCount } = await supabase
    .from("regulations")
    .select("*", { count: "exact", head: true })
    .ilike("source", "MLIT");

  // ページネーション用のURL構築
  function pageUrl(page: number) {
    const p = new URLSearchParams();
    if (sourceFilter) p.set("source", sourceFilter.toLowerCase());
    if (searchQuery) p.set("q", searchQuery);
    if (page > 1) p.set("page", String(page));
    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  }

  // ソースフィルタURL（検索クエリを保持）
  function sourceUrl(source?: string) {
    const p = new URLSearchParams();
    if (source) p.set("source", source);
    if (searchQuery) p.set("q", searchQuery);
    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  }

  // 検索クリアURL（ソースフィルタを保持）
  function clearSearchUrl() {
    const p = new URLSearchParams();
    if (sourceFilter) p.set("source", sourceFilter.toLowerCase());
    const qs = p.toString();
    return `/news${qs ? `?${qs}` : ""}`;
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-4">最新規制ニュース</h1>

      <form method="GET" action="/news" className="flex gap-2 mb-4">
        {sourceFilter && (
          <input type="hidden" name="source" value={sourceFilter.toLowerCase()} />
        )}
        <input
          type="text"
          name="q"
          defaultValue={searchQuery}
          placeholder="規制を検索..."
          className="flex-1 rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
        <button
          type="submit"
          className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          検索
        </button>
      </form>

      {searchQuery && (
        <div className="flex items-center gap-2 mb-4 text-sm">
          <span className="text-zinc-600 dark:text-zinc-400">
            「{searchQuery}」の検索結果: {totalFiltered}件
          </span>
          <Link href={clearSearchUrl()} className="text-blue-600 hover:underline">
            クリア
          </Link>
        </div>
      )}

      <div className="flex gap-2 mb-6 text-sm">
        <Link
          href={sourceUrl()}
          className={`rounded px-3 py-1 ${!sourceFilter ? "bg-blue-600 text-white" : "border border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"}`}
        >
          全て ({totalCount ?? 0})
        </Link>
        <Link
          href={sourceUrl("nk")}
          className={`rounded px-3 py-1 ${sourceFilter === "NK" ? "bg-emerald-600 text-white" : "border border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"}`}
        >
          NK ({nkCount ?? 0})
        </Link>
        <Link
          href={sourceUrl("mlit")}
          className={`rounded px-3 py-1 ${sourceFilter === "MLIT" ? "bg-indigo-600 text-white" : "border border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"}`}
        >
          国交省 ({mlitCount ?? 0})
        </Link>
      </div>

      {items.length === 0 ? (
        <p className="text-zinc-500">規制情報はまだありません</p>
      ) : (
        <>
          <ul className="flex flex-col gap-4">
            {items.map((reg) => (
              <li key={reg.id}>
                <Link
                  href={`/news/${reg.id}`}
                  className="block rounded border border-zinc-200 p-4 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-colors"
                >
                  <div className="flex flex-wrap items-center gap-2 text-sm mb-1">
                    {sourceBadge(reg.source)}
                    {severityBadge(reg.severity)}
                    {reg.category && (
                      <span className="text-zinc-500">{reg.category}</span>
                    )}
                    {confidenceLabel(reg.confidence)}
                  </div>
                  <p className="font-medium">{reg.title}</p>
                  {reg.summary_ja && (
                    <p className="text-xs text-zinc-500 mt-1 line-clamp-2">
                      {reg.summary_ja}
                    </p>
                  )}
                  <p className="text-xs text-zinc-400 mt-1">
                    {formatDate(reg.published_at)}
                  </p>
                </Link>
              </li>
            ))}
          </ul>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 mt-6 text-sm">
              {currentPage > 1 ? (
                <Link href={pageUrl(currentPage - 1)} className="text-blue-600 hover:underline">
                  ← 前へ
                </Link>
              ) : (
                <span className="text-zinc-300">← 前へ</span>
              )}
              <span className="text-zinc-500">
                {currentPage} / {totalPages}
              </span>
              {currentPage < totalPages ? (
                <Link href={pageUrl(currentPage + 1)} className="text-blue-600 hover:underline">
                  次へ →
                </Link>
              ) : (
                <span className="text-zinc-300">次へ →</span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
