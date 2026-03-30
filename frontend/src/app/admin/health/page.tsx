import { createClient } from "@/lib/supabase/server";

export const revalidate = 60;

type Status = "ok" | "warn" | "err";

interface HealthCard {
  label: string;
  value: string;
  status: Status;
}

function StatusBadge({ status }: { status: Status }) {
  switch (status) {
    case "ok":
      return <span className="text-green-600 font-bold">[OK]</span>;
    case "warn":
      return <span className="text-amber-600 font-bold">[WARN]</span>;
    case "err":
      return <span className="text-red-600 font-bold">[ERR]</span>;
  }
}

function Card({ card }: { card: HealthCard }) {
  const borderColor =
    card.status === "ok"
      ? "border-green-400"
      : card.status === "warn"
        ? "border-amber-400"
        : "border-red-400";

  return (
    <div
      className={`rounded-lg border-2 ${borderColor} bg-white p-4 shadow-sm`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-zinc-600">{card.label}</h3>
        <StatusBadge status={card.status} />
      </div>
      <p className="text-2xl font-bold text-zinc-900">{card.value}</p>
    </div>
  );
}

function getWorstStatus(cards: HealthCard[]): Status {
  if (cards.some((c) => c.status === "err")) return "err";
  if (cards.some((c) => c.status === "warn")) return "warn";
  return "ok";
}

function OverallBanner({ worst }: { worst: Status }) {
  switch (worst) {
    case "ok":
      return (
        <div className="rounded-lg border-2 border-green-400 bg-green-50 p-4 mb-6 text-center">
          <span className="text-green-700 font-bold text-lg">
            [OK] システム正常
          </span>
        </div>
      );
    case "warn":
      return (
        <div className="rounded-lg border-2 border-amber-400 bg-amber-50 p-4 mb-6 text-center">
          <span className="text-amber-700 font-bold text-lg">
            [WARN] 注意が必要です
          </span>
        </div>
      );
    case "err":
      return (
        <div className="rounded-lg border-2 border-red-400 bg-red-50 p-4 mb-6 text-center">
          <span className="text-red-700 font-bold text-lg">
            [ERR] エラーがあります
          </span>
        </div>
      );
  }
}

export default async function AdminHealthPage() {
  const cards: HealthCard[] = [];
  const now = new Date().toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" });

  try {
    const supabase = await createClient();

    // 1. DB 接続 + 規制データ数
    const [
      { count: totalRegulations, error: regError },
      { count: nkCount },
      { count: mlitCount },
    ] = await Promise.all([
      supabase
        .from("regulations")
        .select("*", { count: "exact", head: true }),
      supabase
        .from("regulations")
        .select("*", { count: "exact", head: true })
        .eq("source", "NK"),
      supabase
        .from("regulations")
        .select("*", { count: "exact", head: true })
        .eq("source", "MLIT"),
    ]);

    if (regError) {
      cards.push({
        label: "DB 接続",
        value: regError.message,
        status: "err",
      });
    } else {
      cards.push({
        label: "DB 接続",
        value: "接続OK",
        status: "ok",
      });
    }

    cards.push({
      label: "規制データ数",
      value: regError
        ? "取得失敗"
        : `合計: ${totalRegulations ?? 0} / NK: ${nkCount ?? 0} / MLIT: ${mlitCount ?? 0}`,
      status: regError ? "err" : (totalRegulations ?? 0) > 0 ? "ok" : "warn",
    });

    // 2. 最終更新
    const { data: latestReg, error: latestError } = await supabase
      .from("regulations")
      .select("created_at")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (latestError || !latestReg) {
      cards.push({
        label: "最終更新",
        value: latestError ? "取得失敗" : "データなし",
        status: latestError ? "err" : "warn",
      });
    } else {
      const lastUpdate = new Date(latestReg.created_at);
      const hoursAgo = (Date.now() - lastUpdate.getTime()) / (1000 * 60 * 60);
      cards.push({
        label: "最終更新",
        value: lastUpdate.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" }),
        status: hoursAgo > 24 ? "warn" : "ok",
      });
    }

    // 3. 最終クロール (mlit_crawl_state)
    const { data: latestCrawl, error: crawlError } = await supabase
      .from("mlit_crawl_state")
      .select("*")
      .order("updated_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (crawlError) {
      cards.push({
        label: "最終 MLIT クロール",
        value: "取得失敗",
        status: "err",
      });
    } else if (!latestCrawl) {
      cards.push({
        label: "最終 MLIT クロール",
        value: "データなし",
        status: "warn",
      });
    } else {
      const crawlTime = new Date(latestCrawl.updated_at as string);
      const hoursAgo = (Date.now() - crawlTime.getTime()) / (1000 * 60 * 60);
      cards.push({
        label: "最終 MLIT クロール",
        value: crawlTime.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" }),
        status: hoursAgo > 48 ? "warn" : "ok",
      });
    }

    // 4. pending_queue
    const { count: pendingCount, error: pendingError } = await supabase
      .from("pending_queue")
      .select("*", { count: "exact", head: true });

    if (pendingError) {
      cards.push({
        label: "pending_queue",
        value: "取得失敗",
        status: "err",
      });
    } else {
      const count = pendingCount ?? 0;
      cards.push({
        label: "pending_queue",
        value: `${count} 件`,
        status: count > 10 ? "warn" : "ok",
      });
    }

    // 5. ユーザー数 & 船舶数
    const [{ data: profileData, error: profileError }] = await Promise.all([
      supabase.from("ship_profiles").select("user_id"),
    ]);

    if (profileError) {
      cards.push({
        label: "ユーザー数",
        value: "取得失敗",
        status: "err",
      });
      cards.push({
        label: "船舶数",
        value: "取得失敗",
        status: "err",
      });
    } else {
      const profiles = profileData ?? [];
      const uniqueUsers = new Set(profiles.map((p) => p.user_id)).size;
      cards.push({
        label: "ユーザー数",
        value: `${uniqueUsers} 人`,
        status: uniqueUsers > 0 ? "ok" : "warn",
      });
      cards.push({
        label: "船舶数",
        value: `${profiles.length} 隻`,
        status: profiles.length > 0 ? "ok" : "warn",
      });
    }

    // 6. マッチング結果
    const [
      { count: matchTotal, error: matchError },
      { count: matchApplicable },
      { count: matchNotApplicable },
      { count: matchPending },
      { count: matchFailedCount, error: matchFailedError },
    ] = await Promise.all([
      supabase
        .from("user_matches")
        .select("*", { count: "exact", head: true }),
      supabase
        .from("user_matches")
        .select("*", { count: "exact", head: true })
        .eq("is_applicable", true),
      supabase
        .from("user_matches")
        .select("*", { count: "exact", head: true })
        .eq("is_applicable", false),
      supabase
        .from("user_matches")
        .select("*", { count: "exact", head: true })
        .is("is_applicable", null),
      supabase
        .from("user_matches")
        .select("*", { count: "exact", head: true })
        .eq("confidence", 0),
    ]);

    if (matchError) {
      cards.push({
        label: "マッチング結果",
        value: "取得失敗",
        status: "err",
      });
    } else {
      cards.push({
        label: "マッチング結果",
        value: `合計: ${matchTotal ?? 0} / 該当: ${matchApplicable ?? 0} / 非該当: ${matchNotApplicable ?? 0} / 判定中: ${matchPending ?? 0}`,
        status: (matchTotal ?? 0) > 0 ? "ok" : "warn",
      });
    }

    // 7. マッチング品質 (confidence=0 の件数 + 平均 confidence)
    const failedMatches = matchFailedError ? null : (matchFailedCount ?? 0);

    // 平均 confidence を取得
    const { data: confidenceData, error: confidenceError } = await supabase
      .from("user_matches")
      .select("confidence");

    let avgConfidence: number | null = null;
    if (!confidenceError && confidenceData && confidenceData.length > 0) {
      const sum = confidenceData.reduce(
        (acc, row) => acc + (row.confidence as number),
        0,
      );
      avgConfidence = sum / confidenceData.length;
    }

    if (failedMatches !== null) {
      cards.push({
        label: "マッチング品質",
        value:
          `失敗(confidence=0): ${failedMatches} 件` +
          (avgConfidence !== null
            ? ` / 平均信頼度: ${(avgConfidence * 100).toFixed(1)}%`
            : ""),
        status: failedMatches > 5 ? "warn" : "ok",
      });
    }
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "不明なエラー";
    cards.push({
      label: "DB 接続",
      value: message,
      status: "err",
    });
  }

  const worst = getWorstStatus(cards);

  return (
    <main className="min-h-screen bg-zinc-50 p-4 sm:p-8">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold text-zinc-900">
            システムヘルスチェック
          </h1>
          <a
            href="/admin/health"
            className="rounded bg-zinc-200 px-3 py-1 text-sm font-semibold text-zinc-700 hover:bg-zinc-300 transition-colors"
          >
            [REFRESH] 再確認
          </a>
        </div>

        <p className="text-xs text-zinc-500 mb-4">
          最終確認: {now}
        </p>

        <OverallBanner worst={worst} />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {cards.map((card) => (
            <Card key={card.label} card={card} />
          ))}
        </div>
        <p className="mt-6 text-xs text-zinc-400 text-center">
          自動更新間隔: 60秒 | {now} 時点
        </p>
      </div>
    </main>
  );
}
