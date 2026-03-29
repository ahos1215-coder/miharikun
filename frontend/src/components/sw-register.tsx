"use client";

import { useEffect } from "react";

/**
 * Service Worker を登録するクライアントコンポーネント。
 * layout.tsx に配置して、アプリ起動時に SW を有効化する。
 */
export function SwRegister() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((err: unknown) => {
        console.warn("SW registration failed:", err);
      });
    }
  }, []);

  return null;
}
