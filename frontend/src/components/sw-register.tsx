"use client";

import { useEffect, useCallback, useState } from "react";

/**
 * Service Worker を登録し、オンライン復帰時に自動リフレッシュする。
 * 船上 VSAT 環境向け: オフライン→オンライン遷移を検知して通知バナーを表示。
 */
export function SwRegister() {
  const [showBanner, setShowBanner] = useState(false);

  const handleOnline = useCallback(() => {
    setShowBanner(true);
    // 3秒後にデータ更新のためリロード
    const timer = setTimeout(() => {
      setShowBanner(false);
      window.location.reload();
    }, 3000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    // SW 登録
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((err: unknown) => {
        console.warn("SW registration failed:", err);
      });
    }

    // オンライン復帰イベント
    window.addEventListener("online", handleOnline);
    return () => {
      window.removeEventListener("online", handleOnline);
    };
  }, [handleOnline]);

  if (!showBanner) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        bottom: "1rem",
        left: "50%",
        transform: "translateX(-50%)",
        background: "#2563eb",
        color: "#fff",
        padding: "0.75rem 1.5rem",
        borderRadius: "8px",
        fontSize: "0.875rem",
        zIndex: 9999,
        boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
        whiteSpace: "nowrap",
      }}
    >
      通信が回復しました。データを更新中...
    </div>
  );
}
