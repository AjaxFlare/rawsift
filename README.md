# rawsift

**Bracket-aware, non-destructive RAW photo culling.**

English | [简体中文](README.zh-CN.md)

[![Tests](https://github.com/AjaxFlare/rawsift/actions/workflows/tests.yml/badge.svg)](https://github.com/AjaxFlare/rawsift/actions/workflows/tests.yml)
[![Latest release](https://img.shields.io/github/v/release/AjaxFlare/rawsift)](https://github.com/AjaxFlare/rawsift/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

rawsift analyzes camera RAW files, identifies exposure and focus brackets, groups burst sequences, scores technical quality, and generates a reviewable HTML report—without modifying the originals.

It is designed for photographers who shoot RAW, bursts, HDR brackets, macro focus stacks, wildlife, nature, travel, or events.

## Key features

- Supports NEF, NRW, DNG, CR2, CR3, ARW, RAF, ORF, RW2, PEF, SRW, JPEG, TIFF, PNG, and WebP inputs.
- Detects exposure brackets from EXIF settings or stable-composition brightness steps.
- Detects focus brackets from camera metadata, focus-distance changes, or spatial focus-plane movement.
- Protects every detected bracket member from ordinary duplicate or reject demotion.
- Finds near-duplicate burst frames with perceptual and color similarity.
- Scores focus, central focus, exposure, clipping, and contrast relative to the current batch.
- Provides `general` and `macro-nature` scoring profiles.
- Generates an HTML gallery, CSV, JSON, contact sheets, grouped bracket previews, and optional Lightroom-compatible XMP sidecars.
- Never deletes, moves, renames, overwrites, or edits source photos.

## Download for Windows

**[Download rawsift 0.2.0 for Windows x64](https://github.com/AjaxFlare/rawsift/releases/download/v0.2.0/rawsift-0.2.0-windows-x64.exe)**

The portable executable includes Python and all required application dependencies:

1. Download and double-click `rawsift-0.2.0-windows-x64.exe`.
2. Keep the console window open while using rawsift.
3. The application opens in your default browser at `http://127.0.0.1:8765`.
4. Close the console window to stop the local application.

No installation or Python environment is required. Job data is stored under `%USERPROFILE%\.rawsift\jobs`. The executable is currently unsigned, so Windows SmartScreen may show an unknown-publisher warning. The release page includes the SHA-256 checksum and validation details.

See [all releases](https://github.com/AjaxFlare/rawsift/releases) for other versions and release notes.

## Install from source / CLI quick start

```bash
git clone https://github.com/AjaxFlare/rawsift.git
cd rawsift
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e .

rawsift /path/to/photos \
  --output ./rawsift-report \
  --profile macro-nature
```

Open `rawsift-report/report.html` after the run.

## Local application + external vision API

rawsift also includes a local browser application for Windows and macOS. The deterministic pass, RAW decoding, bracket detection, and report generation stay on your computer. An optional OpenAI-compatible vision provider can review compressed JPEG previews for composition, subject clarity, expression, timing, and distractions.

Windows users can run the portable executable above. For macOS, development, or source-based installation, use:

```bash
python -m pip install -e ".[app,raw]"
rawsift-app
```

The application opens at `http://127.0.0.1:8765`. Configure the provider in **API Settings**. You can use environment variables instead of entering credentials in the interface:

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export RAWSIFT_VISION_MODEL="gpt-5.6"
rawsift-app
```

The server binds only to the local computer. API keys are not written to job files or logs. A single AI review sends at most eight bounded JPEG previews; RAW originals are never sent to the provider.

## Use as a ChatGPT/Codex Skill

Clone or copy the complete repository into your personal skills environment. The required Skill files are included at the repository root:

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/cull_photos.py`
- `references/scoring.md`

Invoke it with a request such as:

> Use $rawsift to cull this RAW folder in macro-nature mode. Keep about 25%, and group exposure and focus brackets separately.

## Bracket handling

Bracket detection runs before duplicate detection.

| Sequence | Primary evidence | Output | Culling behavior |
|---|---|---|---|
| Exposure bracket | Exposure EXIF/AEB metadata; otherwise stable composition with systematic brightness steps | `bracket-groups/exposure/E001/` | Preserve the complete sequence |
| Focus bracket | Focus-shift metadata or focus distance; otherwise stable exposure with a moving sharp region | `bracket-groups/focus/F001/` | Preserve the complete sequence |
| Ordinary burst | Perceptual hash and color similarity | Duplicate group `G001` | Recommend the strongest technical frame |

Visually inferred bracket groups are marked with confidence. Medium-confidence groups should always be reviewed.

## Output

```text
rawsift-report/
├── report.html
├── summary.json
├── analysis.json
├── analysis.csv
├── previews/
├── contact-sheets/
├── bracket-groups/
│   ├── exposure/E001/
│   └── focus/F001/
└── xmp-sidecars/          # only with --export-xmp
```

Grouped bracket directories contain preview copies and a machine-readable manifest. Full RAW originals are copied only when `--copy-bracket-originals` is explicitly supplied.

## Optional RAW decoders

Pillow and NumPy are required. The tool can extract embedded JPEG previews from many RAW files without extra software. It also uses these decoders when available:

1. ExifTool
2. embedded JPEG preview
3. rawpy
4. FFmpeg

Install rawpy support with:

```bash
python -m pip install -e ".[raw]"
```

## Documentation

- [Local application and external API](docs/APP.md)
- [本地软件与外接 API](docs/APP.zh-CN.md)
- [Full usage guide](docs/USAGE.md)
- [Detection and scoring algorithm](docs/ALGORITHM.md)
- [中文使用指南](docs/USAGE.zh-CN.md)
- [中文算法说明](docs/ALGORITHM.zh-CN.md)

## Safety and limitations

- All scores are relative to the current batch; do not compare scores across separate runs.
- Intentional blur, silhouettes, high-key, and low-key images can be penalized.
- Subject motion or handheld reframing can resemble focus-plane movement.
- The deterministic pass cannot judge expression, storytelling, insect-eye focus, or artistic value. Final selection remains a visual decision.
- Automatic labels are recommendations, never deletion instructions.

## License

[MIT](LICENSE)
