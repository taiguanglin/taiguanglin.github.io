  // ========== 搜索按鈕智能顯示功能 ==========
  
  // 檢測頂部搜索控制按鈕是否在視窗中完全可見
  function areTopSearchControlsVisible() {
    const searchHeader = document.querySelector('.search-results-header');
    if (!searchHeader) return false;
    
    const rect = searchHeader.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    
    // 設置觸發閾值：當頂部按鈕開始被遮住時就顯示底部按鈕
    // 使用50px的緩衝區，確保用戶體驗的連續性
    const threshold = 50;
    
    // 檢查頂部控制按鈕是否有足夠的可見區域
    // 當按鈕開始被遮住超過閾值時，就認為不完全可見
    return rect.bottom > threshold && rect.top < (viewportHeight - threshold);
  }
  
  // 更新底部搜索按鈕的顯示狀態
  function updateBottomSearchButtonsVisibility() {
    const bottomFooter = document.querySelector('.search-results-footer');
    if (!bottomFooter) return;
    
    const areTopControlsVisible = areTopSearchControlsVisible();
    
    // 當頂部按鈕可見時隱藏底部按鈕，否則顯示底部按鈕
    if (areTopControlsVisible) {
      bottomFooter.style.display = 'none';
    } else {
      bottomFooter.style.display = 'block';
    }
  }

  // 滾動事件（帶節流優化）
  let scrollTimeout;
  function handleScroll() {
    updateReadingProgress();
    
    // 節流處理章節跟踪，避免過度頻繁更新
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(updateCurrentSection, 50);
    
    // 更新搜索按鈕顯示狀態
    updateBottomSearchButtonsVisibility();
  }
  
  window.addEventListener('scroll', handleScroll);
  
  // 窗口大小變化時更新搜索按鈕狀態
  window.addEventListener('resize', () => {
    setTimeout(updateBottomSearchButtonsVisibility, 100);
  });
  
  updateReadingProgress();
  updateCurrentSection(); // 初始化當前章節


  // 平滑滾動章節內 TOC 與回到頂部
  //
  // 為什麼 scrollIntoView 之後還要「收斂」：00-base.css 對
  // .question/.answer/.para-block 設了 `content-visibility: auto` +
  // `contain-intrinsic-size: auto 240px`，視窗外的區塊先以估計高度佔位、
  // 渲染後才換成真實高度。平滑捲動的落點是啟動當下的文件高度算出來的；
  // 捲動途中經過的區塊一個個換成真實高度後，文件總高跟著變，落點必然偏移
  // （ebook/ 實測偏 600+ px，方向取決於上方高度是膨脤還是縮小，兩本書都會發生）。
  // 03d 的 settleAnchorTo 只接在「帶錨點載入」路徑；頁內點擊（目錄、書籤、
  // 回到頂部以外的 # 錨點）都在這裡，故這裡也用同一套短週期重測試斂。
  // 收斂用 block:'start' 對齊（與 scrollIntoView 一致）；使用者一開始自己捲
  // 就立刻放手，不跟使用者搶滚輪。
  //
  // ⚠️ 不能「連續兩次量測相同」就收工：scrollIntoView 的落點本來就是用
  // 同一套估算高度算的，動畫剛結束時 want 與 scrollY 短暫一致，接著上方
  // 區塊換成真實高度、目標又滑走（ebook/ 實測定格偏 755px）。故：
  //   · 至少量測 MIN_TICKS 次（約 1.8s）才允許收工；
  //   · 文件總高一變（估算→真實）就把 stable 歸零重算。
  function settleInPageAnchor(el) {
    const MIN_TICKS = 12;   // 約 1.8s：等 scrollIntoView 動畫結束＋高度換算
    const MAX_TICKS = 40;   // 約 6s 上限
    const TICK_MS = 150;
    let stable = 0;
    let tries = 0;
    let lastHeight = document.documentElement.scrollHeight;
    let userScrolled = false;
    const stop = () => { userScrolled = true; };
    window.addEventListener('wheel', stop, { passive: true, once: true });
    window.addEventListener('touchstart', stop, { passive: true, once: true });
    window.addEventListener('keydown', (e) => {
      if (/^(Arrow|Page|Home|End|Space)/.test(e.key)) stop();
    });

    const tick = () => {
      if (userScrolled || !document.body.contains(el)) return;
      const height = document.documentElement.scrollHeight;
      if (height !== lastHeight) { lastHeight = height; stable = 0; }
      const want = Math.max(0, el.getBoundingClientRect().top + window.pageYOffset);
      if (Math.abs(want - window.pageYOffset) > 2) {
        window.scrollTo(0, want);
        stable = 0;
      } else {
        stable++;
      }
      tries++;
      if ((tries >= MIN_TICKS && stable >= 3) || tries >= MAX_TICKS) return;
      setTimeout(tick, TICK_MS);
    };
    setTimeout(tick, TICK_MS);
  }

  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.pushState(null, null, href);
        // href="" 或單純 "#"（回到頁頂）不需要收斂
        if (href.length > 1) settleInPageAnchor(target);
      }
    });
  });

