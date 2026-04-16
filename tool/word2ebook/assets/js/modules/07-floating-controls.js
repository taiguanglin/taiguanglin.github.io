  // ========== 浮动层级控制功能 ==========
  
  // 检测固定层级控制按钮是否在视窗中可见
  function areTocControlsVisible() {
    const tocControls = document.querySelector('.toc-level-controls');
    if (!tocControls) return false;
    
    const rect = tocControls.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    
    // 检查控制按钮是否在视窗内可见
    return rect.bottom > 0 && rect.top < viewportHeight;
  }
  
  // 检测目录内容是否在视窗中可见（确保有目录需要控制）
  function isTocContentVisible() {
    const mainToc = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!mainToc) return false;
    
    const rect = mainToc.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    
    // 目录内容的任何部分在视窗内都算可见
    return rect.bottom > 0 && rect.top < viewportHeight;
  }
  
  // 更新浮动层级控制的显示状态（全局函数，供搜索功能调用）
  function updateFloatingControlsState() {
    const floatingControls = document.getElementById('floating-level-controls');
    if (!floatingControls) return;
    
    const currentScrollY = window.scrollY;
    const isMobile = window.innerWidth <= 600;
    const scrollThreshold = isMobile ? 100 : 200;
    
    // 检查固定控制按钮是否可见
    const areControlsVisible = areTocControlsVisible();
    // 检查目录内容是否可见（确保有内容需要控制）
    const isTocContentAvailable = isTocContentVisible();
    
    // 只有在达到滚动阈值、固定控制按钮不可见、但目录内容仍可见时才显示浮动控制
    const shouldShow = currentScrollY > scrollThreshold && !areControlsVisible && isTocContentAvailable;
    
    if (shouldShow) {
      floatingControls.style.display = 'block';
    } else {
      floatingControls.style.display = 'none';
    }
  }
  
  function initFloatingLevelControls() {
    const floatingControls = document.getElementById('floating-level-controls');
    const tocControls = document.querySelector('.toc-level-controls');
    
    if (!floatingControls || !tocControls) return;
    
    // 确保浮动控制也应用层级检测（以防在初始化时有时序问题）
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (tocContainer) {
      detectAndHideLevelButtons(tocContainer);
    }
    
    // 调试模式：检查元素是否正确创建
    const debugMode = window.location.hash.includes('debug');
    if (debugMode) {
      console.log('FloatingControls found:', floatingControls);
      console.log('Screen size:', window.innerWidth, 'x', window.innerHeight);
      console.log('Device pixel ratio:', window.devicePixelRatio);
      console.log('User agent:', navigator.userAgent);
    }
    
    // 绑定浮动按钮事件
    bindFloatingLevelEvents();
    
    // 绑定浮动层级控制的收縮/展開功能
    initFloatingLevelToggle();
    
    // 样式重置函数 - 清除JavaScript设置的内联样式
    function resetFloatingControlsStyles() {
      floatingControls.style.removeProperty('right');
      floatingControls.style.removeProperty('zIndex');
      floatingControls.style.removeProperty('position');
      if (debugMode) {
        console.log('Floating controls styles reset');
      }
    }
    
    // 重新应用正确的样式
    function applyCorrectStyles() {
      const isMobile = window.innerWidth <= 600;
      const isSmallMobile = window.innerWidth <= 400;
      
      if (isMobile) {
        // 移动端保持右側定位，設置必要的樣式
        floatingControls.style.zIndex = '10000';
        floatingControls.style.position = 'fixed';
        floatingControls.style.right = isSmallMobile ? '5px' : '8px';
        // 移除 left 設定，確保右側定位
        floatingControls.style.removeProperty('left');
      } else {
        // 桌面端时清除所有内联样式，让CSS媒体查询生效
        resetFloatingControlsStyles();
      }
      
      if (debugMode) {
        console.log('Styles applied for:', isMobile ? 'mobile' : 'desktop', 
                   `(${window.innerWidth}px)`);
      }
    }

    // 监听滚动，控制浮动按钮显示
    let lastScrollY = window.scrollY;
    const tocControlsRect = tocControls.getBoundingClientRect();
    const initialTop = tocControlsRect.top + window.scrollY;
    
    function handleScroll() {
      const currentScrollY = window.scrollY;
      // 检测移动端，降低显示门槛
      const isMobile = window.innerWidth <= 600;
      const scrollThreshold = isMobile ? 100 : 200; // 移动端更早显示
      
      // 检查固定控制按钮是否可见
      const areControlsVisible = areTocControlsVisible();
      // 检查目录内容是否可见
      const isTocContentAvailable = isTocContentVisible();
      
      // 只有在达到滚动阈值、固定控制按钮不可见、但目录内容仍可见时才显示浮动控制
      const shouldShowFloating = currentScrollY > scrollThreshold && !areControlsVisible && isTocContentAvailable;
      
      // 调试输出
      if (debugMode && currentScrollY > 50) {
        console.log(`Scroll: ${currentScrollY}px, Mobile: ${isMobile}, Threshold: ${scrollThreshold}, ControlsVisible: ${areControlsVisible}, TocContentVisible: ${isTocContentAvailable}, Show: ${shouldShowFloating}`);
      }
      
      if (shouldShowFloating) {
        // 滚动时显示浮动版本（仅当固定按钮不可见但目录内容可见时）
        floatingControls.style.display = 'block';
        // 应用正确的样式（基于当前屏幕尺寸）
        applyCorrectStyles();
      } else {
        // 页面顶部时、固定按钮可见时、或目录内容不可见时隐藏浮动版本
        floatingControls.style.display = 'none';
      }
      
      lastScrollY = currentScrollY;
    }
    
    // 添加滚动监听
    window.addEventListener('scroll', handleScroll, { passive: true });
    
    // 添加窗口大小变化监听（处理屏幕旋转）
    let resizeTimeout;
    window.addEventListener('resize', () => {
      // 去抖动处理，避免resize过程中频繁触发
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        if (debugMode) {
          console.log('Resize detected, new size:', window.innerWidth, 'x', window.innerHeight);
        }
        // 重新应用字体设置，确保在屏幕尺寸变化时字体调整依然有效
        applyReadingSettings();
        // 重置所有内联样式，然后重新应用
        resetFloatingControlsStyles();
        handleScroll(); // 重新检查显示状态和应用样式
      }, 150); // 增加延迟确保resize完全完成
    }, { passive: true });
    
    // 添加方向变化监听（移动端特有）
    function handleOrientationChange() {
      setTimeout(() => {
        if (debugMode) {
          console.log('Orientation changed, new size:', window.innerWidth, 'x', window.innerHeight);
        }
        // 重新应用字体设置，确保方向变化后字体调整依然有效
        applyReadingSettings();
        resetFloatingControlsStyles();
        handleScroll();
      }, 200);
    }
    
    if (screen && screen.orientation) {
      screen.orientation.addEventListener('change', handleOrientationChange);
    } else {
      // 兼容旧浏览器的方向变化检测
      window.addEventListener('orientationchange', handleOrientationChange);
    }
    
    // 初始状态
    handleScroll();
  }
  
  function initFloatingLevelToggle() {
    const toggleBtn = document.getElementById('floating-level-toggle');
    const floatingControls = document.getElementById('floating-level-controls');
    
    if (!toggleBtn || !floatingControls) return;
    
    // 獲取保存的收縮狀態，默認為展開（false）
    const savedState = localStorage.getItem('floating-level-collapsed');
    const isCollapsed = savedState === 'true'; // 只有明確設置為 'true' 才收縮，其他情況（包括 null）都展開
    
    // 應用保存的狀態
    if (isCollapsed) {
      floatingControls.classList.add('collapsed');
      toggleBtn.innerHTML = '↔';
      toggleBtn.title = getI18nText('level_control.collapse_expand', false, '收縮/展開層級控制');
    } else {
      floatingControls.classList.remove('collapsed');
      toggleBtn.innerHTML = '⇄';
      toggleBtn.title = getI18nText('level_control.collapse_expand', false, '收縮/展開層級控制');
    }
    
    // 綁定點擊事件
    toggleBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      
      const isNowCollapsed = floatingControls.classList.contains('collapsed');
      
      if (isNowCollapsed) {
        // 展開
        floatingControls.classList.remove('collapsed');
        toggleBtn.innerHTML = '⇄';
        localStorage.setItem('floating-level-collapsed', 'false');
      } else {
        // 收縮
        floatingControls.classList.add('collapsed');
        toggleBtn.innerHTML = '↔';
        localStorage.setItem('floating-level-collapsed', 'true');
      }
    });
  }
  
  function bindFloatingLevelEvents() {
    const floatingButtons = document.querySelectorAll('.floating-level-btn');
    floatingButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const level = this.getAttribute('data-level');
        
        // 更新所有按钮状态（包括顶部和浮动）
        updateAllLevelButtonsActive(level);
        
        // 设置显示层级
        setTocDisplayLevel(level);
        
        // 保存用户偏好
        localStorage.setItem('toc-display-level', level);
      });
    });
  }
  
  function updateAllLevelButtonsActive(activeLevel) {
    // 更新顶部按钮
    const topButtons = document.querySelectorAll('.toc-level-btn');
    topButtons.forEach(btn => {
      btn.classList.remove('active');
      if (btn.getAttribute('data-level') === activeLevel) {
        btn.classList.add('active');
      }
    });
    
    // 更新浮动按钮
    const floatingButtons = document.querySelectorAll('.floating-level-btn');
    floatingButtons.forEach(btn => {
      btn.classList.remove('active');
      if (btn.getAttribute('data-level') === activeLevel) {
        btn.classList.add('active');
      }
    });
  }


