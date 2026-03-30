import { Anchor } from "lucide-react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

export default async function Home() {
  const supabase = await createClient();

  const [
    { count: totalRegulations },
    { count: nkRegulations },
    { count: mlitRegulations },
    { count: totalShips },
  ] = await Promise.all([
    supabase.from("regulations").select("*", { count: "exact", head: true }),
    supabase.from("regulations").select("*", { count: "exact", head: true }).ilike("source", "nk"),
    supabase.from("regulations").select("*", { count: "exact", head: true }).ilike("source", "MLIT"),
    supabase.from("ship_profiles").select("*", { count: "exact", head: true }),
  ]);
  return (
    <div className="flex flex-col items-center justify-center gap-8 px-4 py-16">
      {/* Hero section with gradient background and fade-in */}
      <div className="flex flex-col items-center gap-4 rounded-2xl bg-gradient-to-b from-blue-50 to-transparent px-8 py-12 dark:from-blue-950/20 motion-preset-fade motion-duration-700">
        <Anchor className="h-16 w-16 text-blue-600" />
        <h1 className="text-3xl font-bold tracking-tight">MIHARIKUN</h1>
        <p className="max-w-lg text-center text-zinc-600 dark:text-zinc-400">
          膨大な海事規制の中から、あなたの船にだけ関係ある情報を
          AIが自動で抽出・通知します。
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          href="/news"
          className="rounded-lg border border-zinc-300 px-6 py-2 text-sm font-medium hover:scale-105 hover:bg-zinc-50 transition-transform dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          [NEWS] 最新規制を見る
        </Link>
        <Link
          href="/login"
          className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:scale-105 hover:bg-blue-700 transition-transform"
        >
          無料で始める
        </Link>
      </div>

      {/* Feature cards with staggered slide-up */}
      <div className="mt-8 grid max-w-2xl gap-6 text-sm sm:grid-cols-3">
        <div className="rounded-xl border border-zinc-200 p-6 text-center shadow-sm dark:border-zinc-800 motion-preset-slide-up motion-delay-100">
          <p className="text-2xl">{"[AUTO]"}</p>
          <p className="mt-1 font-medium">自動収集</p>
          <p className="mt-1 text-zinc-500">
            国交省・ClassNK の規制を毎日自動チェック
          </p>
        </div>
        <div className="rounded-xl border border-zinc-200 p-6 text-center shadow-sm dark:border-zinc-800 motion-preset-slide-up motion-delay-200">
          <p className="text-2xl">{"[AI]"}</p>
          <p className="mt-1 font-medium">AI分類</p>
          <p className="mt-1 text-zinc-500">
            Gemini AIが内容を解析し重要度・カテゴリを判定
          </p>
        </div>
        <div className="rounded-xl border border-zinc-200 p-6 text-center shadow-sm dark:border-zinc-800 motion-preset-slide-up motion-delay-300">
          <p className="text-2xl">{"[SHIP]"}</p>
          <p className="mt-1 font-medium">船別マッチング</p>
          <p className="mt-1 text-zinc-500">
            船型・トン数・航行区域から関係する規制だけを通知
          </p>
        </div>
      </div>

      <div className="mt-10 max-w-lg rounded-xl border border-zinc-200 px-6 py-4 text-center shadow-sm dark:border-zinc-700 motion-preset-fade motion-delay-200">
        <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
          「毎朝5分で、自船に関係ある規制だけを確認。
          <br />
          もう膨大な通達を一つずつ読む必要はありません。」
        </p>
      </div>

      {/* Stats section with rounded-xl and subtle border */}
      <div className="mt-10 flex flex-wrap justify-center gap-4 text-sm">
        <div className="rounded-xl border border-zinc-200 px-5 py-3 text-center shadow-sm dark:border-zinc-700">
          <p className="text-2xl font-bold text-blue-600">{totalRegulations ?? 0}</p>
          <p className="mt-1 text-zinc-500">監視中の規制</p>
        </div>
        <div className="rounded-xl border border-zinc-200 px-5 py-3 text-center shadow-sm dark:border-zinc-700">
          <p className="text-2xl font-bold text-emerald-600">{totalShips ?? 0}</p>
          <p className="mt-1 text-zinc-500">登録船舶</p>
        </div>
        <div className="rounded-xl border border-zinc-200 px-5 py-3 text-center shadow-sm dark:border-zinc-700">
          <p className="text-lg font-bold text-zinc-700 dark:text-zinc-300">NK, 国交省</p>
          <p className="mt-1 text-zinc-500">データソース</p>
        </div>
      </div>
    </div>
  );
}
