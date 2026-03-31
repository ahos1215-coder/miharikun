"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Anchor,
  Shield,
  FileEdit,
  Wrench,
  GraduationCap,
  FileCheck,
  ClipboardList,
  BookOpen,
  CheckCircle,
  ExternalLink,
} from "lucide-react";
import { FeedbackButtons } from "@/components/feedback-buttons";
import { DeadlineBadge } from "@/components/deadline-badge";
import { PotentialMatchCard } from "@/app/dashboard/PotentialMatchCard";
import type { Regulation, Severity } from "@/lib/types";

/* ──── types ──── */

type Responsibility = "ship" | "company";

interface ActionItem {
  label: string;
  icon: React.ReactNode;
  colorClass: string;
}

interface SmsChapter {
  chapter: string;
  title: string;
}

interface GlassRegulationCardProps {
  matchId: string;
  regulation: Regulation | undefined;
  isApplicable: boolean | null;
  matchMethod: string;
  confidence: number | null;
  reason: string | null;
  index: number;
}

/* ──── inference helpers ──── */

const SHIP_KEYWORDS = ["訓練", "操練", "点検", "掲示", "周知", "乗組員", "ドリル", "記録", "船上", "乗組"];
const COMPANY_KEYWORDS = ["SMS", "証書", "機材", "図面", "改訂", "調達", "船級", "survey", "Survey", "検査受検", "設備工事"];

function inferResponsibilities(text: string): Responsibility[] {
  const result: Responsibility[] = [];
  if (SHIP_KEYWORDS.some((kw) => text.includes(kw))) result.push("ship");
  if (COMPANY_KEYWORDS.some((kw) => text.includes(kw))) result.push("company");
  return result;
}

const SMS_CHAPTER_MAP: { patterns: RegExp; chapter: SmsChapter }[] = [
  { patterns: /方針|安全.*環境.*方針|ISM.*目的/, chapter: { chapter: "Ch.2", title: "安全及び環境保護の方針" } },
  { patterns: /責任.*権限|指定者|DPA/i, chapter: { chapter: "Ch.3", title: "会社の責任及び権限" } },
  { patterns: /訓練|資格|manning|配乗|教育/i, chapter: { chapter: "Ch.6", title: "資源及び人員" } },
  { patterns: /閉囲区画|立入|作業手順|荷役|係留|船上作業/, chapter: { chapter: "Ch.7", title: "船上作業の計画" } },
  { patterns: /緊急|非常|火災|退船|遭難|捜索救助|浸水/, chapter: { chapter: "Ch.8", title: "緊急事態への準備" } },
  { patterns: /不適合|事故|インシデント|報告.*分析/, chapter: { chapter: "Ch.9", title: "不適合・事故報告" } },
  { patterns: /保守|整備|点検|メンテナンス|予防保全/, chapter: { chapter: "Ch.10", title: "保守整備" } },
  { patterns: /文書|記録|書類|管理.*体制/, chapter: { chapter: "Ch.11", title: "文書管理" } },
  { patterns: /内部監査|検証|レビュー/, chapter: { chapter: "Ch.12", title: "会社検証・レビュー" } },
];

function inferSmsChapter(text: string): SmsChapter | null {
  for (const { patterns, chapter } of SMS_CHAPTER_MAP) {
    if (patterns.test(text)) return chapter;
  }
  return null;
}

const ACTION_PATTERNS: { pattern: RegExp; item: ActionItem }[] = [
  { pattern: /SMS改訂|SMS\s*改[訂定]|安全管理.*改訂/i, item: { label: "SMS改訂", icon: <FileEdit size={11} />, colorClass: "bg-cyan-500/15 text-cyan-300 border border-cyan-500/20" } },
  { pattern: /設備工事|設備.*改[造修]|工事/, item: { label: "設備工事", icon: <Wrench size={11} />, colorClass: "bg-amber-500/15 text-amber-300 border border-amber-500/20" } },
  { pattern: /乗組員訓練|訓練|教育.*実施/, item: { label: "乗組員訓練", icon: <GraduationCap size={11} />, colorClass: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/20" } },
  { pattern: /証書更新|証書.*取得|証書.*発行|検査.*受検/, item: { label: "証書更新", icon: <FileCheck size={11} />, colorClass: "bg-rose-500/15 text-rose-300 border border-rose-500/20" } },
  { pattern: /書類整備|書類.*準備|記録.*整備|文書.*改訂/, item: { label: "書類整備", icon: <ClipboardList size={11} />, colorClass: "bg-zinc-500/15 text-zinc-300 border border-zinc-500/20" } },
  { pattern: /点検.*記録|点検記録|定期点検/, item: { label: "点検記録", icon: <BookOpen size={11} />, colorClass: "bg-teal-500/15 text-teal-300 border border-teal-500/20" } },
];

function extractActionItems(reason: string | null): ActionItem[] {
  if (!reason) return [];
  const items: ActionItem[] = [];
  for (const { pattern, item } of ACTION_PATTERNS) {
    if (pattern.test(reason)) items.push(item);
  }
  return items;
}

/* ──── badge helpers ──── */

function severityBadge(severity: Severity) {
  switch (severity) {
    case "critical": return <Badge variant="critical">Critical</Badge>;
    case "action_required": return <Badge variant="action">要対応</Badge>;
    case "informational": return <Badge variant="info">情報</Badge>;
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

/* ──── main component ──── */

export function GlassRegulationCard({
  matchId,
  regulation,
  isApplicable,
  matchMethod,
  confidence,
  reason,
  index,
}: GlassRegulationCardProps) {
  const combinedText = [
    regulation?.title ?? "",
    regulation?.summary_ja ?? "",
    reason ?? "",
  ].join(" ");

  const responsibilities = isApplicable === true ? inferResponsibilities(combinedText) : [];
  const smsChapter = isApplicable === true ? inferSmsChapter(combinedText) : null;
  const actions = isApplicable === true ? extractActionItems(reason) : [];

  const isHighConfidence = confidence !== null && confidence >= 0.85;
  const isPotential = isApplicable === null && matchMethod === "potential_match";

  return (
    <motion.li
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 + index * 0.06, ease: [0.4, 0, 0.2, 1] }}
      className={cn(
        "glass rounded-xl p-4 transition-all duration-300 glass-hover list-none",
        isApplicable === true && isHighConfidence && "glow-cyan-strong",
        isApplicable === true && !isHighConfidence && "glow-cyan",
        isPotential && "glow-amber border-amber-500/20",
        isApplicable === false && "opacity-50",
      )}
    >
      {/* Row 1: Badges */}
      <div className="flex flex-wrap items-center gap-1.5 mb-2">
        {regulation && severityBadge(regulation.severity)}
        {sourceBadge(regulation?.source)}
        {matchMethod === "user_confirmed" && (
          <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/20 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
            <CheckCircle size={10} />
            確認済み
          </span>
        )}
        {responsibilities.map((r) =>
          r === "ship" ? (
            <span key="ship" className="inline-flex items-center gap-0.5 rounded-full bg-blue-500/15 border border-blue-500/20 px-2 py-0.5 text-[11px] font-medium text-blue-300">
              <Anchor size={10} />
              船側
            </span>
          ) : (
            <span key="company" className="inline-flex items-center gap-0.5 rounded-full bg-purple-500/15 border border-purple-500/20 px-2 py-0.5 text-[11px] font-medium text-purple-300">
              <Shield size={10} />
              会社側
            </span>
          ),
        )}
      </div>

      {/* Row 2: Title */}
      {regulation ? (
        <Link
          href={`/news/${regulation.id}`}
          className="group font-medium text-sm leading-snug block mb-1.5 text-zinc-200 hover:text-accent-cyan transition-colors"
        >
          {regulation.title}
          <ExternalLink size={12} className="inline ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
        </Link>
      ) : (
        <span className="text-zinc-500 block mb-1.5 text-sm">(規制情報なし)</span>
      )}

      {/* Row 3: Summary */}
      {regulation?.summary_ja && (
        <p className="text-xs text-zinc-400 line-clamp-2 mb-2 leading-relaxed">
          {regulation.summary_ja}
        </p>
      )}

      {/* Row 4: Metadata */}
      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500 mb-1.5">
        <DeadlineBadge effectiveDate={regulation?.effective_date ?? null} />
        {confidence !== null && (
          <span className={cn(
            "tabular-nums",
            confidence >= 0.85 ? "text-cyan-400" : confidence >= 0.7 ? "text-zinc-400" : "text-amber-400",
          )}>
            確度 {Math.round(confidence * 100)}%
          </span>
        )}
        {regulation?.published_at && (
          <span>
            {new Date(regulation.published_at).toLocaleDateString("ja-JP", {
              year: "numeric", month: "2-digit", day: "2-digit",
            })} 掲載
          </span>
        )}
      </div>

      {/* Row 5: SMS chapter */}
      {smsChapter && (
        <p className="text-[11px] text-zinc-500">
          <span className="text-cyan-500/70">ISM</span> {smsChapter.chapter} {smsChapter.title}
        </p>
      )}

      {/* Row 6: Action items */}
      {actions.length > 0 && (
        <div className="mt-2.5 pt-2.5 border-t border-white/5">
          <p className="text-[10px] font-medium text-zinc-500 mb-1.5">対応アクション</p>
          <div className="flex flex-wrap gap-1.5">
            {actions.map((action) => (
              <span
                key={action.label}
                className={cn("inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] font-medium", action.colorClass)}
              >
                {action.icon}
                {action.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Row 7: AI reason (non-applicable) */}
      {reason && isApplicable !== true && !isPotential && (
        <p className="text-xs text-zinc-500 mt-1.5">
          {reason.startsWith("AI 判定失敗")
            ? "AI による判定を再試行中です。しばらくお待ちください。"
            : reason}
        </p>
      )}

      {/* Row 8: Feedback buttons */}
      {isApplicable === true &&
        (matchMethod === "convention_based" || matchMethod === "ai_matching") && (
        <div className="mt-2.5 pt-2.5 border-t border-white/5">
          <FeedbackButtons matchId={matchId} currentApplicable={isApplicable} />
        </div>
      )}

      {/* Row 9: Potential match confirmation */}
      {isPotential && (
        <PotentialMatchCard matchId={matchId} reason={reason} />
      )}
    </motion.li>
  );
}
