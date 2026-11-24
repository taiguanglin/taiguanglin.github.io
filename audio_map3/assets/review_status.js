/**
 * 本講所有需要校對的項目是否都已確認。
 *
 * 「確認」與校稿 UI 的既有判定一致：
 * - 有「最後播放」記錄（meta.lastPlayed）；或
 * - zero=true（師父未念，這一段沒有音檔可聽）。
 *
 * 空清單不算完成，避免沒有段落的講次被誤標為 reviewed。
 */
export function areAllItemsConfirmed(items) {
    const list = Array.isArray(items) ? items : [];
    return list.length > 0 && list.every((item) => (
        Boolean(item?.meta?.lastPlayed) || item?.zero === true
    ));
}
