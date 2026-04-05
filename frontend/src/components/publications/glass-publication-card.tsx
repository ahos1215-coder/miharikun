"use client";

import { useState, useCallback } from "react";
import {
  BookOpen,
  ExternalLink,
  Check,
  X,
  Pencil,
  Scale,
  RefreshCcw,
  Building2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import type {
  Publication,
  ShipPublication,
  PublicationCategory,
  PublicationStatus,
} from "@/lib/types";

/* ──── style maps ──── */

const STATUS_CONFIG: Record<
  PublicationStatus,
  { label: string; className: string; glow: string }
> = {
  current: {
    label: "最新版",
    className: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/20",
    glow: "glow-cyan",
  },
  outdated: {
    label: "要更新",
    className: "bg-amber-500/15 text-amber-300 border border-amber-500/20",
    glow: "glow-amber",
  },
  missing: {
    label: "未所持",
    className: "bg-rose-500/15 text-rose-300 border border-rose-500/20",
    glow: "glow-rose",
  },
  unknown: {
    label: "未確認",
    className: "bg-zinc-500/15 text-zinc-300 border border-zinc-500/20",
    glow: "",
  },
  not_required: {
    label: "不要",
    className: "bg-zinc-500/10 text-zinc-500 border border-zinc-500/15",
    glow: "",
  },
};

const CATEGORY_CONFIG: Record<
  PublicationCategory,
  { label: string; full: string; className: string }
> = {
  A: {
    label: "A",
    full: "条約",
    className: "bg-cyan-500/15 text-cyan-300 border border-cyan-500/20",
  },
  B: {
    label: "B",
    full: "航海用",
    className: "bg-indigo-500/15 text-indigo-300 border border-indigo-500/20",
  },
  C: {
    label: "C",
    full: "旗国",
    className: "bg-purple-500/15 text-purple-300 border border-purple-500/20",
  },
  D: {
    label: "D",
    full: "マニュアル",
    className: "bg-amber-500/15 text-amber-300 border border-amber-500/20",
  },
};

/* ──── component ──── */

interface GlassPublicationCardProps {
  shipPublication: ShipPublication;
  publication: Publication;
  index: number;
}

export function GlassPublicationCard({
  shipPublication,
  publication,
  index,
}: GlassPublicationCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(shipPublication.owned_edition ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [currentOwnedEdition, setCurrentOwnedEdition] = useState(
    shipPublication.owned_edition,
  );

  const statusConfig = STATUS_CONFIG[shipPublication.status];
  const categoryConfig = CATEGORY_CONFIG[publication.category];

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      const res = await fetch("/api/publications", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: shipPublication.id,
          owned_edition: editValue || null,
        }),
      });

      if (!res.ok) {
        throw new Error("保存に失敗しました");
      }

      setCurrentOwnedEdition(editValue || null);
      setIsEditing(false);
      toast.success("手持ち版を更新しました");
    } catch {
      toast.error("保存に失敗しました。再度お試しください。");
    } finally {
      setIsSaving(false);
    }
  }, [editValue, shipPublication.id]);

  const handleCancel = useCallback(() => {
    setEditValue(currentOwnedEdition ?? "");
    setIsEditing(false);
  }, [currentOwnedEdition]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        void handleSave();
      } else if (e.key === "Escape") {
        handleCancel();
      }
    },
    [handleSave, handleCancel],
  );

  return (
    <div
      className={cn(
        "glass rounded-xl p-5 transition-all duration-300 glass-hover motion-preset-slide-up motion-duration-300",
        statusConfig.glow,
      )}
    >
      {/* Row 1: Badges */}
      <div className="flex flex-wrap items-center gap-1.5 mb-3">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
            categoryConfig.className,
          )}
        >
          {categoryConfig.label}: {categoryConfig.full}
        </span>
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
            statusConfig.className,
          )}
        >
          {shipPublication.status === "current" && "✅ "}
          {shipPublication.status === "outdated" && "⚠️ "}
          {shipPublication.status === "missing" && "❌ "}
          {statusConfig.label}
        </span>
        {shipPublication.priority === "mandatory" && (
          <Badge variant="critical">必須</Badge>
        )}
      </div>

      {/* Row 2: Title */}
      <h3 className="font-semibold text-sm text-zinc-100 leading-snug mb-0.5">
        {publication.title}
      </h3>
      {publication.title_ja && (
        <p className="text-xs text-zinc-400 mb-3">{publication.title_ja}</p>
      )}

      {/* Row 3: Metadata */}
      <div className="space-y-1.5 mb-4">
        {publication.legal_basis && (
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <Scale size={12} className="shrink-0 text-cyan-500/60" />
            <span>
              法的根拠: <span className="text-zinc-400">{publication.legal_basis}</span>
            </span>
          </div>
        )}
        {publication.current_edition && (
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <BookOpen size={12} className="shrink-0 text-cyan-500/60" />
            <span>
              最新版:{" "}
              <span className="text-zinc-400">
                {publication.current_edition}
                {publication.current_edition_date &&
                  ` (${publication.current_edition_date})`}
              </span>
            </span>
          </div>
        )}
        {publication.update_cycle && (
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <RefreshCcw size={12} className="shrink-0 text-cyan-500/60" />
            <span>
              更新サイクル:{" "}
              <span className="text-zinc-400">{publication.update_cycle}</span>
            </span>
          </div>
        )}
        {publication.publisher && (
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <Building2 size={12} className="shrink-0 text-cyan-500/60" />
            <span>
              発行元:{" "}
              <span className="text-zinc-400">{publication.publisher}</span>
            </span>
          </div>
        )}
      </div>

      {/* Row 4: Owned edition (inline edit) */}
      <div className="border-t border-white/5 pt-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500 shrink-0">手持ち版:</span>
          {isEditing ? (
            <div className="flex items-center gap-1.5 flex-1">
              <input
                type="text"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="例: 2024 Edition"
                disabled={isSaving}
                className={cn(
                  "flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5",
                  "text-xs text-zinc-200 placeholder:text-zinc-600",
                  "focus:outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20",
                  "transition-all duration-200",
                  isSaving && "opacity-50",
                )}
                autoFocus
              />
              <button
                onClick={() => void handleSave()}
                disabled={isSaving}
                className="p-1.5 rounded-lg bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 transition-colors disabled:opacity-50"
              >
                <Check size={12} />
              </button>
              <button
                onClick={handleCancel}
                disabled={isSaving}
                className="p-1.5 rounded-lg bg-zinc-500/15 text-zinc-400 hover:bg-zinc-500/25 transition-colors disabled:opacity-50"
              >
                <X size={12} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsEditing(true)}
              className="group flex items-center gap-1.5 text-xs text-zinc-300 hover:text-cyan-300 transition-colors"
            >
              <span>{currentOwnedEdition ?? "未登録"}</span>
              <Pencil
                size={10}
                className="opacity-0 group-hover:opacity-100 transition-opacity"
              />
            </button>
          )}
        </div>
      </div>

      {/* Row 5: Notes */}
      {shipPublication.notes && (
        <p className="text-[11px] text-zinc-500 mb-3 italic">
          {shipPublication.notes}
        </p>
      )}

      {/* Row 6: Purchase link */}
      {publication.purchase_url && (
        <a
          href={publication.purchase_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
        >
          <ExternalLink size={12} />
          購入リンク
        </a>
      )}
    </div>
  );
}
