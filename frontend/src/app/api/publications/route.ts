import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

interface UpdateBody {
  shipPublicationId: string;
  ownedEdition?: string | null;
  ownedEditionDate?: string | null;
  status?: string;
  notes?: string | null;
}

function isValidUpdateBody(body: unknown): body is UpdateBody {
  if (typeof body !== "object" || body === null) return false;
  const b = body as Record<string, unknown>;
  if (typeof b.shipPublicationId !== "string") return false;

  const validStatuses = ["current", "outdated", "missing", "unknown", "not_required"];
  if (b.status !== undefined && (typeof b.status !== "string" || !validStatuses.includes(b.status))) {
    return false;
  }

  return true;
}

// GET /api/publications?shipId=xxx
// 船舶IDに紐づく備付書籍一覧を返す（publications マスターとJOIN）
export async function GET(request: Request) {
  const supabase = await createClient();

  // 1. 認証チェック
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // 2. shipId パラメータ取得
  const { searchParams } = new URL(request.url);
  const shipId = searchParams.get("shipId");

  if (!shipId) {
    return NextResponse.json(
      { error: "Missing required parameter: shipId" },
      { status: 400 },
    );
  }

  // 3. ship_profiles の所有権チェック
  const { data: ship, error: shipError } = await supabase
    .from("ship_profiles")
    .select("id")
    .eq("id", shipId)
    .eq("user_id", user.id)
    .single();

  if (shipError || !ship) {
    return NextResponse.json(
      { error: "Ship not found or access denied" },
      { status: 403 },
    );
  }

  // 4. ship_publications を publications と JOIN して取得
  const { data, error } = await supabase
    .from("ship_publications")
    .select(`
      id,
      ship_profile_id,
      publication_id,
      status,
      owned_edition,
      owned_edition_date,
      needs_update,
      priority,
      notes,
      created_at,
      updated_at,
      publication:publications (
        id,
        title,
        title_ja,
        category,
        publisher,
        current_edition,
        current_edition_date,
        previous_edition,
        isbn,
        legal_basis,
        applicable_conventions,
        update_cycle,
        purchase_url,
        notes
      )
    `)
    .eq("ship_profile_id", shipId)
    .order("created_at", { ascending: true });

  if (error) {
    console.error("Failed to fetch ship_publications:", error);
    return NextResponse.json(
      { error: "Failed to fetch publications" },
      { status: 500 },
    );
  }

  return NextResponse.json({ data });
}

// PUT /api/publications
// 所持版数・ステータスの更新
export async function PUT(request: Request) {
  const supabase = await createClient();

  // 1. 認証チェック
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // 2. リクエストボディのパース
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!isValidUpdateBody(body)) {
    return NextResponse.json(
      {
        error:
          "Invalid request body. Required: shipPublicationId (string). Optional: ownedEdition, ownedEditionDate, status, notes",
      },
      { status: 400 },
    );
  }

  // 3. ship_publications レコードの存在確認
  const { data: shipPub, error: fetchError } = await supabase
    .from("ship_publications")
    .select("id, ship_profile_id")
    .eq("id", body.shipPublicationId)
    .single();

  if (fetchError || !shipPub) {
    return NextResponse.json(
      { error: "Ship publication record not found" },
      { status: 404 },
    );
  }

  // 4. ship_profile の所有権チェック
  const { data: ship, error: shipError } = await supabase
    .from("ship_profiles")
    .select("id")
    .eq("id", shipPub.ship_profile_id)
    .eq("user_id", user.id)
    .single();

  if (shipError || !ship) {
    return NextResponse.json(
      { error: "Forbidden" },
      { status: 403 },
    );
  }

  // 5. 更新データの構築
  const updateData: Record<string, string | boolean | null> = {};

  if (body.ownedEdition !== undefined) {
    updateData.owned_edition = body.ownedEdition;
  }
  if (body.ownedEditionDate !== undefined) {
    updateData.owned_edition_date = body.ownedEditionDate;
  }
  if (body.status !== undefined) {
    updateData.status = body.status;
  }
  if (body.notes !== undefined) {
    updateData.notes = body.notes;
  }

  if (Object.keys(updateData).length === 0) {
    return NextResponse.json(
      { error: "No fields to update" },
      { status: 400 },
    );
  }

  // 6. 更新実行
  const { error: updateError } = await supabase
    .from("ship_publications")
    .update(updateData)
    .eq("id", body.shipPublicationId);

  if (updateError) {
    console.error("Failed to update ship_publications:", updateError);
    return NextResponse.json(
      { error: "Failed to update publication" },
      { status: 500 },
    );
  }

  return NextResponse.json({ success: true });
}
