import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { cn } from "@/lib/utils";
import {
  Ship,
  Plus,
  Eye,
  EyeOff,
} from "lucide-react";
import type {
  ShipProfile,
  UserMatch,
  Regulation,
  Publication,
  ShipType,
} from "@/lib/types";
import { SHIP_TYPE_LABELS } from "@/lib/types";
import { DashboardShell } from "./dashboard-shell";

/* ──────────────────── category tab definitions ──────────────────── */

interface CategoryTab {
  key: string;
  label: string;
  keywords: RegExp | null;
}

const CATEGORY_TABS: CategoryTab[] = [
  { key: "all", label: "全て", keywords: null },
  { key: "solas", label: "SOLAS / 安全", keywords: /SOLAS|安全|救命|消防|防火|航海|操舵|無線|復原性|構造/i },
  { key: "marpol", label: "MARPOL / 環境", keywords: /MARPOL|環境|排出|汚染|バラスト|硫黄|NOx|SOx|GHG|CII|EEDI|EEXI|温室/i },
  { key: "stcw", label: "STCW / 船員", keywords: /STCW|MLC|船員|乗組員|資格|manning|配乗|労働|当直|訓練/i },
  { key: "national", label: "国内法 / 旗国", keywords: /国内法|旗国|船舶安全法|海防法|船員法|港則|海上交通|船舶職員|JG|MLIT|e-Gov|国土交通/i },
];

type MatchWithReg = UserMatch & { regulation?: Regulation };

function matchesTab(m: MatchWithReg, tab: CategoryTab): boolean {
  if (!tab.keywords) return true;
  const searchText = [
    m.regulation?.headline ?? "",
    m.regulation?.title ?? "",
    m.regulation?.summary_ja ?? "",
    m.regulation?.category ?? "",
    m.reason ?? "",
  ].join(" ");
  return tab.keywords.test(searchText);
}

/* ══════════════════════════════════════════════════
   Server Component — Data Fetching
   ══════════════════════════════════════════════════ */

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ show?: string; tab?: string }>;
}) {
  const params = await searchParams;
  const showAll = params.show === "all";
  const activeTabKey = params.tab ?? "all";
  const activeTab = CATEGORY_TABS.find((t) => t.key === activeTabKey) ?? CATEGORY_TABS[0];

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // 開発モード: 認証リダイレクト一時停止
  // if (!user) redirect("/login");

  // 開発モード: user が null でも全船表示
  let shipsQuery = supabase.from("ship_profiles").select("id,ship_name,ship_type,gross_tonnage,navigation_area,flag_state,classification_society,radio_equipment,created_at");
  if (user) {
    shipsQuery = shipsQuery.eq("user_id", user.id);
  }
  const { data: ships } = await shipsQuery.order("created_at", { ascending: false });

  const shipList = (ships ?? []) as ShipProfile[];
  const shipIds = shipList.map((s) => s.id);

  let matchesByShip: Record<string, MatchWithReg[]> = {};
  let allPublications: Publication[] = [];

  if (shipIds.length > 0) {
    // 並列: matches + publications を同時取得
    const [matchesResult, pubsResult] = await Promise.all([
      supabase
        .from("user_matches")
        .select("id,regulation_id,ship_profile_id,is_applicable,match_method,confidence,reason,citations,notified,created_at")
        .in("ship_profile_id", shipIds)
        .order("created_at", { ascending: false }),
      supabase
        .from("publications")
        .select("id,title,title_ja,category,publisher,current_edition,current_edition_date,legal_basis,update_cycle")
        .order("category", { ascending: true })
        .order("title_ja", { ascending: true }),
    ]);

    allPublications = (pubsResult.data ?? []) as Publication[];

    const allMatches = (matchesResult.data ?? []) as UserMatch[];
    const regIds = [...new Set(allMatches.map((m) => m.regulation_id))];
    let regsMap: Record<string, Regulation> = {};

    if (regIds.length > 0) {
      const { data: regs } = await supabase
        .from("regulations")
        .select("id,source,source_id,title,headline,summary_ja,category,severity,confidence,published_at,effective_date,onboard_actions,shore_actions,sms_chapters")
        .in("id", regIds);

      for (const r of (regs ?? []) as Regulation[]) {
        regsMap[r.id] = r;
      }
    }

    for (const m of allMatches) {
      const entry = { ...m, regulation: regsMap[m.regulation_id] };
      if (!matchesByShip[m.ship_profile_id]) {
        matchesByShip[m.ship_profile_id] = [];
      }
      matchesByShip[m.ship_profile_id].push(entry);
    }
  } else {
    // 船がなくても publications は取得
    const { data: dbPubs } = await supabase
      .from("publications")
      .select("id,title,title_ja,category,publisher,current_edition,current_edition_date,legal_basis,update_cycle")
      .order("category", { ascending: true });
    allPublications = (dbPubs ?? []) as Publication[];
  }

  /* ── Build serializable data for client shell ── */

  const shipData = shipList.map((ship) => {
    const allShipMatches = (matchesByShip[ship.id] ?? []).sort((a, b) => {
      const order = (v: boolean | null) => (v === true ? 0 : v === null ? 1 : 2);
      const orderDiff = order(a.is_applicable) - order(b.is_applicable);
      if (orderDiff !== 0) return orderDiff;
      const dateA = a.regulation?.published_at ?? "";
      const dateB = b.regulation?.published_at ?? "";
      return dateB.localeCompare(dateA);
    });

    const applicableMatches = allShipMatches.filter((m) => m.is_applicable === true);
    const potentialMatches = allShipMatches.filter(
      (m) => m.is_applicable === null,
    );
    const baseMatches = showAll ? allShipMatches : applicableMatches;
    const filteredMatches = baseMatches.filter((m) => matchesTab(m, activeTab));

    return {
      ship,
      allCount: allShipMatches.length,
      applicableCount: applicableMatches.length,
      potentialCount: potentialMatches.length,
      potentialMatches: showAll ? [] : potentialMatches.slice(0, 3),
      filteredMatches,
      hasMorePotential: potentialMatches.length > 3,
      totalPotential: potentialMatches.length,
      publications: allPublications,
    };
  });

  return (
    <div className="min-h-screen bg-navy dark:bg-navy">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-1">
            Maritime Command Center
          </h1>
          <p className="text-sm text-zinc-400">
            自船に該当する規制をリアルタイムに監視
          </p>
        </div>

        {shipList.length === 0 ? (
          /* Empty state */
          <div className="glass rounded-2xl p-12 text-center glow-cyan">
            <Ship size={48} className="mx-auto mb-4 text-cyan-500/50" />
            <p className="text-zinc-400 mb-6">船舶が登録されていません</p>
            <Link
              href="/ships/new"
              className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-6 py-3 text-sm font-medium text-white hover:bg-cyan-500 transition-colors"
            >
              <Plus size={16} />
              船舶を登録する
            </Link>
          </div>
        ) : (
          <>
            {/* Category tabs — 記事の直上 */}
            <nav className="flex gap-1.5 mb-5 overflow-x-auto pb-1 -mx-1 px-1">
              {CATEGORY_TABS.map((tab) => {
                const isActive = tab.key === activeTab.key;
                const p = new URLSearchParams();
                if (showAll) p.set("show", "all");
                if (tab.key !== "all") p.set("tab", tab.key);
                const qs = p.toString();
                const href = `/dashboard${qs ? `?${qs}` : ""}`;
                return (
                  <Link
                    key={tab.key}
                    href={href}
                    className={cn(
                      "whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200",
                      isActive
                        ? "bg-cyan-600 text-white shadow-lg shadow-cyan-600/20"
                        : "glass text-zinc-400 hover:text-zinc-200 hover:bg-white/8",
                    )}
                  >
                    {tab.label}
                  </Link>
                );
              })}
            </nav>

            {/* Ship sections */}
            <DashboardShell
              shipData={shipData.map((sd) => ({
                ship: {
                  id: sd.ship.id,
                  shipName: sd.ship.ship_name,
                  shipType: SHIP_TYPE_LABELS[sd.ship.ship_type as ShipType] ?? sd.ship.ship_type,
                  grossTonnage: sd.ship.gross_tonnage,
                  editHref: `/ships/${sd.ship.id}`,
                },
                applicableCount: sd.applicableCount,
                potentialCount: sd.potentialCount,
                totalCount: sd.allCount,
                filteredMatches: sd.filteredMatches.map((m) => ({
                  matchId: m.id,
                  regulation: m.regulation,
                  isApplicable: m.is_applicable,
                  matchMethod: m.match_method,
                  confidence: m.confidence,
                  reason: m.reason,
                })),
                potentialMatches: sd.potentialMatches.map((m) => ({
                  matchId: m.id,
                  regulation: m.regulation,
                  isApplicable: m.is_applicable,
                  matchMethod: m.match_method,
                  confidence: m.confidence,
                  reason: m.reason,
                })),
                hasMorePotential: sd.hasMorePotential,
                totalPotential: sd.totalPotential,
                publications: sd.publications,
              }))}
              showAll={showAll}
              activeTabKey={activeTabKey}
            />

            {/* Footer links */}
            <div className="mt-8 flex items-center justify-between">
              <Link
                href="/ships/new"
                className="inline-flex items-center gap-1.5 text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                <Plus size={14} />
                船舶を追加する
              </Link>
              {!showAll ? (
                <Link
                  href="/dashboard?show=all"
                  className="inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  <Eye size={13} />
                  全てのマッチング結果を見る
                </Link>
              ) : (
                <Link
                  href="/dashboard"
                  className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
                >
                  <EyeOff size={13} />
                  該当のみ表示に戻る
                </Link>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
