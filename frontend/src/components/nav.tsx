"use client";

import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";
import { Anchor } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import type { User } from "@supabase/supabase-js";

interface NavLinkProps {
  href: string;
  pathname: string;
  children: React.ReactNode;
  onClick?: () => void;
}

function NavLink({ href, pathname, children, onClick }: NavLinkProps) {
  const isActive = pathname === href || pathname.startsWith(href + "/");
  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        "transition-colors",
        isActive
          ? "text-blue-600 dark:text-blue-400 font-semibold"
          : "hover:text-blue-600 dark:hover:text-blue-400",
      )}
    >
      {children}
    </Link>
  );
}

export function Nav() {
  const router = useRouter();
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [user, setUser] = useState<User | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

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
    <header className="sticky top-0 z-50 border-b border-zinc-200 dark:border-zinc-800 backdrop-blur-sm bg-white/80 dark:bg-zinc-950/80">
      <nav className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-bold">
          <Anchor className="h-5 w-5 text-blue-600" />
          <span>MIHARIKUN</span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden sm:flex items-center gap-4 text-sm">
          <NavLink href="/news" pathname={pathname}>
            ニュース
          </NavLink>

          {user ? (
            <>
              <NavLink href="/dashboard" pathname={pathname}>
                ダッシュボード
              </NavLink>
              <NavLink href="/fleet" pathname={pathname}>
                フリート
              </NavLink>
              <NavLink href="/ships/new" pathname={pathname}>
                船舶登録
              </NavLink>
              <NavLink href="/settings" pathname={pathname}>
                設定
              </NavLink>
              <button
                onClick={handleLogout}
                className="text-zinc-500 hover:text-red-600 transition-colors"
              >
                ログアウト
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="rounded-lg bg-blue-600 px-3 py-1 text-white hover:bg-blue-700 transition-colors"
            >
              ログイン
            </Link>
          )}
          {mounted && (
            <button
              onClick={() => {
                const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
                setTheme(next);
              }}
              className="text-zinc-500 hover:text-blue-600 text-xs font-mono transition-colors"
            >
              {theme === "light" ? "[LIGHT]" : theme === "dark" ? "[DARK]" : "[AUTO]"}
            </button>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="sm:hidden text-sm font-bold"
          onClick={() => setMenuOpen((prev) => !prev)}
        >
          {menuOpen ? "[X]" : "[MENU]"}
        </button>
      </nav>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="sm:hidden border-t border-zinc-200 dark:border-zinc-800 px-4 py-3 flex flex-col gap-3 text-sm">
          <NavLink href="/news" pathname={pathname} onClick={() => setMenuOpen(false)}>
            ニュース
          </NavLink>

          {user ? (
            <>
              <NavLink href="/dashboard" pathname={pathname} onClick={() => setMenuOpen(false)}>
                ダッシュボード
              </NavLink>
              <NavLink href="/fleet" pathname={pathname} onClick={() => setMenuOpen(false)}>
                フリート
              </NavLink>
              <NavLink href="/ships/new" pathname={pathname} onClick={() => setMenuOpen(false)}>
                船舶登録
              </NavLink>
              <NavLink href="/settings" pathname={pathname} onClick={() => setMenuOpen(false)}>
                設定
              </NavLink>
              <button
                onClick={() => {
                  setMenuOpen(false);
                  handleLogout();
                }}
                className="text-left text-zinc-500 hover:text-red-600 transition-colors"
              >
                ログアウト
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="rounded-lg bg-blue-600 px-3 py-1 text-white hover:bg-blue-700 text-center transition-colors"
              onClick={() => setMenuOpen(false)}
            >
              ログイン
            </Link>
          )}
          {mounted && (
            <button
              onClick={() => {
                const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
                setTheme(next);
              }}
              className="text-zinc-500 hover:text-blue-600 text-xs font-mono transition-colors"
            >
              {theme === "light" ? "[LIGHT]" : theme === "dark" ? "[DARK]" : "[AUTO]"}
            </button>
          )}
        </div>
      )}
    </header>
  );
}
