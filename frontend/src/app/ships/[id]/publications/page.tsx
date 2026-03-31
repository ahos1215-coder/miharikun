import { redirect } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { ArrowLeft, BookOpen } from "lucide-react";
import type {
  ShipProfile,
  Publication,
  ShipPublication,
  PublicationCategory,
} from "@/lib/types";
import { PublicationsShell } from "./publications-shell";

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ category?: string }>;
}

export default async function ShipPublicationsPage({
  params,
  searchParams,
}: PageProps) {
  const { id } = await params;
  const { category } = await searchParams;
  const supabase = await createClient();

  // Auth check
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  // Fetch ship profile with ownership check
  const { data: ship, error: shipError } = await supabase
    .from("ship_profiles")
    .select("*")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();

  if (shipError || !ship) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="text-center">
          <p className="text-zinc-500 mb-4">船舶が見つかりません</p>
          <Link
            href="/dashboard"
            className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            ダッシュボードに戻る
          </Link>
        </div>
      </div>
    );
  }

  const typedShip = ship as ShipProfile;

  // Fetch ship_publications joined with publications
  const { data: shipPublications, error: pubError } = await supabase
    .from("ship_publications")
    .select("*, publication:publications(*)")
    .eq("ship_profile_id", id);

  if (pubError) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <p className="text-zinc-500">書籍情報の取得に失敗しました</p>
      </div>
    );
  }

  const publications: (ShipPublication & { publication: Publication })[] =
    (shipPublications ?? []) as (ShipPublication & {
      publication: Publication;
    })[];

  // Compute stats
  const mandatory = publications.filter((p) => p.priority === "mandatory");
  const stats = {
    mandatory: mandatory.length,
    current: mandatory.filter((p) => p.status === "current").length,
    outdated: mandatory.filter((p) => p.status === "outdated").length,
    unknown: mandatory.filter(
      (p) => p.status === "unknown" || p.status === "missing",
    ).length,
  };

  // Compliance gauge
  const totalForGauge = stats.mandatory || 1;
  const complianceRate = Math.round((stats.current / totalForGauge) * 100);

  // Category filter
  const validCategories: PublicationCategory[] = ["A", "B", "C", "D"];
  const activeCategory =
    category && validCategories.includes(category as PublicationCategory)
      ? (category as PublicationCategory)
      : null;

  const filtered = activeCategory
    ? publications.filter((p) => p.publication.category === activeCategory)
    : publications;

  // Sort: outdated first, then missing, then unknown, then current
  const statusOrder: Record<string, number> = {
    outdated: 0,
    missing: 1,
    unknown: 2,
    current: 3,
    not_required: 4,
  };
  const sorted = [...filtered].sort(
    (a, b) => (statusOrder[a.status] ?? 5) - (statusOrder[b.status] ?? 5),
  );

  const isEmpty = publications.length === 0;

  return (
    <div className="min-h-screen bg-[#0a1628]">
      <div className="mx-auto max-w-4xl px-4 py-8">
        {/* Back link */}
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 transition-colors mb-6"
        >
          <ArrowLeft size={14} />
          ダッシュボードに戻る
        </Link>

        {/* Hero: Ship name + Compliance gauge */}
        <PublicationsShell
          shipName={typedShip.ship_name}
          complianceRate={complianceRate}
          stats={stats}
          publications={sorted}
          activeCategory={activeCategory}
          shipId={id}
          isEmpty={isEmpty}
        />

        {/* Footer */}
        <div className="mt-8 text-center">
          <Link
            href="/dashboard"
            className="text-sm text-zinc-500 hover:text-cyan-400 transition-colors"
          >
            ダッシュボードに戻る
          </Link>
        </div>
      </div>
    </div>
  );
}
