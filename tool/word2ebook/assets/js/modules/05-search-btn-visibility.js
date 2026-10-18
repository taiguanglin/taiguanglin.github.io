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
  // 03d 的 settleAnchorTo 接在「帶錨點載入」與書籤項點擊路徑；其餘頁內點擊
  // （目錄、回到頂部以外的 # 錨點）都在這裡，兩邊用同樣的「等動畫→短週期
  // 重測」收斂。浮動目錄項（04-events）、首頁目錄清單（03b）、.toc-count
  // 直跳（16）、lightbox「跳回圖片處」（09）也共用本函式——它們與 # 錨點
  // 同樣會跳到「從未渲染」的遠處內容，一次性捲動必然落偏；16/09 是隔離
  // IIFE，經 W2E.settleInPageAnchor 呼叫。
  // 收斂用 block:'start' 對齊（與 scrollIntoView 一致）：目標的
  // scroll-margin-top（講經頁 = 09c 逐群寫入的經文讓位高度）也要扣掉，
  // 否則收斂會把 scrollIntoView 特意留給停留經文的空間又拉回去。
  // 使用者一開始自己捲就立刻放手，不跟使用者搶滚輪。
  //
  // ⚠️ 不能「連續兩次量測相同」就收工：scrollIntoView 的落點本來就是用
  // 同一套估算高度算的，動畫剛結束時 want 與 scrollY 短暫一致，接著上方
  // 區塊換成真實高度、目標又滑走（ebook/ 實測定格偏 755px）。故：
  //   · 至少量測 MIN_TICKS 次（約 1.8s）才允許收工；
  //   · 文件總高一變（估算→真實）就把 stable 歸零重算。
  function anchorScrollMarginTop(el) {
    // getComputedStyle 不支援 scroll-margin-top 的舊瀏覽器回 0（= 舊行為）
    const v = parseFloat(getComputedStyle(el).scrollMarginTop);
    return isNaN(v) ? 0 : v;
  }

  function settleInPageAnchor(el) {
    const MIN_TICKS = 12;   // 約 1.8s：等高度換算（240px 估計→真實）收斂
    const MAX_TICKS = 40;   // 約 6s 上限
    const TICK_MS = 150;
    const myRun = ++w2eSettleRunId;   // 單飛：較新的跳轉會使本迴圈失效
    const debug = scrollDebugOn();
    let stable = 0;
    let tries = 0;
    let lastHeight = document.documentElement.scrollHeight;
    let lastWritten = null;   // 上次自己寫入的位置：偵測是否有別人也在捲視窗
    let userScrolled = false;
    const stop = () => { userScrolled = true; };
    window.addEventListener('wheel', stop, { passive: true, once: true });
    window.addEventListener('touchstart', stop, { passive: true, once: true });
    window.addEventListener('keydown', (e) => {
      if (/^(Arrow|Page|Home|End|Space)/.test(e.key)) stop();
    });

    const tick = () => {
      if (userScrolled || !document.body.contains(el)) return;
      if (myRun !== w2eSettleRunId) return;   // 已被較新的跳轉取代，讓位
      const height = document.documentElement.scrollHeight;
      if (height !== lastHeight) { lastHeight = height; stable = 0; }
      const want = Math.max(0, el.getBoundingClientRect().top + window.pageYOffset
                                       - anchorScrollMarginTop(el));
      const y = window.pageYOffset;
      if (debug && lastWritten !== null && Math.abs(y - lastWritten) > 4) {
        // 收斂期間視窗被本迴圈以外的力量拉走＝還有第二個捲動寫入者
        // （歷史案例：03d 側欄同步的 scrollIntoView 連帶捲動視窗）
        console.warn('[w2e-settle] 外部捲動介入（非本迴圈所寫）',
                     { 預期: Math.round(lastWritten), 實際: Math.round(y), 嘗試: tries });
      }
      if (Math.abs(want - y) > 2) {
        window.scrollTo(0, want);
        lastWritten = want;
        stable = 0;
      } else {
        stable++;
      }
      tries++;
      if (debug) {
        console.log('[w2e-settle]', { 嘗試: tries, want: Math.round(want),
          y: Math.round(window.pageYOffset), stable: stable, 文件高: height });
      }
      if ((tries >= MIN_TICKS && stable >= 3) || tries >= MAX_TICKS) return;
      setTimeout(tick, TICK_MS);
    };

    // 先等發動的平滑捲動結束才開始修正：下面的 scrollTo 是瞬時的，會中途
    // 砍掉 scrollIntoView 的平滑動畫——兩個捲動寫入者同時在場，畫面就是
    // 抖動／閃跳（與 03d 側欄面板同步互搶視窗的教訓同源）。輪詢 scrollY
    // 連續兩次不動＝動畫結束；上限 1.6s 後無論如何開始（保險）。
    const t0 = Date.now();
    let lastY = window.pageYOffset;
    const waitAnimation = () => {
      if (userScrolled || !document.body.contains(el)) return;
      if (myRun !== w2eSettleRunId) return;   // 等動畫期間也被新跳轉取代
      const y = window.pageYOffset;
      const still = (y === lastY);
      lastY = y;
      if (still || Date.now() - t0 > 1600) {
        if (debug) console.log('[w2e-settle] 平滑捲動結束，開始收斂', { y: Math.round(y) });
        tick();
        return;
      }
      setTimeout(waitAnimation, 120);
    };
    setTimeout(waitAnimation, TICK_MS);
  }

  // 供隔離 IIFE 模組（16-jump-share、09-image-lightbox）使用的對外介面
  W2E.settleInPageAnchor = settleInPageAnchor;

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

