(function(){
  const tree = document.getElementById('tree');

  // TOC Parser for client-side import functionality
  class ClientTOCParser {
    constructor() {
      // Roman numeral pattern - fixed order to prevent XIV being parsed as XI.V
      this.romanPattern = /^((?:XIII|XIV|XII|XV|VIII|VII|VI|IX|IV|III|II|XI|X|V|I)(?:\.(?:XIII|XIV|XII|XV|VIII|VII|VI|IX|IV|III|II|XI|X|V|I))*)\.?\s*(.+)$/;
      // Arabic numeral pattern
      this.arabicPattern = /^(\d+(?:\.\d+)*)\.?\s+(.+)$/;
      // Old structure pattern (contains arrows)
      this.oldStructurePattern = /.*->.*/;
    }

    extractCountFromText(text) {
      // Extract number from parentheses (could have symbols like 📋 after)
      const countPattern = /\((\d+)\)/;
      const match = text.match(countPattern);
      return match ? parseInt(match[1]) : null;
    }

    textWithoutCount(text) {
      // Remove count format (number) that might have other symbols after
      const countPattern = /\s*\(\d+\)/;
      return text.replace(countPattern, '').trim();
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
      
      const hierarchy = this.buildHierarchy(items);
      
      // Calculate counts for all items
      this.calculateCounts(hierarchy);
      
      return hierarchy;
    }

    parseLine(line) {
      const cleanLine = line.trim();
      const isOldStructure = this.oldStructurePattern.test(cleanLine);
      
      // Extract original count from text
      const originalCount = this.extractCountFromText(cleanLine);
      
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
          numberPath: numberPath,
          originalCount: originalCount,
          calculatedCount: null
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
          numberPath: numberPath,
          originalCount: originalCount,
          calculatedCount: null
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
        numberPath: "",
        originalCount: originalCount,
        calculatedCount: null
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

    calculateCounts(items) {
      // Calculate counts for all items (bottom-up)
      for (const item of items) {
        this.calculateItemCount(item);
      }
    }

    calculateItemCount(item) {
      // Recursive count calculation for a single item
      if (this.isLeaf(item)) {
        // Leaf node: use original count
        return item.originalCount || 0;
      } else {
        // Non-leaf node: calculate sum of all children first, then set calculated count
        let totalCount = 0;
        for (const child of item.children) {
          const childCount = this.calculateItemCount(child);
          totalCount += childCount;
        }
        
        // Set the calculated count
        item.calculatedCount = totalCount;
        return totalCount;
      }
    }

    isLeaf(item) {
      // Check if item is a leaf node (no children)
      return item.children.length === 0;
    }

    getDisplayCount(item) {
      // Get the count value for display
      if (this.isLeaf(item)) {
        // Leaf node: use original count
        return item.originalCount;
      } else {
        // Non-leaf node: use calculated count
        return item.calculatedCount;
      }
    }

    getDisplayText(item) {
      // Get display text with recalculated count
      const baseText = this.textWithoutCount(item.text);
      const count = this.getDisplayCount(item);
      
      if (this.isLeaf(item)) {
        // Leaf node: only show count if it exists and > 0
        if (count != null && count > 0) {
          return `${baseText} (${count})`;
        }
      } else {
        // Non-leaf node: show calculated count, including 0
        if (count != null) {
          return `${baseText} (${count})`;
        }
      }
      
      return baseText;
    }
  }

  // Generate HTML from parsed items
  function generateTreeHTML(items, indentLevel = 1, parser = null) {
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
      
      // Use display text with recalculated counts if parser is available
      const displayText = parser ? parser.getDisplayText(item) : item.text;
      
      if (item.children.length > 0) {
        html += indent + '<li' + classAttr + '><span class="label">' + escapeHtml(displayText) + '</span>\n';
        html += indent + '  <ul>\n';
        html += generateTreeHTML(item.children, indentLevel + 2, parser);
        html += indent + '  </ul>\n';
        html += indent + '</li>\n';
      } else {
        html += indent + '<li' + classAttr + '><span class="label">' + escapeHtml(displayText) + '</span></li>\n';
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
    
    // 重新初始化展開按鈕
    updateExpandChildrenButtons();
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
        
        // Add copy button for non-Roman numeral items
        const shouldAddCopyBtn = !isRoman && (isArabic || isOldStructure || (!isArabic && !isOldStructure));
        
        if (shouldAddCopyBtn) {
          // Restructure label content with copy button
          label.innerHTML = `
            <span class="label-text">${styledText}</span>
            <span class="label-actions">
              <button class="copy-btn" title="复制此行">📋</button>
            </span>
          `;
        } else if (styledText !== text) {
          label.innerHTML = styledText;
        }
      }
    });
  }

  // Initial tree setup
  initializeTreeFunctionality();
  
  // 初始化展開按鈕
  updateExpandChildrenButtons();
  
  // 复制功能
  function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      // 现代浏览器的 Clipboard API
      return navigator.clipboard.writeText(text).then(() => {
        showMessage('已复制到剪贴板', 'success');
      }).catch(err => {
        console.error('复制失败:', err);
        fallbackCopyTextToClipboard(text);
      });
    } else {
      // 降级方案
      fallbackCopyTextToClipboard(text);
    }
  }
  
  function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
      const successful = document.execCommand('copy');
      if (successful) {
        showMessage('已复制到剪贴板', 'success');
      } else {
        showMessage('复制失败，请手动复制', 'error');
      }
    } catch (err) {
      console.error('降级复制失败:', err);
      showMessage('复制失败，请手动复制', 'error');
    }
    
    document.body.removeChild(textArea);
  }
  
  // 绑定复制按钮事件
  function bindCopyEvents() {
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('copy-btn')) {
        e.preventDefault();
        e.stopPropagation();
        
        // 获取要复制的文本
        const labelText = e.target.closest('.label').querySelector('.label-text');
        if (labelText) {
          const textToCopy = labelText.textContent.trim();
          copyToClipboard(textToCopy);
        }
      }
    });
  }
  
  // 初始化复制功能
  bindCopyEvents();

  // 檢測子節點是否還有未展開的項目（深度檢查）
  function hasCollapsedChildren(li) {
    const childUl = li.querySelector(':scope > ul');
    if (!childUl) return false;
    
    // 檢查所有子孫節點中是否有 has-children 但沒有 open 的項目
    const allDescendants = childUl.querySelectorAll('li.has-children');
    return Array.from(allDescendants).some(child => !child.classList.contains('open'));
  }

  // 獲取節點的展開狀態
  function getExpansionState(li) {
    if (!li.classList.contains('has-children')) {
      return 'no-children'; // 沒有子節點
    }
    
    if (!li.classList.contains('open')) {
      return 'collapsed'; // 未展開
    }
    
    // 已展開，檢查是否還有未展開的子項
    if (hasCollapsedChildren(li)) {
      return 'partially-expanded'; // 部分展開
    } else {
      return 'fully-expanded'; // 完全展開
    }
  }

  // 展開指定節點下的所有子樹
  function expandAllChildren(li) {
    // 先確保父節點本身是展開的
    if (!li.classList.contains('open')) {
      li.classList.add('open');
    }
    
    const childUl = li.querySelector(':scope > ul');
    if (!childUl) return;
    
    // 遞歸展開所有子樹
    function expandRecursively(ul) {
      const directChildren = ul.querySelectorAll(':scope > li.has-children');
      directChildren.forEach(child => {
        // 展開該節點
        child.classList.add('open');
        
        // 遞歸展開該子節點的子樹
        const nestedUl = child.querySelector(':scope > ul');
        if (nestedUl) {
          expandRecursively(nestedUl);
        }
      });
    }
    
    expandRecursively(childUl);
    
    // 強制瀏覽器重排重繪
    tree.offsetHeight;
    
    // 使用 requestAnimationFrame 確保DOM更新後再更新按鈕狀態
    requestAnimationFrame(() => {
      updateExpandChildrenButtons();
    });
  }

  // 更新展開子樹按鈕的顯示狀態
  function updateExpandChildrenButtons() {
    const allItems = tree.querySelectorAll('li.has-children');
    
    allItems.forEach(li => {
      const label = li.querySelector(':scope > .label');
      if (!label) return;
      
      // 移除舊的按鈕和狀態類
      const existingBtn = label.querySelector('.expand-children-btn');
      if (existingBtn) {
        existingBtn.remove();
      }
      
      // 移除舊的狀態類
      li.classList.remove('expansion-collapsed', 'expansion-partially', 'expansion-fully');
      
      // 獲取當前展開狀態
      const state = getExpansionState(li);
      
      // 根據狀態添加CSS類和按鈕
      if (state === 'collapsed') {
        li.classList.add('expansion-collapsed');
        // 創建按鈕（hover時顯示）
        createExpandButton(li, label);
      } else if (state === 'partially-expanded') {
        li.classList.add('expansion-partially');
        // 創建按鈕（恆常顯示）
        createExpandButton(li, label);
      } else if (state === 'fully-expanded') {
        li.classList.add('expansion-fully');
        // 不創建按鈕
      }
    });
  }
  
  // 創建展開按鈕
  function createExpandButton(li, label) {
    const expandBtn = document.createElement('span');
    expandBtn.className = 'expand-children-btn';
    expandBtn.textContent = '⏬';
    expandBtn.title = '展开所有子项';
    
    // 添加點擊事件
    expandBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      expandAllChildren(li);
    });
    
    // 添加到label末尾
    label.appendChild(expandBtn);
  }

  // toggle on li click (anywhere in the item)
  tree.addEventListener('click', e=>{
    // 排除按鈕點擊
    if (e.target.classList.contains('expand-children-btn') || 
        e.target.classList.contains('copy-btn')) {
      return;
    }
    
    // Find the closest li element
    let targetLi = e.target.closest('li');
    if (!targetLi) return;
    
    // Only handle if it's a has-children li
    if (!targetLi.classList.contains('has-children')) return;
    
    // Stop propagation to prevent nested clicks
    e.stopPropagation();
    
    targetLi.classList.toggle('open');
    
    // 更新展開按鈕狀態
    updateExpandChildrenButtons();
  });

  // keyboard (Enter/Space)
  tree.addEventListener('keydown', e=>{
    const label = e.target.closest('.label');
    if(!label) return;
    if(e.key === 'Enter' || e.key === ' '){
      e.preventDefault();
      const li = label.parentElement;
      if(li.classList.contains('has-children')) {
        li.classList.toggle('open');
        // 更新展開按鈕狀態
        updateExpandChildrenButtons();
      }
    }
  });

  // expand helpers
  function expandToLevel(n){
    tree.querySelectorAll('li.has-children').forEach(li=>{
      const depth = Number(li.dataset.depth);
      li.classList.toggle('open', depth < n);
    });
    // 更新展開按鈕狀態
    updateExpandChildrenButtons();
  }
  function expandAll(){
    tree.querySelectorAll('li.has-children').forEach(li=>li.classList.add('open'));
    // 更新展開按鈕狀態
    updateExpandChildrenButtons();
  }
  function collapseAll(){
    tree.querySelectorAll('li.has-children').forEach(li=>li.classList.remove('open'));
    // 更新展開按鈕狀態
    updateExpandChildrenButtons();
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
      toggleBtn.textContent = '隐藏绿色字原始目录';
      toggleBtn.classList.add('active');
      oldStructureHidden = true;
    } else {
      // Show old structure
      body.classList.remove('hide-old-structure');
      toggleBtn.textContent = '隐藏绿色字原始目录';
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
        
        const newHTML = generateTreeHTML(parsedItems, 1, parser);
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

  // export functionality - exports ALL levels regardless of display state
  function exportToc() {
    const allItems = [];
    
    function collectAllItems(element, indent = '') {
      const items = element.querySelectorAll(':scope > li');
      items.forEach(item => {
        const label = item.querySelector('.label');
        if (!label) return;
        
        // Add current item (remove UI control symbols and extra whitespace)
        let text = label.textContent.trim();
        // Remove all UI control symbols: clipboard icons (📋), expand buttons (⏬), and other UI symbols
        text = text.replace(/[📋⏬🔽🔼⏫📁📄]/g, '').trim();
        
        // Always include the text with count in parentheses for ALL nodes
        // 修改：确保所有目录节点后方括号跟数字都被包含在匯出中
        if (text) {
          allItems.push(indent + text);
        }
        
        // Always collect children regardless of open/closed state
        const childUl = item.querySelector(':scope > ul');
        if (childUl) {
          collectAllItems(childUl, indent + '  ');
        }
      });
    }
    
    // Collect ALL items starting from the tree root
    collectAllItems(tree);
    
    // Create text content (filter out empty lines)
    const filteredItems = allItems.filter(item => item.trim() !== '');
    const textContent = filteredItems.join('\n');
    
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