// ============================================================
// 13-player-persist.js — 音檔播放跨頁持續性
//
// 靜態站無法讓 <audio> 跨頁存活；改以「狀態快照 → 喚回播放」：
//   ① 播放中每 3 秒與離頁前，把 {src, 進度秒, 檔名, 頁面, 段落錨點}
//      快照到 sessionStorage('w2e:playerState')（08 播放器的狀態經
//      W2E.qaAudio 讀取）。
//   ② 任何頁面載入後若有 12 小時內的快照，左下角浮出續播膠囊
//      「▶ 檔名 12:34」：點「續播」——同頁優先交回 08 播放器
//      （找到原播放鈕重播再 seek），他頁則自建 Audio 從斷點續播；
//      「回到段落」跳回原文頁面錨點；✕ 丟棄快照。
// ============================================================

;(function () {
  var KEY = 'w2e:playerState';
  var FRESH_MS = 12 * 3600 * 1000;
  var SAVE_MS = 3000;

  function tt(sim, trad) {
    return (typeof isTraditionalChinesePage === 'function' && isTraditionalChinesePage()) ? trad : sim;
  }

  function read() {
    try { return JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) { return null; }
  }
  function write(state) {
    try {
      if (state) sessionStorage.setItem(KEY, JSON.stringify(state));
      else sessionStorage.removeItem(KEY);
    } catch (e) {}
  }
  function fmt(s) {
    s = Math.max(0, Math.floor(s || 0));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return (h ? p(h) + ':' : '') + p(m) + ':' + p(sec);
  }
  function absUrl(u) {
    try { return new URL(u, window.location.href).href; } catch (e) { return u; }
  }

  // ---- 快照：從 08 播放器讀狀態 ----------------------------------------
  function capture() {
    var qa = window.W2E && W2E.qaAudio;
    if (!qa || !qa.audio || !qa.audio.src) return;
    var a = qa.audio;
    if (isNaN(a.currentTime)) return;
    var btn = qa.getActiveButton && qa.getActiveButton();
    var file = '', range = '';
    var bar = document.querySelector('.qa-player.visible');
    if (bar) {
      var f = bar.querySelector('.qa-player-file');
      var r = bar.querySelector('.qa-player-range');
      if (f) file = f.textContent || '';
      if (r) range = r.textContent || '';
    }
    if (!file) file = decodeURIComponent(a.src.split('/').pop() || '');
    var anchor = null;
    if (btn) {
      var host = btn.closest('[id]');
      anchor = host ? host.id : null;
    }
    // 只記「有進度」的狀態；停在段落起點就不打擾
    if (a.currentTime < 2) return;
    write({
      src: a.src,
      t: Math.round(a.currentTime * 10) / 10,
      file: file,
      range: range,
      page: window.location.pathname,
      anchor: anchor,
      playing: !a.paused,
      ts: Date.now()
    });
  }

  setInterval(capture, SAVE_MS);
  window.addEventListener('pagehide', capture);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') capture();
  });

  // ---- 續播膠囊 ---------------------------------------------------------
  var state = read();
  if (!state || !state.src) return;
  if (Date.now() - (state.ts || 0) > FRESH_MS) { write(null); return; }
  // 同頁且播放器已可見（使用者正在操作 08 播放器）→ 不打擾
  if (state.page === window.location.pathname &&
      document.querySelector('.qa-player.visible')) return;

  var pill = document.createElement('div');
  pill.className = 'w2e-audio-resume';
  pill.innerHTML =
    '<button type="button" class="w2e-audio-resume-play">▶</button>' +
    '<div class="w2e-audio-resume-info">' +
      '<div class="w2e-audio-resume-file" title="' + state.file.replace(/"/g, '&quot;') + '"></div>' +
      '<div class="w2e-audio-resume-time">' + fmt(state.t) + '</div>' +
    '</div>' +
    (state.anchor && state.page !== window.location.pathname
      ? '<a class="w2e-audio-resume-back" href="' + state.page + '#' + state.anchor + '">' +
        tt('回到段落', '回到段落') + '</a>'
      : '') +
    '<button type="button" class="w2e-audio-resume-close" aria-label="' + tt('关闭', '關閉') + '">✕</button>';
  pill.querySelector('.w2e-audio-resume-file').textContent = state.file;
  document.body.appendChild(pill);
  requestAnimationFrame(function () { pill.classList.add('visible'); });

  var extraAudio = null;

  function setPlayingUI(playing) {
    pill.querySelector('.w2e-audio-resume-play').textContent = playing ? '⏸' : '▶';
    pill.classList.toggle('is-playing', playing);
  }

  function resumeSamePage() {
    // 在原文頁：找回 08 播放器的對應播放鈕，重播該段後 seek 到斷點
    var qa = W2E.qaAudio;
    var btns = Array.prototype.slice.call(document.querySelectorAll('button.qa-play'));
    var target = null;
    for (var i = 0; i < btns.length; i++) {
      if (absUrl(btns[i].getAttribute('data-audio')) === state.src) {
        var s = parseFloat(btns[i].getAttribute('data-start')) || 0;
        var en = parseFloat(btns[i].getAttribute('data-end'));
        if (state.t >= s && (isNaN(en) || state.t <= en + 1)) { target = btns[i]; break; }
        if (!target) target = btns[i];
      }
    }
    if (!target) return false;
    qa.play(target);
    setTimeout(function () { qa.seekAbs(state.t); }, 300);
    return true;
  }

  pill.querySelector('.w2e-audio-resume-play').addEventListener('click', function () {
    if (extraAudio) {
      if (extraAudio.paused) { extraAudio.play().catch(function () {}); }
      else { extraAudio.pause(); }
      return;
    }
    if (state.page === window.location.pathname && window.W2E && W2E.qaAudio) {
      if (resumeSamePage()) { pill.remove(); write(null); showToastIfAble(tt('已从断点续播', '已從斷點續播')); return; }
    }
    extraAudio = new Audio(state.src);
    extraAudio.currentTime = state.t;
    extraAudio.play().then(function () { setPlayingUI(true); })
      .catch(function () { setPlayingUI(false); });
    extraAudio.addEventListener('pause', function () { setPlayingUI(false); });
    extraAudio.addEventListener('playing', function () { setPlayingUI(true); });
    extraAudio.addEventListener('timeupdate', function () {
      var tEl = pill.querySelector('.w2e-audio-resume-time');
      if (tEl) tEl.textContent = fmt(extraAudio.currentTime);
    });
    extraAudio.addEventListener('error', function () {
      setPlayingUI(false);
      showToastIfAble(tt('音档加载失败', '音檔載入失敗'));
    });
  });

  pill.querySelector('.w2e-audio-resume-close').addEventListener('click', function () {
    if (extraAudio) { extraAudio.pause(); extraAudio = null; }
    write(null);
    pill.remove();
  });

  function showToastIfAble(msg) {
    if (typeof showToast === 'function') showToast(msg);
  }
})();
