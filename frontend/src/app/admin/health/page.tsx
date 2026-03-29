import { createClient } from "@/lib/supabase/server";

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

export default async function AdminHealthPage() {
  const cards: HealthCard[] = [];

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

    // 3. pending_queue
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

    // 4. ユーザー数 & 船舶数
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

    // 5. マッチング結果
    const [
      { count: matchTotal, error: matchError },
      { count: matchApplicable },
      { count: matchNotApplicable },
      { count: matchPending },
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
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "不明なエラー";
    cards.push({
      label: "DB 接続",
      value: message,
      status: "err",
    });
  }

  return (
    <main className="min-h-screen bg-zinc-50 p-4 sm:p-8">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-bold text-zinc-900 mb-6">
          システムヘルスチェック
        </h1>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {cards.map((card) => (
            <Card key={card.label} card={card} />
          ))}
        </div>
        <p className="mt-6 text-xs text-zinc-400 text-center">
          {new Date().toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })} 時点
        </p>
      </div>
    </main>
  );
}
