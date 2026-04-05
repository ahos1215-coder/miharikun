"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Search, Ship, FileText, Settings, BarChart3, Home, Command, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandItem {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  action: () => void;
  keywords: string[];
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const items: CommandItem[] = [
    {
      id: "dashboard",
      label: "ダッシュボード",
      description: "マッチング結果一覧",
      icon: <BarChart3 size={16} />,
      action: () => router.push("/dashboard"),
      keywords: ["dashboard", "ダッシュボード", "マッチング"],
    },
    {
      id: "news",
      label: "規制ニュース",
      description: "最新の海事規制情報",
      icon: <FileText size={16} />,
      action: () => router.push("/news"),
      keywords: ["news", "ニュース", "規制", "regulation"],
    },
    {
      id: "ships",
      label: "船舶登録",
      description: "新しい船舶を登録",
      icon: <Ship size={16} />,
      action: () => router.push("/ships/new"),
      keywords: ["ship", "船舶", "登録", "register"],
    },
    {
      id: "fleet",
      label: "Fleet管理",
      description: "全船一覧・コンプライアンス",
      icon: <Ship size={16} />,
      action: () => router.push("/fleet"),
      keywords: ["fleet", "フリート", "一覧"],
    },
    {
      id: "settings",
      label: "通知設定",
      description: "LINE・メール通知の設定",
      icon: <Settings size={16} />,
      action: () => router.push("/settings"),
      keywords: ["settings", "設定", "通知", "LINE", "メール"],
    },
    {
      id: "publications",
      label: "備付書籍管理",
      description: "船内備付書籍の版数管理",
      icon: <BookOpen size={16} />,
      action: () => router.push("/dashboard"),
      keywords: ["publications", "書籍", "備付", "海図", "水路誌", "条約集"],
    },
    {
      id: "home",
      label: "ホーム",
      description: "トップページに戻る",
      icon: <Home size={16} />,
      action: () => router.push("/"),
      keywords: ["home", "ホーム", "トップ"],
    },
    {
      id: "solas",
      label: "SOLAS / 安全",
      description: "SOLAS関連の規制をフィルタ",
      icon: <FileText size={16} />,
      action: () => router.push("/dashboard?tab=solas"),
      keywords: ["SOLAS", "安全", "救命", "消防"],
    },
    {
      id: "marpol",
      label: "MARPOL / 環境",
      description: "MARPOL関連の規制をフィルタ",
      icon: <FileText size={16} />,
      action: () => router.push("/dashboard?tab=marpol"),
      keywords: ["MARPOL", "環境", "排出", "CII", "EEDI"],
    },
    {
      id: "stcw",
      label: "STCW / 船員",
      description: "STCW関連の規制をフィルタ",
      icon: <FileText size={16} />,
      action: () => router.push("/dashboard?tab=stcw"),
      keywords: ["STCW", "船員", "MLC", "資格"],
    },
  ];

  const filtered = query
    ? items.filter(
        (item) =>
          item.label.toLowerCase().includes(query.toLowerCase()) ||
          item.description.toLowerCase().includes(query.toLowerCase()) ||
          item.keywords.some((kw) => kw.toLowerCase().includes(query.toLowerCase())),
      )
    : items;

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
        setQuery("");
        setSelectedIndex(0);
      }
      if (!open) return;

      if (e.key === "Escape") {
        setOpen(false);
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % filtered.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filtered.length) % filtered.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filtered[selectedIndex]) {
          filtered[selectedIndex].action();
          setOpen(false);
        }
      }
    },
    [open, filtered, selectedIndex],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  return (
    <>
      {/* Trigger hint */}
      <button
        onClick={() => { setOpen(true); setQuery(""); setSelectedIndex(0); }}
        className="hidden md:inline-flex items-center gap-2 rounded-lg glass px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-300 transition-colors"
      >
        <Search size={13} />
        <span>検索</span>
        <kbd className="ml-1 inline-flex items-center gap-0.5 rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] font-mono text-zinc-500">
          <Command size={10} />K
        </kbd>
      </button>

      {/* Modal */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm motion-preset-fade motion-duration-150"
            onClick={() => setOpen(false)}
          />

          {/* Palette */}
          <div
            className="fixed left-1/2 top-[20%] z-50 w-[90vw] max-w-lg -translate-x-1/2 rounded-2xl border border-white/10 bg-navy-light/95 shadow-2xl backdrop-blur-xl motion-preset-slide-down motion-duration-200"
          >
              {/* Search input */}
              <div className="flex items-center gap-3 border-b border-white/5 px-4 py-3">
                <Search size={18} className="text-zinc-500 shrink-0" />
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="ページ・条約名で検索..."
                  className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-500 outline-none"
                />
                <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-zinc-500">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div className="max-h-[300px] overflow-y-auto p-2">
                {filtered.length === 0 ? (
                  <p className="px-3 py-6 text-center text-sm text-zinc-500">
                    該当するコマンドがありません
                  </p>
                ) : (
                  filtered.map((item, i) => (
                    <button
                      key={item.id}
                      onClick={() => { item.action(); setOpen(false); }}
                      onMouseEnter={() => setSelectedIndex(i)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors",
                        i === selectedIndex
                          ? "bg-white/8 text-cyan-300"
                          : "text-zinc-400 hover:bg-white/5",
                      )}
                    >
                      <span className={cn(
                        "shrink-0",
                        i === selectedIndex ? "text-cyan-400" : "text-zinc-500",
                      )}>
                        {item.icon}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{item.label}</p>
                        <p className="text-xs text-zinc-500 truncate">{item.description}</p>
                      </div>
                    </button>
                  ))
                )}
              </div>

              {/* Footer */}
              <div className="border-t border-white/5 px-4 py-2 flex items-center gap-4 text-[10px] text-zinc-600">
                <span>↑↓ 移動</span>
                <span>↵ 決定</span>
                <span>ESC 閉じる</span>
              </div>
            </div>
          </>
        )}
    </>
  );
}
