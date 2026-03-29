import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import type { Regulation, Severity } from "@/lib/types";

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
  searchParams: Promise<{ source?: string }>;
}) {
  const params = await searchParams;
  const sourceFilter = params.source?.toUpperCase();

  const supabase = await createClient();

  let query = supabase
    .from("regulations")
    .select("*")
    .order("published_at", { ascending: false });

  if (sourceFilter) {
    query = query.ilike("source", sourceFilter);
  }

  const { data: regulations } = await query;
  const items = (regulations ?? []) as Regulation[];

  // ソース別件数（フィルタ前の全数）
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

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-4">最新規制ニュース</h1>

      <div className="flex gap-2 mb-6 text-sm">
        <Link
          href="/news"
          className={`rounded px-3 py-1 ${!sourceFilter ? "bg-blue-600 text-white" : "border border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"}`}
        >
          全て ({totalCount ?? 0})
        </Link>
        <Link
          href="/news?source=nk"
          className={`rounded px-3 py-1 ${sourceFilter === "NK" ? "bg-emerald-600 text-white" : "border border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"}`}
        >
          NK ({nkCount ?? 0})
        </Link>
        <Link
          href="/news?source=mlit"
          className={`rounded px-3 py-1 ${sourceFilter === "MLIT" ? "bg-indigo-600 text-white" : "border border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"}`}
        >
          国交省 ({mlitCount ?? 0})
        </Link>
      </div>

      {items.length === 0 ? (
        <p className="text-zinc-500">規制情報はまだありません</p>
      ) : (
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
      )}
    </div>
  );
}
