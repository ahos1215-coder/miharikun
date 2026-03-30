// MIHARIKUN Service Worker v2 — 船上低帯域（VSAT）対応オフラインキャッシュ
// Workbox 不使用・バニラ JS で軽量化

const CACHE_SHELL = "miharikun-shell-v2";
const CACHE_API = "miharikun-api-v1";
const CACHE_STATIC = "miharikun-static-v1";

const CURRENT_CACHES = [CACHE_SHELL, CACHE_API, CACHE_STATIC];

// アプリシェル — install 時に事前キャッシュ
const APP_SHELL_URLS = [
  "/",
  "/news",
  "/dashboard",
  "/login",
  "/ships/new",
  "/settings",
  "/offline.html",
];

// API キャッシュ制限
const API_CACHE_MAX_ENTRIES = 100;
const API_CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

// ─── インストール ───────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_SHELL).then((cache) => cache.addAll(APP_SHELL_URLS))
  );
  self.skipWaiting();
});

// ─── アクティベート: 旧キャッシュ削除 + API キャッシュ TTL 整理 ──
self.addEventListener("activate", (event) => {
  event.waitUntil(
    Promise.all([
      // 古いバージョンのキャッシュを削除
      caches.keys().then((keys) =>
        Promise.all(
          keys
            .filter((key) => !CURRENT_CACHES.includes(key))
            .map((key) => caches.delete(key))
        )
      ),
      // API キャッシュの TTL 超過エントリを削除
      pruneApiCache(),
    ])
  );
  self.clients.claim();
});

// ─── ユーティリティ ─────────────────────────────────────

function isSupabaseAPI(url) {
  return url.hostname.includes("supabase");
}

function isStaticAsset(url) {
  return /\.(js|css|woff2?|ttf|otf|png|jpg|svg|ico|webp)(\?.*)?$/.test(
    url.pathname
  );
}

function isNavigationRequest(request) {
  return request.mode === "navigate";
}

/**
 * API キャッシュの古いエントリを削除（TTL + LRU 上限）
 */
async function pruneApiCache() {
  const cache = await caches.open(CACHE_API);
  const requests = await cache.keys();
  const now = Date.now();

  // メタデータヘッダで保存時刻を確認し、TTL 超過分を削除
  const entries = [];
  for (const req of requests) {
    const res = await cache.match(req);
    if (!res) continue;
    const savedAt = parseInt(res.headers.get("x-sw-cached-at") || "0", 10);
    if (now - savedAt > API_CACHE_TTL_MS) {
      await cache.delete(req);
    } else {
      entries.push({ req, savedAt });
    }
  }

  // LRU: 上限超過分は古い順に削除
  if (entries.length > API_CACHE_MAX_ENTRIES) {
    entries.sort((a, b) => a.savedAt - b.savedAt);
    const toRemove = entries.slice(0, entries.length - API_CACHE_MAX_ENTRIES);
    for (const { req } of toRemove) {
      await cache.delete(req);
    }
  }
}

/**
 * API レスポンスにタイムスタンプヘッダを付与してキャッシュ保存
 */
async function cacheApiResponse(request, response) {
  const cache = await caches.open(CACHE_API);
  const headers = new Headers(response.headers);
  headers.set("x-sw-cached-at", String(Date.now()));
  const tagged = new Response(await response.clone().blob(), {
    status: response.status,
    statusText: response.statusText,
    headers: headers,
  });
  await cache.put(request, tagged);
}

// ─── フェッチハンドラ ───────────────────────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // ── Supabase API: ネットワークファースト + キャッシュフォールバック ──
  if (isSupabaseAPI(url) && event.request.method === "GET") {
    event.respondWith(
      fetch(event.request)
        .then(async (response) => {
          if (response.ok) {
            await cacheApiResponse(event.request, response);
          }
          return response;
        })
        .catch(() =>
          caches.match(event.request).then((cached) => {
            if (cached) return cached;
            // API 失敗時は 503 を返す（UI 側でオフライン表示）
            return new Response(
              JSON.stringify({ error: "offline", message: "オフラインです" }),
              {
                status: 503,
                headers: { "Content-Type": "application/json" },
              }
            );
          })
        )
    );
    return;
  }

  // Supabase への POST/PATCH 等は素通し
  if (isSupabaseAPI(url)) {
    event.respondWith(fetch(event.request));
    return;
  }

  // ── 静的アセット: キャッシュファースト ──
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(event.request).then(
        (cached) =>
          cached ||
          fetch(event.request).then((response) => {
            if (response.ok) {
              const clone = response.clone();
              caches.open(CACHE_STATIC).then((cache) => {
                cache.put(event.request, clone);
              });
            }
            return response;
          })
      )
    );
    return;
  }

  // ── ナビゲーション: ネットワークファースト → キャッシュ → offline.html ──
  if (isNavigationRequest(event.request)) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_SHELL).then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        })
        .catch(() =>
          caches.match(event.request).then(
            (cached) =>
              cached ||
              caches.match("/").then(
                (root) => root || caches.match("/offline.html")
              )
          )
        )
    );
    return;
  }

  // ── その他: ネットワークファースト ──
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
