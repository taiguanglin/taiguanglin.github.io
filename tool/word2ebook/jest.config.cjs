/**
 * @fileoverview Jest 測試配置
 * @author Assistant
 * @version 1.0.0
 */

module.exports = {
  // 測試環境
  testEnvironment: 'jsdom',
  
  // 根目錄
  rootDir: '.',
  
  // 測試檔案模式
  testMatch: [
    '<rootDir>/tests/**/*.test.js',
    '<rootDir>/tests/**/*.spec.js'
  ],
  
  // 覆蓋率收集
  collectCoverage: true,
  collectCoverageFrom: [
    'assets/js/**/*.js',
    '!assets/js/**/*.test.js',
    '!assets/js/**/*.spec.js',
    '!assets/js/app.js', // 主入口檔案，由整合測試覆蓋
  ],
  
  // 覆蓋率門檻
  coverageThreshold: {
    global: {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90
    }
  },
  
  // 覆蓋率報告格式
  coverageReporters: [
    'text',
    'text-summary',
    'html',
    'lcov'
  ],
  
  // 覆蓋率輸出目錄
  coverageDirectory: '<rootDir>/coverage',
  
  // 模組名稱映射（用於處理 ES6 imports）
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/assets/js/$1',
    '^@constants/(.*)$': '<rootDir>/assets/js/constants/$1',
    '^@utils/(.*)$': '<rootDir>/assets/js/utils/$1',
    '^@services/(.*)$': '<rootDir>/assets/js/services/$1',
    '^@components/(.*)$': '<rootDir>/assets/js/components/$1',
    // 模擬外部依賴
    'minisearch': '<rootDir>/tests/__mocks__/minisearch.js'
  },
  
  // 設置檔案
  setupFilesAfterEnv: [
    '<rootDir>/tests/setup.js'
  ],
  
  // 模組檔案擴展名
  moduleFileExtensions: [
    'js',
    'json'
  ],
  
  // 轉換配置（使用 Babel 處理 ES6 模組）
  transform: {
    '^.+\\.js$': 'babel-jest'
  },
  
  // 忽略轉換的檔案
  transformIgnorePatterns: [
    'node_modules/(?!(minisearch)/)'
  ],
  
  // 測試超時時間（毫秒）
  testTimeout: 10000,
  
  // 清除模擬
  clearMocks: true,
  restoreMocks: true,
  
  // 詳細輸出
  verbose: true,
  
  // 全域變數
  globals: {
    'window': {},
    'document': {},
    'localStorage': {},
    'sessionStorage': {},
    'navigator': {},
    'location': {},
    'history': {}
  }
};
