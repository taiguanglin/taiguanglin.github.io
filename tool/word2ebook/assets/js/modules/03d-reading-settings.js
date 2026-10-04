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
          activeItem.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
          });
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
  // 使用者一開始自己捲（wheel/touch/方向鍵）就立刻放手，不跟使用者搖滾輪。
  function settleAnchorTo(el) {
    let stable = 0;
    let tries = 0;
    let userScrolled = false;
    const stop = () => { userScrolled = true; };
    window.addEventListener('wheel', stop, { passive: true, once: true });
    window.addEventListener('touchstart', stop, { passive: true, once: true });
    window.addEventListener('keydown', (e) => {
      if (/^(Arrow|Page|Home|End|Space)/.test(e.key)) stop();
    });

    const tick = () => {
      if (userScrolled || !document.body.contains(el)) return;
      const want = anchorTargetScrollTop(el);
      if (Math.abs(want - window.pageYOffset) > 2) {
        window.scrollTo(0, want);
        stable = 0;
      } else if (++stable >= 2) {
        return;
      }
      if (++tries >= 40) return;   // 約 6 秒上限
      setTimeout(tick, 150);
    };
    setTimeout(tick, 150);
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

