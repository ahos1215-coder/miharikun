import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type {
  ShipProfile,
  UserMatch,
  Regulation,
  ShipType,
} from "@/lib/types";
import { SHIP_TYPE_LABELS } from "@/lib/types";

export default async function FleetPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // 全船舶を取得
  const { data: ships } = await supabase
    .from("ship_profiles")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const shipList = (ships ?? []) as ShipProfile[];
  const shipIds = shipList.map((s) => s.id);

  // 各船舶のマッチ数・最終マッチ日を集計
  let matchStats: Record<
    string,
    { applicableCount: number; lastMatchedAt: string | null }
  > = {};

  if (shipIds.length > 0) {
    const { data: matches } = await supabase
      .from("user_matches")
      .select("*")
      .in("ship_profile_id", shipIds);

    const allMatches = (matches ?? []) as UserMatch[];

    for (const m of allMatches) {
      if (!matchStats[m.ship_profile_id]) {
        matchStats[m.ship_profile_id] = {
          applicableCount: 0,
          lastMatchedAt: null,
        };
      }
      const stat = matchStats[m.ship_profile_id];
      if (m.is_applicable === true) {
        stat.applicableCount++;
      }
      // user_matches には created_at がないため regulation の情報で代替
      // ここでは match の regulation_id の存在を最終マッチとして使う
    }

    // 最終マッチ日は regulations テーブルから取得
    const regIds = [...new Set(allMatches.filter((m) => m.is_applicable === true).map((m) => m.regulation_id))];
    if (regIds.length > 0) {
      const { data: regs } = await supabase
        .from("regulations")
        .select("*")
        .in("id", regIds);

      const regsMap: Record<string, Regulation> = {};
      for (const r of (regs ?? []) as Regulation[]) {
        regsMap[r.id] = r;
      }

      for (const m of allMatches) {
        if (m.is_applicable !== true) continue;
        const reg = regsMap[m.regulation_id];
        if (!reg) continue;
        const stat = matchStats[m.ship_profile_id];
        const regDate = reg.published_at ?? reg.created_at;
        if (!stat.lastMatchedAt || regDate > stat.lastMatchedAt) {
          stat.lastMatchedAt = regDate;
        }
      }
    }
  }

  // サマリー集計
  const totalShips = shipList.length;
  const totalApplicable = Object.values(matchStats).reduce(
    (sum, s) => sum + s.applicableCount,
    0,
  );

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">[FLEET] フリート管理</h1>
        <Link
          href="/ships/new"
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          [ADD] 船舶を追加
        </Link>
      </div>

      {/* サマリーバー */}
      <div className="rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-6 text-sm">
          <span className="font-semibold">
            フリート: <span className="text-blue-600">{totalShips}隻</span>
          </span>
          <span className="font-semibold">
            該当規制: <span className="text-amber-600">{totalApplicable}件</span>
          </span>
        </div>
        <Link
          href="/fleet/summary"
          className="text-sm text-blue-600 hover:underline"
        >
          全規制サマリー →
        </Link>
      </div>

      {shipList.length === 0 ? (
        <div className="rounded border border-zinc-200 dark:border-zinc-800 p-6 text-center">
          <p className="text-zinc-500 mb-4">船舶が登録されていません</p>
          <Link
            href="/ships/new"
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            船舶を登録する
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {shipList.map((ship) => {
            const stat = matchStats[ship.id] ?? {
              applicableCount: 0,
              lastMatchedAt: null,
            };
            return (
              <div
                key={ship.id}
                className="rounded border border-zinc-200 dark:border-zinc-800 p-4 hover:border-blue-400 dark:hover:border-blue-600 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h2 className="font-semibold text-base">
                      [SHIP] {ship.ship_name}
                    </h2>
                    <p className="text-xs text-zinc-500">
                      {SHIP_TYPE_LABELS[ship.ship_type as ShipType] ??
                        ship.ship_type}{" "}
                      / {ship.gross_tonnage.toLocaleString()} GT
                    </p>
                  </div>
                  <Link
                    href={`/ships/${ship.id}`}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    [EDIT]
                  </Link>
                </div>

                <div className="flex items-center gap-4 text-xs text-zinc-500 mt-3">
                  <span>
                    該当規制:{" "}
                    <span
                      className={
                        stat.applicableCount > 0
                          ? "text-amber-600 font-semibold"
                          : ""
                      }
                    >
                      {stat.applicableCount}件
                    </span>
                  </span>
                  <span>
                    最終マッチ:{" "}
                    {stat.lastMatchedAt
                      ? new Date(stat.lastMatchedAt).toLocaleDateString("ja-JP")
                      : "---"}
                  </span>
                </div>

                <div className="mt-3">
                  <Link
                    href={`/dashboard`}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    詳細を見る →
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
