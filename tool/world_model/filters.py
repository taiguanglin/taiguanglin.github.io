#!/usr/bin/env python3
"""Superseded cosmology claims, filtered out of both compilations.

Tai 師父 revised the 銀河系／須彌山 model. 《坐禪1》 first said 須彌山＝銀河系
(銀河的黑洞＝須彌山頂); later he corrected it — 須彌山 is the pillar that pierces
the galaxy and links this small world to the worlds above. Feeding both versions
to a model would make it draw the superseded geometry, so the earlier claim is
excluded by design.

Only two passages assert the old model as fact; the later statements that carry
the corrected model (山腰＝四天王天, 山腳＝人間, 山頂＝忉利天帝釋天宮, 每個小世界
各有一根須彌山) all survive elsewhere, so nothing is lost.
"""
import re

# Phrasings that assert the superseded "須彌山＝銀河系" model.
SUPERSEDED = re.compile(
    r"整個銀河系就是須彌山"
    r"|須彌山就是銀河系"
    r"|中間的黑洞部分就是須彌山頂"
    r"|銀河的黑洞部分是須彌山"
)

# The corrected model, for spot-checking that the filter still targets the old one.
CURRENT = re.compile(
    r"須彌山不是銀河系"
    r"|須彌山是銀河系嗎？不是"
    r"|須彌山是穿透銀河"
    r"|須彌山插進來的柱子"
    r"|須彌山像柱子一樣往下插"
    r"|我們看到的銀河系是須彌山的山腳下"
)


def is_superseded(text):
    """True when the passage asserts the old 須彌山＝銀河系 model."""
    return bool(SUPERSEDED.search(text))