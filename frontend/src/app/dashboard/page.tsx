import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type {
  ShipProfile,
  UserMatch,
  Regulation,
  Severity,
  ShipType,
} from "@/lib/types";
import { SHIP_TYPE_LABELS } from "@/lib/types";

function severityBadge(severity: Severity) {
  switch (severity) {
    case "critical":
      return <span className="text-red-600 font-bold">[CRITICAL]</span>;
    case "action_required":
      return <span className="text-amber-600 font-bold">[ACTION]</span>;
    case "informational":
      return <span className="text-zinc-500 font-bold">[INFO]</span>;
  }
}

function applicabilityLabel(isApplicable: boolean | null) {
  if (isApplicable === true) {
    return <span className="text-green-700 font-semibold">該当</span>;
  }
  if (isApplicable === false) {
    return <span className="text-zinc-400">非該当</span>;
  }
  return <span className="text-amber-600">判定中</span>;
}

export default async function DashboardPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const { data: ships } = await supabase
    .from("ship_profiles")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const shipList = (ships ?? []) as ShipProfile[];

  // Fetch matches for all user's ships
  const shipIds = shipList.map((s) => s.id);

  let matchesByShip: Record<string, (UserMatch & { regulation: Regulation })[]> = {};

  if (shipIds.length > 0) {
    const { data: matches } = await supabase
      .from("user_matches")
      .select("*, regulation:regulations(*)")
      .in("ship_profile_id", shipIds)
      .order("created_at", { ascending: false });

    const allMatches = (matches ?? []) as (UserMatch & {
      regulation: Regulation;
    })[];

    for (const m of allMatches) {
      if (!matchesByShip[m.ship_profile_id]) {
        matchesByShip[m.ship_profile_id] = [];
      }
      matchesByShip[m.ship_profile_id].push(m);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">ダッシュボード</h1>

      {shipList.length === 0 ? (
        <div className="rounded border border-zinc-200 p-6 dark:border-zinc-800 text-center">
          <p className="text-zinc-500 mb-4">船舶が登録されていません</p>
          <Link
            href="/ships/new"
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            船舶を登録する
          </Link>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-6">
            {shipList.map((ship) => {
              const matches = matchesByShip[ship.id] ?? [];
              return (
                <div
                  key={ship.id}
                  className="rounded border border-zinc-200 p-4 dark:border-zinc-800"
                >
                  <div className="mb-3">
                    <h2 className="text-lg font-semibold">
                      {ship.ship_name}
                    </h2>
                    <p className="text-sm text-zinc-500">
                      {SHIP_TYPE_LABELS[ship.ship_type as ShipType] ??
                        ship.ship_type}{" "}
                      / {ship.gross_tonnage.toLocaleString()} GT
                    </p>
                  </div>

                  {matches.length === 0 ? (
                    <p className="text-sm text-zinc-400">
                      マッチした規制はまだありません
                    </p>
                  ) : (
                    <ul className="flex flex-col gap-2">
                      {matches.map((m) => (
                        <li
                          key={m.id}
                          className="rounded border border-zinc-100 p-3 dark:border-zinc-800 text-sm"
                        >
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            {applicabilityLabel(m.is_applicable)}
                            {m.regulation &&
                              severityBadge(m.regulation.severity)}
                            {m.confidence !== null && (
                              <span className="text-xs text-zinc-400">
                                確度 {Math.round(m.confidence * 100)}%
                              </span>
                            )}
                          </div>
                          {m.regulation ? (
                            <Link
                              href={`/news/${m.regulation.id}`}
                              className="hover:underline"
                            >
                              {m.regulation.title}
                            </Link>
                          ) : (
                            <span className="text-zinc-400">
                              (規制情報なし)
                            </span>
                          )}
                          {m.reason && (
                            <p className="text-xs text-zinc-500 mt-1">
                              {m.reason}
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-6">
            <Link
              href="/ships/new"
              className="text-sm text-blue-600 hover:underline"
            >
              + 船舶を追加する
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
