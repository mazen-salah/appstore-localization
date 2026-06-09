# Screenshot pipeline internals

How `scripts/compose.py composite` turns a model-translated caption band into a
pixel-clean localized screenshot, and why each step exists. Read this when a
composite looks wrong and you need to tune it.

## The core problem
Image models cap output at ~1500px on the long edge. A full 1290×2796 screenshot
comes back smaller and has to be upscaled — soft text, soft phone UI. So we only
send the model the **caption band** (a short strip). Its ~1500px output is then a
*downscale* to the 1290px width = crisp. The phone mock-up is never sent to the
model, so it stays exactly as designed.

## Steps

### 1. Downscale-fit
The translated band is resized to the screenshot width with LANCZOS. Because the
band is short, this is virtually always a downscale → sharp glyph edges.

### 2. Additive-only median colour match
Models drift colour slightly (a coral can shift several RGB levels). We correct it
by shifting each channel so the band's **median** equals the original band's
median — i.e. align the dominant *background* colour.

> Do **not** scale by std/IQR ("Reinhard" transfer). On a band that is mostly one
> background colour with a little dark text, IQR scaling compresses the dynamic
> range and **erases the dark text**. Median shift (additive only) preserves
> contrast. This was the single nastiest bug while developing the pipeline.

### 3. Phase-correlation alignment
The model can shift the whole band by a few pixels. We compute the integer
(dy, dx) that best registers the band onto the original (FFT cross-power spectrum)
and roll it back, capped at ±12px. This keeps backgrounds (curves, blobs) aligned
so they stay pristine instead of ghosting.

### 4. The mask
We paint the model's band onto the original **only** where it matters:

```
mask = ( glyph_local_contrast  OR  raw_colour_change ) AND inside a text-line box
```

- **glyph local-contrast** = `|pixel − blur7(pixel)|` over a small threshold —
  catches letter strokes in both the original and the translation.
- **raw colour change** = `|translated − original| > thresh` — catches elements
  that *moved* (e.g. a highlight blob that shifts under right-to-left text, whose
  smooth interior has no local contrast) and the tail of longer source text the
  translation doesn't cover. Safe because step 2 keeps background colour matched,
  so plain background stays below threshold.
- **text-line bounding box** — group changed rows into lines, take each line's
  bounding box. This confines all painting to the caption, so curved shapes / the
  phone edge outside the caption are never touched, and there is no rectangular
  seam across a curved background.

Then the mask is dilated (MaxFilter) and feathered (GaussianBlur) for soft edges.

### 5. Inner-edge guard
The band's edge that faces the rest of the screenshot is zeroed for ~28 rows, so
crop-boundary local contrast and any clipped decoration (e.g. an arrow tip poking
into the band) never create a seam. Top-caption frames guard the bottom rows;
bottom-caption frames guard the top rows.

### 6. RGB flatten
Output is saved as RGB — **App Store Connect rejects screenshots with an alpha
channel**.

## Tuning
| Symptom | Knob |
| --- | --- |
| Faint ghost of the source text's tail | raise `--thresh` slightly, or tighten the band |
| Visible horizontal seam near the band edge | raise `--guard` |
| Text edges look soft | lower `--feather` (default 2) |
| A moved highlight blob leaves a colour ghost | already handled by the raw-colour term; ensure step 2/3 ran (check the "aligned band by…" log) |
| Dark text disappeared | you reintroduced std/IQR scaling — keep colour match additive-only |

## Per-frame band tips
- Top-caption frame → `--y0 0 --y1 <just past the subtitle, in clean background>`.
- Bottom-caption frame → `--y0 <just before the headline> --y1 <image height>`.
- Keep the band tight; exclude arrows and curved-shape boundaries when you can —
  the alignment + colour match will still reproduce them correctly if they fall
  inside, but tighter bands give crisper text.
