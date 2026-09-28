#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《坐禪之問答錄2 · 重點知識》— 完整內容 SoT（組裝 a–e 五個分檔）。

拆成 a／b／c／d／e 五個檔案只是為了讓每次編輯的 diff 不要長到看不出
重點；SoT 仍然是這裡組出來的 `BOOK`。

* a：書籍 metadata ＋ 第一部（ch01–05：地基、意識、業、加持、消業）
* b：第二部（ch06–15：發心戒行 → 生活修行）
* c：第三部（ch16：2025-06 之後的新說法與修正）
* d：第三部（ch17：2025-11 之後的最後一批教導）
* e：第三部（ch18：2026-01～03 補齊）
"""

from __future__ import annotations

import keypoints_a
import keypoints_b
import keypoints_c
import keypoints_d
import keypoints_e

BOOK = dict(keypoints_a.BOOK)
BOOK["chapters"] += (
    keypoints_b.CHAPTERS
    + keypoints_c.CHAPTERS
    + keypoints_d.CHAPTERS
    + keypoints_e.CHAPTERS
)
BOOK["slug"] = "wenda2_keypoints"
BOOK["kind"] = "重點知識"
BOOK["audience"] = "已經讀過《坐禪之問答錄2》的人"
