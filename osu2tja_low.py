# -*- coding: utf-8 -*-
"""osu2tja 低难版 —— osu!taiko（.osu, Mode=1）-> TJA，难度「从鬼往下填」。

和难谱版 ``osu2tja2.py`` 是**同一份转换逻辑**（音符种类/位置、BPM、流速、小节网格、
音源、命名、批量全都不变），唯一区别是启动时把难度方案切成 ``low``：

    1 张 -> 鬼
    2 张 -> 鬼 / 困难
    3 张 -> 鬼 / 困难 / 普通
    4 张 -> 鬼 / 困难 / 普通 / 简单
    5 张 -> 里 / 鬼 / 困难 / 普通 / 简单     （= 模拟器能认的全部 5 档）

星数高的那张永远是更高的难度名（同星数才问先后），和难谱版一致。

用法与难谱版完全相同：
    双击 osu2tja2-low.bat                  # 图形界面（选谱面 -> 选输出文件夹）
    py osu2tja_low.py a.osu b.osu -o 目录   # 命令行多难度
    py osu2tja_low.py --help                # 看全部参数

⚠ 两种版本**共用**输出文件夹记忆（``%APPDATA%\\osu2tja2\\config.json``），换版本不用重选。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import osu2tja2 as core            # noqa: E402  (要先改 sys.path 才能 import)

core.set_profile('low')
core.LAUNCHER_BAT = 'osu2tja2-low.bat'
core.SCRIPT_NAME = 'osu2tja_low.py'


if __name__ == '__main__':
    sys.exit(core.main())
