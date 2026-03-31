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
  Anchor,
  Building2,
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

// 船側対応と会社側対応の詳細定義
interface DetailedAction {
  label: string;
  icon: typeof Wrench;
  side: "onboard" | "shore";
  details: string[];
}

const ONBOARD_ACTION_RULES: {
  keywords: string[];
  actions: DetailedAction[];
}[] = [
  {
    keywords: ["閉囲区画", "enclosed space", "立入"],
    actions: [{
      label: "閉囲区画立入手順の実施",
      icon: ClipboardCheck,
      side: "onboard",
      details: [
        "閉囲区画立入許可証（Enclosed Space Entry Permit）の運用確認",
        "入室前の酸素濃度・有毒ガス測定の実施と記録",
        "監視員（Standby Person）の配置と救助体制の確認",
        "乗組員への閉囲区画立入手順の周知・訓練の実施",
        "閉囲区画一覧表（Enclosed Space Inventory）の最新化",
      ],
    }],
  },
  {
    keywords: ["ISM", "SMS", "安全管理"],
    actions: [{
      label: "SMS関連の船上対応",
      icon: ClipboardCheck,
      side: "onboard",
      details: [
        "改訂されたSMS手順書の船内配布・差し替え",
        "船長による乗組員への改訂内容の説明・ブリーフィング",
        "改訂に伴うチェックリスト・記録簿のフォーマット更新",
        "次回内部監査に向けた改訂事項の実施記録の整備",
      ],
    }],
  },
  {
    keywords: ["STCW", "ドリル", "操練", "能力証明", "海技資格"],
    actions: [{
      label: "STCW関連訓練・操練の実施",
      icon: GraduationCap,
      side: "onboard",
      details: [
        "規制改正に対応した訓練プログラムの見直し・実施",
        "訓練記録簿への実施内容・参加者の記入",
        "訓練用機材・教材の確認と更新",
        "PSC検査での訓練記録提示に備えた書類整理",
      ],
    }],
  },
  {
    keywords: ["防火", "消火", "火災"],
    actions: [{
      label: "防火・消火設備の点検",
      icon: Wrench,
      side: "onboard",
      details: [
        "消火設備の作動試験・点検記録の更新",
        "火災探知装置の感度テスト実施",
        "非常配置表（Muster List）の見直し",
        "消火訓練（Fire Drill）での新要件の反映",
      ],
    }],
  },
  {
    keywords: ["救命", "LSA"],
    actions: [{
      label: "救命設備の点検・訓練",
      icon: Wrench,
      side: "onboard",
      details: [
        "救命艇・救命いかだの降下訓練の実施",
        "救命設備の定期点検・整備記録の更新",
        "退船訓練（Abandon Ship Drill）の実施と記録",
      ],
    }],
  },
  {
    keywords: ["MARPOL", "油", "ビルジ", "IOPP", "排出"],
    actions: [{
      label: "環境関連の船上対応",
      icon: ClipboardCheck,
      side: "onboard",
      details: [
        "油記録簿（Oil Record Book）の記載方法の確認・更新",
        "ビルジ水処理装置の作動確認と記録",
        "廃棄物管理計画（Garbage Management Plan）の見直し",
        "燃料油サンプリング手順の確認",
      ],
    }],
  },
  {
    keywords: ["ISPS", "保安"],
    actions: [{
      label: "保安関連の船上対応",
      icon: ShieldCheck,
      side: "onboard",
      details: [
        "船舶保安計画（SSP）に基づく保安レベルの確認",
        "保安ドリルの実施と記録（四半期ごと）",
        "保安員（SSO）による乗組員への周知事項の伝達",
        "訪船者管理・アクセス制御手順の確認",
      ],
    }],
  },
  {
    keywords: ["航行", "ECDIS", "AIS", "VDR"],
    actions: [{
      label: "航行設備の確認",
      icon: Wrench,
      side: "onboard",
      details: [
        "ECDISソフトウェアの更新確認（最新海図データ含む）",
        "航行設備の作動テスト・記録",
        "航海当直手順書の改訂内容の確認",
      ],
    }],
  },
  {
    keywords: ["バラスト", "BWM", "BWMS"],
    actions: [{
      label: "バラスト水管理の実施",
      icon: ClipboardCheck,
      side: "onboard",
      details: [
        "バラスト水管理計画（BWMP）に基づく処理の実施",
        "バラスト水記録簿の記入",
        "BWMS装置の作動確認・保守点検",
      ],
    }],
  },
];

const SHORE_ACTION_RULES: {
  keywords: string[];
  actions: DetailedAction[];
}[] = [
  {
    keywords: ["ISM", "SMS", "安全管理"],
    actions: [{
      label: "SMS（安全管理マニュアル）改訂",
      icon: FileCheck,
      side: "shore",
      details: [
        "改正規制に基づくSMS該当セクションの改訂案作成",
        "改訂案のDPA（指定者）による審査・承認",
        "改訂版SMSの船級協会への提出（必要な場合）",
        "全管理船舶への改訂版配布・差し替え指示",
        "改訂に伴うDOC（適合証書）の更新要否確認",
      ],
    }],
  },
  {
    keywords: ["設備", "構造", "防火", "救命"],
    actions: [{
      label: "設備の調達・改修工事",
      icon: Wrench,
      side: "shore",
      details: [
        "改正要件に適合する機材・部品のメーカー選定・見積取得",
        "改造が必要な場合の図面作成・船級協会への承認申請",
        "入渠計画との調整（ドック期間中の工事スケジューリング）",
        "施工業者の手配と工事仕様書の作成",
        "完工後の船級検査（サーベイ）の手配",
      ],
    }],
  },
  {
    keywords: ["証書", "検査", "IOPP", "IAPP", "DOC", "SMC"],
    actions: [{
      label: "船舶証書の更新・書き換え",
      icon: FileCheck,
      side: "shore",
      details: [
        "該当する船舶証書の有効期限・記載内容の確認",
        "船級協会への証書更新申請・臨時検査の手配",
        "旗国（行政庁）への届出が必要な場合の手続き",
        "更新された証書の船内への送付・旧証書の回収",
      ],
    }],
  },
  {
    keywords: ["MARPOL", "CII", "EEXI", "SEEMP", "環境", "排出"],
    actions: [{
      label: "環境規制への管理会社対応",
      icon: FileCheck,
      side: "shore",
      details: [
        "SEEMP Part III（CII改善計画）の見直し・更新",
        "EEXI技術ファイルの確認・船級への再提出",
        "DCS（データ収集システム）報告の確認",
        "IAPP証書の記載内容確認・更新手配",
        "燃料油サプライヤーへの新基準の通知",
      ],
    }],
  },
  {
    keywords: ["STCW", "資格証明", "manning", "配乗", "船員法改正"],
    actions: [{
      label: "船員配乗・訓練管理",
      icon: GraduationCap,
      side: "shore",
      details: [
        "乗組員の資格証明書の有効期限・新要件への適合確認",
        "必要な追加訓練・講習の手配（外部機関含む）",
        "訓練記録の一元管理・更新",
        "安全配乗証書（Minimum Safe Manning）の見直し",
      ],
    }],
  },
  {
    keywords: ["リサイクル", "IHM", "インベントリ"],
    actions: [{
      label: "IHM（有害物質一覧表）対応",
      icon: FileCheck,
      side: "shore",
      details: [
        "IHM Part I（船舶構造・設備の有害物質）の作成・更新",
        "IHM Part II/III（廃棄物・貯蔵品）の現況調査",
        "船級協会によるIHM承認取得",
        "IHM適合宣言書（Statement of Compliance）の発行・更新",
      ],
    }],
  },
  {
    keywords: ["ISPS", "保安"],
    actions: [{
      label: "保安関連の管理会社対応",
      icon: ShieldCheck,
      side: "shore",
      details: [
        "船舶保安評価（SSA）の見直し・更新",
        "船舶保安計画（SSP）の改訂・船級への提出",
        "ISSC（国際船舶保安証書）の更新手配",
        "CSO（会社保安担当者）による保安監査の実施",
      ],
    }],
  },
  {
    keywords: ["船級", "NK", "ClassNK", "survey"],
    actions: [{
      label: "船級検査の手配",
      icon: FileCheck,
      side: "shore",
      details: [
        "船級協会への臨時検査（Additional Survey）の申請",
        "検査に必要な書類・図面の準備",
        "検査スケジュールの調整（航行予定との整合）",
        "検査結果に基づく是正措置の計画・実施",
      ],
    }],
  },
];

function inferDetailedActions(
  category: string | null,
  title: string,
  summary: string | null
): { onboard: DetailedAction[]; shore: DetailedAction[] } {
  const text = `${category ?? ""} ${title} ${summary ?? ""}`.toLowerCase();
  const onboard: DetailedAction[] = [];
  const shore: DetailedAction[] = [];
  const seenOnboard = new Set<string>();
  const seenShore = new Set<string>();

  for (const rule of ONBOARD_ACTION_RULES) {
    if (rule.keywords.some((kw) => text.includes(kw.toLowerCase()))) {
      for (const action of rule.actions) {
        if (!seenOnboard.has(action.label)) {
          seenOnboard.add(action.label);
          onboard.push(action);
        }
      }
    }
  }

  for (const rule of SHORE_ACTION_RULES) {
    if (rule.keywords.some((kw) => text.includes(kw.toLowerCase()))) {
      for (const action of rule.actions) {
        if (!seenShore.has(action.label)) {
          seenShore.add(action.label);
          shore.push(action);
        }
      }
    }
  }

  // デフォルト: 少なくとも書類整備
  if (onboard.length === 0 && shore.length === 0) {
    shore.push({
      label: "関連書類の確認・整備",
      icon: FileCheck,
      side: "shore",
      details: ["規制改正に関連する船内文書・記録簿の確認", "必要に応じた書式の更新"],
    });
  }

  return { onboard, shore };
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
          const { onboard, shore } = inferDetailedActions(reg.category, reg.title, reg.summary_ja);
          return (
            <div className="mb-6 space-y-4">
              <h2 className="text-sm font-semibold text-zinc-500">
                想定対応事項
              </h2>

              {onboard.length > 0 && (
                <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 dark:border-blue-900 dark:bg-blue-950/20">
                  <h3 className="flex items-center gap-1.5 text-sm font-semibold text-blue-700 dark:text-blue-400 mb-3">
                    <Anchor size={14} />
                    船側対応（Onboard Action）
                  </h3>
                  <div className="space-y-3">
                    {onboard.map((a) => {
                      const Icon = a.icon;
                      return (
                        <div key={a.label}>
                          <div className="flex items-center gap-1.5 text-sm font-medium text-blue-800 dark:text-blue-300 mb-1">
                            <Icon size={13} />
                            {a.label}
                          </div>
                          <ul className="ml-5 space-y-0.5">
                            {a.details.map((d, i) => (
                              <li key={i} className="text-xs text-zinc-600 dark:text-zinc-400 list-disc">
                                {d}
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {shore.length > 0 && (
                <div className="rounded-xl border border-purple-200 bg-purple-50/50 p-4 dark:border-purple-900 dark:bg-purple-950/20">
                  <h3 className="flex items-center gap-1.5 text-sm font-semibold text-purple-700 dark:text-purple-400 mb-3">
                    <Building2 size={14} />
                    会社側対応（Shore-side Action）
                  </h3>
                  <div className="space-y-3">
                    {shore.map((a) => {
                      const Icon = a.icon;
                      return (
                        <div key={a.label}>
                          <div className="flex items-center gap-1.5 text-sm font-medium text-purple-800 dark:text-purple-300 mb-1">
                            <Icon size={13} />
                            {a.label}
                          </div>
                          <ul className="ml-5 space-y-0.5">
                            {a.details.map((d, i) => (
                              <li key={i} className="text-xs text-zinc-600 dark:text-zinc-400 list-disc">
                                {d}
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
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
