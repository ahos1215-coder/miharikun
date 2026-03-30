import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { cn } from "@/lib/utils";
import type {
  ShipProfile,
  UserMatch,
  Regulation,
  Severity,
  ShipType,
} from "@/lib/types";
import { SHIP_TYPE_LABELS } from "@/lib/types";

const SEVERITY_ORDER: Record<Severity, number> = {
  critical: 0,
  action_required: 1,
  informational: 2,
};

const SEVERITY_LABELS: Record<Severity, { label: string; className: string }> = {
  critical: {
    label: "重大",
    className: "text-red-600 font-bold",
  },
  action_required: {
    label: "要対応",
    className: "text-amber-600 font-bold",
  },
  informational: {
    label: "情報",
    className: "text-zinc-500 font-bold",
  },
};

const SEVERITY_BORDER: Record<Severity, string> = {
  critical: "border-l-4 border-l-red-500",
  action_required: "border-l-4 border-l-amber-500",
  informational: "border-l-4 border-l-zinc-300 dark:border-l-zinc-600",
};

interface RegulationWithShips {
  regulation: Regulation;
  ships: ShipProfile[];
  matches: UserMatch[];
}

export default async function FleetSummaryPage() {
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
    .eq("user_id", user.id);

  const shipList = (ships ?? []) as ShipProfile[];
  const shipIds = shipList.map((s) => s.id);
  const shipsMap: Record<string, ShipProfile> = {};
  for (const s of shipList) {
    shipsMap[s.id] = s;
  }

  // 該当マッチのみ取得
  let regulationGroups: RegulationWithShips[] = [];

  if (shipIds.length > 0) {
    const { data: matches } = await supabase
      .from("user_matches")
      .select("*")
      .in("ship_profile_id", shipIds)
      .eq("is_applicable", true);

    const allMatches = (matches ?? []) as UserMatch[];

    // regulation_id でグループ化
    const regMatchMap: Record<string, UserMatch[]> = {};
    for (const m of allMatches) {
      if (!regMatchMap[m.regulation_id]) {
        regMatchMap[m.regulation_id] = [];
      }
      regMatchMap[m.regulation_id].push(m);
    }

    // regulations を取得
    const regIds = Object.keys(regMatchMap);
    if (regIds.length > 0) {
      const { data: regs } = await supabase
        .from("regulations")
        .select("*")
        .in("id", regIds);

      for (const reg of (regs ?? []) as Regulation[]) {
        const matchesForReg = regMatchMap[reg.id] ?? [];
        const shipProfileIds = [
          ...new Set(matchesForReg.map((m) => m.ship_profile_id)),
        ];
        regulationGroups.push({
          regulation: reg,
          ships: shipProfileIds
            .map((id) => shipsMap[id])
            .filter((s): s is ShipProfile => !!s),
          matches: matchesForReg,
        });
      }
    }

    // severity でソート（critical -> action_required -> informational）
    regulationGroups.sort(
      (a, b) =>
        SEVERITY_ORDER[a.regulation.severity] -
        SEVERITY_ORDER[b.regulation.severity],
    );
  }

  // severity ごとの件数
  const countBySeverity: Record<Severity, number> = {
    critical: 0,
    action_required: 0,
    informational: 0,
  };
  for (const g of regulationGroups) {
    countBySeverity[g.regulation.severity]++;
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">全船規制サマリー</h1>
        <Link
          href="/fleet"
          className="text-sm text-blue-600 hover:underline"
        >
          フリート一覧へ
        </Link>
      </div>

      {/* サマリーバー */}
      <div className="motion-preset-fade rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <span className="font-semibold">
            対象船舶: <span className="text-blue-600">{shipList.length}隻</span>
          </span>
          <span className="font-semibold">
            該当規制合計:{" "}
            <span className="text-amber-600">{regulationGroups.length}件</span>
          </span>
          {countBySeverity.critical > 0 && (
            <span className="text-red-600 font-semibold">
              重大: {countBySeverity.critical}件
            </span>
          )}
          {countBySeverity.action_required > 0 && (
            <span className="text-amber-600 font-semibold">
              要対応: {countBySeverity.action_required}件
            </span>
          )}
          {countBySeverity.informational > 0 && (
            <span className="text-zinc-500 font-semibold">
              情報: {countBySeverity.informational}件
            </span>
          )}
        </div>
      </div>

      {regulationGroups.length === 0 ? (
        <div className="rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-800 p-6 text-center">
          <p className="text-zinc-500">該当する規制はまだありません</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {regulationGroups.map((group, index) => {
            const sev = SEVERITY_LABELS[group.regulation.severity];
            const borderClass = SEVERITY_BORDER[group.regulation.severity];
            return (
              <div
                key={group.regulation.id}
                className={cn(
                  "motion-preset-slide-up rounded-xl shadow-sm border border-zinc-200 dark:border-zinc-800 p-4",
                  borderClass,
                  index === 1 ? "motion-delay-75" :
                  index === 2 ? "motion-delay-100" :
                  index >= 3 ? "motion-delay-150" : "",
                )}
              >
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className={sev.className}>{sev.label}</span>
                  {group.regulation.effective_date && (
                    <span className="text-xs text-zinc-400 dark:text-zinc-500">
                      施行日:{" "}
                      {new Date(
                        group.regulation.effective_date,
                      ).toLocaleDateString("ja-JP")}
                    </span>
                  )}
                </div>

                <Link
                  href={`/news/${group.regulation.id}`}
                  className="text-sm font-semibold hover:underline hover:text-blue-600"
                >
                  {group.regulation.title}
                </Link>

                {group.regulation.summary_ja && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 line-clamp-2">
                    {group.regulation.summary_ja}
                  </p>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  {group.ships.map((ship) => (
                    <span
                      key={ship.id}
                      className="inline-block rounded-lg bg-blue-50 dark:bg-blue-950 px-2 py-0.5 text-xs text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800"
                    >
                      {ship.ship_name} (
                      {SHIP_TYPE_LABELS[ship.ship_type as ShipType] ??
                        ship.ship_type}
                      )
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
