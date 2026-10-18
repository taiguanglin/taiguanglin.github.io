  // 閱讀設置（字級／行距／內容寬度）已搬到 assets/js/reading-prepaint.js：
  // 那裡是唯一真相來源，並在 <head> 內同步執行、首繪前就套用，避免章節頁
  // 先以 16px／800px 畫出來、script.js 到位後再整頁重排（位移 17px）。
  // 本模組只保留「使用者改設定 → 重套」與跨模組共用的狀態變數。
  const R = window.W2EReading;
  const FONT_SIZE_STEP = R.FONT_SIZE_STEP;
  const FONT_STEP_KEY = R.FONT_STEP_KEY;
  const writeStorage = R.writeStorage;

  function getDefaultFontSize() { return R.getDefaultFontSize(); }
  function clampFontSize(size) { return R.clampFontSize(size); }

  // 這三個變數被 02-reader-ux.js（按鈕 active 狀態）與 04-events.js（重設）
  // 直接讀寫，因此維持同名 module-scope 變數，值以 W2EReading 為準。
  let { fontStep, fontSize, lineHeight, contentWidth } = R.getState();

  function applyReadingSettings() {
    R.apply({ fontStep, fontSize, lineHeight, contentWidth });
  }

  function updateFontSize(change) {
    ({ fontSize, fontStep } = R.setFontSize(fontSize + change));
    applyReadingSettings();
    updateFontSizeButtons();
  }

  function updateLineHeight(value) {
    ({ lineHeight } = R.setLineHeight(value));
    applyReadingSettings();
    updateLineHeightButtons();
  }

  function updateContentWidth(value) {
    ({ contentWidth } = R.setContentWidth(value));
    applyReadingSettings();
    updateContentWidthButtons();
  }

  // 閱讀進度功能
  function updateReadingProgress() {
    const scrollTop = window.pageYOffset;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = (scrollTop / docHeight) * 100;
    
    const progressBar = document.querySelector('.reading-progress-bar');
    if (progressBar) {
      progressBar.style.width = Math.max(0, Math.min(100, progress)) + '%';
    }
  }

  // 章節跟踪功能
  function updateCurrentSection() {
    // 首頁跳過章節跟踪
    if (currentChapter.isHomepage) {
      return;
    }
    
    const headings = document.querySelectorAll('h2[id], h3[id], h4[id]');
    const scrollTop = window.pageYOffset;
    const offset = 100; // 偏移量，調整觸發點
    
    let currentSection = null;
    
    // 找到最接近當前位置的章節
    headings.forEach((heading) => {
      const rect = heading.getBoundingClientRect();
      const elementTop = scrollTop + rect.top;
      
      if (elementTop <= scrollTop + offset) {
        currentSection = heading;
      }
    });
    
    // 更新TOC高亮狀態
    const tocItems = document.querySelectorAll('.floating-toc-item[data-target]');
    let activeItem = null;
    
    tocItems.forEach(item => {
      item.classList.remove('active');
      
      if (currentSection) {
        const targetId = '#' + currentSection.id;
        if (item.dataset.target === targetId) {
          item.classList.add('active');
          activeItem = item;
        }
      }
    });
    
    // 自動滾動sidebar到當前章節
    if (activeItem) {
      const tocContainer = activeItem.closest('.floating-toc');
      if (tocContainer && tocContainer.classList.contains('visible')) {
        // 檢查activeItem是否在可視區域內
        const containerRect = tocContainer.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();
        
        // 如果item不在容器的可視區域內，則滾動到該位置
        if (itemRect.top < containerRect.top + 60 || itemRect.bottom > containerRect.bottom - 20) {
          // ⚠️ 只能捲動面板自己的內容，絕不可用 activeItem.scrollIntoView()：
          // scrollIntoView 會「連帶捲動所有可捲動祖先」，包括視窗。面板是
          // position: fixed——項目根本不會隨視窗捲動而移動，瀏覽器卻仍會
          // 為了把項目對齊視窗中央而捲動視窗，把文件拉離閱讀位置。這個
          // 「第二個捲動寫入者」與 05 的收斂迴圈互搶捲軸，就是目錄跳轉時
          // 「畫面在原位置與目標之間來回閃跳 3-4 秒」的元兇（平時開著側欄
          // 閱讀、章節切換時也會被小幅度拉扯）。改為直接捲動面板內容。
          const content = tocContainer.querySelector('.floating-toc-content');
          if (content) {
            const contentRect = content.getBoundingClientRect();
            const delta = (itemRect.top + itemRect.height / 2)
                        - (contentRect.top + contentRect.height / 2);
            content.scrollTo({
              top: Math.max(0, content.scrollTop + delta),
              behavior: 'smooth'
            });
            if (scrollDebugOn()) {
              console.log('[w2e] 側欄面板同步：僅捲動 .floating-toc-content，delta=', Math.round(delta));
            }
          }
        }
      }
    }
  }

  // 顯示通知
  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => document.body.removeChild(toast), 300);
    }, 2000);
  }

  // 複製功能
  function copyText(text) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showToast('已複製到剪貼板');
      });
    } else {
      // 降級處理
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      showToast('已複製到剪貼板');
    }
  }
  
  // 目標是否需要為「經文置頂」留白（講經頁的 sticky 群內）
  function anchorNeedsHeadroom(el) {
    return !!(window.W2E && W2E.sutraPin && W2E.sutraPin.reserveFor &&
              W2E.sutraPin.reserveFor(el) > 0);
  }

  // 錨點目標應停在視窗的哪個位置（距離視窗頂端的偏移）
  // - 目標位於「經文置頂」的 sticky 群內（講經頁）：置頂中的經文佔住視窗最上方，
  //   偏移必須 ≥ 停留經文高度，否則目標（尤其長段落的段首）會被經文蓋住。
  //   09c 另外把同一個高度寫成群上的 scroll-margin-top，讓外部連結的原生
  //   片段錨點導覽也自動留白。
  // - 其他頁面沒有這層遮擋，維持原有的置中。
  function anchorTargetOffset(el) {
    if (anchorNeedsHeadroom(el)) {
      return W2E.sutraPin.reserveFor(el);
    }
    return Math.max(0, (window.innerHeight - el.getBoundingClientRect().height) / 2);
  }

  function anchorTargetScrollTop(el) {
    const absTop = el.getBoundingClientRect().top + window.pageYOffset;
    const max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    return Math.max(0, Math.min(absTop - anchorTargetOffset(el), max));
  }

  // 反覆把目標拉回正確位置，直到連續兩次量測都已在位（或逾時／使用者接手）。
  //
  // 為什麼需要：00-base.css 對 .question/.answer/.para-block 設了
  // `content-visibility: auto` + `contain-intrinsic-size: auto 240px`，
  // 視窗外的區塊先以估計高度佔位、捲動經過後才換成真實高度。於是捲動過程中
  // 文件總高持續變動，任何「捲一次算好的位置」必然落偏（實測偏移數百 px，
  // 有時目標直接被推到視窗外）。停止捲動後被跳過的區塊集合固定，目標的絕對
  // 位置才會穩定，因此用短週期重測試斂即可。
  //
  // 收斂的 scrollTo 是瞬時的，會中途砍掉 scrollIntoView 的平滑動畫——
  // 兩個捲動寫入者同時在場，畫面上就是抖動。故先輪詢等平滑捲動結束
  // （scrollY 連續兩次不動；上限 1.6s 保險），同一時間只留一個寫入者。
  // 單飛：收斂期間使用者再點另一個目錄項（want 不同）時，兩個迴圈互搶
  // 一樣是閃跳——故每回合持有 w2eSettleRunId 編號，較新的跳轉使舊迴圈
  // 立即讓位（含等動畫階段），永遠只有最新目標在收斂。
  //
  // 使用者一開始自己捲（wheel/touch/方向鍵）就立刻放手，不跟使用者搖滾輪。
  function settleAnchorTo(el) {
    const myRun = ++w2eSettleRunId;   // 單飛：較新的跳轉會使本迴圈失效
    let stable = 0;
    let tries = 0;
    let lastWritten = null;   // 上次自己寫入的位置：偵測是否有別人也在捲視窗
    let userScrolled = false;
    const debug = scrollDebugOn();
    const stop = () => { userScrolled = true; };
    window.addEventListener('wheel', stop, { passive: true, once: true });
    window.addEventListener('touchstart', stop, { passive: true, once: true });
    window.addEventListener('keydown', (e) => {
      if (/^(Arrow|Page|Home|End|Space)/.test(e.key)) stop();
    });

    const tick = () => {
      if (userScrolled || !document.body.contains(el)) return;
      if (myRun !== w2eSettleRunId) return;   // 已被較新的跳轉取代，讓位
      const want = anchorTargetScrollTop(el);
      const y = window.pageYOffset;
      if (debug && lastWritten !== null && Math.abs(y - lastWritten) > 4) {
        console.warn('[w2e-anchor-settle] 外部捲動介入（非本迴圈所寫）',
                     { 預期: Math.round(lastWritten), 實際: Math.round(y) });
      }
      if (Math.abs(want - y) > 2) {
        window.scrollTo(0, want);
        lastWritten = want;
        stable = 0;
      } else if (++stable >= 2) {
        return;
      }
      tries++;
      if (tries >= 40) return;   // 約 6 秒上限
      setTimeout(tick, 150);
    };

    const t0 = Date.now();
    let lastY = window.pageYOffset;
    const waitAnimation = () => {
      if (userScrolled || !document.body.contains(el)) return;
      if (myRun !== w2eSettleRunId) return;   // 等動畫期間也被新跳轉取代
      const y = window.pageYOffset;
      const still = (y === lastY);
      lastY = y;
      if (still || Date.now() - t0 > 1600) {
        if (debug) console.log('[w2e-anchor-settle] 平滑捲動結束，開始收斂', { y: Math.round(y) });
        tick();
        return;
      }
      setTimeout(waitAnimation, 120);
    };
    setTimeout(waitAnimation, 150);
  }

  // 處理頁面加載時的錨點跳轉
  function handleInitialAnchor() {
    const hash = window.location.hash;
    if (hash && hash.length > 1) {
      const targetId = hash.substring(1); // 移除#號
      const targetElement = document.getElementById(targetId);
      
      if (targetElement) {
        // 延遲滾動，確保頁面布局完成
        setTimeout(() => {
          // 目標在「經文置頂」的 sticky 群內（講經頁）時用 block:'start'，
          // 讓 09c 寫在群上的 scroll-margin-top 生效；其餘維持置中。
          targetElement.scrollIntoView({
            behavior: 'smooth',
            block: anchorNeedsHeadroom(targetElement) ? 'start' : 'center'
          });
          settleAnchorTo(targetElement);
          
          // 添加臨時高亮效果；使用 class，避免經文的漸層背景蓋住 background-color。
          targetElement.classList.remove('anchor-target-highlight');
          void targetElement.offsetWidth;
          targetElement.classList.add('anchor-target-highlight');
          setTimeout(() => {
            targetElement.classList.remove('anchor-target-highlight');
          }, 3000);
        }, 300);
      }
    }
  }

