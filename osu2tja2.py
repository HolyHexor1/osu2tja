#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
osu2tja2 — osu!taiko (.osu, Mode=1) -> TJA 谱面转换器

★ 本文件是**唯一的转换引擎**, 两个入口共用它, 区别只在「难度的档位表」:
    osu2tja2.py      (本文件)  高难版: 输入就是高难谱, 最多 3 张, 最低只到 Hard
    osu2tja_low.py              低难版: 输入本来就是低难谱, 最多 5 张, 一直铺到 Easy
  差异全部集中在 `DIFF_PROFILES` 一张表和 `set_profile()` 一个函数里, 不要复制代码。
  ⚠ 低难版的入口必须在**任何转换/开窗之前**调 `set_profile('low')` —— 它改的是模块级
    常量, 写进函数默认参数会在 def 的时候就被固化, 改了不生效。

用法:
    python osu2tja2.py                        # 双击/直接运行 -> 弹窗选谱面 + 选输出文件夹
    python osu2tja2.py "谱面.osu"              # 命令行: 输出到谱面同目录
    python osu2tja2.py "谱面.osu" -o 输出目录/   # 命令行: 指定输出目录
    python osu2tja2.py a.osu b.osu c.osu      # 多难度: 三张谱合成**一个** .tja
                                              #   (按星数 = 里 / Oni / 困难, ★ = SR×2 自动算)
    python osu2tja_low.py a.osu ... e.osu     # 低难版: 五张谱 -> 里/鬼/困难/普通/简单
    python osu2tja2.py -o "D:/TJA" 一堆谱/*.osu # 批量: 按歌自动分组, 每首歌各转一个 .tja

第 1 步是一个**自带的谱面列表窗口**(不再从 Windows 文件管理器里一层层翻文件夹):
    输入即搜索 / 点表头按 曲名·曲师·难度·★·音符·大小·修改时间·文件夹 排序 /
    Ctrl·Shift 多选 / 右键「选中这首歌的全部谱面」/ 双击或回车确认。
    列表来自 osu! 的 Songs 目录; 扫描结果缓存在 %APPDATA%\\osu2tja2\\maps_cache.json
    (按「路径+修改时间+大小」失效, 第二次打开瞬开)。要挑 Songs 以外的谱面, 点窗口里的
    「用文件管理器…」退回原来的系统对话框。
图形界面会**记住上次选过的输出文件夹**和上次浏览的谱面目录(想恢复初始状态用 `--forget-out-dir`)。

产出结构（默认）:
    <你选的文件夹>/<曲名>/<谱面名>.tja
    <你选的文件夹>/<曲名>/<谱面名>.ogg      ← 不管源是 mp3 还是 ogg, 一律转成 OGG
    「曲名」默认取 .osu 的 TitleUnicode(原名); 判出该字段在源文件里写坏(泰文/韩文/
    只有汉字加长音符一类)时改用 Title(罗马音)并打印原因, 详见 looks_mojibake()。
    TJA 头部写 TITLE + ARTIST + SUBTITLE:--曲师。
    难度默认 COURSE:Oni(魔王); LEVEL(模拟器里显示的 ★×N)= osu!taiko 的 SR × 2 四舍五入。
    想退回旧行为(全塞进选定文件夹)加 --flat。

多难度（一个 .tja 装多张谱）:
    osu 的多难度 = 「一个文件夹 + 一份音源 + 多个 .osu」; 本家 = 「一个 .tja 里若干段
    COURSE/#START..#END」。给**多个** .osu 就按本家那种形态合成一个文件。
    档位表随入口切换(见 DIFF_PROFILES), 高难版:
        1 个 .osu  -> Oni
        2 个 .osu  -> 里(Edit) / Oni
        3 个 .osu  -> 里(Edit) / Oni / 困难(Hard)
        4 个以上   -> 直接报错(高难版最低只到 Hard: 简单/普通判定比 osu 宽, 会变假难度)
    低难版(osu2tja_low.py)从 Oni 往下铺, 因为它处理的本来就是低难谱:
        1 张 -> Oni | 2 张 -> Oni/Hard | 3 张 -> Oni/Hard/Normal
        4 张 -> Oni/Hard/Normal/Easy | 5 张 -> Edit/Oni/Hard/Normal/Easy
    ★ 谁当哪个难度**由星数决定**(用户 2026-11-15 定): ★ 高的拿更高的难度名, 最高那档必是
      Edit —— 所以同一组谱无论按什么顺序给, 结果都一样。只有两张谱的星数(★N)**完全相同**、
      分不出谁更难时, GUI 才会弹窗问你先后(见 order_by_star)。
    星数不固定: 每段 LEVEL = 该谱的 osu!taiko SR × 2 四舍五入(如 SR 4.31 -> ★9)。
    想手改用 --courses / --levels(它们是「按我给的顺序对号」的覆盖, 此时不再自动排)。
    `TITLE/WAVE/OFFSET/DEMOSTART` 是文件级的, 只写一次 —— 所以几张谱必须共用一条时间轴:
    OFFSET 取**所有谱里最早的谱面起点**, 起点更晚的那几张在开头补空小节(等价于本家
    谱面开头的等待段), 音符的绝对时刻一个都不变。音源只交付第一张谱所在文件夹的那一份。

批量（多首歌一次转）:
    选中的谱面跨了多首歌时, 自动按歌分组: **同一个文件夹 = 同一首歌**
    (osu 里一个 mapset 就是一个文件夹, 各难度共用一份音源; 不同歌必然在不同文件夹)。
        <输出目录>/<曲名A>/<曲名A>.tja + 音源
        <输出目录>/<曲名B>/<曲名B>.tja + 音源
    每首歌内部照上面多难度那套走(档位表同样随入口切换), 星数同样按 SR×2。
    某首歌自己超过本档上限 -> 报错并列出是哪几首, 一个文件都不写(绝不静默截断)。
    批量时**必须用 -o 给输出目录**: 没有安全的缺省位置(写到第一张谱的 mapset 里会把
    成品混进 osu 的 Songs)。--flat 在批量里不生效(音源文件名会互相覆盖, 每首歌必须
    各占一个文件夹); --title/--artist 也不生效(各首歌的曲名曲师来自它自己的 .osu)。
    命令行与双击弹窗都能批量; 弹窗的「排难度顺序」会把同一首歌的谱面排在一起。

选项:
    -o, --output PATH    输出路径; 给目录(或不带扩展名的路径)则自动放进该目录,
                         父目录不存在会自动创建; 默认与输入同目录
    --flat               不新建「曲名」子文件夹, 直接把 .tja 和 .ogg 放进指定目录
    --keep-original-names 不做乱码兜底: TitleUnicode/ArtistUnicode 写什么就用什么
    --title TEXT         强制指定曲名(源字段写坏时用; 同时决定文件夹名)
    --artist TEXT        强制指定曲师
    --gui                强制弹窗(即使已经写了输入文件)
    --encoding ENC       输出编码: cp932 (默认, 本家/日文模拟器惯例) | utf-8 | utf-8-sig
    --course NAME        COURSE: Oni(默认)/Hard/Normal/Easy/Edit; 写 auto 则按 Version 猜
    --level N            LEVEL(星数); 缺省 = SR × 2 四舍五入(拿不到 SR 时 10)
    --courses LIST       多输入时按顺序指定各段 COURSE(逗号分隔), 如 里,Oni / 困难,Oni
    --levels LIST        多输入时按顺序指定各段 LEVEL, 如 10,9(缺省按各谱 SR 算)
    --barline MODE       小节线: auto(默认)=照 osu 的 "Omit first bar line" 标记 | show | hide
    --subdiv N           基准「每拍格数」, 默认 4 (一格 = 1/4 拍, 本家最常用);
                         音符摆不下时自动升到 6/8/12/16/24 等
    --no-red-snap        关闭「红线网格还原」(默认开启, 不建议关)
    --wave-ext EXT       挑音源时只认这个扩展名 (如 ogg); 缺省=优先用 .osu 的 AudioFilename,
                         找不到再自动扫文件夹
    --no-copy-audio      不输出音源文件 (默认会转成 OGG 一起放进曲名文件夹)
    --no-trim-audio      不裁音频末尾冗余的部分 (默认会裁, 见下面的「音源处理」)
    --trim-tail SEC      裁尾时最后一个音符之后保留几秒余韵, 默认 3
    --quiet              不打印摘要
    --forget-out-dir     忘掉图形界面记住的输出文件夹和谱面目录 (下次弹窗从头选)

音源处理（默认行为）:
    输出**一律是 OGG(Vorbis)**, 不管源是 mp3 / ogg / m4a / flac / wav:
      · 源本身是 .ogg  -> 原样拷贝(不重编码)
      · 其它格式       -> 用 ffmpeg 转成 OGG
    WAVE 字段写的就是那个 .ogg 的文件名, 所以「谱面 + 音频」丢进模拟器就能直接出声。
    挑哪一首音源: ① .osu 里 AudioFilename 点名的那个 → ② --wave-ext 限定的扩展名
    → ③ 自动扫文件夹（mp3/ogg 等压缩格式优先, 同格式挑体积最大的, .wav 垫底,
       免得把 osu 谱面里那些 soft-hitnormal.wav 之类的打击音当成歌曲）。
    需要 ffmpeg: PATH 里能找到, 或者放在 C:\\ffmpeg\\bin\\ 下。找不到会如实报错, 不会静默降级。
    **尾部裁剪(默认开)**: osu 的音源往往是完整一首歌, 谱面打完后面还留一大段没音符的音乐,
    所以交付时顺手把尾巴裁掉 —— 只裁尾、**绝不碰开头**(开头一裁就得重算 OFFSET, 风险远大于收益)。
    裁点 = max(最后一个音符/连打终点 + 3s 余韵, DEMOSTART + 5s), 上限是原长; 能省的不足 3s 就不裁。
    需要裁的时候, 连「源是 ogg 就直接拷贝」也会升格成重新编码(Vorbis 有损转有损, 听感差异极小)。
    原音频文件不动, 裁坏了删掉重转即可。参数: --trim-tail 改余韵, --no-trim-audio 整个关掉。

时间/位置换算（来源: 参考/前人转换器（原始存档）.py 的 OFFSET 逻辑, 曾与其产物逐首对齐）:
    OFFSET = -(谱面起点在音频里的位置, 秒) + 全局微调;  谱面起点 = min(第一条红线, 首个音符)。
    前人的等价写法: 若首个音符早于第一条红线, 就在该音符处补一条「合成红线」,
    OFFSET 取计时点列表第 0 项的负千分之一秒 —— 两种写法结果相同。
    于是 TJA 时间轴满足: 音频位置(秒) = 谱面时刻(秒) - OFFSET。
    注意: 早先用「本家 9 份谱面」反推 OFFSET 的做法**已作废** —— 那批 osu 谱与本家谱
    很可能用的不是同一份音源, 这两个 OFFSET 之间没有可比性。现在只以前人转换器为准
    (那份前人脚本与它的 4 首产物是当年的对照物, 现已归档, 不再参与验收)。
    **全局微调(当前唯一一条 OFFSET 逻辑)**: 写出的 OFFSET 再整体减掉一个固定差值,
    当前是 **-30ms**(常数 `DEFAULT_OFFSET_SHIFT_MS`; 历史 -85 → -50 → 2026-11-12
    用户报「跟着歌打普遍偏早」后改为 -30ms)。它只改头部 `OFFSET:` 那一行, 不参与任何时刻换算,
    等价于手工改 .tja 的 OFFSET。要关掉用 `--offset-shift 0` / `--no-offset-shift`。
    ⚠ 刻意保持最简: 就是「减去一个常数」, 别再往这里叠信号处理或按谱面计算的东西。
    #MEASURE n/d 以全音符为单位; 小节由逗号分隔, 换行只是排版。

映射规则（已用数据集验证）:
    hitsound 无 whistle/clap 且无 finish  -> '1' 小咚
    hitsound 有 whistle(2) 或 clap(8)     -> '2' 小咔
    hitsound 有 finish(4)                 -> '3' 大咚
    hitsound 同时有 finish 与 whistle/clap -> '4' 大咔
    slider (滑条)                          -> '5' 连打 ... '8' 结束
        起点带 finish(4) 时用 '6' (大连打)
    spinner (转圈)                         -> '7' 气球 ... '8' 结束
    osu 的 SV 绿线                         -> #SCROLL (见 scroll_value())
    osu 的 BPM 红线                        -> #BPMCHANGE (并隐含 SV 复位成 1.0)
    osu 的 Kiai 区段                       -> #GOGOSTART / #GOGOEND

代码地图（按文件出现顺序, 便于直接跳到要改的那一段）:
    常量与阈值   音源格式、尾部裁剪、网格候选表、气球阈值、OFFSET 常数 —— 每条都写明来历
    小工具       read_text / fnum / safe_name / 乱码判据 / 编码降级 / 音频交付
    Timing       osu 计时点时间轴(红线 BPM+小节 / 绿线 SV / Kiai), 查询一律二分
    parse_osu    .osu -> (meta, timing, 音符/连打/气球)
    难度档位     DIFF_PROFILES / set_profile —— 两个入口唯一的行为差异, 高难版与低难版都改这里
    网格         _cell_index(唯一的拍->格换算) / _grid_fits / _cmd_collapse /
                 _note_collapse / _bar_subdiv / choose_grid
    主流程零件   collect_events / board_origin / balloon_boost / place_* /
                 split_fine_bars(把网格过细的小节二分) /
                 render_body / render_head / write_tja / deliver_audio
    load/layout  load_chart(解析+定起点, 不排版) / layout_chart(切小节+排版) —— 拆成两段
                 是为了多难度: 几张谱先各自解析、统一起点, 再各自排版
    星级         star_from_sr / star_from_db(osu!.db 缓存, 权威) / osu_db_paths
    convert      单难度编排: 解析 -> 定起点 -> 切小节 -> 排版 -> 写盘 -> 出音源
    convert_multi 多难度编排: N 张谱 -> 一个 .tja(文件头写一次, 每段各写一份 COURSE 头)
    convert_batch 批量编排: 按歌分组 -> 每首歌各调一次 convert_multi
    GUI / CLI    gui_flow(回调注入, 可脱机测试) / run_gui / main
    谱面浏览器   scan_osu_maps(扫 Songs, 线程池 + 缓存) / filter_map_rows(整串优先再逐词) /
                 MapBrowserDialog(搜索·排序·多选) / browse_maps(给 run_gui 用)
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import os
import queue
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction

ONP_DON, ONP_KATSU, ONP_DON_DAI, ONP_KATSU_DAI = '1', '2', '3', '4'
ONP_RENDA, ONP_RENDA_DAI, ONP_BALLOON, ONP_END = '5', '6', '7', '8'

OSU_NOTE_CIRCLE, OSU_NOTE_SLIDER, OSU_NOTE_SPINNER = 1, 2, 8

EPS = 1e-6

# 音源候选扩展名, 顺序即「像不像歌曲」的优先级: 压缩格式在前, 未压缩的 .wav 垫底
# (osu 谱面文件夹里常有一堆 soft-hitnormal.wav 之类的打击音, 不能把它们当歌曲)
AUDIO_EXTS = ('.mp3', '.ogg', '.m4a', '.opus', '.aac', '.flac', '.wav')

# 交付出去的音频**一律**是 OGG —— 不管源是 mp3 / ogg / m4a / wav。
# 编码用 Vorbis 而不是 Opus: 太鼓模拟器(OpenTaiko / TJAPlayer3)底层是 Bass,
# 认 OGG 容器里的 Vorbis, 不认 OGG 容器里的 Opus。
AUDIO_OUT_EXT = '.ogg'
OGG_QUALITY = 6                     # libvorbis -q:a 6 ≈ 192kbps, 对本家谱面足够

# -------------------------------------------------------------- 尾部裁剪: 裁掉冗余的音乐尾巴
# osu 的音源通常是**完整一首歌**, 而谱面往往打完就完了 —— 后面留着一大段没音符的
# 音乐(尾奏/淡出/静音)。本家谱面的 .ogg 一般刚好覆盖到最后一个音符, 所以交付时顺手裁掉。
#
# ★ **只裁尾巴, 绝不碰开头**: 裁开头会改变「音频零点」, 等于必须重算 OFFSET,
#   一旦算错整首谱面全歪, 收益却只有几秒。裁尾巴对谱面零影响 ——
#   OFFSET(谱面起点)、DEMOSTART(预览点)、WAVE(文件名)全都在前部。
#
# 裁点 = max(末事件 + TRIM_TAIL_MS, DEMOSTART + TRIM_DEMO_GUARD_MS), 上限是音频原长。
#   · 末事件 = 谱面里最后一个能发声的东西的**结束**时刻(连打/气球的终点, 不是起点),
#     这是硬下限 —— 任何情况下都不许裁到它前面;
#   · +3s 余韵: 让尾音(鼓/镲/钢琴延音)自然收干净, 不出现「咔嚓」断音。
#     用户口径(2026-11-14): 先按 3s 做, 试听不够再调;
#   · DEMOSTART + 5s: 预览点后面总得留得下东西, 否则选曲试听按下去立刻无声。
# 能省的不足 TRIM_MIN_GAIN_MS 就整个跳过 —— 不做「裁 1 秒、重编码一遍」的亏本买卖。
#
# ⚠ 代价: 裁剪必须重新编码。源是 .ogg 时本来走「直接拷贝不损失」的捷径, 需要裁的时候
#   会升级成 libvorbis 再压一遍(听感差异极小, 但不是无损)。原文件不动, 裁坏了删掉重转即可。
TRIM_TAIL_MS = 3000.0               # 末事件之后保留的余韵
TRIM_DEMO_GUARD_MS = 5000.0         # 预览起点之后至少保留这么久
TRIM_MIN_GAIN_MS = 3000.0           # 少于这么多就不裁(不值得重编码)
FFMPEG_HINTS = (                    # PATH 里找不到时按这些位置再试
    r'C:\ffmpeg\bin\ffmpeg.exe',
    r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
    r'C:\ProgramData\chocolatey\bin\ffmpeg.exe',
)


def find_ffmpeg() -> str:
    """找 ffmpeg 可执行文件; 找不到返回 ''(调用方负责如实报错)。"""
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    for p in FFMPEG_HINTS:
        if os.path.isfile(p):
            return p
    return ''


_BAD_NAME_CHARS = '<>:"/\\|?*'


def safe_name(name: str, fallback: str = 'Untitled', limit: int = 80) -> str:
    """把曲名变成「Windows 上合法、不会带路径」的文件夹名 / 文件名。

    Windows 不允许 <>:"/\\|?* 与控制字符; 结尾的 '.' 和空格也会被系统吃掉(导致
    明明写了这个名字却找不到文件) —— 一并削掉。连续空白压成一个, 过长截断。
    """
    s = ''.join('_' if (c in _BAD_NAME_CHARS or ord(c) < 32) else c for c in (name or ''))
    s = ' '.join(s.split()).strip().strip('.')
    s = s[:limit].rstrip(' .')
    return s or fallback


# -------------------------------------------------------------- 曲名 / 曲师的「乱码」兜底
# .osu 里一对字段: Title / Artist 是**罗马音**(纯 ASCII 居多),
# TitleUnicode / ArtistUnicode 是**原名**(日文/中文/带符号)。默认用原名那栏。
#
# 但有些老谱面的 Unicode 字段**被写坏了**, 而且是坏在源文件里、还原不了:
# 实测 `pa-o-mu99999 - Bobobo-bo Bo-bobo` 那份, TitleUnicode 写成
# `忙忙忙ー忙・忙ー忙忙`(真名 `ボボボーボ・ボーボボ`, 每个 ボ 都成了「忙」),
# ArtistUnicode 写成泰文 `ผ้าอ้อม99999`。穷举 24 种编码的「A 编码 -> B 解码」
# 组合(含 cp932/gbk/gb18030/big5/cp949/cp874/latin1/utf-8/euc-jp/euc-kr…),
# 对这两个串**零命中**(工具 .workbuddy/tmp/_moji.py) —— 所以不能"修", 只能改用它旁边
# 那栏没坏的名字。用户口径: **默认原名, 判出乱码才退到罗马音。**

# 太鼓谱面的曲名/曲师里不会出现的文字系统 —— 出现就说明字段被写坏了。
# 注意只列「明确不属于日/中/英」的, 符号(♪ ★ ☆ ・ ー)一律不碰。
_MOJIBAKE_SCRIPTS = (
    (0x0E00, 0x0E7F),      # 泰文
    (0x0E80, 0x0EFF),      # 老挝文
    (0x1000, 0x109F),      # 缅甸文
    (0x1780, 0x17FF),      # 高棉文
    (0x0900, 0x097F),      # 天城文
    (0x0980, 0x09FF),      # 孟加拉文
    (0x0B80, 0x0BFF),      # 泰米尔文
    (0x0D00, 0x0D7F),      # 马拉雅拉姆文
    (0x0C00, 0x0C7F),      # 泰卢固文
    (0xAC00, 0xD7AF),      # 韩文音节
    (0x1100, 0x11FF),      # 韩文字母
    (0x0400, 0x04FF),      # 西里尔
    (0x0590, 0x05FF),      # 希伯来
    (0x0600, 0x06FF),      # 阿拉伯
    (0x0530, 0x058F),      # 亚美尼亚
    (0x10A0, 0x10FF),      # 格鲁吉亚
)
# 「锟斤拷 / 烫烫烫」家族 + UTF-8 被当 GBK 解留下的固定串。
_MOJIBAKE_SEQS = ('锟斤拷', '烫烫烫', '屯屯屯', 'ï»¿', 'â€', 'Ã©', 'Ã¢', 'Ã¤', 'Ã¶', 'Ã¼')


def _is_letter_kana(c: str) -> bool:
    """真·假名(平假名 + 片假名), **不含**长音符 ー 与中黑点 ・ —— 那两个连汉字后面也能写。"""
    return '\u3041' <= c <= '\u3096' or '\u30a1' <= c <= '\u30fa'


def looks_mojibake(s: str):
    """判断这个「展示名」是不是被写坏了。返回 (是否, 一句话依据)。

    只认三种**形状证据**, 不猜原文(猜不出来, 见上面那段说明):
      ① 出现太鼓谱面不可能有的文字系统(泰文/韩文/西里尔/阿拉伯…);
      ② 有「Ã + 0x80~0xBF」这种 UTF-8 被按西欧编码解开的痕迹, 或锟斤拷家族;
      ③ 带着长音符 ー(以及 ≥2 个分隔符)、却一个假名都没有, 而那些方块字本该是片假名。
    ③ 是这份 Bobobo 的形态: 片假名被整体替换成了同一个汉字。
      ⚠ ③ 刻意要求「必须有 ー」且「分隔符 ≥2」: `東京・大阪` 这种全汉字+中黑点是合法标题,
        只有中黑点不算证据; 真正的全汉字标题也极少连写两个长音符。
    """
    s = (s or '').strip()
    if not s:
        return False, ''
    for c in s:
        o = ord(c)
        for lo, hi in _MOJIBAKE_SCRIPTS:
            if lo <= o <= hi:
                return True, '含有太鼓谱面不该出现的文字(泰文/韩文/西里尔一类)'
    for i in range(len(s) - 1):
        if s[i] in 'ÃÂ' and 0x80 <= ord(s[i + 1]) <= 0xBF:
            return True, '有 UTF-8 被按西欧编码解开的痕迹(Ã/Â 后接控制区字符)'
    for seq in _MOJIBAKE_SEQS:
        if seq in s:
            return True, '含已知乱码串 %s' % seq
    seps = s.count('\u30fc') + s.count('\u30fb')
    if '\u30fc' in s and seps >= 2 and not any(_is_letter_kana(c) for c in s) \
            and any('\u4e00' <= c <= '\u9fff' for c in s):
        return True, '有长音符/中黑点却一个假名都没有, 汉字位置本该是片假名'
    return False, ''


def pick_display_name(meta: dict, plain_key: str, uni_key: str,
                      override=None, allow_fallback: bool = True):
    """选一个显示用的名字。返回 (值, 提示语)。

    默认用原名(…Unicode); 判出乱码才退到罗马音那栏(没有 Unicode 后缀的那栏)。
    退不了(罗马音为空 / 同样可疑)就保留原名并如实说明 —— 不做无声的替换。
    """
    if override:
        return override, ''
    uni = (meta.get(uni_key) or '').strip()
    plain = (meta.get(plain_key) or '').strip()
    bad, why = looks_mojibake(uni)
    if not bad:
        return (uni or plain), ''
    if not allow_fallback:
        return (uni or plain), '%s 疑似乱码(%s), 按 --keep-original-names 保留原样' % (uni_key, why)
    plain_bad, _ = looks_mojibake(plain)
    if plain and not plain_bad:
        return plain, '%s 疑似乱码(%s), 已改用罗马音 %s = %s' % (uni_key, why, plain_key, plain)
    if not plain:
        return uni, '%s 疑似乱码(%s), 但没有 %s 可退, 只能保留原样' % (uni_key, why, plain_key)
    return uni, '%s 与 %s 都疑似乱码(%s), 只能保留原样' % (uni_key, plain_key, why)


def resolve_encoding(encoding: str, *texts) -> tuple:
    """决定最终写盘用哪种编码, 返回 `(实际编码, 提示语)`。

    首选仍是调用方给的那个(默认 cp932 —— 本家与旧版 TJAPlayer3 的惯例, 与官方
    谱面一致)。只要有一处编不出来(泰文 / 简体中文 / emoji…), 就把**整份文件**
    降级成 UTF-8 **带 BOM**: BOM 让记事本、.NET StreamReader、Hnx8 编码探测都能
    认出 UTF-8, OpenTaiko 自带的官方谱面本身就是 UTF-8+BOM。

    ⚠ **绝不写 "?"** —— 那是静默的数据丢失, 用户看到的「乱码」就是这么来的。
    ⚠ 必须放在 plan_audio() 之前调用: WAVE 里的音频文件名也受编码影响。
    提示语为空 = 没降级。调用方负责把非空的提示语打给用户。
    """
    try:
        ''.join(t or '' for t in texts).encode(encoding)
    except (UnicodeEncodeError, LookupError):
        if encoding.lower() in ('utf-8', 'utf-8-sig'):
            # 已经是 Unicode 编码还编不出来(只会是代理对残留), 换编码救不了
            return encoding, '标题/曲师里有 %s 编不了的字符, 已写成 "?"' % encoding
        return 'utf-8-sig', ('标题/曲师里有 %s 编不了的字符, 已自动改用 UTF-8(带 BOM) 输出'
                             % encoding)
    return encoding, ''


def _transcode_ogg(src: str, dst: str, trim_to_ms: float = None) -> None:
    """用 ffmpeg 把任意音频转成 OGG/Vorbis; 失败抛 RuntimeError(带 ffmpeg 的原话)。

    `trim_to_ms` 非空时顺手把音频截到这个长度(毫秒) —— 尾部裁剪就走这条路:
    源即使是 .ogg 也要重新编码, 所以它和「拷贝」的取舍在 plan_trim() 里算好。
    """
    ff = find_ffmpeg()
    if not ff:
        raise RuntimeError('找不到 ffmpeg, 无法把音源转成 OGG'
                           r'(装一个 ffmpeg 放进 PATH, 或放到 C:\ffmpeg\bin\)')
    cmd = [ff, '-y', '-hide_banner', '-loglevel', 'error', '-i', src,
           '-vn', '-map_metadata', '-1']        # 丢掉封面图与标签, 少一类播放器兼容问题
    if trim_to_ms:
        # -t 是**输出**时长(从流的第一个采样算), 所以这就是「只取前 N 秒」= 砍掉尾巴。
        # 放在输出选项里, 不要塞到 -i 前面, 否则会被当成输入侧的限时。
        cmd += ['-t', '%.3f' % (trim_to_ms / 1000.0)]
    cmd += ['-c:a', 'libvorbis', '-q:a', str(OGG_QUALITY), dst]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0 or not os.path.isfile(dst) or os.path.getsize(dst) == 0:
        lines = (p.stdout or b'').decode('utf-8', 'replace').strip().splitlines()
        raise RuntimeError('ffmpeg 转换失败: %s' % (lines[-1] if lines else '未知错误'))


def find_ffprobe() -> str:
    """找 ffprobe; 找不到返回 ''。先查 PATH, 再从 ffmpeg 的同级目录推。"""
    exe = shutil.which('ffprobe')
    if exe:
        return exe
    ff = find_ffmpeg()
    if ff:
        cand = os.path.join(os.path.dirname(ff),
                            'ffprobe.exe' if os.name == 'nt' else 'ffprobe')
        if os.path.isfile(cand):
            return cand
    return ''


def probe_audio_ms(path: str) -> float:
    """音频总时长(毫秒)。拿不到就返回 0.0 —— 调用方据此放弃裁剪, 而不是报错。

    ffprobe 优先; 没装 ffprobe 就退回解析 `ffmpeg -i` 的 stderr 里那行
    `Duration: 00:02:51.04`, 保证「有 ffmpeg 就能裁」。
    注意 ffprobe 的 format/duration 对某些容器可能带小数秒, float() 直接能吃。
    """
    try:
        pb = find_ffprobe()
        if pb:
            p = subprocess.run(
                [pb, '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=nw=1:nk=1', path],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            s = (p.stdout or b'').decode('utf-8', 'replace').strip()
            if p.returncode == 0 and s:
                v = float(s)
                if v > 0:
                    return v * 1000.0
        ff = find_ffmpeg()
        if not ff:
            return 0.0
        p = subprocess.run([ff, '-hide_banner', '-i', path],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        txt = (p.stdout or b'').decode('utf-8', 'replace')
        m = re.search(r'Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)', txt)
        if m:
            return ((int(m.group(1)) * 60 + int(m.group(2))) * 60
                    + float(m.group(3))) * 1000.0
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return 0.0


def plan_trim(audio_src: str, last_event_ms: float, demo_ms: float,
              tail_ms: float = None, min_gain_ms: float = None,
              enabled: bool = True) -> dict:
    """决定这首要不要裁尾(只算, 不动文件)。

    返回 {'action', 'orig_ms', 'cut_ms', 'gain_ms', 'note'}
      action = 'trim'  照 cut_ms 截断
               'skip'  无需裁: 本来就贴合 / 省得太少 / 读不到时长(看 note)
               'off'   调用方关掉了
    """
    if tail_ms is None:
        tail_ms = TRIM_TAIL_MS
    if min_gain_ms is None:
        min_gain_ms = TRIM_MIN_GAIN_MS
    res = {'action': 'skip', 'orig_ms': 0.0, 'cut_ms': 0.0, 'gain_ms': 0.0, 'note': ''}
    if not enabled:
        res['action'], res['note'] = 'off', '按 --no-trim-audio 不裁剪尾部'
        return res
    orig = probe_audio_ms(audio_src) if audio_src else 0.0
    if orig <= 0:
        res['note'] = '读不到音频时长, 不裁剪'
        return res
    res['orig_ms'] = orig
    # 两条线取大的: 一是给尾音留余韵, 二是别把预览点后面裁空。
    cut = max(last_event_ms + tail_ms, demo_ms + TRIM_DEMO_GUARD_MS)
    res['cut_ms'] = min(cut, orig)
    res['gain_ms'] = max(0.0, orig - res['cut_ms'])
    if res['gain_ms'] < min_gain_ms:
        # 两种情况分开说, 否则「尾部只多 0 ms」这种话会让人以为算错了:
        #   · 裁点已经越过音频末尾 → 本来就没冗余, 无需裁;
        #   · 裁点还在音频内部, 但只能省一点点 → 不值得为它重编码一遍。
        if cut >= orig:
            res['note'] = '尾部余量不足 %g s, 无需裁剪' % (min_gain_ms / 1000.0)
        else:
            res['note'] = '只能省 %.1f s, 不值得重编码一次' % (res['gain_ms'] / 1000.0)
        return res
    res['action'] = 'trim'
    return res


# -------------------------------------------------------------- 小工具

def read_text(path: str) -> str:
    """读文本文件, 依次尝试 utf-8-sig / utf-8 / cp932, 全失败再带替换字符解。

    .osu 名义上是 UTF-8, 但老谱面常混着 cp932 写出来的元数据; 逐个试比「猜一个
    编码」稳, 也保证不会因为一处坏字节让整份谱面读不出来。
    """
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-8', 'cp932'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def fnum(x: float, nd: int = 6) -> str:
    """把浮点数写成 TJA 里好看的样子: 最多 nd 位小数, 去掉尾随的 0 与小数点。

    `-0.000000` 会写成 `0` 而不是 `-0` —— 负零在 TJA 里没有意义, 却容易让人
    以为数值算反了。
    """
    s = ('%.*f' % (nd, x)).rstrip('0').rstrip('.')
    return '0' if s in ('', '-0') else s


def beats_to_measure(beats: float):
    """把「以四分音符为单位的拍数」写成 TJA 的 #MEASURE n/d (n/d 以全音符为单位)。

    **必须精确**: 写出的 #MEASURE 就是播音器据以推进时间轴的依据, 每个小节差一点点
    会一路累积, 所以这里一律如实转写、不做四舍五入。

    (「把小节长度变整齐」这件事**不在这里做**, 而在上游 restore_red_grid() 里把红线
    时刻本身还原到 1/4 拍网格上。红线还原之后, 这里量出来的拍数本来就已经是 1/4 拍的
    整数倍 —— 于是自然落成 4/4、9/16 这类写法, 不需要任何舍入。)

    整数拍时按本家惯例写成 n/4 (本家谱面里 4/4、6/4、5/4、3/4、2/4 都是这个写法)。
    """
    if beats >= 1.0 and abs(beats - round(beats)) < 1e-9:
        return int(round(beats)), 4
    whole = Fraction(beats / 4.0).limit_denominator(200000)
    return whole.numerator, whole.denominator


# -------------------------------------------------------------- 红线时刻的「网格还原」(默认开启)
# 两个格式最大的差别: osu 把事件**撒在时间轴上**, TJA 把事件**摆在小节线网格上**。
# 所以转换的核心动作就是「还原」—— 把时间轴上量出来的长度, 还原成音乐网格上的刻度。
#
# 要还原什么: 红线(TimingPoint)之间的间隔。它是 osu 里唯一的"结构"信息。
#   * osu 把红线时刻存成**整数毫秒**, msb(每拍毫秒)又只有 6 位小数, 于是一段真值
#     4 拍的红线区间会被量成 3.999 拍 —— 0.33 毫秒的取整噪声。若照实写成精确分数,
#     就是 `#MEASURE 167999/168041`(分母六位数), 而音乐上它明明就是 4 拍。
#   * 实测 4 首语料(osu 谱 + 对应本家谱): **红线段 100% 落在 1/4 拍网格上**
#     (最大偏差 0.86ms; Nivalis 两段例外见 DUP_RED_MS), 本家写出的小节长
#     (4/4、5/4、9/8、n/16…) 也全是 1/4 拍的整数倍。所以「1/4 拍」就是真实的音乐网格。
#
# 关键: **链式**吸附 —— 第 i 条红线的位置 = 上一条**已吸附**红线 + k×单位拍。
#   round() 把每段的取整噪声就地吃掉, 误差只在"这一段"里(毫秒量级), **不逐段累积**。
#   反面做法是"只改声明出来的小节长、不改红线自身位置"(旧 `--measure-snap`): 声明与
#   真实不符, 每段欠一点点, 几十段就累积成十几毫秒的整体漂移 —— 那正是被废弃的原因。
# ⚠ 顺序**有意义**: 链式还原按顺序试, 第一个能在 12ms 内命中的单位就被采用。
#   所以粗的单位必须排在前面 —— 一条本来就在 1/4 拍网格上的红线, 要优先被 1/4 接走,
#   而不是被某个更细的单位「以更小的 k」抢走(那会把它挪到别处, 并让下游整条链跟着平移)。
#   1/5、1/7(用户 2026-09-22 要求): 五连音 / 七连音段落的小节边界。
#   它们排在 1/3、1/6 之后、1/12 之前 —— 比 1/4 细, 但不是最细的兜底档。
GRID_UNITS = (Fraction(1, 4), Fraction(1, 3), Fraction(1, 6), Fraction(1, 5),
              Fraction(1, 7), Fraction(1, 8), Fraction(1, 12), Fraction(1, 16))
GRID_TOL_MS = 12.0      # 偏差超过这个数就不吸(认定原谱真的不在网格上, 比如花式变速)
DUP_RED_MS = 5.0        # 相邻红线只差这么点 -> 视为同一条(osu 编辑残留)


def restore_red_grid(reds, units=GRID_UNITS, tol_ms: float = GRID_TOL_MS,
                     dup_ms: float = DUP_RED_MS):
    """把红线时刻还原到音乐网格上(链式)。

    reds 需已按时间排序。第一条红线不动 —— 它是谱面起点, 决定 OFFSET。

    单位从 1/4 拍起试(本家最常用), 吸不下再退到 1/3、1/6、1/5、1/7、1/8、1/12、1/16 拍
    (三连音/五连音/七连音/更细的网格), 顺序见 GRID_UNITS 上方的说明。
    偏差超过 tol_ms 就整段不动, 免得把花式变速掰弯。

    与上一条只差几毫秒的红线(如 Nivalis 的 `257 -> (2ms) -> 32.125`)属于 osu 编辑
    残留: **丢掉前一条、后一条继承它的位置**, 这样真正的变速(后者)不会因为丢掉前者
    而消失, 只损失几毫秒的过渡。

    返回 `(reds_new, shifts)`:
      reds_new 与 reds 同结构, 但时刻已还原;
      shifts   与 reds 等长, `shifts[i]` = 第 i 条红线被挪了多少毫秒。
      段内的内容(音符/绿线/Kiai)必须跟着搬同样的量, 见 make_seg_shifter()。
    """
    if not reds:
        return [], []
    out = [tuple(reds[0])]
    shifts = [0.0]
    for i in range(1, len(reds)):
        t, msb, meter, omit = reds[i]
        p_t, p_msb = reds[i - 1][0], reds[i - 1][1]
        delta = t - p_t
        if delta <= dup_ms:
            # 与上一条只差几毫秒(osu 编辑残留): 前一条作废, 后一条继承它的位置。
            # shifts 必须与**原始** reds 一一对应(下游按原始时刻做二分查找), 所以
            # 这一条也要补一个条目 —— 它并进上一条, 位移就等于搬到那个位置。
            prev_pos = out[-1][0]
            out[-1] = (prev_pos, msb, meter, omit)
            shifts.append(prev_pos - t)
            continue
        new_t = None
        for u in units:
            step = p_msb * float(u)
            if step <= EPS:
                continue
            k = int(round(delta / step))
            if k < 1:
                continue
            if abs(delta - k * step) <= tol_ms:
                new_t = out[-1][0] + k * step
                break
        out.append((new_t if new_t is not None else t, msb, meter, omit))
        shifts.append((new_t - t) if new_t is not None else 0.0)
    return out, shifts


def make_seg_shifter(reds_raw, shifts):
    """返回 f(t): 把时刻 t 搬到「它所在那条红线段」被挪动的量上。

    为什么段内内容必须跟着搬: osu 里音符是**整数毫秒**, 它相对红线起点的偏移量也
    因此是整数毫秒 —— 这正是排版网格能取到 1/16 拍这种粗格的原因。红线一挪(哪怕
    只挪 0.8ms), 偏移量就变成小数, 音符落到网格外, choose_grid 只好把整行从
    1/16 拍加密到 1/48 拍(实测 Vrykolakas 有 56 个小节被这样加密过)。
    把整段内容按同一个量平移, 偏移量保持不变 —— 于是既拿到了干净的小节线,
    排版密度又和没还原时一模一样。
    """
    times = [r[0] for r in reds_raw]
    if not shifts:
        return lambda t: t

    def f(t):
        i = bisect.bisect_right(times, t + EPS) - 1
        return t + shifts[i if i >= 0 else 0]
    return f




def note_char_from_hitsound(snd: int) -> str:
    """osu 的判定音位掩码 -> 本家音符字符。

    bit0 普通 / bit1 哨声 / bit2 重音 / bit3 拍手。太鼓里哨声与拍手都算**咔**,
    重音算**大**, 所以「咔」的判据是 `snd & 10`(= 2|8) **非零**。
    ⚠ 写成 `snd == 10` 是错的: 那样同时带重音与拍手(4|8=12)的大咔会被判成咔。
    """
    dai = bool(snd & 4)
    katsu = bool(snd & 10)          # whistle(2) 与 clap(8) 都算咔
    if dai:
        return ONP_KATSU_DAI if katsu else ONP_DON_DAI
    return ONP_KATSU if katsu else ONP_DON


def guess_course(version: str) -> str:
    """按 .osu 的 `Version` 字段猜难度名(`--course auto` 才用)。

    默认行为是**一律 Oni**(交付口径), 这里是「照原谱标注」的备选路径。
    从最难往下试, 先命中先返回; 都不像就按 Oni 处理。
    """
    v = (version or '').lower()
    if any(k in v for k in ('inner oni', 'inner', 'ura', 'edit', '里', '裏')):
        return 'Edit'
    if any(k in v for k in ('oni', '鬼')):
        return 'Oni'
    if any(k in v for k in ('hard', 'muzukashii', '難しい')):
        return 'Hard'
    if any(k in v for k in ('normal', 'futsuu', '普通')):
        return 'Normal'
    if any(k in v for k in ('easy', 'kantan', '簡単')):
        return 'Easy'
    return 'Oni'


DEFAULT_COURSE = 'Oni'          # 交付默认一律魔王难度(--course auto 才回到按 Version 猜)
# 星数兜底值: TJA 里没有独立的「星数」字段, LEVEL 就是模拟器里显示的 ★×N。
# 正常路径是「SR × 2 四舍五入」(见 star_from_sr); 连 SR 都拿不到(既不在 osu!.db
# 里、又没装 rosu-pp-py)才用它。
DEFAULT_LEVEL = 10

# -------------------------------------------------------------- 多难度(一个 TJA 装多张谱)
# osu 的多难度是「一个文件夹 + 一份音源 + 多个 .osu」; 本家是「一个 .tja 里若干段」——
# 每段是 `COURSE/LEVEL/BALLOON` + `#START ... #END`, 而 TITLE/BPM/WAVE/OFFSET/DEMOSTART
# 只在文件最前面写一次(见 本家谱面/3Q-4U-AC00/3Q-4U-AC00.tja)。
#
# 难度方案**分两档**(用户 2026-11-15 定高难版, 2026-11-18 追加低难版)。两档都是
# 「星数越高 -> 难度名越高」, 区别只是**从哪一档开始往下填**:
#
#   high —— 难谱版(默认, 交付入口 osu2tja2.py):
#     1 张 -> Oni  |  2 张 -> Edit / Oni  |  3 张 -> Edit / Oni / Hard  |  4 张以上报错
#     最低只到 Hard: 这种高难谱面冒充普通/简单, 会撞上「简单/普通判定比 osu 宽得多」,
#     变成判定不一致的假难度。
#
#   low —— 低难版(交付入口 osu2tja_low.py):
#     1 张 -> Oni               |  2 张 -> Oni / Hard
#     3 张 -> Oni / Hard / Normal  |  4 张 -> Oni / Hard / Normal / Easy
#     5 张 -> Edit / Oni / Hard / Normal / Easy   (= 模拟器的全部 5 个难度)
#     低难版本来就是给低难度谱准备的, 「判定宽」正是它要的, 所以普通/简单照用。
#
# ★ 顺序由 **星数** 决定(用户 2026-11-15 定): 星数高的那张拿更高的难度名; 只有两张谱
#   **星数(★N)一模一样**、屏幕上分不出谁更难时, 才让用户自己定先后(见 order_by_star)。
# 硬约束: 模拟器最多只认 5 个难度(TJA 的 COURSE 只有 Easy/Normal/Hard/Oni/Edit 五档),
#   多写的那些段落根本读不到 —— 所以两档都不超过 5 张(见 TJA_MAX_COURSES)。
# 星数不再固定: LEVEL = round(osu!taiko SR(NM) × 2), 见 star_from_sr()。
#
# 里谱(Ura / Inner Oni)在 TJA 里必须写成 `COURSE:Edit`: 本家/模拟器的 COURSE 只认
# Easy/Normal/Hard/Oni/Edit, 没有 "Ura" 这个关键字(taiko-web 额外认 Ura, 但 OpenTaiko/
# TJAPlayer3 不认, 所以统一写 Edit)。
#
# 表里的值 = 「第 0 位拿什么难度名」, 而第 0 位就是**星数最高的那张**。所以这张表只用
# 来表示「从哪一档往下填」, 它本身不负责排序 —— 排序永远是 order_by_star()。
DIFF_PROFILES = {
    'high': {1: ('Oni',),
             2: ('Edit', 'Oni'),
             3: ('Edit', 'Oni', 'Hard')},
    'low': {1: ('Oni',),
            2: ('Oni', 'Hard'),
            3: ('Oni', 'Hard', 'Normal'),
            4: ('Oni', 'Hard', 'Normal', 'Easy'),
            5: ('Edit', 'Oni', 'Hard', 'Normal', 'Easy')},
}
PROFILE_LABEL = {'high': '难谱版', 'low': '低难版'}

PROFILE = 'high'                        # 当前档位; 低难版入口启动时切到 'low'
MULTI_COURSES = DIFF_PROFILES[PROFILE]
MAX_INPUTS = max(MULTI_COURSES)         # 本档最多几张(high=3, low=5)
TJA_MAX_COURSES = 5                     # 模拟器上限, 只用在报错文案里

# 提示文案里的难度中文名。⚠ 和 COURSE_ALIASES 是两张不同的表: 那张是「用户输入怎么认」,
# 这张是「我们怎么往屏幕上写」。
COURSE_CN = {'Easy': '简单', 'Normal': '普通', 'Hard': '困难',
             'Oni': '鬼', 'Edit': '里'}

# 桌面端启动用的两个名字, 只在提示文案里出现。低难版入口会把它们改成自己那一套。
LAUNCHER_BAT = 'osu2tja2.bat'
SCRIPT_NAME = 'osu2tja2.py'


def set_profile(name: str = 'high') -> None:
    """切换难度方案: `'high'`(难谱版) / `'low'`(低难版)。

    ⚠ 必须在**任何转换或开窗之前**调用 —— 它改的是模块级常量, 已经算好的难度方案、
      已经摆到界面上的文案都不会跟着变。低难版入口 `osu2tja_low.py` 启动时调一次。
    """
    global PROFILE, MULTI_COURSES, MAX_INPUTS
    key = (name or 'high').strip().lower()
    if key not in DIFF_PROFILES:
        raise ValueError('未知的难度方案 %r(只有 %s)'
                         % (name, ' / '.join(sorted(DIFF_PROFILES))))
    PROFILE = key
    MULTI_COURSES = DIFF_PROFILES[key]
    MAX_INPUTS = max(MULTI_COURSES)


def profile_plan_text(indent: str = '  · ') -> str:
    """「1 张 → 鬼 / 2 张 → …」的说明行。报错和 --help 共用, 免得两处说法对不上。"""
    rows = []
    for n in sorted(MULTI_COURSES):
        rows.append('%s%d 张 → %s' % (
            indent, n, ' / '.join(COURSE_CN.get(c, c) for c in MULTI_COURSES[n])))
    return '\n'.join(rows)

# 星数折算: SR × 2 后四舍五入(用户 2026-11-15 定)。只影响 LEVEL 这一行。
SR_PER_STAR = 2.0


def star_from_sr(sr) -> int:
    """osu!taiko 的 SR -> TJA 的 LEVEL(模拟器里显示的 ★×N)。SR × 2 四舍五入。"""
    return int(math.floor(float(sr) * SR_PER_STAR + 0.5))


# `--courses` 能认的写法(小写化后比对)。中文也认, 敲 `--courses 里,Oni` 比记英文顺手。
COURSE_ALIASES = {
    'oni': 'Oni', '鬼': 'Oni', '魔王': 'Oni',
    'hard': 'Hard', '困难': 'Hard', '難しい': 'Hard', 'muzukashii': 'Hard',
    'normal': 'Normal', '普通': 'Normal', 'ふつう': 'Normal', 'futsuu': 'Normal',
    'easy': 'Easy', '简单': 'Easy', '簡単': 'Easy', 'kantan': 'Easy',
    'edit': 'Edit', '里': 'Edit', '裏': 'Edit', 'ura': 'Edit',
    'inner': 'Edit', 'inner oni': 'Edit', 'inneroni': 'Edit',
}


# -------------------------------------------------------------- 解析 .osu

class Timing:
    """osu 的 TimingPoints 时间轴: 红线(BPM/小节) + 绿线(SV) + Kiai。

    三张表都按时刻升序:
      reds    (time, ms_per_beat, meter, omit)  —— BPM 与拍号, 决定小节边界
      greens  (time, sv)                        —— 绿线的 SV 倍率
      kiais   (time, kiai)                      —— GOGO 开关

    查询统一走二分查找(见 `_index()`); 三张表一旦**被整体替换或重排**
    (例如 `restore_red_grid()` 把红线搬到音乐网格上), 必须调用 `finalize()`
    重建索引, 否则查到的还是旧位置。
    """

    def __init__(self):
        # (time:int, ms_per_beat:float, meter:int, omit:bool)
        # omit = osu 编辑器的 "Omit first bar line"(effects 的 bit3) -> TJA #BARLINEOFF
        self.reds = []
        self.greens = []    # (time:int, sv:float)
        self.kiais = []     # (time:int, kiai:bool)
        # 以下三个是派生索引, 全部由 finalize() / 惰性访问生成
        self._red_times = None
        self._kiai_times = None
        self._sv_tl = None          # [(t, sv)] 有效 SV 时间轴
        self._sv_times = None

    def finalize(self):
        """在 reds / greens / kiais 定稿之后调用: 重建全部查询索引。"""
        self._red_times = [r[0] for r in self.reds]
        self._kiai_times = [x[0] for x in self.kiais]
        self.build_sv_timeline()

    def build_sv_timeline(self):
        """把红线与绿线合成一条「有效 SV」时间轴。

        ★ osu 的隐藏机制: **红线(uninherited 时机点)会把 SV 复位成 1.0**,
        除非同一时刻还挂着一条绿线。即「谁更靠后谁说了算; 红线开口时说的是 1.0」。
        原实现只按绿线查 SV, 红线处的复位被整个忽略了 —— One of Us 2:11
        (BPM 130 -> 260, 换 4/4, 只有红线没有绿线) 于是继续沿用上一段的 1.55,
        本家整段就比原谱快 55%。用户 2026-11-15 指出。

        顺带解决「绿线经 `restore_red_grid` 搬运后不再有序」的问题 —— 这里用字典
        合并再排序, 与输入顺序无关。
        """
        pts = {}
        for t, _bl, _m, _o in self.reds:
            pts[t] = 1.0          # 红线 = 复位到 1.0
        for t, sv in self.greens:
            pts[t] = sv           # 同刻的绿线覆盖红线(绿线优先)
        self._sv_tl = sorted(pts.items())
        self._sv_times = [p[0] for p in self._sv_tl]
        return self._sv_tl

    def _last_index(self, times, t: float) -> int:
        """times 里最后一个 <= t 的下标; 全都晚于 t 则返回 -1。"""
        return bisect.bisect_right(times, t + EPS) - 1

    def msb_at(self, t: float):
        """t 时刻生效的那条红线 (time, msb, meter, omit); t 早于第一条就用第一条。"""
        if not self.reds:
            raise ValueError('.osu 里没有任何红线(TimingPoints)，无法转换')
        if self._red_times is None:
            self._red_times = [r[0] for r in self.reds]
        i = self._last_index(self._red_times, t)
        return self.reds[i if i >= 0 else 0]

    def sv_at(self, t: float) -> float:
        """t 时刻生效的 SV(已含红线复位); t 早于所有计时点时按 1.0。"""
        if self._sv_tl is None:
            self.build_sv_timeline()
        i = self._last_index(self._sv_times, t)
        return self._sv_tl[i][1] if i >= 0 else 1.0

    def kiai_at(self, t: float) -> bool:
        """t 时刻是否处于 GOGO(Kiai) 段。"""
        if self._kiai_times is None:
            self._kiai_times = [x[0] for x in self.kiais]
        i = self._last_index(self._kiai_times, t)
        return self.kiais[i][1] if i >= 0 else False


def parse_osu(path: str, red_grid: bool = True):
    """读一个 .osu 谱面, 返回转换需要的全部原料。

    返回 dict:
      meta / diff     头部 [General]/[Metadata]/[Difficulty] 的键值(字符串)
      timing          已定稿的 Timing 时间轴
      circles         [(时刻, 音符字符)] —— hit circle, 字符由判定音决定
      rolls           [{'t','end','char'}] —— 滑条(连打), end 由长度和 SV 算出
      balloons        [{'t','end'}] —— spinner(气球/拨浪鼓)
      slider_mult     [Difficulty] SliderMultiplier, 决定整谱的视觉流速基准

    `red_grid=True`(默认) 会把红线时刻**还原到音乐网格**上, 并把段内的音符 / 绿线 /
    Kiai 按同一位移整体搬运 —— 见 restore_red_grid()。关掉它只用于「只想要 meta」的
    场合(例如 plan_audio 挑音源), 能省下整趟计时点解析。
    """
    txt = read_text(path)
    sec = None
    meta, diff = {}, {}
    tp_lines, obj_lines = [], []
    for raw in txt.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            sec = line[1:-1]
            continue
        if sec in ('General', 'Metadata', 'Difficulty'):
            if ':' in line:
                k, v = line.split(':', 1)
                (diff if sec == 'Difficulty' else meta)[k.strip()] = v.strip()
        elif sec == 'TimingPoints':
            tp_lines.append(line)
        elif sec == 'HitObjects':
            obj_lines.append(line)

    if meta.get('Mode', '0').strip() != '1':
        print('[警告] Mode 不是 1(taiko)，仍按 taiko 规则转换', file=sys.stderr)

    slider_mult = float(diff.get('SliderMultiplier', 1.4) or 1.4)

    timing = Timing()
    for line in tp_lines:
        ps = line.split(',')
        if len(ps) < 2:
            continue
        try:
            t = int(round(float(ps[0])))
            bl = float(ps[1])
            meter = int(float(ps[2])) if len(ps) > 2 else 4
            uninherited = (ps[6].strip() != '0') if len(ps) > 6 else (bl > 0)
            # effects 在字段 7; 只有 6 个字段的老格式里, 字段 6 就兼任 effects
            effects = int(float(ps[7])) if len(ps) > 7 else (int(float(ps[6])) if len(ps) > 6 else 0)
        except ValueError:
            continue
        if bl > 0 and uninherited:
            # effects 的 bit3 = 编辑器的 "Omit first bar line"(隐藏这条红线处的小节线)。
            # 这是 #BARLINEOFF 的**唯一正确来源** —— 早先按「小节短于 1 拍就隐藏」
            # 猜出来的启发式已废弃(用户 2026-09-21 指出它就在文件里写着)。
            timing.reds.append((t, bl, max(1, meter), bool(effects & 8)))
        elif bl < 0:
            timing.greens.append((t, -100.0 / bl))
        # Kiai 可以挂在任意计时点上(红线/绿线都行), 用 effects 的 bit0 表示。
        # effects 已经在上面的 try 里解析过 —— 那里失败会直接 continue, 不会再走到这。
        if len(ps) > 7:
            timing.kiais.append((t, bool(effects & 1)))

    timing.reds.sort(key=lambda x: x[0])
    timing.greens.sort(key=lambda x: x[0])
    timing.kiais.sort(key=lambda x: x[0])

    if red_grid:
        # ★ 核心一步: 把「时间轴上量出来的红线时刻」还原成「音乐网格上的刻度」。
        # 必须在归位音符/切小节之前做 —— 后面所有小节边界都由红线决定。
        _reds_raw = list(timing.reds)
        timing.reds, _shifts = restore_red_grid(_reds_raw)
        # 段内内容(音符/绿线/Kiai)跟着段首一起搬, 见 make_seg_shifter()。
        _move = make_seg_shifter(_reds_raw, _shifts)
        timing.greens = [(_move(t), v) for t, v in timing.greens]
        timing.kiais = [(_move(t), v) for t, v in timing.kiais]
    else:
        def _move(t):
            return t

    # 红线是整张谱的结构骨架(BPM/小节/时间轴), 一条都没有的 .osu 是坏文件。
    # 早点在这里拦下, 比让下游 `reds[0]` 抛 IndexError 更容易看懂。
    if not timing.reds:
        raise ValueError('.osu 里没有任何红线(TimingPoints)，无法转换')

    # 红线/绿线都已搬到「音乐网格」上, 现在才定稿索引(有效 SV 时间轴 + 查询索引)。
    timing.finalize()

    # --- 音符 ---
    # 这里先把时刻搬它所在红线段被挪动的量(_move), 后面所有判断(查 msb、查 SV、
    # 归位小节)都用搬过的时刻 —— 与已还原的红线/绿线保持同一套时间轴。
    circles, rolls, balloons = [], [], []
    for line in obj_lines:
        ps = line.split(',')
        if len(ps) < 4:
            continue
        try:
            # ⚠ 时刻列用 float 解析: 部分编辑器会写出 `1234.5678` 这种小数时刻,
            #   旧写法 int(ps[2]) 会抛 ValueError 然后被下面的 except 吞掉 ->
            #   整个音符**静默消失**(不报错, 只是谱面上少一条)。
            t = _move(int(round(float(ps[2]))))
            typ = int(ps[3]) & ~4            # 去掉 new-combo 位
            snd = int(ps[4]) if len(ps) > 4 else 0
        except ValueError:
            continue

        if typ & OSU_NOTE_CIRCLE:
            circles.append((t, note_char_from_hitsound(snd)))
        elif typ & OSU_NOTE_SLIDER:
            # 滑条时长 = 单程时长 * 折返次数
            try:
                slides = int(ps[6])
                length = float(ps[7])
            except (IndexError, ValueError):
                slides, length = 1, 0.0
            msb = timing.msb_at(t)[1]
            sv = timing.sv_at(t)
            one_span = (length / (slider_mult * 100.0)) * msb / sv if sv else 0.0
            rolls.append({
                't': t,
                'end': t + one_span * max(1, slides),
                'char': ONP_RENDA_DAI if (snd & 4) else ONP_RENDA,
            })
        elif typ & OSU_NOTE_SPINNER:
            try:
                end = _move(int(round(float(ps[5]))))   # 同上: 小数时刻也认
            except (IndexError, ValueError):
                end = t
            balloons.append({'t': t, 'end': max(end, t)})

    return {
        'meta': meta, 'diff': diff, 'timing': timing,
        'circles': circles, 'rolls': rolls, 'balloons': balloons,
        'slider_mult': slider_mult,
    }


def read_meta(src: str) -> dict:
    """只取 .osu 的头部字段(读失败返回 {})。

    挑音源 / 决定「曲名」文件夹名都只需要 meta, 不必解析整趟计时点与音符,
    所以这里固定 `red_grid=False`: 少一趟红线网格还原, 也避免为读一个曲名
    在解析失败时把整次转换拖挂 —— 拿不到就当没有, 由调用方兜底。
    """
    try:
        return parse_osu(src, red_grid=False)['meta']
    except Exception:
        return {}


# -------------------------------------------------------------- 小节切分

# 「每拍格数」候选值 —— 抄本家谱面的习惯。
# 实测 8 首本家 TJA、1113 个小节里只出现过 1/2/3/4/6/8/12/16/24 这些值
# (其中「每拍 4 格」占 692 个), 从没有「为了摆一条命令点把整行加密几十倍」的写法。
# 旧版按需升到 96/192 格, 结果同一串 1/6 音符在不同行里疏密差 16 倍, 预览完全不像原谱。
#
# 5 与 7(用户 2026-09-22 要求加入): 五连音 / 七连音在 osu 与太鼓里都极罕见, 但确实存在。
#   ⚠ 这是「音符的档位」—— 只决定音符落在哪一格。命令点(SV)不参与选档位,
#     见 choose_grid() 里「① 只用音符选档位」那一步。加这两档的代价只是「多试一次」: 落不下就跳过。
#   为什么不加 9/11/13: 九连音以上基本是「导出成 1/12 拍也能听出来」的量级, 且本家从不写。
NICE_SUBDIV = (4, 5, 6, 7, 8, 12, 16, 24, 32, 48, 64, 96, 192, 384)

# 「命令点可以借用的额外格宽」上限。命令点(SV/GOGO)的换值时刻允许被吸到最近的格上,
# 而不是逼着整个小节加密 —— 因为 SV 在谱面上不可见, 只影响它之后音符的流速(P1)。
# ⚠ 这里给的是**倍数**: 音符选出的格宽 cell 最多可以再细 CMD_EXTRA_FACTOR 倍去找一个
#   容纳命令点的档位; 再找不到就直接吸到最近的格, 不再加密。
#   实测(ON.UR.MARKS): 旧口径为了命令点精确落格, 总格数 13602 -> 32162(2.4 倍),
#   而按用户的验收次序, 这些格子在游戏里看不见 —— 不值得。
CMD_EXTRA_FACTOR = 2

# 命令点(SCROLL/GOGO)的落格容差, 单位毫秒。
# 旧值 30ms 会把命令点吸到「它所影响的音符那一格」之后 —— 实测 ON.UR.MARKS 有
# 749 个命令点晚了 26ms, 1430 个偏 >10ms, 逐音符「当时生效的 SCROLL」105 个与 osu
# 不符(= 那些音符在游戏里会以错误的流速飞过来)。
# 收紧到 8ms: 偏 >10ms 的 0 个, 不符 5 个; 收到 5ms: 不符 0 个。
# ⚠ 这个判据会把「渐变 SV」谱的格数推高(命令位置不对齐任何整齐格网), 但它是
#   choose_grid 里唯一能压住 SV 生效时刻误差的手段, 所以保留 —— 见 _cmd_collapse。
CMD_TOL_MS = 5.0

# 兜底加密时的硬上限(单个小节的格数)。本家语料里最密的小节是 1560 格,
# 这里留一倍余量。防止病态输入把一个小节撑到几万格。
FALLBACK_MAX_CELLS = 3072

# -------------------------------------------------------------- 气球(拨浪鼓)的「提前显示」补偿
# osu!taiko 有一个本家没有的显示机制: 气球在**极低 SV** 下滚得极慢, 游戏会把它
# 推迟到快被击打时才画出来。所以原作可以把一小节的气球配成 SV=0.01 —— 玩家看到
# 的是「气球突然出现、马上要打」。
#
# 本家 TJA 没有这个机制: `7` 从出现那一刻就挂在轨道上, 按 #SCROLL 慢慢爬 ——
# 极慢时等于「一个几乎不动的气球挡在屏幕上半首曲子」, 完全不是原作的手感。
#
# 补偿办法: 判据用**等效 BPM** = 当前 BPM × 该处 #SCROLL(= HS 倍率)。
#   osu 的滚速(px/秒) = 245 × HS × BPM/60, 所以「等效 BPM」就是「把 HS 折成 BPM」。
# 小于 BALLOON_MIN_EFF_BPM(5) 时, 说明这一段的滚动比「5BPM + 1HS」还慢,
# 那就把**气球整个持续区间**强制写成当前 BPM 下的 1HS(#SCROLL 1.0),
# 气球一结束立刻恢复原谱流速。
#   ⚠ 只动气球区间, 不碰别处; 区间内原本的绿线(渐变 SV 常把气球夹在中间)一律
#     让位 —— 否则会在气球中途把流速打回 0.01。
#   ⚠ 恢复值取气球**结束之后**那一刻的 osu 原值, 不是气球开始时的值。
BALLOON_MIN_EFF_BPM = 5.0

# -------------------------------------------------------------- OFFSET 常数
#
# ★ 当前 OFFSET 逻辑(2026-09-22 用户拍板, **就这一条, 刻意保持最简单**):
#
#       写出的 OFFSET = -谱面起点(秒) + DEFAULT_OFFSET_SHIFT_MS / 1000
#
#   也就是「照搬 osu 的谱面起点, 然后整体再减掉一个固定差值」。
#
#   历史取值: 用户拿转换器转了几首歌, 在本家模拟器里自己听、自己调, 报回来数据 ——
#       第 1 首: 我们写 -194ms, 实际 -279ms 最好  -> 差 -85
#       第 2 首: 我们写 -200ms, 实际 -284ms 最好  -> 差 -84
#   两首一致, 当时取整为 -85ms。
#   ★ 2026-11-12 调值轨迹: -85 -> **-50**(试玩后要求) -> **-30**(报「跟着歌打普遍偏早」,
#     = OFFSET 偏小, 往正方向加 20ms)。调值时只改这个常数, 不要动别处。
#
# ⚠ 它是「模拟器与 osu 之间的系统差」, 不是精度问题 —— 所以是一个常数, 不是
#   按谱面算出来的量。正因为如此, 它必须**可关、可覆盖**:
#       --offset-shift 0        关掉(回到原样), 用于排查
#       --offset-shift <ms>     换成别的值
#   如果将来发现不同模拟器/设备需要的差值不同, 那是用户侧的判定线延迟, 不要
#   再往这个常数里塞更多逻辑。
DEFAULT_OFFSET_SHIFT_MS = -30.0


def scroll_value(sv: float, scroll_base: float) -> float:
    """把 osu 的绿线 SV 折算成要写进 TJA 的 `#SCROLL` 值。

    osu!taiko 的实际滚动速度 ∝ SliderMultiplier × 绿线 SV, 而 TJA 只有一个数,
    所以乘上 `scroll_base`(= SliderMultiplier / 1.4); `scroll_base == 1.0`
    (即 SliderMultiplier 就是 osu 默认的 1.4) 时**原样返回**, 保证既有产物不变。
    乘完保留 4 位小数: 远超视觉可辨, 也避免写出 1.142857142857 这种长尾。
    """
    return sv if scroll_base == 1.0 else round(sv * scroll_base, 4)


def build_bars(origin: float, end_time: float, timing: Timing, base: int = 4,
               scroll_base: float = 1.0):
    """把 [origin, end_time] 切成小节, 返回 [bar, ...]。

    规则(用户 2026-09-21 确认, 已用 8 首本家谱面逐节交叉验证):
      * **每一条红线都是一个小节起点**, 不论 BPM 变没变 —— 这正是 osu 编辑器
        画小节线的规则; 照抄它, 本家的小节线才会和 osu 里看起来一样。
      * 一条红线给出的「标称小节长」= 它的 Meter 拍; 下一条红线把当前小节**截断**。
      * 红线 effects 的 bit3 (`& 8`) = 编辑器的 "Omit first bar line",
        输出 #BARLINEOFF(到下一条可见小节线再 #BARLINEON)。
      * 红线之间按 Meter 周期继续排自然小节, 直到下一条红线。

    `scroll_base` = osu `[Difficulty] SliderMultiplier` 归一化后的流速系数
    (详见 convert 里那段说明): 本家的 #SCROLL 只认一个数, 而 osu taiko 的实际
    滚动速度是「SliderMultiplier × 绿线 SV」, 所以这里乘上去。

    bar: start/end/beats/msb/meter/bpm/omit/scroll/kiai/cuts/events/fragment
    """
    reds = list(timing.reds)
    if origin < reds[0][0] - 1e-9:
        # 谱面起点早于第一条红线(首个音符更早) -> 补一条合成起点, 沿用后面那条的参数
        reds.insert(0, (origin,) + tuple(reds[0][1:]))

    bars = []
    for k, (t0, msb, meter, omit) in enumerate(reds):
        if t0 > end_time + 1e-9:
            break
        nxt = reds[k + 1][0] if k + 1 < len(reds) else None
        final = (nxt is None) or (nxt >= end_time + 1e-9)
        seg_end = end_time if final else nxt
        min_len = msb / 2.0                 # 短于半拍的人为碎节不要

        starts, b = [t0], t0
        while b + meter * msb < seg_end - 1e-9:
            b += meter * msb
            starts.append(b)
        # 最后剩的那一截太短时, 撤掉最后一条边界让上一小节吸收它 ——
        # 否则预览里会多出一行只有零点几拍的碎小节(旧版正是这么碎出 15 个
        # 「0.02 拍 = 7ms」的小节的)。
        if len(starts) > 1 and seg_end - starts[-1] < min_len:
            starts.pop()
        if final:
            # 末小节补齐成完整小节(谱面不必正好停在最后一个音符上)
            seg_end = max(seg_end, starts[-1] + meter * msb)

        # ★ 这一段(本红线 -> 下一条红线)的总拍数。红线已经被 restore_red_grid()
        # 还原到 1/4 拍网格上, 所以这里量出来就是精确的 k/4 拍, 照实转写即落成
        # `4/4`、`9/16` 这类写法 —— 不需要任何舍入, 误差为 0。
        # 只影响**尾小节**的拍数 —— 中间那些完整小节本来就是整数拍。
        seg_beats = (seg_end - t0) / msb

        for j, s in enumerate(starts):
            e = starts[j + 1] if j + 1 < len(starts) else seg_end
            if j + 1 < len(starts):
                beats = (e - s) / msb               # 完整小节, 本来就是整数拍
            else:
                beats = seg_beats - j * meter       # 尾小节: 用吸附后的总长反推
            # 压在小节开头那一瞬的绿线不能被边界误差吃掉, 所以往后取千分之一拍
            # scroll = 该时刻的 osu 实际流速(见 scroll_base), 不是裸的绿线 SV。
            # scroll_raw 只用于「这条命令要不要写」的相等判断 —— 判据必须基于原谱,
            # 否则缩放/舍入会把两条本不相同的绿线判成相同, 悄悄少写一条 #SCROLL。
            _sv_raw = timing.sv_at(s + msb * 1e-3)
            _sv = scroll_value(_sv_raw, scroll_base)
            bars.append({
                'start': s, 'end': e, 'beats': beats, 'msb': msb,
                'meter': float(meter), 'bpm': 60000.0 / msb, 'omit': bool(omit),
                'scroll': _sv, 'scroll_raw': _sv_raw,
                'kiai': timing.kiai_at(s + msb * 1e-3),
                'fragment': beats < meter - 1e-6,
                'cuts': [], 'events': [],
            })
    return bars


def _cell_index(p: float, n: int, cell: float) -> int:
    """把小节内位置 `p`(单位: 拍)吸附到 0..n 号格点上, 越界夹紧。

    格号允许等于 n —— 那表示「正好压在小节末尾」, 输出时交给下一小节的第 0 格
    (等价于落在小节线上), 与音符的真实时刻误差为 0。

    这里是全程序唯一一处「拍位置 -> 格号」的换算。`_grid_fits` / `_cmd_collapse` /
    `_grid_worst_err` / `_note_collapse` / `_bar_subdiv._solve` / 铺格那一段全都走它,
    保证「判定用的格号」与「真正写出去的格号」永远是同一个。
    """
    i = int(round(p / cell))
    return 0 if i < 0 else (n if i > n else i)


def _grid_fits(positions, n, cell, tol):
    """positions(单位: 拍) 能否都落在 0..n 号格点上(容差 tol 拍)。

    容差内能吸附到某个格点就算通过; 这是「音符 / 连打终点能不能用这张格网表达」的判据。
    """
    for p in positions:
        i = _cell_index(p, n, cell)
        if abs(p - i * cell) > tol:
            return False
    return True


def _cmd_collapse(positions, n, cell, tol):
    """命令点在格宽 cell 下会有几条「挤进同一格」? 返回冲突数(0 = 全都能各占一格)。

    ★ 这是 P1 流速还原的**真正判据** —— 比「落格偏差」要紧得多。
    因为 `convert()` 铺格时同一格的多条命令**只有最后一条存活**(前面的被覆盖),
    一条被覆盖的 `#SCROLL` 意味着**它影响的那段音符全部用错流速**。
    实测(ON.UR.MARKS)被覆盖处出现过差 0.75~1.0(即流速整体错一倍)的音符。

    同时要求 round() 后的偏差不超过 tol: 偏差太大说明这条命令被吸到了别的变速区间,
    前后关系可能跨过音符。

    positions 单位: 拍。tol 单位: 拍。

    ★★ 位置**完全相同**的连续几条先合并成一条(2026-11-14 修): 那是「同一毫秒的两条
    计时点」(osu 里红线与绿线同刻、或 GOGO 与 SV 在同一刻换), 铺格时后者本来就覆盖
    前者、语义正确, **不该算冲突**。曾经没合并: One of Us 有个小节里 GOGO 结束与 SV
    变化撞在同一刻 → 冲突数恒为 1、怎么加密都消不掉 → choose_grid 的 ②b 找遍
    FALLBACK_MAX_CELLS 也没等到 `== 0`, 最后退回最粗的 D=16, 把 49 条绿线压成 16 格,
    33 条 #SCROLL 被覆盖 —— 用户听到的就是「中间这段 SV 没识别」。

    ⚠ 别试图用「把格宽压到 1~2ms」来让每条命令都精确落格: 渐变 SV 谱的命令位置是
    19ms 网格的产物、和任何整齐格网都不同余, 那么做的结果是 BUZZ CUTZ 总格数
    26172 → 302252(11.5 倍), 而 SV 变化时刻只从「差半格」变成「差 1ms」—— 看不出来。
    """
    conflict = 0
    prev_i = None
    prev_p = None
    for p in positions:
        if prev_p is not None and abs(p - prev_p) <= 1e-9:
            # 同刻重复: 后一条生效, 前一条本来就会被覆盖 —— 跳过它, 只算后一条
            continue
        prev_p = p
        i = _cell_index(p, n, cell)
        if abs(p - i * cell) > tol:
            conflict += 1
            continue
        if i == prev_i:
            conflict += 1
        prev_i = i
    return conflict


def _grid_worst_err(positions, n, cell):
    """把 positions 吸到 0..n 号格点上之后的最大误差(单位同 cell)。"""
    worst = 0.0
    for p in positions:
        i = _cell_index(p, n, cell)
        worst = max(worst, abs(p - i * cell))
    return worst


def _note_collapse(positions, n, cell):
    """有几个音符会因为「挤进同一格」而被吃掉? 返回冲突数(0 = 每个音符各占一格)。

    ★ 这是**比落格偏差更硬的约束**: `convert()` 铺格时是 `slots[i] = ch` 的**覆盖**
    写法, 两个音符落进同一格 → 前一个**直接从谱面上消失**。那就是 P0-a (音符数目)
    出错, 用户的第一条红线, 绝对不可以。

    (同类问题在命令点上叫 `_cmd_collapse`, 但后果不同: 命令被吃掉丢的是流速(P1),
     音符被吃掉丢的是音符本身(P0)。所以这里的判据必须更严 —— 只按「格号是否相同」
     判定, 不看偏差。)
    """
    seen = set()
    conflict = 0
    for p in positions:
        i = _cell_index(p, n, cell)
        if i in seen:
            conflict += 1
        seen.add(i)
    return conflict


# 「常见节奏型」= 每拍格数。1 = 整拍一下, 2 = 半拍, 3 = 三连, 4 = 十六分, 5 = 五连…
# ★★ 这张表是用来**判定「这个音符属于哪种节奏型」**的, 与 NICE_SUBDIV
#    (**挑格宽**的候选表)是两件事, 千万别混。
#    判定表里 **1/5 与 1/4 地位完全平等** —— 用户 2026-09-23 拍板:
#    「上一个是 1/4, 下一个还是有可能是 1/5, 并不是说音符之间就一定是经常等距的」。
#    1/7 同理(只是更少见)。谁出现就谁留格子, 谁多谁少都不该影响判定。
# ⚠⚠ 2026-09-23 第二轮修 bug (BUZZ CUTZ 7:33 用户报) 补进 **9 与 36**:
#    - **9**: osu 编辑器的吸附档位本来就有 1/9。原表缺它 → 一个 34ms(≈1/9 拍)的间隔
#      全表最强命中变成了 **5/48**(误差 1.6ms), 于是 34/35/69ms 被判成 5/48、7/32,
#      最小公倍被抬到 96, 整小节被无谓加密 2.7 倍。补 9 之后它们立刻回到 1/9、2/9。
#    - **36**: 跨拍型留下的「尾巴」需要它。例: 一小组音符按 1/9 摆(1/9、2/9),
#      末音落在 1/4 网格点上(3/4 拍), 于是最后一段间隔 = 3/4 − 4/9 = **11/36 拍**
#      (实测 95ms, 与 11/36 只差 0.009ms)。有了 36, LCM(4, 6, 9, 36) = 36, 一格全收。
#    表里同时保留 24/32/48(它们对应更细的合法档); 因为现在按**从粗到细**试且容差很紧
#    (见 GAP_TOL_MS), 它们不会再抢走本该属于粗档的间隔。
#
# ⚠⚠ 2026-09-23 第四轮修 bug (Fellsius - Talk 17.2s 用户报) 补进 **35** —— 这是「接缝分母」:
#    **两群不同节奏型在同一拍里相遇时, 中间那一下间隔 = 两个「好分数」之差**,
#    它的分母**不在**上面那套「1/n」里, 而且**可以无限生成**, 逐个塞是塞不完的。
#    用户那首 (BeatDivisor=7) 的动机就是 `1/7 1/7 1/7 | 6/35 | 1/5 1/5`, 合计正好 1 拍:
#        3/7 + 6/35 + 2/5 = 15/35 + 6/35 + 14/35 = 35/35 ✓
#    6/35 = 1/5 − 1/7×... 即「1/7 群与 1/5 群的接缝」。82ms 实测:
#        · 6/35 (真值) 误差 **0.37ms**  · 1/6 误差 2.63ms  · 5/48 误差 8.9ms
#    表里没有 35 → 紧容差(1ms)整表判不出 → 落进兜底容差(3ms), 被**最粗**的 1/6 抢走。
#    后果不只是「名字错」: 分母集合从 {7,5,2,18} 变成 {6,7,5,2,18}, 最小公倍从 630 变成
#    630(不变), 但 `choose_grid` 的打分里「能整除的档数」变了 —— 实测该小节最终 D 被推到
#    **378 (1512 格/小节)**, 而正确识别后是 **70 (280 格)**, 整小节白白放大 5.4 倍,
#    且 1/5 与 6/35 都落不到整数格上。
#
# ⚠ **35 必须排在 36 之后**(这是本表唯一一处不按升序排列, 刻意的):
#    1/35 = 0.028571 与 1/36 = 0.027778 只差 0.00079 拍(**0.38ms**), 在 1ms 容差里
#    两者会互相冒充。而 1/36 是**真节奏型**(跨拍尾巴 11/36、13/36 用得到), 1/35 只在
#    「接缝」里以 6/35、11/35 这类**多分子**形式出现(那与任何 k/36 都差很远, 不会撞)。
#    所以要**先试 36 再试 35** —— 反过来会把所有真 1/36 间隔判成 1/35(实测 VIGVANGS)。
GAP_SUBDIV = (1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 16, 24, 32, 36, 35, 48)

# 「判节奏型」用的容差(毫秒)。**必须比「摆放音符」的容差(note_tol_ms=3ms)紧**:
#   摆放时允许把音符吸到最近格(3ms 听不出来), 但**判定它属于哪种节奏型必须接近精确** ——
#   否则细档会靠「巧合命中」赢过粗档。踩过的坑:
#     · 34ms 被 5/48 命中(误差 1.62ms) → 本该是 1/9(误差 0.54ms);
#     · 69ms 被 7/32 命中(误差 0.99ms) → 本该是 2/9(误差 0.086ms);
#     · 95ms 被 5/16 命中(误差 2.15ms) → 本该是 11/36(误差 0.009ms)。
#   容差收到 1.0ms 后, 上面三个全部回到正确档位。
GAP_TOL_MS = 1.0

# 「判出来的最小公倍」允许有多细: 上限 = 本小节总格数不超过 GRID_CAP_CELLS。
#   ★ 取 1536 是**和 `rebuild.py` 的排版体检口径对齐**(本家语料最密的一小节就是 1560 格),
#     两边不一致的话 rebuild 会把刚生成的谱面判失败。
#   旧上限是 `int(1/tol_beats)`(=193BPM 下只有 103), **把合法的 LCM 也挡掉了**:
#     · 1/4+1/6+1/9        → LCM = 36    (旧上限 103 放行, 没问题)
#     · 1/4+1/5+1/6+1/9    → LCM = 180   (旧上限 103 **挡住** → need=None → 回退到坏格宽)
#     · 1/4+1/5+1/6+1/8+1/9→ LCM = 360   (同上, 挡住)
#   被挡住后的回退结果正是用户报的「不等距」: 1/5 跑动写成 13/13/12/13/13、
#   1/6 跑动写成 11/10/11。所以上限必须放到能容下 360。
#   仍然挡掉真正病态的 LCM(504、720、3360…), 那些回退到老候选表。
GRID_CAP_CELLS = 1536

# ★★ 「最小公倍」还不够 —— 必须再验一次「等距到底有没有成立」。
#   (2026-09-23 第三轮, BUZZ CUTZ 7:33 那个混了 1/3/1/4/1/8/1/5 的小节报的 bug)
#
#   **病症**: 最小公倍**算对了**, 音符也都在 3ms 内, 但同一串本该等距的音符被写成不等距。
#   **病因**: 铺格是 `i = int(round(p / cell))`, 而 osu 的时刻只有整数毫秒 —— 同一个 1/5
#   跑动的相邻间隔实测在 62/63ms 之间抖 1ms。格宽一旦细到「1ms 抖动能跨过半格」,
#   这串音符就会写出不同的格子数。实测(BUZZ CUTZ, msb=310.88ms):
#     · D=360(一格 0.86ms) → 1/5 跑动 = 72,73,72,72,71        ✗
#     · D=180(一格 1.73ms) → 1/9 跑动 = 19,21                 ✗
#     · D=120(一格 2.59ms) → 1/5 = 24×5、1/9 = 13,13          ✓
#   ⇒ 格宽 **不能只看「能不能整除」, 还要看「整除之后格子数稳不稳」**。
#
#   **判据**(取代原来的「格宽不许细过 4ms」这个拍脑袋常数):
#     ① 把每个间隔判成**约分后的分数**(2/9 与 1/9 是两种节奏型, 不能混为一谈);
#     ② 对候选格宽 D, 数出**「同型相邻间隔格子数不等」的次数** `bad`
#        (「同型」= 两个相邻间隔判成了同一个分数);
#     ③ 候选范围 `D ≤ min(GRID_CAP_CELLS/length, max(ideal, base))` ——
#        **绝不需要比「所有节奏型的最小公倍 ideal」还细**, 更细只会让抖动更容易跨格;
#     ④ 打分 = (`bad` ↓, 能**整除**的节奏型档数 ↑, 格宽 ↓) —— 取最优。
#        第二项是「最小公倍」的推广: 理想格宽能整除所有节奏型, 所以理想可行时它必然胜出;
#        理想不可行时退而求「能整除尽量多节奏型」, 落点仍是某个子集的最小公倍, 有结构。
#   ⇒ `bad=0` 的含义就是「每一串同型音符在原谱里等距, 在 TJA 里也严格等距」。


def _bar_subdiv(note_pos, msb: float, tol_beats: float, length: float = 0.0,
                base: int = 4):
    """给本小节挑一个「每拍格数 D」—— 判据是**让每一串同型音符严格等距**。

    ★ 口径(用户 2026-09-22/23 两次拍板):
      `choose_grid` 是「一个小节共用一个格宽」, 所以只要小节里同时出现 1/4 与 1/5,
      格宽就必须**同时**容得下 1/4 拍与 1/5 拍 —— 最小的公共格是 **1/20 拍**,
      也就是「每拍 20 格」。而老候选表 NICE_SUBDIV 里**恰好没有 20 这一档**,
      逐档试过去只能上到 48, 于是 1/5 的等距被写成 8/48 与 10/48 交替
      (绝对误差 ≤3ms 过得去, 但**相邻间隔不再相等**)。
      这正是用户两次报的同一个问题: 「1/5 的 note 之间应该是等距的」。

    ★ 为什么是「每个间隔独立判型」而不是「按主导拍型分段」:
      分段会让多数派决定格宽、少数派被吸到最近格 —— 用户明确否掉了这条路:
      「不能因为这个小节里 1/5 更多你就把它全部表达成 1/5」。
      独立判型 + 逐候选打分, 相当于让 1/3、1/4、1/5、1/6、1/7 全都平权。

    ★★ 为什么不是「算出最小公倍就完事」(2026-09-23 第三轮, BUZZ CUTZ 7:33 报的 bug):
      最小公倍**算对了**也**可能摆错**。铺格是 `i = int(round(p / cell))`, 而 osu 的时刻
      只有整数毫秒: 同一个 1/5 跑动的相邻间隔实测在 62/63ms 之间抖 1ms。格宽一旦细到
      「1ms 抖动能跨过半格」, 这串音符就写出不同的格子数 —— 绝对时刻仍 ≤3ms(所以
      「看着几乎一样」), 但**不再等距**。实测 D=360(一格 0.86ms) 让 1/5 写成
      `72,73,72,72,71`、D=180 让 1/9 写成 `19,21`; D=120(一格 2.59ms) 才两者都对。
      ⇒ 所以这里不再「算完就去用」, 而是**逐个候选真的摆一遍、数不等距的次数**, 取最好的。

    判据(`bad` = 「同型相邻间隔格子数不等」的次数, 「同型」指两个相邻间隔判成了同一个分数):
      ① `bad` 最小; ② 同样 `bad` 里能**整除**的节奏型档数最多; ③ 再同样就取**最粗**(格数最少)。
      候选上限 `D ≤ min(GRID_CAP_CELLS/length, max(ideal, base))` ——
      **绝不需要比「所有节奏型的最小公倍 ideal」还细**, 更细只会让抖动更容易跨格。
      `ideal` 本身可行就直接返回它(绝大多数小节走这条快路, 与上一轮口径一致)。

    返回 None = 「一个间隔都量不出节奏型」或「候选里没有能装下本小节音符的档」;
    退回原来的逐档扫描(不会比改动前更差)。

    ⚠ 判型容差用 `GAP_TOL_MS`(=1ms), **不是**调用方传进来的摆放容差(3ms) —— 见 GAP_TOL_MS。
    ⚠ 判出来的东西必须**约分**: `2/9` 与 `1/9` 是两种节奏型, 混为一谈会让 `bad` 数错
      (`2/9` 记成 9 就会把 `1/9,2/9` 当成「同型不等距」)。
    """
    if len(note_pos) < 2 or msb <= 0 or length <= 0:
        return None
    tol = min(tol_beats, GAP_TOL_MS / msb)

    def _identify(gap, tolerance):
        """把一个间隔量到**能容下它的最粗**那一档(从粗到细取第一个命中); 量不出返回 None。
        这就是用户说的「把 1/3、1/4、1/5、1/6 甚至 1/7 带进去, 看它离哪个最近」的稳定版:
        粗档先被考虑, 细档只有在前面的粗档都够不着时才可能赢。
        ⚠ 容差只用**绝对毫秒**折成的拍数, 不能乘「间隔的百分比」—— 踩过的坑:
          5/12 拍(0.4167) 与 2/5 拍(0.4) 只差 0.0167 拍, 若容差取「间隔 × 8%」,
          5/12 就会被判成 1/5, 最小公倍从 12 抬到 60, 一整串小节跟着虚胖。
          间隔的测量误差是**固定几毫秒**(osu 时刻是整数毫秒), 不随间隔长短缩放。
        """
        for n in GAP_SUBDIV:
            k = int(gap * n + 0.5)      # 半拍向上取整, 避免 round(0.5) 的银行家舍入
            if k < 1:
                continue
            if abs(gap - k / n) <= tolerance:
                return Fraction(k, n)   # 约分: 2/9 与 1/9 必须区分开
        return None

    vals = []
    for i in range(len(note_pos) - 1):
        gap = note_pos[i + 1] - note_pos[i]
        if gap <= 0:
            return None
        v = _identify(gap, tol)                 # 先用紧容差判
        if v is None:
            v = _identify(gap, tol_beats)       # 判不出就退回摆放容差(3ms)
        vals.append(v)
    dens_all = {v.denominator for v in vals if v is not None}
    if not dens_all:
        return None

    # ★★ 第五轮 (2026-09-23): 「孤立 + 不在接缝上」的细档先降级, 不配抬高格宽下限。
    #
    #   背景: 补进 35 之后 (BUZZ CUTZ t=374315.5, msb=310.881ms) 出现一个 79ms 间隔 ——
    #     真值 1/4 = 77.72ms(差 1.28ms), 被判成 9/35(差 0.94ms), 只赢 **0.34ms**。
    #     可就为这 0.34ms, `ideal` 从 4 抬到 140, 该小节格数 **16 → 560**(放大 35 倍)。
    #     而该小节通篇都是 ±1ms 的量化噪声: 1/2 写成 155/156, 1/4 写成 77/78/79/77/78。
    #     那个 79 只是噪声里最偏的样本, **不是节奏型** —— 真接缝两侧必须是不同的细分,
    #     而它两边都是 1/4。 ⇒ 用户口径是「绝对时刻差得少不算还原, 等距关系才算」,
    #     那么反过来: **为 0.34ms 多付 35 倍格子同样不算还原, 是虚胖**。
    #
    #   判据(「它到底是不是一种节奏型」的结构性定义, 与用户否掉的「多数决」无关):
    #     ① **多次出现** —— 同一分数在本小节出现 ≥2 次 ⇒ 是一条真的拍型, 保留。
    #        (Talk 的 6/35 出现 3 次, 靠这条安全留下。)
    #     ② **真接缝** —— 相邻两个间隔判成了**不同**的分数(细分在变), 中间那一下才可能
    #        是接缝, 保留。 (11/36 这类跨拍尾巴同理。)
    #     ③ 其余 = 孤立 + 两侧同型 ⇒ 先剔除, 当作「相邻那种粗档被量化抖了一下的样本」。
    #
    #   ⚠ 剔除后**必须复验**: 若该间隔的终点音符在粗格上会偏离 > tol_beats(3ms),
    #     说明它其实非细不可(例如 1/5 夹在一堆 1/4 中间, 差 15.5ms), 立刻把分母收回来。
    #   ⚠ 过滤版若取不出解, 就退回未过滤的版本 —— 保证**绝不比改动前更差**。
    freq = {}
    for v in vals:
        if v is not None:
            freq[v] = freq.get(v, 0) + 1
    keep = set()
    for i, v in enumerate(vals):
        if v is None:
            continue
        if freq[v] >= 2:
            keep.add(v)
            continue
        l = vals[i - 1] if i > 0 else None
        r = vals[i + 1] if i + 1 < len(vals) else None
        if l is None or r is None:
            # 小节首/尾的间隔只有一个邻居, 判不了「是不是接缝」-> 保守留下, 不动它。
            keep.add(v)
            continue
        if l != r:
            keep.add(v)             # 真接缝: 两侧细分不同
    # (未进 keep 的 = 夹在同型跑动中间 + 孤立 => 视为「那串跑动被量化抖了一下的样本」)

    def _lcm(ds):
        m = 1
        for d in sorted(ds):
            m = m * d // math.gcd(m, d)
        return m

    while True:
        cur = {v.denominator for v in vals if v is not None and v in keep}
        if not cur:
            keep = {v for v in vals if v is not None}
            break
        d0 = max(_lcm(cur), base)
        n0 = int(round(d0 * length))
        if n0 < 1:
            n0 = 1
        cell0 = length / n0
        restore = None
        for i, v in enumerate(vals):
            if v is None or v in keep:
                continue
            p = note_pos[i + 1]
            if abs(p - round(p / cell0) * cell0) > tol_beats:
                restore = v
                break
        if restore is None:
            break
        keep.add(restore)
    dens = {v.denominator for v in vals if v is not None and v in keep}
    if not dens:
        dens = dens_all

    # 逐个候选格宽真的摆一遍, 打分 = (破坏等距次数 bad, −能精确表达的节奏型档数)。取最小。
    # ★ 为什么第二项是「精确档数」而不是「偏差最小」或「格数最少」:
    #   · 「偏差最小」会一路挑到候选上限(格越细偏差越小), 把整曲格数撑大十倍 —— 试过, 不可用;
    #   · 「格数最少」会挑到 55、65 这类毫无结构可言的格宽(bad=0 纯属巧合);
    #   · 「精确档数」正好是「最小公倍」的推广: 理想格宽能整除**所有**节奏型, 档数最多,
    #     所以理想可行时它必然胜出(和上一轮口径完全一致); 理想不可行时, 它退而求
    #     「能整除尽量多节奏型」的自然折中, 落点也总是某个子集的最小公倍, 有结构。
    #   · 同样好时取**最粗**(格数最少) —— 格子只在谱面里看不见地占位, 少比多好。
    def _solve(dens_ideal, dens_score):
        """给定分母集合, 逐个候选格宽真的摆一遍, 取最优 D(取不出返回 None)。

        ⚠ `dens_ideal` 只用来定**上限** `hi`(哪些细档值得为它加密);
          `dens_score` 用来算「能精确整除的档数」这个打分项。
          两者分开是刻意的: 过滤只该体现在**「不配把格宽往上抬」**这一件事上,
          不该顺带改掉排序口径 —— 否则一个末尾的孤立细档会连带把别的小节的
          最优 D 换掉(实测 BUZZ t=284781.8 的 132 会变成 77)。
        """
        ideal = _lcm(dens_ideal)
        cap = int(GRID_CAP_CELLS / length)
        hi = min(cap, max(ideal, base))
        if hi < 1:
            return None
        best = None
        for D in range(hi, 0, -1):
            n = int(round(D * length))
            if n < 1:
                continue
            cell = length / n
            worst = 0.0
            prev = None
            ks = []
            ok = True
            for p in note_pos:
                i = _cell_index(p, n, cell)
                e = abs(p - i * cell)
                if e > worst:
                    worst = e
                if prev is not None and i == prev:
                    ok = False       # 音符撞格 -> 会被覆盖吃掉, P0-a, 直接淘汰
                    break
                prev = i
                ks.append(i)
            if not ok or worst > tol_beats:
                continue
            bad = 0
            for j in range(len(vals) - 1):
                if vals[j] is not None and vals[j] == vals[j + 1] \
                        and ks[j + 1] - ks[j] != ks[j + 2] - ks[j + 1]:
                    bad += 1
            if bad == 0 and D == ideal:
                return D            # 理想格宽本身就能保证等距 -> 直接用它(绝大多数小节走这里)
            exact = sum(1 for d in dens_score if D % d == 0)
            key = (bad, -exact)
            if best is None or key <= best[0]:
                best = (key, D)
        return best[1] if best is not None else None

    D = _solve(dens, dens_all)
    if D is None and dens != dens_all:
        D = _solve(dens_all, dens_all)      # 过滤版取不出解 -> 退回原口径, 绝不更差
    return D


def choose_grid(length: float, note_pos, cmd_pos, msb: float, base: int = 4,
                fuzzy_pos=(), note_tol_ms: float = 3.0, fuzzy_tol: float = 0.08,
                cmd_tol_ms: float = CMD_TOL_MS):
    """给一个小节挑「每拍格数 D」和「总格数 N」。

    选档位分三步:
      ⓪ **先给本小节挑一个「节奏型都能严格等距」的格宽**(见 `_bar_subdiv`):
         把每个间隔**各自独立**判成常见节奏型(判成约分后的分数), 再逐个候选格宽真的摆
         一遍, 数「同型相邻间隔格子数不等」的次数 —— 取次数最少、且最细的那一档。
         一个小节里同时有 1/4 与 1/5 时, 格宽会取到「每拍 20 格」, 两种节奏型**都落
         整数格**, 谁都不用被牺牲。
         (这正是 2026-09-22/23 用户两次报的那个 bug: 老候选表里没有 20 这一档。
          第三轮又发现「最小公倍算对了也可能摆错」—— 见 `_bar_subdiv` 的 ★★ 段。)
      ① **只用音符**(与连打/气球结束点)选出格宽 —— 它们是 P0。
      ② 再看命令点(SV/GOGO)在这个格宽下是否**各自有格**(见 _cmd_collapse), 不够就
         按 CMD_EXTRA_FACTOR 逐级放宽, 仍不够就认了 —— 宁可个别 SV 挤在一起,
         也不再为它把音符的排版加密。

    D 从本家惯用的 4 开始试, 放不下再按 6/8/12/16/24... 依次加密; 只有在小节长度
    不是 1/4 拍整数倍时(红线被 osu 取整到整数毫秒的后果)才会退到 D<4 或非整数格。
    这样同一串音符在任何行里都保持同样的疏密, 且一定落在格点上。

    容差说明(note_tol_ms=3ms):
      osu 的时刻是整数毫秒, 而谱面本来是按节拍摆的 —— 例如一段 1/6 音符在
      180BPM 下应该每 55.56ms 一下, 文件里写成 55/56ms 交替。若要求「严格贴合
      文件时刻」, 就会为了这 1~2ms 把整行从 24 格加密到 768 格(旧版正是如此,
      结果是同一串音符在某些行疏、某些行密)。所以宁可把音符吸附回它真正的
      节拍位置(误差 ≤3ms, 远小于人耳能分辨的量级), 换来全曲一致的排版。
      容差远小于半格, 所以绝不会出现「两个音符挤进同一格」。

    cmd_pos: SCROLL / GOGO 的**换值时刻**(单位: 拍)。
      ★ 2026-09-22 用户拍板改口径: **音符优先, 命令点松绑**。
      旧口径要求「命令点和音符都必须各占一格」, 于是**只要有一条绿线落不进格子,
      整个小节就被迫加密** —— 而 SV 在谱面上不可见, 只影响它之后音符的流速(用户验收
      次序里的 P1), 拿音符的排版去换它是本末倒置。
      新口径分两步:
        ① 只用音符 + 连打/气球结束时刻选档位 (它们才是 P0, 决定音符落在哪一格);
        ② 在这个格宽上再允许放宽 CMD_EXTRA_FACTOR 倍, 给命令点找位置;
           仍放不下就**让命令点吸到最近的格** —— 宁可 SV 的生效时刻偏几个 ms。
      代价与收益(实测 ON.UR.MARKS): 旧口径为了命令点精确落格, 总格数 13602 -> 32162
      (2.4 倍); 这些多出来的格子游戏里看不见, 而 SV 只差几毫秒。所以新口径**同时**
      让音符能表达 1/5、1/7 拍, 又不再让 SV 拖着整行加密。

      注意「前后关系」仍然不许乱: 命令点只会被吸到**它自己那一格**, 不会跨过它所
      影响的音符 —— 这是旧版 30ms 容差那个 bug 的教训(见 CMD_TOL_MS 上方注释)。

    fuzzy_pos: 连打/气球的**结束时刻**。它是按滑条长度算出来的, 本来就不在节拍网格上,
               所以用宽松容差(默认 0.08 拍), 免得它一个人把整行加密。
    """
    nt = note_tol_ms / msb
    ft = fuzzy_tol
    ct = cmd_tol_ms / msb
    # ---- 候选格宽 ----
    # 除了原来那张表, 再加一个「本小节节奏型都能严格等距」的格宽(见 _bar_subdiv)。
    # ★ 该档**排在最前**: 只要算得出来就优先用它。
    #   理由: 它已经**真的摆过一遍**、确认过每一串同型音符格子数相同; 而后面那些
    #   候选只保证「音符落在 3ms 内」, 相邻间隔可能变成 10/9 交替 —— 也就是用户报的
    #   「看起来很像、但不再等距」。所以在这个转换器里 **「等距」优先于「格数少」**
    #   (用户 2026-09-22/23 两次拍板)。
    #   算不出来时 need = None, 顺序与原来完全一致。
    need = _bar_subdiv(note_pos, msb, nt, length, base)
    if need is not None and need >= base:
        pool = sorted(set(NICE_SUBDIV) | {need})
        head = [d for d in pool if abs(d / need - round(d / need)) < 1e-9]
        step = head + [d for d in pool if d not in head]
    else:
        step = sorted(NICE_SUBDIV)
    step = [d for d in step if d >= base] + [d for d in reversed(step) if d < base]

    def _pick(fit_pos, tol, also_pos=(), also_tol=0.0):
        """在一张候选表上找出第一个能同时容纳 fit_pos 与 also_pos 的档位。

        ⚠ **两组位置必须一起判**, 不能先挑再复核 —— 先找到的档位若容不下另一组,
          复核失败会把人推进兜底分支(那里的起点是 NICE_SUBDIV[-1] × length,
          实测直接把一个 4 拍小节撑到 1536 格)。这正是「先 `_pick(note)` 再查
          fuzzy」写法踩出来的坑(vs.VIGVANGS 出现过一个 384 格/拍的小节)。
        ⚠ **还要查 `_note_collapse`**: 铺格是 `slots[i] = ch` 的覆盖写法, 两个事件
          落进同一格 → 前一个**从谱面上消失**(P0-a)。落格误差在容差内 ≠ 不会撞格。
        """
        for d in step:
            n = int(round(d * length))
            if n < 1:
                continue
            cell = length / n
            if _grid_fits(fit_pos, n, cell, tol) and \
                    _grid_fits(also_pos, n, cell, also_tol) and \
                    not _note_collapse(list(fit_pos) + list(also_pos), n, cell):
                return (d, n)
        return None

    # ---- ① 只用音符(与连打/气球结束点)选格宽: 「所有音符都落进同一张格网」 ----
    # ★ 2026-09-23 起**不再有「按主导拍型分段」那一步**。用户否掉了它:
    #   「不能因为这个小节里 1/5 更多你就把它全部表达成 1/5」。
    #   现在的做法是让 ⓪ 的最小公倍档出场 —— 它能让 1/4 与 1/5 **同时**落在整数格上,
    #   根本不需要谁让谁, 也就不存在「少数派被吸走」的取舍了。
    chosen = _pick(note_pos, nt, fuzzy_pos, ft)

    if chosen is None:
        # 音符自己就放不下 -> 走兜底加密(原来那套逻辑, 只按音符判定)。
        # ⚠ 硬上限照旧: 防病态小节撑到几万格。
        tried = []
        n = max(1, int(round(NICE_SUBDIV[-1] * length)))
        while n <= FALLBACK_MAX_CELLS:
            cell = length / n
            if _grid_fits(note_pos, n, cell, nt) and _grid_fits(fuzzy_pos, n, cell, ft):
                return (n / length if length else 1.0), n
            tried.append(n)
            n *= 2
        best, best_n = None, tried[-1] if tried else 1
        for cand in tried:
            cell = length / cand
            score = max(_grid_worst_err(note_pos, cand, cell) / nt if nt else 0.0,
                        _grid_worst_err(fuzzy_pos, cand, cell) / ft if ft else 0.0)
            if best is None or score < best:
                best, best_n = score, cand
        return (best_n / length if length else 1.0), best_n

    d0, n0 = chosen
    if not cmd_pos:
        return d0, n0

    # ---- ② 命令点: 先在同一格宽下试, 再按 CMD_EXTRA_FACTOR 逐级放宽 ----
    # 判据在 _cmd_collapse(): **不许两条命令挤进同一格**(挤了 = 前一条被覆盖 =
    # 它影响的那段音符全部用错流速; 实测有差 0.75~1.0 的大错)。
    # ★ 兜底(2026-11-14): 找不到 `conflict == 0` 的档时, 取**冲突最少**的那一档, 而不是
    #   直接退回最粗的 (d0, n0)。原来那写法把「有 1 处无法消除的冲突」和「49 条命令全挤进
    #   16 格」当成同一件事, 后果差得远 —— 退化要尽量轻微。
    #   ⚠ 这条只是保险, 真正的病根在 _cmd_collapse 的「同刻重复」, 已在那里修掉。
    best = None          # (conflict, n) —— conflict 相同则保留先到的小 n
    for n in (n0, n0 * CMD_EXTRA_FACTOR, n0 * CMD_EXTRA_FACTOR * 2):
        c = _cmd_collapse(cmd_pos, n, length / n, ct)
        if c == 0:
            return (n / length if length else 1.0), n
        if best is None or c < best[0]:
            best = (c, n)

    # ---- ②b 上面三级都不行 -> 继续沿 **n0 的整数倍** 往上找 ----
    # ⚠ 为什么必须有这一步(2026-09-22 实测踩坑):
    #   ① 的「音符优先」会把格宽压到**音符自己够用**的最小档(典型 D=4),
    #   而 SV 绿线常常比音符密得多 —— BUZZ CUTZ t=522.3s 那个 8 拍小节就是:
    #   25 个音符只要 D=4 就全落网, 但 27 条绿线是按 0.2509 拍(=1/4 拍)排的,
    #   在 D=4 的格上全部挤在 0.125 拍的位置上, 任何容差都放不下。
    #   旧版(改动前)是「音符+命令一起选档」, 于是命令把 D 一路抬到 32 才通过;
    #   改成「音符优先」之后, ② 只试到 4×n0 就放弃并**退回 D=4**,
    #   把 27 条绿线压成几条 —— 逐音符生效流速就错了(实测差 1.0667)。
    #   所以这里继续加密: 命令点需要多细就给多细。
    # ⚠⚠ 但加密**只能取 n0 的整数倍**, 不能拿候选表里随便一个更细的档!
    #   踩过的坑(2026-09-23 实测): ON.UR.MARKS t=225.5s 那一小节的音符只要 D=6 就
    #   全部落网(1/3 与 1/6 拍), 可旧的 ②b 一路挑到了 **D=32** —— 32 **不是 6 的
    #   整数倍**, 于是本该落在 1/3 拍(=8/24)的音符, 在 1/32 的格上只能落到
    #   11/32 = 0.34375, 偏差 3.2~4.0ms(在 n0 格上只有 0.04ms)。
    #   「加密只会让误差更小」**只在整数倍的前提下成立**: n0 的整数倍格网包含
    #   原来的格点, 音符仍落在原来那一格上; 非整数倍则会把音符重新取整到别处。
    k = CMD_EXTRA_FACTOR * 2 + 1
    while n0 * k <= FALLBACK_MAX_CELLS:
        n = n0 * k
        cell = length / n
        c = _cmd_collapse(cmd_pos, n, cell, ct)
        if c == 0:
            return (n / length if length else 1.0), n
        if c < best[0]:
            best = (c, n)
        k += 1

    # 命令点比格还密, 实在排不下 -> 用**冲突最少**的那档(通常是能各占一格的最小 n),
    # 由铺格那步把剩下的冲突按 round() 落格。只有在最小冲突就等于 n0 那一档时才原样返回。
    if best is not None and best[1] != n0:
        return (best[1] / length if length else 1.0), best[1]
    return d0, n0


def timing_cuts(timing: Timing):
    """SCROLL / Kiai 的值真的变了的位置。

    它们在小节**内部**, 属于「命令点」, 不切割小节 —— 为它们切小节会凭空多出
    大量小节线, 视觉上跟原谱完全不一样。
    """
    cut_times = []
    all_tp = sorted(set([r[0] for r in timing.reds] +
                        [g[0] for g in timing.greens] +
                        [k[0] for k in timing.kiais]))
    cur_sv, cur_kiai = None, None
    for t in all_tp:
        sv, k = timing.sv_at(t), timing.kiai_at(t)
        changed = False
        if cur_sv is None or abs(sv - cur_sv) > 1e-9:
            changed = changed or cur_sv is not None
            cur_sv = sv
        if cur_kiai is None or k != cur_kiai:
            changed = changed or cur_kiai is not None
            cur_kiai = k
        # ★ 同一时刻 sv 与 kiai **同时**变化时, 老写法会往 cut_times 里塞两条同样的
        #   时刻(两次 append 都没去重)。那对输出无碍(反正挤在同一格、值也取自同一刻),
        #   但会让 _cmd_collapse 的「挤格」计数多出一条**永远消不掉的**冲突, 进而
        #   使 choose_grid 的 ②b 一路扫到格数上限还是 `!= 0`, 最后退回最粗档。
        #   2026-11-14 One of Us 的 bar 216 就是这么丢掉 33 条 #SCROLL 的。
        if changed and (not cut_times or cut_times[-1] != t):
            cut_times.append(t)
    return cut_times



def audio_candidates(folder: str):
    """列出文件夹里的音频文件, 按「像不像这首曲子的音源」排序。

    排序键 = (扩展名优先级, 体积从大到小): mp3/ogg/... 排在 .wav 前面,
    同扩展名里挑最大的 —— osu 谱面文件夹里那些 soft-hitnormal.wav 之类又小又多,
    这样排不会把它们当成歌曲。
    """
    out = []
    try:
        names = os.listdir(folder)
    except OSError:
        return out
    for n in names:
        ext = os.path.splitext(n)[1].lower()
        if ext not in AUDIO_EXTS:
            continue
        fp = os.path.join(folder, n)
        try:
            if not os.path.isfile(fp):
                continue
            size = os.path.getsize(fp)
        except OSError:
            continue
        out.append((AUDIO_EXTS.index(ext), -size, n))
    out.sort()
    return [n for _, _, n in out]


def _ogg_name(picked: str, src: str, encoding: str) -> str:
    """音频的最终文件名: 跟着源文件的主名, 扩展名换成 .ogg。

    若这个名字用目标编码编不出来(cp932 编不了简体中文等), 就退回 ASCII 的 audio.ogg ——
    WAVE 行必须和磁盘上的文件名逐字节一致, 否则模拟器直接找不到音源。
    """
    stem = os.path.splitext(picked)[0] if picked else os.path.splitext(os.path.basename(src))[0]
    cand = safe_name(stem, 'audio') + AUDIO_OUT_EXT
    try:
        cand.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return 'audio' + AUDIO_OUT_EXT
    return cand


def plan_audio(src: str, dst_dir: str, wave_ext=None, meta=None,
               encoding: str = 'cp932') -> dict:
    """算出这个谱面的音源该怎么处理（只算, 不动文件）。

    挑音源的优先级:
      1. .osu 里 AudioFilename 指名的那个文件（最准, 通常就是它）
      2. --wave-ext 限定的扩展名里, 挑最像歌曲的那个
      3. 直接扫文件夹, 挑最像歌曲的那个

    **输出一律是 OGG**:
      · 源本身是 .ogg -> 原样拷贝（不重编码, 不损失）
      · mp3/m4a/flac/wav/... -> ffmpeg 转成 Vorbis OGG
    WAVE 里写的就是这个 .ogg 的文件名。

    返回 {'src','dst','wave','action','note'}:
      action = 'copy'       源已是 .ogg, 拷过去
               'transcode'  需要 ffmpeg 转成 .ogg
               'same'       源和目标本来就是同一个文件
               'missing'    没找到音源, wave 里写的是兜底名字
    """
    folder = os.path.dirname(os.path.abspath(src))
    if meta is None:
        meta = read_meta(src)
    want = (meta.get('AudioFilename') or '').strip()
    want = want.replace('\\', '/').split('/')[-1]      # 只取文件名, 防止写法里带路径

    ext_want = ('.' + wave_ext.strip().lstrip('.').lower()) if wave_ext else None
    pool = audio_candidates(folder)
    note = ''
    if ext_want and pool:
        only = [n for n in pool if os.path.splitext(n)[1].lower() == ext_want]
        if only:
            pool = only
        else:
            note = '文件夹里没有 %s 音源, 已改用 %s' % (ext_want, pool[0])

    picked = ''
    for n in pool:
        if want and n.lower() == want.lower():
            picked = n
            break
    if not picked and pool:
        picked = pool[0]
        if not note:
            note = '%s 不在文件夹里, 按扩展名/体积挑了 %s' % (want or 'AudioFilename', picked)

    wave = _ogg_name(picked, src, encoding)
    res = {'src': None, 'dst': None, 'wave': wave, 'action': 'missing', 'note': ''}
    if not picked:
        res['note'] = note or '这份谱面所在的文件夹里没有音频文件'
        return res

    a_src = os.path.join(folder, picked)
    a_dst = os.path.join(dst_dir, wave)
    res['src'], res['dst'], res['note'] = a_src, a_dst, note
    if os.path.normcase(os.path.abspath(a_src)) == os.path.normcase(os.path.abspath(a_dst)):
        res['action'] = 'same'
    elif os.path.splitext(picked)[1].lower() == AUDIO_OUT_EXT:
        res['action'] = 'copy'
    else:
        res['action'] = 'transcode'
    return res


def _is_output_file(path: str) -> bool:
    """`-o` 给的是「谱面文件路径」还是「目录」。

    只有**明确以 .tja / .osu 结尾、且不是已存在的目录**才算文件, 其余一律当目录。
    ⚠ 早先用「basename 里有没有 `.`」判断: 目录名一到带版本号(`D:\\out\\v1.2`)
      或者本身就是曲名(`…\\vs.VIGVANGS`), 就会被当成文件, 于是 .tja 被写成一个
      **没有扩展名**的文件(2026-11-14 实测踩到)。当时只修了命令行那条路径,
      GUI 里还留着旧判据 —— 现在两处共用这一个函数。
    """
    p = (path or '').rstrip('/\\')
    if not p or os.path.isdir(p):
        return False
    return p.lower().endswith(('.tja', '.osu'))


def output_paths(src: str, dst: str, meta=None, song_folder: bool = True,
                 title_opt=None, allow_name_fallback: bool = True):
    """把「用户指定的输出位置」换算成最终落盘位置。

    song_folder=True(默认): 在 dst 所在目录下再建一层**以曲名命名的文件夹**,
    .tja 与 .ogg 都放进那一层 —— 模拟器是按「一个文件夹 = 一首歌」收录的。
    若 dst 已经就在叫这个名字的文件夹里(比如 -o 直接指进去过), 就不再套一层。

    返回 (谱面路径, 该谱面所在的文件夹)。
    """
    dst = os.path.abspath(dst)
    parent = os.path.dirname(dst)
    if not song_folder:
        return dst, parent
    if meta is None:
        meta = read_meta(src)
    # 文件夹名要和 TJA 里的 TITLE 完全一致, 所以走同一个取名函数(含乱码兜底)。
    title, _ = pick_display_name(meta, 'Title', 'TitleUnicode', title_opt,
                                 allow_name_fallback)
    name = safe_name(title)
    if os.path.basename(parent).casefold() == name.casefold():
        song_dir = parent                      # 已经在曲名文件夹里, 不重复套
    else:
        song_dir = os.path.join(parent, name)
    return os.path.join(song_dir, os.path.basename(dst)), song_dir


def snap_beat_24(t, timing: Timing):
    """把时刻吸附到「以最近的红色计时点为原点」的 1/24 拍网格上。

    照搬前人 osu2tja.py 里的 get_real_offset():
        base   = 最近的一条红色计时点(早于 t 的最后一条; t 比第一条还早就是第一条)
        units  = round(|t - base| / 每拍毫秒 * 24)      # 以 1/24 拍为单位
        结果   = base ± units/24 拍

    前人拿它吸附**所有**音符与绿线的时刻。我们不照搬那一步 —— 本转换器的小节网格
    比它细得多(1/48 拍起, 按需升到 1/96、1/192、1/384), 逐音符残差已压到毫秒级
    且不随曲长累积漂移; 换成 1/24 拍反而会引入最大半格(低 BPM 时十几毫秒)的量化误差。
    这里只用它来确定「谱面起点」—— 起点是 OFFSET 的唯一输入, 这样 OFFSET 的取值
    方式就与前人完全一致。
    """
    base = timing.msb_at(t)             # 早于 t 的最后一条红线(t 更早则用第一条)
    msb = base[1]                       # 每拍毫秒
    delta = t - base[0]
    if abs(delta) < 1e-9:
        return base[0]
    sign = 1.0 if delta > 0 else -1.0
    units = round(abs(delta) / msb * 24.0)
    return base[0] + sign * units / 24.0 * msb


# -------------------------------------------------------------- 主流程的零件(convert 用)
# convert() 只做编排; 具体每一步都拆成下面这些纯函数, 便于单独推敲和测试。
# 它们的输入输出都是普通数值/列表/dict, 不碰文件系统, 也不依赖 osu2tja2 的全局状态。

def collect_events(circles, rolls, balloons):
    """把三类音符摊平成一条按时刻升序的事件流。

    每条是 `(时刻, 种类, 字符)`, 种类取值 note / roll_start / roll_end /
    balloon_start / balloon_end —— 连打与气球要**起止两条**(中间空格由渲染那步填)。
    排序是稳定的: 同一毫秒上的多条保持「音符 -> 连打 -> 气球」的原始次序。
    """
    events = [(t, 'note', ch) for t, ch in circles]
    for r in rolls:
        events.append((r['t'], 'roll_start', r['char']))
        events.append((r['end'], 'roll_end', ONP_END))
    for b in balloons:
        events.append((b['t'], 'balloon_start', ONP_BALLOON))
        events.append((b['end'], 'balloon_end', ONP_END))
    if not events:
        raise ValueError('这个 .osu 里没有任何可转换的音符')
    events.sort(key=lambda e: e[0])
    return events


def last_sounding_ms(circles, rolls, balloons):
    """谱面里最后一个「还在发声」的时刻 —— 尾部裁剪的硬下限。

    ⚠ 连打/气球取**终点**('end'), 不是起点: 从起点截断等于把长条切成半截,
      会留下没有结尾的 '5'/'7', 谱面直接坏掉。
    """
    ends = ([t for t, _ in circles]
            + [r['end'] for r in rolls]
            + [b['end'] for b in balloons])
    return max(ends) if ends else 0.0


def board_origin(timing, events):
    """谱面起点 —— 写出的 OFFSET 的唯一输入。

    取「第一条红线」与「首个音符吸附到 1/24 拍网格之后」的更早者。前人在首个音符
    早于红线时会补一条合成红线并把音符挪上去; 我们不挪音符, 所以吸附万一把起点
    推到音符之后, 就退回音符本身的时刻 —— 保证没有任何音符落在谱面起点之前。
    (实测 8 首语料里两种写法取值完全相同。)
    """
    first_red = timing.reds[0][0]
    first_note = events[0][0]
    o = min(first_red, snap_beat_24(first_note, timing))
    return first_note if o > first_note else o


def extend_end_for_tail(timing, end_time):
    """把结束时刻往后延到「末音符之后一个小节内」的最后一个计时点。

    最常见的就是最后一条 #GOGOEND —— 丢掉它, GOGO 状态会一直挂到谱面结束,
    演出就和 osu / 本家不一致了(Irregular Clock: 末音符 137.10s, kiai 在 137.99s
    才关, 本家谱面也确实把这一下画了出来)。超过一个小节的计时点不再追, 那属于
    下一段的元数据。
    """
    t = timing.msb_at(end_time)
    horizon = end_time + t[1] * float(t[2])
    tail = [x[0] for x in timing.reds + timing.greens + timing.kiais
            if end_time < x[0] <= horizon]
    return max(tail) + 1.0 if tail else end_time


def scroll_base_of(slider_mult) -> float:
    """SliderMultiplier -> `#SCROLL` 的基准系数(osu 默认的 1.4 记作 1.0)。

    osu!taiko 的实际滚动速度 ∝ SliderMultiplier × 绿线 SV × BPM, 而 TJA 的
    `#SCROLL` 只有一个数, 所以要把这个全局倍率折进去。依据(2023 官方论坛实测帖
    1851087): 默认皮肤 245 px/拍 = 175 × 1.4; 谱面设成 1.6 → 280 px/拍。
    ⚠ osu 常把 1.4 存成 1.39999996870756(浮点写回文件), 这种噪声按 1.0 处理,
      否则整首谱的 `#SCROLL` 会被乘上一个毫无意义的 0.99999998。
    """
    base = float(slider_mult or 1.4) / 1.4
    return 1.0 if abs(base - 1.0) < 1e-4 else base


def balloon_boost(balloons, timing, scroll_base, cut_times):
    """气球(拨浪鼓)「提前显示」补偿: 算出需要强制 1HS 的区间, 并改写命令点列表。

    判据见 BALLOON_MIN_EFF_BPM 上方: 等效 BPM(= 当前 BPM × #SCROLL)小于阈值时,
    osu 里那个气球其实是「快到才画出来」的, 本家没有这机制, 所以整段改成 1HS。

    返回 `(spans, over, cut_times)`:
      spans     需要强制 1HS 的区间 [(t0, t1), ...]
      over      {round(时刻,6): 手动指定的原始 SV} —— 该时刻的 SCROLL 用这个值
      cut_times 已剔除区间内原有绿线、并补上两端时刻的新列表
    """
    spans, over = [], {}
    for bl in balloons:
        t0, t1 = bl['t'], bl['end']
        if t1 <= t0:
            continue
        hs = scroll_value(timing.sv_at(t0), scroll_base)
        bpm0 = 60000.0 / timing.msb_at(t0)[1]
        if hs * bpm0 >= BALLOON_MIN_EFF_BPM:
            continue
        spans.append((t0, t1))
        # 原始 SV 写 1.0/scroll_base: scroll_value() 乘回 base 之后正好是 1.0
        over[round(t0, 6)] = 1.0 / scroll_base if scroll_base else 1.0
        # 恢复值取气球**结束之后**那一刻的原谱 SV(+0.5ms 避开边界上那条绿线)
        over[round(t1, 6)] = timing.sv_at(t1 + 0.5)
    if spans:
        # 区间内原有的绿线全部让位(否则会在气球中途把流速打回极低)
        cut_times = [c for c in cut_times
                     if not any(a - 1e-9 <= c < z - 1e-9 for a, z in spans)]
        cut_times = sorted(set(cut_times) | {t for span in spans for t in span})
    return spans, over, cut_times


def place_commands(bars, cut_times, balloon_over, timing, scroll_base) -> None:
    """把每个命令点(SCROLL / GOGO 的换值时刻)归到它所在的小节里。

    ⚠ 必须按**未吸附的原始切点**取 SV / Kiai 值: 若按吸附后的时刻去查, 可能取到
      它自己那条绿线之前的值, 整条 SV 渐变就整体滞后一格(实测 People People
      晚 130~260ms)。
    """
    ci = 0
    for b in bars:
        while ci < len(cut_times) and cut_times[ci] < b['end'] - 1e-9:
            c = cut_times[ci]
            if c >= b['start'] - 1e-9:
                raw = balloon_over.get(round(c, 6), timing.sv_at(c))
                b['cuts'].append((c, scroll_value(raw, scroll_base),
                                  timing.kiai_at(c), raw))
            ci += 1


def place_notes(bars, events) -> None:
    """把事件流按 [start, end) 分派到各个小节。

    真正「正好落在小节线上」的时刻由 choose_grid 允许的 0..N 号格 + carry 处理,
    误差为 0。
    """
    j = 0
    for ei, (t, kind, ch) in enumerate(events):
        while j + 1 < len(bars) and t >= bars[j]['end'] - 1e-9:
            j += 1
        bars[j]['events'].append((t, kind, ch, ei))


def align_last_bar(bars) -> None:
    """把末小节长度对齐到 1/4 拍, 并保证最后一个事件之后至少留半拍。

    末小节不是由红线量出来的, 而是「最后一个音符之后补齐」算出来的, 长度里带着
    整数毫秒的取整噪声 —— 实测写出过 `#MEASURE 4001/4000`。它又是全谱唯一没有
    下一条红线来「截断」的小节, 所以必须在这里对齐。
    留半拍的理由: 否则末音符会被挤到小节末尾的格号 N 上, 被当成「压在小节线上」
    交给并不存在的下一小节, 最后退回 N-1 格(整格的时间误差)。
    """
    if not bars:
        return
    lb = bars[-1]
    last = max((t for t, k, ch, ei in lb['events']), default=lb['start'])
    step = lb['msb'] * 0.25
    need = (last - lb['start']) + lb['msb'] * 0.5
    # 现有长度就近取整到 1/4 拍(把取整噪声抹掉), 再与「需要的最小长度」取大, 最后向上对齐
    base = max(need, round((lb['end'] - lb['start']) / step) * step)
    length = math.ceil((base - 1e-9) / step) * step        # 单位: 毫秒
    lb['end'] = lb['start'] + length
    lb['beats'] = length / lb['msb']


# -------------------------------------------------------------- 碎小节的二分
# 背景(2026-11-15, 用户报 Checklist (feat. Chromeo) 31 秒处「音符不在整齐网格上」):
#   一个小节里如果同时出现 1/7、1/9 这种互质的细分, `_bar_subdiv` 只能给出它们的
#   最小公倍 —— 实测那一个小节的理想格数是 **2016 格**(远超 GRID_CAP_CELLS),
#   退一步落到 864 格: 音符时刻仍然 ≤1ms, 但每拍 216 格, 写成 TJA 就是一行
#   864 个字符、音符落在 71/143/287 这种毫无规律的格号上 —— 看着就是"没对齐"。
#
#   而 TJA 本来就允许用 `#MEASURE n/d` 把一个小节拆成几段(本家谱面里
#   `#MEASURE 17/16` 这种写法就有)。拆开之后每一段只需容纳**自己那段**的细分:
#   同一个位置可以写成「前 2 拍 48 格 + 中间半拍 7 格(七连音) + 后半拍 9 格 ……」,
#   每段各自 choose_grid, 各自落在整齐的格网上。
#
# ── 判据: 按「每拍几格」卡, 不能按「每小节几格」卡 ──────────────────────────
#   一拍 48 格 = 1/48 拍一格, 这已经是 GAP_SUBDIV 认得的最细节奏型; 比它还细,
#   说明这一段是 choose_grid 退档退出来的, 音符必然落在乱七八糟的格号上。
#   所以: 只在 `N > SPLIT_MAX_DENSITY × beats` 时才拆(另外 192 格是绝对上限,
#   它管的是「一行不要太长」, 对 4/4 小节正好等于 48/拍)。
#   ★ 按每小节 N 卡是错的: 那样会把「四四拍写 1/16」这种最标准的 64 格小节也切碎。
#
#   拆完必须 ① 最碎的那一段比原来小(`max(sub) < N`) ② 总格数 ≤ 原来的 2 倍。
#   两条缺一就不拆 —— 宁可照原样写, 也不要把谱面拆成一堆没意义的碎节。
#
# 实测(密度 48 / 绝对 192 / 最短半拍可拆, 即最小成品段 1/4 拍):
#   谱面        小节        总格          最大小节
#   Checklist   67->227     27592->5864   1152->192
#   Talk        108->196    15184->7559   1008->192
#   BUZZ CUTZ   486->598    27048->20031  768->192
#   ON.UR.MARKS 327->533    36330->25550  1248->192
#   vs.VIGVANGS 171         4066(不变)    48(不变)
#   One of Us   248->249    5536(不变)    256->128
#   ★ 音符数 / 偏差 / SV 全都没动(见 tmp/_cmp_split.py): 拆小节只改「一行画几格」。
#   ★ 「拍分母 > 48」的音符数: Checklist 23->4、Talk 18->11、BUZZ 14->7、其余为 0。
SPLIT_MAX_CELLS = 192
SPLIT_MAX_DENSITY = 48
SPLIT_MAX_DEPTH = 6
# 半拍以下的小节不再拆。判的是**被拆的那一节**, 所以成品段最细到 1/4 拍。
# 再细就没意义: 1/4 拍里通常只剩 1~2 个音符, 拆了总格数反而涨(实测 Checklist 的
# 半拍 N=560 那三处, 必须允许再拆一次才收得干净)。
SPLIT_MIN_BEATS = 0.5


def _grid_for_bar(b, base_subdiv: int):
    """按 render_body 的口径算出这个小节要多少格(返回 (D, N))。"""
    note_pos, fuzzy_pos = [], []
    for t, k, ch, ei in b['events']:
        (fuzzy_pos if k in ('roll_end', 'balloon_end') else note_pos).append(
            (t - b['start']) / b['msb'])
    cmd_pos = [(t - b['start']) / b['msb'] for t, sv, kiai, raw in b['cuts']]
    return choose_grid(b['beats'], note_pos, cmd_pos, b['msb'], base_subdiv,
                       fuzzy_pos=fuzzy_pos)


def _split_bar(b, base_subdiv: int, max_cells: int, depth: int = 0):
    """密度超标就二分(递归), 返回若干「小节样」的 dict。"""
    D, N = _grid_for_bar(b, base_subdiv)
    # ⚠ beats 是 (end-start)/msb 算出来的浮点: 本该正好 1.0 的小节常常是
    #   0.9999999996 —— 不减去 1e-6 的话, 这些小节会被当成"已经短于下限"而放弃
    #   拆分, 实测正是 Checklist 里几个超大节一直拆不干净的元凶。
    cap = min(max_cells, SPLIT_MAX_DENSITY * b['beats'])
    if (N <= cap or b['beats'] < SPLIT_MIN_BEATS - 1e-6
            or depth >= SPLIT_MAX_DEPTH):
        b['D'], b['N'] = D, N
        return [b]

    mid = b['start'] + (b['beats'] / 2.0) * b['msb']
    pieces = []
    for first in (True, False):
        p = dict(b)
        p.pop('D', None)
        p.pop('N', None)
        p['start'], p['end'] = (b['start'], mid) if first else (mid, b['end'])
        p['beats'] = (p['end'] - p['start']) / b['msb']
        # 拆出来的段不是真的小节线: 除第一段外一律藏线, 让画面仍是原来的小节
        p['omit'] = b['omit'] if first else True
        # `fragment` = 「这一节比标称小节短」, 摘要里的「N 个是切分出来的片段」就是数它
        p['fragment'] = p['beats'] < b['meter'] - 1e-6
        p['events'] = [e for e in b['events'] if (e[0] < mid) == first]
        p['cuts'] = [c for c in b['cuts'] if (c[0] < mid) == first]
        if not first:
            # 后半段的起始流速/GOGO 必须是**拆点那一刻**的状态 —— 否则前半段里
            # 改过的 SV 会被后半段的第一段继承成旧值(#SCROLL 少写一条)。
            for t, sv, kiai, raw in b['cuts']:
                if t < mid - 1e-9:
                    p['scroll'], p['scroll_raw'], p['kiai'] = sv, raw, kiai
        pieces.append(p)

    out = []
    for p in pieces:
        out.extend(_split_bar(p, base_subdiv, max_cells, depth + 1))
    ns = [x['N'] for x in out]
    if max(ns) < N and sum(ns) <= 2 * N:
        return out
    b['D'], b['N'] = D, N          # 拆了没好处 -> 原样返回
    return [b]


def split_fine_bars(bars, base_subdiv: int, max_cells: int = None):
    """把「密度超标」的小节二分掉。返回新的小节列表(顺序不变)。

    `max_cells` 缺省时才去读 `SPLIT_MAX_CELLS` —— 不能写成默认参数值, 那个在 def
    的时候就被固定下来了, 之后再改模块常量不会生效(调试时被这一点坑过)。
    """
    if max_cells is None:
        max_cells = SPLIT_MAX_CELLS
    out = []
    for b in bars:
        out.extend(_split_bar(b, base_subdiv, max_cells))
    return out


def render_body(bars, rolls, balloons, base_subdiv: int = 4,
                barline: str = 'auto', reset_barline: bool = False):
    """逐小节排版, 生成 `#START` 之后的全部正文行。

    返回 `(out_lines, balloon_hits)`:
      out_lines     正文行(已含结尾的 `#END`)
      balloon_hits  `BALLOON:` 头部要写的气球击打数, 按出现顺序(每个气球一项)

    一个小节的处理次序是固定的:
      ① `choose_grid` 定「每拍格数 D / 总格数 N」(音符优先, 命令点松绑);
      ② 写小节级命令 `#MEASURE` / `#BPMCHANGE` / `#BARLINEOFF`;
      ③ 把事件铺进 slots —— **同一格只能活一个字符**;
      ④ 按命令点把本小节切成 segs, 段与段之间插 `#SCROLL` / `#GOGO`。

    `reset_barline` = 正文第一小节无条件重发一次小节线状态。多难度时每段是一个独立
    `#START` 块, 上一段可能停在 `#BARLINEOFF` 上 —— 不重发的话, 下一段要不要画线
    取决于模拟器是否在 `#START` 复位, 靠猜不如写明。单谱保持默认 False(字节不变)。

    ⚠ ③ 的「一格一个字符」是覆盖写法: 两个音符落进同一格, 前一个会**从谱面上消失**。
      所以 choose_grid 里有 `_note_collapse` 专门拦这种事, 这里不再重复判。
    """
    # 连打/气球的终点索引: 事件流里只有起点, 终点要按时刻回查(osu 里没有别的字段能推)
    roll_end, balloon_end = {}, {}
    for r in rolls:
        roll_end.setdefault(r['t'], r['end'])
    for bl in balloons:
        balloon_end.setdefault(bl['t'], bl['end'])

    out_lines = []
    cur_bpm = cur_scroll_raw = None
    cur_kiai = False
    cur_measure = None
    # None = 「状态未知」-> 第一小节一定写一条 BARLINE 命令(多难度复位用); False = 已知是 ON
    barline_off = None if reset_barline else False

    balloon_hits = []
    for b in bars:
        for t, kind, ch, ei in b['events']:
            if kind == 'balloon_start':
                # 本家 BALLOON: 写的是「要打几下」—— osu 的 spinner 没有次数,
                # 按每 100ms 一下折算, 并夹在 1..99(本家惯例的上限)
                balloon_hits.append(
                    max(1, min(99, int(round((balloon_end[t] - t) / 100.0)))))

    carry = []
    for bi, b in enumerate(bars):
        L = b['beats']
        note_pos, fuzzy_pos = [], []
        for t, k, ch, ei in b['events']:
            (fuzzy_pos if k in ('roll_end', 'balloon_end') else note_pos).append(
                (t - b['start']) / b['msb'])
        cmd_pos = [(t - b['start']) / b['msb'] for t, sv, kiai, raw in b['cuts']]
        # split_fine_bars() 已经算过一遍的就不用重算(它把结果留在 b['D']/b['N'])
        D, N = b.get('D'), b.get('N')
        if D is None or N is None:
            D, N = choose_grid(L, note_pos, cmd_pos, b['msb'], base_subdiv,
                               fuzzy_pos=fuzzy_pos)
        b['D'], b['N'] = D, N
        cell = L / N

        n, d = beats_to_measure(L)
        cmds = []
        measure_changed = (cur_measure != (n, d))
        bpm_changed = (cur_bpm is None or abs(b['bpm'] - cur_bpm) > 1e-6)
        if measure_changed:
            cmds.append('#MEASURE %d/%d' % (n, d))
            cur_measure = (n, d)
        if bpm_changed:
            cmds.append('#BPMCHANGE %s' % fnum(b['bpm']))
            cur_bpm = b['bpm']

        # 小节线是否隐藏: 直接读 osu 的 "Omit first bar line"(effects 的 bit3)。
        # 旧版按「小节短于 1 拍就隐藏」猜 —— 那个启发式已经废掉: 实测本家里长短小节
        # 都照常画线, 而 osu 文件里本来就写着该不该隐藏。
        need_off = (barline == 'hide') or (barline == 'auto' and b['omit'])
        if need_off != barline_off:
            cmds.append('#BARLINEOFF' if need_off else '#BARLINEON')
            barline_off = need_off

        if cmds:
            out_lines.append('')
            out_lines.extend(cmds)

        # ---- 铺字符 ----
        slots = ['0'] * N
        carry_next = []
        roll_spans = []
        for t, kind, ch, ei in b['events']:
            # ⚠ 这里**不能**用 _cell_index(): 它会把格号夹到 N, 而铺格必须先看出
            #   「i >= N(压在小节线上)」再决定是交给下一小节还是退回 N-1。
            i = int(round((t - b['start']) / b['msb'] / cell))
            if i >= N:
                # 正好压在小节线上 -> 交给下一小节第 0 格(时刻完全一致, 误差 0)
                if bi + 1 < len(bars):
                    carry_next.append(ch)
                    continue
                i = N - 1
            i = max(0, i)
            slots[i] = ch
            if kind == 'roll_start':
                roll_spans.append((i, roll_end[t]))
            elif kind == 'balloon_start':
                roll_spans.append((i, balloon_end[t]))
        # 连打/气球内部一律填空
        for i0, end_t in roll_spans:
            jj = int(round((end_t - b['start']) / b['msb'] / cell))
            jj = max(0, min(N, jj))
            for kk in range(i0 + 1, jj):
                slots[kk] = '0'
        # 上一小节挤过来的字符(压在小节线上的那一下)落到第 0 格
        for ci2, ch in enumerate(carry):
            if ci2 >= N:
                break
            if slots[ci2] == '0':
                slots[ci2] = ch
        carry = carry_next

        # ---- 小节内部的命令分段: [(起始格, scroll, kiai, scroll_raw), ...] ----
        # ⚠ 同一格的多条命令只有最后一条存活, 前一条被覆盖 = 它影响的音符用错流速。
        #   所以档位选择那一步 (_cmd_collapse) 会尽力保证命令点各占一格。
        segs = []
        for t, sv, kiai, sv_raw in ([(b['start'], b['scroll'], b['kiai'], b['scroll_raw'])]
                                    + list(b['cuts'])):
            i = int(round((t - b['start']) / b['msb'] / cell))
            if i > N:
                continue
            i = max(0, i)
            if segs and segs[-1][0] == i:
                segs[-1] = (i, sv, kiai, sv_raw)
            else:
                segs.append((i, sv, kiai, sv_raw))
        if not segs:
            segs = [(0, b['scroll'], b['kiai'], b['scroll_raw'])]

        # ⚠ 这里的 `any(slots)` 判的其实是「元素是不是非空字符串」, 而 '0' 是非空字符串,
        #   所以它恒为真 —— 这一支实际上走不到, 空小节一律被写成「一行 N 个 0」。
        #   语义上没问题(小节长度由 #MEASURE + BPM 决定, 与格数无关, 本家谱面里的空小节
        #   两种写法都有), 而且单谱转换里空小节极少, 所以**刻意保持原样**: 改它会动到
        #   已经验收过的产物字节。多难度开头那几段等待小节也就沿用这个写法。
        if not b['events'] and not any(slots):
            # 空小节: 没有中途命令就直接写 ','; 有命令点才写占位字符(命令靠字符定位)
            slots = [] if len(segs) == 1 else ['0'] * N

        # ---- 按分段输出(段间插命令, 只有最后一段带逗号) ----
        # ★ 换小节长度 / 换 BPM 的那一小节, 即使流速没变也把当前 #SCROLL 重发一次
        #   (2026-11-15)。理论上 `#SCROLL` 是「持续到下一条」, 不必重发; 但实测有
        #   模拟器在读 #MEASURE 重建小节时把滚动状态清掉, 表现就是「从某个 #MEASURE
        #   起流速不再跟原谱」—— 用户报的 One of Us 2:11 那段正是这种位置(8/4 -> 4/4)。
        #   多发一条同值命令零副作用(值一样、位置一样), 只多几行, 却能兜住这种情形。
        reassert_scroll = (measure_changed or bpm_changed) and \
            cur_scroll_raw is not None and abs(b['scroll_raw'] - cur_scroll_raw) <= 1e-9
        for si, (i0, sv, kiai, sv_raw) in enumerate(segs):
            i1 = segs[si + 1][0] if si + 1 < len(segs) else N
            # 与上一段的**原始** SV 比: 「要不要写这条命令」只由原谱决定,
            # 不受 SliderMultiplier 的缩放与舍入影响
            if reassert_scroll and si == 0:
                out_lines.append('#SCROLL %s' % fnum(sv))
                cur_scroll_raw = sv_raw
                reassert_scroll = False
            elif cur_scroll_raw is None or abs(sv_raw - cur_scroll_raw) > 1e-9:
                out_lines.append('#SCROLL %s' % fnum(sv))
                cur_scroll_raw = sv_raw
            if kiai != cur_kiai:
                out_lines.append('#GOGOSTART' if kiai else '#GOGOEND')
                cur_kiai = kiai
            body = ''.join(slots[i0:i1]) if slots else ''
            if si + 1 == len(segs):
                out_lines.append(body + ',')
            elif body:
                out_lines.append(body)

    # 丢掉末尾的空小节(末小节补齐后可能一行音符都没有)
    while out_lines and out_lines[-1].strip() in ('', ',', '0,'):
        out_lines.pop()

    out_lines.append('')
    out_lines.append('#END')
    return out_lines, balloon_hits


def render_file_head(title: str, artist: str, wave: str, bpm: float,
                     offset_ms: float, demo_ms: float, src_names):
    """TJA 的**文件级**头部 —— 整个文件只写一次, 所有难度共用。

    `TITLE/ARTIST/SUBTITLE/BPM/WAVE/OFFSET/DEMOSTART` 这几行在多难度文件里是
    **全局**的(见 本家谱面/8OROCHI/8OROCHI.tja: 5 段难度共用最前面那一份 BPM 与
    OFFSET)。BPM 写的是第一段的值, 各段自己的 BPM 由正文开头的 `#BPMCHANGE` 决定,
    所以即使两张谱的 BPM 不同也不会互相影响。

    `src_names` 可以是单个文件名或一列文件名 —— 注释行据此列出这次用了哪几个 .osu。
    """
    if isinstance(src_names, str):
        src_names = [src_names]
    listed = ', '.join('"%s"' % os.path.basename(n) for n in src_names)
    return [
        'TITLE:%s' % title,
        'ARTIST:%s' % artist,
        'SUBTITLE:--%s' % artist,
        'BPM:%s' % fnum(bpm),
        'WAVE:%s' % wave,
        'OFFSET:%.3f' % offset_ms,
        'DEMOSTART:%.3f' % (demo_ms / 1000.0),
        'SONGVOL:100',
        'SEVOL:100',
        'SCOREMODE:2',
        '//Converted from %s by osu2tja2' % listed,
    ]


def render_course_head(course: str, level: int, balloon_hits):
    """一段难度自己的头部: `COURSE` / `LEVEL` / `BALLOON` + `#START`。

    `LEVEL` 就是模拟器里显示的 ★×N —— TJA 没有独立的星数字段。
    `BALLOON` 写每个气球要打几下; 没有气球时是空串(本家惯例)。
    """
    return [
        'COURSE:%s' % course,
        'LEVEL:%d' % level,
        'BALLOON:%s' % ','.join(str(x) for x in balloon_hits),
        '',
        '#START',
    ]


def render_head(title: str, artist: str, wave: str, bpm: float, offset_ms: float,
                demo_ms: float, course: str, level: int, balloon_hits,
                src_name: str):
    """生成**单难度** TJA 的头部(从 `TITLE:` 到 `#START`)。

    · `ARTIST` 是本家头部里正式的曲师字段; `SUBTITLE` 再用 `--曲师` 写一遍,
      是因为多数模拟器的选曲列表显示的是 SUBTITLE, 只写 ARTIST 在游戏里看不见。
    · 单难度 = 文件头 + 一段段头, 两者之间空一行(本家谱面的写法)。
    多难度文件不走这里, 而是 render_file_head() 写一次、每段再各写一份
    render_course_head() —— 见 convert_multi()。
    """
    return render_file_head(title, artist, wave, bpm, offset_ms, demo_ms,
                            src_name) + [''] + render_course_head(course, level,
                                                                  balloon_hits)


def write_tja(path: str, head, body, encoding: str) -> None:
    """按 TJA 惯例写盘: CRLF 换行 + 指定编码。

    `errors='replace'` 是最后一道保险 —— 正常路径上 resolve_encoding() 已经保证
    编码能容纳标题/曲师, 走到 replace 说明有更冷僻的字符混进了正文。
    """
    text = '\r\n'.join(list(head) + list(body)) + '\r\n'
    with open(path, 'wb') as f:
        f.write(text.encode(encoding, errors='replace'))


def deliver_audio(plan: dict, last_event_ms: float, demo_ms: float,
                  copy_audio: bool = True, trim_audio: bool = True,
                  trim_tail_ms: float = None):
    """把音源落到输出目录(必要时转码 / 裁尾)。

    返回 `(copied, error, skipped, trim)`:
      copied    是否已经产出音源文件
      error     失败原因(空 = 成功或本来就不用做)
      skipped   是否按 --no-copy-audio 主动跳过
      trim      plan_trim() 的结果, 供摘要与 GUI 报数用
    """
    copied, error, skipped = False, '', False
    trim = {'action': 'off', 'orig_ms': 0.0, 'cut_ms': 0.0, 'gain_ms': 0.0, 'note': ''}
    if plan['action'] not in ('copy', 'transcode'):
        return copied, error, skipped, trim
    if not copy_audio:
        return copied, error, True, trim
    try:
        os.makedirs(os.path.dirname(plan['dst']), exist_ok=True)
        # 先算要不要裁尾; 要裁就把「直接拷贝」升级成「重编码到 cut_ms」。
        trim = plan_trim(plan['src'], last_event_ms, demo_ms,
                         trim_tail_ms, enabled=trim_audio)
        if trim['action'] == 'trim':
            _transcode_ogg(plan['src'], plan['dst'], trim['cut_ms'])
        elif plan['action'] == 'copy':
            shutil.copy2(plan['src'], plan['dst'])
        else:
            _transcode_ogg(plan['src'], plan['dst'])
        copied = True
    except Exception as e:          # ffmpeg 报错 / 没装 / 磁盘满 都在这
        error = str(e)
    return copied, error, skipped, trim


def display_names(meta, title_opt=None, artist_opt=None, allow_name_fallback=True):
    """选 TITLE / ARTIST。返回 `(title, artist, 提示语列表)`。

    默认用原名(`TitleUnicode` / `ArtistUnicode`); 判出源字段写坏了才退到罗马音,
    判据见 looks_mojibake()。`--title` / `--artist` 的显式覆盖优先级最高。
    """
    title, tn = pick_display_name(meta, 'Title', 'TitleUnicode',
                                  title_opt, allow_name_fallback)
    artist, an = pick_display_name(meta, 'Artist', 'ArtistUnicode',
                                   artist_opt, allow_name_fallback)
    return title, artist, [x for x in (tn, an) if x]


# -------------------------------------------------------------- 星级(SR)
# SR 不在 .osu 里 —— 它是客户端按谱面内容算出来的, 而且**跟着算法版本变**。
# 两个来源, 按可信度排:
#   ① `osu!.db` 里客户端缓存的星级 —— 就是你在游戏里看到的那个数
#   ② rosu-pp-py 本地重算           —— **落后于 osu! 2026-07-03 的星数重构**
# 2026-11-15 拿 osu.ppy.sh 官网页面里的 difficulty_rating 当基准, 逐张对过:
#   ① 20/21 逐位吻合(唯一差的一张差 0.001, 客户端缓存略旧)
#   ② 全部偏高, 平均 +0.046, 最高 +0.264(MASTER 7.3081 vs 官方 7.0445)
# 原因: osu! 在 2026-07-03 重做了星数(新增 Reading 技能、速度改调和求和), 而
# rosu-pp 目前最新版 4.0.2 实现的仍是 2025-10-29 那版公式 —— 换旧版 rosu 只会更偏,
# 没有任何本地库能复现现行公式。所以**默认读 db**, 拿不到才退回重算。
#
# db 条目布局(实测 version=20260924; md5 之后的部分):
#     md5(32 字节) + osuFileName(0x0B + uLeb128 长度 + utf8)
#     +1  ranked status          +6  3×short(圆圈/滑条/转盘数)
#     +8  long 最后修改时间       +16 4×float AR/CS/HP/OD
#     +8  double SliderMultiplier +4  int(保留)
#     +4  int 星级条目数(通常 9)  然后每个 10 字节: [08][int mods][0C][float 星数]
# 9 个条目的 mods 是 NM/DT/HT/HR/HRDT/HRHT/EZ/EZDT/EZHT, **mods==0 那条就是 No Mod 星级**。
_OSU_DB_BYTES = {}          # osu!.db 路径 -> 文件内容(一次读进内存, 3~10MB)
_SR_SOURCE = {}             # .osu 绝对路径 -> 'db' / 'calc'
_SR_WARNED = set()          # 只提醒一次的提示类别


def _warn_once(key: str, msg: str):
    if key not in _SR_WARNED:
        _SR_WARNED.add(key)
        print(msg, file=sys.stderr)


def osu_db_paths(sample_path=None):
    """列出可能放着 `osu!.db` 的位置。

    先顺着输入文件往上找(输入一般长在 `<osu!>/Songs/<谱面集>/xxx.osu`, 往上两三层
    就是 `<osu!>`), 再试常规安装位置。返回的都是**确实存在**的路径。
    """
    seen = []

    def add(p):
        p = os.path.abspath(p)
        if p not in seen and os.path.isfile(p):
            seen.append(p)

    d = os.path.dirname(os.path.abspath(sample_path)) if sample_path else None
    for _ in range(5):
        if not d:
            break
        add(os.path.join(d, 'osu!.db'))
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    la = os.environ.get('LOCALAPPDATA')
    if la:
        add(os.path.join(la, 'osu!', 'osu!.db'))
    for songs in DEFAULT_INPUT_DIRS:            # 这些是 Songs 目录, 上一级才是 osu! 根
        add(os.path.join(os.path.dirname(songs.rstrip('\\/')), 'osu!.db'))
    return seen


def _db_lookup(buf: bytes, md5_hex: str):
    """在一份 osu!.db 的内容里按 md5 找这张谱的 No Mod 星级。找不到/格式不符返回 None。"""
    pos = buf.find(md5_hex.encode('ascii'))
    if pos < 0:
        return None
    c = pos + 32
    if c >= len(buf) or buf[c] != 0x0B:         # md5 后面必须紧跟 0x0B 串(.osu 文件名)
        return None
    n = 0
    sh = 0
    i = c + 1
    while i < len(buf):                          # uLeb128 长度
        x = buf[i]
        i += 1
        n |= (x & 0x7f) << sh
        sh += 7
        if not x & 0x80:
            break
    i += n                                       # 跳过文件名 -> ranked status 处
    if i + 47 + 4 > len(buf):
        return None
    cnt = struct.unpack_from('<i', buf, i + 43)[0]
    if not 0 < cnt < 200:
        return None
    for k in range(cnt):
        q = i + 47 + k * 10
        if q + 10 > len(buf):
            return None
        if struct.unpack_from('<i', buf, q + 1)[0] == 0:    # mods == 0 -> No Mod
            v = struct.unpack_from('<f', buf, q + 6)[0]
            return v if 0.0 <= v < 40.0 else None
    return None


def _osu_md5_and_mode(path: str):
    """一次读完 .osu: 返回 `(md5, Mode)`。读不了就是 (None, None)。

    md5 用来在 db 里定位记录; Mode 用来确认这张谱本身是 taiko —— 因为 db 里存的是
    「这张谱自己那个模式」的星级, 拿 std 谱的 std 星级去填 taiko 的 LEVEL 是错的。
    """
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except OSError:
        return None, None
    mode = None
    for line in raw.decode('utf-8', 'replace').splitlines():
        if line.startswith('Mode:'):
            mode = line.split(':', 1)[1].strip()
            break
        if line.startswith('[HitObjects]'):
            break
    return hashlib.md5(raw).hexdigest(), mode


def star_from_db(path: str):
    """读 `osu!.db` 里缓存的星级。谱没导入过(或未提交到官网)就返回 None。"""
    md5, mode = _osu_md5_and_mode(path)
    if md5 is None:
        return None
    if mode is not None and mode != '1':        # 非 taiko: db 值不是 taiko SR
        return None
    for db_path in osu_db_paths(path):
        buf = _OSU_DB_BYTES.get(db_path)
        if buf is None:
            try:
                with open(db_path, 'rb') as f:
                    buf = f.read()
            except OSError:
                continue
            _OSU_DB_BYTES[db_path] = buf
        v = _db_lookup(buf, md5)
        if v is not None:
            return v
    return None


def star_from_calc(path: str):
    """用 rosu-pp-py 本地重算星级(算不了返回 None)。

    ⚠ 它实现的是 **2025-10-29** 那版公式, 比官网现行值系统性偏高(实测最高 +0.26),
      只当兜底用。缺包不算错误 —— 绝不因为缺依赖让转换失败。
    """
    try:
        from rosu_pp_py import Beatmap, Difficulty
    except Exception as e:
        _warn_once('nocalc',
                   '⚠ 用不了 rosu-pp-py(%s: %s), 算不了 SR, 星数一律回退 ★%d。\n'
                   '  想要自动星数: py -m pip install rosu-pp-py'
                   % (type(e).__name__, e, DEFAULT_LEVEL))
        return None
    try:
        return float(Difficulty().calculate(Beatmap(path=path)).stars)
    except Exception as e:
        _warn_once('calc:%s' % e, '⚠ 算 SR 失败(%s: %s)' % (type(e).__name__, e))
        return None


def taiko_star_rating(path: str):
    """这张 .osu 的 osu!taiko 星级(SR, No Mod)。拿不到就返回 None。

    先读 `osu!.db` 缓存(= 游戏里显示的数, 与官网一致), 读不到才用 rosu-pp 重算。
    见上面那段注释里的实测对比。
    """
    v = star_from_db(path)
    if v is not None:
        _SR_SOURCE[os.path.abspath(path)] = 'db'
        return v
    v = star_from_calc(path)
    if v is not None:
        _SR_SOURCE[os.path.abspath(path)] = 'calc'
        _warn_once('nodb',
                   '⚠ 有谱面不在 osu!.db 里(没导入过), 星数改用 rosu-pp 估算;\n'
                   '  它落后于 osu! 2026-07 的星数重构, 值可能偏高 0.05~0.3。')
    return v


def sr_source_label(path: str) -> str:
    """星级是从哪来的(`osu!.db` / `rosu-pp` / 空)。只用于打印。"""
    return {'db': 'osu!.db', 'calc': 'rosu-pp'}.get(
        _SR_SOURCE.get(os.path.abspath(path)), '')


def difficulty_of(course_opt, version: str, level_opt=None, sr=None):
    """决定 `COURSE` 与 `LEVEL`。返回 `(course, level)`。

    COURSE 默认 Oni(魔王); `--course auto` 才回到「按 .osu 的 Version 猜」的老行为。
    LEVEL 就是模拟器里显示的 ★×N(TJA 没有独立的星数字段), 优先级:
        `--level` 显式给的 > `sr × 2` 四舍五入 > 兵底 DEFAULT_LEVEL。
    """
    course = course_opt or DEFAULT_COURSE
    if course == 'auto':
        course = guess_course(version)
    if level_opt is not None:
        return course, int(level_opt)
    if sr is not None:
        return course, star_from_sr(sr)
    return course, DEFAULT_LEVEL


def preview_point(meta: dict, demostart_s=None):
    """DEMOSTART —— 选曲界面试听从哪一声开始。返回 `(毫秒, 来源)`。

    TJA 的 `DEMOSTART:` 单位是秒、时间轴是**音频文件开头**; osu 的 `PreviewTime`
    同样是「从音频开头算的毫秒」→ 直接 /1000, 语义一一对应。
    ⚠ 千万别掺 OFFSET 去「修正」它: OFFSET 描述的是**谱面起点**落在音频的哪一刻,
      DEMOSTART 与谱面无关、只跟音频有关; 掺进去等于把系统延迟重复扣一次。
    osu 没设预览时 `PreviewTime` 是 -1(客户端自己挑高潮段), 这里退成 0 —— 与本家
      谱面不写 DEMOSTART 的行为一致, 绝不写负数。

    来源取值: `override`(--demostart 指定) / `osu`(照抄 PreviewTime) / `auto`(没设, 从 0)。
    """
    if demostart_s is not None:
        return max(0, int(round(float(demostart_s) * 1000.0))), 'override'
    try:
        demo_ms = int(round(float(meta.get('PreviewTime', -1))))
    except (TypeError, ValueError):
        demo_ms = -1
    return max(0, demo_ms), ('osu' if demo_ms >= 0 else 'auto')


def print_summary(summary: dict) -> None:
    """把一次转换的结果打到 stdout(`--quiet` 时不调用)。

    与 GUI 的完成弹窗**共用同一套 summary 字段**, 所以两处的说法不会跑偏。
    """
    trim = summary.get('audio_trim') or {}
    shift = summary.get('offset_shift_ms') or 0.0
    print('输入: %s' % summary['src'])
    print('输出: %s  [%s]' % (summary['dst'], summary['encoding_used']))
    sr = summary.get('star_sr')
    print('难度: %s ★%d%s' % (summary['course'], summary['level'],
                            '  (SR %.4f × 2 四舍五入, 取自 %s)'
                            % (sr, summary.get('star_src') or 'osu!.db')
                            if sr is not None else '  (算不了 SR, 用兜底值)'))
    print('  咚/咔/大音符 %d 条 | 连打 %d 条 | 气球 %d 个 | 小节 %d 个 (其中 %d 个是切分出来的片段)'
          % (summary['circles'], summary['rolls'], summary['balloons'],
             summary['bars'], summary['fragments']))
    if summary['balloons_boosted']:
        print('  气球提速: %d 个气球所在段流速慢于 %.0fBPM/1HS, 已在该段强制 #SCROLL 1'
              % (summary['balloons_boosted'], BALLOON_MIN_EFF_BPM))
    print('  OFFSET: %.3f  (谱面起点 %d ms%s)'
          % (summary['offset_written'], summary['origin_ms'],
             '' if not shift else ' + 全局微调 %+g ms' % shift))
    print('  DEMOSTART: %.3f  (%s)'
          % (summary['demostart_ms'] / 1000.0,
             {'osu': '照抄 osu 的 PreviewTime',
              'override': '按 --demostart 指定',
              'auto': 'osu 没设预览起点, 从音频开头'}[summary['preview_source']]))
    if summary['scroll_base'] != 1.0:
        print('  流速基准: SliderMultiplier %g -> #SCROLL 整体 ×%g'
              % (summary['slider_mult'], summary['scroll_base']))
    print('  音源: %s' % audio_report(summary))
    if trim.get('action') == 'trim':
        print('  裁尾: 原长 %.3f s -> 裁到 %.3f s  (省 %.1f s)'
              % (trim['orig_ms'] / 1000.0, trim['cut_ms'] / 1000.0,
                 trim['gain_ms'] / 1000.0))
    elif trim.get('note'):
        print('  裁尾: 跳过 (%s)' % trim['note'])
    if summary.get('encoding_warning'):
        print('  ⚠ %s' % summary['encoding_warning'])
    for n in summary.get('name_notes') or []:
        print('  ⚠ %s' % n)


def load_chart(src: str, encoding: str = 'cp932', barline: str = 'auto',
               base_subdiv: int = 4, red_grid: bool = True,
               offset_shift_ms: float = None, demostart_s: float = None,
               title_opt=None, artist_opt=None,
               allow_name_fallback: bool = True) -> dict:
    """解析一张 .osu, 算出**所有与排版无关**的东西, 返回 chart dict。

    这一步产出的是「这张谱是什么」(音符流、计时点、谱面起点、曲名、预览点), 至于
    「怎么排版成 TJA 文本」由 layout_chart() 负责 —— 两段拆开是为了多难度转换:
    几张谱必须共用同一个 OFFSET 和同一份音源, 所以要先各自解析、统一起点, 再排版。

    `origin` 是**这张谱自己的**起点; 多难度模式下真正用来排版的是
    `min(所有谱的 origin)`(见 convert_multi), 由 layout_chart 的 origin 参数传入。

    返回的 key 全部是普通数值/列表/dict, 不含任何文件句柄或全局状态。
    """
    if offset_shift_ms is None:
        offset_shift_ms = DEFAULT_OFFSET_SHIFT_MS
    data = parse_osu(src, red_grid=red_grid)
    meta, timing = data['meta'], data['timing']
    circles, rolls, balloons = data['circles'], data['rolls'], data['balloons']

    last_event_ms = last_sounding_ms(circles, rolls, balloons)
    events = collect_events(circles, rolls, balloons)
    origin = board_origin(timing, events)
    end_time = extend_end_for_tail(timing, max(events[-1][0], timing.reds[0][0]) + 1.0)

    # 流速基准(osu 的 SliderMultiplier -> #SCROLL 系数), 见 scroll_base_of()。
    # ⚠ 只影响观感, 不影响判定: 音符时刻 / 小节 / BPM 都不经过这里。
    slider_mult = float(data.get('slider_mult') or 1.4)
    scroll_base = scroll_base_of(slider_mult)

    title, artist, name_notes = display_names(meta, title_opt, artist_opt,
                                              allow_name_fallback)
    demo_ms, preview_source = preview_point(meta, demostart_s)

    return {
        'src': src, 'meta': meta, 'timing': timing,
        'circles': circles, 'rolls': rolls, 'balloons': balloons,
        'events': events, 'last_event_ms': last_event_ms,
        'origin': origin, 'end_time': end_time,
        'cut_times': timing_cuts(timing),
        'slider_mult': slider_mult, 'scroll_base': scroll_base,
        'bpm0': 60000.0 / timing.reds[0][1],
        'title': title, 'artist': artist, 'name_notes': name_notes,
        'demo_ms': demo_ms, 'preview_source': preview_source,
        'barline': barline, 'base_subdiv': base_subdiv,
        'offset_shift_ms': offset_shift_ms,
    }


def layout_chart(chart: dict, origin: float = None,
                 reset_barline: bool = False) -> dict:
    """把 load_chart() 的产物排成 TJA 正文, 结果**写回** chart 并返回它。

    `origin` = 谱面起点(毫秒)。省略时用这张谱自己的起点(单谱模式);
    多难度模式传「所有谱里最早的那个」, 让每段的小节 0 都落在同一个音频时刻上 ——
    TJA 里只有一个 OFFSET, 各段的第 0 小节必须是同一刻, 否则整段都会错位。

    起点早于这张谱的第一条红线时, build_bars() 会补一条合成红线, 于是这段谱开头
    会有若干空小节 —— 那是**对的**, 等价于本家谱面开头的等待小节。

    `reset_barline` 见 render_body(); 多难度每段都要传 True。

    写回 chart 的 key: bars / body / balloon_hits / balloon_spans / balloon_over。
    可以重复调用(每次重新建 bars), 不会污染 chart 里的切点列表。
    """
    if origin is None:
        origin = chart['origin']
    timing = chart['timing']
    scroll_base = chart['scroll_base']
    base_subdiv = chart['base_subdiv']

    bars = build_bars(origin, chart['end_time'], timing, base_subdiv, scroll_base)

    # ---- 气球(拨浪鼓)的「提前显示」补偿(判据与理由见 BALLOON_MIN_EFF_BPM 上方) ----
    spans, over, cut_times = balloon_boost(
        chart['balloons'], timing, scroll_base, chart['cut_times'])

    place_commands(bars, cut_times, over, timing, scroll_base)
    place_notes(bars, chart['events'])
    align_last_bar(bars)
    # 格数过多的小节二分成几段(理由与判据见 SPLIT_MAX_CELLS 那一段)。
    # 必须在 place_notes 之后: 要靠 events 才能判断"这一段需要多细的网格"。
    bars = split_fine_bars(bars, base_subdiv)

    # ---- 逐小节排版(格位选择 / 命令分段 / 铺字符) ----
    body, balloon_hits = render_body(bars, chart['rolls'], chart['balloons'],
                                     base_subdiv, chart['barline'],
                                     reset_barline=reset_barline)

    chart.update({'bars': bars, 'body': body, 'balloon_hits': balloon_hits,
                  'balloon_spans': spans, 'balloon_over': over})
    return chart


def chart_summary(chart: dict) -> dict:
    """把一张已排版的 chart 压成「这一张谱」的计数字段(摘要/报数共用)。"""
    return {
        'src': chart['src'],
        'circles': len(chart['circles']), 'rolls': len(chart['rolls']),
        'balloons': len(chart['balloons']),
        'balloons_boosted': len(chart['balloon_spans']),
        'bars': len(chart['bars']),
        'fragments': sum(1 for b in chart['bars'] if b['fragment']),
        'bpm_changes': sum(1 for b in chart['bars']
                           if abs(b['bpm'] - chart['bpm0']) > 1e-6),
        'last_event_ms': chart['last_event_ms'],
        'slider_mult': chart['slider_mult'], 'scroll_base': chart['scroll_base'],
    }


def convert(src: str, dst: str, encoding: str = 'cp932', course_opt=None,
            level_opt=None, barline: str = 'auto', base_subdiv: int = 4,
            quiet: bool = False, wave_ext=None,
            copy_audio: bool = True, red_grid: bool = True,
            offset_shift_ms: float = None,
            demostart_s: float = None,
            title_opt=None, artist_opt=None,
            allow_name_fallback: bool = True,
            trim_audio: bool = True, trim_tail_ms: float = None) -> dict:
    """把一个 .osu taiko 谱面转换成 TJA, 返回本次转换的摘要 dict。

    流程: 解析 .osu -> 定谱面起点(OFFSET) -> 切小节 -> 排版 -> 写 .tja -> 出音源。
    每一步都由模块级的独立函数完成(见模块头「代码地图」), 这里只按序调用并组装
    summary —— 想改某一环, 直接去改那个函数, 不用在这堆参数里翻。

    base_subdiv = **每拍最少格数**。默认 4 —— 这是本家谱面的主流写法
    (实测 8 首本家谱面 1113 个小节里「每拍 4 格」占 692 个)。

    ⚠ 不要随手调大: 它会把**每一个小节**的格数按倍数放大(12 → 每小节 48 格),
      预览里的排版立刻不像本家。这里的默认值曾经是 12, 交付目录被校验脚本
      用 12 覆盖过一次, 结果整批谱面都是「每拍 12 格」。

    offset_shift_ms = **全局 OFFSET 微调**(毫秒, 正数=写出的 OFFSET 变大)。
    `None`(默认) 表示用模块常数 `DEFAULT_OFFSET_SHIFT_MS`(当前 **-30ms**,
    见该常数的说明); 显式传 `0.0` 就是**不加偏移**。
    它**只改头部那一行 `OFFSET:` 的数值**, 不碰任何音符/小节/BPM 的时刻 ——
    等价于手工把 .tja 里的 `OFFSET` 改掉。它平移的是「音符+小节线」相对音频的
    **同一个**位移, 所以不会破坏任何内部相对关系(见模块头部的时间轴换算说明)。

    demostart_s = **预览起点**(秒, 从音频开头算), 写到头部 `DEMOSTART:`。
    `None`(默认) = 照抄 osu 的 `PreviewTime`; osu 里没设(-1)就从 0 开始。
    显式传数值可覆盖。口径与坑见 preview_point()。

    trim_audio = **是否裁掉音频冗余的尾巴**(默认 True, 见 TRIM_TAIL_MS 那一段)。
    只裁尾、绝不碰开头; 裁点 = max(末事件 + 余韵, DEMOSTART + 5s)。
    `trim_tail_ms` 可改余韵长度(默认 None = 模块常数 TRIM_TAIL_MS = 3000ms)。
    能省的不足 TRIM_MIN_GAIN_MS、或读不到音频时长 → 自动跳过, 不影响转换。
    """
    if offset_shift_ms is None:
        offset_shift_ms = DEFAULT_OFFSET_SHIFT_MS

    # ---- ① 解析 + 定谱面起点(OFFSET 的唯一输入) ----
    chart = load_chart(src, encoding, barline, base_subdiv, red_grid,
                       offset_shift_ms, demostart_s, title_opt, artist_opt,
                       allow_name_fallback)
    # ---- ② 切小节 + 排版(单谱模式: 用这张谱自己的起点) ----
    layout_chart(chart)

    # ---- ③ 头部 ----
    # 难度、曲名/曲师(含乱码兜底, 见 looks_mojibake)、预览起点。各自的小函数里
    # 都写明了口径与踩过的坑, 这里只按序调用。
    # 星数 = 这张谱的 osu!taiko SR × 2 四舍五入(算不了 SR 就回退 ★10, 见 taiko_star_rating)。
    # `--level` 显式给了就以它为准。
    sr = taiko_star_rating(src)
    course, level = difficulty_of(course_opt, chart['meta'].get('Version') or '',
                                  level_opt, sr)

    # ---- 输出编码: 编不了就整份换 UTF-8+BOM, 绝不写 "?" ----
    # 规则与理由见 resolve_encoding(); 这里只负责把结果拿去用。
    enc_used, enc_warning = resolve_encoding(encoding, chart['title'], chart['artist'])

    # WAVE: 交付出去的音源一律是 OGG, 这里写的就是那个 .ogg 的真实文件名。
    plan = plan_audio(src, os.path.dirname(os.path.abspath(dst)), wave_ext,
                      chart['meta'], enc_used)
    wave = plan['wave']

    # 写出的 OFFSET = 谱面起点(取负) + 全局微调(默认 -30ms)。
    # ⚠ 这是转换器里**唯一**允许动 OFFSET 的地方; 微调只改这一个数, 不参与任何时刻换算。
    off_written = -chart['origin'] / 1000.0 + offset_shift_ms / 1000.0

    head = render_head(chart['title'], chart['artist'], wave, chart['bpm0'],
                       off_written, chart['demo_ms'], course, level,
                       chart['balloon_hits'], src)
    write_tja(dst, head, chart['body'], enc_used)

    copied, audio_error, audio_skipped, trim = deliver_audio(
        plan, chart['last_event_ms'], chart['demo_ms'],
        copy_audio, trim_audio, trim_tail_ms)

    summary = {
        'dst': dst, 'course': course, 'level': level, 'star_sr': sr,
        'star_src': sr_source_label(src),
        'wave': wave, 'audio_src': plan['src'], 'audio_dst': plan['dst'],
        'audio_action': plan['action'], 'audio_copied': copied,
        'audio_skipped': audio_skipped,
        'audio_error': audio_error, 'audio_note': plan['note'],
        'audio_trim': trim,
        'encoding_used': enc_used, 'encoding_warning': enc_warning,
        'name_notes': chart['name_notes'],
        'origin_ms': chart['origin'], 'offset_written': off_written,
        'offset_shift_ms': offset_shift_ms,
        'demostart_ms': chart['demo_ms'], 'preview_source': chart['preview_source'],
    }
    summary.update(chart_summary(chart))
    if not quiet:
        print_summary(summary)
    return summary


# -------------------------------------------------------------- 多难度: N 个 .osu -> 1 个 .tja

def parse_course(name: str) -> str:
    """把用户写的难度名规范成 TJA 认的五个值之一。

    认大小写、也认中文/和制(`里`/`裏`/`困难`/`鬼`/`inner oni`)—— 命令行里敲
    `--courses 里,Oni` 比记 Edit 顺手。认不出来就原样传下去(让模拟器去挑刺)。
    """
    s = (name or '').strip()
    return COURSE_ALIASES.get(s.casefold(), s or DEFAULT_COURSE)


def _course_arg(name: str) -> str:
    """`--course` 的取值校验: 认别名(同 parse_course), 另加 `auto`。

    和 `parse_course` 的区别是**认不出来要报错** —— 单难度只有一个 COURSE 头,
    写错一个字就会让模拟器读不出这段谱, 不如当场拒绝; `--courses` 是列表,
    保持宽容(原样传下去)。
    """
    s = (name or '').strip()
    if s.casefold() == 'auto':
        return 'auto'
    val = COURSE_ALIASES.get(s.casefold())
    if not val:
        raise argparse.ArgumentTypeError(
            '不认识的难度名 %r —— 可写 Oni/Hard/Normal/Easy/Edit, '
            '或 鬼/困难/普通/简单/里, 或 auto' % name)
    return val


def _star_label(level) -> str:
    """`★14` / `★?` —— 拿不到星数时别写 ★None。只用于文案。"""
    return '★%d' % level if level is not None else '★?'


def order_by_star(paths, srs=None):
    """按星数从高到低排好谱面, 并指出哪些是**真的并列**(需要人来定先后)。

    用户 2026-11-15 定: **难度名由星数决定** —— ★ 高的那张拿更高的难度名, 最高那档是
    Edit。所以只有两种情况才该打扰用户:
      · 两张谱的星数(★N, 也就是模拟器里显示的那个数)**一模一样** —— 屏幕上分不出来;
      · 星数拿不到(既不在 osu!.db 里、又没装 rosu-pp-py) —— 同理分不出来。

    返回 `(ordered, ties)`:
      · `ordered` —— 排好的路径。★ 降序; ★ 相同时 SR 高的在前(只为让结果稳定,
        不代表我们认为谁更难 —— 平手仍然要问); 都取不到就保持调用方给的顺序。
      · `ties`    —— `[(level, [路径...]), ...]`, 只含 ≥2 张的并列组; 空 = 不用问。
    """
    ps = [p for p in (paths or []) if p]
    if not ps:
        return [], []
    if srs is None:
        srs = [taiko_star_rating(p) for p in ps]
    info = []
    for i, p in enumerate(ps):
        sr = srs[i] if i < len(srs) else None
        info.append({
            'path': p,
            'level': None if sr is None else star_from_sr(sr),
            'sr': -1.0 if sr is None else float(sr),
        })
    # ★ 降序; sort 是稳定的 ⇒ 完全并列的保持调用方给的顺序。
    info.sort(key=lambda d: (-1 if d['level'] is None else d['level'], d['sr']),
              reverse=True)
    ties, i = [], 0
    while i < len(info):
        j = i
        while j + 1 < len(info) and info[j + 1]['level'] == info[i]['level']:
            j += 1
        if j > i:
            ties.append((info[i]['level'], [d['path'] for d in info[i:j + 1]]))
        i = j + 1
    return [d['path'] for d in info], ties


def multi_difficulties(n: int, courses_opt=None, levels_opt=None, srs=None):
    """决定 N 张谱各自写成什么难度。返回 `[(course, level), ...]`, 长度 = n。

    难度按**给定顺序**往下排(组合见 DIFF_PROFILES 那段, 由 set_profile 选定):
      难谱版(high): 1 张=鬼 / 2 张=里+鬼 / 3 张=里+鬼+困难
      低难版(low):  1 张=鬼 / 2 张=鬼+困难 / 3 张=+普通 / 4 张=+简单 /
                    5 张=里+鬼+困难+普通+简单
      超过本档上限 -> ValueError

    ⚠ 「顺序」必须由调用方先按星数排好(见 order_by_star): 本函数不重排, 只按位置套名字。
      这样 CLI 的 `--courses 里,Oni`(按你给的顺序对号) 才不会被悄悄改掉。

    星数 `level` 的优先级: `levels_opt`(显式) > `srs[i] × 2` 四舍五入 > DEFAULT_LEVEL。
    `srs` 是各张谱的 osu!taiko SR; 某项为 None(既不在 osu!.db 里、又没装 rosu-pp-py)
    就回退 DEFAULT_LEVEL。

    `courses_opt` / `levels_opt` 是按顺序对齐的覆盖列表(`--courses 里,Oni` / `--levels 10,9`)。
    给得比 n 短时, 缺的那几张沿用默认值 —— 只写想改的那一张就行。
    """
    n = int(n)
    if n < 1:
        n = 1
    if n > MAX_INPUTS:
        raise ValueError(
            '一次最多 %d 张谱(得到 %d 张)。\n'
            '  模拟器只认 %d 个难度(Easy/Normal/Hard/Oni/Edit), 本档(%s)能对应的组合是:\n%s'
            % (MAX_INPUTS, n, TJA_MAX_COURSES, PROFILE_LABEL[PROFILE],
               profile_plan_text()))

    courses = list(MULTI_COURSES[n])
    if courses_opt:
        names = [parse_course(x) for x in courses_opt]
        courses = [names[i] if i < len(names) else c for i, c in enumerate(courses)]

    plan = []
    for i, c in enumerate(courses):
        lv = DEFAULT_LEVEL
        if srs and i < len(srs) and srs[i] is not None:
            lv = star_from_sr(srs[i])
        if levels_opt and i < len(levels_opt):
            lv = int(levels_opt[i])
        plan.append((c, lv))
    return plan


def convert_multi(srcs, dst: str, encoding: str = 'cp932',
                  courses_opt=None, levels_opt=None,
                  barline: str = 'auto', base_subdiv: int = 4,
                  quiet: bool = False, wave_ext=None,
                  copy_audio: bool = True, red_grid: bool = True,
                  offset_shift_ms: float = None, demostart_s: float = None,
                  title_opt=None, artist_opt=None,
                  allow_name_fallback: bool = True,
                  trim_audio: bool = True, trim_tail_ms: float = None,
                  auto_order: bool = False) -> dict:
    """把**同一首歌的多个 .osu** 合成一个多难度 .tja(本家就是这种形态)。

    为什么不是一个文件一段地单独转再拼接: TJA 的 `OFFSET` 与 `WAVE` 是**文件级**的,
    所有难度共用。各 .osu 的谱面起点(第一条红线/首个音符)可能不同, 所以:

      · **全局起点** = 所有谱里最早的那个 `board_origin()` -> 写出的 OFFSET 只此一个;
      · 起点比它晚的那些谱, 开头会多出若干**空小节**(等价于本家谱面开头的等待段),
        音符的绝对时刻一个都不变 —— 这是唯一能让多段共用一条时间轴的做法;
      · 音源取第一张谱所在文件夹的那一份; 其余谱指向别的文件时只记一条提示,
        不会悄悄换音源。

    音源只交付一次、放在 dst 所在目录, `WAVE` 指向它。

    参数含义与 convert() 完全一致(`courses_opt`/`levels_opt` 见 multi_difficulties)。

    `auto_order` = 先按星数把 srcs 从高到低排一遍(见 order_by_star), 让**星数高的那张拿更高
    的难度名**。默认 False = 严格按你给的顺序对号; 命令行在没显式给 `--courses`/`--levels`
    时打开它(GUI 自己排好并问过并列者, 所以走默认)。给了 `--courses`/`--levels` 就别再开 ——
    那两个参数本来就是「按我给的顺序」的覆盖。

    返回的 summary 里多两个键: `multi`(True) 与 `charts`(每张谱各自的计数)。
    """
    srcs = [s for s in (srcs or []) if s]
    if not srcs:
        raise ValueError('没有给出任何 .osu')
    # 先拦张数再解析文件 —— 否则用户白等一圈才被告知“最多 3 张”。
    if len(srcs) > MAX_INPUTS:
        multi_difficulties(len(srcs))            # 直接让它抛那段完整的报错文案
    if offset_shift_ms is None:
        offset_shift_ms = DEFAULT_OFFSET_SHIFT_MS

    # ---- ⓪ 按星数定谁更难(用户 2026-11-15 定): ★ 高的排前面 -> 难度名更高, 最高是 Edit ----
    order_note = None
    if auto_order and len(srcs) > 1:
        srcs, ties = order_by_star(srcs)
        if ties:
            order_note = ('有 %d 组谱面的星数分不出高低(%s), 已按 SR 细排; '
                          '想换先后请用 --courses/--levels' % (
                              len(ties),
                              ', '.join('未知' if lv is None else _star_label(lv)
                                        for lv, _ in ties)))

    # ---- ① 全部解析一遍(先不排版): 每张谱各自的起点/音符/名字 ----
    charts = [load_chart(s, encoding, barline, base_subdiv, red_grid,
                         offset_shift_ms, demostart_s, title_opt, artist_opt,
                         allow_name_fallback) for s in srcs]

    notes = []
    base = charts[0]
    # 起点取最早的一张: 早于它的谱不存在的时刻, 晚于它的谱用空小节补。
    origin = min(c['origin'] for c in charts)

    # 曲名/曲师必须一致 —— 不一致时仍按第一张走, 但要明说(否则用户会以为转换错了)。
    for c in charts[1:]:
        if c['title'] != base['title'] or c['artist'] != base['artist']:
            notes.append('这几张 .osu 的曲名/曲师不一致, 已统一用第一张:「%s - %s」'
                         % (base['artist'], base['title']))
            break

    # ---- ② 统一起点后各自排版 ----
    for c in charts:
        layout_chart(c, origin, reset_barline=True)

    # 每张谱的 osu!taiko SR(算不了就是 None) -> 星数 = SR×2 四舍五入。
    srs = [taiko_star_rating(s) for s in srcs]
    plan_courses = multi_difficulties(len(charts), courses_opt, levels_opt, srs=srs)

    # ---- ③ 音源: 只用第一张谱文件夹里的那一份 ----
    enc_used, enc_warning = resolve_encoding(encoding, base['title'], base['artist'])
    dst_dir = os.path.dirname(os.path.abspath(dst))
    audio = plan_audio(srcs[0], dst_dir, wave_ext, base['meta'], enc_used)
    wave = audio['wave']
    for s, c in zip(srcs[1:], charts[1:]):
        other = plan_audio(s, dst_dir, wave_ext, c['meta'], enc_used)
        if (other['src'] and audio['src']
                and os.path.normcase(os.path.abspath(other['src']))
                != os.path.normcase(os.path.abspath(audio['src']))):
            notes.append('这几张 .osu 指定的音源不是同一个文件, 已采用第一张的「%s」'
                         % os.path.basename(audio['src']))
            break

    off_written = -origin / 1000.0 + offset_shift_ms / 1000.0
    demo_ms = base['demo_ms']

    # ---- ④ 拼正文: 文件头写一次, 每段再各写一份 COURSE 头 + 自己的正文 ----
    lines = render_file_head(base['title'], base['artist'], wave, base['bpm0'],
                             off_written, demo_ms, srcs)
    for i, c in enumerate(charts):
        course, level = plan_courses[i]
        lines.append('')                      # 段与段之间空一行(本家写法)
        lines += render_course_head(course, level, c['balloon_hits'])
        lines += c['body']
    write_tja(dst, lines, [], enc_used)

    # ---- ⑤ 音源交付一次; 裁尾以「所有谱里最后一个音」为准 ----
    last_ms = max(c['last_event_ms'] for c in charts)
    copied, audio_error, audio_skipped, trim = deliver_audio(
        audio, last_ms, demo_ms, copy_audio, trim_audio, trim_tail_ms)

    summary = {
        'multi': True, 'dst': dst, 'wave': wave,
        'audio_src': audio['src'], 'audio_dst': audio['dst'],
        'audio_action': audio['action'], 'audio_copied': copied,
        'audio_skipped': audio_skipped, 'audio_error': audio_error,
        'audio_note': audio['note'], 'audio_trim': trim,
        'encoding_used': enc_used, 'encoding_warning': enc_warning,
        'name_notes': (list(base['name_notes']) + notes
                       + ([order_note] if order_note else [])),
        'origin_ms': origin, 'offset_written': off_written,
        'offset_shift_ms': offset_shift_ms,
        'demostart_ms': demo_ms, 'preview_source': base['preview_source'],
        'waves': wave,
        'charts': [dict(chart_summary(c), course=plan_courses[i][0],
                        level=plan_courses[i][1], star_sr=srs[i],
                        star_src=sr_source_label(srcs[i]),
                        lead_ms=round(c['origin'] - origin, 3),
                        demo_ms=c['demo_ms'],
                        preview_source=c['preview_source'])
                   for i, c in enumerate(charts)],
    }
    # 顶层也放一份合计数, 命令行 / GUI 的通用逻辑(如 audio_report)不必分叉
    summary.update({
        'src': srcs[0],
        'circles': sum(c['circles'] for c in summary['charts']),
        'rolls': sum(c['rolls'] for c in summary['charts']),
        'balloons': sum(c['balloons'] for c in summary['charts']),
        'balloons_boosted': sum(c['balloons_boosted'] for c in summary['charts']),
        'bars': sum(c['bars'] for c in summary['charts']),
        'fragments': sum(c['fragments'] for c in summary['charts']),
        'bpm_changes': sum(c['bpm_changes'] for c in summary['charts']),
        'last_event_ms': last_ms,
        'slider_mult': base['slider_mult'], 'scroll_base': base['scroll_base'],
    })
    if not quiet:
        print_multi_summary(summary)
    return summary


def print_multi_summary(summary: dict) -> None:
    """多难度转换的结果打到 stdout —— 与单难度摘要的写法保持一致, 只是多一段一行的表。"""
    trim = summary.get('audio_trim') or {}
    shift = summary.get('offset_shift_ms') or 0.0
    print('输入: %d 张谱面' % len(summary['charts']))
    for c in summary['charts']:
        sr = c.get('star_sr')
        print('  %-6s ★%-2d  %s%s' % (c['course'], c['level'],
                                     os.path.basename(c['src']),
                                     '' if sr is None else
                                     '   (SR %.4f × 2, 取自 %s)'
                                     % (sr, c.get('star_src') or 'osu!.db')))
    print('输出: %s  [%s]' % (summary['dst'], summary['encoding_used']))
    print('  合计: 咚/咔/大音符 %d 条 | 连打 %d 条 | 气球 %d 个 | 小节 %d 个'
          % (summary['circles'], summary['rolls'], summary['balloons'],
             summary['bars']))
    if summary['balloons_boosted']:
        print('  气球提速: %d 个气球所在段流速慢于 %.0fBPM/1HS, 已在该段强制 #SCROLL 1'
              % (summary['balloons_boosted'], BALLOON_MIN_EFF_BPM))
    print('  OFFSET: %.3f  (最早起点 %d ms%s)'
          % (summary['offset_written'], summary['origin_ms'],
             '' if not shift else ' + 全局微调 %+g ms' % shift))
    lead = [c for c in summary['charts'] if c['lead_ms'] > 0.5]
    if lead:
        print('  起点对齐: %s' % ', '.join(
            '%s 晚 %+.0f ms(开头补空小节)' % (c['course'], c['lead_ms']) for c in lead))
    print('  DEMOSTART: %.3f  (%s)'
          % (summary['demostart_ms'] / 1000.0,
             {'osu': '照抄第一张的 PreviewTime',
              'override': '按 --demostart 指定',
              'auto': 'osu 没设预览起点, 从音频开头'}[summary['preview_source']]))
    print('  ' + audio_report(summary).replace('\n', '\n  '))
    for n in summary.get('name_notes') or []:
        print('  注意: %s' % n)
    if trim.get('action') == 'trim' and trim.get('note'):
        print('  %s' % trim['note'])


# -------------------------------------------------------------- 批量: 多首歌一起转
# 用户会把 Songs 里挑中的一大把谱面一次丢进来。这时程序要自己分辨:
#   **同一首歌的几张谱 -> 合成一个多难度 .tja;  不同的歌 -> 各转一个。**
#
# 判据只有一条: **是不是同一个文件夹**。
#   osu 里一个 mapset 就是一个文件夹, 各难度共用同一份音源(这是官方结构);
#   不同的歌必然在不同文件夹。
#   比「曲名+曲师相同」可靠 —— 原曲与 remix、同名不同作品都很常见, 曲名可能一字不差,
#   但一定在不同文件夹; 反过来同一文件夹里绝不会放两首歌。
def group_by_song(paths, allow_name_fallback: bool = True):
    """把选中的 .osu 按**歌曲**分组。返回 `[dict(key, folder, title, artist, meta, paths)]`。

    顺序 = 各组第一张谱在 `paths` 里出现的顺序(所以用户排好的组顺序会被保留)。
    同组内的顺序 = `paths` 里的相对顺序, 也就是「谁当里谱、谁当 Oni」的依据。
    """
    groups = []
    index = {}
    for p in paths or []:
        if not p:
            continue
        folder = os.path.dirname(os.path.abspath(p))
        key = os.path.normcase(folder)
        g = index.get(key)
        if g is None:
            meta = read_meta(p)
            title, _ = pick_display_name(meta, 'Title', 'TitleUnicode', None,
                                         allow_name_fallback)
            artist, _ = pick_display_name(meta, 'Artist', 'ArtistUnicode', None,
                                          allow_name_fallback)
            g = {'key': key, 'folder': folder, 'title': title or '',
                 'artist': artist or '', 'meta': meta, 'paths': []}
            index[key] = g
            groups.append(g)
        g['paths'].append(p)
    return groups


def _too_many_groups_text(over) -> str:
    """`over` = [(歌名, 张数), ...] -> 「这首歌唱不下这么多难度」的说明文案。"""
    names = '\n'.join('  · %s（%d 张）' % (t or '(无标题)', n) for t, n in over)
    return ('下面这些歌的谱面超过上限（每首最多 %d 张）：\n%s\n\n'
            '一个 .tja 最多只装 %d 个难度（模拟器只认 Easy/Normal/Hard/Oni/Edit 五档），'
            '本档（%s）能对应的组合是：\n%s\n\n'
            '请每首歌最多只选 %d 张。'
            % (MAX_INPUTS, names, TJA_MAX_COURSES, PROFILE_LABEL[PROFILE],
               profile_plan_text(), MAX_INPUTS))


def batch_targets(groups, out_root: str, song_folder: bool = True):
    """给每首歌算落盘位置, 并保证**本次批量内部**的文件夹名不撞车(撞了加 ` (2)`)。

    TJA 按「一个文件夹 = 一首歌」收录, 而文件夹名取曲名 —— 两首不同的歌叫同一个名字
    (同名曲、或曲名只差标点被 safe_name 归一)时会落到同一个文件夹, 于是后一首的 .tja
    覆盖前一首。所以这里排一次序, 第二个起加序号后缀。

    ⚠ 只处理「本次批量内部」的冲突。磁盘上**已经存在**的同名文件夹照旧复用(和单曲一致),
      要不要覆盖由调用方先问用户。
    """
    used = set()
    out = []
    for g in groups:
        base = safe_name(g['title'], 'Untitled')
        name, k = base, 2
        while name.casefold() in used:
            name = '%s (%d)' % (base, k)
            k += 1
        used.add(name.casefold())
        song_dir = os.path.join(out_root, name) if song_folder else out_root
        out.append({'group': g, 'name': name, 'song_dir': song_dir,
                    'dst': os.path.join(song_dir, name + '.tja')})
    return out


def batch_audio_plan(target, wave_ext=None):
    """预测这一组会写出哪个音源文件（只算, 不动文件）。

    只给「要覆盖吗」的提示和结果汇报用; 真正落盘时 convert_multi 会自己再算一遍,
    所以这里用的编码/取名逻辑必须和它一模一样(同一个 resolve_encoding + plan_audio)。
    """
    g = target['group']
    enc, _ = resolve_encoding('cp932', g['title'], g['artist'])
    return plan_audio(g['paths'][0], target['song_dir'], wave_ext, g['meta'], enc)


def convert_batch(srcs, out_root: str, encoding: str = 'cp932',
                  courses_opt=None, levels_opt=None,
                  barline: str = 'auto', base_subdiv: int = 4,
                  quiet: bool = False, wave_ext=None,
                  copy_audio: bool = True, red_grid: bool = True,
                  offset_shift_ms: float = None, demostart_s: float = None,
                  artist_opt=None, allow_name_fallback: bool = True,
                  trim_audio: bool = True, trim_tail_ms: float = None,
                  song_folder: bool = True, auto_order: bool = False) -> dict:
    """把**一堆** .osu 按歌分组转出去: 同一首合成一个多难度 .tja, 不同的歌各转一个。

    输出结构(默认):
        <out_root>/<曲名1>/<曲名1>.tja + 音源
        <out_root>/<曲名2>/<曲名2>.tja + 音源
    每首歌内部对 `convert_multi()`, 所以「什么张数配什么难度名」跟单首歌完全一致
    与星数规则和单首歌完全一致。

    ⚠ 多首歌时 **强制每首歌一个文件夹**(忽略 song_folder=False): 音源文件名跟着源文件
      走(很多谱都叫 `audio.ogg`), 平铺到一个目录里必然互相覆盖, 结果就是 A 歌的 .tja
      指向 B 歌的音源。这种「看起来正常、听起来全错」的坑不值得留口子。

    ⚠ `title_opt` 故意**没有**这个参数: 多首歌不可能共用一个曲名。

    `auto_order` 见 convert_multi: 打开后每首歌内部先按星数把难度排好(★ 高的难度名更高)。

    单组失败(文件坏了)不会中断整批 —— 记进 `items[i]['error']`, 其余的照转, 最后汇总。
    返回 {'batch','out_root','count_files','count_groups','items','notes','ok'}。
    """
    srcs = [s for s in (srcs or []) if s]
    if not srcs:
        raise ValueError('没有给出任何 .osu')
    out_root = os.path.abspath(out_root)
    notes = []
    if offset_shift_ms is None:
        offset_shift_ms = DEFAULT_OFFSET_SHIFT_MS

    groups = group_by_song(srcs, allow_name_fallback)
    if auto_order:
        # ★ 必须先在这里排: batch_targets 拿 g['title'] 当文件夹名, 而 convert_multi
        #   是排完星数序之后才写 TITLE —— 两处顺序不一致就成了「文件夹 A / TITLE B」。
        #   排完还把 auto_order 关掉往下传, 免得同一首歌白算两遍星数。
        for g in groups:
            g['paths'], _ties = order_by_star(g['paths'])
        groups = group_by_song([p for g in groups for p in g['paths']],
                               allow_name_fallback)
        auto_order = False
    over = [(g['title'], len(g['paths'])) for g in groups
            if len(g['paths']) > MAX_INPUTS]
    if over:
        raise ValueError(_too_many_groups_text(over))

    if not song_folder:
        song_folder = True
        notes.append('多首歌会给每首歌各建一个文件夹(音源文件名会撞, 平铺会互相覆盖)')

    targets = batch_targets(groups, out_root, song_folder)
    items = []
    for t in targets:
        if not quiet:
            print('→ %s  (%d 张谱面)' % (t['name'], len(t['group']['paths'])))
        try:
            os.makedirs(t['song_dir'], exist_ok=True)
        except OSError as e:
            items.append({'target': t, 'summary': None,
                          'error': '无法创建文件夹: %s' % e})
            continue
        try:
            one = convert_multi(
                t['group']['paths'], t['dst'], encoding, courses_opt, levels_opt,
                barline, base_subdiv, True, wave_ext,
                copy_audio=copy_audio, red_grid=red_grid,
                offset_shift_ms=offset_shift_ms, demostart_s=demostart_s,
                title_opt=None, artist_opt=artist_opt,
                allow_name_fallback=allow_name_fallback,
                trim_audio=trim_audio, trim_tail_ms=trim_tail_ms,
                auto_order=auto_order)
        except Exception as e:              # 单首失败不拖垮整批
            items.append({'target': t, 'summary': None,
                          'error': '%s: %s' % (type(e).__name__, e)})
            continue
        items.append({'target': t, 'summary': one, 'error': None})

    ok = all(not it['error'] and not (it['summary'] or {}).get('audio_error')
             for it in items)
    summary = {'batch': True, 'out_root': out_root, 'song_folder': song_folder,
               'count_files': len(srcs), 'count_groups': len(groups),
               'items': items, 'notes': notes, 'ok': ok}
    if not quiet:
        print_batch_summary(summary)
    return summary


def _batch_audio_note(s: dict) -> str:
    """一首歌的音源处理结果, 压成半句话(给批量结果用, 别写成 audio_report 那么长)。"""
    if not s:
        return ''
    txt = s.get('wave') or ''
    if s.get('audio_error'):
        return '%s（没转成: %s）' % (txt, s['audio_error'])
    if s.get('audio_skipped'):
        return '%s（未输出）' % txt
    if s.get('audio_action') == 'missing':
        # 源谱面文件夹里本来就没有音频文件: WAVE 写的是个占位名, 别让用户以为已经出好了。
        return '%s（⚠ 没找到音源，谱面能打但没音乐）' % txt
    trim = s.get('audio_trim') or {}
    if trim.get('action') == 'trim':
        txt += '（裁尾省 %.1f s）' % (trim['gain_ms'] / 1000.0)
    return txt


def batch_done_text(summary: dict) -> str:
    """批量结果的人话版 —— 命令行与弹窗共用同一份文字。"""
    lines = ['转换完成：%d 首歌 / 共 %d 张谱面\n'
             % (summary['count_groups'], summary['count_files'])]
    failed = 0
    for i, it in enumerate(summary['items'], 1):
        t = it['target']
        if it['error']:
            failed += 1
            lines.append('%d) ✖ %s\n   失败：%s' % (i, t['name'], it['error']))
            continue
        s = it['summary']
        courses = ' / '.join('%s ★%d' % (c['course'], c['level'])
                             for c in s['charts'])
        lines.append('%d) %s\n   %s\n   %s\n   音源：%s'
                     % (i, t['name'], courses, s['dst'], _batch_audio_note(s)))
    if failed:
        lines.append('\n有 %d 首歌没转成，其余已正常输出。' % failed)
    for n in summary.get('notes') or []:
        lines.append('注意：%s' % n)
    return '\n'.join(lines)


def print_batch_summary(summary: dict) -> None:
    """批量结果打到 stdout（与 GUI 弹窗同一份内容, 只是前缀不同）。"""
    print('批量: %d 首歌 / 共 %d 张谱面'
          % (summary['count_groups'], summary['count_files']))
    for i, it in enumerate(summary['items'], 1):
        t = it['target']
        if it['error']:
            print('  %2d) ✖ %s  —— %s' % (i, t['name'], it['error']))
            continue
        s = it['summary']
        print('  %2d) %s  [%d 难度]  %s'
              % (i, t['name'], len(s['charts']),
                 ' / '.join('%s ★%d' % (c['course'], c['level'])
                            for c in s['charts'])))
        print('      %s' % s['dst'])
        note = _batch_audio_note(s)
        if note:
            print('      音源 %s' % note)
    for n in summary.get('notes') or []:
        print('  注意: %s' % n)
    print('  %s' % ('全部成功' if summary['ok'] else '有失败项, 见上面 ✖'))


def audio_report(summary: dict) -> str:
    """把音源的处理结果写成一句人话 —— 命令行和弹窗共用, 保证两处说法一致。

    裁了尾巴就在末尾补一句「裁到多少、省了多少」, 不裁/跳过则一个字都不加
    (跳过是常态, 不该在正常结果里多一行噪声)。
    """
    action = summary['audio_action']
    trim = summary.get('audio_trim') or {}
    trimming = trim.get('action') == 'trim'
    if action in ('copy', 'transcode'):
        verb = '转码' if action == 'transcode' else '拷贝'
        if summary['audio_copied']:
            if trimming:
                # 裁尾一定走重新编码, 所以哪怕源本来是 ogg(plan 里算 'copy'), 也不能说「已拷贝」。
                # 源文件名和产出同名时(常见: 都是 audio.ogg)不必再写一遍来源。
                srcnm = os.path.basename(summary['audio_src'] or '')
                head = summary['wave']
                head += ('（由 %s 转成 OGG ' % srcnm
                         if srcnm and srcnm.lower() != summary['wave'].lower()
                         else '（重新编码')
                txt = '%s并裁尾: 裁到 %.3f s, 省 %.1f s）' % (
                    head, trim['cut_ms'] / 1000.0, trim['gain_ms'] / 1000.0)
            elif action == 'transcode':
                txt = '%s（由 %s 转成 OGG）' % (
                    summary['wave'], os.path.basename(summary['audio_src'] or ''))
            else:
                txt = '%s -> 已拷到输出文件夹' % summary['wave']
        elif summary.get('audio_skipped'):
            txt = '%s -> 没有%s（按 --no-copy-audio）' % (summary['wave'], verb)
        else:
            txt = '%s -> 没%s成（%s）' % (summary['wave'], verb,
                                        summary['audio_error'] or '原因不明')
    elif action == 'same':
        txt = '%s -> 谱面和音源本来就在同一个文件夹, 无需处理' % summary['wave']
    else:
        return '没找到音源（%s）; WAVE 里写的仍是 %s' % (summary['audio_note'], summary['wave'])
    return txt


# -------------------------------------------------------------- 图形界面

def open_folder(path: str) -> None:
    """在系统的文件管理器里打开一个文件夹; 打不开只提示, 不影响转换结果本身。"""
    try:
        if hasattr(os, 'startfile'):            # Windows
            os.startfile(path)
        elif sys.platform == 'darwin':          # macOS
            subprocess.Popen(['open', path])
        else:                                   # Linux
            subprocess.Popen(['xdg-open', path])
    except Exception as e:
        print('（没能自动打开文件夹: %s）' % e, file=sys.stderr)


# -------------------------------------------------------------- 记住上次用过的输出文件夹
# 给图形界面用: 双击进来的用户, 转出来的 .tja 总是堆在同一个文件夹里, 不想每次重选。
#   * 只记**输出**文件夹。**输入**文件夹不记 —— 但要转的谱面天天在 osu! 的 Songs 里,
#     所以第 1 步的选文件框直接停到 Songs(见下面的 DEFAULT_INPUT_DIRS)。
#   * 配置文件坏了 / 写不进去(只读目录、权限) 一律当没有, **绝不让它影响转换本身**。
CONFIG_PATH = os.path.join(
    os.environ.get('APPDATA') or os.path.expanduser('~'),
    'osu2tja2', 'config.json')


# -------------------------------------------------------------- 第 1 步选文件框的落脚点
# 用户日常从 osu! 的 Songs 目录里挑谱面, 每次从「文档」或上次的随便某个位置
# 一路点过去很烦。这里给一列候选目录, **取第一个真实存在的**:
#   1. 作者本机的 osu! 安装位置
#   2. osu! 的默认安装位置 %LOCALAPPDATA%\osu!\Songs
# 一个都不存在 → 返回 ''(就不传 initialdir, 让 tkinter 用它自己的默认位置, 不报错)。
# ⚠ 只决定**弹窗停在哪**, 不影响能不能转换 —— 用户随时可以导航到别处。
DEFAULT_INPUT_DIRS = (
    r'D:\Download App\osu!\Songs',
    os.path.join(os.environ.get('LOCALAPPDATA') or
                 os.path.join(os.path.expanduser('~'), 'AppData', 'Local'),
                 'osu!', 'Songs'),
)


def default_input_dir() -> str:
    """选文件框的初始目录: `DEFAULT_INPUT_DIRS` 里第一个存在的; 都没有则 ''。"""
    for d in DEFAULT_INPUT_DIRS:
        try:
            if d and os.path.isdir(d):
                return d
        except OSError:
            continue
    return ''


def load_config() -> dict:
    """读小配置。任何异常都当成「没配置过」。"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(**items) -> bool:
    """合并写入小配置; 返回是否写成功。写不进去不抛异常。"""
    d = load_config()
    d.update(items)
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2, sort_keys=True)
        return True
    except OSError:
        return False


def remembered_out_dir(fallback: str) -> str:
    """选输出文件夹时, 弹窗的初值: 上次用过的那个; 它被删/移走了就退回 fallback。

    ⚠ 只影响弹窗**停在哪**。用户随时可以导航到别处, 选完立刻覆盖记忆 ——
      所以即使记错了也会自愈, 不需要额外的「清除」步骤(想清就删配置文件)。
    """
    last = load_config().get('out_dir') or ''
    if last and os.path.isdir(last):
        return last
    return fallback


def gui_flow(ask_files, ask_dir, ask_yes, error, output_hint=None,
             base_subdiv: int = 4, red_grid: bool = True,
             offset_shift_ms: float = None, info=None,
             open_output_dir: bool = False, song_folder: bool = True,
             allow_name_fallback: bool = True,
             trim_audio: bool = True, trim_tail_ms: float = None,
             ask_order=None) -> int:
    """图形界面的流程主体。

    所有交互都通过外部注入的回调完成, 这样这段逻辑可以脱离 tkinter 单独测试:
        ask_files()          -> 选输入 .osu, 返回路径**列表**(可以多选), 取消返回 []
        ask_dir(initialdir)  -> 选输出文件夹, 取消返回 ''
        ask_yes(title, text) -> 是/否
        error(title, text)   -> 报错
        info(title, text)    -> 只通知、不需回答(缺省退回 print)
        ask_order(paths)     -> **只在星数打平时**才调: 给用户定这几张谁排前面, 返回新顺序;
                                取消返回 [];  缺省(None) = 不问(并列就按 SR 细排)
        output_hint          -> 命令行已用 -o 指定过输出时, 就不再问文件夹
        open_output_dir      -> 转换完是否顺手打开输出文件夹。默认 False:
                                转完只弹一条结果提示, 不问、不打开。
        song_folder          -> 在选定文件夹下再建一层「曲名」文件夹放 .tja + .ogg。
                                默认 True; 传 False 就是旧行为(直接放进选定文件夹)。
        allow_name_fallback  -> 原名(…Unicode)疑似乱码时是否退到罗马音那栏。默认 True。
        trim_audio           -> 是否裁掉音频冗余的尾巴(默认 True, 见 TRIM_TAIL_MS)。
        trim_tail_ms         -> 余韵长度; None = 模块常数(3s)。

    按选中内容自动分三档:
      · 1 个 .osu                       -> 单难度(Oni)
      · 同一首歌的 2~N 个                -> 合成一个多难度 .tja
      · 跨了多首歌                       -> **批量**: 每首歌各转一个 .tja, 各占一个文件夹
    每首歌最多 MAX_INPUTS 张(难谱版 3 / 低难版 5), 超了在排难度之前就报错。

    ★ 多难度时**哪个谱当哪个难度由星数决定**(用户 2026-11-15 定, 见 order_by_star):
      ★ 高的那张拿更高的难度名。星数不同就直接排好、不再打扰用户;
      只有星数(★N)**完全一样**、屏幕上分不出谁更难时, 才调 ask_order 让用户定先后。
    星数不固定: 每段 LEVEL = 该谱的 osu!taiko SR × 2 四舍五入, 见 convert_multi()。
    """
    srcs = [s for s in (ask_files() or []) if s]
    if not srcs:
        print('已取消。')
        return 0
    for s in srcs:
        if not os.path.isfile(s):
            error('文件不存在', '找不到这个文件：\n%s' % s)
            return 1
        if not s.lower().endswith('.osu'):
            error('文件类型不对', '请选择 .osu 谱面文件：\n%s' % os.path.basename(s))
            return 1
    # 先按歌分组: 同一个文件夹 = 同一首歌(见 group_by_song)。
    # ⚠ 张数上限是**每首歌**的, 不是总数 —— 一次丢二十首歌进来是正常用法,
    #   只有「某一首歌自己有 4 张以上谱面」才装不下。
    groups = group_by_song(srcs, allow_name_fallback)
    over = [(g['title'], len(g['paths'])) for g in groups
            if len(g['paths']) > MAX_INPUTS]
    if over:
        error('某首歌的谱面太多了', _too_many_groups_text(over))
        return 1

    multi = len(srcs) > 1
    if multi:
        # ★★ 难度名由**星数**决定(用户 2026-11-15 定): 每组先按 ★ 从高到低排, 星数最高的
        #    那张当 Edit(见 order_by_star / MULTI_COURSES)。只有**星数一模一样**、屏幕上
        #    根本分不出谁更难的时候, 才把这几张丢给用户定先后。
        ask_paths = []
        for g in groups:
            g['paths'], ties = order_by_star(g['paths'])
            for _lv, sub in ties:
                ask_paths += sub
        if ask_paths and ask_order is not None:
            chosen = list(ask_order(ask_paths) or [])
            if not chosen:
                print('已取消。')
                return 0
            # 用户只可能在「同星数」的那几张之间换位置: 把新顺序填回原槽位,
            # 组与组的先后、每组的张数都不受影响。
            key = os.path.normcase
            got = {key(os.path.abspath(p)) for p in chosen}
            for g in groups:
                slots = [i for i, p in enumerate(g['paths'])
                         if key(os.path.abspath(p)) in got]
                if len(slots) < 2:
                    continue
                mine = [g['paths'][i] for i in slots]
                mine_keys = {key(os.path.abspath(p)) for p in mine}
                fresh = [p for p in chosen
                         if key(os.path.abspath(p)) in mine_keys]
                if len(fresh) != len(slots):        # 回调没原样返回 -> 保持原顺序
                    continue
                for i, p in zip(slots, fresh):
                    g['paths'][i] = p
        # ⚠ 这段必须在 if 外面: 星数全不同(不询问)时同样要把排好的顺序写回 srcs。
        srcs = [p for g in groups for p in g['paths']]
        groups = group_by_song(srcs, allow_name_fallback)   # 让 title/meta 跟着新第一张
    batch = len(groups) > 1
    src = srcs[0]

    dst = None
    if output_hint:
        hint = output_hint.rstrip('/\\')
        if _is_output_file(hint):
            # -o 给了具体文件名: 按名字写, 目录取它所在的那一层
            dst_dir = os.path.dirname(os.path.abspath(hint))
            if hint.lower().endswith('.tja'):
                dst = hint
        else:
            dst_dir = output_hint
    else:
        dst_dir = ask_dir(os.path.dirname(os.path.abspath(src)))
        if not dst_dir:
            print('已取消。')
            return 0

    if not dst_dir:
        dst_dir = os.path.dirname(os.path.abspath(src))
    if not os.path.isdir(dst_dir):
        try:
            os.makedirs(dst_dir, exist_ok=True)
        except OSError as e:
            error('无法创建输出文件夹', '%s\n%s' % (dst_dir, e))
            return 1

    # ------------------------------------------------ 多首歌: 各自转一个, 各自一个文件夹
    if batch:
        targets = batch_targets(groups, dst_dir, song_folder=True)
        # 会被覆盖的文件先一次列全、问一次(批量里逐个弹窗没法用)。
        overwrite = []
        for t in targets:
            if os.path.exists(t['dst']):
                overwrite.append(t['dst'])
            plan = batch_audio_plan(t)
            if (plan['action'] in ('copy', 'transcode') and plan['dst']
                    and os.path.exists(plan['dst'])):
                overwrite.append(plan['dst'])
        if overwrite and not ask_yes(
                '同名文件已存在',
                '下面这些文件会被覆盖：\n  %s\n\n要继续吗？'
                % '\n  '.join(overwrite)):
            print('已取消（未覆盖）')
            return 0
        try:
            summary = convert_batch(
                srcs, dst_dir, encoding='cp932', barline='auto',
                base_subdiv=base_subdiv, red_grid=red_grid,
                offset_shift_ms=offset_shift_ms,
                allow_name_fallback=allow_name_fallback,
                trim_audio=trim_audio, trim_tail_ms=trim_tail_ms)
        except Exception as e:
            error('转换失败', '%s: %s' % (type(e).__name__, e))
            return 1
        text = batch_done_text(summary)
        if info is not None:
            info('批量转换完成' if summary['ok'] else '批量转换完成（有失败）', text)
        else:
            print(text)
        if open_output_dir:
            open_folder(dst_dir)
        return 0 if summary['ok'] else 1

    if dst is None:
        if multi:
            # 一个文件装了多张谱 -> 用曲名命名, 不再沿用某一张谱的文件名
            _m0 = read_meta(src)
            _t0, _ = pick_display_name(_m0, 'Title', 'TitleUnicode', None,
                                       allow_name_fallback)
            dst = os.path.join(dst_dir, safe_name(_t0) + '.tja')
        else:
            dst = os.path.join(dst_dir,
                               os.path.splitext(os.path.basename(src))[0] + '.tja')

    # 再套一层「曲名」文件夹: 模拟器是按「一个文件夹一首歌」收录的,
    # .tja 和 .ogg 都放进这一层。
    dst, song_dir = output_paths(src, dst, song_folder=song_folder,
                                 allow_name_fallback=allow_name_fallback)
    if not os.path.isdir(song_dir):
        try:
            os.makedirs(song_dir, exist_ok=True)
        except OSError as e:
            error('无法创建输出文件夹', '%s\n%s' % (song_dir, e))
            return 1

    # 会被写进去的东西: 谱面 .tja + 转好的 .ogg。先把会被覆盖的列出来问一次。
    overwrite = []
    if os.path.exists(dst):
        overwrite.append(os.path.basename(dst))
    # ⚠ 这里必须用**和 convert 同一个编码**去算音频文件名, 否则覆盖提示查的是一个
    #   实际不会生成的路径(标题编不进 cp932 时, convert 会降级成 UTF-8+BOM 再取名)。
    _meta = read_meta(src)
    _t, _ = pick_display_name(_meta, 'Title', 'TitleUnicode', None, allow_name_fallback)
    _a, _ = pick_display_name(_meta, 'Artist', 'ArtistUnicode', None, allow_name_fallback)
    _enc, _ = resolve_encoding('cp932', _t, _a)
    plan = plan_audio(src, song_dir, encoding=_enc)
    if plan['action'] in ('copy', 'transcode') and os.path.exists(plan['dst']):
        overwrite.append(os.path.basename(plan['dst']))
    if overwrite and not ask_yes(
            '同名文件已存在',
            '这个文件夹里已经有同名文件：\n  %s\n\n要覆盖吗？' % '\n  '.join(overwrite)):
        print('已取消（未覆盖）: %s' % dst)
        return 0

    try:
        if multi:
            summary = convert_multi(srcs, dst, encoding='cp932', barline='auto',
                                    base_subdiv=base_subdiv, quiet=False,
                                    red_grid=red_grid, offset_shift_ms=offset_shift_ms,
                                    allow_name_fallback=allow_name_fallback,
                                    trim_audio=trim_audio, trim_tail_ms=trim_tail_ms)
        else:
            summary = convert(src, dst, encoding='cp932', course_opt=None,
                              level_opt=None, barline='auto',
                              base_subdiv=base_subdiv, quiet=False,
                              red_grid=red_grid, offset_shift_ms=offset_shift_ms,
                              allow_name_fallback=allow_name_fallback,
                              trim_audio=trim_audio, trim_tail_ms=trim_tail_ms)
    except Exception as e:
        error('转换失败', '%s: %s' % (type(e).__name__, e))
        return 1

    # 转完只报结果, 不问「要不要打开文件夹」; 想打开得显式要求(--open-out-dir)。
    if multi:
        done_text = (
            '转换完成（%d 个难度）\n\n'
            '输出谱面：\n%s\n'
            '难度：%s\n'
            '输出音源：%s\n\n'
            '合计：音符 %d 条 ｜ 连打 %d 条 ｜ 气球 %d 个\n'
            '小节 %d 个（其中 %d 个是切分出来的片段）'
            % (len(summary['charts']), summary['dst'],
               ' ｜ '.join('%s ★%d' % (c['course'], c['level'])
                          for c in summary['charts']),
               audio_report(summary), summary['circles'], summary['rolls'],
               summary['balloons'], summary['bars'], summary['fragments']))
    else:
        done_text = (
            '转换完成\n\n'
            '输出谱面：\n%s\n'
            '输出音源：%s\n\n'
            '音符 %d 条 ｜ 连打 %d 条 ｜ 气球 %d 个\n'
            '小节 %d 个（其中 %d 个是切分出来的片段）'
            % (summary['dst'], audio_report(summary), summary['circles'], summary['rolls'],
               summary['balloons'], summary['bars'], summary['fragments']))
    extra = list(summary.get('name_notes') or [])
    if summary.get('encoding_warning'):
        extra.append(summary['encoding_warning'])
    if extra:
        done_text += '\n\n注意：\n' + '\n'.join('· ' + x for x in extra)
    if info is not None:
        info('转换完成', done_text)
    else:
        print(done_text)
    if summary.get('encoding_warning'):
        print('⚠ %s' % summary['encoding_warning'], file=sys.stderr)
    if open_output_dir:
        open_folder(song_dir)
    return 0


def ask_order_dialog(root, paths):
    """**只有星数打平时**才弹的小窗口: 让用户定这几张谁排前面(上移/下移)。

    难度名现在由星数自动分配(见 order_by_star): ★ 高的那张拿更高的难度名, 最高那档是
    Edit。所以只有「星数一模一样、屏幕上分不出谁更难」的几张才需要人来定先后 ——
    本窗口只显示这几张, 而且**只能在同一首歌、同一星数内部**上下移:
    不同歌之间没有难度关系, 不同星数的先后已经由星数定死了。
    取消返回 [], 由 gui_flow 当成「已取消」处理。

    跨了多首歌时每组一个 `── 曲名 · ★N ──` 分隔行; 单首歌时直接平铺(列表项是 `1. 文件名`)。
    返回值仍是扁平的文件列表, 同组的项保持相邻。

    窗口**不能**挂在隐藏的 root 上当 transient 子窗口(会跟着不可见), 详见下面的 ⚠。

    `root` 由调用方给(必须是已存在的 Tk, 通常是那个 withdraw 的宿主窗口);
    拿不到 tkinter 时直接按原顺序返回, 不阻断转换。
    """
    try:
        import tkinter as tk
    except Exception as e:                        # 无 tkinter 的 Python: 跳过排序
        print('⚠ 没有 tkinter, 跳过难度排序 (%s)' % e, file=sys.stderr)
        return list(paths)
    if len(paths) < 2:
        return list(paths)
    win = tk.Toplevel(root)
    win.title('第 2 步 — 定星数相同的谱面先后')
    win.resizable(False, False)
    # 分组 = (同一首歌, 同一星数)。跨歌没有难度关系、不同星数的先后已由星数定死,
    # 所以两种情况下都不许上下移(见下面 move 里的 keys 判断)。
    lv_of = {}
    for p in paths:
        sr = taiko_star_rating(p)
        lv_of[p] = None if sr is None else star_from_sr(sr)
    try:
        song_titles = {os.path.normcase(g['folder']): (g['title'] or '(无标题)')
                       for g in group_by_song(paths)}
    except Exception:
        song_titles = {}
    glist, index = [], {}
    for p in paths:
        fk = os.path.normcase(os.path.dirname(os.path.abspath(p)))
        k = (fk, lv_of[p])
        g = index.get(k)
        if g is None:
            g = {'key': k, 'level': lv_of[p], 'paths': []}
            index[k] = g
            glist.append(g)
        g['paths'].append(p)
    multi_group = len(glist) > 1
    multi_song = len({k[0] for k in index}) > 1
    for g in glist:
        # 单首歌时星数就够区分了; 多首歌时得带上曲名, 否则两条 ── ★14 ── 分不清。
        g['title'] = ('%s · %s' % (song_titles.get(g['key'][0], ''), _star_label(g['level']))
                      if multi_song else _star_label(g['level']))

    if multi_group:
        head = ('只有星数相同的谱面需要你定先后（其余几张已按星数排好）：\n'
                '越靠上，拿到的难度名越高（最高是 Edit）。\n\n')
    else:
        head = ('这几张的星数完全一样（%s），模拟器里分不出谁更难 ——\n'
                '请定一下先后：越靠上，拿到的难度名越高（最高是 Edit）。\n\n'
                % _star_label(glist[0]['level']))
    tk.Label(win, justify='left', text=(
        head + '用「上移 / 下移」调整，满意后点「确定」（回车 = 确定，Esc = 取消）。')
    ).pack(padx=14, pady=10)

    # rows 是这个列表的真实内容: ('head', 组标题) 是分隔行、不可移动; ('file', 路径) 是谱面行。
    # 单组时全部是谱面行, 列表项仍是「1. 文件名」。
    rows = []
    if multi_group:
        for g in glist:
            rows.append(('head', g['title']))
            rows += [('file', p) for p in g['paths']]
    else:
        rows = [('file', p) for p in glist[0]['paths']]
    # 每行属于哪一组(分隔行算它自己): 上下移只允许发生在同组内部。
    keys, cur = [], None
    for kind, val in rows:
        if kind == 'head':
            cur = ('head', len(keys))
        keys.append(cur if cur is not None else ('one', 0))

    box = tk.Listbox(win, width=76, height=min(14, max(3, len(rows))),
                     activestyle='dotbox', exportselection=False)
    box.pack(padx=14, fill='both', expand=True)
    state = {'ok': False, 'shown': False}

    def redraw(sel=0):
        box.delete(0, 'end')
        n = 0
        for kind, val in rows:
            if kind == 'head':
                box.insert('end', '── %s ──' % val)
                n = 0                              # 组内重新编号
            else:
                n += 1
                box.insert('end', '%d. %s' % (n, os.path.basename(val)))
        if rows:
            box.selection_set(min(sel, len(rows) - 1))

    def move(delta):
        sel = box.curselection()
        if not sel:
            return
        i = sel[0]
        if rows[i][0] != 'file':                   # 分隔行不参与移动
            return
        j = i + delta
        if 0 <= j < len(rows) and rows[j][0] == 'file' and keys[j] == keys[i]:
            rows[i], rows[j] = rows[j], rows[i]
            keys[i], keys[j] = keys[j], keys[i]
            redraw(j)

    def on_select(_ev=None):
        """点到分隔行时自动跳到该组第一张谱 —— 否则按上移/下移会「没反应」。"""
        sel = box.curselection()
        if sel and rows[sel[0]][0] == 'head' and sel[0] + 1 < len(rows):
            box.selection_clear(0, 'end')
            box.selection_set(sel[0] + 1)

    def ok():
        state['ok'] = True
        win.destroy()

    def cancel():
        win.destroy()

    btns = tk.Frame(win)
    btns.pack(pady=10)
    for text, cmd in (('上移', lambda: move(-1)), ('下移', lambda: move(1)),
                      ('确定', ok), ('取消', cancel)):
        tk.Button(btns, text=text, width=8, command=cmd).pack(side='left', padx=4)
    win.protocol('WM_DELETE_WINDOW', cancel)
    win.bind('<Return>', lambda e: ok())
    win.bind('<Escape>', lambda e: cancel())
    box.bind('<<ListboxSelect>>', on_select)
    redraw(0)

    # ---- 让它一定浮出来 ----
    # ⚠ 这里**不能** `win.transient(root)`: root 是 withdraw 的宿主窗口,
    #   transient 到隐藏窗口的子窗口在 Windows 上会跟着不可见 —— 窗口建了、
    #   grab 也拿了, 却没人看得见, 表现就是「多选后不弹窗 + 程序卡死」
    #   (2026-11-15 用户实测踩到)。
    win.update_idletasks()
    try:
        w, h = win.winfo_width(), win.winfo_height()
        x = max(0, (win.winfo_screenwidth() - w) // 2)
        y = max(0, (win.winfo_screenheight() - h) // 3)
        win.geometry('+%d+%d' % (x, y))
    except tk.TclError:
        pass
    win.deiconify()
    win.lift()
    try:
        win.attributes('-topmost', True)     # 压过其他窗口, 免得躲到后面
    except tk.TclError:
        pass
    try:
        win.focus_force()
    except tk.TclError:
        pass

    def try_grab(tries=15):
        """确认窗口真的可见了才抢输入 —— 不可见时抢, 等于把键盘鼠标全吞掉。

        没可见就每 100ms 再试, 最多 15 次(1.5 秒)。抢不到也不影响使用:
        没 grab 时窗口照样能点, 只是不会锁住别的窗口。
        """
        try:
            if state['shown'] or not win.winfo_exists():
                return
            if win.winfo_viewable():
                state['shown'] = True
                win.grab_set()
                return
            if tries > 0:
                win.after(100, lambda: try_grab(tries - 1))
        except tk.TclError:
            pass

    def give_up():
        """兜底: 窗口始终没能显示出来 -> 按当前顺序继续, 绝不死等。

        某些 Tk 版本/主题组合下 Toplevel 可能一直不映射。用户看不到窗口时
        唯一能做的就是别让他以为程序挂了: 直接放行, 并在 stderr 说明。
        2.5 秒才判死(原来是 0.8 秒) —— 首次初始化 Tk 或机器卡顿时, 0.8 秒
        可能窗口还没映射完, 会被误判成「显示不出来」而一闪而过。
        """
        try:
            if state['shown'] or not win.winfo_exists():
                return
            if win.winfo_viewable():
                state['shown'] = True
                return
            print('⚠ 排序窗口没能显示出来，已按当前顺序继续（想要别的顺序，'
                  '可以把文件名前面加上 1、2、3 再选）', file=sys.stderr)
            state['ok'] = True
            win.destroy()
        except tk.TclError:
            pass

    win.after(120, try_grab)
    win.after(2500, give_up)
    root.wait_window(win)
    if not state['ok']:
        return []
    return [val for kind, val in rows if kind == 'file']


# -------------------------------------------------------------- 第 1 步: 谱面浏览器
# 用户 2026-11-15 提出: 「每次都要点开 bat, 然后在 Windows 文件管理器里一层层翻文件夹,
# 太低效」—— 所以第 1 步换成自绘的列表窗口: 输入即搜索 / 点表头排序 / Ctrl·Shift 多选 /
# 双击或回车确认; 选中结果直接喂给后面的 gui_flow(分组 -> 排难度 -> 选输出目录)。
# 仍然保留一个「用文件管理器…」的退路(要挑 Songs 以外的谱面时用), 走原来的文件对话框。
#
# 数据来源 = 把 Songs 目录扫一遍(只读每个 .osu 的头部, 不解析音符): 4100 多个文件串行
# 要 30 秒(每个文件 open 约 7ms, 大头是杀软), 所以用线程池并行读 —— 本机 12 线程 1.8 秒。
# 结果按「路径 + 修改时间 + 大小」缓存到 `%APPDATA%\osu2tja2\maps_cache.json`,
# 第二次打开是瞬开; 缓存里也存了星级, 省掉再算一遍。

MAPS_CACHE_VERSION = 4          # 缓存结构改了就把这个数 +1, 旧缓存自动作废

BROWSE_COLS = (
    ('title',   '曲名',      290, 'w'),
    ('artist',  '曲师',      150, 'w'),
    ('version', '难度',      150, 'w'),
    ('level',   '★',          46, 'center'),
    ('notes',   '音符',       62, 'e'),
    ('bpm',     'BPM',        52, 'e'),
    ('size',    '大小',       70, 'e'),
    ('mtime',   '修改时间',  118, 'w'),
    ('folder',  '所在文件夹', 230, 'w'),
)


def maps_cache_path() -> str:
    """谱面列表的缓存文件位置(和 config.json 放同一个目录)。"""
    return os.path.join(os.path.dirname(CONFIG_PATH), 'maps_cache.json')


def load_maps_cache() -> dict:
    """读缓存: `{路径小写: [mtime, 大小, 曲名, 曲师, 作者, 难度, mode, bpm, 音符, sr]}`。

    版本不符 / 文件坏了 / 没权限 —— 一律当成「没有缓存」, 绝不因此打不开窗口。
    """
    try:
        with open(maps_cache_path(), 'r', encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(d, dict) or d.get('v') != MAPS_CACHE_VERSION:
        return {}
    maps = d.get('maps')
    return maps if isinstance(maps, dict) else {}


def save_maps_cache(maps: dict) -> bool:
    """写缓存(先写 .tmp 再原子替换, 断电也不会留半份)。失败不抛异常。"""
    p = maps_cache_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'v': MAPS_CACHE_VERSION, 'maps': maps}, f, ensure_ascii=False)
        os.replace(tmp, p)
        return True
    except OSError:
        return False


def _browse_meta(path: str, st=None):
    """只为「列表里显示」解析一个 .osu, 返回曲名/曲师/作者/难度名/Mode/BPM/音符数。

    与 load_chart() 无关 —— 那个是转换用的完整解析(红线/绿线/每个音符都要), 这里只要
    能填表格的那几列。文件读不了(被删/被占用)返回 None, 调用方跳过即可。
    """
    try:
        if st is None:
            st = os.stat(path)
        with open(path, 'rb') as f:
            raw = f.read()
    except OSError:
        return None
    d = {'title': '', 'artist': '', 'creator': '', 'version': '',
         'mode': -1, 'bpm': 0.0, 'notes': 0}
    section = ''
    for line in raw.decode('utf-8', 'replace').splitlines():
        s = line.strip()
        if s[:1] == '[':
            section = s
            continue
        if section == '[General]':
            if s.startswith('Mode:'):
                try:
                    d['mode'] = int(s[5:].strip() or 0)
                except ValueError:
                    pass
        elif section == '[Metadata]':
            if s.startswith('Title:'):
                d['title'] = s[6:].strip()
            elif s.startswith('Artist:'):
                d['artist'] = s[7:].strip()
            elif s.startswith('Creator:'):
                d['creator'] = s[8:].strip()
            elif s.startswith('Version:'):
                d['version'] = s[8:].strip()
        elif section == '[TimingPoints]' and not d['bpm']:
            try:
                parts = s.split(',')
                if len(parts) > 1 and float(parts[1]) > 0:
                    d['bpm'] = 60000.0 / float(parts[1])
            except ValueError:
                pass
        elif section == '[HitObjects]' and s:
            d['notes'] += 1
    d['size'] = st.st_size
    d['mtime'] = st.st_mtime
    d['md5'] = hashlib.md5(raw).hexdigest()
    return d


def _osu_db_buffers(sample_path):
    """把能找到的 osu!.db 都读进内存(一次), 之后按 md5 查星级不用再开文件。"""
    bufs = []
    for p in osu_db_paths(sample_path):
        buf = _OSU_DB_BYTES.get(p)
        if buf is None:
            try:
                with open(p, 'rb') as f:
                    buf = f.read()
            except OSError:
                continue
            _OSU_DB_BYTES[p] = buf
        bufs.append(buf)
    return bufs


def _db_star_in(bufs, md5_hex):
    """在这几份 db 内容里按 md5 找 No Mod 星级; 找不到返回 None。"""
    for buf in bufs:
        v = _db_lookup(buf, md5_hex)
        if v is not None:
            return v
    return None


def _row_from_record(path: str, rec, st) -> dict:
    """缓存记录 -> 列表行(不重新读文件)。"""
    meta = {'title': rec[2], 'artist': rec[3], 'creator': rec[4],
            'version': rec[5], 'mode': rec[6], 'bpm': rec[7], 'notes': rec[8],
            'sr': rec[9] if len(rec) > 9 else None}
    return _make_row(path, meta, st)


def _make_row(path: str, meta: dict, st) -> dict:
    """拼一行给列表窗口用。`hay` 是搜索用的全小写串, 建的时候算一次。"""
    folder = os.path.basename(os.path.dirname(path))
    sr = meta.get('sr')
    row = {
        'path': path,
        'key': path.casefold(),
        'song': os.path.dirname(path).casefold(),     # 同一首歌 = 同一个文件夹
        'folder': folder,
        'title': meta.get('title', ''),
        'artist': meta.get('artist', ''),
        'creator': meta.get('creator', ''),
        'version': meta.get('version', ''),
        'mode': meta.get('mode', -1),
        'bpm': meta.get('bpm', 0.0),
        'notes': meta.get('notes', 0),
        'size': st.st_size,
        'mtime': st.st_mtime,
        'sr': sr,
        'level': star_from_sr(sr) if sr is not None else None,
    }
    row['hay'] = ('%s\n%s\n%s\n%s\n%s' % (row['title'], row['artist'],
                                          row['version'], row['folder'],
                                          row['creator'])).casefold()
    return row


def filter_map_rows(rows, query: str, only_taiko: bool = True):
    """按搜索词 + 「只看 taiko」过滤列表行。

    查询词的处理是「整串优先、再逐词」:
      · 先把整段查询当成一句话找(「song a」「one of us」这种曲名里的空格不会被拆开);
      · 整串没命中, 才拆成词做**交集**(「katagiri oni」= 曲师 ∩ 难度名)。
    只做逐词交集的话, 搜「Song A」会把 ArtistB 的歌也带出来 —— 'a' 是 'ArtistB' 的子串。
    """
    picked = [r for r in rows if not only_taiko or r['mode'] == 1]
    q = (query or '').strip().casefold()
    if not q:
        return picked
    hits = [r for r in picked if q in r['hay']]
    if hits:
        return hits
    terms = [t for t in q.split() if t]
    return [r for r in picked if all(t in r['hay'] for t in terms)]


def scan_osu_maps(root_dir: str, progress=None, use_cache: bool = True,
                  workers: int = 12):
    """扫 `root_dir` 下所有 .osu, 返回 (行列表, 新缓存记录)。

    `progress(已完成, 总数)` 在**工作线程**里被调用 —— 调用方负责转回 UI 线程。
    行按路径排序返回(窗口自己再按表头排), 缓存里只保留这次真的扫到的东西(自动清理失效项)。
    """
    paths, stats = [], {}
    for dirpath, dirs, files in os.walk(root_dir):
        dirs[:] = [x for x in dirs if not x.startswith('.')]
        for name in files:
            if name.lower().endswith('.osu'):
                p = os.path.join(dirpath, name)
                try:
                    stats[p] = os.stat(p)
                except OSError:
                    continue
                paths.append(p)
    total = len(paths)
    cache = load_maps_cache() if use_cache else {}

    rows, todo, records = [], [], {}
    done = 0
    for p in paths:
        st = stats[p]
        rec = cache.get(p.casefold())
        if (isinstance(rec, list) and len(rec) >= 10
                and abs(rec[0] - st.st_mtime) < 1e-6 and rec[1] == st.st_size):
            rows.append(_row_from_record(p, rec, st))
            records[p.casefold()] = rec
            done += 1
        else:
            todo.append(p)
    if progress and done:
        progress(done, total)

    if todo:
        bufs = _osu_db_buffers(root_dir)
        step = max(1, total // 100)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for p, meta in ex.map(lambda x: (x, _browse_meta(x, stats[x])), todo):
                done += 1
                if meta is None:
                    continue
                if meta['mode'] == 1:                    # 只有 taiko 谱 db 里才是 taiko 星级
                    meta['sr'] = _db_star_in(bufs, meta['md5'])
                rows.append(_make_row(p, meta, stats[p]))
                rec = [stats[p].st_mtime, stats[p].st_size, meta['title'],
                       meta['artist'], meta['creator'], meta['version'],
                       meta['mode'], meta['bpm'], meta['notes'], meta.get('sr')]
                records[p.casefold()] = rec
                if progress and done % step == 0:
                    progress(done, total)
    if progress:
        progress(total, total)
    rows.sort(key=lambda r: r['key'])
    return rows, records


class MapBrowserDialog:
    """第 1 步的谱面选择窗口(自绘表格, 不用系统文件管理器)。

    · 搜索框: 空格分隔多个词, **全部**命中(曲名/曲师/作者/难度名/文件夹)才显示
    · 点表头排序, 再点一次反向; 默认按曲名。★ / 音符 / 大小 / 时间按数值排
    · Ctrl / Shift 多选; 双击某行 = 确定; 回车 = 确定; Esc = 取消
    · 右键: 选中这首歌的全部谱面 / 全选当前列表 / 清空选择
    · 底栏一直显示「共多少张 / 涉及多少首歌 / 已选多少」, 免得漏选或多选

    ⚠ 窗口**不能** transient 到隐藏的宿主 root(会跟着不可见还抢输入), 见
      ask_order_dialog() 里那段说明 —— 这里复刻同一套「显示 -> lift -> 确认可见再 grab」。
    """

    def __init__(self, master, initial_root=None):
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        self.master = master
        self.result = []                 # 确定时填, 里面是选中的 .osu 路径
        self.want_dialog = False         # True = 用户要退回系统文件对话框
        self.root_dir = initial_root or default_input_dir() or ''
        self.rows = []                   # 全部行
        self.view = []                   # 当前筛选+排序后显示的
        self.sel = set()                 # 已选路径(小写); 筛选掉的选择也留着
        self.sort_key, self.sort_desc = 'title', False
        self.search = ''
        self.only_taiko = True
        self.scanning = False
        self.scan_token = 0
        self._rendering = False
        self._search_job = None
        self._shown = False
        self._build()

    # ---------------------------------------------------------- 界面
    def _build(self):
        tk = self.tk
        win = tk.Toplevel(self.master)
        self.win = win
        win.title('第 1 步 — 选择谱面（搜索 / 排序 / 多选）')
        win.geometry('1180x700')
        win.minsize(820, 420)
        win.protocol('WM_DELETE_WINDOW', self._cancel)

        top = tk.Frame(win)
        top.pack(fill='x', padx=10, pady=(10, 4))
        tk.Label(top, text='搜索').pack(side='left')
        self.var_search = tk.StringVar()
        self.entry = tk.Entry(top, textvariable=self.var_search, width=44)
        self.entry.pack(side='left', padx=(6, 8))
        self.var_search.trace_add('write', self._on_search_typed)
        tk.Label(top, text='（整串优先，找不到再按空格拆词；搜曲名/曲师/作者/难度/文件夹）',
                 fg='#888').pack(side='left')
        self.var_taiko = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text='只看 taiko', variable=self.var_taiko,
                       command=self.refresh).pack(side='right')
        tk.Button(top, text='刷新', width=6, command=self.start_scan).pack(side='right', padx=4)
        tk.Button(top, text='用文件管理器…', command=self._classic).pack(side='right', padx=4)
        tk.Button(top, text='换目录…', width=9, command=self._choose_root).pack(side='right', padx=4)

        mid = tk.Frame(win)
        mid.pack(fill='both', expand=True, padx=10)
        cols = [c[0] for c in BROWSE_COLS]
        self.tree = self.ttk.Treeview(mid, columns=cols, show='headings',
                                      selectmode='extended')
        for key, text, width, anchor in BROWSE_COLS:
            if key == self.sort_key:                 # 默认按曲名, 表头带个 ▲
                text = '%s %s' % (text, '▼' if self.sort_desc else '▲')
            self.tree.heading(key, text=text,
                              command=lambda k=key: self.sort_by(k))
            self.tree.column(key, width=width, anchor=anchor,
                             stretch=(key in ('title', 'folder', 'version')))
        vsb = self.ttk.Scrollbar(mid, orient='vertical', command=self.tree.yview)
        hsb = self.ttk.Scrollbar(mid, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Double-1>', self._on_double)
        self.tree.bind('<Button-3>', self._popup)

        self.menu = tk.Menu(win, tearoff=0)
        self.menu.add_command(label='选中这首歌的全部谱面', command=self._select_song)
        self.menu.add_command(label='全选当前列表', command=self._select_all)
        self.menu.add_command(label='清空选择', command=self._clear_sel)

        bottom = tk.Frame(win)
        bottom.pack(fill='x', padx=10, pady=8)
        self.lbl_dir = tk.Label(bottom, text='', fg='#888', anchor='w')
        self.lbl_dir.pack(side='left')
        self.btn_ok = tk.Button(bottom, text='确定转换', width=16, command=self._confirm)
        self.btn_ok.pack(side='right', padx=4)
        tk.Button(bottom, text='取消', width=8, command=self._cancel).pack(side='right')
        self.lbl_status = tk.Label(win, text='正在准备…', anchor='w')
        self.lbl_status.pack(fill='x', padx=10, pady=(0, 8))

        win.bind('<Return>', lambda e: self._confirm())
        win.bind('<Escape>', lambda e: self._cancel())
        win.bind('<Control-a>', lambda e: (self._select_all(), 'break')[1])
        win.bind('<Control-A>', lambda e: (self._select_all(), 'break')[1])

        self._set_dir_label()
        self.start_scan()
        self._show()

    def _show(self):
        """定位到屏幕中间并确保真的可见(隐藏 root 的子窗口容易「建了但看不见」)。"""
        win = self.win
        win.update_idletasks()
        try:
            w, h = win.winfo_width(), win.winfo_height()
            x = max(0, (win.winfo_screenwidth() - w) // 2)
            y = max(0, (win.winfo_screenheight() - h) // 3)
            win.geometry('+%d+%d' % (x, y))
        except self.tk.TclError:
            pass
        win.deiconify()
        win.lift()
        try:
            win.attributes('-topmost', True)
        except self.tk.TclError:
            pass
        try:
            self.entry.focus_force()
        except self.tk.TclError:
            pass
        self._shown = False
        self.win.after(120, self._try_grab)
        self.win.after(2500, self._give_up)

    def _try_grab(self, tries=15):
        try:
            if self._shown or not self.win.winfo_exists():
                return
            if self.win.winfo_viewable():
                self._shown = True
                self.win.grab_set()
                return
            if tries > 0:
                self.win.after(100, lambda: self._try_grab(tries - 1))
        except self.tk.TclError:
            pass

    def _give_up(self):
        """窗口始终没能显示 -> 退回系统文件对话框, 绝不死等。

        和 ask_order_dialog 的 give_up 一个道理: 用户看不见窗口时, 唯一能做的就是
        别让他以为程序挂了。
        """
        try:
            if self._shown or not self.win.winfo_exists():
                return
            if self.win.winfo_viewable():
                self._shown = True
                return
            print('⚠ 谱面浏览器没能显示出来，改用系统文件对话框', file=sys.stderr)
            self.want_dialog = True
            self.win.destroy()
        except self.tk.TclError:
            pass

    # ---------------------------------------------------------- 扫描
    def _set_dir_label(self):
        self.lbl_dir.configure(text='目录：%s' % (self.root_dir or '(未找到 osu! 的 Songs 目录)'))

    def start_scan(self):
        """后台线程扫目录; 结果通过队列回到 UI 线程(跨线程碰控件会崩)。"""
        if not self.root_dir or not os.path.isdir(self.root_dir):
            self.rows, self.view = [], []
            self._render()
            self.lbl_status.configure(text='没有可扫描的目录，用「换目录…」指定 osu! 的 Songs 文件夹')
            return
        self.scan_token += 1
        token = self.scan_token
        self.scanning = True
        self.lbl_status.configure(text='正在扫描…')
        q = queue.Queue()

        def worker():
            try:
                rows, records = scan_osu_maps(
                    self.root_dir, progress=lambda d, t: q.put(('progress', d, t)))
                q.put(('done', rows, records))
            except Exception as e:                   # 扫描失败不该让窗口崩
                q.put(('error', '%s: %s' % (type(e).__name__, e), None))

        threading.Thread(target=worker, daemon=True).start()
        self.win.after(80, lambda: self._poll(token, q))

    def _poll(self, token, q):
        if token != self.scan_token or not self.win.winfo_exists():
            return
        try:
            while True:
                kind, a, b = q.get_nowait()
                if kind == 'progress':
                    self.lbl_status.configure(text='正在扫描… %d / %d' % (a, b))
                elif kind == 'done':
                    self.scanning = False
                    self.rows = a
                    save_maps_cache(b)
                    self.refresh()
                    return
                else:
                    self.scanning = False
                    self.lbl_status.configure(text='扫描失败：%s' % a)
                    return
        except queue.Empty:
            pass
        self.win.after(80, lambda: self._poll(token, q))

    # ---------------------------------------------------------- 筛选 / 排序 / 渲染
    def _on_search_typed(self, *_a):
        """打字防抖: 每停 220ms 才真的重排一次(四千行重建列表有点重)。"""
        if self._search_job is not None:
            try:
                self.win.after_cancel(self._search_job)
            except self.tk.TclError:
                pass
        self._search_job = self.win.after(220, self.refresh)

    def refresh(self):
        self._search_job = None
        for i, r in enumerate(self.rows):            # 表格 iid 用行下标, 每次重建都刷新一遍
            r['_idx'] = i
        self.search = self.var_search.get().strip()
        self.only_taiko = bool(self.var_taiko.get())
        self.view = self._sorted(filter_map_rows(self.rows, self.search, self.only_taiko))
        self._render()

    def _sorted(self, rows):
        key = self.sort_key
        numeric = key in ('level', 'notes', 'bpm', 'size', 'mtime')

        def sort_val(r):
            v = r.get(key)
            if v is None:
                v = -1.0 if numeric else ''
            if isinstance(v, str):
                v = v.casefold()
            return v
        return sorted(rows, key=sort_val, reverse=self.sort_desc)

    def sort_by(self, key):
        if key == self.sort_key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key = key
            # 数值列默认「大的在前」(★ / 音符 / 大小), 文本列默认升序
            self.sort_desc = key in ('level', 'notes', 'bpm', 'size', 'mtime')
        for k, text, _w, _a in BROWSE_COLS:
            if k == key:
                text = '%s %s' % (text, '▼' if self.sort_desc else '▲')
            self.tree.heading(k, text=text)
        self.view = self._sorted(self.view)
        self._render()

    def _values(self, r):
        return (
            r['title'] or '(无标题)',
            r['artist'],
            r['version'],
            '' if r['level'] is None else str(r['level']),
            str(r['notes']) if r['notes'] else '',
            ('%.0f' % r['bpm']) if r['bpm'] else '',
            _fmt_size(r['size']),
            time.strftime('%Y-%m-%d %H:%M', time.localtime(r['mtime'])),
            r['folder'],
        )

    def _render(self):
        """重建表格。iid 用行在 self.rows 里的下标, 重建时按 key 把选择还原。"""
        self._rendering = True
        try:
            tree = self.tree
            tree.delete(*tree.get_children())
            for r in self.view:
                tree.insert('', 'end', iid=str(r['_idx']), values=self._values(r))
            keep = [str(r['_idx']) for r in self.view if r['key'] in self.sel]
            if keep:
                tree.selection_set(keep)
        finally:
            self._rendering = False
        self._update_status()

    def _visible_selected(self):
        """当前列表里被选中的行(按表格顺序)。"""
        picked = set(self.tree.selection())
        return [r for r in self.view if str(r['_idx']) in picked]

    def _on_select(self, _ev=None):
        if self._rendering:
            return
        self.sel = {r['key'] for r in self._visible_selected()}
        self._update_status()

    def _update_status(self):
        n_songs = len({r['song'] for r in self.rows})
        hidden = len(self.sel) - len([r for r in self.view if r['key'] in self.sel])
        text = '共 %d 张谱面 / %d 首歌　·　当前显示 %d 张' % (
            len(self.rows), n_songs, len(self.view))
        picked = self._visible_selected()
        if picked:
            songs = {}
            for r in picked:
                songs[r['folder']] = songs.get(r['folder'], 0) + 1
            text += '　·　已选 %d 张（%d 首）：' % (len(picked), len(songs))
            text += '、'.join('%s×%d' % (_song_label(k), v)
                             for k, v in list(songs.items())[:4])
            if len(songs) > 4:
                text += ' …'
            over = [k for k, v in songs.items() if v > MAX_INPUTS]
            if over:
                text += '　⚠ %s 超过 %d 张，转不了（会报错）' % (over[0], MAX_INPUTS)
        elif self.sel:
            text += '　·　已选 %d 张' % len(self.sel)
        if hidden:
            text += '（%d 张被筛选隐藏）' % hidden
        self.lbl_status.configure(text=text)
        self.btn_ok.configure(
            text='确定转换 (%d 张)' % len(self.sel) if self.sel else '确定转换')

    # ---------------------------------------------------------- 选择操作
    def _select_all(self):
        self.tree.selection_set([str(r['_idx']) for r in self.view])
        self._on_select()

    def _clear_sel(self):
        self.tree.selection_remove(*self.tree.selection())
        self.sel = set()
        self._update_status()

    def _select_song(self):
        """把「当前点中的那一行所属文件夹」的全部谱面选上(一首歌整组选中)。"""
        picked = self._visible_selected()
        if not picked:
            return
        folders = {r['song'] for r in picked}
        idx = [str(r['_idx']) for r in self.view if r['song'] in folders]
        self.tree.selection_add(*idx)
        self._on_select()

    def _popup(self, ev):
        row = self.tree.identify_row(ev.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
            self._on_select()
        try:
            self.menu.tk_popup(ev.x_root, ev.y_root)
        finally:
            self.menu.grab_release()

    def _on_double(self, ev):
        if self.tree.identify_row(ev.y):
            self._confirm()

    # ---------------------------------------------------------- 收尾
    def _confirm(self):
        picked = self._visible_selected()
        if not picked:
            self.messagebox.showwarning(
                '还没选谱面', '先在列表里点选（Ctrl/Shift 可多选），再点「确定转换」。',
                parent=self.win)
            return
        if self.scanning:
            self.messagebox.showwarning(
                '还在扫描', '列表还在补全，等扫描结束（底栏进度消失）再确定。',
                parent=self.win)
            return
        self.result = [r['path'] for r in picked]
        self.win.destroy()

    def _cancel(self):
        self.result = []
        self.win.destroy()

    def _classic(self):
        """退回老路: 系统文件对话框(挑 Songs 以外的谱面时用)。"""
        self.want_dialog = True
        self.win.destroy()

    def _choose_root(self):
        from tkinter import filedialog
        picked = filedialog.askdirectory(
            parent=self.win, title='选择 osu! 的 Songs 目录（或任意装着 .osu 的文件夹）',
            initialdir=self.root_dir or default_input_dir() or os.getcwd())
        if not picked:
            return
        self.root_dir = os.path.abspath(picked)
        save_config(maps_root=self.root_dir)
        self.sel = set()
        self._set_dir_label()
        self.start_scan()


def _song_label(folder: str) -> str:
    """osu 的谱面集文件夹名形如 `1777519 Memme - Gaehwa`, 状态栏里只留曲名部分。"""
    return re.sub(r'^\d+\s+', '', folder or '') or (folder or '')


def _fmt_size(n):
    """字节数 -> 人看的「12 KB / 1.4 MB」。"""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ''
    if n >= 1024 * 1024:
        return '%.1f MB' % (n / 1024.0 / 1024.0)
    if n >= 1024:
        return '%.0f KB' % (n / 1024.0)
    return '%d B' % int(n)


def browse_maps(master, initial_root=None):
    """弹出谱面浏览器并等它关掉。

    返回: 选中的 .osu 路径列表(按列表当前顺序) / `[]` 表示取消 /
          `None` 表示「用户要改用系统文件对话框」或窗口打不开(调用方退回 filedialog)。
    """
    try:
        dlg = MapBrowserDialog(master, initial_root)
    except Exception as e:
        print('⚠ 谱面浏览器打不开(%s: %s)，改用系统文件对话框'
              % (type(e).__name__, e), file=sys.stderr)
        return None
    master.wait_window(dlg.win)
    return None if dlg.want_dialog else dlg.result


def run_gui(output_hint=None, red_grid: bool = True,
            offset_shift_ms: float = None,
            open_output_dir: bool = False,
            song_folder: bool = True, allow_name_fallback: bool = True,
            trim_audio: bool = True, trim_tail_ms: float = None) -> int:
    """弹出图形选择框, 依次三步: 选谱面 -> (多选时)排难度顺序 -> 选输出文件夹。

    第 1 步是自带的谱面浏览器(见 MapBrowserDialog): 在列表里搜索/排序/多选, 不再翻
    Windows 文件管理器; 它也能退回系统对话框(用户点「用文件管理器…」或窗口没能显示)。

    难度名按星数自动定(见 order_by_star), 只有星数打平才多一步「谁先谁后」; 然后问落到哪个目录。
    输出文件夹会记住上次的选择(见 remembered_out_dir); 第 1 步的谱面列表扫的是上次
    浏览过的目录(见 config 的 maps_root), 没有就扫 osu! 的 Songs(见 DEFAULT_INPUT_DIRS)。
    转换完成后只弹一条结果提示, 不询问是否打开输出文件夹;
    要它顺手打开就传 open_output_dir=True。
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception as e:
        print('这个 Python 里没有 tkinter, 用不了图形界面 (%s)' % e, file=sys.stderr)
        print('双击 %s 启动(它用 py, 自带 tkinter), 或者改用命令行:'
              % LAUNCHER_BAT, file=sys.stderr)
        print('    python %s "谱面.osu" -o 输出目录' % SCRIPT_NAME, file=sys.stderr)
        return 1

    root = tk.Tk()
    root.withdraw()                             # 只借它当对话框的宿主, 不显示主窗口
    try:
        root.attributes('-topmost', True)       # 让选择框浮到最前面
    except tk.TclError:
        pass
    root.update()

    def ask_files():
        # 第 1 步默认走**自带的谱面浏览器**(搜索 / 点表头排序 / Ctrl·Shift 多选),
        # 不再每次都从 Windows 文件管理器一层层翻文件夹。
        # 它返回 None = 用户点了「用文件管理器…」, 或窗口没能显示出来 -> 退回下面的老路。
        start = load_config().get('maps_root')
        if not (isinstance(start, str) and start and os.path.isdir(start)):
            start = default_input_dir()
        picked = browse_maps(root, start)
        if picked is not None:
            return picked
        # ---- 下面是老行为(系统文件对话框), 原样保留 ----
        # 默认停在 osu! 的 Songs 目录(见 DEFAULT_INPUT_DIRS); 找不到才交给 tkinter 自己定。
        kw = dict(
            parent=root,
            title='第 1 步 — 选择 osu!taiko 谱面（可多选；同一首歌的几张合成多难度谱，'
                  '不同歌各自转）',
            filetypes=[('osu! 谱面 (*.osu)', '*.osu'), ('所有文件', '*.*')])
        if start:
            kw['initialdir'] = start
        picked = filedialog.askopenfilenames(**kw)
        # 老版本 Tk 可能返回「空格分隔的整串」而不是 tuple —— 直接 list() 会把它
        # 拆成一个个字符, 后面全是垃圾路径。用 Tcl 的 splitlist 拆才可靠。
        if isinstance(picked, str):
            picked = root.tk.splitlist(picked)
        return [p for p in picked if p]

    def ask_dir(initialdir):
        # 弹窗停在上次用过的输出文件夹; 选完立刻记下来, 下次直接用它开框。
        picked = filedialog.askdirectory(
            parent=root,
            title='最后一步 — 选择输出位置（每首歌会在其中各建一个「曲名」文件夹）',
            initialdir=remembered_out_dir(initialdir), mustexist=False)
        if picked:
            save_config(out_dir=os.path.abspath(picked))
        return picked

    def ask_order(paths):
        """多选时弹「排难度顺序」小窗口; 实现见模块级的 ask_order_dialog()。

        这一步是锦上添花, 绝不能因为 Tk 抛个异常就把整次转换废掉:
        出错就退回选择框给的顺序, 并在 stderr 说明一句。
        """
        try:
            return ask_order_dialog(root, paths)
        except Exception as e:
            print('⚠ 排序窗口出错，已按选择框给的顺序继续 (%s)' % e, file=sys.stderr)
            return list(paths)

    def ask_yes(title, text):
        return bool(messagebox.askyesno(title, text, parent=root))

    def info(title, text):
        messagebox.showinfo(title, text, parent=root)

    def error(title, text):
        print('%s: %s' % (title, text), file=sys.stderr)
        messagebox.showerror(title, text, parent=root)

    try:
        return gui_flow(ask_files, ask_dir, ask_yes, error, output_hint,
                        red_grid=red_grid, offset_shift_ms=offset_shift_ms,
                        info=info, open_output_dir=open_output_dir,
                        song_folder=song_folder,
                        allow_name_fallback=allow_name_fallback,
                        trim_audio=trim_audio, trim_tail_ms=trim_tail_ms,
                        ask_order=ask_order)
    finally:
        root.destroy()


# -------------------------------------------------------------- 命令行

def _split_list(text):
    """把 `--courses Hard,Normal` 这种逗号列表拆开; 全角逗号也认(中文输入法常见)。"""
    return [x.strip() for x in (text or '').replace('，', ',').split(',') if x.strip()]


def _cli_multi(inputs, args, shift_ms) -> int:
    """命令行里「给了多个 .osu」的分支: 算输出位置 -> convert_multi -> 退出码。

    输出文件名不再沿用某一张谱的文件名(一个文件装了多张谱), 改用**曲名**,
    于是目录形如 `<你选的>/<曲名>/<曲名>.tja` —— 模拟器按「一个文件夹一首歌」收录。
    """
    fallback = not args.keep_original_names
    courses_opt = _split_list(args.courses)
    levels_opt = [int(x) for x in _split_list(args.levels)]
    if args.level is not None and not levels_opt:
        levels_opt = [args.level] * len(inputs)      # --level 在多输入时表示「全都用这个」
    if args.course:
        print('多难度模式下 --course 不生效, 各段难度请用 --courses', file=sys.stderr)
    # 张数上限先拦, 不进 convert_multi 白解一遍文件(报错文案在 multi_difficulties 里)
    # 张数上限先拦: 不进 convert_multi 白解一遍文件(完整报错文案在 multi_difficulties 里)
    try:
        multi_difficulties(len(inputs))
    except ValueError as e:
        print('✖ %s' % e, file=sys.stderr)
        return 1

    # ★ 取名必须和 convert_multi 内部**同一个顺序**: 它按星数降序排过之后才写 TITLE,
    #   这里若还沿用用户给的 inputs[0], 就会出现「文件夹叫 Talk、TITLE 写 BUZZ CUTZ」
    #   这种错位(4~5 张的低难版一撞就中)。order_by_star 是幂等的, 多排一次没副作用。
    ordered = list(inputs)
    if not (courses_opt or levels_opt):
        ordered, _ties = order_by_star(ordered)

    meta0 = read_meta(ordered[0])
    title0, _ = pick_display_name(meta0, 'Title', 'TitleUnicode', args.title, fallback)
    stem = safe_name(title0) + '.tja'
    if not args.output:
        dst = os.path.join(os.path.dirname(os.path.abspath(ordered[0])), stem)
    elif _is_output_file(args.output):
        dst = args.output
    else:
        dst = os.path.join(args.output, stem)
    dst, out_dir = output_paths(ordered[0], dst, meta0, song_folder=not args.flat,
                               title_opt=args.title, allow_name_fallback=fallback)
    if out_dir and not os.path.isdir(out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            print('无法创建输出目录 %s: %s' % (out_dir, e), file=sys.stderr)
            return 1

    try:
        summary = convert_multi(
            ordered, dst, args.encoding, courses_opt, levels_opt,
            args.barline, args.subdiv, args.quiet, args.wave_ext,
            copy_audio=not args.no_copy_audio, red_grid=not args.no_red_snap,
            offset_shift_ms=shift_ms, demostart_s=args.demostart,
            title_opt=args.title, artist_opt=args.artist,
            allow_name_fallback=fallback,
            trim_audio=not args.no_trim_audio,
            trim_tail_ms=(args.trim_tail * 1000.0
                          if args.trim_tail is not None else None),
            # 没显式指定难度名/星数时, 让星数决定谁的难度更高(见 order_by_star);
            # 一旦给了 --courses/--levels, 就老老实实按用户给的顺序对号。
            auto_order=not (courses_opt or levels_opt))
    except Exception as e:
        print('转换失败: %s' % e, file=sys.stderr)
        return 1
    if summary.get('audio_error'):
        print('⚠ 音源没转成 OGG: %s' % summary['audio_error'], file=sys.stderr)
        return 1
    if args.quiet and summary.get('encoding_warning'):
        print('⚠ %s' % summary['encoding_warning'], file=sys.stderr)
    return 0

def _cli_batch(inputs, args, shift_ms) -> int:
    """命令行里「选的谱面跨了多首歌」的分支: 每首歌各转一个 .tja。

    ⚠ 批量**必须**有输出目录: 没有合理的缺省位置 —— 写到第一张谱所在的 mapset 文件夹里
      会把成品混进 osu 的 Songs 目录, 而每首歌的目录又各不相同。所以 -o 没给就直接报错。
    """
    fallback = not args.keep_original_names
    if not args.output:
        print('✖ 一次转多首歌时必须用 -o 指定输出目录，例如：\n'
              '    python %s a.osu b.osu -o D:\\TJA' % SCRIPT_NAME, file=sys.stderr)
        return 1
    out_root = args.output
    if _is_output_file(out_root):
        out_root = os.path.dirname(os.path.abspath(out_root))
        print('⚠ -o 给的是文件名，批量模式改用它的目录：%s' % out_root, file=sys.stderr)
    courses_opt = _split_list(args.courses)
    levels_opt = [int(x) for x in _split_list(args.levels)]
    if args.level is not None and not levels_opt:
        levels_opt = [args.level] * MAX_INPUTS       # 「所有段都用这个星数」
    if args.course:
        print('多难度模式下 --course 不生效，各段难度请用 --courses', file=sys.stderr)
    if args.title or args.artist:
        print('⚠ 一次转多首歌时 --title / --artist 不生效（各首歌的曲名曲师来自它自己的 .osu）',
              file=sys.stderr)
    if args.flat:
        print('⚠ 多首歌不能用 --flat（音源文件名会互相覆盖），已改为每首歌一个文件夹',
              file=sys.stderr)
    try:
        summary = convert_batch(
            inputs, out_root, args.encoding, courses_opt, levels_opt,
            args.barline, args.subdiv, args.quiet, args.wave_ext,
            copy_audio=not args.no_copy_audio, red_grid=not args.no_red_snap,
            offset_shift_ms=shift_ms, demostart_s=args.demostart,
            allow_name_fallback=fallback,
            trim_audio=not args.no_trim_audio,
            trim_tail_ms=(args.trim_tail * 1000.0
                          if args.trim_tail is not None else None),
            auto_order=not (courses_opt or levels_opt))
    except Exception as e:
        print('转换失败: %s' % e, file=sys.stderr)
        return 1
    if args.quiet:
        print('批量: %d 首歌 / 共 %d 张谱面 -> %s  (%s)'
              % (summary['count_groups'], summary['count_files'], out_root,
                 '全部成功' if summary['ok'] else '有失败项'))
        for it in summary['items']:
            if it['error']:
                print('  ✖ %s: %s' % (it['target']['name'], it['error']), file=sys.stderr)
            elif (it['summary'] or {}).get('audio_error'):
                print('  ⚠ %s 音源没转成: %s'
                      % (it['target']['name'], it['summary']['audio_error']),
                      file=sys.stderr)
    return 0 if summary['ok'] else 1


def main() -> int:
    """命令行入口: 解析参数 -> 走图形界面或直接转换, 返回进程退出码。"""
    # 难度组合的短语, 拼进 --help 用。⚠ argparse 会拿 help 串做 % 替换, 所以这里
    # 先格式化干净, 别把裸 % 留给它。
    plan_short = '、'.join(
        '%d 张=%s' % (n, ','.join(MULTI_COURSES[n]))
        for n in sorted(MULTI_COURSES))
    ap = argparse.ArgumentParser(
        add_help=True,
        description='osu!taiko -> TJA 转换器（%s）' % PROFILE_LABEL[PROFILE])
    ap.add_argument('input', nargs='*', default=None, metavar='OSU',
                    help='输入的 .osu 文件。1 个 = 单难度(Oni); 同一首歌的 2~%d 个 = 合成'
                         '**一个多难度 .tja**(按星数从高到低排); '
                         '选中的谱面跨了多首歌 = **每首歌各转一个 .tja**(批量, 此时必须用 -o '
                         '指定输出目录)。"同一首歌"的判据 = 在同一个文件夹里。'
                         '本档组合: %s。每首歌最多 %d 张。不写这个参数就弹出图形选择框'
                         % (MAX_INPUTS, plan_short, MAX_INPUTS))
    ap.add_argument('-o', '--output', default=None,
                    help='输出 .tja 路径; 给目录则自动放进该目录; 缺省=与输入同目录同名。'
                         '多输入时改用「曲名」命名; 批量(多首歌)时**必须给目录**')
    ap.add_argument('--encoding', default='cp932', choices=['cp932', 'utf-8', 'utf-8-sig'])
    ap.add_argument('--course', default=None, type=_course_arg, metavar='NAME',
                    help='难度: Oni(鬼/魔王, 默认) / Hard(困难) / Normal(普通) / '
                         'Easy(简单) / Edit(里) / auto(按 .osu 的 Version 猜)。'
                         '中英文都认。多输入时这一项不作数, 改用 --courses')
    ap.add_argument('--level', type=int, default=None,
                    help='星数 (= LEVEL, 模拟器里显示成 ★×N)。缺省 = 这张谱的 osu!taiko SR × 2 '
                         '四舍五入(SR 读你 osu!.db 里缓存的值, 即游戏里显示的数)。'
                         '多输入时表示「所有段都用这个星数」')
    ap.add_argument('--courses', default=None, metavar='LIST',
                    help='多输入时按顺序指定各段的 COURSE(逗号分隔), 如 里,Oni 或 Edit,Oni。'
                         '认 Oni/Hard/Normal/Easy/Edit 与 鬼/困难/里。'
                         '缺省按张数定: %s' % plan_short)
    ap.add_argument('--levels', default=None, metavar='LIST',
                    help='多输入时按顺序指定各段的 LEVEL(星数), 如 10,9。'
                         '缺省 = 每张谱各自 SR × 2 四舍五入')
    ap.add_argument('--barline', default='auto', choices=['auto', 'show', 'hide'],
                    help='小节线: auto(默认)=照 osu 的 "Omit first bar line" 标记 | show=全画 | hide=全隐藏')
    ap.add_argument('--subdiv', type=int, default=4,
                    help='基准「每拍格数」, 默认 4(本家最常用: 一格=1/4 拍); '
                         '音符摆不下时会自动升到 6/8/12/16/24 等, 一般不用改')
    ap.add_argument('--wave-ext', default=None,
                    help='音源只认这个扩展名(如 ogg); 缺省=优先用 .osu 的 AudioFilename, 找不到再自动扫')
    ap.add_argument('--no-copy-audio', action='store_true',
                    help='不输出音源文件(默认会把音源转成 OGG 一起放进曲名文件夹, 并让 WAVE 指向它)')
    ap.add_argument('--no-trim-audio', action='store_true',
                    help='不裁音频末尾冗余的部分(默认会裁: 谱面最后一个音符之后只留 %g 秒余韵)。'
                         '只裁尾、绝不碰开头, 所以 OFFSET / DEMOSTART 都不受影响'
                         % (TRIM_TAIL_MS / 1000.0))
    ap.add_argument('--trim-tail', type=float, default=None, metavar='SEC',
                    help='裁尾时在最后一个音符(连打/气球看终点)之后保留多少秒余韵, '
                         '默认 %g 秒。觉得尾音被切短了就调大(如 5)' % (TRIM_TAIL_MS / 1000.0))
    ap.add_argument('--flat', action='store_true',
                    help='不在输出目录下新建「曲名」文件夹, 直接把 .tja 和 .ogg 放进指定目录(旧行为)')
    ap.add_argument('--title', default=None, metavar='TEXT',
                    help='强制指定曲名(同时用于 TITLE: 头和「曲名」文件夹名)。'
                         '源 .osu 的 TitleUnicode 是坏的时候(很多老谱面会把假名写坏成'
                         '别的汉字), 用这个覆盖, 不必去改源文件')
    ap.add_argument('--artist', default=None, metavar='TEXT',
                    help='强制指定曲师(写入 ARTIST: 与 SUBTITLE:)。'
                         '想让它和曲名走同一套编码时可配合 --encoding')
    ap.add_argument('--keep-original-names', action='store_true',
                    help='不做「乱码自动退到罗马音」: TitleUnicode/ArtistUnicode 里写什么就用什么。'
                         '默认会检查原名是否被写坏(泰文/韩文/只有汉字+长音符一类), '
                         '判坏时改用 Title/Artist 那栏的罗马音')
    ap.add_argument('--no-red-snap', action='store_true',
                    help='关闭「红线网格还原」(默认开启): 原样保留 osu 的整数毫秒红线时刻, '
                         '#MEASURE 会退回 167999/168041 这种畸形分数, 仅供对照排查')
    ap.add_argument('--offset-shift', type=float, default=None, metavar='MS',
                    help='全局 OFFSET 微调(毫秒, 正数=写出的 OFFSET 变大)。只改头部 '
                         'OFFSET: 这一行, 音符/小节/BPM 一律不动 —— 等价于手工把 .tja 里的 '
                         'OFFSET 改掉。缺省 = 模块常数(当前 %gms, 见该常数说明); '
                         '--offset-shift 0 就是不加偏移' % DEFAULT_OFFSET_SHIFT_MS)
    ap.add_argument('--no-offset-shift', action='store_true',
                    help='等价于 --offset-shift 0: 完全照搬 osu 的谱面起点, 不加那 %gms 的固定差值'
                         % DEFAULT_OFFSET_SHIFT_MS)
    ap.add_argument('--demostart', type=float, default=None, metavar='SEC',
                    help='预览起点(秒, 从音频开头算), 写到头部 DEMOSTART:。缺省 = 照抄 osu 的 '
                         'PreviewTime(毫秒 / 1000); osu 里没设(-1)就从 0 开始。'
                         '传负数等价于 0。')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--forget-out-dir', action='store_true',
                    help='忘掉图形界面记住的输出文件夹和谱面目录(下次弹窗从头选)。')
    ap.add_argument('--open-out-dir', action='store_true',
                    help='转换完成后顺手打开输出文件夹(默认不打开、也不询问)')
    ap.add_argument('--gui', action='store_true', help='强制弹窗选择(即使已经写了输入文件)')
    args = ap.parse_args()

    if args.forget_out_dir:
        save_config(out_dir='', maps_root='')
        print('已忘掉记住的输出文件夹和谱面目录（下次弹窗会从头选）')
        print('配置文件: %s' % CONFIG_PATH)
        return 0

    # OFFSET 微调: 缺省 = 模块常数; --offset-shift 显式给了就用它; --no-offset-shift 等价于 0
    shift_ms = args.offset_shift
    if args.no_offset_shift:
        shift_ms = 0.0

    # 没给输入文件(或明确要求) -> 走图形界面
    if args.gui or not args.input:
        return run_gui(args.output, red_grid=not args.no_red_snap,
                       offset_shift_ms=shift_ms,
                       open_output_dir=args.open_out_dir,
                       song_folder=not args.flat,
                       allow_name_fallback=not args.keep_original_names,
                       trim_audio=not args.no_trim_audio,
                       trim_tail_ms=(args.trim_tail * 1000.0
                                     if args.trim_tail is not None else None))

    inputs = list(args.input or [])
    for p in inputs:
        if not os.path.isfile(p):
            print('找不到输入文件: %s' % p, file=sys.stderr)
            return 1
        if not p.lower().endswith('.osu'):
            print('输入文件应当是 .osu: %s' % p, file=sys.stderr)
            return 1

    # 多输入: 先按歌分组。同一首歌的几张 -> 合成一个多难度 .tja(convert_multi);
    # 跨了多首歌 -> 每首歌各转一个(convert_batch)。
    if len(inputs) > 1:
        groups = group_by_song(inputs, not args.keep_original_names)
        if len(groups) > 1:
            return _cli_batch(inputs, args, shift_ms)
        return _cli_multi(inputs, args, shift_ms)

    src = inputs[0]
    # 输出路径: 未指定 -> 与输入同目录同名; -o 是目录 -> 放进该目录;
    # 只有明确给了 .tja/.osu 才算文件路径(判据见 _is_output_file)。
    stem = os.path.splitext(os.path.basename(src))[0] + '.tja'
    if not args.output:
        dst = os.path.join(os.path.dirname(os.path.abspath(src)), stem)
    elif _is_output_file(args.output):
        dst = args.output
    else:
        dst = os.path.join(args.output, stem)
    # 默认再套一层「曲名」文件夹, 让 .tja 与 .ogg 归到一首歌一个目录。
    dst, out_dir = output_paths(src, dst, song_folder=not args.flat,
                                title_opt=args.title,
                                allow_name_fallback=not args.keep_original_names)
    if out_dir and not os.path.isdir(out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            print('无法创建输出目录 %s: %s' % (out_dir, e), file=sys.stderr)
            return 1
    try:
        summary = convert(src, dst, args.encoding, args.course, args.level,
                          args.barline, args.subdiv, args.quiet, args.wave_ext,
                          copy_audio=not args.no_copy_audio,
                          red_grid=not args.no_red_snap,
                          offset_shift_ms=shift_ms,
                          demostart_s=args.demostart,
                          title_opt=args.title, artist_opt=args.artist,
                          allow_name_fallback=not args.keep_original_names,
                          trim_audio=not args.no_trim_audio,
                          trim_tail_ms=(args.trim_tail * 1000.0
                                        if args.trim_tail is not None else None))
    except Exception as e:
        print('转换失败: %s' % e, file=sys.stderr)
        return 1
    if summary.get('audio_error'):
        print('⚠ 音源没转成 OGG: %s' % summary['audio_error'], file=sys.stderr)
        return 1
    if args.quiet and summary.get('encoding_warning'):
        print('⚠ %s' % summary['encoding_warning'], file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
