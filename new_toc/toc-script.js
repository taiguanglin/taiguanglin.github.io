(function(){
  const tree = document.getElementById('tree');

  // TOC Parser for client-side import functionality
  class ClientTOCParser {
    constructor() {
      // Roman numeral pattern
      this.romanPattern = /^((?:XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V)(?:\.(?:XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V))*)\.?\s*(.+)$/;
      // Arabic numeral pattern
      this.arabicPattern = /^(\d+(?:\.\d+)*)\.?\s+(.+)$/;
      // Old structure pattern (contains arrows)
      this.oldStructurePattern = /.*->.*/;
    }

    parseLines(lines) {
      const items = [];
      
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        
        const item = this.parseLine(line);
        if (item) {
          items.push(item);
        }
      }
      
      return this.buildHierarchy(items);
    }

    parseLine(line) {
      const cleanLine = line.trim();
      const isOldStructure = this.oldStructurePattern.test(cleanLine);
      
      // Try Roman numeral pattern
      const romanMatch = cleanLine.match(this.romanPattern);
      if (romanMatch) {
        const numberPath = romanMatch[1];
        const text = romanMatch[2];
        const level = numberPath.split('.').length;
        
        const formattedText = cleanLine.startsWith(numberPath + '.') ? 
          cleanLine : numberPath + '. ' + text;
        
        return {
          text: formattedText,
          level: level,
          isRoman: true,
          isArabic: false,
          isOldStructure: isOldStructure,
          children: [],
          numberPath: numberPath
        };
      }
      
      // Try Arabic numeral pattern
      const arabicMatch = cleanLine.match(this.arabicPattern);
      if (arabicMatch) {
        const numberPath = arabicMatch[1];
        const text = arabicMatch[2];
        const level = numberPath.split('.').length;
        
        return {
          text: cleanLine,
          level: level,
          isRoman: false,
          isArabic: true,
          isOldStructure: isOldStructure,
          children: [],
          numberPath: numberPath
        };
      }
      
      // Non-numeric structure
      return {
        text: cleanLine,
        level: 0,
        isRoman: false,
        isArabic: false,
        isOldStructure: isOldStructure,
        children: [],
        numberPath: ""
      };
    }

    buildHierarchy(items) {
      const rootItems = [];
      const stack = []; // Track Roman numeral parent items only
      
      for (const item of items) {
        if (item.isRoman) {
          // Only Roman numeral items participate in hierarchy building
          while (stack.length > 0 && stack[stack.length - 1].level >= item.level) {
            stack.pop();
          }
          
          if (stack.length > 0) {
            stack[stack.length - 1].children.push(item);
          } else {
            rootItems.push(item);
          }
          
          stack.push(item);
        } else {
          // All non-Roman items (Arabic numerals, old structure, non-numeric) are added under the most recent Roman item
          if (stack.length > 0) {
            stack[stack.length - 1].children.push(item);
          } else {
            // If no Roman parent exists, add as root item (should be rare)
            rootItems.push(item);
          }
        }
      }
      
      return rootItems;
    }
  }

  // Generate HTML from parsed items
  function generateTreeHTML(items, indentLevel = 1) {
    let html = '';
    
    for (const item of items) {
      const cssClasses = [];
      if (item.children.length > 0) {
        cssClasses.push('has-children');
      }
      if (item.isOldStructure) {
        cssClasses.push('old-structure');
      }
      if (!item.isRoman && !item.isArabic) {
        cssClasses.push('non-numeric');
      }
      if (item.isArabic) {
        cssClasses.push('arabic-numeric');
      }
      
      const classAttr = cssClasses.length > 0 ? ' class="' + cssClasses.join(' ') + '"' : '';
      const indent = '  '.repeat(indentLevel);
      
      if (item.children.length > 0) {
        html += indent + '<li' + classAttr + '><span class="label">' + escapeHtml(item.text) + '</span>\n';
        html += indent + '  <ul>\n';
        html += generateTreeHTML(item.children, indentLevel + 2);
        html += indent + '  </ul>\n';
        html += indent + '</li>\n';
      } else {
        html += indent + '<li' + classAttr + '><span class="label">' + escapeHtml(item.text) + '</span></li>\n';
      }
    }
    
    return html;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Rebuild tree with new content
  function rebuildTree(newHTML) {
    tree.innerHTML = newHTML;
    
    // Re-initialize tree functionality
    initializeTreeFunctionality();
  }

  // Initialize tree functionality
  function initializeTreeFunctionality() {
    // mark has-children and compute depth
    const allLis = tree.querySelectorAll('li');
    allLis.forEach(li=>{
      if(li.querySelector(':scope > ul')) li.classList.add('has-children');
      let depth = 1, p = li.parentElement;
      while (p && p !== tree) {
        if (p.tagName === 'UL') depth++;
        p = p.parentElement && p.parentElement.closest ? p.parentElement.closest('ul') : null;
      }
      li.dataset.depth = depth;
      
      // Get label text BEFORE any HTML modifications
      const label = li.querySelector('.label');
      const labelText = label?.textContent || '';
      
      // Mark structure types FIRST
      
      // Check for Roman numeral pattern
      const romanPattern = /^(XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V)(\.((XI{0,3}|IX|VI{0,3}|IV|I{1,3}|X|V)))*\.?\s*/;
      const isRoman = labelText.match(romanPattern);
      
      // Check for Arabic numeral pattern
      const arabicPattern = /^(\d+(?:\.\d+)*)\.?\s/;
      const isArabic = labelText.match(arabicPattern);
      
      // Check for old structure (containing arrows)
      const isOldStructure = labelText.match(/.*->.*/);
      
      // Apply appropriate classes
      if (isOldStructure) {
        li.classList.add('old-structure');
      }
      
      if (isArabic && !isOldStructure) {
        li.classList.add('arabic-numeric');
      } else if (!isRoman && !isArabic) {
        li.classList.add('non-roman');
      }
      
      // Add background to numbers in parentheses AFTER classification
      if (label) {
        const text = label.textContent;
        // Replace numbers in parentheses with styled spans
        const styledText = text.replace(/\((\d+)\)/g, '<span class="number-badge">($1)</span>');
        if (styledText !== text) {
          label.innerHTML = styledText;
        }
      }
    });
  }

  // Initial tree setup
  initializeTreeFunctionality();

  // toggle on li click (anywhere in the item)
  tree.addEventListener('click', e=>{
    // Find the closest li element
    let targetLi = e.target.closest('li');
    if (!targetLi) return;
    
    // Only handle if it's a has-children li
    if (!targetLi.classList.contains('has-children')) return;
    
    // Stop propagation to prevent nested clicks
    e.stopPropagation();
    
    targetLi.classList.toggle('open');
  });

  // keyboard (Enter/Space)
  tree.addEventListener('keydown', e=>{
    const label = e.target.closest('.label');
    if(!label) return;
    if(e.key === 'Enter' || e.key === ' '){
      e.preventDefault();
      const li = label.parentElement;
      if(li.classList.contains('has-children')) li.classList.toggle('open');
    }
  });

  // expand helpers
  function expandToLevel(n){
    tree.querySelectorAll('li.has-children').forEach(li=>{
      const depth = Number(li.dataset.depth);
      li.classList.toggle('open', depth < n);
    });
  }
  function expandAll(){
    tree.querySelectorAll('li.has-children').forEach(li=>li.classList.add('open'));
  }
  function collapseAll(){
    tree.querySelectorAll('li.has-children').forEach(li=>li.classList.remove('open'));
  }

  // control buttons
  document.querySelectorAll('.controls [data-level]').forEach(btn=>{
    btn.addEventListener('click',()=>expandToLevel(Number(btn.dataset.level)));
  });
  document.getElementById('expandAll').addEventListener('click', expandAll);
  document.getElementById('collapseAll').addEventListener('click', collapseAll);

  // toggle old structure functionality
  let oldStructureHidden = false;
  
  function toggleOldStructure() {
    const toggleBtn = document.getElementById('toggleNumbers');
    const body = document.body;
    
    if (!oldStructureHidden) {
      // Hide old structure
      body.classList.add('hide-old-structure');
      toggleBtn.textContent = '切换旧目录显示';
      toggleBtn.classList.add('active');
      oldStructureHidden = true;
    } else {
      // Show old structure
      body.classList.remove('hide-old-structure');
      toggleBtn.textContent = '切换旧目录显示';
      toggleBtn.classList.remove('active');
      oldStructureHidden = false;
    }
  }
  
  document.getElementById('toggleNumbers').addEventListener('click', toggleOldStructure);

  // import functionality
  const fileInput = document.getElementById('fileInput');
  const importBtn = document.getElementById('importToc');
  
  importBtn.addEventListener('click', () => {
    fileInput.click();
  });
  
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target.result;
        const lines = content.split('\n');
        
        const parser = new ClientTOCParser();
        const parsedItems = parser.parseLines(lines);
        
        const newHTML = generateTreeHTML(parsedItems);
        rebuildTree(newHTML);
        
        // Show success message
        showMessage('文件汇入成功！', 'success');
        
      } catch (error) {
        console.error('Import error:', error);
        showMessage('文件汇入失败：' + error.message, 'error');
      }
    };
    
    reader.readAsText(file, 'utf-8');
    
    // Reset file input
    fileInput.value = '';
  });

  // export functionality
  function exportToc() {
    const visibleItems = [];
    
    function collectVisibleItems(element, indent = '') {
      const items = element.querySelectorAll(':scope > li');
      items.forEach(item => {
        const label = item.querySelector('.label');
        if (!label) return;
        
        // Check if item is visible (not hidden by CSS)
        const computedStyle = window.getComputedStyle(item);
        if (computedStyle.display === 'none') return;
        
        // Add current item
        visibleItems.push(indent + label.textContent.trim());
        
        // If item is expanded, collect its children
        if (item.classList.contains('open')) {
          const childUl = item.querySelector(':scope > ul');
          if (childUl) {
            collectVisibleItems(childUl, indent + '  ');
          }
        }
      });
    }
    
    // Collect all visible items starting from the tree root
    collectVisibleItems(tree);
    
    // Create text content
    const textContent = visibleItems.join('\n');
    
    // Create and download file
    const blob = new Blob([textContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '目录结构.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
  
  document.getElementById('exportToc').addEventListener('click', exportToc);

  // Message display function
  function showMessage(message, type = 'info') {
    // Remove existing message
    const existingMessage = document.querySelector('.message-toast');
    if (existingMessage) {
      existingMessage.remove();
    }
    
    // Create message element
    const messageEl = document.createElement('div');
    messageEl.className = `message-toast message-${type}`;
    messageEl.textContent = message;
    
    // Style the message
    messageEl.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 20px;
      border-radius: 6px;
      color: white;
      font-weight: 500;
      z-index: 1000;
      animation: slideIn 0.3s ease-out;
    `;
    
    if (type === 'success') {
      messageEl.style.backgroundColor = '#10b981';
    } else if (type === 'error') {
      messageEl.style.backgroundColor = '#ef4444';
    } else {
      messageEl.style.backgroundColor = '#3b82f6';
    }
    
    // Add animation styles
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
    `;
    document.head.appendChild(style);
    
    document.body.appendChild(messageEl);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
      messageEl.remove();
    }, 3000);
  }

  // 浮动控制栏功能
  const floatingControls = document.getElementById('floatingControls');
  const originalControls = document.querySelector('.controls');
  let currentActiveLevel = null;
  let isFloatingVisible = false;
  
  // 节流函数，优化滚动性能
  function throttle(func, limit) {
    let inThrottle;
    return function() {
      const args = arguments;
      const context = this;
      if (!inThrottle) {
        func.apply(context, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    }
  }
  
  // 检查原控制栏是否可用（用户能看到并点击）
  function isControlsVisible() {
    if (!originalControls) return true;
    const rect = originalControls.getBoundingClientRect();
    
    // 更精确的判断，特别针对快速滚动优化
    const windowHeight = window.innerHeight;
    const controlsHeight = rect.height;
    
    // 控制栏必须有足够的可见区域才认为是可用的
    // 1. 控制栏顶部在视窗内（允许小幅超出）
    // 2. 控制栏底部在视窗内有足够空间
    const topVisible = rect.top >= -5 && rect.top < windowHeight;
    const hasUsableHeight = rect.bottom > Math.max(controlsHeight * 0.6, 25);
    
    // 额外检查：如果页面滚动位置很接近顶部，强制认为控制栏可见
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const nearTop = scrollTop < 100; // 距离顶部100px内
    
    return (topVisible && hasUsableHeight) || nearTop;
  }
  
  // 显示/隐藏浮动控制栏
  function toggleFloatingControls() {
    const controlsVisible = isControlsVisible();
    const shouldShow = !controlsVisible;
    
    // 添加防抖，避免频繁切换
    if (shouldShow && !isFloatingVisible) {
      floatingControls.classList.add('visible');
      isFloatingVisible = true;
    } else if (!shouldShow && isFloatingVisible) {
      floatingControls.classList.remove('visible');
      isFloatingVisible = false;
    }
  }
  
  // 同步按钮状态
  function syncButtonStates() {
    // 同步层级按钮状态
    const originalLevelBtns = originalControls.querySelectorAll('[data-level]');
    const floatingLevelBtns = floatingControls.querySelectorAll('[data-level]');
    
    originalLevelBtns.forEach((btn, index) => {
      const floatingBtn = floatingLevelBtns[index];
      if (btn.classList.contains('active')) {
        floatingBtn.classList.add('active');
      } else {
        floatingBtn.classList.remove('active');
      }
    });
    
    // 同步切换按钮状态
    const originalToggle = document.getElementById('toggleNumbers');
    const floatingToggle = document.getElementById('floatingToggleNumbers');
    if (originalToggle.classList.contains('active')) {
      floatingToggle.classList.add('active');
    } else {
      floatingToggle.classList.remove('active');
    }
  }
  
  // 设置层级按钮的激活状态
  function setActiveLevelButton(level) {
    // 清除所有激活状态
    document.querySelectorAll('[data-level]').forEach(btn => {
      btn.classList.remove('active');
    });
    
    // 设置新的激活状态
    if (level) {
      document.querySelectorAll(`[data-level="${level}"]`).forEach(btn => {
        btn.classList.add('active');
      });
      currentActiveLevel = level;
    } else {
      currentActiveLevel = null;
    }
  }
  
  // 绑定浮动控制栏事件
  function bindFloatingControlEvents() {
    // 层级按钮事件
    floatingControls.querySelectorAll('[data-level]').forEach(btn => {
      btn.addEventListener('click', () => {
        const level = Number(btn.dataset.level);
        expandToLevel(level);
        setActiveLevelButton(level);
      });
    });
    
    // 展开所有按钮
    document.getElementById('floatingExpandAll').addEventListener('click', () => {
      expandAll();
      setActiveLevelButton(null); // 清除层级选择状态
    });
    
    // 收起所有按钮
    document.getElementById('floatingCollapseAll').addEventListener('click', () => {
      collapseAll();
      setActiveLevelButton(null); // 清除层级选择状态
    });
    
    // 切换旧目录显示按钮
    document.getElementById('floatingToggleNumbers').addEventListener('click', () => {
      // 触发原按钮的点击事件以保持功能一致
      document.getElementById('toggleNumbers').click();
      // 同步状态
      setTimeout(syncButtonStates, 50);
    });
  }
  
  // 修改原有的层级按钮事件，添加状态管理
  document.querySelectorAll('.controls [data-level]').forEach(btn => {
    btn.addEventListener('click', () => {
      const level = Number(btn.dataset.level);
      setActiveLevelButton(level);
    });
  });
  
  // 修改原有的展开/收起按钮，清除层级选择状态
  document.getElementById('expandAll').addEventListener('click', () => {
    setActiveLevelButton(null);
  });
  
  document.getElementById('collapseAll').addEventListener('click', () => {
    setActiveLevelButton(null);
  });
  
  // 滚动结束检测
  let scrollEndTimer = null;
  
  // 立即响应的滚动处理（减少节流延迟）
  const immediateScrollHandler = throttle(() => {
    // 使用 requestAnimationFrame 确保在正确的渲染时机检测
    requestAnimationFrame(() => {
      toggleFloatingControls();
      syncButtonStates();
    });
  }, 50); // 减少到50ms以提高响应速度
  
  // 滚动结束后的最终检测
  function handleScrollEnd() {
    clearTimeout(scrollEndTimer);
    scrollEndTimer = setTimeout(() => {
      // 滚动结束后再次确认状态，确保准确性
      requestAnimationFrame(() => {
        toggleFloatingControls();
        syncButtonStates();
      });
    }, 150); // 滚动结束150ms后最终检测
  }
  
  // 滚动事件监听
  window.addEventListener('scroll', () => {
    immediateScrollHandler();
    handleScrollEnd();
  });
  
  window.addEventListener('resize', () => {
    immediateScrollHandler();
    handleScrollEnd();
  });
  
  // 初始化浮动控制栏
  bindFloatingControlEvents();
  
  // 页面加载完成后检查初始状态
  setTimeout(() => {
    toggleFloatingControls();
    syncButtonStates();
  }, 100);

  // default state: all collapsed (no auto-expansion)
  // expandToLevel(1);
})();