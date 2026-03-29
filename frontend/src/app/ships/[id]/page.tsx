import { createClient } from "@/lib/supabase/server";
import { ShipProfile } from "@/lib/types";
import { ShipEditForm } from "./ship-edit-form";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ShipEditPage({ params }: PageProps) {
  const { id } = await params;
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("ship_profiles")
    .select("*")
    .eq("id", id)
    .single();

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <p className="text-zinc-500">船舶が見つかりません</p>
      </div>
    );
  }

  const ship = data as ShipProfile;

  return <ShipEditForm ship={ship} />;
}
