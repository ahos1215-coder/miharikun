import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

interface FeedbackBody {
  matchId: string;
  isCorrect: boolean;
}

function isValidBody(body: unknown): body is FeedbackBody {
  if (typeof body !== "object" || body === null) return false;
  const b = body as Record<string, unknown>;
  return typeof b.matchId === "string" && typeof b.isCorrect === "boolean";
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
          "Invalid request body. Required: matchId (string), isCorrect (boolean)",
      },
      { status: 400 },
    );
  }

  // 2. user_matches レコードの存在確認 & 所有権チェック
  const { data: match, error: fetchError } = await supabase
    .from("user_matches")
    .select("id, ship_profile_id, reason")
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
  const now = new Date().toISOString();

  if (body.isCorrect) {
    // 正しい判定 — フィードバックを記録するのみ
    const { error: updateError } = await supabase
      .from("user_matches")
      .update({
        user_feedback: "correct",
        feedback_at: now,
      })
      .eq("id", body.matchId);

    if (updateError) {
      console.error("Failed to update user_matches:", updateError);
      return NextResponse.json(
        { error: "Failed to save feedback" },
        { status: 500 },
      );
    }
  } else {
    // 誤判定 — needs_review フラグを立てて reason にも記録
    const existingReason = (match.reason as string) ?? "";
    const feedbackNote = "[ユーザー報告: 誤判定]";
    const updatedReason = existingReason.includes(feedbackNote)
      ? existingReason
      : `${feedbackNote} ${existingReason}`.trim();

    const { error: updateError } = await supabase
      .from("user_matches")
      .update({
        user_feedback: "incorrect",
        feedback_at: now,
        needs_review: true,
        reason: updatedReason,
      })
      .eq("id", body.matchId);

    if (updateError) {
      console.error("Failed to update user_matches:", updateError);
      return NextResponse.json(
        { error: "Failed to save feedback" },
        { status: 500 },
      );
    }
  }

  return NextResponse.json({ success: true });
}
