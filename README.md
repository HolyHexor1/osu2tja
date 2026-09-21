# osu2tja

Convert **osu!taiko** beatmaps (`.osu`, `Mode: 1`) into **Taiko TJA** charts, for simulators such as
**OpenTaiko / TaikoJiro**.

It aims for a faithful conversion, not a lossy one: note types, note timings, BPM changes and
scroll speed (SV) are reconstructed on a clean TJA grid instead of dumping raw milliseconds
straight out of the osu file.

## Features

- **Note conversion** — circles / sliders / spinners map to `1 2 3 4` (don / ka, big / small),
  rolls (`5`/`6` … `8`) and balloons (`7` … `8`).
- **Red-line (BPM / time signature) grid restoration** — osu stores timing points as integer
  milliseconds, which produces absurd measures like `#MEASURE 167999/168041`. They are chained back
  onto the 1/4-beat grid, so measures come out as `16`, `4`, `8` … instead.
- **Green-line (SV) → `#SCROLL`** — scroll changes are placed on the grid so that the scroll speed
  *in effect at each note* matches the osu original.
- **GOGO time** from osu kiai sections, **bar lines** from the "omit first bar line" flag.
- **Audio handling** — the song file used by the beatmap is copied next to the output chart, and
  `WAVE` is written with its real file name, so the folder can be dropped straight into a simulator.
- **GUI or CLI** — double-click to get file dialogs, or run it as a normal command line tool.
- **No dependencies** — standard library only (Python 3.8+).

## Requirements

- Python 3.8 or newer.
- `tkinter` only if you want the graphical file pickers (optional for CLI use).

## Usage

Graphical (no arguments):

```
python osu2tja2.py
```

Command line:

```
python osu2tja2.py "beatmap.osu"              # -> beatmap.tja next to it
python osu2tja2.py "beatmap.osu" -o out_dir/  # -> out_dir/beatmap.tja
```

Useful options:

| Option | Meaning |
| --- | --- |
| `-o, --output PATH` | Output file or folder (created if missing). |
| `--encoding ENC` | `cp932` (default, the usual convention), `utf-8`, `utf-8-sig`. |
| `--course NAME` | Force `Easy / Normal / Hard / Oni / Inner Oni` (otherwise inferred from the difficulty name). |
| `--level N` | Force the `LEVEL` value. |
| `--barline MODE` | `auto` (default, follows osu's omit-bar-line flag), `show`, `hide`. |
| `--subdiv N` | Base cells per beat (default `4`); raised automatically when notes need it. |
| `--offset-shift MS` | Shift the written `OFFSET` by MS milliseconds (`--offset-shift 0` disables the trim). |
| `--no-copy-audio` | Do not copy the audio file into the output folder. |
| `--no-red-snap` | Disable red-line grid restoration (kept for comparison only). |
| `--forget-out-dir` | Forget the remembered output folder used by the GUI. |

## Note mapping

| osu!taiko hitsound | TJA |
| --- | --- |
| no whistle / clap, no finish | `1` — small don |
| whistle (`2`) or clap (`8`) | `2` — small ka |
| finish (`4`) | `3` — big don |
| finish (`4`) + whistle / clap | `4` — big ka |
| slider | `5` … `8` (roll, `6` when its head has a finish) |
| spinner | `7` … `8` (balloon) |

## Notes and limitations

- Converted from osu data only. Very dense scroll (SV) sections may need extra grid cells; notes and
  BPM are never sacrificed for that.
- osu records note positions in milliseconds while TJA places notes on musical cells. Where the two
  cannot agree exactly, the note lands on the cell implied by its BPM and rhythm pattern — that is
  the intended behaviour, not a rounding error.
- This project contains **no beatmaps and no audio**. Please do not redistribute other people's
  charts or songs with it.

## Acknowledgements

The `OFFSET` convention follows the earlier `osu2tja` converter (offset = minus the position of the
first timing point or note). Only the idea is reused here — that project's code is **not** included
in this repository.

## Author

TakanashiR — [github.com/HolyHexor1](https://github.com/HolyHexor1)

## License

MIT — see [LICENSE](LICENSE).

---

## 中文说明

osu!taiko 谱面（`.osu`，`Mode: 1`）→ 本家 TJA 谱面转换器，面向 OpenTaiko / OpenTycho 等模拟器。

目标不是"能出个文件"，而是**忠实还原**：音符种类与位置、BPM 变化的数值与位置、流速变化
（osu 绿线 SV → TJA `#SCROLL`）都会被重建到干净的 TJA 网格上，而不是把 osu 的毫秒值原样倒出来。

- **红线（BPM / 拍号）网格还原**：osu 的计时点是整数毫秒，直接换算会写出 `#MEASURE 167999/168041`
  这种畸形分数；转换时会把它们链式还原到 1/4 拍网格，小节分母降到 `16 / 4 / 8` 这种正常值。
- **音符映射**：`1` 小咚 `2` 小咔 `3` 大咚 `4` 大咔，滑条 → 连打 `5`/`6` … `8`，转盘 → 气球 `7` … `8`；
  kiai 区 → `#GOGOSTART/#GOGOEND`；osu 的 "omit first bar line" → `#BARLINEOFF`。
- **音源**：默认把谱面用的音源一并拷到输出文件夹，`WAVE` 写真实文件名，整个文件夹可直接丢进模拟器。
- **用法**：不给参数 = 弹窗选谱面；`python osu2tja2.py "谱面.osu" -o 输出目录/` = 命令行。
  图形界面会记住上次的输出文件夹。
- **依赖**：纯标准库，Python 3.8+ 即可，不需要 `pip install`（只有图形界面需要 `tkinter`）。
- 本仓库**不包含任何谱面与音频**，请勿用它再分发他人的谱面或歌曲。
- `OFFSET` 的写法沿用早先那个 `osu2tja` 转换器的约定（偏移 = 减去首个计时点或首个音符的位置）。
  这里只借鉴了思路，**没有**收录那个项目的代码。
- 作者：TakanashiR（GitHub: [HolyHexor1](https://github.com/HolyHexor1)）
