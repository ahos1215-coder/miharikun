import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { Badge } from "@/components/ui/badge";
import {
  ExternalLink,
  FileText,
  AlertTriangle,
  Scale,
  BookOpen,
  Wrench,
  ShieldCheck,
  GraduationCap,
  ClipboardCheck,
  FileCheck,
} from "lucide-react";
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

interface ConventionInfo {
  convention: string;
  nationalLaw: string;
}

const CONVENTION_RULES: {
  keywords: string[];
  convention: string;
  nationalLaw: string;
}[] = [
  {
    keywords: ["SOLAS", "安全", "救命", "防火", "復原性"],
    convention: "SOLAS (海上人命安全条約)",
    nationalLaw: "船舶安全法",
  },
  {
    keywords: ["MARPOL", "環境", "油", "排出", "バラスト", "汚染", "SOx", "NOx"],
    convention: "MARPOL (海洋汚染防止条約)",
    nationalLaw: "海洋汚染等及び海上災害の防止に関する法律",
  },
  {
    keywords: ["ISM", "SMS", "安全管理"],
    convention: "ISM Code (国際安全管理コード)",
    nationalLaw: "船舶安全法（ISM告示）",
  },
  {
    keywords: ["STCW", "乗組員", "資格", "訓練"],
    convention: "STCW (船員の訓練及び資格証明並びに当直の基準に関する条約)",
    nationalLaw: "船舶職員及び小型船舶操縦者法",
  },
  {
    keywords: ["MLC", "労働", "居住"],
    convention: "MLC 2006 (海上労働条約)",
    nationalLaw: "船員法",
  },
  {
    keywords: ["ISPS", "保安", "セキュリティ"],
    convention: "ISPS Code (国際船舶港湾保安コード)",
    nationalLaw: "国際船舶・港湾保安法",
  },
];

function inferConventions(
  category: string | null,
  title: string
): ConventionInfo[] {
  const text = `${category ?? ""} ${title}`.toLowerCase();
  const matched: ConventionInfo[] = [];

  for (const rule of CONVENTION_RULES) {
    if (rule.keywords.some((kw) => text.includes(kw.toLowerCase()))) {
      matched.push({
        convention: rule.convention,
        nationalLaw: rule.nationalLaw,
      });
    }
  }
  return matched;
}

interface ActionItem {
  label: string;
  icon: typeof Wrench;
}

const ACTION_RULES: {
  keywords: string[];
  actions: ActionItem[];
}[] = [
  {
    keywords: ["ISM", "SMS", "安全管理"],
    actions: [
      { label: "SMS改訂", icon: ClipboardCheck },
      { label: "乗組員訓練", icon: GraduationCap },
    ],
  },
  {
    keywords: ["設備", "SOLAS", "防火", "救命", "構造"],
    actions: [
      { label: "設備工事", icon: Wrench },
      { label: "証書更新", icon: FileCheck },
    ],
  },
  {
    keywords: ["MARPOL", "環境", "油", "排出", "SOx", "NOx"],
    actions: [
      { label: "設備工事", icon: Wrench },
      { label: "書類整備", icon: FileCheck },
    ],
  },
  {
    keywords: ["STCW", "訓練", "乗組員"],
    actions: [{ label: "乗組員訓練", icon: GraduationCap }],
  },
  {
    keywords: ["証書", "検査", "更新"],
    actions: [{ label: "証書更新", icon: FileCheck }],
  },
  {
    keywords: ["ISPS", "保安"],
    actions: [
      { label: "SMS改訂", icon: ClipboardCheck },
      { label: "乗組員訓練", icon: GraduationCap },
    ],
  },
];

function inferActions(
  category: string | null,
  title: string
): ActionItem[] {
  const text = `${category ?? ""} ${title}`.toLowerCase();
  const seen = new Set<string>();
  const result: ActionItem[] = [];

  for (const rule of ACTION_RULES) {
    if (rule.keywords.some((kw) => text.includes(kw.toLowerCase()))) {
      for (const action of rule.actions) {
        if (!seen.has(action.label)) {
          seen.add(action.label);
          result.push(action);
        }
      }
    }
  }

  // Default action if nothing matched
  if (result.length === 0) {
    result.push({ label: "書類整備", icon: FileCheck });
  }

  return result;
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

        <h1 className="text-xl font-semibold mb-1">{reg.title}</h1>

        {reg.headline && (
          <p className="text-lg text-blue-600 dark:text-blue-400 font-medium mt-1 mb-1">
            {reg.headline}
          </p>
        )}

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

        {(() => {
          const conventions = inferConventions(reg.category, reg.title);
          if (conventions.length === 0) return null;
          return (
            <div className="mb-4 rounded border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">
                <Scale size={14} className="shrink-0" />
                適用条約・関連法令
              </h2>
              <div className="flex flex-col gap-2">
                {conventions.map((c) => (
                  <div key={c.convention} className="text-sm">
                    <p className="font-medium text-blue-700 dark:text-blue-300">
                      {c.convention}
                    </p>
                    <p className="text-blue-600 dark:text-blue-400 ml-4">
                      <ShieldCheck size={12} className="inline mr-1" />
                      国内法: {c.nationalLaw}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}

        {(() => {
          const actions = inferActions(reg.category, reg.title);
          return (
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-zinc-500 mb-2">
                想定対応事項
              </h2>
              <div className="flex flex-wrap gap-2">
                {actions.map((a) => {
                  const Icon = a.icon;
                  return (
                    <Badge key={a.label} variant="default">
                      <Icon size={12} className="mr-1" />
                      {a.label}
                    </Badge>
                  );
                })}
              </div>
            </div>
          );
        })()}

        {citations.length > 0 && (
          <div className="mb-4">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold text-zinc-500 mb-2">
              <BookOpen size={14} className="shrink-0" />
              引用・根拠
            </h2>
            <div className="flex flex-col gap-2 rounded border border-zinc-100 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
              {citations.map((c, i) => (
                <blockquote
                  key={i}
                  className="border-l-2 border-blue-300 pl-3 text-sm text-zinc-600 dark:border-blue-700 dark:text-zinc-400"
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
