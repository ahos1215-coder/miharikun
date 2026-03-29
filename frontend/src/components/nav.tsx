"use client";

import { createClient } from "@/lib/supabase/client";
import { Anchor } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { User } from "@supabase/supabase-js";

export function Nav() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setUser(data.user));

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <header className="border-b border-zinc-200 dark:border-zinc-800">
      <nav className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-bold">
          <Anchor className="h-5 w-5 text-blue-600" />
          <span>MIHARIKUN</span>
        </Link>

        <div className="flex items-center gap-4 text-sm">
          <Link href="/news" className="hover:text-blue-600">
            [NEWS] ニュース
          </Link>

          {user ? (
            <>
              <Link href="/dashboard" className="hover:text-blue-600">
                [DASH] ダッシュボード
              </Link>
              <Link href="/ships/new" className="hover:text-blue-600">
                [SHIP] 船舶登録
              </Link>
              <Link href="/settings" className="hover:text-blue-600">
                [SET] 設定
              </Link>
              <button
                onClick={handleLogout}
                className="text-zinc-500 hover:text-red-600"
              >
                ログアウト
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="rounded bg-blue-600 px-3 py-1 text-white hover:bg-blue-700"
            >
              ログイン
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
