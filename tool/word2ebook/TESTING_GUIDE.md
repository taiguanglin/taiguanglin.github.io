# 📋 測試執行指南

## 🎯 概述

本文檔提供 Word2EBook 專案重構後的完整測試指南，包括測試環境設置、執行方法、測試策略和最佳實踐。

## 🔧 環境準備

### 1. 安裝 Node.js 和 npm

確保安裝了 Node.js 16+ 和 npm 7+：

```bash
# 檢查版本
node --version  # 應該 >= 16.0.0
npm --version   # 應該 >= 7.0.0

# 如果需要安裝，推薦使用 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18
```

### 2. 安裝專案依賴

```bash
# 進入專案目錄
cd /Users/paul/taiguanglin.github.io/tool/word2ebook

# 安裝所有依賴
npm install
```

### 3. 驗證安裝

```bash
# 檢查 Jest 是否正確安裝
npx jest --version

# 檢查 ESLint 是否正確安裝
npx eslint --version
```

## 🧪 測試執行

### 基本測試命令

```bash
# 執行所有測試
npm test

# 執行測試並生成覆蓋率報告
npm run test:coverage

# 監控模式執行測試（檔案變更時自動重新執行）
npm run test:watch

# 生成覆蓋率報告並在瀏覽器中打開
npm run test:coverage:open
```

### 高級測試選項

```bash
# 執行特定測試檔案
npx jest tests/utils/dom.test.js

# 執行符合模式的測試
npx jest --testNamePattern="DOMUtils"

# 執行測試並顯示詳細輸出
npx jest --verbose

# 執行測試但跳過覆蓋率收集（更快）
npx jest --passWithNoTests

# 執行測試並更新快照
npx jest --updateSnapshot

# 執行特定目錄的測試
npx jest tests/services/

# 並行執行測試（預設）
npx jest --maxWorkers=4

# 串行執行測試（用於調試）
npx jest --runInBand
```

### 除錯模式

```bash
# 在 Node.js 除錯模式下執行測試
node --inspect-brk node_modules/.bin/jest --runInBand

# 使用 VS Code 除錯
# 在 VS Code 中設置斷點，然後按 F5 執行 "Jest Debug" 配置
```

## 📊 覆蓋率報告

### 查看覆蓋率

執行 `npm run test:coverage` 後，會生成以下報告：

1. **終端輸出**: 即時的覆蓋率摘要
2. **HTML 報告**: `coverage/lcov-report/index.html`
3. **LCOV 檔案**: `coverage/lcov.info` (可用於 CI/CD)

### 覆蓋率門檻

專案設定的最低覆蓋率要求：

- **分支覆蓋率**: ≥ 90%
- **函數覆蓋率**: ≥ 90%  
- **行覆蓋率**: ≥ 90%
- **語句覆蓋率**: ≥ 90%

### 查看詳細覆蓋率

```bash
# 生成並打開 HTML 覆蓋率報告
npm run test:coverage:open

# 或手動打開
open coverage/lcov-report/index.html  # macOS
start coverage/lcov-report/index.html # Windows
xdg-open coverage/lcov-report/index.html # Linux
```

## 🎯 測試結構

### 測試檔案組織

```
tests/
├── setup.js                   # 測試環境設置
├── __mocks__/                 # 模擬檔案
│   └── minisearch.js         # 外部依賴模擬
├── utils/                     # 工具函數測試
│   ├── dom.test.js           # DOM 工具測試
│   ├── page.test.js          # 頁面工具測試
│   └── storage.test.js       # 儲存工具測試
├── services/                  # 服務層測試
│   ├── i18n.test.js          # 國際化服務測試
│   ├── search.test.js        # 搜索服務測試
│   └── bookmark.test.js      # 書籤服務測試
├── components/                # 組件測試
│   ├── base-component.test.js # 基礎組件測試
│   └── search-component.test.js # 搜索組件測試
└── integration/               # 整合測試
    └── app.test.js           # 應用程式整合測試
```

### 測試命名規範

```javascript
// 描述測試群組
describe('ComponentName', () => {
  
  // 描述測試情境
  describe('methodName', () => {
    
    // 描述預期行為
    test('應該在特定條件下產生預期結果', () => {
      // 測試實現
    });
    
    test('應該處理錯誤情況', () => {
      // 錯誤處理測試
    });
  });
});
```

## 🔬 測試策略

### 1. 單元測試

測試單一函數或方法的功能：

```javascript
// 範例：測試 DOM 工具函數
test('querySelector 應該能找到存在的元素', () => {
  // Arrange（準備）
  const container = document.createElement('div');
  const testElement = document.createElement('span');
  testElement.className = 'test-class';
  container.appendChild(testElement);

  // Act（執行）
  const result = DOMUtils.querySelector('.test-class', container);

  // Assert（驗證）
  expect(result).toBe(testElement);
});
```

### 2. 整合測試

測試多個模組之間的交互：

```javascript
// 範例：測試搜索組件與搜索服務的整合
test('搜索組件應該能通過搜索服務執行搜索', async () => {
  const searchComponent = new SearchComponent(container);
  await searchComponent.activate();
  
  const results = await searchComponent.search('測試查詢');
  
  expect(results).toBeDefined();
  expect(Array.isArray(results)).toBe(true);
});
```

### 3. 模擬 (Mocking)

模擬外部依賴和複雜互動：

```javascript
// 模擬 fetch API
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve([{ id: 'test', content: 'test content' }])
  })
);

// 模擬瀏覽器 API
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: jest.fn(),
    setItem: jest.fn(),
    removeItem: jest.fn(),
  }
});
```

### 4. 快照測試

用於組件輸出的回歸測試：

```javascript
test('搜索結果應該渲染正確的 HTML 結構', () => {
  const results = [
    { id: 'test1', title: '測試標題', content: '測試內容' }
  ];
  
  const html = searchComponent._renderResults(results);
  expect(html).toMatchSnapshot();
});
```

## ⚡ 效能測試

### 測試執行效能

```bash
# 測量測試執行時間
time npm test

# 使用 Jest 內建的效能分析
npx jest --detectOpenHandles --forceExit

# 分析記憶體使用
npx jest --logHeapUsage
```

### 非同步測試最佳實踐

```javascript
// 使用 async/await
test('應該正確處理非同步操作', async () => {
  const result = await someAsyncFunction();
  expect(result).toBe('expected value');
});

// 設置超時時間
test('長時間運行的操作', async () => {
  // 這個測試最多執行 10 秒
  const result = await longRunningOperation();
  expect(result).toBeDefined();
}, 10000);

// 測試 Promise 拒絕
test('應該處理錯誤情況', async () => {
  await expect(functionThatShouldThrow()).rejects.toThrow('錯誤訊息');
});
```

## 🔍 代碼品質檢查

### ESLint 檢查

```bash
# 檢查所有 JavaScript 檔案
npm run lint

# 自動修復可修復的問題
npm run lint:fix

# 檢查特定檔案
npx eslint assets/js/utils/dom.js

# 忽略特定規則
npx eslint assets/js/ --rule "no-console: off"
```

### 自定義 ESLint 規則

編輯 `.eslintrc.js` 來調整規則：

```javascript
module.exports = {
  rules: {
    // 自定義規則
    'indent': ['error', 2],
    'quotes': ['error', 'single'],
    'semi': ['error', 'always'],
    
    // Jest 特定規則
    'jest/no-focused-tests': 'error',
    'jest/valid-expect': 'error',
  }
};
```

## 🚀 持續整合 (CI) 設置

### GitHub Actions 範例

創建 `.github/workflows/test.yml`：

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        node-version: [16, 18, 20]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Use Node.js ${{ matrix.node-version }}
      uses: actions/setup-node@v4
      with:
        node-version: ${{ matrix.node-version }}
        cache: 'npm'
    
    - name: Install dependencies
      run: npm ci
    
    - name: Run linter
      run: npm run lint
    
    - name: Run tests
      run: npm run test:coverage
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage/lcov.info
```

## 🐛 除錯技巧

### 1. 測試除錯

```javascript
// 在測試中使用 console.log
test('除錯範例', () => {
  const result = someFunction();
  console.log('Debug:', result); // 這會顯示在測試輸出中
  expect(result).toBe('expected');
});

// 使用 Jest 的 .only 來單獨執行特定測試
test.only('只執行這個測試', () => {
  // 測試代碼
});

// 跳過特定測試
test.skip('暫時跳過這個測試', () => {
  // 測試代碼
});
```

### 2. VS Code 除錯配置

創建 `.vscode/launch.json`：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "node",
      "request": "launch",
      "name": "Jest Debug",
      "program": "${workspaceFolder}/node_modules/.bin/jest",
      "args": ["--runInBand"],
      "console": "integratedTerminal",
      "internalConsoleOptions": "neverOpen",
      "disableOptimisticBPs": true,
      "windows": {
        "program": "${workspaceFolder}/node_modules/jest/bin/jest"
      }
    }
  ]
}
```

### 3. 常見問題解決

**問題**: 測試超時
```javascript
// 解決方案：增加超時時間
jest.setTimeout(10000);

// 或在個別測試中設置
test('長時間測試', async () => {
  // 測試代碼
}, 15000);
```

**問題**: 模擬沒有正確重置
```javascript
// 解決方案：在每個測試後清理
afterEach(() => {
  jest.clearAllMocks();
  jest.restoreAllMocks();
});
```

**問題**: DOM 元素沒有正確清理
```javascript
// 解決方案：在每個測試後清理 DOM
afterEach(() => {
  document.body.innerHTML = '';
  document.head.innerHTML = '';
});
```

## 📈 測試指標

### 關鍵指標追蹤

1. **覆蓋率趨勢**: 確保覆蓋率不下降
2. **測試執行時間**: 監控效能退化
3. **測試成功率**: 追蹤測試穩定性
4. **變更檢測**: 確保測試能檢測到破壞性變更

### 覆蓋率報告解讀

- **綠色**: 覆蓋率 ≥ 90%
- **黃色**: 覆蓋率 75-90%
- **紅色**: 覆蓋率 < 75%

重點關注：
- 未覆蓋的分支 (Uncovered branches)
- 未測試的函數 (Uncovered functions)
- 複雜度高的未覆蓋代碼

## 🎓 最佳實踐

### 1. 測試撰寫原則

- **AAA 模式**: Arrange（準備）、Act（執行）、Assert（驗證）
- **單一責任**: 每個測試只驗證一個行為
- **描述性命名**: 測試名稱清楚說明測試意圖
- **獨立性**: 測試之間不應相互依賴

### 2. 模擬使用指南

- 只模擬必要的外部依賴
- 避免過度模擬導致測試失去意義
- 使用真實的模擬數據
- 確保模擬與實際 API 一致

### 3. 測試維護

- 定期更新測試依賴
- 重構代碼時同步更新測試
- 移除過時或無效的測試
- 保持測試代碼的品質

## 📞 支援與協助

### 獲取協助

1. **查看文檔**: 閱讀 Jest 和相關工具的官方文檔
2. **檢查日誌**: 仔細閱讀錯誤訊息和堆疊追蹤
3. **搜索問題**: 在 GitHub Issues 或 Stack Overflow 搜索類似問題
4. **提交 Issue**: 如果找不到解決方案，提交詳細的問題報告

### 有用資源

- [Jest 官方文檔](https://jestjs.io/docs/getting-started)
- [Testing Library 文檔](https://testing-library.com/docs/)
- [ESLint 規則參考](https://eslint.org/docs/rules/)
- [Node.js 測試最佳實踐](https://github.com/goldbergyoni/javascript-testing-best-practices)

---

遵循這個測試指南，你可以確保 Word2EBook 專案的代碼品質和穩定性。記住，良好的測試不僅能捕捉 bug，還能作為代碼的活文檔，幫助理解系統行為。
