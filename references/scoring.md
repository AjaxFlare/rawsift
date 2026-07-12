# Scoring and calibration

## Metrics

- Focus: variance of a luminance Laplacian, ranked robustly within the current batch.
- Center focus: the same measure within the central 60% of the frame. The `macro-nature` profile gives this more weight.
- Exposure: penalties for extreme median luminance and clipped highlight or shadow fractions.
- Contrast: robust P95 minus P5 luminance range, ranked within the batch.
- Near duplicates: perceptual-hash similarity plus color-histogram similarity, evaluated inside a filename/time-adjacent window.
- Exposure brackets: camera bracket metadata or stable adjacent composition with at least three systematically different recorded exposures or preview luminance levels.
- Focus brackets: camera focus-shift metadata, recorded focus-distance changes, or stable adjacent composition and exposure with a substantial change in the 4×4 spatial focus signature.

## Default weighting

- `general`: 65% whole-frame focus, 25% exposure, 10% contrast.
- `macro-nature`: focus component is 65% center focus and 35% whole-frame focus; the combined score is then weighted 75% focus, 20% exposure, and 5% contrast.

## Important limitations

- A high score means technically strong relative to the batch, not artistically superior.
- Intentional motion blur, low-key scenes, silhouettes, and high-key scenes may be penalized.
- Background texture can inflate whole-frame focus. Inspect the intended subject at useful magnification.
- The deterministic analyzer does not identify insect eyes, facial expressions, gestures, or storytelling value.
- Embedded RAW previews may be smaller or more processed than the sensor data. The report records decoder method and preview dimensions.
- Perceptual grouping can miss bursts with substantial subject movement or group similar compositions that are not true duplicates.
- Visual focus-bracket inference is deliberately conservative. Subject movement, wind, or handheld reframing can imitate a shifting focus plane, so medium-confidence groups require visual review.
- Bracket detection runs before duplicate detection. Every detected bracket member is excluded from automatic duplicate demotion.

## Calibration

- Increase `--duplicate-window` before lowering the similarity threshold.
- Lower `--duplicate-similarity` in steps of 0.02 only after reviewing false negatives.
- Raise `--max-preview` when embedded previews are large enough and focus differences are subtle.
- Keep automatic rejection conservative. Prefer adding a visual warning over declaring an image unusable.
