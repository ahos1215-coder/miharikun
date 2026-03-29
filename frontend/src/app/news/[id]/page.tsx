import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { Regulation, Severity, Citation } from "@/lib/types";

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
  if (source === "NK") {
    return <span className="text-emerald-700 font-semibold">[NK]</span>;
  }
  if (source === "MLIT") {
    return <span className="text-indigo-700 font-semibold">[MLIT]</span>;
  }
  return <span className="text-zinc-500 font-semibold">[{source}]</span>;
}

function confidenceDisplay(confidence: number | null) {
  if (confidence === null) return "不明";
  const pct = Math.round(confidence * 100);
  if (confidence >= 0.8) return `${pct}%`;
  if (confidence >= 0.5) return `${pct}% [!] 要確認`;
  return `${pct}% [?] AI不確実`;
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return "日付不明";
  return new Date(dateStr).toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export default async function RegulationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const { data } = await supabase
    .from("regulations")
    .select("*")
    .eq("id", id)
    .single();

  if (!data) {
    notFound();
  }

  const reg = data as Regulation;
  const citations = (reg.citations ?? []) as Citation[];

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <Link
        href="/news"
        className="text-sm text-blue-600 hover:underline"
      >
        &larr; ニュース一覧へ戻る
      </Link>

      <div className="mt-4 rounded border border-zinc-200 p-6 dark:border-zinc-800">
        <div className="flex flex-wrap items-center gap-2 text-sm mb-2">
          {sourceBadge(reg.source)}
          {severityBadge(reg.severity)}
          {reg.category && (
            <span className="text-zinc-500">{reg.category}</span>
          )}
        </div>

        <h1 className="text-xl font-bold mb-2">{reg.title}</h1>

        {reg.title_en && (
          <p className="text-sm text-zinc-400 mb-4">{reg.title_en}</p>
        )}

        <dl className="grid grid-cols-2 gap-2 text-sm mb-4">
          <dt className="text-zinc-500">公開日</dt>
          <dd>{formatDate(reg.published_at)}</dd>
          {reg.effective_date && (
            <>
              <dt className="text-zinc-500">施行日</dt>
              <dd>{formatDate(reg.effective_date)}</dd>
            </>
          )}
          <dt className="text-zinc-500">AI確度</dt>
          <dd>{confidenceDisplay(reg.confidence)}</dd>
        </dl>

        {reg.needs_review && (
          <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200 mb-4">
            [!] この分類はAIの確度が低いため、原文の確認を推奨します
          </div>
        )}

        {reg.summary_ja && (
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-zinc-500 mb-1">
              要約
            </h2>
            <p className="text-sm leading-relaxed">{reg.summary_ja}</p>
          </div>
        )}

        {citations.length > 0 && (
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-zinc-500 mb-2">
              引用
            </h2>
            <div className="flex flex-col gap-2">
              {citations.map((c, i) => (
                <blockquote
                  key={i}
                  className="border-l-2 border-zinc-300 pl-3 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400"
                >
                  {c.text}
                  {c.page && (
                    <span className="ml-2 text-xs text-zinc-400">
                      (p.{c.page})
                    </span>
                  )}
                </blockquote>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-3 text-sm">
          {reg.url && (
            <a
              href={reg.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              原文リンク &rarr;
            </a>
          )}
          {reg.pdf_url && (
            <a
              href={reg.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              PDF &rarr;
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
