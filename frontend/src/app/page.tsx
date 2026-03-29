import { Anchor } from "lucide-react";
import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center gap-8 px-4 py-16">
      <Anchor className="h-16 w-16 text-blue-600" />
      <h1 className="text-3xl font-bold tracking-tight">MIHARIKUN</h1>
      <p className="max-w-lg text-center text-zinc-600 dark:text-zinc-400">
        膨大な海事規制の中から、あなたの船にだけ関係ある情報を
        AIが自動で抽出・通知します。
      </p>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          href="/news"
          className="rounded border border-zinc-300 px-6 py-2 text-sm font-medium hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          [NEWS] 最新規制を見る
        </Link>
        <Link
          href="/login"
          className="rounded bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          無料で始める
        </Link>
      </div>

      <div className="mt-8 grid max-w-2xl gap-6 text-sm sm:grid-cols-3">
        <div className="text-center">
          <p className="text-2xl">{"[AUTO]"}</p>
          <p className="mt-1 font-medium">自動収集</p>
          <p className="mt-1 text-zinc-500">
            国交省・ClassNK の規制を毎日自動チェック
          </p>
        </div>
        <div className="text-center">
          <p className="text-2xl">{"[AI]"}</p>
          <p className="mt-1 font-medium">AI分類</p>
          <p className="mt-1 text-zinc-500">
            Gemini AIが内容を解析し重要度・カテゴリを判定
          </p>
        </div>
        <div className="text-center">
          <p className="text-2xl">{"[SHIP]"}</p>
          <p className="mt-1 font-medium">船別マッチング</p>
          <p className="mt-1 text-zinc-500">
            船型・トン数・航行区域から関係する規制だけを通知
          </p>
        </div>
      </div>
    </div>
  );
}
<!-- auto-deploy test -->
