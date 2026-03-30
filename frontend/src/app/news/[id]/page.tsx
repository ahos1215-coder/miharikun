import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, FileText, AlertTriangle } from "lucide-react";
import type { Metadata } from "next";
import type { Regulation, Severity, Citation } from "@/lib/types";

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
  if (source === "NK") {
    return <Badge variant="nk">NK</Badge>;
  }
  if (source === "MLIT") {
    return <Badge variant="mlit">国交省</Badge>;
  }
  return <Badge>{source}</Badge>;
}

function confidenceDisplay(confidence: number | null) {
  if (confidence === null) {
    return <span className="text-zinc-400">不明</span>;
  }
  const pct = Math.round(confidence * 100);
  if (confidence >= 0.8) {
    return (
      <span className="text-green-600 font-semibold">{pct}%</span>
    );
  }
  if (confidence >= 0.5) {
    return (
      <span className="text-amber-600 font-semibold">
        {pct}% <AlertTriangle size={12} className="inline" /> 要確認
      </span>
    );
  }
  return (
    <span className="text-red-600 font-semibold">
      {pct}% <AlertTriangle size={12} className="inline" /> AI不確実
    </span>
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

async function fetchRegulation(id: string): Promise<Regulation | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("regulations")
    .select("*")
    .eq("id", id)
    .single();
  return data as Regulation | null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const reg = await fetchRegulation(id);

  if (!reg) {
    return { title: "規制情報が見つかりません | MIHARIKUN" };
  }

  const description =
    reg.summary_ja ?? `${reg.source} の規制情報: ${reg.title}`;

  return {
    title: `${reg.title} | MIHARIKUN`,
    description,
    openGraph: {
      title: `[${reg.source}] ${reg.title}`,
      description,
      type: "article",
      publishedTime: reg.published_at ?? undefined,
    },
  };
}

export default async function RegulationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const reg = await fetchRegulation(id);

  if (!reg) {
    notFound();
  }

  const citations = (reg.citations ?? []) as Citation[];

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <Link
        href="/news"
        className="text-sm text-blue-600 hover:underline"
      >
        &larr; ニュース一覧に戻る
      </Link>

      <div className="mt-4 rounded border border-zinc-200 p-6 dark:border-zinc-800">
        <div className="flex flex-wrap items-center gap-2 text-sm mb-2">
          {sourceBadge(reg.source)}
          {severityBadge(reg.severity)}
          {reg.category && (
            <Badge variant="default">{reg.category}</Badge>
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
          <div className="flex items-start gap-2 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200 mb-4">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            この分類はAIの確度が低いため、原文の確認を推奨します
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
              <ExternalLink size={14} className="inline mr-1" />
              原文を見る
            </a>
          )}
          {reg.pdf_url && (
            <a
              href={reg.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              <FileText size={14} className="inline mr-1" />
              PDF を開く
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
