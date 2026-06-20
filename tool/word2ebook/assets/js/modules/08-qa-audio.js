  // ============================================================
  // 08-qa-audio.js — QA 答疑章節的逐段音檔播放（含底部浮動播放器）
  //
  // 僅 qa/ 資料夾轉出的章節含 .qa-play 按鈕（data-audio/-start/-end/-label）。
  // 點擊後從指定時間播放對應 .opus 音檔，到段落結束自動停止，並在畫面底部
  // 顯示一個浮動迷你播放器（音檔名稱 + 起訖時間 + 可拖拉進度條 + ±5s + 暫停）。
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

    var SKIP_SECONDS = 5;

    var audio = new Audio();
    audio.preload = 'none';

    var segEnd = null;       // 目前段落的結束秒數（到此自動停止）
    var segStart = 0;        // 目前段落的起始秒數
    var activeButton = null; // 目前播放中的按鈕
    var isDragging = false;  // 拖拉進度條中

    // ---- 底部浮動播放器 ------------------------------------------------
    var bar = document.createElement('div');
    bar.className = 'qa-player';
    bar.setAttribute('aria-hidden', 'true');
    bar.innerHTML =
      '<button class="qa-player-toggle" type="button" aria-label="播放/暫停">▶</button>' +
      '<div class="qa-player-info">' +
        '<div class="qa-player-file"></div>' +
        '<div class="qa-player-range"></div>' +
        '<div class="qa-player-seek-row">' +
          '<button class="qa-player-skip qa-player-skip--back" type="button" aria-label="後退 5 秒">−5s</button>' +
          '<div class="qa-player-progress" role="slider" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" tabindex="0">' +
            '<span class="qa-player-progress-fill"></span>' +
            '<span class="qa-player-progress-thumb"></span>' +
          '</div>' +
          '<button class="qa-player-skip qa-player-skip--fwd" type="button" aria-label="前進 5 秒">+5s</button>' +
        '</div>' +
      '</div>' +
      '<button class="qa-player-close" type="button" aria-label="關閉">✕</button>';
    document.body.appendChild(bar);

    var toggleBtn = bar.querySelector('.qa-player-toggle');
    var fileEl = bar.querySelector('.qa-player-file');
    var rangeEl = bar.querySelector('.qa-player-range');
    var progressEl = bar.querySelector('.qa-player-progress');
    var fillEl = bar.querySelector('.qa-player-progress-fill');
    var thumbEl = bar.querySelector('.qa-player-progress-thumb');
    var skipBackBtn = bar.querySelector('.qa-player-skip--back');
    var skipFwdBtn = bar.querySelector('.qa-player-skip--fwd');
    var closeBtn = bar.querySelector('.qa-player-close');

    function decodeName(url) {
      var base = (url || '').split('/').pop();
      try { base = decodeURIComponent(base); } catch (e) {}
      return base;
    }

    function absoluteUrl(url) {
      try { return new URL(url, window.location.href).href; } catch (e) { return url; }
    }

    function segmentEndLimit() {
      if (segEnd != null) return segEnd;
      return isFinite(audio.duration) ? audio.duration : segStart;
    }

    function clampToSegment(t) {
      return Math.max(segStart, Math.min(t, segmentEndLimit()));
    }

    function updateProgressUI(currentTime) {
      var end = segmentEndLimit();
      var span = end - segStart;
      var pct = 0;
      if (span > 0) {
        pct = ((currentTime - segStart) / span) * 100;
        pct = Math.max(0, Math.min(100, pct));
      }
      fillEl.style.width = pct + '%';
      thumbEl.style.left = pct + '%';
      progressEl.setAttribute('aria-valuenow', String(Math.round(pct)));
    }

    function showBar() {
      bar.classList.add('visible');
      bar.setAttribute('aria-hidden', 'false');
    }

    function setPlayingUI(isPlaying) {
      toggleBtn.textContent = isPlaying ? '⏸' : '▶';
      toggleBtn.setAttribute('aria-label', isPlaying ? '暫停' : '播放');
      buttons.forEach(function (b) { b.classList.remove('playing'); });
      if (activeButton && isPlaying) activeButton.classList.add('playing');
    }

    function stopPlayback() {
      audio.pause();
      setPlayingUI(false);
    }

    function seekTo(time, updateUi) {
      var t = clampToSegment(time);
      try { audio.currentTime = t; } catch (e) {}
      if (updateUi !== false) updateProgressUI(t);
      return t;
    }

    function seekFromClientX(clientX) {
      var rect = progressEl.getBoundingClientRect();
      if (!rect.width) return segStart;
      var ratio = (clientX - rect.left) / rect.width;
      ratio = Math.max(0, Math.min(1, ratio));
      var end = segmentEndLimit();
      return seekTo(segStart + ratio * (end - segStart));
    }

    function skipBy(delta) {
      if (!activeButton) return;
      seekTo(audio.currentTime + delta);
      if (audio.paused) {
        var p = audio.play();
        if (p && p.catch) p.catch(function () {});
      }
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
      updateProgressUI(segStart);
      showBar();

      var seekAndPlay = function () {
        seekTo(segStart);
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
      if (isDragging) return;
      if (segEnd != null && audio.currentTime >= segEnd) {
        stopPlayback();
        updateProgressUI(segEnd);
        return;
      }
      updateProgressUI(audio.currentTime);
    });

    audio.addEventListener('play', function () { setPlayingUI(true); });
    audio.addEventListener('pause', function () { setPlayingUI(false); });
    audio.addEventListener('ended', function () { stopPlayback(); });

    toggleBtn.addEventListener('click', function () {
      if (!activeButton) return;
      if (audio.paused) {
        // 若已播到段落結束，重頭播該段
        if (segEnd != null && audio.currentTime >= segEnd) {
          seekTo(segStart);
        }
        var p = audio.play();
        if (p && p.catch) p.catch(function () {});
      } else {
        audio.pause();
      }
    });

    skipBackBtn.addEventListener('click', function () { skipBy(-SKIP_SECONDS); });
    skipFwdBtn.addEventListener('click', function () { skipBy(SKIP_SECONDS); });

    progressEl.addEventListener('pointerdown', function (e) {
      if (!activeButton) return;
      isDragging = true;
      fillEl.style.transition = 'none';
      thumbEl.style.transition = 'none';
      progressEl.setPointerCapture(e.pointerId);
      seekFromClientX(e.clientX);
      e.preventDefault();
    });

    progressEl.addEventListener('pointermove', function (e) {
      if (!isDragging) return;
      seekFromClientX(e.clientX);
    });

    function endDrag(e) {
      if (!isDragging) return;
      isDragging = false;
      fillEl.style.transition = '';
      thumbEl.style.transition = '';
      if (e && progressEl.hasPointerCapture(e.pointerId)) {
        progressEl.releasePointerCapture(e.pointerId);
      }
    }

    progressEl.addEventListener('pointerup', endDrag);
    progressEl.addEventListener('pointercancel', endDrag);

    progressEl.addEventListener('keydown', function (e) {
      if (!activeButton) return;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        skipBy(-SKIP_SECONDS);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        skipBy(SKIP_SECONDS);
      } else if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        toggleBtn.click();
      }
    });

    closeBtn.addEventListener('click', function () {
      stopPlayback();
      bar.classList.remove('visible');
      bar.setAttribute('aria-hidden', 'true');
    });
  })();
