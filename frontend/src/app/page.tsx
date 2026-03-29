import { Anchor } from "lucide-react";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <Anchor className="h-16 w-16 text-blue-600" />
      <h1 className="text-3xl font-bold tracking-tight">MIHARIKUN</h1>
      <p className="max-w-md text-center text-zinc-600">
        海事規制の自動収集・AI分類・パーソナライズ通知サービス
      </p>
    </div>
  );
}
