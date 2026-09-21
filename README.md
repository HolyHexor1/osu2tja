# osu2tja

Convert **osu!taiko** beatmaps (`.osu` with `Mode: 1`) into **TJA** charts for Taiko no Tatsujin
simulators such as **OpenTaiko**, **TJAPlayer3**, **TaikoJiro (太鼓次郎)** and their derivatives.

The goal is a *faithful* conversion, not a lossy dump: note types, note positions, BPM changes and
scroll speed are **reconstructed on a clean musical grid**, matching how TJA charts are actually
written by hand.

```
python osu2tja2.py "beatmap.osu" -o out/
```

- No dependencies — Python 3.8+ standard library only.
- GUI (double-click) or CLI.
- Reports its own verification results while converting.

---

## Why a converter at all?

Several simulators (OpenTaiko, TJAPlayer3, TaikoJiro) read TJA, not `.osu`. Some also read `.osu`
directly — but not all of them, not all features, and osu's own visual logic (scroll speed, bar
lines) is not what a Taiko sim expects.

## Why not simply dump osu's milliseconds?

Because a TJA chart is not a list of timestamps — it is **a musical score**. Notes live on cells
inside measures; measures are divided by `#MEASURE`; tempo is carried by `BPM` / `#BPMCHANGE`; and
scroll speed is a pure visual multiplier (`#SCROLL`).

osu, by contrast, records every object as an integer millisecond and lets a timing-point list imply
everything else. Converted naively, that produces files that technically play but do not behave like
a real chart — for example:

| naive conversion | what this tool writes |
| --- | --- |
| `#MEASURE 167999/168041` (from integer-ms timing points) | `#MEASURE 4/4`, `16`, `8` … |
| every note on a private 1/1000-beat grid | notes classified into the rhythm pattern (1/4, 1/3, 1/6, 1/8, 1/12, 1/16 beat) implied by the BPM in effect |
| `#SCROLL` values written wherever the osu green line happened to sit | `#SCROLL` placed so that the scroll speed **in effect at each note** matches osu |

So the converter's real job is to decide, for each note, **which BPM and which rhythm pattern it
belongs to** — and then write the chart the way a human charter would.

## Requirements

- Python 3.8 or newer.
- `tkinter` — only for the graphical file pickers (optional; the CLI does not need it).

Nothing to install: no `pip install`, no third-party packages, no network access.

## Usage

**Graphical** — double-click `osu2tja2.bat`, or run with no arguments:

```
python osu2tja2.py
```

Pick an `.osu` file, pick an output folder, done. The output folder is remembered between runs;
the input file is never remembered.

**Command line**

```
python osu2tja2.py "beatmap.osu"                  # -> beatmap.tja next to the input
python osu2tja2.py "beatmap.osu" -o out/          # -> out/beatmap.tja
python osu2tja2.py "beatmap.osu" -o out/ --course Oni --level 10
```

### Options

| Option | Meaning |
| --- | --- |
| `-o, --output PATH` | Output `.tja` path, or a directory to write into (created if missing). Default: next to the input file. |
| `--encoding ENC` | Output encoding: `cp932` (default — the usual convention for Japanese simulators), `utf-8`, `utf-8-sig`. |
| `--course NAME` | Force `COURSE`: `Easy` / `Normal` / `Hard` / `Oni` / `Edit`. Default: inferred from the osu difficulty name. |
| `--level N` | Force the `LEVEL` value. Default: a conventional value for the course. |
| `--barline MODE` | `auto` (default — follows osu's "Omit first bar line" flag), `show` (always draw), `hide`. |
| `--subdiv N` | Base cells per beat, default `4` (one cell = a 1/4 beat, the most common TJA convention). Raised automatically (6 / 8 / 12 / 16 / 24) when a section needs finer cells. |
| `--wave-ext EXT` | Only accept this audio extension (e.g. `ogg`) when looking for the song file. |
| `--no-copy-audio` | Do not copy the audio file into the output folder. |
| `--offset-shift MS` | Shift the written `OFFSET` by MS milliseconds (positive = larger OFFSET). Touches only the `OFFSET:` header line — notes, measures and BPM are never affected. |
| `--no-offset-shift` | Equivalent to `--offset-shift 0`: use the raw osu chart origin with no trim. |
| `--no-red-snap` | Disable timing-point grid restoration. Kept for comparison/debugging only. |
| `--quiet` | Less console output. |
| `--gui` | Force the dialog even when an input file was given. |
| `--forget-out-dir` | Forget the output folder remembered by the GUI (clears that one setting). |
| `--open-out-dir` | Open the output folder when finished. Off and not prompted by default. |

## Conversion reference

### Hit objects

osu!taiko has three object types; all three map onto TJA note characters.

| osu object | TJA |
| --- | --- |
| hit circle | `1` / `3` — don (small / big) |
| slider (drumroll) | `5` … `8` — roll; `6` when the head carries a finish |
| spinner (denden) | `7` … `8` — balloon |

### Hitsounds

osu stores sound as a **bitmask**: `1` normal, `2` whistle, `4` finish, `8` clap. In Taiko, whistle
and clap both mean *rim* (ka), and finish means *big*.

| osu hitsound | TJA |
| --- | --- |
| (no whistle, no clap, no finish) | `1` — small don |
| whistle `2` and/or clap `8` | `2` — small ka |
| finish `4` | `3` — big don |
| finish `4` + whistle/clap | `4` — big ka |

### Timing points and effects

| osu | TJA |
| --- | --- |
| uninherited ("red") timing point — BPM | `BPM:` header and `#BPMCHANGE` |
| red timing point — `meter` (beats per measure) | `#MEASURE n/d` |
| inherited ("green") timing point — slider velocity | `#SCROLL 100 / (−beatLength)` |
| `effects` bit 0 — kiai time | `#GOGOSTART` / `#GOGOEND` |
| `effects` bit 3 — omit first bar line | `#BARLINEOFF` / `#BARLINEON` |

### Chart headers

`TITLE`, `SUBTITLE`, `BPM`, `WAVE`, `OFFSET`, `DEMOSTART`, `SONGVOL`, `SEVOL`, `SCOREMODE`,
`COURSE`, `LEVEL`, `BALLOON`, plus a `//Converted from "…"` comment line.

### Course inference

`COURSE` is guessed from the osu difficulty name, following the five difficulty slots Taiko games
use:

| osu difficulty name contains | `COURSE` | Slot |
| --- | --- | --- |
| `Easy`, `Kantan`, 簡単 | `Easy` | Easy |
| `Normal`, `Futsuu`, 普通 | `Normal` | Normal |
| `Hard`, `Muzukashii`, 難しい | `Hard` | Hard |
| `Oni`, 鬼 | `Oni` | Oni |
| `Inner Oni`, `Ura`, `Edit`, 裏 | `Edit` | Inner Oni / Ura |

In TJA, the fifth slot (`Inner Oni`, also called `Ura Oni`) is written as `COURSE:Edit` (= `4`).
Override with `--course` if the guess is wrong.

### Audio

The song file referenced by the beatmap is copied next to the output chart and `WAVE` is written
with its **real** file name, so the resulting folder can be dropped straight into a simulator's song
directory. Use `--no-copy-audio` to skip the copy.

## Known limitations

- **Not every sub-millisecond detail survives — on purpose.** osu stores positions in milliseconds;
  TJA places notes on musical cells. When the two cannot agree exactly, the note lands on the cell
  implied by its BPM and rhythm pattern. This is the intended behaviour, not a rounding error.
- **Scroll speed (SV) is visual only.** It affects how the chart looks, not when notes must be hit.
  Dense SV sections may need extra cells in a measure; notes and BPM are never sacrificed for that.
- **Timing-point grid restoration shifts absolute positions slightly** (accumulated integer-ms
  rounding, well under one beat). Relative rhythm — the spacing between notes — is preserved.
- Converted from osu data only; osu-specific metadata that has no TJA equivalent is dropped.

## Compatibility

TJA output is plain text and is intended for:

- **OpenTaiko** — the most accessible modern simulator.
- **TJAPlayer3** and its forks (`TJAPlayer3-Develop-ReWrite`, `TJAPlayer3-f`, …).
- **TaikoJiro (太鼓次郎)** and its derivatives (太鼓さん大次郎, …).
- **taiko-web** and other TJA readers.

If a simulator rejects a file, please include the simulator name and version in the report — TJA
dialects differ in small ways.

## Credits

- The `OFFSET` convention follows the earlier `osu2tja` converter (offset = minus the position of
  the first timing point or note). Only the idea is reused here; that project's code is **not**
  included in this repository.
- Thanks to the Taiko simulator community for documenting the TJA format.

## How this was built

This converter was developed with heavy AI assistance. The author defined the conversion
requirements and the verification criteria, tested the output in Taiko simulators, and validated it
note by note against the original osu! beatmaps. Code was written with an AI assistant.

## Author

TakanashiR — [github.com/HolyHexor1](https://github.com/HolyHexor1)

## License

MIT — see [LICENSE](LICENSE).

---

## 中文说明

osu!taiko 谱面（`.osu`，`Mode: 1`）→ 太鼓本家 TJA 谱面转换器，面向 **OpenTaiko**、**TJAPlayer3**、
**太鼓次郎（TaikoJiro）** 等太鼓模拟器。

目标不是"能出个文件"，而是**忠实还原**：音符种类与位置、BPM 变化的数值与位置、流速变化
（osu 绿线 SV → TJA `#SCROLL`）都会被重建到干净的谱面网格上，而不是把 osu 的毫秒值原样倒出来。

**为什么不能直接把毫秒倒出来**：TJA 谱面本质是一份**乐谱**——音符落在小节里的格子上，小节由
`#MEASURE` 划分，速度由 `BPM`/`#BPMCHANGE` 决定，`#SCROLL` 只影响视觉滚动速度。而 osu 只用整数
毫秒记录位置，其余靠计时点推导。直译出来的文件"能播"但不像人写的谱面：会出现
`#MEASURE 167999/168041` 这种畸形分数。所以转换的核心是**判断每个音符属于哪个 BPM 下的哪个节奏型**
（1/4、1/3、1/6、1/8、1/12、1/16 拍），再按人写谱的方式排出来。

### 主要还原点

- **音符**：`1` 小咚 `2` 小咔 `3` 大咚 `4` 大咔；滑条 → 连打 `5`/`6` … `8`；转盘 → 气球 `7` … `8`。
- **判定音映射**：osu 的判定位掩码 `1` 普通 / `2` 哨声 / `4` 重音 / `8` 拍手；太鼓里哨声与拍手
  都算**咔**（鼓边），重音算**大**。
- **红线（BPM / 拍号）网格还原**：链式还原到 1/4 拍网格，小节分母从六位数降到 `16 / 4 / 8`
  这种正常值；BPM 变化写出 `#BPMCHANGE`。
- **绿线（SV）→ `#SCROLL`**：按"**每个音符当时生效的流速**与 osu 一致"来摆放，而不是照抄绿线时刻。
- **其他**：kiai 区 → `#GOGOSTART/#GOGOEND`；osu 的 "Omit first bar line" → `#BARLINEOFF`。
- **难度槽**：osu 难度名 → `COURSE: Easy / Normal / Hard / Oni / Edit`；太鼓的第五档
  **Inner Oni（里谱 / Ura）在 TJA 里就写作 `COURSE:Edit`**。判错了可用 `--course` 强制指定。
- **音源**：默认把谱面用的音源一并拷到输出文件夹，`WAVE` 写真实文件名，整个文件夹可直接丢进
  模拟器的歌曲目录（`--no-copy-audio` 可关）。
- **用法**：不给参数 = 弹窗选谱面（会记住上次的输出文件夹，不记输入文件）；
  `python osu2tja2.py "谱面.osu" -o 输出目录/` = 命令行。选项表见上方英文部分。
- **依赖**：纯标准库，Python 3.8+ 即可，不需要 `pip install`（只有图形界面需要 `tkinter`）。
- **已知限制**：音符落格以 BPM + 节奏型为准，不追求逐音符毫秒贴合（那正是 osu 的旧逻辑）；
  SV 只影响观感；红线网格还原会带来亚拍级（远小于一拍）的绝对位置平移，音符之间的相对间隔不变。
- 本仓库**不包含任何谱面与音频**，请勿用它再分发他人的谱面或歌曲。
- **开发说明**：本工具在 AI 助手协助下开发——转换需求、验收标准与 OFFSET 标定由作者确定，输出经
  模拟器试玩并与 osu 原谱逐音符核对，代码由 AI 协助编写。
- 作者：TakanashiR（GitHub: [HolyHexor1](https://github.com/HolyHexor1)）
