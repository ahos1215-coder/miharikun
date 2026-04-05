// ISR: トップページは1時間キャッシュ（規制件数は頻繁に変わらない）
export const revalidate = 3600;

import {
  Anchor,
  Ship,
  Brain,
  Bell,
  RefreshCw,
  Wifi,
} from "lucide-react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { cn } from "@/lib/utils";

export default async function Home() {
  const supabase = await createClient();

  const [
    { count: totalRegulations },
    { count: nkRegulations },
    { count: mlitRegulations },
    { count: totalShips },
  ] = await Promise.all([
    supabase.from("regulations").select("*", { count: "exact", head: true }),
    supabase
      .from("regulations")
      .select("*", { count: "exact", head: true })
      .ilike("source", "nk"),
    supabase
      .from("regulations")
      .select("*", { count: "exact", head: true })
      .ilike("source", "MLIT"),
    supabase
      .from("ship_profiles")
      .select("*", { count: "exact", head: true }),
  ]);

  const showStats =
    (totalRegulations ?? 0) > 0 || (totalShips ?? 0) > 0;

  return (
    <div className="flex flex-col">
      {/* ───────── 1. Hero Section ───────── */}
      <section
        className={cn(
          "flex flex-col items-center gap-6 px-4 py-24 text-center",
          "bg-gradient-to-b from-blue-50 via-white to-white",
          "dark:from-blue-950/20 dark:via-zinc-950 dark:to-zinc-950",
          "motion-preset-fade motion-duration-700"
        )}
      >
        <Anchor className="h-12 w-12 text-blue-600" />
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          MIHARIKUN
        </h1>
        <p className="text-lg text-zinc-500">海事規制モニタリング AI</p>
        <p className="max-w-xl text-zinc-600 dark:text-zinc-400">
          膨大な海事規制の中から、あなたの船にだけ関係ある情報をAIが自動で抽出・通知します。
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/news"
            className={cn(
              "rounded-lg border border-zinc-300 px-8 py-3 text-sm font-medium",
              "hover:scale-105 hover:bg-zinc-50 transition-transform",
              "dark:border-zinc-700 dark:hover:bg-zinc-900"
            )}
          >
            最新規制を見る
          </Link>
          <Link
            href="/dashboard"
            className={cn(
              "rounded-lg bg-blue-600 px-8 py-3 text-sm font-medium text-white",
              "hover:scale-105 hover:bg-blue-700 transition-transform"
            )}
          >
            ダッシュボードを見る
          </Link>
        </div>
      </section>

      {/* ───────── 2. How It Works ───────── */}
      <section className="px-4 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-12 text-center text-2xl font-bold motion-preset-fade">
            3ステップで完結
          </h2>

          <div className="relative grid gap-10 sm:grid-cols-3 sm:gap-6">
            {/* dashed connector line (desktop only) */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute top-10 left-[16.67%] right-[16.67%] hidden border-t-2 border-dashed border-zinc-300 dark:border-zinc-700 sm:block"
            />

            {(
              [
                {
                  num: 1,
                  icon: Ship,
                  title: "船舶を登録",
                  desc: "船種・トン数・航行区域を入力するだけ",
                },
                {
                  num: 2,
                  icon: Brain,
                  title: "AIが自動監視",
                  desc: "NK・国交省の規制を毎日チェック＆分類",
                },
                {
                  num: 3,
                  icon: Bell,
                  title: "該当規制を通知",
                  desc: "自船に関係ある規制だけをお届け",
                },
              ] as const
            ).map((step, i) => (
              <div
                key={step.num}
                className={cn(
                  "relative flex flex-col items-center text-center",
                  "motion-preset-slide-up",
                  i === 0 && "motion-delay-100",
                  i === 1 && "motion-delay-200",
                  i === 2 && "motion-delay-300"
                )}
              >
                {/* number circle */}
                <span
                  className={cn(
                    "z-10 mb-3 flex h-8 w-8 items-center justify-center rounded-full",
                    "bg-blue-600 text-sm font-bold text-white"
                  )}
                >
                  {step.num}
                </span>
                <step.icon className="mb-3 h-8 w-8 text-blue-600" />
                <p className="font-medium">{step.title}</p>
                <p className="mt-1 text-sm text-zinc-500">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ───────── 3. Features ───────── */}
      <section className="bg-zinc-50 px-4 py-20 dark:bg-zinc-900/50">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-12 text-center text-2xl font-bold motion-preset-fade">
            主な機能
          </h2>

          <div className="grid gap-6 sm:grid-cols-2">
            {(
              [
                {
                  icon: RefreshCw,
                  title: "自動収集",
                  desc: "ClassNK、国交省、e-Govを毎日自動チェック",
                },
                {
                  icon: Brain,
                  title: "AI分類",
                  desc: "Gemini AIが重要度・カテゴリを自動判定",
                },
                {
                  icon: Ship,
                  title: "船別マッチング",
                  desc: "船型・トン数・航行区域から関係する規制だけを抽出",
                },
                {
                  icon: Wifi,
                  title: "船上対応",
                  desc: "衛星通信下でも動作するオフライン対応PWA",
                },
              ] as const
            ).map((feat, i) => (
              <div
                key={feat.title}
                className={cn(
                  "rounded-xl border border-zinc-200 bg-white p-6 shadow-sm",
                  "dark:border-zinc-800 dark:bg-zinc-900",
                  "motion-preset-slide-up",
                  i === 0 && "motion-delay-100",
                  i === 1 && "motion-delay-200",
                  i === 2 && "motion-delay-300",
                  i === 3 && "motion-delay-[400ms]"
                )}
              >
                <feat.icon className="mb-3 h-7 w-7 text-blue-600" />
                <p className="font-medium">{feat.title}</p>
                <p className="mt-1 text-sm text-zinc-500">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ───────── 4. Stats ───────── */}
      {showStats && (
        <section className="px-4 py-16 motion-preset-fade motion-delay-200">
          <div className="mx-auto flex max-w-5xl flex-wrap justify-center gap-8">
            {(totalRegulations ?? 0) > 0 && (
              <div className="text-center">
                <p className="text-4xl font-bold text-blue-600">
                  {totalRegulations}
                </p>
                <p className="mt-1 text-sm text-zinc-500">監視中の規制</p>
              </div>
            )}
            {(totalShips ?? 0) > 0 && (
              <div className="text-center">
                <p className="text-4xl font-bold text-emerald-600">
                  {totalShips}
                </p>
                <p className="mt-1 text-sm text-zinc-500">登録船舶</p>
              </div>
            )}
            <div className="text-center">
              <p className="text-4xl font-bold text-zinc-700 dark:text-zinc-300">
                2
              </p>
              <p className="mt-1 text-sm text-zinc-500">データソース</p>
            </div>
          </div>
        </section>
      )}

      {/* ───────── 5. CTA Repeat ───────── */}
      <section className="px-4 py-20 text-center motion-preset-fade">
        <Link
          href="/dashboard"
          className={cn(
            "inline-block rounded-lg bg-blue-600 px-8 py-3 text-sm font-medium text-white",
            "hover:scale-105 hover:bg-blue-700 transition-transform"
          )}
        >
          ダッシュボードを見る
        </Link>
        <p className="mt-3 text-sm text-zinc-400">
          開発中 — フィードバック歓迎です。
        </p>
      </section>

      {/* ───────── 6. Trust / Disclaimer ───────── */}
      <section className="border-t border-zinc-200 px-4 py-8 text-center dark:border-zinc-800">
        <p className="mx-auto max-w-2xl text-xs leading-relaxed text-zinc-400">
          本サービスは ClassNK・国土交通省等の公開情報を自動収集・AI
          解析するものであり、公式な法的助言を提供するものではありません。
          規制対応の最終判断は必ず専門家にご確認ください。
        </p>
      </section>
    </div>
  );
}
