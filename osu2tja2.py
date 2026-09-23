#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
osu2tja2 — osu!taiko (.osu, Mode=1) -> TJA 谱面转换器 (v1)

用法:
    python osu2tja2.py                        # 双击/直接运行 -> 弹窗选谱面 + 选输出文件夹
    python osu2tja2.py "谱面.osu"              # 命令行: 输出到谱面同目录同名 .tja
    python osu2tja2.py "谱面.osu" -o 输出目录/   # 命令行: 指定输出目录

图形界面会**记住上次选过的输出文件夹**: 下次弹窗直接停在那个文件夹, 选一下文件名就行。
（只记输出目录; 输入目录不记 —— 每次要转的谱面都在不同地方。想恢复初始状态用 `--forget-out-dir`。）

选项:
    -o, --output PATH    输出路径; 给目录(或不带扩展名的路径)则自动放进该目录,
                         父目录不存在会自动创建; 默认与输入同目录同名 .tja
    --gui                强制弹窗(即使已经写了输入文件)
    --encoding ENC       输出编码: cp932 (默认, 本家/日文模拟器惯例) | utf-8 | utf-8-sig
    --course NAME        强制 COURSE: Easy/Normal/Hard/Oni/Edit (默认按难度名推断)
    --level N            强制 LEVEL (默认按 COURSE 给一个常规值)
    --barline MODE       小节线: auto(默认)=照 osu 的 "Omit first bar line" 标记 | show | hide
    --subdiv N           基准「每拍格数」, 默认 4 (一格 = 1/4 拍, 本家最常用);
                         音符摆不下时自动升到 6/8/12/16/24 等
    --no-red-snap        关闭「红线网格还原」(默认开启, 不建议关)
    --wave-ext EXT       音源只认这个扩展名 (如 ogg); 缺省=优先用 .osu 的 AudioFilename,
                         找不到再自动扫文件夹; 限定不到任何文件时会退回自动找并提示
    --no-copy-audio      不把音源拷到输出文件夹 (默认会拷)
    --quiet              不打印摘要
    --forget-out-dir     忘掉图形界面记住的输出文件夹 (下次弹窗从头选)

音源处理（默认行为）:
    转换时会把这份谱面用的音源一并拷到输出文件夹，并让 TJA 的 WAVE 字段写上它的真实文件名，
    这样输出文件夹丢进模拟器就能直接出声，不用再手工配音频。
    挑哪一首音源: ① .osu 里 AudioFilename 点名的那个 → ② --wave-ext 限定的扩展名
    → ③ 自动扫文件夹（mp3/ogg 等压缩格式优先, 同格式挑体积最大的, .wav 垫底,
       免得把 osu 谱面里那些 soft-hitnormal.wav 之类的打击音当成歌曲）。
    输出文件夹就是谱面所在文件夹时, 不会重复拷; 已有一份内容完全相同的也不会再拷。
    WAVE 始终写「实际挑中的那个文件的真实名字」, 不会把 .mp3 改名成 .ogg 之类的假名字。

时间/位置换算（来源: 前人转换器 osu2tja.py 的 OFFSET 逻辑, 并与其产物逐首对齐数值）:
    OFFSET = -(谱面起点在音频里的位置, 秒) + 全局微调;  谱面起点 = min(第一条红线, 首个音符)。
    前人的等价写法: 若首个音符早于第一条红线, 就在该音符处补一条「合成红线」,
    OFFSET 取计时点列表第 0 项的负千分之一秒 —— 两种写法结果相同。
    于是 TJA 时间轴满足: 音频位置(秒) = 谱面时刻(秒) - OFFSET。
    注意: 早先用「本家 9 份谱面」反推 OFFSET 的做法**已作废** —— 那批 osu 谱与本家谱
    很可能用的不是同一份音源, 这两个 OFFSET 之间没有可比性。现在只以前人转换器为准
    (其 4 首产物在 基线转换结果/, 可逐首核对数值)。
    **全局微调(当前唯一一条 OFFSET 逻辑)**: 写出的 OFFSET 再整体减掉一个固定差值,
    当前是 **-85ms**(常数 `DEFAULT_OFFSET_SHIFT_MS`, 依据: 用户试玩两首谱面, 实测最好值
    分别比我们写的少 85ms 和 84ms, 一致)。它只改头部 `OFFSET:` 那一行, 不参与任何时刻换算,
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
    osu 的 SV 绿线                         -> #SCROLL (值 = 100/-beatLength)
    osu 的 Kiai 区段                       -> #GOGOSTART / #GOGOEND
    osu 的 BPM 红线                        -> #BPMCHANGE
"""
from __future__ import annotations

import argparse
import bisect
import filecmp
import json
import math
import os
import shutil
import subprocess
import sys
from fractions import Fraction

ONP_DON, ONP_KATSU, ONP_DON_DAI, ONP_KATSU_DAI = '1', '2', '3', '4'
ONP_RENDA, ONP_RENDA_DAI, ONP_BALLOON, ONP_END = '5', '6', '7', '8'

OSU_NOTE_CIRCLE, OSU_NOTE_SLIDER, OSU_NOTE_SPINNER = 1, 2, 8

EPS = 1e-6

# 音源候选扩展名, 顺序即「像不像歌曲」的优先级: 压缩格式在前, 未压缩的 .wav 垫底
# (osu 谱面文件夹里常有一堆 soft-hitnormal.wav 之类的打击音, 不能把它们当歌曲)
AUDIO_EXTS = ('.mp3', '.ogg', '.m4a', '.opus', '.aac', '.flac', '.wav')


# ---------------------------------------------------------------- 小工具

def read_text(path: str) -> str:
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-8', 'cp932'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def fnum(x: float, nd: int = 6) -> str:
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


# ---- 红线时刻的「网格还原」(默认开启) --------------------------------------
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
            out[-1] = (out[-1][0], msb, meter, omit)
            shifts.append(out[-1][0] - t)
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
    dai = bool(snd & 4)
    katsu = bool(snd & 10)          # whistle(2) 与 clap(8) 都算咔
    if dai:
        return ONP_KATSU_DAI if katsu else ONP_DON_DAI
    return ONP_KATSU if katsu else ONP_DON


def guess_course(version: str) -> str:
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


DEFAULT_LEVEL = {'Easy': 3, 'Normal': 5, 'Hard': 7, 'Oni': 10, 'Edit': 10}


# ---------------------------------------------------------------- 解析 .osu

class Timing:
    """osu 的 TimingPoints 时间轴: 红线(BPM/小节) + 绿线(SV) + Kiai"""

    def __init__(self):
        # (time:int, ms_per_beat:float, meter:int, omit:bool)
        # omit = osu 编辑器的 "Omit first bar line"(effects 的 bit3) -> TJA #BARLINEOFF
        self.reds = []
        self.greens = []    # (time:int, sv:float)
        self.kiais = []     # (time:int, kiai:bool)

    def msb_at(self, t: float):
        if not self.reds:
            raise ValueError('.osu 里没有任何红线(TimingPoints)，无法转换')
        cur = self.reds[0]
        for r in self.reds:
            if r[0] <= t + EPS:
                cur = r
            else:
                break
        return cur

    def sv_at(self, t: float) -> float:
        sv = 1.0
        for g in self.greens:
            if g[0] <= t + EPS:
                sv = g[1]
            else:
                break
        return sv

    def kiai_at(self, t: float) -> bool:
        k = False
        for x in self.kiais:
            if x[0] <= t + EPS:
                k = x[1]
            else:
                break
        return k


def parse_osu(path: str, red_grid: bool = True):
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
        if sec == 'General' or sec == 'Metadata' or sec == 'Difficulty':
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
        # Kiai 标记可以挂在任意 timing point 上
        if len(ps) > 7:
            try:
                timing.kiais.append((t, bool(int(float(ps[7])) & 1)))
            except ValueError:
                pass

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

    # --- 音符 ---
    # 这里先把时刻搬它所在红线段被挪动的量(_move), 后面所有判断(查 msb、查 SV、
    # 归位小节)都用搬过的时刻 —— 与已还原的红线/绿线保持同一套时间轴。
    circles, rolls, balloons = [], [], []
    for line in obj_lines:
        ps = line.split(',')
        if len(ps) < 4:
            continue
        try:
            t = _move(int(ps[2]))
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
                end = _move(int(ps[5]))
            except (IndexError, ValueError):
                end = t
            balloons.append({'t': t, 'end': max(end, t)})

    return {
        'meta': meta, 'diff': diff, 'timing': timing,
        'circles': circles, 'rolls': rolls, 'balloons': balloons,
        'slider_mult': slider_mult,
    }


# ---------------------------------------------------------------- 小节切分

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
# ⚠ 只有「SV 极密」的谱面才需要更细的格子 —— 4 首配对语料在这三档下总格数
#   完全不变, 一格都没多, 所以这个值不会动到已经对的谱面。
CMD_TOL_MS = 5.0

# 兜底加密时的硬上限(单个小节的格数)。本家语料里最密的小节是 1560 格,
# 这里留一倍余量。防止病态输入把一个小节撑到几万格。
FALLBACK_MAX_CELLS = 3072

# ---------------------------------------------------------------- OFFSET 常数
#
# ★ 当前 OFFSET 逻辑(2026-09-22 用户拍板, **就这一条, 刻意保持最简单**):
#
#       写出的 OFFSET = -谱面起点(秒) + DEFAULT_OFFSET_SHIFT_MS / 1000
#
#   也就是「照搬 osu 的谱面起点, 然后整体再减掉一个固定差值」。
#
#   为什么是 -85ms: 用户拿转换器转了几首歌, 在本家模拟器里自己听、自己调,
#   报回来两组数据 ——
#       第 1 首: 我们写 -194ms, 实际 -279ms 最好  -> 差 -85
#       第 2 首: 我们写 -200ms, 实际 -284ms 最好  -> 差 -84
#   两首一致, 取整为 **-85ms**(= 写出的 OFFSET 比原来小 0.085)。
#   用户明确要求: 先按这个最简逻辑走, 以后发现不对再回来优化。
#
# ⚠ 它是「模拟器与 osu 之间的系统差」, 不是精度问题 —— 所以是一个常数, 不是
#   按谱面算出来的量。正因为如此, 它必须**可关、可覆盖**:
#       --offset-shift 0        关掉(回到原样), 用于排查
#       --offset-shift <ms>     换成别的值
#   如果将来发现不同模拟器/设备需要的差值不同, 那是用户侧的判定线延迟, 不要
#   再往这个常数里塞更多逻辑。
DEFAULT_OFFSET_SHIFT_MS = -85.0


def build_bars(origin: float, end_time: float, timing: Timing, base: int = 4):
    """把 [origin, end_time] 切成小节, 返回 [bar, ...]。

    规则(用户 2026-09-21 确认, 已用 8 首本家谱面逐节交叉验证):
      * **每一条红线都是一个小节起点**, 不论 BPM 变没变 —— 这正是 osu 编辑器
        画小节线的规则; 照抄它, 本家的小节线才会和 osu 里看起来一样。
      * 一条红线给出的「标称小节长」= 它的 Meter 拍; 下一条红线把当前小节**截断**。
      * 红线 effects 的 bit3 (`& 8`) = 编辑器的 "Omit first bar line",
        输出 #BARLINEOFF(到下一条可见小节线再 #BARLINEON)。
      * 红线之间按 Meter 周期继续排自然小节, 直到下一条红线。

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
            bars.append({
                'start': s, 'end': e, 'beats': beats, 'msb': msb,
                'meter': float(meter), 'bpm': 60000.0 / msb, 'omit': bool(omit),
                # 压在小节开头那一瞬的绿线不能被边界误差吃掉, 所以往后取千分之一拍
                'scroll': timing.sv_at(s + msb * 1e-3),
                'kiai': timing.kiai_at(s + msb * 1e-3),
                'fragment': beats < meter - 1e-6,
                'cuts': [], 'events': [],
            })
    return bars


def _grid_fits(positions, n, cell, tol):
    """positions(单位: 拍) 能否都落在 0..n 号格点上(容差 tol 拍)。

    格号允许等于 n —— 那表示「正好压在小节末尾」, 输出时交给下一小节的第 0 格
    (等价于落在小节线上), 与音符的真实时刻误差为 0。
    """
    for p in positions:
        i = int(round(p / cell))
        i = 0 if i < 0 else (n if i > n else i)
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
    """
    conflict = 0
    prev_i = None
    for p in positions:
        i = int(round(p / cell))
        i = 0 if i < 0 else (n if i > n else i)
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
        i = int(round(p / cell))
        i = 0 if i < 0 else (n if i > n else i)
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
        i = int(round(p / cell))
        i = 0 if i < 0 else (n if i > n else i)
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
                i = int(round(p / cell))
                i = 0 if i < 0 else (n if i > n else i)
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
    for n in (n0, n0 * CMD_EXTRA_FACTOR, n0 * CMD_EXTRA_FACTOR * 2):
        cell = length / n
        if _cmd_collapse(cmd_pos, n, cell, ct) == 0:
            return (n / length if length else 1.0), n

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
        if _cmd_collapse(cmd_pos, n, cell, ct) == 0:
            return (n / length if length else 1.0), n
        k += 1

    # 命令点比格还密, 实在排不下 -> 用音符选的格宽, 由铺格那步按 round() 落格。
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
        if cur_sv is None or abs(sv - cur_sv) > 1e-9:
            if cur_sv is not None:
                cut_times.append(t)
            cur_sv = sv
        if cur_kiai is None or k != cur_kiai:
            if cur_kiai is not None:
                cut_times.append(t)
            cur_kiai = k
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


def plan_audio(src: str, dst_dir: str, wave_ext=None, meta=None) -> dict:
    """算出这个谱面的音源该怎么处理（只算, 不复制）。

    挑音源的优先级:
      1. .osu 里 AudioFilename 指名的那个文件（最准, 通常就是它）
      2. --wave-ext 限定的扩展名里, 挑最像歌曲的那个
      3. 直接扫文件夹, 挑最像歌曲的那个
    --wave-ext 限定不到任何文件时, 会退回不限定并记在 note 里, 不会让你拿到一个没有音源的谱面。

    返回 {'src','dst','wave','action','note'}:
      action = 'copy'    需要拷过去
               'same'    源和目标本来就是同一个文件（输出到谱面所在文件夹时）
               'exists'  目标已有内容完全相同的文件, 不用再拷
               'missing' 没找到音源, wave 里写的是兜底名字
    """
    folder = os.path.dirname(os.path.abspath(src))
    if meta is None:
        try:
            meta = parse_osu(src)['meta']
        except Exception:
            meta = {}
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
            if ext_want:
                note = '按 --wave-ext %s 挑了 %s' % (ext_want, picked)
            else:
                note = '%s 不在文件夹里, 按扩展名/体积挑了 %s' % (want or 'AudioFilename', picked)

    res = {'src': None, 'dst': None, 'wave': '', 'action': 'missing', 'note': ''}
    if not picked:
        res['wave'] = want or (os.path.splitext(os.path.basename(src))[0] + (ext_want or '.ogg'))
        res['note'] = note or '这份谱面所在的文件夹里没有音频文件'
        return res

    a_src = os.path.join(folder, picked)
    a_dst = os.path.join(dst_dir, picked)
    res['src'], res['dst'], res['wave'], res['note'] = a_src, a_dst, picked, note
    if os.path.normcase(os.path.abspath(a_src)) == os.path.normcase(os.path.abspath(a_dst)):
        res['action'] = 'same'
    elif os.path.exists(a_dst) and filecmp.cmp(a_src, a_dst, shallow=False):
        res['action'] = 'exists'
    else:
        res['action'] = 'copy'
    return res


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
    reds = timing.reds
    base = reds[0]
    for r in reds:
        if r[0] > t:
            break
        base = r
    msb = base[1]                       # 每拍毫秒
    delta = t - base[0]
    if abs(delta) < 1e-9:
        return base[0]
    sign = 1.0 if delta > 0 else -1.0
    units = round(abs(delta) / msb * 24.0)
    return base[0] + sign * units / 24.0 * msb


def convert(src: str, dst: str, encoding: str = 'cp932', course_opt=None,
            level_opt=None, barline: str = 'auto', base_subdiv: int = 4,
            quiet: bool = False, wave_ext=None,
            copy_audio: bool = True, red_grid: bool = True,
            offset_shift_ms: float = None) -> dict:
    """base_subdiv = **每拍最少格数**。默认 4 —— 这是本家谱面的主流写法
    (实测 8 首本家谱面 1113 个小节里「每拍 4 格」占 692 个)。

    ⚠ 不要随手调大: 它会把**每一个小节**的格数按倍数放大(12 → 每小节 48 格),
      预览里的排版立刻不像本家。这里的默认值曾经是 12, 交付目录被校验脚本
      用 12 覆盖过一次, 结果整批谱面都是「每拍 12 格」。

    offset_shift_ms = **全局 OFFSET 微调**(毫秒, 正数=写出的 OFFSET 变大)。
    `None`(默认) 表示用模块常数 `DEFAULT_OFFSET_SHIFT_MS`(当前 **-85ms**,
    见该常数的说明); 显式传 `0.0` 就是**不加偏移**。
    它**只改头部那一行 `OFFSET:` 的数值**, 不碰任何音符/小节/BPM 的时刻 ——
    等价于手工把 .tja 里的 `OFFSET` 改掉。它平移的是「音符+小节线」相对音频的
    **同一个**位移, 所以不会破坏任何内部相对关系(见模块头部的时间轴换算说明)。
    """
    if offset_shift_ms is None:
        offset_shift_ms = DEFAULT_OFFSET_SHIFT_MS
    data = parse_osu(src, red_grid=red_grid)
    meta, timing = data['meta'], data['timing']
    circles, rolls, balloons = data['circles'], data['rolls'], data['balloons']

    events = []
    for t, ch in circles:
        events.append((t, 'note', ch))
    for r in rolls:
        events.append((r['t'], 'roll_start', r['char']))
        events.append((r['end'], 'roll_end', ONP_END))
    for b in balloons:
        events.append((b['t'], 'balloon_start', ONP_BALLOON))
        events.append((b['end'], 'balloon_end', ONP_END))
    if not events:
        raise ValueError('这个 .osu 里没有任何可转换的音符')
    events.sort(key=lambda e: e[0])

    first_red = timing.reds[0][0]
    # 谱面起点(它决定写出的 OFFSET): 取「第一条红线」与「首个音符」的更早者,
    # 并按前人做法把首个音符吸附到 1/24 拍网格。
    # 前人在这种情况下会补一条「合成红线」放在首个音符处, 并把该音符也挪到起点;
    # 我们不挪音符, 所以吸附万一越过了首个音符, 就退回音符本身的时刻 ——
    # 保证不会有任何音符落在谱面起点之前。实测 8 首里两种写法取值完全相同。
    origin = min(first_red, snap_beat_24(events[0][0], timing))
    if origin > events[0][0]:
        origin = events[0][0]
    end_time = max(events[-1][0], first_red) + 1.0

    # 尾部: 最后一个音符之后「一个小节内」若还有计时点, 必须把它们包进来。
    # 最常见的就是最后一条 #GOGOEND —— 丢掉它, GOGO 状态会一直挂到谱面结束,
    # 演出和 osu/本家就不一致了(Irregular Clock: 末音符 137.10s, kiai 在 137.99s 才关,
    # 本家谱面也确实把这一下画了出来)。超过一个小节的计时点不再追(那是下一段的元数据)。
    _t_end = timing.msb_at(end_time)
    horizon = end_time + _t_end[1] * float(_t_end[2])
    _tail = [x[0] for x in timing.reds + timing.greens + timing.kiais
             if end_time < x[0] <= horizon]
    if _tail:
        end_time = max(_tail) + 1.0

    cut_times = timing_cuts(timing)
    bars = build_bars(origin, end_time, timing, base_subdiv)

    # ---- 命令点(SCROLL/GOGO)归位 ----
    # 必须按**未吸附的原始切点**取 SV/Kiai 值: 若按吸附后的时刻去查, 可能取到它自己
    # 那条绿线之前的值, 整条 SV 渐变就整体滞后一格(实测 People People 晚 130~260ms)。
    ci = 0
    for b in bars:
        while ci < len(cut_times) and cut_times[ci] < b['end'] - 1e-9:
            c = cut_times[ci]
            if c >= b['start'] - 1e-9:
                b['cuts'].append((c, timing.sv_at(c), timing.kiai_at(c)))
            ci += 1

    # ---- 音符归位 ----
    # 先按 [start, end) 归位; 若已经贴到下一条小节线(半个基础格以内), 就交给下一小节。
    # 真正「正好落在小节线上」由 choose_grid 允许的 0..N 号格 + carry 处理, 误差为 0。
    j = 0
    for ei, (t, kind, ch) in enumerate(events):
        while j + 1 < len(bars) and t >= bars[j]['end'] - 1e-9:
            j += 1
        bars[j]['events'].append((t, kind, ch, ei))

    # ---- 末小节: 长度对齐到 1/4 拍 + 留出安全余量 ----
    # 末小节不是由红线量出来的, 而是「最后一个音符之后补齐」算出来的, 长度里带着
    # 整数毫秒的取整噪声 —— 实测写出过 `#MEASURE 4001/4000`。它又是全谱唯一没有
    # 下一条红线来"截断"的小节, 所以必须在这里对齐。
    # 同时保证最后一个事件之后至少留半拍: 否则它会被挤到小节末尾的格号 N 上, 被当成
    # 「压在小节线上」而交给并不存在的下一小节, 最后退回 N-1 格(整格的时间误差)。
    if bars:
        _lb = bars[-1]
        _last = max((t for t, k, ch, ei in _lb['events']), default=_lb['start'])
        _step = _lb['msb'] * 0.25
        _need = (_last - _lb['start']) + _lb['msb'] * 0.5
        # 现有长度就近取整到 1/4 拍(把取整噪声抹掉), 再与"需要的最小长度"取大, 最后向上对齐
        _base = max(_need, round((_lb['end'] - _lb['start']) / _step) * _step)
        _L = math.ceil((_base - 1e-9) / _step) * _step          # 单位: 毫秒
        _lb['end'] = _lb['start'] + _L
        _lb['beats'] = _L / _lb['msb']

    # 生成每一行
    out_lines = []
    cur_bpm = cur_scroll = None
    cur_kiai = False
    cur_measure = None
    barline_off = False
    balloon_hits = []

    for b in bars:
        for t, kind, ch, ei in b['events']:
            if kind == 'balloon_start':
                for bb in balloons:
                    if bb['t'] == t:
                        balloon_hits.append(max(1, min(99, int(round((bb['end'] - bb['t']) / 100.0)))))
                        break

    grid_warn = 0
    carry = []
    for bi, b in enumerate(bars):
        L = b['beats']
        note_pos, fuzzy_pos = [], []
        for t, k, ch, ei in b['events']:
            (fuzzy_pos if k in ('roll_end', 'balloon_end') else note_pos).append(
                (t - b['start']) / b['msb'])
        cmd_pos = [(t - b['start']) / b['msb'] for t, sv, kiai in b['cuts']]
        D, N = choose_grid(L, note_pos, cmd_pos, b['msb'], base_subdiv,
                           fuzzy_pos=fuzzy_pos)
        b['D'], b['N'] = D, N
        cell = L / N
        if D > NICE_SUBDIV[-2]:
            grid_warn += 1

        n, d = beats_to_measure(L)
        cmds = []
        if cur_measure != (n, d):
            cmds.append('#MEASURE %d/%d' % (n, d))
            cur_measure = (n, d)
        if cur_bpm is None or abs(b['bpm'] - cur_bpm) > 1e-6:
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
                end = next(e['end'] for e in rolls if e['t'] == t)
                roll_spans.append((i, end))
            elif kind == 'balloon_start':
                end = next(e['end'] for e in balloons if e['t'] == t)
                roll_spans.append((i, end))
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

        # ---- 小节内部的命令分段: [(起始格, scroll, kiai), ...] ----
        # ⚠ 同一格的多条命令只有最后一条存活, 前一条被覆盖 = 它影响的音符用错流速。
        #   所以档位选择那一步 (_cmd_collapse) 会尽力保证命令点各占一格。
        segs = []
        for t, sv, kiai in [(b['start'], b['scroll'], b['kiai'])] + list(b['cuts']):
            i = int(round((t - b['start']) / b['msb'] / cell))
            if i > N:
                continue
            i = max(0, i)
            if segs and segs[-1][0] == i:
                segs[-1] = (i, sv, kiai)
            else:
                segs.append((i, sv, kiai))
        if not segs:
            segs = [(0, b['scroll'], b['kiai'])]

        if not b['events'] and not any(slots):
            # 空小节: 没有中途命令就直接写 ','; 有命令点才写占位字符(命令靠字符定位)
            slots = [] if len(segs) == 1 else ['0'] * N

        # ---- 按分段输出(段间插命令, 只有最后一段带逗号) ----
        for si, (i0, sv, kiai) in enumerate(segs):
            i1 = segs[si + 1][0] if si + 1 < len(segs) else N
            if cur_scroll is None or abs(sv - cur_scroll) > 1e-9:
                out_lines.append('#SCROLL %s' % fnum(sv))
                cur_scroll = sv
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


    # ---------------------------------------------------------- 头部
    title = meta.get('TitleUnicode') or meta.get('Title') or 'Untitled'
    artist = meta.get('ArtistUnicode') or meta.get('Artist') or ''
    version = meta.get('Version') or ''
    course = course_opt or guess_course(version)
    level = level_opt if level_opt is not None else DEFAULT_LEVEL.get(course, 8)
    bpm0 = 60000.0 / timing.reds[0][1]
    try:
        preview = int(float(meta.get('PreviewTime', -1)))
    except ValueError:
        preview = -1

    # WAVE: 写「实际挑中的那个音源文件的真实文件名」, 和转换时一并拷过去的那份对得上。
    plan = plan_audio(src, os.path.dirname(os.path.abspath(dst)), wave_ext, meta)
    wave = plan['wave']

    # 写出的 OFFSET = 谱面起点(取负) + 全局微调(默认 -85ms)。
    # ⚠ 这是转换器里**唯一**允许动 OFFSET 的地方; 微调只改这一个数, 不参与任何时刻换算。
    off_written = -origin / 1000.0 + offset_shift_ms / 1000.0

    head = [
        'TITLE:%s' % title,
        'SUBTITLE:--%s' % artist,
        'BPM:%s' % fnum(bpm0),
        'WAVE:%s' % wave,
        'OFFSET:%.3f' % off_written,
        'DEMOSTART:%.3f' % (max(0, preview) / 1000.0),
        'SONGVOL:100',
        'SEVOL:100',
        'SCOREMODE:2',
        '//Converted from "%s" by osu2tja2' % os.path.basename(src),
        '',
        'COURSE:%s' % course,
        'LEVEL:%d' % level,
        'BALLOON:%s' % ','.join(str(x) for x in balloon_hits),
        '',
        '#START',
    ]

    text = '\r\n'.join(head + out_lines) + '\r\n'
    with open(dst, 'wb') as f:
        f.write(text.encode(encoding, errors='replace'))

    # 把音源一并拷到输出文件夹（WAVE 已经写成它的真实文件名）
    copied, audio_error, audio_skipped = False, '', False
    if plan['action'] == 'copy':
        if copy_audio:
            try:
                os.makedirs(os.path.dirname(plan['dst']), exist_ok=True)
                shutil.copy2(plan['src'], plan['dst'])
                copied = True
            except OSError as e:
                audio_error = str(e)
        else:
            audio_skipped = True

    summary = {
        'src': src, 'dst': dst, 'course': course, 'level': level,
        'circles': len(circles), 'rolls': len(rolls), 'balloons': len(balloons),
        'bars': len(bars), 'fragments': sum(1 for b in bars if b['fragment']),
        'bpm_changes': sum(1 for b in bars if abs(b['bpm'] - bpm0) > 1e-6),
        'wave': wave, 'audio_src': plan['src'], 'audio_dst': plan['dst'],
        'audio_action': plan['action'], 'audio_copied': copied,
        'audio_skipped': audio_skipped,
        'audio_error': audio_error, 'audio_note': plan['note'],
        'origin_ms': origin, 'offset_written': off_written,
        'offset_shift_ms': offset_shift_ms,
    }
    if not quiet:
        print('输入: %s' % src)
        print('输出: %s  [%s]' % (dst, encoding))
        print('  咚/咔/大音符 %d 条 | 连打 %d 条 | 气球 %d 个 | 小节 %d 个 (其中被切开的 %d 个)'
              % (summary['circles'], summary['rolls'], summary['balloons'],
                 summary['bars'], summary['fragments']))
        print('  OFFSET: %.3f  (谱面起点 %d ms%s)'
              % (off_written, origin,
                 '' if not offset_shift_ms else
                 ' + 全局微调 %+g ms' % offset_shift_ms))
        print('  音源: %s' % audio_report(summary))
    return summary


def audio_report(summary: dict) -> str:
    """把音源的处理结果写成一句人话 —— 命令行和弹窗共用, 保证两处说法一致。"""
    action = summary['audio_action']
    if action == 'copy':
        if summary['audio_copied']:
            return '%s -> 已拷到输出文件夹' % summary['wave']
        if summary.get('audio_skipped'):
            return '%s -> 没有拷贝（按 --no-copy-audio）' % summary['wave']
        return '%s -> 没拷成（%s）' % (summary['wave'], summary['audio_error'] or '原因不明')
    if action == 'exists':
        return '%s -> 输出文件夹里已有一份完全相同的, 不用再拷' % summary['wave']
    if action == 'same':
        return '%s -> 谱面和音源本来就在同一个文件夹, 无需拷贝' % summary['wave']
    return '没找到音源（%s）; WAVE 里写的仍是 %s' % (summary['audio_note'], summary['wave'])


# ---------------------------------------------------------------- 图形界面

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


# ------------------------------------------------- 记住上次用过的输出文件夹
# 给图形界面用: 双击进来的用户, 转出来的 .tja 总是堆在同一个文件夹里, 不想每次重选。
#   * 只记**输出**文件夹。**输入**文件夹故意不记 —— 每次要转的谱面都在不同地方,
#     记了反而每次都要先绕回旧目录再导航走。
#   * 配置文件坏了 / 写不进去(只读目录、权限) 一律当没有, **绝不让它影响转换本身**。
CONFIG_PATH = os.path.join(
    os.environ.get('APPDATA') or os.path.expanduser('~'),
    'osu2tja2', 'config.json')


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


def gui_flow(ask_file, ask_dir, ask_yes, error, output_hint=None,
             base_subdiv: int = 4, red_grid: bool = True,
             offset_shift_ms: float = None, info=None,
             open_output_dir: bool = False) -> int:
    """图形界面的流程主体。

    所有交互都通过外部注入的回调完成, 这样这段逻辑可以脱离 tkinter 单独测试:
        ask_file()           -> 选输入 .osu, 返回路径, 取消返回 ''
        ask_dir(initialdir)  -> 选输出文件夹, 取消返回 ''
        ask_yes(title, text) -> 是/否
        error(title, text)   -> 报错
        info(title, text)    -> 只通知、不需回答(缺省退回 print)
        output_hint          -> 命令行已用 -o 指定过输出时, 就不再问文件夹
        open_output_dir      -> 转换完是否顺手打开输出文件夹。默认 False:
                                转完只弹一条结果提示, 不问、不打开。
    """
    src = ask_file()
    if not src:
        print('已取消。')
        return 0
    if not os.path.isfile(src):
        error('文件不存在', '找不到这个文件：\n%s' % src)
        return 1
    if not src.lower().endswith('.osu'):
        error('文件类型不对', '请选择 .osu 谱面文件：\n%s' % os.path.basename(src))
        return 1

    dst = None
    if output_hint:
        hint = output_hint.rstrip('/\\')
        if os.path.isdir(hint) or '.' not in os.path.basename(hint):
            dst_dir = output_hint
        else:
            # -o 给了具体文件名: 按名字写, 目录取它所在的那一层
            dst_dir = os.path.dirname(os.path.abspath(hint))
            if hint.lower().endswith('.tja'):
                dst = hint
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

    if dst is None:
        dst = os.path.join(dst_dir, os.path.splitext(os.path.basename(src))[0] + '.tja')

    # 会被写进去的东西: 谱面 .tja + 顺带拷过去的音源。先把会被覆盖的列出来问一次。
    overwrite = []
    if os.path.exists(dst):
        overwrite.append(os.path.basename(dst))
    plan = plan_audio(src, dst_dir)
    if plan['action'] == 'copy' and os.path.exists(plan['dst']):
        overwrite.append(os.path.basename(plan['dst']))
    if overwrite and not ask_yes(
            '同名文件已存在',
            '这个文件夹里已经有同名文件：\n  %s\n\n要覆盖吗？' % '\n  '.join(overwrite)):
        print('已取消（未覆盖）: %s' % dst)
        return 0

    try:
        summary = convert(src, dst, 'cp932', None, None, 'auto', base_subdiv, False,
                          red_grid=red_grid, offset_shift_ms=offset_shift_ms)
    except Exception as e:
        error('转换失败', '%s: %s' % (type(e).__name__, e))
        return 1

    # 转完只报结果, 不问「要不要打开文件夹」; 想打开得显式要求(--open-out-dir)。
    done_text = (
        '转换完成\n\n'
        '输出谱面：\n%s\n'
        '输出音源：%s\n\n'
        '音符 %d 条 ｜ 连打 %d 条 ｜ 气球 %d 个\n'
        '小节 %d 个（其中被切开的 %d 个）'
        % (dst, audio_report(summary), summary['circles'], summary['rolls'],
           summary['balloons'], summary['bars'], summary['fragments']))
    if info is not None:
        info('转换完成', done_text)
    else:
        print(done_text)
    if open_output_dir:
        open_folder(dst_dir)
    return 0


def run_gui(output_hint=None, red_grid: bool = True,
            offset_shift_ms: float = None,
            open_output_dir: bool = False) -> int:
    """弹出图形选择框: 先选 .osu, 再选输出文件夹, 然后转换。

    输出文件夹会记住上次的选择(见 remembered_out_dir), 输入文件不记。
    转换完成后只弹一条结果提示, 不询问是否打开输出文件夹;
    要它顺手打开就传 open_output_dir=True。
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception as e:
        print('这个 Python 里没有 tkinter, 用不了图形界面 (%s)' % e, file=sys.stderr)
        print('请改用命令行: python osu2tja2.py "谱面.osu" -o 输出目录', file=sys.stderr)
        return 1

    root = tk.Tk()
    root.withdraw()                             # 只借它当对话框的宿主, 不显示主窗口
    try:
        root.attributes('-topmost', True)       # 让选择框浮到最前面
    except tk.TclError:
        pass
    root.update()

    def ask_file():
        return filedialog.askopenfilename(
            parent=root,
            title='第 1 步 / 共 2 步 — 选择要转换的 osu!taiko 谱面 (.osu)',
            filetypes=[('osu! 谱面 (*.osu)', '*.osu'), ('所有文件', '*.*')])

    def ask_dir(initialdir):
        # 弹窗停在上次用过的输出文件夹; 选完立刻记下来, 下次直接用它开框。
        picked = filedialog.askdirectory(
            parent=root,
            title='第 2 步 / 共 2 步 — 选择存放 .tja 的文件夹',
            initialdir=remembered_out_dir(initialdir), mustexist=False)
        if picked:
            save_config(out_dir=os.path.abspath(picked))
        return picked

    def ask_yes(title, text):
        return bool(messagebox.askyesno(title, text, parent=root))

    def info(title, text):
        messagebox.showinfo(title, text, parent=root)

    def error(title, text):
        print('%s: %s' % (title, text), file=sys.stderr)
        messagebox.showerror(title, text, parent=root)

    try:
        return gui_flow(ask_file, ask_dir, ask_yes, error, output_hint,
                        red_grid=red_grid, offset_shift_ms=offset_shift_ms,
                        info=info, open_output_dir=open_output_dir)
    finally:
        root.destroy()


# ---------------------------------------------------------------- 命令行

def main():
    ap = argparse.ArgumentParser(add_help=True, description='osu!taiko -> TJA 转换器')
    ap.add_argument('input', nargs='?', default=None,
                    help='输入的 .osu 文件; 不写这个参数就弹出图形选择框')
    ap.add_argument('-o', '--output', default=None,
                    help='输出 .tja 路径; 给目录则自动放进该目录; 缺省=与输入同目录同名')
    ap.add_argument('--encoding', default='cp932', choices=['cp932', 'utf-8', 'utf-8-sig'])
    ap.add_argument('--course', default=None, choices=['Easy', 'Normal', 'Hard', 'Oni', 'Edit'])
    ap.add_argument('--level', type=int, default=None)
    ap.add_argument('--barline', default='auto', choices=['auto', 'show', 'hide'],
                    help='小节线: auto(默认)=照 osu 的 "Omit first bar line" 标记 | show=全画 | hide=全隐藏')
    ap.add_argument('--subdiv', type=int, default=4,
                    help='基准「每拍格数」, 默认 4(本家最常用: 一格=1/4 拍); '
                         '音符摆不下时会自动升到 6/8/12/16/24 等, 一般不用改')
    ap.add_argument('--wave-ext', default=None,
                    help='音源只认这个扩展名(如 ogg); 缺省=优先用 .osu 的 AudioFilename, 找不到再自动扫')
    ap.add_argument('--no-copy-audio', action='store_true',
                    help='不把音源拷到输出文件夹(默认会拷, 并让 WAVE 用它的真实文件名)')
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
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--forget-out-dir', action='store_true',
                    help='忘掉图形界面记住的输出文件夹(下次弹窗从头选)。'
                         '只清这一项, 不影响别的设置')
    ap.add_argument('--open-out-dir', action='store_true',
                    help='转换完成后顺手打开输出文件夹(默认不打开、也不询问)')
    ap.add_argument('--gui', action='store_true', help='强制弹窗选择(即使已经写了输入文件)')
    args = ap.parse_args()

    if args.forget_out_dir:
        save_config(out_dir='')
        print('已忘掉记住的输出文件夹（下次弹窗会从头选）')
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
                       open_output_dir=args.open_out_dir)

    if not os.path.isfile(args.input):
        print('找不到输入文件: %s' % args.input, file=sys.stderr)
        return 1
    if not args.input.lower().endswith('.osu'):
        print('输入文件应当是 .osu', file=sys.stderr)
        return 1

    # 输出路径: 未指定 -> 与输入同目录同名; -o 是目录(或未带扩展名) -> 放进该目录; 否则按给定路径
    stem = os.path.splitext(os.path.basename(args.input))[0] + '.tja'
    if not args.output:
        dst = os.path.join(os.path.dirname(os.path.abspath(args.input)), stem)
    elif os.path.isdir(args.output) or '.' not in os.path.basename(args.output.rstrip('/\\')):
        dst = os.path.join(args.output, stem)
    else:
        dst = args.output
    parent = os.path.dirname(os.path.abspath(dst))
    if parent and not os.path.isdir(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            print('无法创建输出目录 %s: %s' % (parent, e), file=sys.stderr)
            return 1
    try:
        convert(args.input, dst, args.encoding, args.course, args.level,
                args.barline, args.subdiv, args.quiet, args.wave_ext,
                copy_audio=not args.no_copy_audio,
                red_grid=not args.no_red_snap,
                offset_shift_ms=shift_ms)
    except Exception as e:
        print('转换失败: %s' % e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
