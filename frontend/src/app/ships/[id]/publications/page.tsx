import { redirect } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { ArrowLeft } from "lucide-react";
import type {
  ShipProfile,
  Publication,
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

  // Fetch ALL publications from DB master (法定書籍は船舶登録に関係なく表示)
  const { data: dbPubs } = await supabase
    .from("publications")
    .select("*")
    .order("category", { ascending: true })
    .order("title_ja", { ascending: true });

  const allPublications = (dbPubs ?? []) as Publication[];

  // Category filter
  const validCategories: PublicationCategory[] = ["A", "B", "C", "D"];
  const activeCategory =
    category && validCategories.includes(category as PublicationCategory)
      ? (category as PublicationCategory)
      : null;

  const filtered = activeCategory
    ? allPublications.filter((p) => p.category === activeCategory)
    : allPublications;

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

        <PublicationsShell
          shipName={typedShip.ship_name}
          publications={filtered}
          activeCategory={activeCategory}
          shipId={id}
          totalCount={allPublications.length}
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
