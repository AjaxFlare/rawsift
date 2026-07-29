# Usage guide

[简体中文](USAGE.zh-CN.md)

## Installation

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

For RAW files without a usable embedded JPEG preview, install rawpy:

```bash
python -m pip install -e ".[raw]"
```

ExifTool and FFmpeg are optional system-level fallbacks. The program discovers them automatically when they are available on `PATH`.

## Basic command

```bash
rawsift INPUT --output OUTPUT [OPTIONS]
```

`INPUT` may be one supported file or a directory. Directories are scanned recursively. If the requested output directory is non-empty, the program creates a numbered sibling rather than overwriting it.

Selection has no fixed keep-rate quota. Every eligible non-duplicate frame and each eligible duplicate-group winner is marked as a pick.

## Options

| Option | Default | Description |
|---|---:|---|
| `--profile general\|macro-nature` | `general` | Select technical scoring weights. |
| `--duplicate-window 1..100` | `8` | Number of preceding adjacent files checked for near duplicates. |
| `--duplicate-similarity 0.80..0.99` | `0.90` | Perceptual similarity threshold for duplicate grouping. |
| `--max-preview 800..4000` | `1600` | Maximum preview edge in pixels. |
| `--bracket-detection auto\|off` | `auto` | Enable or disable exposure/focus bracket detection. |
| `--copy-bracket-originals` | off | Copy full detected bracket originals into report subfolders. |
| `--export-xmp` | off | Export Lightroom-compatible rating sidecars under the report directory. |

## Profiles

### General

Uses whole-frame focus as the primary focus measure. Choose it for travel, events, portraits, landscapes, and mixed folders.

### Macro nature

Gives more weight to the central 60% of the frame. Choose it for insects, flowers, small animals, and close-up nature work. This is still a technical heuristic; visually verify the intended eye or body detail.

## Examples

General selection:

```bash
rawsift ~/Pictures/Trip --output ./trip-report
```

Macro and insect folder:

```bash
rawsift ~/Pictures/Insects \
  --output ./insect-report \
  --profile macro-nature
```

Long burst sequences:

```bash
rawsift ~/Pictures/Birds \
  --output ./bird-report \
  --duplicate-window 20
```

Create XMP recommendations without writing beside originals:

```bash
rawsift ~/Pictures/RAW \
  --output ./review \
  --export-xmp
```

Copy full bracket originals after explicitly deciding that the extra storage is acceptable:

```bash
rawsift ~/Pictures/HDR-and-Stacks \
  --output ./review \
  --copy-bracket-originals
```

## Review sequence

1. Open `summary.json` to confirm discovered, analyzed, failed, and bracket counts.
2. Open `report.html`.
3. Review exposure and focus groups before ordinary picks.
4. Verify every medium-confidence bracket group.
5. For each ordinary duplicate group, compare at least its top two frames.
6. Treat `reject` as a review candidate, not a deletion command.

## Labels

| Label | Meaning |
|---|---|
| `pick` | Strong automatic candidate among non-bracket frames. |
| `maybe` | Usable frame needing visual judgment. |
| `duplicate` | Lower-ranked member of an ordinary near-duplicate group. |
| `exposure-bracket` | Complete member of an HDR/exposure-blending sequence. |
| `focus-bracket` | Complete member of a focus-stacking sequence. |
| `reject` | Likely technical problem; still requires human confirmation. |

## Source safety

The normal workflow writes only inside the output directory. Source files are opened read-only. The program does not delete, move, rename, overwrite, or edit them. `--copy-bracket-originals` copies files and never removes the source.

