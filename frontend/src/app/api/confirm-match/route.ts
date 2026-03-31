import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

interface ConfirmMatchBody {
  matchId: string;
  confirmed: boolean;
  shipProfileUpdate?: Record<string, string | number | boolean | null>;
}

function isValidBody(body: unknown): body is ConfirmMatchBody {
  if (typeof body !== "object" || body === null) return false;
  const b = body as Record<string, unknown>;
  return typeof b.matchId === "string" && typeof b.confirmed === "boolean";
}

export async function POST(request: Request) {
  const supabase = await createClient();

  // 1. 認証チェック
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // リクエストボディのパース
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!isValidBody(body)) {
    return NextResponse.json(
      {
        error:
          "Invalid request body. Required: matchId (string), confirmed (boolean)",
      },
      { status: 400 },
    );
  }

  // 2. user_matches レコードの存在確認 & 所有権チェック
  const { data: match, error: fetchError } = await supabase
    .from("user_matches")
    .select("id, ship_profile_id")
    .eq("id", body.matchId)
    .single();

  if (fetchError || !match) {
    return NextResponse.json(
      { error: "Match not found" },
      { status: 404 },
    );
  }

  // ship_profile が自分のものか確認
  const { data: ship, error: shipError } = await supabase
    .from("ship_profiles")
    .select("id")
    .eq("id", match.ship_profile_id)
    .eq("user_id", user.id)
    .single();

  if (shipError || !ship) {
    return NextResponse.json(
      { error: "Forbidden" },
      { status: 403 },
    );
  }

  // 3. user_matches を更新
  const { error: updateError } = await supabase
    .from("user_matches")
    .update({
      is_applicable: body.confirmed,
      match_method: "user_confirmed",
      confidence: 1.0,
    })
    .eq("id", body.matchId);

  if (updateError) {
    console.error("Failed to update user_matches:", updateError);
    return NextResponse.json(
      { error: "Failed to update match" },
      { status: 500 },
    );
  }

  // 4. ship_profiles の追加スペック更新（オプション）
  if (body.shipProfileUpdate && Object.keys(body.shipProfileUpdate).length > 0) {
    const { error: profileError } = await supabase
      .from("ship_profiles")
      .update(body.shipProfileUpdate)
      .eq("id", match.ship_profile_id)
      .eq("user_id", user.id);

    if (profileError) {
      console.error("Failed to update ship_profiles:", profileError);
      // マッチ更新は成功しているので警告だけ返す
      return NextResponse.json({
        success: true,
        warning: "Match updated but ship profile update failed",
      });
    }
  }

  return NextResponse.json({ success: true });
}
