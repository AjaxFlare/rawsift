---
name: rawsift
description: Batch-cull camera RAW and ordinary image files, extract safe previews, detect exposure-bracketing and focus-bracketing sequences before near-duplicate bursts, identify technical problems, score candidates, and generate grouped folders, an HTML gallery, CSV, JSON, and contact sheets for visual review. Use when Codex needs to help select, shortlist, compare, rate, group, or triage NEF, DNG, CR2, CR3, ARW, RAF, ORF, RW2, PEF, SRW, JPEG, TIFF, PNG, or WebP photos, especially nature, insect, macro, HDR, focus stacking, travel, event, or burst photography.
---

# rawsift

Use deterministic analysis for the first pass and visual judgment for the final pass. Treat every automatic label as a recommendation, never as permission to delete a source file.

## Safety rules

- Never delete, move, rename, overwrite, or modify source photos.
- Write previews and reports only to a separate output directory.
- Never copy full bracket RAW originals unless the user explicitly requests it; grouped preview copies are safe defaults.
- Do not write XMP sidecars beside originals unless the user explicitly requests it.
- Describe `reject` results as technical rejection candidates. Require human confirmation before any destructive action.
- Report preview-decoding failures explicitly; never silently skip them.

## Workflow

1. Resolve the input file or folder and discover supported photos recursively.
2. Select `macro-nature` for insects, flowers, small animals, or close-up nature work; otherwise use `general`.
3. Run the bundled analyzer from this skill's directory:

   ```bash
   python3 "$SKILL_DIR/scripts/cull_photos.py" "$INPUT" --output "$OUTPUT" --profile macro-nature
   ```

4. Read `summary.json` and `analysis.csv`. Inspect `bracket-groups/exposure/` and `bracket-groups/focus/` before reviewing ordinary picks. Treat all members of a confirmed bracket group as a set; do not discard the darkest exposure frame or the frames focused away from the center.
5. Open every generated contact sheet with the image-viewing tool. Verify medium-confidence bracket groups visually. Exposure groups should retain stable composition while brightness or recorded exposure changes systematically. Focus groups should retain stable exposure and composition while the sharp plane moves across the subject.
6. Visually review at least all `pick` candidates and each ordinary duplicate group's highest-ranked two images. For macro photographs, prioritize focus on the insect's or animal's visible eye and critical body detail. For people, prioritize expression, open eyes, and gesture. For landscapes and travel, assess composition, timing, and distracting elements.
7. Override technical ranking or bracket classification in the written recommendation when visual evidence warrants it. Explain the reason briefly; do not pretend the script measured semantics it cannot measure.
8. Return a link to `report.html`, summarize ordinary picks plus exposure/focus bracket group counts, list decoding failures, and state that no original was changed.

## Command options

- `--profile general|macro-nature`: choose scoring weights.
- `--duplicate-window N`: compare each image with the preceding `N` images; use 8 for normal bursts and 20 for long bursts.
- `--duplicate-similarity 0.80..0.99`: lower values group more aggressively; keep 0.90 unless results show missed bursts.
- `--max-preview 800..4000`: longest preview edge. Use at least 1600 for focus review.
- `--bracket-detection auto|off`: detect exposure and focus bracket sequences before duplicate grouping. Keep `auto` unless the user asks to disable it.
- `--copy-bracket-originals`: copy detected bracket RAW originals into their group directories. Use only when the user explicitly requests full-file copies; grouped previews are created automatically.
- `--export-xmp`: generate optional Lightroom-compatible rating sidecars inside the report directory. Never copy them beside originals without an explicit user request.

The analyzer requires Pillow and NumPy. It can decode ordinary images directly, extract embedded JPEG previews from many RAW files, and optionally use ExifTool, rawpy, or FFmpeg when available.

## Interpreting results

- `pick`: strongest automatic candidates after duplicate grouping.
- `maybe`: usable images needing visual judgment.
- `duplicate`: lower-ranked alternative in a near-duplicate group; inspect expressions and exact focus before choosing.
- `exposure-bracket`: preserve the entire sequence for HDR or exposure blending; do not rank its dark and bright frames as ordinary rejects.
- `focus-bracket`: preserve the entire sequence for focus stacking; individual frames may be intentionally sharp in only one depth plane.
- `reject`: likely blur or severe exposure problem, but still requires visual confirmation.

Technical scores are relative to the current batch. Do not compare scores from separate runs as if they share an absolute scale. Read [references/scoring.md](references/scoring.md) only when calibrating thresholds, auditing a result, or explaining limitations.
