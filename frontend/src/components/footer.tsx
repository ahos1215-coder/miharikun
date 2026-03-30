import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-zinc-200 px-4 py-8 text-center text-xs text-zinc-500 dark:border-zinc-800">
      <div className="mx-auto max-w-5xl space-y-3">
        <nav className="flex flex-wrap items-center justify-center gap-4">
          <Link
            href="#"
            className="hover:text-zinc-700 hover:underline dark:hover:text-zinc-300"
          >
            利用規約
          </Link>
          <Link
            href="#"
            className="hover:text-zinc-700 hover:underline dark:hover:text-zinc-300"
          >
            プライバシーポリシー
          </Link>
          <a
            href="mailto:support@miharikun.com"
            className="hover:text-zinc-700 hover:underline dark:hover:text-zinc-300"
          >
            お問い合わせ
          </a>
        </nav>

        <p>
          本サービスはAIによる参考情報の提供を目的としており、公式文書の代替ではありません。
          法令遵守の最終判断は、必ず原文を確認の上ご自身の責任で行ってください。
        </p>

        {/* v2.0 */}
        <p className="mt-1">&copy; 2026 MIHARIKUN</p>
      </div>
    </footer>
  );
}
