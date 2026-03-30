import { NextResponse } from "next/server";
import { Resend } from "resend";
import WeeklySummaryEmail from "@/emails/weekly-summary";
import type { EmailShipSummary } from "@/lib/types";

interface SendSummaryBody {
  to: string;
  ships: EmailShipSummary[];
  dateRange: string;
}

function isValidBody(body: unknown): body is SendSummaryBody {
  if (typeof body !== "object" || body === null) return false;
  const b = body as Record<string, unknown>;
  return (
    typeof b.to === "string" &&
    typeof b.dateRange === "string" &&
    Array.isArray(b.ships)
  );
}

export async function POST(request: Request) {
  // Auth check — GHA passes this header
  const apiKey = request.headers.get("x-api-key");
  const expectedKey = process.env.SUMMARY_API_KEY;

  if (!expectedKey || apiKey !== expectedKey) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const resendApiKey = process.env.RESEND_API_KEY;
  if (!resendApiKey) {
    return NextResponse.json(
      { error: "RESEND_API_KEY is not configured" },
      { status: 500 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!isValidBody(body)) {
    return NextResponse.json(
      { error: "Invalid request body. Required: to (string), ships (array), dateRange (string)" },
      { status: 400 },
    );
  }

  const resend = new Resend(resendApiKey);

  try {
    const { data, error } = await resend.emails.send({
      from: "MIHARIKUN <noreply@miharikun.com>",
      to: body.to,
      subject: `MIHARIKUN 週次サマリー — ${body.dateRange}`,
      react: WeeklySummaryEmail({
        dateRange: body.dateRange,
        ships: body.ships,
      }),
    });

    if (error) {
      console.error("Resend error:", error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ success: true, id: data?.id });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("Failed to send weekly summary email:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
