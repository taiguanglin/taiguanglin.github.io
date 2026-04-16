  // ============ 功能實現 ============
  
  // 生成內容的簡單hash（與Python端保持一致，使用MD5前12位）
  function simpleHash(str) {
    // 注意：這是一個簡化版本，實際應該使用與Python端相同的MD5算法
    // 為了保持一致性，我們暫時使用相同的邏輯結構
    let hash = 0;
    if (str.length === 0) return '000000000000';
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // 轉換為32位整數
    }
    // 將hash轉換為12位16進制字符串，模擬MD5前12位
    const hexHash = Math.abs(hash).toString(16).padStart(12, '0').substring(0, 12);
    return hexHash;
  }
  
  // 標準化文本內容，提高ID生成的穩定性
  function normalizeTextForId(text) {
    if (!text) return '';
    
    return text
      .trim()                                    // 移除首尾空白
      .replace(/[\\r\\n\\t]/g, ' ')              // 替換換行符和制表符為空格
      .replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');  // 處理HTML實體，與Python端保持一致
  }
  
  // 生成穩定的內容ID
  function generateStableContentId(questioner, content, time) {
    // 標準化各個組件
    const normalizedQuestioner = normalizeTextForId(questioner);
    const normalizedContent = normalizeTextForId(content);
    
    // 標準化時間：只保留數字部分
    const normalizedTime = time ? time.replace(/[^\\d]/g, '').substring(0, 8) : '';
    
    // 組合穩定的標識內容：人名 + 時間 + 前50個字（與Python端保持一致）
    const stableContent = normalizedQuestioner + 
                         normalizedTime +
                         normalizedContent.substring(0, 50); // 改為50字符，與用戶要求一致
    
    return simpleHash(stableContent);
  }
  
  // 生成兼容性的舊版ID（用於遷移）
  function generateLegacyContentId(questioner, content, time) {
    // 使用舊的邏輯生成ID，用於查找現有書籤
    const contentText = questioner + content + time;
    return simpleHash(contentText);
  }
  
  // 生成舊版80字符邏輯的ID（用於向後兼容）
  function generateLegacy80CharId(questioner, content, time) {
    // 舊的邏輯：人名 + 前80字符 + 時間
    const normalizedQuestioner = normalizeTextForId(questioner);
    const normalizedContent = normalizeTextForId(content);
    const normalizedTime = time ? time.replace(/[^\\d]/g, '').substring(0, 8) : '';
    
    const stableContent = normalizedQuestioner + 
                         normalizedContent.substring(0, 80) + // 舊的80字符
                         normalizedTime;
    
    return simpleHash(stableContent);
  }
  
  // 嘗試查找元素的多種ID策略
  function findElementByMultipleIds(questioner, content, time, prefix = 'qa') {
    // 1. 先嘗試新的穩定ID（人名+時間+前50字）
    const stableId = prefix + '-' + generateStableContentId(questioner, content, time);
    let element = document.getElementById(stableId);
    
    if (!element) {
      // 2. 嘗試舊的80字符邏輯
      const legacy80Id = prefix + '-' + generateLegacy80CharId(questioner, content, time);
      element = document.getElementById(legacy80Id);
    }
    
    if (!element) {
      // 3. 嘗試最原始的舊ID邏輯
      const legacyId = prefix + '-' + generateLegacyContentId(questioner, content, time);
      element = document.getElementById(legacyId);
    }
    
    return element;
  }
  
  // 確保元素有唯一且穩定的ID
  function ensureElementId(element, prefix = 'qa') {
    if (!element.id) {
      let questioner = '', content = '', time = '';
      
      if (element.classList.contains('question')) {
        questioner = element.querySelector('.questioner')?.textContent || '';
        content = element.querySelector('.question-text')?.textContent || '';
        time = element.querySelector('.question-time')?.textContent || '';
      } else if (element.classList.contains('answer')) {
        questioner = element.querySelector('.answerer')?.textContent || '';
        content = element.querySelector('.answer-text')?.textContent || '';
        // 答案通常沒有時間，使用空字符串
        time = '';
      }
      
      // 使用新的穩定ID生成邏輯
      const stableHash = generateStableContentId(questioner, content, time);
      element.id = prefix + '-' + stableHash;
    }
    return element.id;
  }
  
  // 生成分享URL
  function generateShareUrl(targetElement) {
    const prefix = targetElement.classList.contains('question') ? 'question' : 'answer';
    const elementId = ensureElementId(targetElement, prefix);
    const baseUrl = window.location.origin + window.location.pathname;
    return baseUrl + '#' + elementId;
  }
  
  // 找到問答配對
  function findQuestionForAnswer(answerElement) {
    let currentElement = answerElement.previousElementSibling;
    
    // 向上查找最近的問題元素
    while (currentElement) {
      if (currentElement.classList.contains('question')) {
        return currentElement;
      }
      currentElement = currentElement.previousElementSibling;
    }
    
    return null;
  }
  
  function findAnswerForQuestion(questionElement) {
    let currentElement = questionElement.nextElementSibling;
    
    // 向下查找最近的回答元素
    while (currentElement) {
      if (currentElement.classList.contains('answer')) {
        return currentElement;
      }
      currentElement = currentElement.nextElementSibling;
    }
    
    return null;
  }
  
  // 獲取問答的完整文本
  function getQAPairText(element) {
    let questionElement, answerElement;
    let text = '';
    
    // 判断传入的是问题还是答案元素
    if (element.classList.contains('question')) {
      questionElement = element;
      answerElement = findAnswerForQuestion(element);
    } else if (element.classList.contains('answer')) {
      answerElement = element;
      questionElement = findQuestionForAnswer(element);
    }
    
    // 提取問題內容
    if (questionElement) {
      const questioner = questionElement.querySelector('.questioner')?.textContent || '匿名';
      const questionTime = questionElement.querySelector('.question-time')?.textContent || '';
      const questionText = questionElement.querySelector('.question-text')?.textContent || '';
      
      text += `問：${questioner}`;
      if (questionTime) text += ` (${questionTime})`;
      text += `\n${questionText}\n\n`;
    }
    
    // 提取回答內容
    if (answerElement) {
      const answerer = answerElement.querySelector('.answerer')?.textContent || 'Taiguanglin';
      const answerText = answerElement.querySelector('.answer-text')?.textContent || '';
      
      text += `答：${answerer}\n${answerText}`;
    }
    
    return text;
  }
  
