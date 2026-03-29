// MIHARIKUN Service Worker — 船上低帯域対応のためオフラインキャッシュ
const CACHE_NAME = "miharikun-v1";

// アプリシェルの事前キャッシュ対象
const APP_SHELL = ["/", "/news", "/dashboard", "/login"];

// インストール時: アプリシェルを事前キャッシュ
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  // 待機中の SW を即座にアクティブ化
  self.skipWaiting();
});

// アクティベート時: 古いキャッシュを削除
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// フェッチ戦略の判定
function isSupabaseAPI(url) {
  return url.hostname.includes("supabase");
}

function isStaticAsset(url) {
  return /\.(js|css|woff2?|ttf|otf|png|jpg|svg|ico)(\?.*)?$/.test(
    url.pathname
  );
}

function isNavigationRequest(request) {
  return request.mode === "navigate";
}

// フェッチハンドラ
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Supabase API: ネットワークのみ（ユーザーデータをキャッシュしない）
  if (isSupabaseAPI(url)) {
    event.respondWith(fetch(event.request));
    return;
  }

  // 静的アセット: キャッシュファースト
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(event.request).then(
        (cached) =>
          cached ||
          fetch(event.request).then((response) => {
            // 正常なレスポンスのみキャッシュ
            if (response.ok) {
              const clone = response.clone();
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(event.request, clone);
              });
            }
            return response;
          })
      )
    );
    return;
  }

  // ナビゲーション: ネットワークファースト、失敗時はキャッシュ済み / にフォールバック
  if (isNavigationRequest(event.request)) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // 正常なレスポンスをキャッシュに保存
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        })
        .catch(() =>
          caches
            .match(event.request)
            .then((cached) => cached || caches.match("/"))
        )
    );
    return;
  }

  // その他: ネットワークファースト
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
