  // ============================================================
  // 09b-para-track.js — 講經「段落跟播」
  //
  // 適用頁面：存在帶 data-start/data-end 的 .para-block 段落（books2ebook 依
  // audio_map3/<series>.json 於建置時注入）。整講播放（.qa-play）由
  // 08-qa-audio.js 提供，本模組透過其暴露的 W2E.qaAudio 介面掛接。
  //
  // 功能：
  //   1. 每個含段落時間的講次 h2 旁插入「段落跟播」toggle（🎯，localStorage
  //      paraTrackEnabled，預設 ON）。ON 時播放中依 audio.currentTime
  //      高亮當前段落（.para-active，前一段 .para-prev 淡化），並平滑捲動：
  //      目標 = min(當前段頂 − 22% 視窗高, 當前段頂 − 上一段高 − 24px)，
  //      使上一段底部仍貼近視窗頂端可見。僅在段落切換時捲動。
  //   2. 跟播 ON 時點擊任一段落 → 播放所屬講次音檔並 seek 至該段起點。
  //      此為「para 模式」：若「段末自停」toggle（localStorage paraAutoStop，
  //      預設 ON）開啟，播到該段 end 即自動暫停並結束 para 模式。由章節
  //      喇叭觸發的整講播放永不自停。
  //   3. toggle 即時生效、不需重新載入；只操作 .para-active/.para-prev
  //      兩個 class，不與搜尋高亮等其他模組衝突。
  //
  // 以具名 IIFE 隔離作用域（本檔被串接進共用的 DOMContentLoaded 函式中）。
  // ============================================================
  ;(function () {
    var paras = Array.prototype.slice.call(
      document.querySelectorAll('.para-block[data-start]')
    );
    if (!paras.length) return;
    if (!window.W2E || !W2E.qaAudio) return;

    var TRACK_KEY = 'paraTrackEnabled';
    var AUTOSTOP_KEY = 'paraAutoStop';
    var SCROLL_THROTTLE_MS = 250;

    var qa = W2E.qaAudio;
    var audio = qa.audio;

    function loadState(key, dflt) {
      try {
        var v = localStorage.getItem(key);
        return v == null ? dflt : v === '1';
      } catch (e) {
        return dflt;
      }
    }

    function saveState(key, val) {
      try { localStorage.setItem(key, val ? '1' : '0'); } catch (e) {}
    }

    var trackOn = loadState(TRACK_KEY, true);
    var autoStopOn = loadState(AUTOSTOP_KEY, true);

    function isTrad() {
      return typeof isTraditionalChinesePage === 'function' && isTraditionalChinesePage();
    }

    function ptText(key, fallback) {
      if (typeof getI18nText === 'function') {
        return getI18nText(key, isTrad(), fallback, {});
      }
      return fallback;
    }

    // ---- 建立「講次 → 段落清單」索引 ----------------------------------
    // 講次 = 含 .qa-play 的 h2；其後直到下一個 h2 之間、且帶齊
    // data-start/data-end 的 .para-block 為該講段落（h3 小節不打斷歸屬）。
    var sections = [];          // [{btn, paras:[{el,start,end}]}]
    var paraSection = new Map(); // el → section
    Array.prototype.slice.call(
      document.querySelectorAll('h2 .qa-play')
    ).forEach(function (btn) {
      var h2 = btn.closest('h2');
      if (!h2) return;
      var list = [];
      var node = h2.nextElementSibling;
      while (node && node.tagName !== 'H2') {
        if (node.classList && node.classList.contains('para-block') &&
            node.hasAttribute('data-start') && node.hasAttribute('data-end')) {
          var s = parseFloat(node.getAttribute('data-start'));
          var e = parseFloat(node.getAttribute('data-end'));
          if (isFinite(s) && isFinite(e) && e > s) {
            list.push({ el: node, start: s, end: e });
          }
        }
        node = node.nextElementSibling;
      }
      if (!list.length) return;
      list.sort(function (a, b) { return a.start - b.start; });
      var sec = { btn: btn, paras: list };
      sections.push(sec);
      list.forEach(function (p) { paraSection.set(p.el, sec); });
    });
    if (!sections.length) return;

    // ---- 講次 h2 旁的「段落跟播」toggle -------------------------------
    var toggleLabel = ptText('paraTrack.toggle', '段落跟播');
    var toggles = [];
    sections.forEach(function (sec) {
      var t = document.createElement('button');
      t.type = 'button';
      t.className = 'para-track-toggle';
      t.textContent = '🎯';
      t.setAttribute('aria-label', toggleLabel);
      t.title = toggleLabel;
      sec.btn.parentNode.insertBefore(t, sec.btn.nextSibling);
      toggles.push(t);
      t.addEventListener('click', function () {
        trackOn = !trackOn;
        saveState(TRACK_KEY, trackOn);
        syncToggleUI();
        if (!trackOn) {
          clearParaClasses();
          paraMode = null;
        }
      });
    });

    function syncToggleUI() {
      toggles.forEach(function (t) {
        t.classList.toggle('on', trackOn);
        t.setAttribute('aria-pressed', trackOn ? 'true' : 'false');
      });
    }

    // ---- 播放器進度條列的「段末自停」toggle ---------------------------
    var autoStopLabel = ptText('paraTrack.autoStop', '段末自停');
    var seekRow = document.querySelector('.qa-player-seek-row');
    var autoStopBtn = null;
    if (seekRow) {
      autoStopBtn = document.createElement('button');
      autoStopBtn.type = 'button';
      autoStopBtn.className = 'qa-player-skip para-autostop-toggle';
      autoStopBtn.textContent = '⏹';
      autoStopBtn.setAttribute('aria-label', autoStopLabel);
      autoStopBtn.title = autoStopLabel;
      seekRow.appendChild(autoStopBtn);
      autoStopBtn.addEventListener('click', function () {
        autoStopOn = !autoStopOn;
        saveState(AUTOSTOP_KEY, autoStopOn);
        syncAutoStopUI();
      });
    }
    function syncAutoStopUI() {
      if (!autoStopBtn) return;
      autoStopBtn.classList.toggle('on', autoStopOn);
      autoStopBtn.setAttribute('aria-pressed', autoStopOn ? 'true' : 'false');
    }

    syncToggleUI();
    syncAutoStopUI();

    // ---- 段落高亮與捲動 -----------------------------------------------
    var activePara = null;   // 目前高亮的段落元素
    var prevPara = null;     // 目前淡化的上一段
    var paraMode = null;     // 點段落觸發的播放：{el, end}，段末自停用

    function clearParaClasses() {
      if (activePara) activePara.classList.remove('para-active');
      if (prevPara) prevPara.classList.remove('para-prev');
      activePara = null;
      prevPara = null;
    }

    function setActivePara(el, prevEl) {
      if (el === activePara) return;
      clearParaClasses();
      activePara = el;
      prevPara = prevEl || null;
      el.classList.add('para-active');
      if (prevPara) prevPara.classList.add('para-prev');
      scrollToPara(el, prevEl);
    }

    function scrollToPara(el, prevEl) {
      // 目標：當前段頂停在視窗上方約 1/4；若上一段存在，保留其底部貼近
      // 視窗頂端可見（取較小 scrollTop，即「頂 − 上一段高 − 24px」錨點）。
      var y = el.getBoundingClientRect().top + window.pageYOffset;
      var target = y - window.innerHeight * 0.22;
      if (prevEl) {
        var prevH = prevEl.getBoundingClientRect().height;
        target = Math.min(target, y - prevH - 24);
      }
      window.scrollTo({ top: Math.max(0, target), behavior: 'smooth' });
    }

    function findSectionByButton(btn) {
      if (!btn) return null;
      for (var i = 0; i < sections.length; i++) {
        if (sections[i].btn === btn) return sections[i];
      }
      return null;
    }

    function sectionIndexOf(sec, time) {
      // 回傳 time 所在的段落 index；落在兩段之間時取下一段的上一段（-1=尚未到首段）
      var list = sec.paras;
      if (time < list[0].start) return -1;
      for (var i = list.length - 1; i >= 0; i--) {
        if (list[i].start <= time) return i;
      }
      return -1;
    }

    function updateTracking() {
      var sec = findSectionByButton(qa.getActiveButton());
      if (!sec) { clearParaClasses(); return; }
      var idx = sectionIndexOf(sec, audio.currentTime);
      if (idx < 0) { clearParaClasses(); return; }
      var cur = sec.paras[idx];
      setActivePara(cur.el, idx > 0 ? sec.paras[idx - 1].el : null);
    }

    // ---- timeupdate：節流的高亮跟播 + 段末自停 -------------------------
    var lastTrackTs = 0;
    audio.addEventListener('timeupdate', function () {
      if (paraMode && autoStopOn && audio.currentTime >= paraMode.end) {
        // 段末自停：僅「點段落觸發」的播放才生效；暫停後結束 para 模式
        paraMode = null;
        audio.pause();
        return;
      }
      if (!trackOn || audio.paused) return;
      var now = Date.now();
      if (now - lastTrackTs < SCROLL_THROTTLE_MS) return;
      lastTrackTs = now;
      updateTracking();
    });
    audio.addEventListener('ended', function () { paraMode = null; });

    // 切換講次（點章節喇叭）→ 脫離 para 模式（整講順播，絕不自停）
    sections.forEach(function (sec) {
      sec.btn.addEventListener('click', function () {
        paraMode = null;
        if (!trackOn) return;
        // 章節鈕播放從頭開始：清掉前一段落高亮，等 timeupdate 重新定位
        clearParaClasses();
      });
      // 播放中點同一鈕也會暫停，這裡已先清模式，行為一致
    });

    // ---- 點段落即播（僅跟播 ON 時） ------------------------------------
    document.addEventListener('click', function (e) {
      if (!trackOn) return;
      var el = e.target && e.target.closest
        ? e.target.closest('.para-block[data-start]')
        : null;
      if (!el) return;
      var sec = paraSection.get(el);
      if (!sec) return;
      var start = parseFloat(el.getAttribute('data-start'));
      var end = parseFloat(el.getAttribute('data-end'));
      if (!isFinite(start) || !isFinite(end)) return;
      paraMode = { el: el, end: end };

      function doSeek() { qa.seekAbs(start); }

      if (qa.getActiveButton() !== sec.btn) {
        // 換講：qa.play 會在 loadedmetadata 時 seek 回 0，故我們的 seek
        // 註冊在其後（once），確保最後停在段落起點
        qa.play(sec.btn);
        if (audio.readyState >= 1) {
          doSeek();
        } else {
          audio.addEventListener('loadedmetadata', doSeek, { once: true });
        }
      } else {
        doSeek();
        if (audio.paused) {
          var p = audio.play();
          if (p && p.catch) p.catch(function () {});
        }
      }
      // 立即回饋高亮（不等 timeupdate）
      var idx = -1;
      for (var i = 0; i < sec.paras.length; i++) {
        if (sec.paras[i].el === el) { idx = i; break; }
      }
      if (idx >= 0) {
        setActivePara(el, idx > 0 ? sec.paras[idx - 1].el : null);
      }
    });
  })();
