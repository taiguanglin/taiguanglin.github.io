  // ============================================================
  // 08-qa-audio.js — QA 答疑章節的逐段音檔播放（含底部浮動播放器）
  //
  // 僅 qa/ 資料夾轉出的章節含 .qa-play 按鈕（data-audio/-start/-end/-label）。
  // 點擊後從指定時間播放對應 .opus 音檔，到段落結束自動停止，並在畫面底部
  // 顯示一個浮動迷你播放器（音檔名稱 + 起訖時間 + 播放進度）。
  //
  // data-audio 為 percent-encoded 的相對路徑（../audio/<檔名>.opus），可避免
  // OpenCC 簡繁轉換破壞中文檔名；顯示時再以 decodeURIComponent 還原。
  //
  // 以具名 IIFE 隔離作用域（本檔被串接進共用的 DOMContentLoaded 函式中）。
  // ============================================================
  ;(function () {
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll('button.qa-play')
    );
    if (!buttons.length) return;

    var audio = new Audio();
    audio.preload = 'none';

    var segEnd = null;       // 目前段落的結束秒數（到此自動停止）
    var segStart = 0;        // 目前段落的起始秒數
    var activeButton = null; // 目前播放中的按鈕

    // ---- 底部浮動播放器 ------------------------------------------------
    var bar = document.createElement('div');
    bar.className = 'qa-player';
    bar.setAttribute('aria-hidden', 'true');
    bar.innerHTML =
      '<button class="qa-player-toggle" type="button" aria-label="播放/暫停">▶</button>' +
      '<div class="qa-player-info">' +
        '<div class="qa-player-file"></div>' +
        '<div class="qa-player-range"></div>' +
        '<div class="qa-player-progress"><span class="qa-player-progress-fill"></span></div>' +
      '</div>' +
      '<button class="qa-player-close" type="button" aria-label="關閉">✕</button>';
    document.body.appendChild(bar);

    var toggleBtn = bar.querySelector('.qa-player-toggle');
    var fileEl = bar.querySelector('.qa-player-file');
    var rangeEl = bar.querySelector('.qa-player-range');
    var fillEl = bar.querySelector('.qa-player-progress-fill');
    var closeBtn = bar.querySelector('.qa-player-close');

    function decodeName(url) {
      var base = (url || '').split('/').pop();
      try { base = decodeURIComponent(base); } catch (e) {}
      return base;
    }

    function absoluteUrl(url) {
      try { return new URL(url, window.location.href).href; } catch (e) { return url; }
    }

    function showBar() {
      bar.classList.add('visible');
      bar.setAttribute('aria-hidden', 'false');
    }

    function setPlayingUI(isPlaying) {
      toggleBtn.textContent = isPlaying ? '⏸' : '▶';
      buttons.forEach(function (b) { b.classList.remove('playing'); });
      if (activeButton && isPlaying) activeButton.classList.add('playing');
    }

    function stopPlayback() {
      audio.pause();
      setPlayingUI(false);
    }

    function playSegment(btn) {
      var url = btn.getAttribute('data-audio');
      if (!url) return;
      segStart = parseFloat(btn.getAttribute('data-start')) || 0;
      var end = parseFloat(btn.getAttribute('data-end'));
      segEnd = isNaN(end) ? null : end;
      activeButton = btn;

      fileEl.textContent = decodeName(url);
      rangeEl.textContent = btn.getAttribute('data-label') || '';
      fillEl.style.width = '0%';
      showBar();

      var seekAndPlay = function () {
        try { audio.currentTime = segStart; } catch (e) {}
        var p = audio.play();
        if (p && p.catch) p.catch(function () {});
      };

      if (absoluteUrl(url) !== audio.src) {
        audio.src = url;
        audio.addEventListener('loadedmetadata', seekAndPlay, { once: true });
        audio.load();
      } else if (audio.readyState >= 1) {
        seekAndPlay();
      } else {
        audio.addEventListener('loadedmetadata', seekAndPlay, { once: true });
        audio.load();
      }
    }

    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        // 點擊正在播放的同一段 → 暫停
        if (activeButton === btn && !audio.paused) {
          stopPlayback();
          return;
        }
        playSegment(btn);
      });
    });

    audio.addEventListener('timeupdate', function () {
      if (segEnd != null && audio.currentTime >= segEnd) {
        stopPlayback();
        fillEl.style.width = '100%';
        return;
      }
      if (segEnd != null && segEnd > segStart) {
        var pct = ((audio.currentTime - segStart) / (segEnd - segStart)) * 100;
        fillEl.style.width = Math.max(0, Math.min(100, pct)) + '%';
      }
    });

    audio.addEventListener('play', function () { setPlayingUI(true); });
    audio.addEventListener('pause', function () { setPlayingUI(false); });
    audio.addEventListener('ended', function () { stopPlayback(); });

    toggleBtn.addEventListener('click', function () {
      if (!activeButton) return;
      if (audio.paused) {
        // 若已播到段落結束，重頭播該段
        if (segEnd != null && audio.currentTime >= segEnd) {
          try { audio.currentTime = segStart; } catch (e) {}
        }
        var p = audio.play();
        if (p && p.catch) p.catch(function () {});
      } else {
        audio.pause();
      }
    });

    closeBtn.addEventListener('click', function () {
      stopPlayback();
      bar.classList.remove('visible');
      bar.setAttribute('aria-hidden', 'true');
    });
  })();

