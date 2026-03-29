import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <h1 className="text-4xl font-bold">404</h1>
      <p className="text-zinc-500">ページが見つかりません</p>
      <Link href="/" className="text-blue-600 hover:underline">トップへ戻る</Link>
    </div>
  );
}
