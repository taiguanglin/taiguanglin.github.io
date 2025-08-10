/**
 * @fileoverview MiniSearch 模擬檔案
 * @author Assistant
 * @version 1.0.0
 */

class MockMiniSearch {
  constructor(options = {}) {
    this.options = options;
    this.documents = [];
  }

  addAll(documents) {
    this.documents = [...documents];
  }

  search(query, options = {}) {
    // 簡單的模擬搜索邏輯
    const results = this.documents
      .filter(doc => 
        doc.title?.toLowerCase().includes(query.toLowerCase()) ||
        doc.content?.toLowerCase().includes(query.toLowerCase())
      )
      .map((doc, index) => ({
        ...doc,
        score: Math.random() * 2, // 模擬評分
        match: {},
        terms: [query],
      }));

    return results.slice(0, options.limit || 100);
  }

  autoSuggest(query, options = {}) {
    // 模擬自動建議
    const suggestions = [
      { suggestion: `${query}測試`, score: 1.5, terms: [query] },
      { suggestion: `${query}範例`, score: 1.2, terms: [query] },
    ];

    return suggestions.slice(0, options.limit || 5);
  }

  removeAll() {
    this.documents = [];
  }

  remove(id) {
    this.documents = this.documents.filter(doc => doc.id !== id);
  }

  add(document) {
    this.documents.push(document);
  }

  has(id) {
    return this.documents.some(doc => doc.id === id);
  }

  getStoredFields(id) {
    const doc = this.documents.find(d => d.id === id);
    return doc || null;
  }
}

module.exports = MockMiniSearch;
