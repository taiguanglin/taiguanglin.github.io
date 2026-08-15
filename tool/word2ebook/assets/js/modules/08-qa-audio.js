  // ============================================================
  // 08-qa-audio.js — QA 答疑章節的逐段音檔播放（含底部浮動播放器）
  //
  // 僅 qa/ 資料夾轉出的章節含 .qa-play 按鈕（data-audio/-start/-end/-label）。
  // 點擊後從指定時間播放對應 .opus 音檔，到段落結束自動停止，並在畫面底部
  // 顯示一個浮動迷你播放器（音檔名稱 + 起訖時間 + 可拖拉進度條 + ±5s + 暫停 +
  // 音量控制：b站風格，列上只有一個喇叭鈕，點擊後彈出垂直音量滑桿，
  // 音量值存於 localStorage 以便跨頁保留）。
  //
  // 首次載入（或跳到尚未緩衝的時間點）時，播放鈕與迷你播放器會顯示載入中
  // 狀態與緩衝進度，避免使用者以為沒反應。
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
    var LOADING_DELAY_MS = 120; // 避免已快取音檔時載入 UI 閃爍
    var VOLUME_STORAGE_KEY = 'qa-volume';

    var audio = new Audio();
    audio.preload = 'none';

    var segEnd = null;       // 目前段落的結束秒數（到此自動停止）
    var segStart = 0;        // 目前段落的起始秒數
    var activeButton = null; // 目前播放中的按鈕
    var isDragging = false;  // 拖拉進度條中
    var isLoading = false;   // 正在等待音檔可播放
    var loadGen = 0;         // 載入世代，用於取消過期回呼
    var loadingDelayTimer = null;
    var savedRangeLabel = '';

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
      '<div class="qa-player-volume-group">' +
        '<button class="qa-player-volume-btn" type="button" aria-label="音量" aria-expanded="false">🔊</button>' +
        '<div class="qa-player-volume-popup" role="group" aria-label="音量">' +
          '<input class="qa-player-volume" type="range" min="0" max="1" step="0.05" value="1" aria-label="音量">' +
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
    var volumeGroup = bar.querySelector('.qa-player-volume-group');
    var volumeBtn = bar.querySelector('.qa-player-volume-btn');
    var volumeInput = bar.querySelector('.qa-player-volume');
    var closeBtn = bar.querySelector('.qa-player-close');

    function isTrad() {
      return typeof isTraditionalChinesePage === 'function' && isTraditionalChinesePage();
    }

    function qaText(key, fallback, params) {
      if (typeof getI18nText === 'function') {
        return getI18nText(key, isTrad(), fallback, params || {});
      }
      return fallback;
    }

    function decodeName(url) {
      var base = (url || '').split('/').pop();
      try { base = decodeURIComponent(base); } catch (e) {}
      return base;
    }

    function absoluteUrl(url) {
      try { return new URL(url, window.location.href).href; } catch (e) { return url; }
    }

    // ---- 音量控制（b站風格：喇叭鈕點擊後彈出垂直音量滑桿） --------------
    function clampVolume(v) {
      if (!isFinite(v)) return 1;
      return Math.max(0, Math.min(1, v));
    }

    function loadSavedVolume() {
      try {
        var saved = localStorage.getItem(VOLUME_STORAGE_KEY);
        if (saved == null) return 1;
        return clampVolume(parseFloat(saved));
      } catch (e) {
        return 1;
      }
    }

    function saveVolume(v) {
      try { localStorage.setItem(VOLUME_STORAGE_KEY, String(v)); } catch (e) {}
    }

    function updateVolumeUI() {
      var muted = audio.muted || audio.volume === 0;
      volumeBtn.textContent = muted ? '🔇' : '🔊';
    }

    function setVolumeOpen(open) {
      volumeGroup.classList.toggle('is-open', open);
      volumeBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    // 初始化音量（預設 1，若有上次儲存值則還原）
    audio.volume = loadSavedVolume();
    volumeInput.value = String(audio.volume);
    volumeInput.setAttribute('aria-label', qaText('qaAudio.volume', '音量'));
    updateVolumeUI();

    function segmentEndLimit() {
      if (segEnd != null) return segEnd;
      return isFinite(audio.duration) ? audio.duration : segStart;
    }

    function clampToSegment(t) {
      return Math.max(segStart, Math.min(t, segmentEndLimit()));
    }

    function updateProgressUI(currentTime) {
      if (isLoading) return;
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

    function getBufferPercent() {
      try {
        if (!audio.buffered || audio.buffered.length === 0) return 0;
        var i;
        for (i = 0; i < audio.buffered.length; i++) {
          if (audio.buffered.start(i) <= segStart && audio.buffered.end(i) >= segStart) {
            return 100;
          }
        }
        var farthest = 0;
        var covered = 0;
        for (i = 0; i < audio.buffered.length; i++) {
          farthest = Math.max(farthest, audio.buffered.end(i));
          covered += audio.buffered.end(i) - audio.buffered.start(i);
        }
        if (audio.duration && isFinite(audio.duration) && audio.duration > 0) {
          return Math.min(99, Math.round((covered / audio.duration) * 100));
        }
        if (segStart > 0) {
          return Math.min(99, Math.round((farthest / segStart) * 100));
        }
        return farthest > 0 ? 50 : 0;
      } catch (e) {
        return -1;
      }
    }

    function setPlayIconLoading(btn, loading) {
      if (!btn) return;
      var icon = btn.querySelector('.qa-play-icon');
      if (!icon) return;
      if (loading) {
        if (!icon.getAttribute('data-play-icon-html')) {
          icon.setAttribute('data-play-icon-html', icon.innerHTML);
        }
        icon.innerHTML = '';
        icon.classList.add('qa-play-icon--spinner');
      } else {
        icon.classList.remove('qa-play-icon--spinner');
        var saved = icon.getAttribute('data-play-icon-html');
        if (saved != null) {
          icon.innerHTML = saved;
          icon.removeAttribute('data-play-icon-html');
        }
        btn.style.removeProperty('--qa-load-pct');
      }
    }

    function applyLoadingVisual(pct) {
      bar.classList.add('is-loading');
      var known = pct > 0;
      progressEl.classList.toggle('is-indeterminate', !known);
      if (known) {
        fillEl.style.width = pct + '%';
        thumbEl.style.left = pct + '%';
        progressEl.setAttribute('aria-valuenow', String(pct));
        rangeEl.textContent = qaText(
          'qaAudio.loadingProgress',
          '正在載入音檔… ' + pct + '%',
          { pct: pct }
        );
        if (activeButton) {
          activeButton.style.setProperty('--qa-load-pct', pct + '%');
        }
      } else {
        rangeEl.textContent = qaText('qaAudio.loading', '正在載入音檔…');
        if (activeButton) {
          activeButton.style.setProperty('--qa-load-pct', '0%');
        }
      }
      toggleBtn.classList.add('is-loading');
      toggleBtn.setAttribute('aria-label', qaText('qaAudio.loading', '正在載入音檔…'));
      toggleBtn.setAttribute('aria-busy', 'true');
      if (activeButton) {
        activeButton.classList.add('loading');
        activeButton.setAttribute('aria-busy', 'true');
        setPlayIconLoading(activeButton, true);
      }
    }

    function clearLoadingVisual() {
      bar.classList.remove('is-loading');
      progressEl.classList.remove('is-indeterminate');
      toggleBtn.classList.remove('is-loading');
      toggleBtn.removeAttribute('aria-busy');
      buttons.forEach(function (b) {
        b.classList.remove('loading');
        b.removeAttribute('aria-busy');
        setPlayIconLoading(b, false);
      });
      if (savedRangeLabel) {
        rangeEl.textContent = savedRangeLabel;
      }
    }

    function updateLoadProgress() {
      if (!isLoading) return;
      var pct = getBufferPercent();
      applyLoadingVisual(pct);
    }

    function beginLoading() {
      if (loadingDelayTimer) {
        clearTimeout(loadingDelayTimer);
        loadingDelayTimer = null;
      }
      isLoading = true;
      // 短延遲後再顯示，避免本機快取命中時閃一下
      loadingDelayTimer = setTimeout(function () {
        loadingDelayTimer = null;
        if (!isLoading) return;
        updateLoadProgress();
      }, LOADING_DELAY_MS);
    }

    function endLoading() {
      if (loadingDelayTimer) {
        clearTimeout(loadingDelayTimer);
        loadingDelayTimer = null;
      }
      if (!isLoading && !bar.classList.contains('is-loading')) return;
      isLoading = false;
      clearLoadingVisual();
      updateProgressUI(audio.currentTime || segStart);
    }

    function setPlayingUI(isPlaying) {
      if (!toggleBtn.classList.contains('is-loading')) {
        toggleBtn.textContent = isPlaying ? '⏸' : '▶';
        toggleBtn.setAttribute('aria-label', isPlaying ? '暫停' : '播放');
      }
      buttons.forEach(function (b) { b.classList.remove('playing'); });
      if (activeButton && isPlaying) activeButton.classList.add('playing');
    }

    function stopPlayback() {
      audio.pause();
      endLoading();
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
      if (!activeButton || isLoading) return;
      seekTo(audio.currentTime + delta);
      if (audio.paused) {
        var p = audio.play();
        if (p && p.catch) p.catch(function () {});
      }
    }

    function playSegment(btn) {
      var url = btn.getAttribute('data-audio');
      if (!url) return;
      var myGen = ++loadGen;
      segStart = parseFloat(btn.getAttribute('data-start')) || 0;
      var end = parseFloat(btn.getAttribute('data-end'));
      segEnd = isNaN(end) ? null : end;
      activeButton = btn;

      savedRangeLabel = btn.getAttribute('data-label') || '';
      fileEl.textContent = decodeName(url);
      rangeEl.textContent = savedRangeLabel;
      updateProgressUI(segStart);
      showBar();
      beginLoading();

      var seekAndPlay = function () {
        if (myGen !== loadGen) return;
        seekTo(segStart);
        var p = audio.play();
        if (p && p.catch) {
          p.catch(function () {
            if (myGen === loadGen) endLoading();
          });
        }
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
        // 點擊正在載入的同一段 → 取消載入
        if (activeButton === btn && isLoading) {
          loadGen += 1;
          stopPlayback();
          return;
        }
        playSegment(btn);
      });
    });

    audio.addEventListener('timeupdate', function () {
      if (isDragging || isLoading) return;
      if (segEnd != null && audio.currentTime >= segEnd) {
        stopPlayback();
        updateProgressUI(segEnd);
        return;
      }
      updateProgressUI(audio.currentTime);
    });

    audio.addEventListener('progress', function () {
      if (isLoading) updateLoadProgress();
    });

    audio.addEventListener('waiting', function () {
      if (!activeButton || audio.paused) return;
      beginLoading();
      updateLoadProgress();
    });

    audio.addEventListener('playing', function () {
      endLoading();
      setPlayingUI(true);
    });

    audio.addEventListener('play', function () { setPlayingUI(true); });
    audio.addEventListener('pause', function () {
      if (!isLoading) setPlayingUI(false);
    });
    audio.addEventListener('ended', function () { stopPlayback(); });
    audio.addEventListener('error', function () {
      endLoading();
      rangeEl.textContent = qaText('qaAudio.loadError', '音檔載入失敗');
      setPlayingUI(false);
    });

    toggleBtn.addEventListener('click', function () {
      if (!activeButton || isLoading) return;
      if (audio.paused) {
        // 若已播到段落結束，重頭播該段
        if (segEnd != null && audio.currentTime >= segEnd) {
          seekTo(segStart);
        }
        beginLoading();
        var p = audio.play();
        if (p && p.catch) p.catch(function () { endLoading(); });
      } else {
        audio.pause();
      }
    });

    skipBackBtn.addEventListener('click', function () { skipBy(-SKIP_SECONDS); });
    skipFwdBtn.addEventListener('click', function () { skipBy(SKIP_SECONDS); });

    volumeBtn.addEventListener('click', function () {
      setVolumeOpen(!volumeGroup.classList.contains('is-open'));
    });

    // 點擊控制區外或按 Esc 時關閉音量彈出層
    document.addEventListener('pointerdown', function (e) {
      if (!volumeGroup.classList.contains('is-open')) return;
      if (!volumeGroup.contains(e.target)) {
        setVolumeOpen(false);
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && volumeGroup.classList.contains('is-open')) {
        setVolumeOpen(false);
        volumeBtn.focus();
      }
    });

    volumeInput.addEventListener('input', function () {
      var v = clampVolume(parseFloat(volumeInput.value));
      audio.volume = v;
      if (v === 0) {
        audio.muted = true;
      } else if (audio.muted) {
        audio.muted = false;
      }
      updateVolumeUI();
      saveVolume(v);
    });

    progressEl.addEventListener('pointerdown', function (e) {
      if (!activeButton || isLoading) return;
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
      if (!activeButton || isLoading) return;
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
      loadGen += 1;
      stopPlayback();
      setVolumeOpen(false);
      bar.classList.remove('visible');
      bar.setAttribute('aria-hidden', 'true');
    });
  })();
