import { BookOpen, Ship } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { Publication, PublicationCategory } from "@/lib/types";

const CATEGORY_TABS: { key: PublicationCategory | null; label: string }[] = [
  { key: null, label: "全て" },
  { key: "A", label: "A: 条約" },
  { key: "B", label: "B: 航海用" },
  { key: "C", label: "C: 旗国/船級" },
  { key: "D", label: "D: マニュアル" },
];

const catColors: Record<string, string> = {
  A: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  B: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  C: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  D: "text-amber-400 bg-amber-500/10 border-amber-500/20",
};

const catLabels: Record<string, string> = {
  A: "条約",
  B: "航海用",
  C: "旗国/船級",
  D: "マニュアル",
};

interface PublicationsShellProps {
  shipName: string;
  publications: Publication[];
  activeCategory: PublicationCategory | null;
  shipId: string;
  totalCount: number;
}

export function PublicationsShell({
  shipName,
  publications,
  activeCategory,
  shipId,
  totalCount,
}: PublicationsShellProps) {
  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="glass rounded-2xl p-5 motion-preset-slide-up motion-duration-500">
        <div className="flex items-center gap-3">
          <Ship size={20} className="text-cyan-400" />
          <div>
            <h1 className="text-lg font-bold text-white">{shipName}</h1>
            <p className="text-sm text-zinc-400">
              備付書籍管理 — 法定書籍 {totalCount} 冊
            </p>
          </div>
        </div>
      </div>

      {/* Category tabs */}
      <nav className="flex gap-1.5 overflow-x-auto pb-1">
        {CATEGORY_TABS.map((tab) => {
          const isActive = tab.key === activeCategory;
          const href = tab.key
            ? `/ships/${shipId}/publications?category=${tab.key}`
            : `/ships/${shipId}/publications`;
          return (
            <Link
              key={tab.key ?? "all"}
              href={href}
              className={cn(
                "whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-all",
                isActive
                  ? "bg-cyan-600 text-white shadow-lg shadow-cyan-600/20"
                  : "glass text-zinc-400 hover:text-zinc-200",
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>

      {/* Count */}
      <p className="text-xs text-zinc-500">{publications.length} 件表示</p>

      {/* Publication list */}
      {publications.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center">
          <BookOpen size={32} className="mx-auto mb-3 text-zinc-600" />
          <p className="text-sm text-zinc-500">該当する書籍はありません</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {publications.map((pub, i) => {
            const isSms = pub.legal_basis?.includes("SMS管理図書") ?? false;
            return (
              <div
                key={pub.id}
                className="glass rounded-xl p-4 motion-preset-slide-up motion-duration-300"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium",
                          catColors[pub.category] ?? "",
                        )}
                      >
                        {catLabels[pub.category] ?? pub.category}
                      </span>
                      {isSms && (
                        <span className="text-[10px] text-zinc-500 border border-zinc-700 rounded-full px-1.5 py-0.5">
                          SMS管理
                        </span>
                      )}
                      <span className="text-[10px] text-zinc-500">
                        {pub.publisher}
                      </span>
                    </div>
                    <h3 className="text-sm font-medium text-zinc-200 mb-0.5">
                      {pub.title_ja ?? pub.title}
                    </h3>
                    <p className="text-xs text-zinc-500">{pub.title}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-zinc-400">
                      {pub.current_edition ?? "—"}
                    </p>
                    {pub.current_edition_date && (
                      <p className="text-[10px] text-zinc-500 tabular-nums">
                        {pub.current_edition_date.slice(0, 7)}
                      </p>
                    )}
                  </div>
                </div>
                {pub.legal_basis && (
                  <p className="text-[10px] text-zinc-600 mt-1.5">
                    根拠: {pub.legal_basis}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
