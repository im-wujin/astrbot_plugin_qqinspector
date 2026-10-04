"""
合并转发文本清洗
=================

QQ 客户端（以及 OneBot 的合并转发 Plain 组件）在渲染时会因为文本里存在
以下字符出现「合并转发打不开」/「消息异常」的问题：

1. Bidi 排版控制符（U+202A–U+202E、U+2066–U+2069），会强制切换段落方向，
   导致整条消息排版崩溃；
2. UTF-16 代理项字符（U+D800–U+DFFF），QQ 消息体走 UTF-16 编码，单存的
   代理项属于非法字符；
3. 各类控制字符（含 C0、C1、DEL）以及零宽连接符（ZWJ，容易被误解为
   代理项）；
4. 补充平面字符（Supplementary Multilingual Plane，U+10000 以上），
   其中数学花体字母（U+1D400–U+1D7FF，例如 𝓔𝓽𝓮𝓻𝓷𝓸）在部分 QQ 客户端
   的合并转发渲染路径上会因代理对处理不当而直接导致消息卡片打不开；
   其他稀有 SMP 字符同样不安全；
5. 「\\uXXXX」/「\\xXX」字面量未成对出现的字符串——常见于用户把
   「unicode 转义写法」贴进昵称、个性签名，QQ 端会尝试解析导致渲染异常。

清洗策略：
- 保留常见 emoji（U+1F300–U+1FAFF）以及 BMP 内的常用字符；
- 将上列问题字符统一替换为空格；
- 移除多余的连续空格；
- 不修改调用方传入的结构，仅返回清洗后的字符串。
"""

import re

# 未配对的字面量转义：\uXXXX 或 \xXX（前面不是转义反斜杠）
_BAD_ESCAPE_RE = re.compile(
    r"(?<!\\)(?:\\u[0-9A-Fa-f]{1,4}|\\x[0-9A-Fa-f]{1,2})"
)

# 用于在替换之后压缩连续空白（保留换行）
_SPACE_RUN_RE = re.compile(r"[ \t]+")


def sanitize_text(s) -> str:
    """清洗一段用于合并转发 Plain 的文本，去掉会让 QQ 客户端打不开的特殊字符。

    - None / 非字符串 → 原样字符串化
    - 空字符串 → 空字符串
    - 其余按下列顺序处理：

    1. 去除 Bidi 排版控制符、ZWJ、C0/C1/DEL 控制字符（保留换行、制表）、
       UTF-16 代理项字符、U+0000 等不可打印字符；
    2. 用空格替换不合法的 ``\\uXXXX`` / ``\\xXX`` 字面量；
    3. 压缩连续空白；
    4. 去掉首尾空白。
    """
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    if not s:
        return s

    out: list[str] = []
    for ch in s:
        cp = ord(ch)
        # 换行/制表保留（用于文本布局），其他控制字符丢弃
        if ch in ("\n", "\r", "\t"):
            out.append(ch)
            continue
        # C0 控制字符（除上一步保留的换行/制表）以及 NUL
        if cp < 0x20:
            out.append(" ")
            continue
        # Bidi 排版控制符、零宽字符、方向隔离符
        if cp in (
            0x202A, 0x202B, 0x202C, 0x202D, 0x202E,  # LRE/RLE/FSI/PDI/BDI/…
            0x200E, 0x200F,                             # LRM/RLM
            0x200D,                                     # ZWJ
            0x200B,                                     # ZWSP
            0x200C,                                     # ZWNJ
            0xFEFF,                                     # ZWNBSP / BOM
            0x2066, 0x2067, 0x2068, 0x2069, 0x206A,    # BDI/BOM/BMC/…
            0x061C,                                     # Arabic Letter Mark
        ):
            out.append(" ")
            continue
        # DEL + C1 控制块
        if 0x007F <= cp <= 0x009F:
            out.append(" ")
            continue
        # UTF-16 代理项（BMP 内）
        if 0xD800 <= cp <= 0xDFFF:
            out.append(" ")
            continue
        # 补充平面（SMP）：仅保留常见 emoji 区间，其他一律剔除
        # —— U+10000 以上的字符会以代理对形式在 UTF-16 里传输，QQ 合并
        # 转发的部分渲染路径处理不严谨，会直接导致消息卡片打不开。
        if cp >= 0x10000:
            if 0x1F300 <= cp <= 0x1FAFF:  # 常见 emoji 保持原样
                out.append(ch)
            else:
                out.append(" ")
            continue
        out.append(ch)

    result = "".join(out)
    # 用空格替换掉不合法的 \uXXXX / \xXX 字面量
    result = _BAD_ESCAPE_RE.sub(" ", result)
    # 压缩连续空白（保留换行）
    result = _SPACE_RUN_RE.sub(" ", result)
    # 每行去首尾空白
    return "\n".join(ln.strip() for ln in result.splitlines())
