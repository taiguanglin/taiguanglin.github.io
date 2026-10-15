  // ============================================================
  // 09b-para-track.js — 講經「段落跟播」
  //
  // 適用頁面：存在帶 data-start/data-end 的 .para-block 段落（books2ebook 依
  // audio_map3/<series>.json 於建置時注入）。整講播放（.qa-play）由
  // 08-qa-audio.js 提供，本模組透過其暴露的 W2E.qaAudio 介面掛接。
  //
  // 功能：
  //   1. 每個含段落時間的講次 h2 旁插入「段落跟播」文字 checkbox
  //      （localStorage
  //      paraTrackEnabled，預設 ON）。ON 時播放中依 audio.currentTime    //      高亮當前段落（.para-active，上一段不做任何視覺改變），並平滑捲動：
    //      目標 = min(當前段頂 − 22% 視窗高, 當前段頂 − 上一段高 − 24px)，
    //      再以「當前段頂 − 停留經文高 − 24px」為上限（經文置頂開啟時，
    //      使高亮段落永遠落在停留經文下方）。僅在段落切換時捲動。
  //   2. 跟播 ON 時點擊任一段落 → 播放所屬講次音檔並 seek 至該段起點，
  //      之後一路順播到底，不在段末自停。拖選文字、有反白選區，或點到
  //      段落內按鈕/連結時不觸發；**只有真的可點播的段落**才顯示手形游標——
  //      建立講次索引時逐段掛 `.para-clickable`，CSS 據此上 pointer
  //      （body.para-track-on .para-block.para-clickable）。不跟播的段落
  //      （沒有時間、或不屬於任何講次區段）保持文字游標，點了沒反應就不該
  //      掛手指頭。
  //   3. toggle 即時生效、不需重新載入；只操作 .para-active
  //      一個 class，不與搜尋高亮等其他模組衝突。
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
    //
    // ⚠️ 必須以「文件順序」走訪（TreeWalker），不可只掃 h2 的直接兄弟節點：
    // 09c 經文置頂自 2026-10 起由 books2ebook 建置期直接輸出
    // `.sutra-pin-group > .sutra-pin-host > .sutra-text.para-block` 包層，經文
    // 之後的講解段落因此是 h2 的**孫節點**。舊的 `h2.nextElementSibling` 掃描
    // 只認得第一段經文之前的那些直屬段落：四十二章 L1 只認 24/63 段（其餘段落在
    // 經文之後，落在包層內），L2–L14 一段都認不到 →「段落跟播」toggle 要麼只跟到
    // 一小截、要麼整個不出現。lengqie/liuzutanjing/lengyanjing 同一原因。
    var sections = [];          // [{btn, paras:[{el,start,end}]}]
    var paraSection = new Map(); // el → section
    var playBtnByH2 = new Map(); // h2 → .qa-play（同一 h2 只認第一個鈕）
    Array.prototype.slice.call(
      document.querySelectorAll('h2 .qa-play')
    ).forEach(function (btn) {
      var h2 = btn.closest('h2');
      if (h2 && !playBtnByH2.has(h2)) playBtnByH2.set(h2, btn);
    });

    if (document.body && typeof document.createTreeWalker === 'function') {
      var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
      var cur = null;
      while (walker.nextNode()) {
        var el = walker.currentNode;
        // 任何 h2 都是講次邊界：有播放鈕者開新講次，其餘（頁首「本章目录」等）
        // 結束前一講，與原本 nextElementSibling 掃描的語意一致。
        if (el.tagName === 'H2') {
          var btn = playBtnByH2.get(el);
          cur = btn ? { btn: btn, paras: [] } : null;
          if (cur) sections.push(cur);
          continue;
        }
        if (!cur || !el.classList || !el.classList.contains('para-block')) continue;
        if (!el.hasAttribute('data-start') || !el.hasAttribute('data-end')) continue;
        var s = parseFloat(el.getAttribute('data-start'));
        var e = parseFloat(el.getAttribute('data-end'));
        if (isFinite(s) && isFinite(e) && e > s) {
          cur.paras.push({ el: el, start: s, end: e });
        }
      }
    }

    // 一段時間都沒對到的講次不建 toggle；段內依時間排序後才掛 paraSection
    sections = sections.filter(function (sec) { return sec.paras.length > 0; });
    sections.forEach(function (sec) {
      sec.paras.sort(function (a, b) { return a.start - b.start; });
      sec.paras.forEach(function (p) {
        paraSection.set(p.el, sec);
        // `.para-clickable` = 手形游標的唯一依據：只有真的歸屬某講（點了會 seek
        // 並播放）才掛。不可改回 `.para-block[data-start]`：那只代表「有時間」，
        // 不屬於任何講次區段的段落點了沒有反應，手指頭是假承諾。
        p.el.classList.add('para-clickable');
      });
    });
    if (!sections.length) return;

    // ---- 講次 h2 旁的「段落跟播」toggle -------------------------------
    // 文字 checkbox（取代舊 🎯 純圖示按鈕，好理解用途）：
    // <label class="para-track-toggle"><input type="checkbox"><span>段落跟播</span></label>
    var toggleLabel = ptText('paraTrack.toggle', '段落跟播');
    var toggles = [];
    sections.forEach(function (sec) {
      var t = document.createElement('label');
      t.className = 'para-track-toggle';
      t.title = toggleLabel;
      var box = document.createElement('input');
      box.type = 'checkbox';
      box.checked = trackOn;
      box.setAttribute('aria-label', toggleLabel);
      var txt = document.createElement('span');
      txt.textContent = toggleLabel;
      t.appendChild(box);
      t.appendChild(txt);
      sec.btn.parentNode.insertBefore(t, sec.btn.nextSibling);
      toggles.push(t);
      box.addEventListener('change', function () {
        trackOn = box.checked;
        saveState(TRACK_KEY, trackOn);
        syncToggleUI();
        if (!trackOn) {
          clearParaClasses();
        }
      });
    });

    function syncToggleUI() {
      toggles.forEach(function (t) {
        t.classList.toggle('on', trackOn);
        t.setAttribute('aria-pressed', trackOn ? 'true' : 'false');
        var box = t.querySelector('input[type="checkbox"]');
        if (box && box.checked !== trackOn) box.checked = trackOn;
      });
      // 跟播開關同步到 body，供 CSS 把可點播段落切成手形游標
      if (document.body) document.body.classList.toggle('para-track-on', trackOn);
    }

    syncToggleUI();

    // ---- 段落高亮與捲動 -----------------------------------------------
    var activePara = null;   // 目前高亮的段落元素
    var prevPara = null;     // 上一段（僅供捲動定位保留可見，不做視覺改變）

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
      // 經文置頂（09c-sutra-pin）：目標段落所在的 sticky 群經文捲動後會停在
      // 視窗頂（top:0、佔高 reserve），捲動上限取「段頂 − reserve − 24px」，
      // 確保高亮段落捲動後永遠落在停留經文下方、不被蓋住。
      if (window.W2E && W2E.sutraPin && W2E.sutraPin.reserveFor) {
        var reserve = W2E.sutraPin.reserveFor(el);
        if (reserve > 0) target = Math.min(target, y - reserve - 24);
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

    // ---- timeupdate：節流的高亮跟播 -------------------------------------
    var lastTrackTs = 0;
    audio.addEventListener('timeupdate', function () {
      if (!trackOn || audio.paused) return;
      var now = Date.now();
      if (now - lastTrackTs < SCROLL_THROTTLE_MS) return;
      lastTrackTs = now;
      updateTracking();
    });
    // 切換講次（點章節喇叭）→ 清掉段落高亮，等 timeupdate 重新定位
    sections.forEach(function (sec) {
      sec.btn.addEventListener('click', function () {
        if (!trackOn) return;
        // 章節鈕播放從頭開始：清掉前一段落高亮，等 timeupdate 重新定位
        clearParaClasses();
      });
    });

    // ---- 點段落即播（僅跟播 ON 時） ------------------------------------
    // 誤觸排除：拖選文字（按下/放開距離過大或放開時有反白選區）、
    // 點到段落內的互動元件（⋯ 按鈕列、書籤標識、連結、按鈕）都不觸發播放。
    var downPos = null;
    document.addEventListener('mousedown', function (e) {
      if (!trackOn) { downPos = null; return; }
      downPos = (e.target && e.target.closest && e.target.closest('.para-block[data-start]'))
        ? { x: e.clientX, y: e.clientY }
        : null;
    }, true);
    document.addEventListener('click', function (e) {
      if (!trackOn) return;
      var el = e.target && e.target.closest
        ? e.target.closest('.para-block[data-start]')
        : null;
      if (!el) return;
      // 段落內的操作元件：交給各自的處理，不觸發播放
      if (e.target.closest('.qa-actions, .bookmark-indicator, a, button')) return;
      // 拖選：按下與放開距離超過 8px，視為選取操作
      if (downPos) {
        var dx = e.clientX - downPos.x;
        var dy = e.clientY - downPos.y;
        if (dx * dx + dy * dy > 64) return;
      }
      // 放開時有反白選區：視為選取文字，不播放
      try {
        var sel = window.getSelection();
        if (sel && !sel.isCollapsed && String(sel).length > 0) return;
      } catch (err) { /* 取不到選區時照常走播放流程 */ }
      var sec = paraSection.get(el);
      if (!sec) return;
      var start = parseFloat(el.getAttribute('data-start'));
      if (!isFinite(start)) return;

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
