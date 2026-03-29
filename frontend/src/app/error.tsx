"use client";

export default function Error({ reset }: { reset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <h1 className="text-2xl font-bold">エラーが発生しました</h1>
      <p className="text-zinc-500">しばらくしてから再度お試しください</p>
      <button onClick={reset} className="text-blue-600 hover:underline">再試行</button>
    </div>
  );
}
