/* TaiGuangLin 電子書 service worker（PWA 離線支援）
 *
 * 策略：
 *  - 靜態資產（電子書 CSS/JS/WASM、字型、vendor、圖片）→ cache-first。
 *  - 電子書頁面（/wenda2_ebook/、/ebook/ 下的 .html）→ stale-while-revalidate，
 *    離線時可開啟所有「曾讀過」的章節。
 *  - 搜尋索引 search_index*.json → stale-while-revalidate（體積大但讀過一次即離線可用）。
 *  - 音檔（.opus/.mp3，/audio/ 另站）→ 網路直連，永不快取（避免佔滿儲存）。
 *  - 其他（根目錄行銷頁等）→ 直接放行，不介入。
 */
'use strict';

var VERSION = 'v1-2026-09';
var STATIC_CACHE = 'tgl-ebook-static-' + VERSION;
var PAGES_CACHE = 'tgl-ebook-pages-' + VERSION;

function isAsset(url) {
  if (url.origin !== location.origin) return false;
  var p = url.pathname;
  if (/^\/(wenda2_ebook\/assets|ebook\/assets|fonts|vendor)\//.test(p)) return true;
  if (/\.(css|js|woff2?|wasm|png|webp|ico|svg)$/.test(p)) return true;
  return false;
}

function isEbookHtml(url) {
  if (url.origin !== location.origin) return false;
  return /^\/(wenda2_ebook|ebook)\/.*\.html$/.test(url.pathname) ||
         /^\/(wenda2_ebook|ebook)\/?$/.test(url.pathname);
}

function isSearchIndex(url) {
  return url.origin === location.origin && /search_index[^/]*\.json$/.test(url.pathname);
}

function isAudio(url) {
  return /\.(opus|mp3|m4a|wav|ogg)$/.test(url.pathname) || url.pathname.indexOf('/audio/') === 0;
}

/* 每導覽一頁就把該頁 HTML 存進 PAGES_CACHE（每頁頂多一筆），離線時命中 */
function swr(request, cacheName) {
  return caches.open(cacheName).then(function (cache) {
    return cache.match(request, { ignoreSearch: true }).then(function (cached) {
      var fetched = fetch(request).then(function (resp) {
        if (resp.ok) {
          cache.put(request, resp.clone());
          /* 無 hash 的失敗頁也寫進去無妨；hash 不同視同新頁不處理 */
          if (request.url.indexOf('#') === -1) {
            cache.put(new Request(request.url.split('#')[0]), resp.clone());
          }
        }
        return resp;
      }).catch(function () { return cached; });
      return cached || fetched;
    });
  });
}

function cacheFirst(request) {
  return caches.match(request, { ignoreSearch: true }).then(function (cached) {
    if (cached) return cached;
    return fetch(request).then(function (resp) {
      if (resp.ok) {
        caches.open(STATIC_CACHE).then(function (cache) { cache.put(request, resp.clone()); });
      }
      return resp;
    });
  });
}

self.addEventListener('install', function () { self.skipWaiting(); });

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        if (k.indexOf('tgl-ebook-') === 0 && k.indexOf(VERSION) === -1) return caches.delete(k);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') return;
  var url = new URL(request.url);
  if (isAudio(url)) return;                      /* 音檔：網路直連 */
  if (isAsset(url)) { event.respondWith(cacheFirst(request)); return; }
  if (isEbookHtml(url) || isSearchIndex(url)) {
    event.respondWith(swr(request, isEbookHtml(url) ? PAGES_CACHE : STATIC_CACHE));
  }
  /* 其他請求不攔截 */
});
