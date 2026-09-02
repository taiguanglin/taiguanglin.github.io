  // ========== 目录折叠控制功能 ==========
  
  // 初始化目录折叠控制（首页和章节页面都需要）
  initTocCollapseControl();
  initFloatingLevelControls();
  
  function initTocCollapseControl() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    // 检测实际的目录层级并隐藏不必要的按钮
    const maxLevel = detectAndHideLevelButtons(tocContainer);
    
    // 根據頁面類型設定不同的默認值
    const isChapterPage = document.getElementById('chapter-toc') !== null;
    const defaultLevel = isChapterPage ? '3' : '2'; // 章節頁面默認第3層，首頁默認第2層
    
    // 获取用户保存的偏好，使用對應的默認值
    const rawSavedLevel = localStorage.getItem('toc-display-level') || defaultLevel;
    
    // 智能選擇可用的層級
    const validLevel = selectValidLevel(rawSavedLevel, maxLevel, defaultLevel, tocContainer);
    
    // 初始化按钮状态
    updateLevelButtonsActive(validLevel);
    
    // 根据智能选择的层级设置初始显示
    setTocDisplayLevel(validLevel);
    
    // 绑定层级切换按钮事件
    bindLevelControlEvents();
    
    // 为有展开图标的目录项添加 toc-expandable 类
    initializeTocExpandableItems();
    
    // 绑定展开/折叠图标事件
    bindExpandCollapseEvents();
    
    // 绑定全部展开/折叠按钮事件
    bindExpandAllEvents();
  }
  
  // 智能選擇可用的層級
  function selectValidLevel(savedLevel, maxLevel, defaultLevel, tocContainer) {
    const savedLevelNum = parseInt(savedLevel);
    const maxLevelNum = parseInt(maxLevel);
    const defaultLevelNum = parseInt(defaultLevel);
    
    // 檢查當前頁面實際存在的層級（有內容的層級）
    const availableLevels = [];
    
    // 檢查每個層級是否有實際的目錄項目
    for (let level = 1; level <= maxLevelNum; level++) {
      const itemsAtLevel = tocContainer.querySelectorAll(`.toc-item[data-level="${level}"]`);
      if (itemsAtLevel.length > 0) {
        availableLevels.push(level);
      }
    }
    
    // 也檢查是否有對應的層級按鈕可見
    const visibleButtons = [];
    const allLevelButtons = document.querySelectorAll('.toc-level-btn, .floating-level-btn');
    allLevelButtons.forEach(btn => {
      const level = parseInt(btn.getAttribute('data-level'));
      if (btn.style.display !== 'none' && !btn.hasAttribute('data-hidden-level')) {
        if (!visibleButtons.includes(level)) {
          visibleButtons.push(level);
        }
      }
    });
    
    // 取交集：既有內容又有按鈕的層級
    const validLevels = availableLevels.filter(level => visibleButtons.includes(level));
    
    console.log('有內容的層級:', availableLevels, '可見按鈕層級:', visibleButtons, '有效層級:', validLevels);
    console.log('保存的層級:', savedLevelNum, '最大層級:', maxLevelNum);
    
    // 如果保存的層級在有效層級中，直接使用
    if (validLevels.includes(savedLevelNum)) {
      console.log('使用保存的層級:', savedLevelNum);
      return savedLevel;
    }
    
    // 如果保存的層級不可用，選擇最接近的有效層級
    if (validLevels.length === 0) {
      console.warn('沒有找到有效層級，使用默認值');
      return defaultLevel;
    }
    
    // 找到最接近保存層級的有效層級
    let selectedLevel = validLevels[0];
    let minDistance = Math.abs(validLevels[0] - savedLevelNum);
    
    for (const level of validLevels) {
      const distance = Math.abs(level - savedLevelNum);
      if (distance < minDistance) {
        minDistance = distance;
        selectedLevel = level;
      }
    }
    
    console.log('智能選擇的層級:', selectedLevel, '原因: 最接近保存的層級', savedLevelNum);
    return selectedLevel.toString();
  }

  // 检测目录实际层级并隐藏不必要的层级按钮
  function detectAndHideLevelButtons(tocContainer) {
    let maxLevel = 1; // 默认至少有第1层
    
    // 检测所有目录项的层级
    const tocItems = tocContainer.querySelectorAll('.toc-item[data-level]');
    tocItems.forEach(item => {
      const level = parseInt(item.getAttribute('data-level'));
      if (level > maxLevel) {
        maxLevel = level;
      }
    });
    
    // 也检查传统的嵌套结构（ul > li）
    const nestedItems = tocContainer.querySelectorAll('ul li');
    if (nestedItems.length > 0) {
      // 计算嵌套深度
      nestedItems.forEach(item => {
        let depth = 1;
        let parent = item.parentElement;
        while (parent && parent !== tocContainer) {
          if (parent.tagName === 'UL') {
            depth++;
          }
          parent = parent.parentElement;
        }
        if (depth > maxLevel) {
          maxLevel = depth;
        }
      });
    }
    
    console.log('检测到的最大目录层级:', maxLevel);
    
    // 隐藏超出实际层级的按钮
    const allLevelButtons = document.querySelectorAll('.toc-level-btn, .floating-level-btn');
    allLevelButtons.forEach(btn => {
      const buttonLevel = parseInt(btn.getAttribute('data-level'));
      if (buttonLevel > maxLevel) {
        btn.style.display = 'none';
        // 同时为其父容器添加一个属性，表示这个按钮被隐藏了
        btn.setAttribute('data-hidden-level', 'true');
      } else {
        btn.style.display = '';
        btn.removeAttribute('data-hidden-level');
      }
    });
    
    // 返回检测到的最大层级，供其他函数使用
    return maxLevel;
  }
  
  function bindLevelControlEvents() {
    const levelButtons = document.querySelectorAll('.toc-level-btn');
    levelButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const level = this.getAttribute('data-level');
        
        // 更新所有按钮状态（包括浮动按钮）
        updateAllLevelButtonsActive(level);
        
        // 设置显示层级
        setTocDisplayLevel(level);
        
        // 保存用户偏好
        localStorage.setItem('toc-display-level', level);
      });
    });
  }
  
  function updateLevelButtonsActive(activeLevel) {
    // 保持向后兼容，但现在使用统一的更新函数
    updateAllLevelButtonsActive(activeLevel);
  }
  
  function setTocDisplayLevel(level) {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    const allItems = tocContainer.querySelectorAll('.toc-item');
    const targetLevel = parseInt(level);
    
    // 最深的「顯示層級」（按鈕只到這一層；更深層如第 6 層不出現在按鈕中）。
    // 當選到最深顯示層級時，一併顯示更深一層的子項（例如坐禅2 的羅馬數字 h6，
    // 只有這處有第 6 層，不值得獨立成一個「顯示層級」按鈕）。
    let deepestButtonLevel = 0;
    document.querySelectorAll('.toc-level-btn, .floating-level-btn').forEach(btn => {
      const lv = parseInt(btn.getAttribute('data-level'));
      if (!isNaN(lv) && lv > deepestButtonLevel) deepestButtonLevel = lv;
    });
    const showDeeper = deepestButtonLevel > 0 && targetLevel >= deepestButtonLevel;
    
    // 清除所有手動標記，讓層級控制重新接管
    allItems.forEach(item => {
      item.removeAttribute('data-user-toggled');
      item.removeAttribute('data-manually-shown');
    });
    
    allItems.forEach(item => {
      const itemLevel = parseInt(item.getAttribute('data-level'));
      
      // 根據層級控制顯示/隱藏；選到最深層時連更深層（第 6 層）一起顯示
      if (itemLevel <= targetLevel || (showDeeper && itemLevel > targetLevel)) {
        item.classList.remove('hidden');
      } else {
        item.classList.add('hidden');
      }
      
      // 重新設置圖標狀態
      const expandIcon = item.querySelector('.toc-expand-icon');
      if (expandIcon) {
        if (itemLevel < targetLevel) {
          // 小於目標層級的項目自動展開
          expandIcon.classList.remove('collapsed');
          expandIcon.textContent = '▼';
        } else if (itemLevel === targetLevel) {
          // 等於目標層級的項目設為折疊狀態
          expandIcon.classList.add('collapsed');
          expandIcon.textContent = '▶';
        }
      }
    });
  }
  
  // 同步图标状态与实际展开状态
  function syncIconStates() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    const expandableItems = tocContainer.querySelectorAll('.toc-item.toc-expandable');
    expandableItems.forEach(item => {
      const icon = item.querySelector('.toc-expand-icon');
      if (icon) {
        const actuallyExpanded = hasVisibleDirectChildren(item);
        
        if (actuallyExpanded) {
          icon.classList.remove('collapsed');
          icon.textContent = '▼';
        } else {
          icon.classList.add('collapsed');
          icon.textContent = '▶';
        }
      }
    });
  }

  // 初始化可展开的目录项
  function initializeTocExpandableItems() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    // 为所有有展开图标的目录项添加 toc-expandable 类
    const itemsWithIcons = tocContainer.querySelectorAll('.toc-item .toc-expand-icon');
    itemsWithIcons.forEach(icon => {
      const tocItem = icon.closest('.toc-item');
      if (tocItem) {
        tocItem.classList.add('toc-expandable');
      }
    });
    
    // 同步图标状态
    syncIconStates();
  }

  // 检查一个目录项是否有可见的直接子项
  function hasVisibleDirectChildren(parentItem) {
    const parentLevel = parseInt(parentItem.getAttribute('data-level'));
    
    // 首先检查嵌套结构（首页TOC）：查找直接的ul子元素
    const nestedUl = parentItem.querySelector(':scope > ul');
    if (nestedUl) {
      const directChildren = nestedUl.querySelectorAll(':scope > .toc-item');
      for (let child of directChildren) {
        if (!child.classList.contains('hidden')) {
          return true;
        }
      }
      return false;
    }
    
    // 然后检查扁平结构（章节页TOC）：查找兄弟元素
    let nextSibling = parentItem.nextElementSibling;
    while (nextSibling && nextSibling.classList.contains('toc-item')) {
      const siblingLevel = parseInt(nextSibling.getAttribute('data-level'));
      
      if (siblingLevel <= parentLevel) {
        // 遇到同级或更高级别的项目，停止
        break;
      }
      
      if (siblingLevel === parentLevel + 1) {
        // 这是直接子项，检查是否可见
        if (!nextSibling.classList.contains('hidden')) {
          return true;
        }
      }
      
      nextSibling = nextSibling.nextElementSibling;
    }
    
    return false;
  }

  function bindExpandCollapseEvents() {
    const tocContainer = document.getElementById('main-toc') || document.getElementById('chapter-toc');
    if (!tocContainer) return;
    
    // 使用事件委托处理展开/折叠和跳转
    tocContainer.addEventListener('click', function(e) {
      // 检查是否直接点击了链接文字
      if (e.target.tagName === 'A') {
        // 直接点击链接文字，允许默认行为（页面跳转）
        return;
      }
      
      // 查找最近的目录项
      const tocItem = e.target.closest('.toc-item');
      if (!tocItem) return;
      
      // 检查是否点击了可展开的目录项（有三角形图标的）
      const expandableItem = tocItem.classList.contains('toc-expandable') ? tocItem : null;
      if (expandableItem) {
        e.preventDefault();
        e.stopPropagation();
        
        const icon = expandableItem.querySelector('.toc-expand-icon');
        if (icon) {
          // 检查实际的展开状态：查看是否有可见的直接子项
          const actuallyExpanded = hasVisibleDirectChildren(expandableItem);
          
          // 标记这个项目已经被用户手动操作
          expandableItem.setAttribute('data-user-toggled', 'true');
          
          if (actuallyExpanded) {
            // 当前已展开，执行折叠
            collapseTocItem(expandableItem);
            icon.classList.add('collapsed');
            icon.textContent = '▶';
          } else {
            // 当前已折叠，执行展开
            expandTocItem(expandableItem);
            icon.classList.remove('collapsed');
            icon.textContent = '▼';
          }
        }
      } else {
        // 这是没有展开图标的目录项（叶子节点），处理整行点击跳转
        const link = tocItem.querySelector('a');
        if (link && !e.target.closest('a')) {
          // 点击的是目录项但不是链接本身，触发链接跳转
          e.preventDefault();
          e.stopPropagation();
          
          // 模拟点击链接
          link.click();
        }
      }
    });
  }
  
  function expandTocItem(parentItem) {
    const parentLevel = parseInt(parentItem.getAttribute('data-level'));
    const parentChapter = parentItem.getAttribute('data-chapter');
    
    // 首先检查嵌套结构（首页TOC）
    const nestedUl = parentItem.querySelector(':scope > ul');
    if (nestedUl) {
      const directChildren = nestedUl.querySelectorAll(':scope > .toc-item');
      directChildren.forEach(child => {
        const childLevel = parseInt(child.getAttribute('data-level'));
        const childChapter = child.getAttribute('data-chapter');
        
        // 只展開同一章節且是直接子項的項目
        if (childLevel === parentLevel + 1 && childChapter === parentChapter) {
          child.classList.remove('hidden');
          child.setAttribute('data-manually-shown', 'true');
        }
      });
      return;
    }
    
    // 处理扁平结构（章节页TOC）
    let nextSibling = parentItem.nextElementSibling;
    while (nextSibling && nextSibling.classList.contains('toc-item')) {
      const siblingLevel = parseInt(nextSibling.getAttribute('data-level'));
      const siblingChapter = nextSibling.getAttribute('data-chapter');
      
      if (siblingLevel <= parentLevel) {
        // 遇到同级或更高级别的项目，停止
        break;
      }
      
      // 只處理同一章節的子項目
      if (siblingLevel === parentLevel + 1 && siblingChapter === parentChapter) {
        // 这是直接子项，显示它
        nextSibling.classList.remove('hidden');
        // 添加标记，表示这是用户手动展开的
        nextSibling.setAttribute('data-manually-shown', 'true');
      }
      
      nextSibling = nextSibling.nextElementSibling;
    }
  }
  
  function collapseTocItem(parentItem) {
    const parentLevel = parseInt(parentItem.getAttribute('data-level'));
    const parentChapter = parentItem.getAttribute('data-chapter');
    
    // 首先检查嵌套结构（首页TOC）
    const nestedUl = parentItem.querySelector(':scope > ul');
    if (nestedUl) {
      const allChildren = nestedUl.querySelectorAll('.toc-item');
      allChildren.forEach(child => {
        const childLevel = parseInt(child.getAttribute('data-level'));
        const childChapter = child.getAttribute('data-chapter');
        
        // 只收縮同一章節且層級更深的項目
        if (childLevel > parentLevel && childChapter === parentChapter) {
          child.classList.add('hidden');
          child.removeAttribute('data-manually-shown');
          const childIcon = child.querySelector('.toc-expand-icon');
          if (childIcon) {
            childIcon.classList.add('collapsed');
            childIcon.textContent = '▶';
          }
        }
      });
      return;
    }
    
    // 处理扁平结构（章节页TOC）
    let nextSibling = parentItem.nextElementSibling;
    while (nextSibling && nextSibling.classList.contains('toc-item')) {
      const siblingLevel = parseInt(nextSibling.getAttribute('data-level'));
      const siblingChapter = nextSibling.getAttribute('data-chapter');
      
      if (siblingLevel <= parentLevel) {
        // 遇到同级或更高级别的项目，停止
        break;
      }
      
      // 只處理同一章節的子項目
      if (siblingChapter === parentChapter) {
        // 这是子项，隐藏它，并同时折叠其展开状态
        nextSibling.classList.add('hidden');
        // 清除手动展开标记
        nextSibling.removeAttribute('data-manually-shown');
        const childIcon = nextSibling.querySelector('.toc-expand-icon');
        if (childIcon) {
          childIcon.classList.add('collapsed');
          childIcon.textContent = '▶';
        }
      }
      
      nextSibling = nextSibling.nextElementSibling;
    }
  }
  
  function bindExpandAllEvents() {
    // 移除了全部展开/折叠按钮，因为现在只有3个层级按钮
    // 功能已经整合到层级按钮中
  }
  
