# Detection and scoring algorithm

[简体中文](ALGORITHM.zh-CN.md)

## Pipeline

1. Discover supported files recursively and keep deterministic filename order.
2. Extract a display preview without writing to the source.
3. Read available EXIF and maker-note metadata.
4. Compute technical and structural image features.
5. Detect exposure and focus bracket runs.
6. Exclude bracket members from ordinary duplicate grouping.
7. Score non-bracket candidates and assign conservative labels.
8. Generate grouped previews and review artifacts.

## Preview extraction

The decoder order is:

1. Pillow for ordinary image formats.
2. ExifTool preview tags when ExifTool is installed.
3. The largest valid embedded JPEG found in the RAW container.
4. rawpy when installed.
5. FFmpeg when installed.

The report records the decoder and preview dimensions. A small embedded preview is less reliable for subtle focus comparison than a full-resolution render.

## Technical metrics

### Focus

Focus is estimated from the variance of a luminance Laplacian. The raw value is log-scaled, then robustly normalized between the batch's 10th and 90th percentiles.

The macro profile also evaluates the central 60% crop. It combines 65% center focus and 35% whole-frame focus before the final technical score.

### Exposure

Exposure scoring penalizes extreme median luminance and substantial highlight or shadow clipping. The thresholds are deliberately conservative because low-key, high-key, silhouette, and night photographs may be intentional.

### Contrast

Contrast uses the luminance range between P5 and P95 and is normalized within the batch.

## Structural similarity

A 63-bit perceptual hash represents low-frequency frame structure. Color similarity is measured with normalized 16-bin histograms for each RGB channel. Ordinary duplicate grouping requires both strong perceptual similarity and strong color similarity inside a configurable adjacent-file window.

## Exposure bracket detection

A candidate run needs at least three adjacent, structurally similar frames. Detection prefers:

1. Camera AEB/bracket metadata.
2. At least three distinct EXIF exposure values with a meaningful EV span.
3. Stable composition with a systematic preview-luminance span when metadata is unavailable.

Exposure differences can change clipping and therefore perturb the perceptual hash. Candidate generation uses a slightly more permissive structural threshold than ordinary duplicate grouping, while classification still requires a clear exposure pattern.

## Focus bracket detection

Focus detection prefers:

1. Camera focus-shift or focus-bracket metadata.
2. At least three distinct recorded focus distances under stable exposure.
3. Stable structure and exposure with a substantial change in a 4×4 spatial focus signature.

The spatial signature standardizes Laplacian focus values across 16 image regions. A moving focus plane changes the relative sharpness pattern; uniform blur normally changes magnitude without moving the pattern.

Visual-only focus detection is marked medium confidence because subject motion, wind, or handheld reframing may produce similar evidence.

## Labels and grouping

Detected bracket members receive `exposure-bracket` or `focus-bracket` before technical reject rules are evaluated. They are never submitted to the ordinary duplicate union operation.

For remaining images, every non-duplicate image and the strongest technical member in each duplicate group becomes a `pick` unless it has a severe technical concern. There is no fixed pick-rate quota. Lower-ranked group members are labeled `duplicate`. Severe exposure or relative-focus concerns may receive `reject`, but this is always a review recommendation.

## Non-goals

The deterministic algorithm does not claim to recognize artistic merit, expression, gesture, storytelling, species, or exact eye focus. A vision-capable reviewer or photographer should make the final selection.

