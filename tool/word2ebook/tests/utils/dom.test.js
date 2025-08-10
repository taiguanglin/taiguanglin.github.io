/**
 * @fileoverview DOMUtils 工具類測試
 * @author Assistant
 * @version 1.0.0
 */

import { DOMUtils } from '../../assets/js/utils/dom.js';
import { CSS_CLASSES } from '../../assets/js/constants/config.js';

describe('DOMUtils', () => {
  let container;

  beforeEach(() => {
    container = document.createElement('div');
    container.id = 'test-container';
    document.body.appendChild(container);
  });

  afterEach(() => {
    if (container && container.parentNode) {
      container.parentNode.removeChild(container);
    }
  });

  describe('querySelector', () => {
    test('應該能找到存在的元素', () => {
      const testElement = document.createElement('div');
      testElement.className = 'test-element';
      container.appendChild(testElement);

      const result = DOMUtils.querySelector('.test-element', container);
      expect(result).toBe(testElement);
    });

    test('應該在找不到元素時返回 null', () => {
      const result = DOMUtils.querySelector('.non-existent', container);
      expect(result).toBeNull();
    });

    test('應該在無效選擇器時返回 null 並記錄警告', () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      const result = DOMUtils.querySelector('invalid>>selector', container);
      
      expect(result).toBeNull();
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Invalid selector'),
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    test('應該使用 document 作為預設上下文', () => {
      const testElement = document.createElement('div');
      testElement.id = 'global-element';
      document.body.appendChild(testElement);

      const result = DOMUtils.querySelector('#global-element');
      expect(result).toBe(testElement);

      document.body.removeChild(testElement);
    });
  });

  describe('querySelectorAll', () => {
    test('應該能找到多個元素', () => {
      const element1 = document.createElement('div');
      const element2 = document.createElement('div');
      element1.className = 'test-item';
      element2.className = 'test-item';
      container.appendChild(element1);
      container.appendChild(element2);

      const result = DOMUtils.querySelectorAll('.test-item', container);
      expect(result).toHaveLength(2);
      expect(result[0]).toBe(element1);
      expect(result[1]).toBe(element2);
    });

    test('應該在無效選擇器時返回空陣列', () => {
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      const result = DOMUtils.querySelectorAll('invalid>>selector', container);
      
      expect(result).toEqual([]);
      expect(consoleSpy).toHaveBeenCalled();
      
      consoleSpy.mockRestore();
    });
  });

  describe('createElement', () => {
    test('應該創建基本元素', () => {
      const element = DOMUtils.createElement('div');
      expect(element.tagName).toBe('DIV');
    });

    test('應該設置所有指定的選項', () => {
      const options = {
        className: 'test-class',
        id: 'test-id',
        innerHTML: '<span>Test content</span>',
        attributes: {
          'data-test': 'value',
          'aria-label': 'Test label'
        },
        dataset: {
          custom: 'custom-value'
        }
      };

      const element = DOMUtils.createElement('div', options);

      expect(element.className).toBe('test-class');
      expect(element.id).toBe('test-id');
      expect(element.innerHTML).toBe('<span>Test content</span>');
      expect(element.getAttribute('data-test')).toBe('value');
      expect(element.getAttribute('aria-label')).toBe('Test label');
      expect(element.dataset.custom).toBe('custom-value');
    });
  });

  describe('類名操作', () => {
    let element;

    beforeEach(() => {
      element = document.createElement('div');
      container.appendChild(element);
    });

    test('addClass 應該添加類名', () => {
      DOMUtils.addClass(element, 'class1', 'class2');
      expect(element.classList.contains('class1')).toBe(true);
      expect(element.classList.contains('class2')).toBe(true);
    });

    test('removeClass 應該移除類名', () => {
      element.className = 'class1 class2 class3';
      DOMUtils.removeClass(element, 'class1', 'class3');
      expect(element.classList.contains('class1')).toBe(false);
      expect(element.classList.contains('class2')).toBe(true);
      expect(element.classList.contains('class3')).toBe(false);
    });

    test('toggleClass 應該切換類名', () => {
      const result1 = DOMUtils.toggleClass(element, 'toggle-class');
      expect(result1).toBe(true);
      expect(element.classList.contains('toggle-class')).toBe(true);

      const result2 = DOMUtils.toggleClass(element, 'toggle-class');
      expect(result2).toBe(false);
      expect(element.classList.contains('toggle-class')).toBe(false);
    });

    test('toggleClass 應該支援強制參數', () => {
      DOMUtils.toggleClass(element, 'force-class', true);
      expect(element.classList.contains('force-class')).toBe(true);

      DOMUtils.toggleClass(element, 'force-class', true);
      expect(element.classList.contains('force-class')).toBe(true);

      DOMUtils.toggleClass(element, 'force-class', false);
      expect(element.classList.contains('force-class')).toBe(false);
    });

    test('hasClass 應該檢查類名是否存在', () => {
      element.className = 'existing-class';
      expect(DOMUtils.hasClass(element, 'existing-class')).toBe(true);
      expect(DOMUtils.hasClass(element, 'non-existing-class')).toBe(false);
    });

    test('類名操作應該處理 null 元素', () => {
      expect(() => {
        DOMUtils.addClass(null, 'class');
        DOMUtils.removeClass(null, 'class');
        DOMUtils.toggleClass(null, 'class');
        DOMUtils.hasClass(null, 'class');
      }).not.toThrow();

      expect(DOMUtils.hasClass(null, 'class')).toBe(false);
      expect(DOMUtils.toggleClass(null, 'class')).toBe(false);
    });
  });

  describe('顯示/隱藏操作', () => {
    let element;

    beforeEach(() => {
      element = document.createElement('div');
      container.appendChild(element);
    });

    test('show 應該顯示元素', () => {
      element.style.display = 'none';
      element.classList.add(CSS_CLASSES.STATE.HIDDEN);

      DOMUtils.show(element);

      expect(element.style.display).toBe('block');
      expect(element.classList.contains(CSS_CLASSES.STATE.HIDDEN)).toBe(false);
    });

    test('show 應該支援自定義 display 值', () => {
      DOMUtils.show(element, 'flex');
      expect(element.style.display).toBe('flex');
    });

    test('hide 應該隱藏元素', () => {
      DOMUtils.hide(element);
      expect(element.style.display).toBe('none');
      expect(element.classList.contains(CSS_CLASSES.STATE.HIDDEN)).toBe(true);
    });

    test('toggle 應該切換顯示狀態', () => {
      // 初始狀態：顯示
      DOMUtils.toggle(element);
      expect(element.style.display).toBe('none');

      // 切換：顯示
      DOMUtils.toggle(element);
      expect(element.style.display).toBe('block');
    });

    test('isVisible 應該正確檢測可見性', () => {
      expect(DOMUtils.isVisible(element)).toBe(true);

      element.style.display = 'none';
      expect(DOMUtils.isVisible(element)).toBe(false);

      element.style.display = 'block';
      element.style.visibility = 'hidden';
      expect(DOMUtils.isVisible(element)).toBe(false);

      element.style.visibility = 'visible';
      element.style.opacity = '0';
      expect(DOMUtils.isVisible(element)).toBe(false);
    });
  });

  describe('屬性操作', () => {
    let element;

    beforeEach(() => {
      element = document.createElement('div');
      container.appendChild(element);
    });

    test('setAttributes 應該設置多個屬性', () => {
      const attributes = {
        'data-test': 'value1',
        'aria-label': 'Test label',
        'role': 'button'
      };

      DOMUtils.setAttributes(element, attributes);

      expect(element.getAttribute('data-test')).toBe('value1');
      expect(element.getAttribute('aria-label')).toBe('Test label');
      expect(element.getAttribute('role')).toBe('button');
    });

    test('removeAttributes 應該移除屬性', () => {
      element.setAttribute('attr1', 'value1');
      element.setAttribute('attr2', 'value2');
      element.setAttribute('attr3', 'value3');

      DOMUtils.removeAttributes(element, 'attr1', 'attr3');

      expect(element.hasAttribute('attr1')).toBe(false);
      expect(element.hasAttribute('attr2')).toBe(true);
      expect(element.hasAttribute('attr3')).toBe(false);
    });
  });

  describe('DOM 操作', () => {
    let element;

    beforeEach(() => {
      element = document.createElement('div');
      element.innerHTML = '<span>Original content</span>';
      container.appendChild(element);
    });

    test('empty 應該清空元素內容', () => {
      DOMUtils.empty(element);
      expect(element.innerHTML).toBe('');
    });

    test('remove 應該移除元素', () => {
      expect(container.contains(element)).toBe(true);
      DOMUtils.remove(element);
      expect(container.contains(element)).toBe(false);
    });

    test('insertBefore 應該在指定元素前插入', () => {
      const newElement = document.createElement('div');
      newElement.textContent = 'New element';

      DOMUtils.insertBefore(newElement, element);

      expect(container.children[0]).toBe(newElement);
      expect(container.children[1]).toBe(element);
    });

    test('insertAfter 應該在指定元素後插入', () => {
      const newElement = document.createElement('div');
      newElement.textContent = 'New element';

      DOMUtils.insertAfter(newElement, element);

      expect(container.children[0]).toBe(element);
      expect(container.children[1]).toBe(newElement);
    });
  });

  describe('位置和滾動', () => {
    let element;

    beforeEach(() => {
      element = document.createElement('div');
      container.appendChild(element);

      // 模擬 getBoundingClientRect
      element.getBoundingClientRect = jest.fn(() => ({
        top: 100,
        left: 50,
        width: 200,
        height: 150,
        bottom: 250,
        right: 250
      }));

      // 模擬頁面滾動
      Object.defineProperty(window, 'pageYOffset', { value: 10, writable: true });
      Object.defineProperty(window, 'pageXOffset', { value: 5, writable: true });
    });

    test('getPosition 應該返回正確的位置信息', () => {
      const position = DOMUtils.getPosition(element);

      expect(position).toEqual({
        top: 110, // 100 + 10 (pageYOffset)
        left: 55,  // 50 + 5 (pageXOffset)
        width: 200,
        height: 150,
        viewportTop: 100,
        viewportLeft: 50
      });
    });

    test('getPosition 應該處理 null 元素', () => {
      const position = DOMUtils.getPosition(null);
      expect(position).toEqual({
        top: 0,
        left: 0,
        width: 0,
        height: 0,
        viewportTop: 0,
        viewportLeft: 0
      });
    });

    test('scrollToElement 應該調用 scrollIntoView', () => {
      const scrollSpy = jest.spyOn(element, 'scrollIntoView');

      DOMUtils.scrollToElement(element);

      expect(scrollSpy).toHaveBeenCalledWith({
        behavior: 'smooth',
        block: 'start'
      });

      DOMUtils.scrollToElement(element, { behavior: 'auto', block: 'center' });

      expect(scrollSpy).toHaveBeenCalledWith({
        behavior: 'auto',
        block: 'center'
      });
    });
  });

  describe('工具函數', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    test('throttle 應該限制函數調用頻率', () => {
      const mockFn = jest.fn();
      const throttledFn = DOMUtils.throttle(mockFn, 100);

      // 快速調用多次
      throttledFn('arg1');
      throttledFn('arg2');
      throttledFn('arg3');

      // 應該立即執行第一次
      expect(mockFn).toHaveBeenCalledTimes(1);
      expect(mockFn).toHaveBeenCalledWith('arg1');

      // 等待節流時間
      jest.advanceTimersByTime(100);

      // 應該執行最後一次調用
      expect(mockFn).toHaveBeenCalledTimes(2);
      expect(mockFn).toHaveBeenLastCalledWith('arg3');
    });

    test('debounce 應該延遲函數執行', () => {
      const mockFn = jest.fn();
      const debouncedFn = DOMUtils.debounce(mockFn, 100);

      // 快速調用多次
      debouncedFn('arg1');
      debouncedFn('arg2');
      debouncedFn('arg3');

      // 應該還沒有執行
      expect(mockFn).not.toHaveBeenCalled();

      // 等待防抖時間
      jest.advanceTimersByTime(100);

      // 應該只執行最後一次調用
      expect(mockFn).toHaveBeenCalledTimes(1);
      expect(mockFn).toHaveBeenCalledWith('arg3');
    });

    test('debounce 應該在新調用時重置計時器', () => {
      const mockFn = jest.fn();
      const debouncedFn = DOMUtils.debounce(mockFn, 100);

      debouncedFn('arg1');
      jest.advanceTimersByTime(50);
      
      debouncedFn('arg2'); // 重置計時器
      jest.advanceTimersByTime(50);
      
      // 應該還沒有執行
      expect(mockFn).not.toHaveBeenCalled();
      
      jest.advanceTimersByTime(50);
      
      // 現在應該執行
      expect(mockFn).toHaveBeenCalledTimes(1);
      expect(mockFn).toHaveBeenCalledWith('arg2');
    });
  });
});
