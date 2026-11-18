# osu2tja

Convert **osu!taiko** beatmaps (`.osu` with `Mode: 1`) into **TJA** charts for Taiko no Tatsujin
simulators such as **OpenTaiko**, **TJAPlayer3**, **TaikoJiro (太鼓次郎)** and their derivatives.

> **第一次用？** 分步中文说明在 [`docs/使用说明.md`](docs/使用说明.md) —— 安装、双击、
> 选谱面、常见问题，不用懂 TJA 格式也能上手。本文件是技术向的完整参考。

The goal is a *faithful* conversion, not a lossy dump: note types, note positions, BPM changes and
scroll speed are **reconstructed on a clean musical grid**, matching how TJA charts are actually
written by hand.

```
python osu2tja2.py "beatmap.osu" -o out/
```

- Zero dependencies for the conversion itself — Python 3.8+ standard library only.
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
| one row of 864 characters for a bar that mixes 1/7 and 1/9 | that bar split into `#MEASURE 2/4` + `1/4` + `1/8` … so each piece sits on a tidy grid |
| `#SCROLL` values written wherever the osu green line happened to sit | `#SCROLL` placed so that the scroll speed **in effect at each note** matches osu — including the map's global `SliderMultiplier` |

So the converter's real job is to decide, for each note, **which BPM and which rhythm pattern it
belongs to** — and then write the chart the way a human charter would.

## Requirements

- Python 3.8 or newer.
- `tkinter` — only for the graphical file pickers (optional; the CLI does not need it).
- `ffmpeg` — turns the song into OGG. Put it on `PATH` or at `C:\ffmpeg\bin\`. Only needed if you
  want the audio file; `--no-copy-audio` skips it.
- `rosu-pp-py` — **optional, fallback only**. Star ratings are read from your own `osu!.db` (that is
  the number the client shows); rosu-pp is only used for charts that were never imported.
  `py -m pip install rosu-pp-py`. Note it still implements the **pre-2026-07** formula, so its values
  run slightly high (measured +0.05 average, +0.26 worst). No network access either way.

## Usage

**Graphical** — double-click `osu2tja2.bat` (high edition) or `osu2tja2-low.bat` (low edition), or
run with no arguments:

```
python osu2tja2.py            # high edition: up to 3 charts -> 里 / Oni / Hard
python osu2tja_low.py         # low edition:  up to 5 charts -> Oni … 里 (see the table below)
```

Pick an `.osu` file, pick an output folder, done. The output folder is remembered between runs;
the input file is never remembered.

**Command line**

```
python osu2tja2.py "beatmap.osu"                  # -> ./<Title>/beatmap.tja + beatmap.ogg (next to the input)
python osu2tja2.py "beatmap.osu" -o out/          # -> out/<Title>/beatmap.tja + beatmap.ogg
python osu2tja2.py "beatmap.osu" -o out/ --course Oni --level 10
python osu2tja2.py "beatmap.osu" -o out/ --flat   # old layout: files straight into out/
python osu2tja2.py ura.osu oni.osu hard.osu -o out/   # one multi-difficulty .tja (里 / Oni / 困难)
python osu2tja2.py -o out/ a/*.osu b/*.osu c/*.osu   # batch: one .tja per song (see below)
```

### Several difficulties in one file

osu spreads difficulties across *files* (one folder + one audio file + several `.osu`); TJA puts
them in *one file* (several `COURSE:` / `#START`…`#END` blocks). Pass more than one `.osu` **of the
same song** and the converter writes the TJA shape instead — see `本家谱面/8OROCHI/8OROCHI.tja`
for the layout:

| Charts of the same song | `osu2tja2.py` (high edition) | `osu2tja_low.py` (low edition) |
| --- | --- | --- |
| 1 | `Oni` | `Oni` |
| 2 | `Edit` (= 里 / Inner Oni), `Oni` | `Oni`, `Hard` |
| 3 | `Edit`, `Oni`, `Hard` | `Oni`, `Hard`, `Normal` |
| 4 | **error** (see below) | `Oni`, `Hard`, `Normal`, `Easy` |
| 5 | **error** | `Edit`, `Oni`, `Hard`, `Normal`, `Easy` |

`LEVEL` (the `★×N` shown in game) is no longer a fixed number: each block gets
`round(SR × 2)`, where SR is the **osu!taiko star rating** of that `.osu` at No Mod. SR is not stored
in `.osu`, so it is read from your own `osu!.db` — the same cached number the song-select screen shows.
Charts that were never imported fall back to [`rosu-pp-py`](https://pypi.org/project/rosu-pp-py/)
(`py -m pip install rosu-pp-py`), which is a slightly dated formula (see *Difficulty* below). With
neither source available `LEVEL` falls back to `10` and a warning is printed.

Which chart becomes which difficulty is decided by the **star rating**, not by the order you hand
them over: the higher the `★`, the higher the course name. Giving the same charts in any order
therefore produces the same file.

Both editions share one engine; pick one by which launcher you double-click — `osu2tja2.bat` (high)
or `osu2tja2-low.bat` (low). The high edition stops at `Hard` on purpose: those inputs are already
hard osu charts, and `Easy` / `Normal` judgement windows are far wider than osu's, so an osu chart
labelled that way would not play the same. The low edition fills **downward from `Oni`** and does use
`Normal` / `Easy` — that is the point of it, since its inputs are low-difficulty charts to begin with.

Two charts that land on the **same** `★N` are indistinguishable in game, so only then does the GUI
pop up its little reorder box to ask which one goes first — and it only lets you swap those tied
charts (different `★` is already decided). On the command line there is nobody to ask, so it keeps
the SR order and prints a note. `--courses` / `--levels` are explicit overrides: they are applied
**in the order you give them**, with no re-sorting:

```
python osu2tja2.py a.osu b.osu c.osu --courses 里,Oni,困难 --levels 10,9,8
```

`TITLE`, `WAVE`, `OFFSET` and `DEMOSTART` are **file-level** in TJA — written once, shared by every
block — so all difficulties must sit on one audio timeline. The written `OFFSET` therefore comes
from the *earliest* chart origin among the inputs; a chart that starts later simply gets empty bars
at the front (what official charts do while waiting for the music).

**Different offsets are fine.** Each `.osu` carries its own `[TimingPoints]`, so every block is laid
out from its own red lines; the shared `OFFSET` only fixes where bar 0 sits on the audio. Both
shapes are covered by `tmp/_test_multi.py` — charts whose first red line is 60 s later, and two
charts shifted by a non-integer 37 ms — and in both cases every block's notes stay on their own
chart's absolute times (max deviation ≤ 1.4 ms). The one thing that *cannot* be shared is the audio
file: all inputs must point at the same recording, otherwise you get a warning and the first one
wins. Audio is taken from the first input's folder and delivered once.

### Batch conversion: several songs at once

Pick charts from more than one song and the converter switches to batch mode: it groups the inputs
by song and writes **one `.tja` per song**, each in its own folder.

**How "same song" is decided: by folder.** In osu a mapset *is* a folder — one audio file with all
difficulties side by side — so charts from the same folder are the same song, and two different
songs can never share one. (Title text is deliberately *not* used: remixes and unrelated works can
carry an identical title, and the same title in two folders means two separate mapsets.)

```
<songs>/**/*.osu  ->   <your folder>/<Title A>/<Title A>.tja + audio
                       <your folder>/<Title B>/<Title B>.tja + audio
                       <your folder>/<Title C>/<Title C>.tja + audio
```

Each song goes through the multi-difficulty rules above, so three charts of one song still become
`Edit` / `Oni` / `Hard` inside a single file (ordered by star rating), and `LEVEL` is still
`round(SR × 2)`.

```bash
python osu2tja2.py -o "D:/TJA" songA/*.osu songB/*.osu songC/*.osu
```

Batch mode **requires `-o`** — there is no safe default, since writing next to the first input would
drop converted files inside osu's own `Songs` tree. `--flat` is ignored (audio files are usually all
called `audio.ogg`; flattening a batch would overwrite one song's music with another's), and so are
`--title` / `--artist` (each song keeps the names from its own `.osu`).

A song with **4 or more** charts is an error. Every offending song is named up front and *nothing*
is written — no silent dropping of a difficulty. The GUI behaves the same and stops before the
reorder step.

### Output layout

Every conversion creates a folder named after the song inside the folder you choose, and puts both
files in it — one folder per song is what taiko simulators expect:

```
<your folder>/<Title>/
    <beatmap>.tja
    <beatmap>.ogg      # always OGG, whatever the source format was
```

`<Title>` comes from the `.osu` (`TitleUnicode`, falling back to `Title`) with characters Windows
forbids (`<>:"/\|*?`) replaced by `_`. Use `--flat` to skip the extra folder.

The `.tja` is named after the `.osu` file for a single input; with multiple inputs it is named after
the song (`<Title>/<Title>.tja`) — one file holds them all, so no single beatmap name applies.

### Options

| Option | Meaning |
| --- | --- |
| `-o, --output PATH` | Where to write (created if missing). Default: next to the input file. A song-named subfolder is created inside it unless `--flat` is given. A path counts as a **file** only when it ends in `.tja` / `.osu`; anything else is treated as a folder — a directory called `v1.2` or `vs.VIGVANGS` would otherwise be mistaken for a filename. |
| `--flat` | Do not create the song-named subfolder; write `.tja` and `.ogg` straight into the target folder. |
| `--title TEXT` | Override the chart title (used for both `TITLE:` and the song folder name). Needed when the source `.osu` has a corrupted `TitleUnicode` — some old beatmaps store broken characters there, and this converter copies the field verbatim. |
| `--artist TEXT` | Override the artist (`ARTIST:` and `SUBTITLE:`). Use it when the source artist field is unreadable in the target encoding. |
| `--keep-original-names` | Disable the automatic "corrupted name → romanised name" fallback: use `TitleUnicode` / `ArtistUnicode` exactly as written, even if they look broken. |
| `--encoding ENC` | Output encoding: `cp932` (default — the usual convention for Japanese simulators), `utf-8`, `utf-8-sig`. If the title or artist contains characters the chosen encoding cannot represent, the whole file is re-encoded as `utf-8-sig` (UTF-8 with BOM, which is what official OpenTaiko charts use) instead of writing `?` — no character is ever lost, and a warning is printed. |
| `--course NAME` | `COURSE`: `Oni` (default), `Hard`, `Normal`, `Easy`, `Edit`, or `auto` to infer it from the osu difficulty name. With multiple inputs this is ignored — use `--courses`. |
| `--level N` | `LEVEL`, shown in-game as `★×N`. Default: `round(SR × 2)` of that chart (`10` if no star rating can be read). With multiple inputs it means "use this star count for every block". |
| `--courses LIST` | Multiple inputs only: `COURSE` per block, comma-separated, **in the order you pass them** (`Edit,Oni` or `里,困难`). Giving this turns off the automatic star-based ordering. Default follows the input count: 2 → `里,Oni`, 3 → `里,Oni,困难`, with the highest `★` on top. |
| `--levels LIST` | Multiple inputs only: `LEVEL` per block, comma-separated, in input order. Also disables the automatic star-based ordering. Default = each chart's own `round(SR × 2)`. |
| `--barline MODE` | `auto` (default — follows osu's "Omit first bar line" flag), `show` (always draw), `hide`. |
| `--subdiv N` | Base cells per beat, default `4` (one cell = a 1/4 beat, the most common TJA convention). Raised automatically (6 / 8 / 12 / 16 / 24) when a section needs finer cells. |
| `--wave-ext EXT` | Only accept this audio extension (e.g. `ogg`) when picking the song file. Output is always `.ogg` regardless. |
| `--no-copy-audio` | Do not produce the audio file at all (the chart then points at a file that is not there). |
| `--no-trim-audio` | Keep the redundant tail of the song. By default the audio ends ~3 s after the last note instead of running to the end of the track (see *Tail trimming* below). |
| `--trim-tail SEC` | Reverb/tail room to keep after the last note, default `3`. Raise it (e.g. `5`) if the last hit sounds cut off. |
| `--offset-shift MS` | Shift the written `OFFSET` by MS milliseconds (positive = larger OFFSET). Touches only the `OFFSET:` header line — notes, measures and BPM are never affected. |
| `--no-offset-shift` | Equivalent to `--offset-shift 0`: use the raw osu chart origin with no trim. |
| `--demostart SEC` | Override the `DEMOSTART:` header (preview start, seconds from the beginning of the audio). Default: copy osu's `PreviewTime`; `0` if the source has none. |
| `--no-red-snap` | Disable timing-point grid restoration. Kept for comparison/debugging only. |
| `--quiet` | Less console output. |
| `--gui` | Force the dialog even when an input file was given. |
| `--forget-out-dir` | Forget the output folder remembered by the GUI (clears that one setting). |
| `--open-out-dir` | Open the output folder when finished. Off and not prompted by default. |

### GUI

Double-clicking the `.bat` opens up to three dialogs, in this order:

1. **Pick the charts — in a built-in list, not the Windows file dialog.** Every `.osu` under
   your osu! `Songs` folder is listed in a table together with its star rating, note count,
   BPM, file size and mapset folder:

   * **type to search** — the whole query is tried as one phrase first (`song a`,
     `one of us`); if nothing matches it falls back to an AND over the space-separated
     words (`katagiri oni`);
   * **click a column header to sort** (title / artist / difficulty / star / notes / BPM /
     size / modified / folder), click again to reverse — numeric columns start big-first;
   * **Ctrl-click / shift-click / Ctrl-A** to multi-select; right-click for *select every
     chart of this song*; double-click or Enter confirms, Esc cancels;
   * the status line always says *how many charts, how many songs, how many picked*.

   The list is scanned from `D:\Download App\osu!\Songs`, falling back to
   `%LOCALAPPDATA%\osu!\Songs` (see `DEFAULT_INPUT_DIRS`). About 4100 files are read
   with a thread pool (~3 s), and the result is cached in
   `%APPDATA%\osu2tja2\maps_cache.json`, so the second launch is instant.
   *Change folder…* points the list somewhere else, *Use the file dialog…* falls back to the
   classic picker. Charts of one song become a multi-difficulty chart, charts of several
   songs are converted as a batch.
2. **Only if two charts share the same `★`.** The star rating normally decides everything, so this
   step is skipped: the highest `★` becomes `Edit`, the next one `Oni`, the next `Hard`. But when
   two charts land on the **same** `★N` the song-select screen cannot tell them apart either, so a
   list pops up with *Move up / Move down* for just those tied charts — swapping them decides which
   one gets the higher course name. Each tie group gets its own `── Title · ★14 ──` separator and
   moving stays inside it (different `★`, or a different song, is already fixed). Enter = OK,
   Esc = cancel, and cancel aborts the conversion.
3. **Pick the output folder.** It is remembered for next time; one subfolder per song is created
   inside it automatically.

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
| inherited ("green") timing point — slider velocity | `#SCROLL` = `100 / (−beatLength)` × `SliderMultiplier / 1.4` |
| red timing point — **implicit SV reset to 1.0** | `#SCROLL 1` (× the same `SliderMultiplier / 1.4` factor) |
| `effects` bit 0 — kiai time | `#GOGOSTART` / `#GOGOEND` |
| `effects` bit 3 — omit first bar line | `#BARLINEOFF` / `#BARLINEON` |

**A red line resets the scroll speed to 1.0 — that is the hidden half of the rule.** In osu, SV is
whatever the *last* timing point says; a red line carries no SV field, so hitting one means "back to
1.0×" unless a green line sits on the very same tick (the green one wins). Charts lean on this: a
section change is often signalled by a bare red line with no green line attached, and every player sees
the speed snap back. Ignore it and that whole section keeps the previous `#SCROLL`, which reads as
"the sim doesn't follow the map" — One of Us at 2:11 (130 BPM block → bare `4/4` red line while the
previous `#SCROLL` was 1.55) was 55 % too fast for 16 seconds because of exactly this. The converter
now builds one merged "effective SV" timeline — red lines contribute `1.0`, green lines contribute
their own value and override a red line on the same tick — and every `#BPMCHANGE`/`#MEASURE`-only
boundary therefore emits `#SCROLL 1` when the map means it.

**Why `SliderMultiplier` is in that formula.** In osu!taiko the scroll speed is
`175 × SliderMultiplier × SV × BPM` pixels/minute-of-play, i.e. `[Difficulty] SliderMultiplier` (the
editor's global *slider velocity*, 1.4 by default) **scales the whole chart's visual speed**, and each
green line only multiplies on top of it. Measured against the official forum thread
["Note Speed Mechanics"](https://osu.ppy.sh/community/forums/topics/1851087): the standard skin scrolls
245 px/beat = 175 × 1.4, and a map with `SliderMultiplier: 1.6` scrolls 280 px/beat. So the converter
divides by 1.4 and folds the result into `#SCROLL`:

- `SliderMultiplier: 1.4` (nearly every map) → factor 1.0, output is exactly the raw green-line SV.
- `1.6` → every `#SCROLL` is 14.3 % larger; `0.8` → 42.9 % smaller.
- BPM needs no extra work: both sides scroll a fixed number of pixels *per beat*, so tempo scales
  identically. HR/EZ are ignored — they are mods applied in-game, not part of the file.

### Bar density: splitting a measure that is too fine

A measure gets as many cells as its notes need, and the cell grid is whatever rhyme the notes imply.
That works until one measure contains **mutually prime** subdivisions — say 1/7 and 1/9 — because the
only grid holding both is their least common multiple. A real example (Checklist, at 0:31) hit
**2016 cells for one measure**, which is past the cap, so the converter fell back to 864 cells:
every note is still within 1 ms, but the bar is 864 characters long and the notes land on cells
71 / 143 / 287 — technically exact, visually random.

TJA does not require a measure to stay one measure: `#MEASURE n/d` may be re-declared at any bar
line, and real charts do write things like `#MEASURE 17/16`. So the converter **bisects** a bar whose
grid is too fine and gives each half its own `#MEASURE`, which means each half only has to host *its
own* subdivisions. The same passage becomes

```
#MEASURE 2/4
100100100100200010001000200000100000200000000000,
#BARLINEOFF
200000020000,
```

every piece on a grid you can actually read, and not a single note moved.

The threshold is **density, not length**: a piece is split when it needs more than
`SPLIT_MAX_DENSITY = 48` cells *per beat* (48 is also the finest subdivision the rhythm classifier
knows), with `SPLIT_MAX_CELLS = 192` as an absolute cap. Judging by cells-per-measure instead would
tear apart the most ordinary bar there is — a 4/4 measure written on a 1/16 grid is 64 cells, and
that is perfectly tidy. A split is kept only if it actually helps: the largest piece must end up
smaller than the original bar, and the total cell count must not more than double. Every piece after
the first gets `#BARLINEOFF`, so the chart still *looks* like the original measures.

Measured on the test set (notes, note kinds, deviations and `#SCROLL` values are byte-for-byte
unaffected — only bar layout changes):

| chart | measures | total cells | largest bar |
| --- | --- | --- | --- |
| Checklist | 67 → 227 | 27592 → 5864 | 1152 → 192 |
| Talk | 108 → 196 | 15184 → 7559 | 1008 → 192 |
| BUZZ CUTZ | 486 → 598 | 27048 → 20031 | 768 → 192 |
| ON.UR.MARKS | 327 → 533 | 36330 → 25550 | 1248 → 192 |
| One of Us | 248 → 249 | 5536 | 256 → 128 |
| vs.VIGVANGS | 171 | 4066 | 48 |

### Chart headers

`TITLE`, `ARTIST`, `SUBTITLE` (`--` + artist), `BPM`, `WAVE`, `OFFSET`, `DEMOSTART`, `SONGVOL`,
`SEVOL`, `SCOREMODE`, `COURSE`, `LEVEL`, `BALLOON`, plus a `//Converted from "…"` comment line.

**`DEMOSTART` is osu's `PreviewTime`, copied over.** Both mean the same thing and use the same
timeline: the position **inside the audio file** where the song-list preview starts. TJA stores it
in seconds, osu in milliseconds, so it is a straight `/ 1000` — the `OFFSET` trim is deliberately
*not* applied on top, because `OFFSET` describes where the chart starts in the audio, which is a
different question (mixing the two would subtract the device latency twice). When osu has no preview
point set (`PreviewTime: -1`, the client then picks a loud section itself) the value falls back to
`0.000`, which is what a TJA without `DEMOSTART` does. Use `--demostart SEC` to override.

`TITLE` and `ARTIST` prefer the original name (`TitleUnicode` / `ArtistUnicode`), which is what a
chart should normally show. If that field looks **corrupted in the source file**, the romanised field
(`Title` / `Artist`) is used instead, and the reason is printed. The artist is also repeated in
`SUBTITLE` as `--Artist`, because that is the line most simulators actually print in the song list.

The corruption check only looks at the *shape* of the string — it never tries to guess the original
text, because that is unrecoverable. It flags three cases: a writing system a taiko chart would never
use (Thai / Hangul / Cyrillic / Arabic …), the leftover signature of UTF-8 read as a single-byte
encoding (`Ã©`, `锟斤拷` …), and a title that has long-vowel marks but not a single kana — the tell of
katakana having been replaced wholesale by ideographs. Old beatmaps do contain such fields: one chart
in this repo's test set stores `ボボボーボ・ボーボボ` as `忙忙忙ー忙・忙ー忙忙` and its artist as Thai.
`--keep-original-names` turns the fallback off; `--title` / `--artist` override outright.

### Difficulty

A single chart is written as `COURSE:Oni` (魔王 / 鬼). TJA has no separate star-rating field —
`LEVEL` *is* the star count TJAPlayer3 / OpenTaiko displays. It is derived from the chart itself:

```
LEVEL = round(SR × 2)      SR = osu!taiko star rating of the .osu, No Mod
```

SR lives in no file — osu! computes it from the chart, and the formula changes whenever osu! ships a
star-rating rework (the latest was **2026-07-03**). So the converter does not guess: it reads the
cached rating out of your `osu!.db`, which is exactly the number your client displays. For charts that
were never imported it falls back to `rosu-pp-py`, whose latest release (4.0.2) still implements the
**2025-10-29** formula — measured against osu.ppy.sh on 21 charts it reads high by 0.05 on average and
0.26 at worst, so prefer the `osu!.db` path. With neither source available, `LEVEL:10` plus a warning.
`--level` overrides; `--course auto` falls back to guessing from the osu difficulty name
(`Easy` / `Normal` / `Hard` / `Oni` / `Edit`, where `Inner Oni` is `COURSE:Edit`).

Note that `SR × 2` is not capped at 10: an 8★ osu!taiko chart becomes `★16` here. If your simulator
mangles two-digit levels, pass `--level` explicitly (or `--levels` for multi-difficulty files).

For **multiple inputs** the labels follow the **star rating**: highest → `里(Edit)`, then `Oni`,
then `困难(Hard)` for 2 / 3 files; 4+ inputs is rejected — see *Several difficulties in one file*
above. Only charts tied on the same `★N` fall back to input order (or to whatever the GUI's reorder
box decides).

### Audio

Output audio is **always OGG/Vorbis**, whatever the source was:

| Source | What happens |
| --- | --- |
| `.ogg` | copied as-is (no re-encode) |
| `.mp3`, `.m4a`, `.flac`, `.wav`, … | transcoded with `ffmpeg -c:a libvorbis -q:a 6` |

`WAVE` is written with the real `.ogg` file name, so `<Title>/` can be dropped straight into a
simulator's song directory. Vorbis rather than Opus on purpose: OpenTaiko / TJAPlayer3 decode audio
through Bass, which handles Vorbis in OGG but not Opus.

`ffmpeg` must be on `PATH`, or at `C:\ffmpeg\bin\`. If it is missing the conversion reports an error
instead of silently shipping an MP3 — use `--no-copy-audio` to skip audio entirely.

#### Tail trimming (on by default)

osu ships the **full song**, but a chart usually ends long before the music does, so the tail is
dead weight. The converter cuts it off:

```
cut point = max(last sounding event + 3 s, DEMOSTART + 5 s)     # capped at the original length
```

- "Last sounding event" means the **end** of the final note / drum roll / balloon, not its start —
  cutting at a roll's start would leave a roll without an ending.
- The extra 3 s lets the last hit ring out instead of being chopped mid-decay. Change it with
  `--trim-tail SEC` if you can hear the tail being clipped.
- Nothing is cut if it would save less than 3 s, so charts that already fit are left alone.

Only the **tail** is ever trimmed. Trimming the head would move the audio's zero point and force an
OFFSET recomputation, which risks shifting the whole chart for a few seconds of gain — not worth it.

⚠ Two consequences worth knowing:

1. Trimming means **re-encoding**. A `.ogg` source normally takes the "copy, no lossy round-trip"
   shortcut; when trimming is needed it is upgraded to a Vorbis re-encode. Audible difference is
   negligible, but it is not lossless.
2. The source file is untouched — only the copy in the output folder is trimmed. Delete it and
   re-run if you dislike the result.

Turn it off with `--no-trim-audio`.

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

### Code layout

`osu2tja2.py` is deliberately a single file (double-clickable, no install step). Sections appear in
reading order, and every non-obvious constant carries the measurement that produced it:

| Section | What lives there |
| --- | --- |
| constants | audio formats, tail trimming, grid candidate tables, balloon threshold, the OFFSET constant |
| utilities | encoding-safe reading, number formatting, filesystem-safe names, mojibake detection, output-encoding fallback, audio delivery |
| `Timing` | the osu timing-point timeline (red = BPM/bar, green = SV, kiai); all queries are binary searches |
| `parse_osu` | `.osu` → meta, timing, hit objects / sliders / spinners |
| grid | `_cell_index` (the single beat→cell conversion), `_grid_fits`, `_cmd_collapse`, `_note_collapse`, `_bar_subdiv`, `choose_grid` |
| pipeline pieces | `collect_events`, `board_origin`, `balloon_boost`, `place_*`, `split_fine_bars` (bisects over-dense measures), `render_body`, `render_head`, `write_tja`, `deliver_audio` |
| `load_chart` / `layout_chart` | the pipeline split in two: *what the chart is* (parsed, origin fixed) vs *how it is laid out* (bars, text). Split so multi-difficulty can share one origin |
| `convert` | single-difficulty orchestration — it reads like the pipeline, left to right |
| `convert_multi` | N inputs → one `.tja`: file header once, then one `COURSE:` block per input |
| GUI / CLI | `gui_flow` (callbacks injected, so the flow is testable without Tk), `run_gui`, `main` |

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

### 两个版本（高难版 / 低难版）

同一套转换逻辑，两种难度分配方案。**只有"哪张谱写成哪个难度"不同** —— 音符、BPM、流速、小节网格、
音源、命名、批量处理都完全一样。

| 同一首歌给几张 | `osu2tja2.py`（高难版） | `osu2tja_low.py`（低难版） |
| --- | --- | --- |
| 1 张 | 鬼 | 鬼 |
| 2 张 | 里 / 鬼 | 鬼 / 困难 |
| 3 张 | 里 / 鬼 / 困难 | 鬼 / 困难 / 普通 |
| 4 张 | 报错 | 鬼 / 困难 / 普通 / 简单 |
| 5 张 | 报错 | 里 / 鬼 / 困难 / 普通 / 简单 |

双击哪个 `.bat` 就是哪个版本：`osu2tja2.bat`（高难）/ `osu2tja2-low.bat`（低难）。两版都是
**星数高的那张拿更高的难度名**（同星数才会问先后）。单张都写「鬼」，不叫里谱。

高难版最低只到「困难」：那些输入本身就是 osu 的高难谱，而本家「简单/普通」的判定比 osu 宽得多，
硬挂上去会变成判定不一致的假难度。低难版是**从「鬼」往下填**，它的输入本来就是低难谱，
所以「普通/简单」照用。

### 主要还原点

- **选谱面不再是翻文件夹**：双击 `.bat` 后第一屏是程序自带的谱面列表（曲名/曲师/难度/★/音符/BPM/
  大小/修改时间/文件夹），打字即搜索、点表头即排序、Ctrl·Shift 多选、右键一次选走一首歌的全部谱面。
  列表扫 `osu!\Songs`（4100 多个 `.osu` 用线程池读，约 3 秒），结果缓存在
  `%APPDATA%\osu2tja2\maps_cache.json`，第二次打开瞬开。
- **音符**：`1` 小咚 `2` 小咔 `3` 大咚 `4` 大咔；滑条 → 连打 `5`/`6` … `8`；转盘 → 气球 `7` … `8`。
- **判定音映射**：osu 的判定位掩码 `1` 普通 / `2` 哨声 / `4` 重音 / `8` 拍手；太鼓里哨声与拍手
  都算**咔**（鼓边），重音算**大**。
- **红线（BPM / 拍号）网格还原**：链式还原到 1/4 拍网格，小节分母从六位数降到 `16 / 4 / 8`
  这种正常值；BPM 变化写出 `#BPMCHANGE`。
- **太细的小节会被切开（`#MEASURE` 二分）**：一个小节里如果同时出现 1/7、1/9 这种**互质**的细分，
  能同时容纳它们的网格只有最小公倍 —— 实测 Checklist 的 0:31 那一个小节理想格数是 **2016 格**，
  超上限后退成 864 格：音符时刻仍然 ≤1ms，但一行 864 个字符、音符落在 71/143/287 这种毫无规律的
  格号上，看着就是"没对齐"。TJA 本来就允许在小节线上重写 `#MEASURE n/d`，所以转换器把**网格太细
  的小节二分开**，每半段只需容纳自己那半段的细分，写成 `#MEASURE 2/4` + `2/4` + `1/8` …… 每段都
  落在能一眼看懂的格网上，而音符一个都没动。
  判据是**密度**不是长度：一段要的格数超过 `SPLIT_MAX_DENSITY = 48` 格/拍（48 也正是节奏识别表
  认得的最细档）才切，另有 `SPLIT_MAX_CELLS = 192` 的绝对上限。按"每小节几格"判是错的 —— 四四拍
  写 1/16 本来就是 64 格的**标准写法**，那样会被白白打碎。切完还要"最碎的一段确实变小、总格数不
  超过两倍"才认账，否则原样保留。除第一段外一律 `#BARLINEOFF`，画面仍是原来的小节。
  实测：Checklist 小节 67→227、总格 27592→5864、最大小节 1152→192；Talk 108→196、15184→7559、
  1008→192；BUZZ CUTZ 486→598、27048→20031、768→192；ON.UR.MARKS 327→533、36330→25550、
  1248→192。**音符数、咚咔种类、时刻偏差、`#SCROLL` 全都没变**，只有小节划分变了。
- **绿线（SV）→ `#SCROLL`**：按"**每个音符当时生效的流速**与 osu 一致"来摆放，而不是照抄绿线时刻。
  写出的数值 = `100 / (−绿线 beatLength)` **× `SliderMultiplier / 1.4`** —— 因为 osu!taiko 的滚动速度是
  `175 × SliderMultiplier × 绿线SV × BPM`，谱面 `[Difficulty]` 里那个全局滑条速度（默认 1.4）会把整首谱
  一起加速/减速，绿线只是在它上面乘。1.4 的谱（绝大多数）折算系数正好是 1.0，产物与以前完全一样；
  1.6 的谱 `#SCROLL` 整体 ×1.143，0.8 的整体 ×0.571。BPM 不用另补：两边都是"每拍固定像素"。
- **红线自带"SV 归 1"**：osu 里生效的 SV 由**最后一个** timing point 决定，而红线不带 SV 字段 ——
  撞上红线就等于回到 **1.0×**，除非同一毫秒还有一条绿线（绿线优先）。谱师常拿"光秃秃的红线"当
  段落切换标记，玩家看到的就是速度一下弹回原速。不还原这一层，那一段会一直沿用上一条 `#SCROLL`。
  One of Us 的 2:11（130 BPM 段 → 一条只有 `4/4` 的红线，而前一条 `#SCROLL` 是 1.55）当时整段快
  55%、持续 16 秒，就是这么来的。实现上把红线（值 1.0）与绿线合成一条"有效 SV"时间轴再取用，
  因此只有红线、没有绿线的 `#BPMCHANGE` / `#MEASURE` 边界会自动写出 `#SCROLL 1`。
- **换小节 / 换 BPM 处重发一次 `#SCROLL`（防御性冗余）**：理论上 `#SCROLL` 一直有效到下一条，
  不必重复。但实测有模拟器在读 `#MEASURE` 重建小节时把滚动状态清掉，表现是"从某个换拍号的小节起
  流速突然不再跟原谱"。所以凡是要写 `#MEASURE` 或 `#BPMCHANGE` 的小节，开头都补发一条**当前值**
  的 `#SCROLL`。值一样、位置一样，对判定零影响，只多几行。
- **气球（拨浪鼓）的极慢段会被强制成 1HS**：osu!taiko 有个本家没有的机制 —— 气球在极低 SV 下滚得
  太慢时，游戏会把它推迟到快被击打才画出来，所以原作可以给气球配 `SV=0.01`。TJA 没有这个机制，
  `7` 会从出现那一刻就挂在轨道上慢慢爬。转换时按**等效 BPM = 当前 BPM × 该处 `#SCROLL`** 判断：
  小于 **5**（即比"5BPM + 1HS"还慢）就把**气球整个持续区间**写成当前 BPM 下的 1HS（`#SCROLL 1`），
  气球一结束立刻恢复原谱流速；区间内原有的绿线一律让位。阈值是 `osu2tja2.BALLOON_MIN_EFF_BPM`。
- **其他**：kiai 区 → `#GOGOSTART/#GOGOEND`；osu 的 "Omit first bar line" → `#BARLINEOFF`。
- **难度与星数**：单谱一律输出 `COURSE:Oni`（魔王/鬼）。TJA 没有独立的星数字段，`LEVEL` 就是
  模拟器显示的 `★×N`，取值 **`round(SR × 2)`** —— SR 是这首谱在 osu!taiko 下的星级（No Mod）。
  SR 不在任何文件里（它是客户端按谱面算的，而且每次 osu! 重构星数都会变，最近一次是 2026-07-03），
  所以转换器不自己猜：它读你 `osu!.db` 里缓存的星级 —— 就是选歌界面显示的那个数。
  没导入过的谱才退回 [`rosu-pp-py`](https://pypi.org/project/rosu-pp-py/)
  （`py -m pip install rosu-pp-py`），而它最新版 4.0.2 实现的仍是 **2025-10-29** 那版公式，
  实测比官网偏高 0.05（最高 0.26），只能当兜底。两个来源都没有时 `LEVEL` 回退 `10` 并打警告。
  要手改加 `--level`。
  ⚠ 这条折算**不封顶 10**：8★ 的 osu taiko 谱会写成 `★16`。模拟器显示两位数不好看的话，用 `--level` 指定。
- **多难度（一个 `.tja` 装多张谱）**：osu 是「一个文件夹 + 一份音源 + 多个 `.osu`」，本家是
  「一个 `.tja` 里若干段 `COURSE` + `#START … #END`」。给**多个** `.osu` 就按本家那种形态合成一个文件：
  `1 张 → Oni`｜`2 张 → 里(Edit) / Oni`｜`3 张 → 里(Edit) / Oni / 困难(Hard)`；
  **4 张及以上直接报错**（模拟器只认 5 个难度档位，而「简单/普通」的判定比 osu 宽得多、已经弃用，
  拿 osu 谱冒充会变成判定不一致的假难度）。星数照上面的 SR 折算，每段按各自那张谱算。
  ★ **哪张谱当哪个难度由星数决定**：★ 高的拿更高的难度名，最高那档必是 Edit ——
  所以同一组谱不管你按什么顺序塞进去，转出来的结果都一样。只有两张谱的**星数（★N）完全相同**、
  模拟器里也分不出谁更难时，才需要你定先后（命令行没法问，就按 SR 细排并在输出里说明）。
  `--courses` / `--levels` 是显式覆盖：**按你给的顺序对号**，此时不再自动按星数排。
  `TITLE / WAVE / OFFSET / DEMOSTART` 是**文件级**的、只写一次，所以几张谱必须共用一条时间轴：
  `OFFSET` 取所有谱里**最早的谱面起点**，起点更晚的那几张在开头补空小节（就是本家谱面开头的
  等待段），音符绝对时刻一个都不变。
  **offset 不一样不会错乱**：每个 `.osu` 自带整套 `[TimingPoints]`，每段都按自己的红线独立排小节，
  共用的 `OFFSET` 只决定「第 0 小节落在音频的哪个时刻」。`tmp/_test_multi.py` 里两种形态都测了
  （首条红线晚 60 秒、两张谱整体错开 37ms），逐音符最大偏差 ≤ 1.4ms。唯一不能共用的是音源
  文件本身 —— 几张谱指向不同音频时会提示，并采用第一张的。
  音源取第一张谱所在文件夹的那一份、只交付一次。
  图形界面的流程是**选谱面 → （星数打平时才）定先后 → 选输出文件夹**：
  星级不同就直接排好往下走，不再多一步；只有星数相同的几张才弹「定先后」的小窗口
  （上移/下移，回车=确定、Esc=取消），而且只能在这些打平的谱之间换 —— 不同星数、不同歌都不许跨。
  万一那个小窗口因为系统原因显示不出来，程序会在 2.5 秒后按当前顺序继续，**不会卡死**。
- **批量（一次转很多首歌）**：选中的谱面跨了多首歌时自动按歌分组，**每首歌各转一个 `.tja`**。
  「同一首歌」的判据是**在同一个文件夹**：osu 里一个 mapset 就是一个文件夹（一份音源 + 若干难度），
  不同的歌必然不在同一文件夹；反过来同名不同版本（原曲 / remix）也不会被误合成一首。
  产物形如 `<输出目录>/<曲名A>/<曲名A>.tja`、`<输出目录>/<曲名B>/<曲名B>.tja`，每首歌内部的
  难度分配与星数折算和单曲完全一样。某首歌自己超过 3 张谱 → **报错并列出是哪几首，一个文件都不写**
  （不会偷偷丢掉多出来的难度）。命令行批量**必须给 `-o` 输出目录**；`--flat` 与 `--title/--artist`
  在批量里不生效（音源文件名会互相覆盖 / 各首歌的曲名来自它自己的 `.osu`）。图形界面同样支持：
  每首歌内部同样按星数定难度，只有星数打平的那几张才会问你。
- **音源一律转 OGG**：源是 `.ogg` 就直接拷（不重编码），是 mp3 / m4a / flac / wav 就用 ffmpeg
  转成 OGG/Vorbis；`WAVE` 写这个 `.ogg` 的文件名。用 Vorbis 不用 Opus，是因为 OpenTaiko /
  TJAPlayer3 走 Bass 解码，认 Vorbis 不认 OGG 里的 Opus。**需要 ffmpeg**（`PATH` 或
  `C:\ffmpeg\bin\`）；找不到会直接报错，不会偷偷把 mp3 塞给你。
- **裁掉冗余的音乐尾巴（默认开）**：osu 的音源是完整一首歌，而谱面往往打完就完了，
  后面留着一大段没音符的音乐。转换时按
  `裁点 = max(最后一个能发声的东西的结束时刻 + 3s, DEMOSTART + 5s)`
  把尾巴切掉（上限是音频原长）。连打/气球取**终点**——从起点切会留下没有结尾的长条。
  只**裁尾**、绝不碰开头：裁开头会改变音频零点、连带要重算 OFFSET，风险远大于收益。
  可省的不足 3 秒就整个跳过，本来贴合谱面的歌一点不动。`--trim-tail 5` 加余韵，
  `--no-trim-audio` 整个关掉。⚠ 裁剪要重新编码，源是 `.ogg` 时的「直接拷贝不损失」会
  升级成 Vorbis 再压一遍（听感差异极小，但不是无损）；原文件不动，不满意删掉重转即可。
- **输出目录**：在选定文件夹下新建一层**以曲名命名的文件夹**，`.tja` 与 `.ogg` 都放进去
  （模拟器按「一首歌一个文件夹」收录）。曲名优先取 `.osu` 的 `TitleUnicode`（原名），
  判出该字段在源文件里已写坏时改用 `Title`（罗马音）并打印原因；`--keep-original-names` 可关掉这套兜底。
  Windows 非法字符替换成 `_`。`TJA` 头部同时写 `TITLE`、`ARTIST`、`SUBTITLE:--曲师`。
  要旧行为（全部塞进选定文件夹）加 `--flat`。
- **用法**：不给参数 = 弹窗选谱面（会记住上次的输出文件夹，不记输入文件）；
  `python osu2tja2.py "谱面.osu" -o 输出目录/` = 命令行；
  `python osu2tja2.py a.osu b.osu c.osu -o 输出目录/` = 三张谱合成一个多难度 `.tja`
  （按星数 = 里 `Edit` / `Oni` / `困难`；4 张以上报错）。
  选项表见上方英文部分。
- **依赖**：纯标准库，Python 3.8+ 即可（图形界面需要 `tkinter`）；转 OGG 需要 **ffmpeg**。
  自动星数（`LEVEL = round(SR×2)`）默认读你机器上的 `osu!.db`，不需要额外依赖；
  只有「没导入进 osu! 的谱」才会退化到 `rosu-pp-py`（可选，`py -m pip install rosu-pp-py`）估算。
- **已知限制**：音符落格以 BPM + 节奏型为准，不追求逐音符毫秒贴合（那正是 osu 的旧逻辑）；
  SV 只影响观感；红线网格还原会带来亚拍级（远小于一拍）的绝对位置平移，音符之间的相对间隔不变。
- 本仓库**不包含任何谱面与音频**，请勿用它再分发他人的谱面或歌曲。
- **开发说明**：本工具在 AI 助手协助下开发——转换需求、验收标准与 OFFSET 标定由作者确定，输出经
  模拟器试玩并与 osu 原谱逐音符核对，代码由 AI 协助编写。
- 作者：TakanashiR（GitHub: [HolyHexor1](https://github.com/HolyHexor1)）
