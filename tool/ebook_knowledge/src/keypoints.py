#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《坐禪與講經十書・重點知識》— 完整內容 SoT（組裝 keypoints_a…keypoints_e）。

拆成五個檔案只是為了讓每次編輯的 diff 不要長到看不出重點；
SoT 仍然是這裡組出來的 `BOOK`。
"""

from __future__ import annotations

import keypoints_a
import keypoints_b
import keypoints_c
import keypoints_d
import keypoints_e

BOOK = dict(keypoints_a.BOOK)
_all = (keypoints_a.CHAPTERS + keypoints_b.CHAPTERS + keypoints_c.CHAPTERS
        + keypoints_d.CHAPTERS + keypoints_e.CHAPTERS)
# 章號連續性守門：由組裝結果統一編號，避免手寫 num 漂移
for i, ch in enumerate(_all, 1):
    ch["num"] = i
BOOK["chapters"] = _all
BOOK["slug"] = "ebook_keypoints"
BOOK["kind"] = "重點知識"
BOOK["audience"] = "已經讀完坐禪系列與講經系列十本書的人"
