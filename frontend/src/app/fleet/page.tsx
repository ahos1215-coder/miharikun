import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { cn } from "@/lib/utils";
import type {
  ShipProfile,
  UserMatch,
  Regulation,
  ShipType,
  NavigationArea,
} from "@/lib/types";
import { SHIP_TYPE_LABELS } from "@/lib/types";

interface ConventionBadge {
  code: string;
  label: string;
  color: string;
}

/** Ship specs に基づいて適用される条約バッジを返す */
function getApplicableConventionBadges(ship: ShipProfile): ConventionBadge[] {
  const badges: ConventionBadge[] = [];
  const gt = ship.gross_tonnage;
  const isInternational = (ship.navigation_area as NavigationArea[]).includes("international");
  const shipType = ship.ship_type as ShipType;

  // GT≥500 + international → core conventions
  if (gt >= 500 && isInternational) {
    badges.push({ code: "SOLAS", label: "SOLAS", color: "bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800" });
    badges.push({ code: "ISM", label: "ISM", color: "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800" });
    badges.push({ code: "ISPS", label: "ISPS", color: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800" });
    badges.push({ code: "STCW", label: "STCW", color: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800" });
    badges.push({ code: "MLC", label: "MLC", color: "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950 dark:text-indigo-300 dark:border-indigo-800" });
  }

  // GT≥400 → MARPOL, AFS
  if (gt >= 400) {
    badges.push({ code: "MARPOL I", label: "MARPOL I", color: "bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800" });
    badges.push({ code: "MARPOL VI", label: "MARPOL VI", color: "bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950 dark:text-teal-300 dark:border-teal-800" });
    badges.push({ code: "AFS", label: "AFS", color: "bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-950 dark:text-cyan-300 dark:border-cyan-800" });
  }

  // Bulk carrier specific
  if (shipType === "bulk_carrier") {
    badges.push({ code: "IMSBC", label: "IMSBC", color: "bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800" });
    badges.push({ code: "ESP", label: "ESP", color: "bg-lime-50 text-lime-700 border-lime-200 dark:bg-lime-950 dark:text-lime-300 dark:border-lime-800" });
  }

  // Tanker / chemical / LPG / LNG specific
  if (["tanker", "chemical", "lpg", "lng"].includes(shipType)) {
    badges.push({ code: "IBC", label: "IBC/IGC", color: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-800" });
  }

  // Passenger specific
  if (shipType === "passenger") {
    badges.push({ code: "LSA", label: "LSA", color: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950 dark:text-sky-300 dark:border-sky-800" });
  }

  return badges;
}

export default async function FleetPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  // 開発モード: 認証不要
  // if (!user) redirect("/login");

  // 全船舶を取得（開発モード: user_id チェック緩和）
  let shipsQuery = supabase.from("ship_profiles").select("id,ship_name,ship_type,gross_tonnage,navigation_area,flag_state,classification_society,created_at");
  if (user) {
    shipsQuery = shipsQuery.eq("user_id", user.id);
  }
  const { data: ships } = await shipsQuery.order("created_at", { ascending: false });

  const shipList = (ships ?? []) as ShipProfile[];
  const shipIds = shipList.map((s) => s.id);

  let matchStats: Record<
    string,
    { applicableCount: number; totalAssessed: number; lastMatchedAt: string | null }
  > = {};

  if (shipIds.length > 0) {
    const { data: matches } = await supabase
      .from("user_matches")
      .select("id,regulation_id,ship_profile_id,is_applicable")
      .in("ship_profile_id", shipIds);

    const allMatches = (matches ?? []) as UserMatch[];

    for (const m of allMatches) {
      if (!matchStats[m.ship_profile_id]) {
        matchStats[m.ship_profile_id] = { applicableCount: 0, totalAssessed: 0, lastMatchedAt: null };
      }
      const stat = matchStats[m.ship_profile_id];
      if (m.is_applicable !== null) stat.totalAssessed++;
      if (m.is_applicable === true) stat.applicableCount++;
    }

    const regIds = [...new Set(allMatches.filter((m) => m.is_applicable === true).map((m) => m.regulation_id))];
    if (regIds.length > 0) {
      const { data: regs } = await supabase
        .from("regulations")
        .select("id,published_at,created_at")
        .in("id", regIds);

      const regsMap: Record<string, { published_at: string | null; created_at: string }> = {};
      for (const r of (regs ?? []) as { id: string; published_at: string | null; created_at: string }[]) {
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
        <h1 className="text-2xl font-bold">フリート管理</h1>
        <Link
          href="/ships/new"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 hover:scale-[1.02] transition-transform"
        >
          船舶を追加
        </Link>
      </div>

      {/* サマリーバー */}
      <div className="motion-preset-fade rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4 mb-6 flex items-center justify-between">
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
          全規制サマリー
        </Link>
      </div>

      {shipList.length === 0 ? (
        <div className="rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-800 p-6 text-center">
          <p className="text-zinc-500 mb-4">船舶が登録されていません</p>
          <Link
            href="/ships/new"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            船舶を登録する
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {shipList.map((ship, index) => {
            const stat = matchStats[ship.id] ?? {
              applicableCount: 0,
              totalAssessed: 0,
              lastMatchedAt: null,
            };
            const badges = getApplicableConventionBadges(ship);
            const complianceRate =
              stat.totalAssessed > 0
                ? Math.round((stat.applicableCount / stat.totalAssessed) * 100)
                : null;
            return (
              <div
                key={ship.id}
                className={cn(
                  "motion-preset-slide-up rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-800 p-4 hover:shadow-md transition-shadow",
                  index === 1 ? "motion-delay-75" :
                  index === 2 ? "motion-delay-100" :
                  index >= 3 ? "motion-delay-150" : "",
                )}
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h2 className="font-semibold text-base">
                      {ship.ship_name}
                    </h2>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {SHIP_TYPE_LABELS[ship.ship_type as ShipType] ??
                        ship.ship_type}{" "}
                      / {ship.gross_tonnage.toLocaleString()} GT
                    </p>
                  </div>
                  <Link
                    href={`/ships/${ship.id}`}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    編集
                  </Link>
                </div>

                {/* 適用条約バッジ */}
                {badges.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {badges.map((badge) => (
                      <span
                        key={badge.code}
                        className={cn(
                          "inline-block rounded px-1.5 py-0.5 text-[10px] font-medium border",
                          badge.color,
                        )}
                      >
                        {badge.label}
                      </span>
                    ))}
                  </div>
                )}

                {/* コンプライアンス対応率 */}
                {complianceRate !== null && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-zinc-500 dark:text-zinc-400">
                        コンプライアンス対応率
                      </span>
                      <span
                        className={cn(
                          "font-semibold",
                          complianceRate >= 80
                            ? "text-green-600"
                            : complianceRate >= 50
                              ? "text-amber-600"
                              : "text-red-600",
                        )}
                      >
                        {complianceRate}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all",
                          complianceRate >= 80
                            ? "bg-green-500"
                            : complianceRate >= 50
                              ? "bg-amber-500"
                              : "bg-red-500",
                        )}
                        style={{ width: `${complianceRate}%` }}
                      />
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400 mt-3">
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
                    詳細を見る
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
